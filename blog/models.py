from django.db import models
from django.contrib.auth.models import User
from django.utils.html import format_html
from ckeditor_uploader.fields import RichTextUploadingField


STATUS = (
    ('draft', 'پیش نویس'),
    ('published', 'منتشر شود'),
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


class Article(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='نویسنده مقاله')
    category = models.ManyToManyField(Category, related_name='articles', verbose_name='دسته بندی مربوطه')
    tags = models.ManyToManyField(Tag, blank=True, related_name='articles', verbose_name='برچسب‌ها')
    title = models.CharField(max_length=200, unique=True, verbose_name='عنوان مقاله')
    slug = models.SlugField(max_length=200, unique=True, allow_unicode=True, verbose_name='نامک')
    description = RichTextUploadingField(verbose_name='متن مقاله')
    image = models.ImageField(upload_to='articles/', blank=True, null=True, verbose_name='تصویر مقاله')
    status = models.CharField(choices=STATUS, max_length=10, verbose_name='وضعیت')
    views = models.IntegerField(default=0, editable=False, verbose_name='بازدید')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')
    meta_title = models.CharField(max_length=70, blank=True, verbose_name='عنوان سئو')
    meta_description = models.CharField(max_length=160, blank=True, verbose_name='توضیحات سئو')
    canonical_url = models.URLField(blank=True, verbose_name='آدرس canonical')

    class Meta:
        verbose_name = 'مقاله'
        verbose_name_plural = 'مقالات'
        ordering = ['-created_at', '-id']

    def article_image(self):
        if self.image:
            return format_html(f'<img src="{self.image.url}" width="50px" height="50px">')
        return format_html(f'<h3 style="color: red">تصویر ندارد</h3>')

    def __str__(self):
        return self.title

