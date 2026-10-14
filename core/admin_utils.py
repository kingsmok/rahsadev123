"""ابزارهای مشترک `ModelAdmin` در ادمین فایل‌مارکت.

سه mixin کوچک که در همهٔ appها استفاده می‌شوند:

* :class:`PersianDateMixin` — تبدیل تاریخ میلادی به شمسی برای ستون‌های لیست.
* :class:`ExportCsvMixin` — اکشن «خروجی CSV» با BOM برای نمایش درست فارسی در اکسل.
* :class:`EnhancedAdminMixin` — تنظیمات پیش‌فرض مشترک (تعداد ردیف، حفظ فیلترها و …).
"""
import csv
from datetime import date, datetime

from django.contrib import admin
from django.db.models import Manager, QuerySet
from django.http import HttpResponse
from django.utils.html import strip_tags

from core.csv_safety import csv_safe
from jalali_date import datetime2jalali

JALALI_DATETIME_FORMAT = '%Y/%m/%d — %H:%M'
JALALI_DATE_FORMAT = '%Y/%m/%d'

PERSIAN_MONTHS = [
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
]
# jdatetime.weekday() از شنبه شروع می‌شود.
PERSIAN_WEEKDAYS = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه']


def to_jalali(value, fmt=JALALI_DATETIME_FORMAT):
    """تبدیل امن تاریخ/زمان به رشتهٔ شمسی (برای مقدار خالی خط تیره).

    نام ماه و روز هفته فارسی برگردانده می‌شود؛ strftime خودِ jdatetime
    برای %a/%A/%b/%B معادل لاتین («Wed»/«Mehr») می‌دهد که در پنل فارسی
    بیگانه است، پس این نشانه‌ها پیش از قالب‌بندی جایگزین می‌شوند.
    """
    if not value:
        return '—'
    jalali = datetime2jalali(value)
    replacements = {
        '%B': PERSIAN_MONTHS[jalali.month - 1],
        '%b': PERSIAN_MONTHS[jalali.month - 1],
        '%A': PERSIAN_WEEKDAYS[jalali.weekday()],
        '%a': PERSIAN_WEEKDAYS[jalali.weekday()],
    }
    safe_fmt = fmt
    tokens = {}
    for index, (token, text) in enumerate(replacements.items()):
        placeholder = f'\x00{index}\x00'
        if token in safe_fmt:
            safe_fmt = safe_fmt.replace(token, placeholder)
            tokens[placeholder] = text
    rendered = jalali.strftime(safe_fmt)
    for placeholder, text in tokens.items():
        rendered = rendered.replace(placeholder, text)
    return rendered


class PersianDateMixin:
    """کمک‌متد نمایش تاریخ شمسی در `list_display`."""

    jalali_datetime_format = JALALI_DATETIME_FORMAT
    jalali_date_format = JALALI_DATE_FORMAT

    def jalali_datetime(self, value):
        return to_jalali(value, self.jalali_datetime_format)

    def jalali_date(self, value):
        return to_jalali(value, self.jalali_date_format)


class ExportCsvMixin:
    """اکشن خروجی CSV از ردیف‌های انتخاب‌شده (یا همهٔ ردیفهای فیلترشده)."""

    csv_export_fields = ()
    csv_filename = None
    csv_max_rows = 5000

    def _csv_columns(self):
        if self.csv_export_fields:
            return list(self.csv_export_fields)
        return [
            name for name in (self.list_display or ())
            if name != admin.helpers.ACTION_CHECKBOX_NAME
        ]

    def _csv_header(self, name):
        attr = getattr(self, name, None)
        description = getattr(attr, 'short_description', None)
        if description:
            return str(description)
        field = self.model._meta.get_field(name) if self._is_model_field(name) else None
        if field is not None:
            return str(field.verbose_name)
        return name.replace('_', ' ')

    def _is_model_field(self, name):
        try:
            self.model._meta.get_field(name)
        except Exception:
            return False
        return True

    def _csv_value(self, obj, name):
        attr = getattr(self, name, None)
        if callable(attr):
            value = attr(obj)
        else:
            value = getattr(obj, name, '')
            # رابطه‌های چندبه‌چند «callable» هستند ولی فراخوانی‌شدنی نیستند؛
            # پیش از بررسی callable بودن باید جدا شوند.
            if isinstance(value, (Manager, QuerySet)):
                return '، '.join(str(item) for item in list(value.all())[:5])
            if callable(value):
                value = value()
        if isinstance(value, datetime):
            return to_jalali(value, self.jalali_datetime_format)
        if isinstance(value, date):
            return to_jalali(value, self.jalali_date_format)
        if value is None:
            return ''
        # پیش‌نمایش تصویر و ستون‌های HTML‌دار به متن ساده تبدیل می‌شوند
        return csv_safe(strip_tags(str(value)).strip())

    @admin.action(description='خروجی CSV از موارد انتخاب‌شده')
    def export_selected_as_csv(self, request, queryset):
        columns = self._csv_columns()
        filename = self.csv_filename or f'{self.model._meta.model_name}s.csv'

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        # BOM تا اکسل متن فارسی را با کدگذاری درست باز کند
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow([self._csv_header(name) for name in columns])
        for obj in queryset.select_related()[:self.csv_max_rows]:
            writer.writerow([self._csv_value(obj, name) for name in columns])

        self.message_user(request, f'خروجی {queryset.count()} ردیف آمادهٔ دانلود شد.')
        return response


class EnhancedAdminMixin(ExportCsvMixin, PersianDateMixin):
    """تنظیمات مشترک ادمین فایل‌مارکت."""

    list_per_page = 25
    show_full_result_count = True
    preserve_filters = True
    actions = ['export_selected_as_csv']
