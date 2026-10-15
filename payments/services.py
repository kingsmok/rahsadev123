from .base import PaymentGateway
from .gateways import zarinpal_request, zarinpal_verify
from .installments import SnappayGateway, TorobpayGateway, ZarinplusGateway


class ZarinpalGateway(PaymentGateway):
    code = 'zarinpal'
    implemented = True

    def start(self, transaction, callback_url, customer=None):
        return zarinpal_request(transaction, callback_url)

    def verify(self, transaction, callback_data):
        return zarinpal_verify(transaction, callback_data.get('Authority', ''))


GATEWAYS = {
    'zarinpal': ZarinpalGateway(),
    'zarinplus': ZarinplusGateway(),
    'snappay': SnappayGateway(),
    'torobpay': TorobpayGateway(),
}

#: Gateways that return the customer to ``payments:gateway_callback`` (the
#: Zarinpal flow keeps its original ``payments:callback`` URL).
GATEWAY_CALLBACK_KEYS = ('zarinplus', 'snappay', 'torobpay')
#: Gateways that need the customer's mobile number to open an instalment plan.
MOBILE_REQUIRED_KEYS = ('snappay', 'torobpay')
