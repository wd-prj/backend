from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseEmailProvider(ABC):
    @abstractmethod
    def send_email(self, to: str, subject: str, html: str) -> Dict[str, Any]:
        """Send an email to a recipient and return provider response dict."""
        pass
