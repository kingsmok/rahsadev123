"""محصولات ویترین‌های صفحهٔ اصلی (product.ProductShowcase)."""
from django.db import models
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Product, ProductShowcase


def _with_discount(queryset):
    # Templates read ``product.discount`` (percent) on every card.
    return queryset.annotate(
        discount=models.Case(
            models.When(
                old_price__gt=models.F('price'),
                then=models.ExpressionWrapper(
                    (models.F('old_price') - models.F('price')) * 100 / models.F('old_price'),
                    output_field=models.IntegerField(),
                ),
            ),
            default=models.Value(0),
            output_field=models.IntegerField(),
        )
    )


def source_queryset(source):
    queryset = _with_discount(Product.objects.filter(status='published'))
    if source == 'popular':
        return queryset.order_by('-views', '-created_at')
    if source == 'best_selling':
        return queryset.order_by('-sales_count', '-created_at')
    if source == 'featured':
        return queryset.filter(is_featured=True).order_by('-created_at')
    if source == 'discounted':
        return queryset.filter(old_price__isnull=False, old_price__gt=models.F('price'), discount__gt=0) \
            .order_by('-discount', '-created_at')
    return queryset.order_by('-created_at')


def _storefront(queryset):
    return queryset.select_related('digital_asset').prefetch_related('brand')


def showcase_products(placement, default_source, default_limit):
    """Return ``(showcase_or_None, products)`` for a home-page placement.

    Without a configured row the previous behaviour is kept.  An inactive or
    expired showcase returns no products, which hides its section.
    """
    showcase = ProductShowcase.objects.filter(placement=placement).first()
    if showcase is None:
        return None, list(_storefront(source_queryset(default_source))[:default_limit])
    if not showcase.is_active or (showcase.ends_at and showcase.ends_at <= timezone.now()):
        return showcase, []
    if showcase.source == 'manual':
        manual = (
            _with_discount(Product.objects.filter(status='published', showcase_items__showcase=showcase))
            .annotate(showcase_order=Coalesce('showcase_items__order', 0))
            .order_by('showcase_order', 'showcase_items__id')
        )
        products = list(_storefront(manual)[:showcase.limit])
        if products:
            return showcase, products
        return showcase, list(_storefront(source_queryset('latest'))[:showcase.limit])
    return showcase, list(_storefront(source_queryset(showcase.source))[:showcase.limit])
