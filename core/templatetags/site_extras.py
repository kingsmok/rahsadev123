"""تگ‌های قالبِ اجزای مشترک فروشگاه: شبکه‌های اجتماعی، بلوک‌های HTML و مگامنو."""
from django import template
from django.core.cache import cache
from django.db.models import Count, Q
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def asset(path):
    """Like ``{% static %}`` but with a content-hash ``?v=`` so updated CSS/JS is never served stale."""
    from core.assets import asset_url

    return asset_url(path)

MEGA_MENU_CACHE_VERSION_KEY = 'fm.megamenu.version'
MEGA_MENU_PRODUCTS_PER_CATEGORY = 4


@register.inclusion_tag('includes/social_icons.html', takes_context=True)
def social_icons(context, variant='footer', title=''):
    links = context.get('social_links') or []
    return {
        'links': links,
        'global_links': [link for link in links if link['group'] == 'global'],
        'iran_links': [link for link in links if link['group'] == 'iran'],
        'variant': variant,
        'title': title,
    }


@register.simple_tag
def html_blocks(placement):
    """Active staff-authored HTML blocks for a placement (raw HTML by design)."""
    from core.models import HtmlBlock

    try:
        blocks = list(HtmlBlock.objects.filter(placement=placement, is_active=True))
    except Exception:  # tables missing during a first migrate
        return ''
    if not blocks:
        return ''
    parts = []
    for block in blocks:
        wrapper = 'fm-html-block fm-html-block--full' if block.full_width else 'fm-html-block container'
        parts.append(f'<div class="{wrapper}" data-html-block="{block.pk}">{block.html}</div>')
    return mark_safe(''.join(parts))


def mega_menu_version():
    version = cache.get(MEGA_MENU_CACHE_VERSION_KEY)
    if version is None:
        version = 1
        cache.set(MEGA_MENU_CACHE_VERSION_KEY, version, None)
    return version


def bump_mega_menu_version(*args, **kwargs):
    try:
        cache.incr(MEGA_MENU_CACHE_VERSION_KEY)
    except ValueError:
        cache.set(MEGA_MENU_CACHE_VERSION_KEY, 2, None)


def mega_menu_data():
    """Categories with product counts and a few products each (cached, versioned)."""
    from product.models import Product, ProductCategory

    key = f'fm.megamenu.data.v{mega_menu_version()}'
    data = cache.get(key)
    if data is not None:
        return data
    # ``Product.category`` is many-to-many with related_name «categories».
    published = Q(categories__status='published')
    categories = list(
        ProductCategory.objects.filter(show_in_menu=True)
        .annotate(product_count=Count('categories', filter=published, distinct=True))
        .order_by('menu_order', 'title')
    )
    data = []
    for category in categories:
        products = list(
            Product.objects.filter(status='published', category=category)
            .order_by('-is_featured', '-sales_count', '-created_at')
            .only('id', 'pid', 'slug', 'title', 'price', 'old_price', 'image')[:MEGA_MENU_PRODUCTS_PER_CATEGORY]
        )
        data.append({
            'id': category.pk,
            'title': category.title,
            'slug': category.slug,
            'icon': category.icon,
            'image': category.image.url if category.image else '',
            'description': category.short_description,
            'count': category.product_count,
            'products': [
                {
                    'title': product.title,
                    'pid': product.pid,
                    'slug': product.slug,
                    'price': product.price,
                    'old_price': product.old_price if (product.old_price and product.old_price > product.price) else None,
                    'discount': product.discount_percentage(),
                    'image': product.image.url if product.image else '',
                }
                for product in products
            ],
        })
    cache.set(key, data, 60 * 30)
    return data


@register.inclusion_tag('includes/mega_menu.html', takes_context=True)
def mega_menu(context, variant='desktop'):
    try:
        categories = mega_menu_data()
    except Exception:
        categories = []
    return {'mega_categories': categories, 'variant': variant, 'request': context.get('request')}


@register.simple_tag(takes_context=True)
def staff_edit_link(context, target, label='تنظیم این بخش', query=''):
    """A small "edit this section" shortcut, rendered only for staff who may edit it.

    ``target`` is a model instance (links to its change page) or an
    ``'app_label.model'`` string (links to the changelist, optionally filtered
    by ``query``).  Anonymous visitors and customers never get any markup.
    """
    request = context.get('request')
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and user.is_active and user.is_staff) or not target:
        return ''
    if isinstance(target, str):
        try:
            app_label, model_name = target.lower().split('.')
        except ValueError:
            return ''
        pk = None
    else:
        app_label, model_name, pk = target._meta.app_label, target._meta.model_name, target.pk
    if not user.has_perm(f'{app_label}.change_{model_name}'):
        return ''
    try:
        if pk is not None:
            url = reverse(f'admin:{app_label}_{model_name}_change', args=[pk])
        else:
            url = reverse(f'admin:{app_label}_{model_name}_changelist')
    except NoReverseMatch:
        return ''
    if query:
        url = f'{url}?{query}'
    return format_html(
        '<a class="fm-staff-edit" href="{}" title="این دکمه فقط برای مدیر نمایش داده می‌شود">'
        '<i class="fa fa-pen" aria-hidden="true"></i> {}</a>',
        url, label,
    )
