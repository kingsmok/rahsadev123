"""
سازگاری با نسخه‌های جدید پایتون.

در پایتون ۳.۱۴ رفتار ``copy.copy()`` روی شیء ``super()`` تغییر کرده است و
پیاده‌سازی ``django.template.context.BaseContext.__copy__`` در جنگو ۵.۱ با خطای
زیر از کار می‌افتد:

    AttributeError: 'super' object has no attribute 'dicts'
    and no __dict__ for setting new attributes

این خطا هنگام رندر شدن هر قالبی که از inclusion tag استفاده می‌کند رخ می‌دهد؛
یعنی عملاً تمام صفحات پنل ادمین جنگو و بخش‌هایی از سایت از کار می‌افتند.

این ماژول همان اصلاحی را که در نسخه‌های جدید جنگو انجام شده، در زمان اجرا روی
جنگوی نصب‌شده اعمال می‌کند تا پروژه روی پایتون ۳.۱۴ هم درست کار کند.
"""

import sys


def _patched_base_context_copy(self):
    duplicate = object.__new__(self.__class__)
    duplicate.__dict__.update(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate


def _needs_base_context_patch():
    """فقط وقتی پچ لازم است که پیاده‌سازی فعلی جنگو روی این پایتون خراب باشد."""
    from django.template.context import Context

    try:
        import copy as copy_module

        copy_module.copy(Context({"a": 1}))
    except Exception:
        return True
    return False


def patch_template_context_copy():
    """اصلاح copy() روی Context برای پایتون ۳.۱۴ به بالا."""
    if sys.version_info < (3, 14):
        return False

    from django.template.context import BaseContext

    if not _needs_base_context_patch():
        return False

    BaseContext.__copy__ = _patched_base_context_copy
    return True


def apply_patches():
    """اعمال تمام پچ‌های سازگاری. در AppConfig.ready صدا زده می‌شود."""
    patch_template_context_copy()
