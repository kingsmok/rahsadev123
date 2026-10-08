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
