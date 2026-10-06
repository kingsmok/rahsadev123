from .gateways import zarinpal_request, zarinpal_verify
from .base import PaymentGateway


class ZarinpalGateway(PaymentGateway):
    code = 'zarinpal'

    def start(self, transaction, callback_url):
        return zarinpal_request(transaction, callback_url)

    def verify(self, transaction, callback_data):
        return zarinpal_verify(transaction, callback_data.get('Authority', ''))


class SnappayGateway(PaymentGateway):
    code = 'snappay'

    def start(self, transaction, callback_url):
        raise RuntimeError(
            'اتصال به اسنپ‌پی نیازمند فعال‌سازی رسمی و مستندات اختصاصی این درگاه است؛ '
            'کلیدها را می‌توانید در پنل مدیریت ثبت کنید اما اتصال نهایی با هماهنگی پشتیبانی اسنپ‌پی انجام می‌شود.'
        )

    def verify(self, transaction, callback_data):
        raise NotImplementedError('اسنپ‌پی فعال نشده است.')


class TorobpayGateway(PaymentGateway):
    code = 'torobpay'

    def start(self, transaction, callback_url):
        raise RuntimeError(
            'اتصال به ترب‌پی نیازمند فعال‌سازی رسمی و مستندات اختصاصی این درگاه است؛ '
            'کلیدها را می‌توانید در پنل مدیریت ثبت کنید اما اتصال نهایی با هماهنگی پشتیبانی ترب انجام می‌شود.'
        )

    def verify(self, transaction, callback_data):
        raise NotImplementedError('ترب‌پی فعال نشده است.')


GATEWAYS = {
    'zarinpal': ZarinpalGateway(),
    'snappay': SnappayGateway(),
    'torobpay': TorobpayGateway(),
}
