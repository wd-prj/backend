import logging
from typing import Dict, Any
import resend
from app.services.email.base import BaseEmailProvider

logger = logging.getLogger("email.resend")


class ResendEmailProvider(BaseEmailProvider):
    def __init__(self, api_key: str, from_email: str = "ZenithHR <onboarding@resend.dev>"):
        self.api_key = api_key
        self.from_email = from_email
        resend.api_key = self.api_key

    def send_email(self, to: str, subject: str, html: str) -> Dict[str, Any]:
        params: resend.Emails.SendParams = {
            "from": self.from_email,
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "html": html,
        }
        logger.info(f"Sending email via Resend to {to} from {self.from_email}: {subject}")
        try:
            response = resend.Emails.send(params)
            logger.info(f"Resend email dispatched successfully: {response}")
            return response if isinstance(response, dict) else getattr(response, "__dict__", {"id": str(response)})
        except Exception as e:
            logger.error(f"Resend API error sending email to {to}: {e}", exc_info=True)
            raise e
