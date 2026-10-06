from django import forms
from .models import Address
from django.core.exceptions import ValidationError
from accounts.models import Profile


_DIGIT_TRANSLATION = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def _normalize_digits(value):
    """Store phone, postal, and card data consistently regardless of keyboard locale."""
    return (value or '').strip().translate(_DIGIT_TRANSLATION)


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['title', 'full_address', 'city', 'province', 'postal_code', 'receiver_name', 'phone_number',
                  'is_default']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'address-line1'}),
            'full_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'autocomplete': 'street-address'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'address-level2'}),
            'province': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'address-level1'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric', 'autocomplete': 'postal-code', 'dir': 'ltr'}),
            'receiver_name': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'name'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'type': 'tel', 'inputmode': 'numeric', 'autocomplete': 'tel', 'dir': 'ltr'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_title(self):
        title = (self.cleaned_data.get('title') or '').strip()
        if len(title) < 3:
            raise ValidationError("عنوان آدرس باید حداقل 3 کاراکتر باشد.")
        if len(title) > 100:
            raise ValidationError("عنوان آدرس باید حداکثر 100 کاراکتر باشد.")
        return title

    def clean_full_address(self):
        full_address = (self.cleaned_data.get('full_address') or '').strip()
        if len(full_address) < 10:
            raise ValidationError("آدرس باید حداقل 10 کاراکتر باشد.")
        if len(full_address) > 300:
            raise ValidationError("آدرس باید حداکثر 300 کاراکتر باشد.")
        return full_address

    def clean_city(self):
        city = (self.cleaned_data.get('city') or '').strip()
        if len(city) < 2:
            raise ValidationError("شهر باید حداقل 2 کاراکتر باشد.")
        if len(city) > 50:
            raise ValidationError("شهر باید حداکثر 50 کاراکتر باشد.")
        return city

    def clean_province(self):
        province = (self.cleaned_data.get('province') or '').strip()
        if len(province) < 2:
            raise ValidationError("استان باید حداقل 2 کاراکتر باشد.")
        if len(province) > 50:
            raise ValidationError("استان باید حداکثر 50 کاراکتر باشد.")
        return province

    def clean_postal_code(self):
        postal_code = _normalize_digits(self.cleaned_data.get('postal_code'))
        if len(postal_code) != 10:
            raise ValidationError("کد پستی باید 10 رقم باشد.")
        if not postal_code.isdigit():
            raise ValidationError("کد پستی باید فقط شامل اعداد باشد.")
        return postal_code

    def clean_phone_number(self):
        phone_number = _normalize_digits(self.cleaned_data.get('phone_number'))
        if not phone_number.startswith('09'):
            raise ValidationError("شماره تلفن باید با 09 شروع شود.")
        if len(phone_number) != 11 or not phone_number.isdigit():
            raise ValidationError("شماره تلفن باید 11 رقم باشد.")
        return phone_number

    def clean_receiver_name(self):
        receiver_name = (self.cleaned_data.get('receiver_name') or '').strip()
        if len(receiver_name.split()) < 2:
            raise ValidationError("لطفا نام و نام خانوادگی تحویل گیرنده را وارد کنید.")
        return receiver_name


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['first_name', 'last_name', 'email', 'about_me', 'phone', 'card_number', 'image']
        widgets = {
            'first_name': forms.TextInput(attrs={'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'autocomplete': 'family-name'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email', 'dir': 'ltr'}),
            'about_me': forms.Textarea(attrs={'rows': 3}),
            'phone': forms.TextInput(attrs={'type': 'tel', 'inputmode': 'numeric', 'autocomplete': 'tel', 'dir': 'ltr'}),
            'card_number': forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off', 'dir': 'ltr'}),
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def clean_first_name(self):
        first_name = (self.cleaned_data.get('first_name') or '').strip()
        if len(first_name) > 100:
            raise ValidationError("نام باید حداکثر 100 کاراکتر باشد.")
        return first_name

    def clean_last_name(self):
        last_name = (self.cleaned_data.get('last_name') or '').strip()
        if len(last_name) > 100:
            raise ValidationError("نام خانوادگی باید حداکثر 100 کاراکتر باشد.")
        return last_name

    def clean_email(self):
        # Profile.email is an EmailField, so Django validates the address format.
        # Do not limit customers to one provider such as Gmail.
        return (self.cleaned_data.get('email') or '').strip().lower()

    def clean_about_me(self):
        about_me = (self.cleaned_data.get('about_me') or '').strip()
        if len(about_me) > 250:
            raise ValidationError("متن درباره من باید حداکثر 250 کاراکتر باشد.")
        return about_me

    def clean_phone(self):
        phone = _normalize_digits(self.cleaned_data.get('phone'))
        if phone:
            if not phone.isdigit() or not phone.startswith('09') or len(phone) != 11:
                raise ValidationError("شماره تلفن باید با 09 شروع شده و 11 رقم باشد.")
        return phone

    def clean_card_number(self):
        card_number = _normalize_digits(self.cleaned_data.get('card_number'))
        if card_number:
            if len(card_number) != 16:
                raise ValidationError("شماره کارت باید 16 رقم باشد.")
            if not card_number.isdigit():
                raise ValidationError("شماره کارت باید فقط شامل اعداد باشد.")
        return card_number
