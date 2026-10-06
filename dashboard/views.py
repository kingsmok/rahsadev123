from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from accounts.models import Profile
from cart.models import Order, CartItem, Cart
from product.models import Product, ProductComment
from downloads.models import DownloadToken
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from .models import Wishlist, Address, Notification
from .forms import AddressForm, ProfileEditForm
from django.db.models import Q
from accounts.forms import ChangePasswordForm
from django.contrib.auth import update_session_auth_hash
from django.views.decorators.http import require_POST
from django.contrib import messages


def get_pages_to_show(current_page, total_pages):
    if total_pages <= 3:
        return list(range(1, total_pages + 1))

    if current_page <= 2:
        return [1, 2, 3, '...', total_pages]

    if current_page >= total_pages - 1:
        return [1, '...', total_pages - 2, total_pages - 1, total_pages]

    return [1, '...', current_page - 1, current_page, current_page + 1, '...', total_pages]


@login_required
def home(request):
    user = request.user
    profile = Profile.objects.get(user=user)

    # User account statistics
    current_cart_items = CartItem.objects.filter(cart__user=user).count()
    delivered_orders = Order.objects.filter(user=user, status='delivered').count()
    cancelled_orders = Order.objects.filter(user=user, status='cancelled').count()
    comments_count = ProductComment.objects.filter(author=user).count()
    wishlist_products_count = Wishlist.objects.filter(user=user).count()
    user_notifications_count = Notification.objects.filter(Q(is_for_all_users=True) | Q(users=user), is_active=True).count()

    recent_orders = Order.objects.filter(user=user).order_by('-created_at')[:5]
    popular_products = Product.objects.filter(status='published', stock_count__gt=0).order_by('-views')[:10]

    context = {
        'profile': profile,

        'current_cart_items': current_cart_items,
        'delivered_orders': delivered_orders,
        'cancelled_orders': cancelled_orders,
        'comments_count': comments_count,
        'wishlist_products_count': wishlist_products_count,
        'user_notifications_count': user_notifications_count,

        'recent_orders': recent_orders,
        'popular_products': popular_products,
    }
    return render(request, 'dashboard/home.html', context)


@login_required
def order_list(request):
    user = request.user
    profile = Profile.objects.get(user=user)
    orders = Order.objects.filter(user=user).order_by('-created_at')

    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(orders, 6)
    object_list = paginator.get_page(page_number)
    pages_to_show = get_pages_to_show(object_list.number, paginator.num_pages)

    context = {
        'profile': profile,

        'orders': object_list,
        'pages_to_show': pages_to_show,
    }
    return render(request, 'dashboard/orders.html', context)


@login_required
def order_detail(request, order_number):
    user = request.user
    profile = Profile.objects.get(user=user)
    order = get_object_or_404(Order, order_number=order_number, user=user)

    items = []
    items_data = order.items_data or {}
    raw_items = items_data.get('items', []) if isinstance(items_data, dict) else items_data
    for item_data in raw_items:
        product_id = item_data.get('product_id') or item_data.get('product')
        # یکسان‌سازی کلیدها برای قالب فاکتور
        unit_price = item_data.get('unit_price') or item_data.get('price') or 0
        item_data['unit_price'] = unit_price
        item_data.setdefault('total_price', unit_price * item_data.get('quantity', 1))
        item_data.setdefault('product_title', item_data.get('title', ''))
        try:
            product = Product.objects.get(pk=product_id)
            item_data['product_obj'] = product
            items.append(item_data)
        except (Product.DoesNotExist, TypeError, ValueError):
            continue

    # توکن‌های دانلود این سفارش (فایل‌های دیجیتال)
    download_tokens = DownloadToken.objects.filter(order=order, user=user).select_related('product')

    context = {
        'profile': profile,

        'order': order,
        'items': items,
        'download_tokens': download_tokens,
    }
    return render(request, 'dashboard/order_detail.html', context)


@login_required
def my_downloads(request):
    """فایل‌های خریداری‌شده کاربر به همراه لینک دانلود امن."""
    user = request.user
    profile = Profile.objects.get(user=user)
    tokens = DownloadToken.objects.filter(user=user).select_related('product', 'order').order_by('-created_at')

    page_number = request.GET.get('page')
    paginator = Paginator(tokens, 10)
    object_list = paginator.get_page(page_number)
    pages_to_show = get_pages_to_show(object_list.number, paginator.num_pages)

    context = {
        'profile': profile,
        'tokens': object_list,
        'pages_to_show': pages_to_show,
    }
    return render(request, 'dashboard/my_downloads.html', context)


@login_required
def orders_delivered(request):
    user = request.user
    profile = Profile.objects.get(user=user)
    orders = Order.objects.filter(user=user, status='delivered').order_by('-created_at')

    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(orders, 6)
    object_list = paginator.get_page(page_number)
    pages_to_show = get_pages_to_show(object_list.number, paginator.num_pages)

    context = {
        'profile': profile,

        'orders': object_list,
        'pages_to_show': pages_to_show,
    }
    return render(request, 'dashboard/orders_delivered.html', context)


@login_required
def cart_summary(request):
    user = request.user
    profile = Profile.objects.get(user=user)
    cart, created = Cart.objects.get_or_create(user=user)
    cart_items = cart.items.all()

    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(cart_items, 6)
    object_list = paginator.get_page(page_number)
    pages_to_show = get_pages_to_show(object_list.number, paginator.num_pages)

    context = {
        'profile': profile,

        'cart_items': object_list,
        'pages_to_show': pages_to_show,
    }
    return render(request, 'dashboard/cart_summary.html', context)


@login_required
def orders_cancelled(request):
    user = request.user
    profile = Profile.objects.get(user=user)
    orders = Order.objects.filter(user=user, status='cancelled').order_by('-created_at')

    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(orders, 6)
    object_list = paginator.get_page(page_number)
    pages_to_show = get_pages_to_show(object_list.number, paginator.num_pages)

    context = {
        'profile': profile,

        'orders': object_list,
        'pages_to_show': pages_to_show,
    }
    return render(request, 'dashboard/orders_cancelled.html', context)


@login_required
def orders_return(request):
    user = request.user
    profile = Profile.objects.get(user=user)

    def respond(success, message):
        """Use JSON for the enhanced form and a useful redirect without JavaScript."""
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': success, 'message': message})
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect('dashboard:orders_return')

    if request.method == 'POST':
        order_number = (request.POST.get('order_number') or '').strip()
        if not order_number:
            return respond(False, 'لطفاً کد سفارش را وارد کنید.')

        try:
            order = Order.objects.get(order_number=order_number, user=user)
        except Order.DoesNotExist:
            return respond(False, 'سفارشی با این شماره یافت نشد.')

        if not profile.card_number:
            return respond(False, 'برای لغو سفارش باید شماره کارت خود را در پروفایل ثبت کنید.')

        time_since_order = timezone.now() - order.created_at
        if time_since_order.total_seconds() > 48 * 3600:
            return respond(False, 'زمان لغو سفارش گذشته است. فقط تا 48 ساعت پس از ثبت سفارش امکان لغو وجود دارد.')

        # FileMarket delivers digital purchases from the account dashboard; a
        # legacy physical-shipping state must never be presented as cancellable.
        if order.status not in ['paid', 'pending']:
            return respond(False, 'این سفارش قابل لغو نیست. فقط سفارش‌های پرداخت‌شده یا در انتظار پرداخت قابل بررسی هستند.')

        order.status = 'processing'
        order.save(update_fields=['status', 'updated_at'])
        return respond(True, 'درخواست لغو سفارش شما ثبت شد. پس از بررسی، نتیجه در بخش اعلان‌ها اطلاع‌رسانی می‌شود.')

    context = {
        'profile': profile,
    }
    return render(request, 'dashboard/orders_return.html', context)


@login_required
def wishlist_products(request):
    user = request.user
    profile = Profile.objects.get(user=user)
    wishlist_items = Wishlist.objects.filter(user=user).select_related('product').order_by('-created_at')

    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(wishlist_items, 6)
    object_list = paginator.get_page(page_number)
    pages_to_show = get_pages_to_show(object_list.number, paginator.num_pages)

    context = {
        'profile': profile,

        'wishlist_items': object_list,
        'pages_to_show': pages_to_show,
    }
    return render(request, 'dashboard/wishlist_products.html', context)


@login_required
@require_POST
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)

    if created:
        message = "محصول به لیست علاقه ‌مندی‌ ها اضافه شد."
        status = 'success'
    else:
        message = "این محصول قبلاً در لیست علاقه‌ مندی‌ های شما وجود دارد."
        status = 'info'

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': status, 'message': message})
    return redirect('product:product_list')


@login_required
@require_POST
def remove_from_wishlist(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    wishlist_item = get_object_or_404(Wishlist, user=request.user, product=product)
    wishlist_item.delete()

    message = "محصول از لیست علاقه‌ مندی‌ ها حذف شد."
    status = 'success'

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': status, 'message': message})
    return redirect('dashboard:wishlist_products')


@login_required
def user_addresses(request):
    user = request.user
    profile = Profile.objects.get(user=user)
    addresses = Address.objects.filter(user=user).order_by('-created_at')

    show_address_modal = False
    if request.method == 'POST':
        if 'delete_address' in request.POST:
            address_id = request.POST.get('delete_address')
            address = get_object_or_404(Address, pk=address_id, user=user)
            address.delete()
            messages.success(request, 'آدرس با موفقیت حذف شد.')
            return redirect('dashboard:user_addresses')

        if 'set_default' in request.POST:
            address_id = request.POST.get('set_default')
            address = get_object_or_404(Address, pk=address_id, user=user)
            address.is_default = True
            address.save()
            messages.success(request, 'آدرس پیش‌فرض شما به‌روزرسانی شد.')
            return redirect('dashboard:user_addresses')

        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = user
            address.save()
            messages.success(request, 'آدرس جدید با موفقیت ثبت شد.')
            return redirect('dashboard:user_addresses')
        show_address_modal = True
    else:
        form = AddressForm()

    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(addresses, 6)
    object_list = paginator.get_page(page_number)
    pages_to_show = get_pages_to_show(object_list.number, paginator.num_pages)

    context = {
        'profile': profile,

        'addresses': object_list,
        'form': form,
        'show_address_modal': show_address_modal,
        'pages_to_show': pages_to_show,
    }
    return render(request, 'dashboard/user_addresses.html', context)


@login_required
def notifications_list(request):
    user = request.user
    profile = Profile.objects.get(user=user)

    Notification.delete_expired_notifications()

    now = timezone.now()
    notifications = Notification.objects.filter(
        is_active=True
    ).filter(
        Q(is_for_all_users=True) | Q(users=user)
    ).filter(
        Q(expiration_date__isnull=True) | Q(expiration_date__gte=now)
    ).distinct().order_by('-created_at')

    context = {
        'profile': profile,

        'notifications': notifications,
    }
    return render(request, 'dashboard/notifications_list.html', context)


@login_required
def user_profile(request):
    user = request.user
    profile = Profile.objects.get(user=user)

    context = {
        'profile': profile,
    }
    return render(request, 'dashboard/user_profile.html', context)


@login_required
def edit_profile(request, username):
    """Edit only the authenticated user's profile.

    The username remains in the historical URL for compatibility, but must never
    be used to select another customer's profile.
    """
    user = request.user
    profile = get_object_or_404(Profile, user=user)
    if username != user.username:
        messages.error(request, 'شما فقط می‌توانید اطلاعات حساب خودتان را ویرایش کنید.')
        return redirect('dashboard:user_profile')

    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            updated_profile = form.save()
            # Keep Django's canonical user data in sync with the profile shown
            # throughout the storefront and admin panel.
            user.first_name = updated_profile.first_name
            user.last_name = updated_profile.last_name
            user.email = updated_profile.email
            user.save(update_fields=['first_name', 'last_name', 'email'])
            messages.success(request, 'اطلاعات حساب کاربری شما ذخیره شد.')
            return redirect('dashboard:user_profile')
    else:
        form = ProfileEditForm(instance=profile)

    return render(request, 'dashboard/edit_profile.html', {'profile': profile, 'form': form})


@login_required
def change_password(request):
    user = request.user
    profile = Profile.objects.get(user=user)

    if request.method == 'POST':
        form = ChangePasswordForm(request.POST, user=user)
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password'])
            user.save(update_fields=['password'])
            # Preserve the current session after a successful password change.
            update_session_auth_hash(request, user)
            messages.success(request, 'رمز عبور شما با موفقیت تغییر یافت.')
            return redirect('dashboard:user_profile')
    else:
        form = ChangePasswordForm(user=user)

    return render(request, 'dashboard/change_password.html', {'profile': profile, 'form': form})
