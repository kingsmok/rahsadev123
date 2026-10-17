"""نقش‌های کاربری فروشگاه.

نقش‌ها گروه‌های استاندارد جنگو هستند تا مدیر بتواند از صفحهٔ ویرایش کاربر
(بخش «گروه‌ها») یا با اکشن‌های فهرست کاربران، نقش بدهد یا بگیرد:

* «فروشندگان»: در فیلد «فروشنده»ی محصول قابل انتخاب‌اند.
* «نویسندگان»: در فیلد «نویسنده»ی مقاله قابل انتخاب‌اند.

مدیران (is_staff / superuser) همیشه در هر دو فهرست هستند. گروه‌ها با مایگریشن
accounts.0003 ساخته می‌شوند و فروشندگان/نویسندگان فعلی هم به آن‌ها اضافه
می‌شوند تا داده‌های قبلی معتبر بمانند.
"""
from django.db.models import Q

VENDOR_GROUP = 'فروشندگان'
AUTHOR_GROUP = 'نویسندگان'

ROLE_GROUPS = {
    'vendor': VENDOR_GROUP,
    'author': AUTHOR_GROUP,
}


def _group_member_ids(group_name):
    # A subquery on the user/group join table: filtering ``groups__name`` on
    # the user table would duplicate rows for members of several groups (the
    # admin autocomplete would then list a user twice).
    from django.contrib.auth.models import User

    return User.groups.through.objects.filter(group__name=group_name).values('user_id')


def _role_choices(group_name):
    return Q(is_active=True) & (
        Q(is_staff=True) | Q(is_superuser=True) | Q(pk__in=_group_member_ids(group_name))
    )


def vendor_choices():
    """``limit_choices_to`` for ``Product.vendor``."""
    return _role_choices(VENDOR_GROUP)


def author_choices():
    """``limit_choices_to`` for ``Article.author``."""
    return _role_choices(AUTHOR_GROUP)


def user_roles(user):
    """Persian role labels for admin lists."""
    labels = []
    if user.is_superuser:
        labels.append('مدیر کل')
    elif user.is_staff:
        labels.append('مدیر')
    names = {group.name for group in user.groups.all()}
    if VENDOR_GROUP in names:
        labels.append('فروشنده')
    if AUTHOR_GROUP in names:
        labels.append('نویسنده')
    return labels or ['مشتری']
