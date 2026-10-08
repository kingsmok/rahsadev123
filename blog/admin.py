from django.contrib import admin
from . import models
from core.admin_utils import EnhancedAdminMixin
from jalali_date import datetime2jalali
from jalali_date.admin import ModelAdminJalaliMixin


@admin.register(models.Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ['title']


@admin.register(models.Category)
class CategoryAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['title', 'get_created_jalali']
    prepopulated_fields = {'slug': ('title',)}
    # برای autocomplete در فرم مقاله
    search_fields = ['title']

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%a, %d %b %Y')


@admin.register(models.Article)
class ArticleAdmin(ModelAdminJalaliMixin, EnhancedAdminMixin, admin.ModelAdmin):
    list_display = ['short_title', 'author', 'views', 'article_image', 'get_created_jalali', 'status']
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ['status']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['title', 'description', 'author__username', 'category__title', 'tags__title']
    autocomplete_fields = ['category', 'tags']
    date_hierarchy = 'created_at'
    list_select_related = ['author']
    readonly_fields = ['views', 'created_at', 'updated_at']
    csv_filename = 'masaishop-articles.csv'
    actions = ['publish_articles', 'draft_articles', 'export_selected_as_csv']
    fieldsets = (
        ('محتوا', {
            'fields': ('author', 'title', 'slug', 'description', 'image', 'category', 'tags', 'status')
        }),
        ('سئو', {
            'fields': ('meta_title', 'meta_description', 'canonical_url')
        }),
        ('آمار (فقط خواندنی)', {
            'classes': ('collapse',),
            'fields': ('views', 'created_at', 'updated_at')
        }),
    )

    @admin.action(description='انتشار مقالات انتخاب‌شده')
    def publish_articles(self, request, queryset):
        updated = queryset.update(status='published')
        self.message_user(request, f'{updated} مقاله منتشر شد.')

    @admin.action(description='پیش‌نویس کردن مقالات انتخاب‌شده')
    def draft_articles(self, request, queryset):
        updated = queryset.update(status='draft')
        self.message_user(request, f'{updated} مقاله پیش‌نویس شد.')

    def short_title(self, obj):
        if len(obj.title) > 20:
            return obj.title[:20] + '...'
        return obj.title
    short_title.short_description = 'عنوان مقاله'

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%Y/%m/%d')


