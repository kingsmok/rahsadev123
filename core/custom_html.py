"""کد HTML سفارشی برای محصول، مقاله و صفحه.

کد خام HTML (همراه با <style> و <script>) عیناً در سایت اجرا می‌شود؛ پس فقط
مدیران مورد اعتماد اجازهٔ ویرایش آن را دارند: مدیر کل (superuser) یا کاربری که
مجوز ``core.edit_raw_html`` به او داده شده است. ادمین‌ها برای بقیه این فیلدها را
فقط‌خواندنی نشان می‌دهند (``RawHtmlAdminMixin``).
"""
from django.db import models

RAW_HTML_PERMISSION = 'core.edit_raw_html'

CUSTOM_HTML_MODES = (
    ('after', 'نمایش پس از محتوا'),
    ('before', 'نمایش پیش از محتوا'),
    ('replace', 'جایگزین کامل محتوا'),
)

CUSTOM_HTML_HELP = (
    'کد HTML (می‌تواند <style> و <script> هم داشته باشد) که عیناً در صفحه اجرا می‌شود. '
    'پیش‌نمایش زنده زیر همین کادر نمایش داده می‌شود. فقط مدیران دارای مجوز «ویرایش کد HTML خام» '
    'می‌توانند این فیلد را تغییر دهند.'
)


def can_edit_raw_html(user):
    return bool(user and user.is_active and (user.is_superuser or user.has_perm(RAW_HTML_PERMISSION)))


class CustomHtmlMixin(models.Model):
    custom_html = models.TextField(blank=True, verbose_name='کد HTML سفارشی', help_text=CUSTOM_HTML_HELP)
    custom_html_mode = models.CharField(
        max_length=10, choices=CUSTOM_HTML_MODES, default='after', verbose_name='حالت نمایش کد HTML',
    )

    class Meta:
        abstract = True

    @property
    def has_custom_html(self):
        return bool((self.custom_html or '').strip())

    @property
    def custom_html_before(self):
        return self.has_custom_html and self.custom_html_mode == 'before'

    @property
    def custom_html_after(self):
        return self.has_custom_html and self.custom_html_mode == 'after'

    @property
    def custom_html_replaces_content(self):
        return self.has_custom_html and self.custom_html_mode == 'replace'
