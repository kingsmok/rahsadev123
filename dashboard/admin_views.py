from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.shortcuts import render
from cart.models import Order
from product.models import Product
from blog.models import Article
from payments.models import PaymentTransaction
from services.models import ServicePackage, ServiceRequest, PortfolioItem
from payments.models import GatewaySettings
from core.models import Redirect


@staff_member_required
def admin_home(request):
    context = {
        'orders_count': Order.objects.count(),
        'sales_total': Order.objects.filter(status='paid').aggregate(total=Sum('final_price'))['total'] or 0,
        'products_count': Product.objects.count(),
        'articles_count': Article.objects.count(),
        'recent_orders': Order.objects.select_related('user').order_by('-created_at')[:8],
        'recent_payments': PaymentTransaction.objects.select_related('order').order_by('-created_at')[:6],
        'new_service_requests': ServiceRequest.objects.filter(status='new').count(),
        'service_requests': ServiceRequest.objects.order_by('-created_at')[:6],
        'packages_count': ServicePackage.objects.count(),
        'gateways': GatewaySettings.objects.all(),
        'redirects_count': Redirect.objects.filter(is_active=True).count(),
        'portfolio_count': PortfolioItem.objects.count(),
    }
    return render(request, 'dashboard/admin_home.html', context)
