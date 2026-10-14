from django import template

register = template.Library()


@register.filter
def format_price(value):
    """قالب‌بندی قیمت با جداکننده هزارگان؛ در برابر مقدار خالی یا متنی مقاوم است."""
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return value


@register.filter
def multiply(value, arg):
    try:
        return value * arg
    except (TypeError, ValueError):
        return 0


@register.filter
def persian_digits(value):
    """تبدیل ارقام لاتین به فارسی برای نمایش در رابط کاربری.

    مقدار ورودی هر چیزی می‌تواند باشد؛ اگر رشته نباشد بدون تغییر برمی‌گردد
    تا در ترکیب با فیلترهای دیگر (مثل format_price) خطا ندهد.
    """
    if value is None or isinstance(value, bool):
        return value
    if not isinstance(value, str):
        value = str(value)
    return value.translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))


from core.admin_utils import PERSIAN_MONTHS  # فهرست مرکزی نام ماه‌ها


@register.filter
def to_jalali_fa(value, fmt='%d %B %Y'):
    """تاریخ شمسی با نام فارسی ماه و ارقام فارسی.

    فیلتر `to_jalali` کتابخانهٔ jalali-date برای %b/%B نام لاتین ماه
    («Meh»/«Mehr») برمی‌گرداند که در رابط فارسی بیگانه است. این فیلتر همان
    تبدیل تاریخ را انجام می‌دهد ولی نام ماه و ارقام را فارسی برمی‌گرداند.
    """
    if value is None:
        return '-'
    from datetime import date, datetime

    from jalali_date import date2jalali, datetime2jalali

    if isinstance(value, datetime):
        jalali = datetime2jalali(value)
    elif isinstance(value, date):
        jalali = date2jalali(value)
    else:
        return '-'

    month_name = PERSIAN_MONTHS[jalali.month - 1]
    safe_fmt = fmt.replace('%B', '\x00').replace('%b', '\x00')
    rendered = jalali.strftime(safe_fmt).replace('\x00', month_name)
    return persian_digits(rendered)
