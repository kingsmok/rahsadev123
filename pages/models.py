from django.db import models
from ckeditor_uploader.fields import RichTextUploadingField
class StaticPage(models.Model):
    title=models.CharField(max_length=200, verbose_name='عنوان')
    slug=models.SlugField(max_length=220, unique=True, allow_unicode=True)
    summary=models.CharField(max_length=160, blank=True, verbose_name='توضیحات سئو')
    content=RichTextUploadingField(verbose_name='محتوا')
    is_published=models.BooleanField(default=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: verbose_name='صفحه'; verbose_name_plural='صفحات'
    def __str__(self): return self.title
