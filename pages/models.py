from django.db import models
from ckeditor_uploader.fields import RichTextUploadingField
class StaticPage(models.Model):
    title=models.CharField(max_length=200, verbose_name='عنوان')
    slug=models.SlugField(max_length=220, unique=True, allow_unicode=True)
    summary=models.CharField(max_length=160, blank=True, verbose_name='توضیحات سئو')
    content=RichTextUploadingField(verbose_name='محتوا')
    is_published=models.BooleanField(default=True)
    updated_at=models.DateTimeField(auto_now=True)

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
                pass
        super().save(*args, **kwargs)
    class Meta:
        verbose_name = 'صفحه'
        verbose_name_plural = 'صفحات'
        ordering = ['title']
    def __str__(self): return self.title
