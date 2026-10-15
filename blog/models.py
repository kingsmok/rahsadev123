from django.db import models
from core.thumbnails import admin_thumbnail
from django.contrib.auth.models import User
from django_ckeditor_5.fields import CKEditor5Field

from accounts.roles import author_choices
from core.custom_html import CustomHtmlMixin


STATUS = (
    ('draft', 'پیش‌نویس'),
    ('published', 'منتشر شده'),
)


class Category(models.Model):
    title = models.CharField(max_length=100, unique=True, verbose_name='عنوان دسته بندی')
    slug = models.SlugField(max_length=100, unique=True, allow_unicode=True, verbose_name='نامک')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    class Meta:
        verbose_name = 'دسته بندی'
        verbose_name_plural = 'دسته بندی ها'
        ordering = ['title']

    def __str__(self):
        return self.title


class Tag(models.Model):
    title = models.CharField(max_length=80, unique=True, verbose_name='برچسب')
    slug = models.SlugField(max_length=100, unique=True, allow_unicode=True)
    def __str__(self): return self.title


class Article(CustomHtmlMixin, models.Model):
    # فقط مدیران و کاربرانِ گروه «نویسندگان» (accounts.roles).
    author = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to=author_choices,
                               verbose_name='نویسنده مقاله')
    category = models.ManyToManyField(Category, related_name='articles', verbose_name='دسته بندی مربوطه')
    tags = models.ManyToManyField(Tag, blank=True, related_name='articles', verbose_name='برچسب‌ها')
    title = models.CharField(max_length=200, unique=True, verbose_name='عنوان مقاله')
    slug = models.SlugField(max_length=200, unique=True, allow_unicode=True, verbose_name='نامک')
    description = CKEditor5Field(config_name='default', verbose_name='متن مقاله')
    image = models.ImageField(upload_to='articles/', blank=True, null=True, verbose_name='تصویر مقاله')
    status = models.CharField(choices=STATUS, max_length=10, verbose_name='وضعیت')
    views = models.IntegerField(default=0, editable=False, verbose_name='بازدید')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')
    meta_title = models.CharField(max_length=70, blank=True, verbose_name='عنوان سئو')
    meta_description = models.CharField(max_length=160, blank=True, verbose_name='توضیحات سئو')
    canonical_url = models.URLField(blank=True, verbose_name='آدرس canonical')

    def save(self, *args, **kwargs):
        """ریدایرکت خودکار ۳۰۱ هنگام تغییر نامک مقاله (حفظ اعتبار سئو)."""
        from core.models import Redirect
        if self.pk:
            try:
                old_slug = Article.objects.filter(pk=self.pk).values_list('slug', flat=True).first()
                if old_slug and old_slug != self.slug:
                    # جلوگیری از حلقه: ریدایرکت معکوس قبلی حذف شود
                    Redirect.objects.filter(old_path=f'/blog/{self.slug}/').delete()
                    Redirect.objects.update_or_create(
                        old_path=f'/blog/{old_slug}/',
                        defaults={
                            'new_path': f'/blog/{self.slug}/',
                            'status_code': '301',
                            'is_active': True,
                            'note': 'تغییر نامک مقاله: ' + str(self.title),
                        },
                    )
            except Exception:
                pass
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'مقاله'
        verbose_name_plural = 'مقالات'
        ordering = ['-created_at', '-id']

    def article_image(self):
        return admin_thumbnail(self.image, self.title)
    article_image.short_description = 'تصویر'

    def __str__(self):
        return self.title

