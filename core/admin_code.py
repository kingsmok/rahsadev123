"""ویرایشگر کد HTML با پیش‌نمایش زنده برای پنل مدیریت."""
import json

from django import forms
from django.templatetags.static import static

from .custom_html import can_edit_raw_html

# همان لایه‌های CSS فروشگاه تا پیش‌نمایش شبیه صفحهٔ واقعی باشد.
PREVIEW_STYLESHEETS = (
    'fonts/font-awesome/css/fontawesome.min.css',
    'fonts/font-awesome/css/solid.css',
    'fonts/font-awesome/css/brands.css',
    'css/bootstrap.min.css',
    'css/style.css',
    'css/theme.css',
    'css/modern-2026.css',
    'css/fm-design-system.css',
    'css/fm-pages.css',
    'css/fm-features.css',
)


class CodeEditorWidget(forms.Textarea):
    template_name = 'core/widgets/code_editor.html'

    def __init__(self, attrs=None):
        base = {'rows': 16, 'spellcheck': 'false', 'dir': 'ltr', 'class': 'fm-code-editor__input',
                'autocapitalize': 'off', 'autocomplete': 'off'}
        base.update(attrs or {})
        super().__init__(attrs=base)

    class Media:
        css = {'all': ('css/fm-code-editor.css',)}
        js = ('js/fm-code-editor.js',)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['preview_css'] = json.dumps([static(path) for path in PREVIEW_STYLESHEETS])
        return context


class RawHtmlAdminMixin:
    """کد HTML خام فقط برای مدیر کل یا دارندهٔ مجوز core.edit_raw_html قابل ویرایش است."""

    raw_html_fields = ('custom_html',)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not can_edit_raw_html(request.user):
            fields.extend(name for name in self.raw_html_fields if name not in fields)
        return fields

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in self.raw_html_fields:
            kwargs['widget'] = CodeEditorWidget()
        return super().formfield_for_dbfield(db_field, request, **kwargs)
