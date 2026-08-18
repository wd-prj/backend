import logging
from typing import Optional, Dict, Any
from app.core.config import settings
from app.services.email.base import BaseEmailProvider
from app.services.email.resend_provider import ResendEmailProvider

logger = logging.getLogger("email.service")


class ConsoleEmailProvider(BaseEmailProvider):
    def __init__(self, from_email: str = "ZenithHR <onboarding@resend.dev>"):
        self.from_email = from_email

    def send_email(self, to: str, subject: str, html: str) -> Dict[str, Any]:
        logger.info(f"== [MOCK EMAIL DISPATCH] ==")
        logger.info(f"From: {self.from_email}")
        logger.info(f"To: {to}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Content:\n{html}")
        logger.info(f"===========================")
        return {"status": "success", "mock": True}


class EmailService:
    def __init__(self):
        self.provider: BaseEmailProvider
        if settings.EMAIL_PROVIDER == "resend" and settings.RESEND_API_KEY:
            self.provider = ResendEmailProvider(
                api_key=settings.RESEND_API_KEY,
                from_email=settings.EMAIL_FROM or "ZenithHR <onboarding@resend.dev>",
            )
        else:
            self.provider = ConsoleEmailProvider(
                from_email=settings.EMAIL_FROM or "ZenithHR <onboarding@resend.dev>"
            )

    def send_invitation_email(
        self,
        to_email: str,
        name: str,
        role: str,
        department: str,
        team: str,
        manager: str,
        location: str,
        raw_token: str,
    ) -> Dict[str, Any]:
        accept_url = f"{settings.APP_URL}/accept-invitation?token={raw_token}"
        subject = f"You're invited to join ZenithHR as {role}"

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #0f172a; padding: 24px; }}
    .card {{ max-width: 560px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
    .logo {{ font-size: 20px; font-weight: 800; color: #4f46e5; margin-bottom: 24px; }}
    h2 {{ font-size: 20px; font-weight: 700; color: #0f172a; margin-top: 0; }}
    .details {{ background: #f1f5f9; border-radius: 12px; padding: 16px 20px; margin: 20px 0; font-size: 14px; line-height: 1.8; }}
    .btn {{ display: inline-block; background-color: #4f46e5; color: #ffffff !important; text-decoration: none; padding: 12px 28px; border-radius: 10px; font-weight: 700; font-size: 14px; margin-top: 16px; }}
    .footer {{ margin-top: 24px; font-size: 12px; color: #94a3b8; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">Zenith<span style="color:#0f172a;">HR</span></div>
    <h2>You've been invited to join the organization.</h2>
    <p>Your enterprise account has been provisioned. Please review your organization assignment details and accept your invitation below:</p>
    
    <div class="details">
      <div><strong>Name:</strong> {name}</div>
      <div><strong>Role:</strong> {role}</div>
      <div><strong>Department:</strong> {department}</div>
      <div><strong>Team:</strong> {team}</div>
      <div><strong>Manager:</strong> {manager}</div>
      <div><strong>Location:</strong> {location}</div>
    </div>

    <p style="text-align: center; margin: 28px 0;">
      <a href="{accept_url}" class="btn" style="color: #ffffff;">[Accept Invitation]</a>
    </p>

    <div class="footer">
      <p>This invitation link is single-use and will expire in {settings.INVITATION_EXPIRE_HOURS} hours.</p>
      <p>If the button above does not work, copy and paste this link into your browser:<br/>
      <span style="color: #4f46e5; word-break: break-all;">{accept_url}</span></p>
    </div>
  </div>
</body>
</html>"""

        try:
            return self.provider.send_email(to=to_email, subject=subject, html=html)
        except Exception as e:
            logger.warning(
                f"Email dispatch via configured provider failed ({e}). Raw invitation link for testing: {accept_url}"
            )
            return {"status": "fallback_logged", "accept_url": accept_url, "error": str(e)}


email_service = EmailService()
