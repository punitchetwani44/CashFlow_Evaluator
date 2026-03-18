"""Async email service for OTP delivery.

In dev mode (OTP_DEV_MODE=true) the OTP is printed to console instead of
being sent via SMTP — no email configuration required.
"""
import ssl
from typing import Optional

from ..config import settings


async def send_otp_email(
    to_email: str,
    otp_code: str,
    purpose: str = "login_2fa",
) -> None:
    """Send an OTP email. Falls back to console printing in dev mode."""
    if settings.otp_dev_mode:
        purpose_label = "Login OTP" if purpose == "login_2fa" else "Password Reset OTP"
        print(
            f"\n{'='*50}\n"
            f"[DEV MODE] {purpose_label} for {to_email}: {otp_code}\n"
            f"{'='*50}\n"
        )
        return

    # ── Production SMTP via aiosmtplib ───────────────────────────────────────
    try:
        import aiosmtplib
    except ImportError:
        print(f"[WARNING] aiosmtplib not installed; OTP for {to_email}: {otp_code}")
        return

    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if purpose == "password_reset":
        subject = "Your CashFlow Evaluator Password Reset Code"
        body = f"""
        <html><body>
        <p>You requested to reset your password.</p>
        <p>Your verification code is: <strong style="font-size:24px">{otp_code}</strong></p>
        <p>This code expires in <strong>15 minutes</strong>.</p>
        <p>If you did not request this, please ignore this email.</p>
        </body></html>
        """
    else:
        subject = "Your CashFlow Evaluator Login Code"
        body = f"""
        <html><body>
        <p>Your one-time login code is: <strong style="font-size:24px">{otp_code}</strong></p>
        <p>This code expires in <strong>5 minutes</strong>.</p>
        <p>If you did not attempt to log in, please change your password immediately.</p>
        </body></html>
        """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=True,
        )
    except Exception as e:
        # Log but don't crash — the caller already created the OTP row
        print(f"[ERROR] Failed to send OTP email to {to_email}: {e}")
        raise
