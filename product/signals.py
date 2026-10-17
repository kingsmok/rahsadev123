"""باطل‌کردن کش مگامنو با هر تغییر محصول یا دسته‌بندی."""
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from core.templatetags.site_extras import bump_mega_menu_version

from .models import Product, ProductCategory


@receiver(post_save, sender=Product, dispatch_uid='megamenu_product_saved')
@receiver(post_delete, sender=Product, dispatch_uid='megamenu_product_deleted')
@receiver(post_save, sender=ProductCategory, dispatch_uid='megamenu_category_saved')
@receiver(post_delete, sender=ProductCategory, dispatch_uid='megamenu_category_deleted')
def _invalidate_mega_menu(sender, raw=False, **kwargs):
    if not raw:
        bump_mega_menu_version()


@receiver(m2m_changed, sender=Product.category.through, dispatch_uid='megamenu_product_categories')
def _invalidate_on_category_change(sender, action, **kwargs):
    if action in ('post_add', 'post_remove', 'post_clear'):
        bump_mega_menu_version()
