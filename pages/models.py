import logging

from django.db import models
from django_ckeditor_5.fields import CKEditor5Field

from core.custom_html import CustomHtmlMixin

logger = logging.getLogger(__name__)


class StaticPage(CustomHtmlMixin, models.Model):
    LAYOUTS = (
        ('sidebar', 'استاندارد — محتوا همراه منوی کناری صفحات راهنما'),
        ('wide', 'تمام‌عرض — محتوا در یک کادر پهن، بدون منوی کناری'),
        ('narrow', 'متن باریک — مناسب مطالب طولانی و خوانا'),
        ('landing', 'لندینگ — بدون سربرگ و کادر؛ مناسب صفحه‌های ساخته‌شده با کد HTML'),
    )

    title=models.CharField(max_length=200, verbose_name='عنوان')
    slug=models.SlugField(max_length=220, unique=True, allow_unicode=True, verbose_name='نامک')
    summary=models.CharField(max_length=160, blank=True, verbose_name='توضیحات سئو')
    layout = models.CharField(max_length=20, choices=LAYOUTS, default='sidebar', verbose_name='چیدمان صفحه')
    show_page_head = models.BooleanField(default=True, verbose_name='نمایش سربرگ (عنوان و مسیر صفحه)',
                                         help_text='در چیدمان «لندینگ» سربرگ نمایش داده نمی‌شود.')
    # در صفحه‌های ساخته‌شده فقط با کد HTML، محتوای ویرایشگر می‌تواند خالی بماند.
    content=CKEditor5Field(config_name='default', blank=True, verbose_name='محتوا')
    is_published=models.BooleanField(default=True, verbose_name='منتشر شده')
    updated_at=models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')

    @property
    def displays_page_head(self):
        return self.show_page_head and self.layout != 'landing'

    def save(self, *args, **kwargs):
        """ریدایرکت خودکار ۳۰۱ هنگام تغییر نامک صفحه (حفظ اعتبار سئو)."""
        from core.models import Redirect
        if self.pk:
            try:
                old_slug = StaticPage.objects.filter(pk=self.pk).values_list('slug', flat=True).first()
                if old_slug and old_slug != self.slug:
                    # جلوگیری از حلقه: ریدایرکت معکوس قبلی حذف شود
                    Redirect.objects.filter(old_path=f'/pages/{self.slug}/').delete()
                    Redirect.objects.update_or_create(
                        old_path=f'/pages/{old_slug}/',
                        defaults={
                            'new_path': f'/pages/{self.slug}/',
                            'status_code': '301',
                            'is_active': True,
                            'note': 'تغییر نامک صفحه: ' + str(self.title),
                        },
                    )
            except Exception:
                # Saving the page must never fail because the SEO redirect could
                # not be recorded, but the failure must not be silent either.
                logger.exception('ثبت ریدایرکت ۳۰۱ برای تغییر نامک صفحه انجام نشد.')
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'صفحه'
        verbose_name_plural = 'صفحات'
        ordering = ['title']
    def __str__(self): return self.title
