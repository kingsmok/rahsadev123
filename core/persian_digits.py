"""Normalising helpers for user-typed Persian/Arabic digits and phone numbers.

Iranian users frequently type numbers with a Persian or Arabic-Indic keyboard
layout, and paste mobile numbers in several common formats.  These helpers are
shared by every public form so validation behaves identically everywhere.
"""
from __future__ import annotations

# Persian (U+06F0…) and Arabic-Indic (U+0660…) digits both map to ASCII digits.
_DIGIT_TRANSLATION = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def to_latin_digits(value: str | None) -> str:
    """Return ``value`` with Persian/Arabic digits replaced by ASCII ones."""
    return (value or '').strip().translate(_DIGIT_TRANSLATION)


def normalise_iran_phone(value: str | None) -> str:
    """Accept Persian/Arabic digits and the common Iranian mobile prefixes.

    ``+98912…``, ``0098912…`` and ``912…`` are all normalised to ``0912…``.
    """
    phone = to_latin_digits(value).replace(' ', '').replace('-', '')
    if phone.startswith('+98'):
        phone = '0' + phone[3:]
    elif phone.startswith('0098'):
        phone = '0' + phone[4:]
    elif len(phone) == 10 and phone.startswith('9'):
        phone = '0' + phone
    return phone
