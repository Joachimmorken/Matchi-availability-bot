import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in ("1", "true", "yes", "on")


def _load_env() -> None:
    # Load environment variables from .env if python-dotenv is available
    if load_dotenv is not None:
        try:
            load_dotenv()
        except Exception:
            # Best-effort; ignore issues loading .env
            pass


def send_email_notification(subject: str, body: str) -> bool:
    """Send an email using SMTP configuration from environment variables.

    Expected environment variables:
      - EMAIL_ENABLED: enable/disable sending (true/false)
      - SMTP_HOST, SMTP_PORT, SMTP_SSL (true/false)
      - SMTP_USER, SMTP_PASS
      - EMAIL_FROM, EMAIL_TO (comma-separated)

    Returns True on success, False otherwise.
    """
    _load_env()

    email_enabled = _is_truthy(os.getenv("EMAIL_ENABLED", "false"))
    if not email_enabled:
        print("[EMAIL] Email notifications disabled")
        return False

    try:
        smtp_host = (os.getenv("SMTP_HOST", "").strip())
        smtp_port_text = os.getenv("SMTP_PORT", "587").strip()
        try:
            smtp_port = int(smtp_port_text)
        except ValueError:
            smtp_port = 587
        smtp_ssl = _is_truthy(os.getenv("SMTP_SSL", "false"))
        smtp_user = (os.getenv("SMTP_USER", "").strip())
        smtp_pass = (os.getenv("SMTP_PASS", "").strip())
        email_from = (os.getenv("EMAIL_FROM", "").strip())
        email_to = (os.getenv("EMAIL_TO", "").strip())

        if not all([smtp_host, smtp_user, smtp_pass, email_from, email_to]):
            print("[EMAIL] Missing SMTP configuration")
            return False

        recipients = [addr.strip() for addr in email_to.split(",") if addr.strip()]
        if not recipients:
            print("[EMAIL] No valid recipients found")
            return False

        message = MIMEMultipart()
        message["From"] = email_from
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        if smtp_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()

        try:
            server.login(smtp_user, smtp_pass)
            server.send_message(message, to_addrs=recipients)
        finally:
            try:
                server.quit()
            except Exception:
                pass

        print(f"[EMAIL] Sent: {subject}")
        return True
    except Exception as exc:  # pragma: no cover
        print(f"[EMAIL] Failed to send: {exc}")
        return False


