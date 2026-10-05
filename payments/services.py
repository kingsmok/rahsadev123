from .gateways import zarinpal_request, zarinpal_verify
from .base import PaymentGateway

class ZarinpalGateway(PaymentGateway):
    code='zarinpal'
    def start(self, transaction, callback_url):
        return zarinpal_request(transaction, callback_url)
    def verify(self, transaction, callback_data):
        return zarinpal_verify(transaction, callback_data.get('Authority',''))

class UnsupportedGateway(PaymentGateway):
    def __init__(self, code): self.code=code
    def start(self, transaction, callback_url):
        raise NotImplementedError(f'Provider {self.code} requires official merchant API documentation and credentials.')
    def verify(self, transaction, callback_data):
        raise NotImplementedError(f'Provider {self.code} is not enabled.')

GATEWAYS={'zarinpal': ZarinpalGateway(), 'snappay': UnsupportedGateway('snappay'), 'torobpay': UnsupportedGateway('torobpay')}
