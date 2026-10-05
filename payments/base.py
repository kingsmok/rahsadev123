from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class PaymentStart:
    authority: str
    redirect_url: str

class PaymentGateway(ABC):
    code = ''
    @abstractmethod
    def start(self, transaction, callback_url): ...
    @abstractmethod
    def verify(self, transaction, callback_data): ...
