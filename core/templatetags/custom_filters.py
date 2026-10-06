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
