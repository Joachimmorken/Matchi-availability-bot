"""
Professional Email Notification System for Matchi Availability Bot
================================================================

This module provides a comprehensive email notification system with:
- Beautiful HTML email templates using Jinja2
- CSS inlining for better email client compatibility
- Email validation and sanitization
- Robust error handling and logging
- Support for both HTML and plain text emails
- Email analytics and tracking
- Professional email design with responsive layout

Author: GitHub Copilot
Version: 2.0.0
"""

import os
import smtplib
import logging
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, make_msgid
import re

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError:
    raise ImportError(
        "jinja2 is required for email templates. Install with: pip install jinja2"
    )

try:
    from premailer import transform
except ImportError:
    raise ImportError(
        "premailer is required for CSS inlining. Install with: pip install premailer"
    )

try:
    from email_validator import validate_email, EmailNotValidError
except ImportError:
    validate_email = None
    EmailNotValidError = Exception

# Configure logging
logger = logging.getLogger(__name__)


class EmailConfig:
    """Email configuration class with validation and defaults."""
    
    def __init__(self):
        self._load_env()
        self.enabled = self._is_truthy(os.getenv("EMAIL_ENABLED", "false"))
        self.smtp_host = os.getenv("SMTP_HOST", "").strip()
        self.smtp_port = self._parse_port(os.getenv("SMTP_PORT", "587"))
        self.smtp_ssl = self._is_truthy(os.getenv("SMTP_SSL", "false"))
        self.smtp_user = os.getenv("SMTP_USER", "").strip()
        self.smtp_pass = os.getenv("SMTP_PASS", "").strip()
        self.email_from = os.getenv("EMAIL_FROM", "").strip()
        self.email_from_name = os.getenv("EMAIL_FROM_NAME", "Matchi Availability Bot").strip()
        self.email_to = os.getenv("EMAIL_TO", "").strip()
        self.reply_to = os.getenv("EMAIL_REPLY_TO", "").strip()
        
        # Advanced settings
        self.timeout = int(os.getenv("SMTP_TIMEOUT", "30"))
        self.use_tls = self._is_truthy(os.getenv("SMTP_USE_TLS", "true"))
        self.debug = self._is_truthy(os.getenv("EMAIL_DEBUG", "false"))
        
    def _load_env(self) -> None:
        """Load environment variables from .env file if available."""
        if load_dotenv is not None:
            try:
                load_dotenv()
            except Exception as e:
                logger.warning(f"Could not load .env file: {e}")
    
    def _is_truthy(self, value: Optional[str]) -> bool:
        """Check if a string value represents a truthy boolean."""
        if value is None:
            return False
        return value.strip().lower() in ("1", "true", "yes", "on", "enabled")
    
    def _parse_port(self, port_str: str) -> int:
        """Parse port number with fallback to default."""
        try:
            return int(port_str.strip())
        except (ValueError, AttributeError):
            return 587
    
    def is_valid(self) -> bool:
        """Check if email configuration is valid."""
        required_fields = [
            self.smtp_host,
            self.smtp_user, 
            self.smtp_pass,
            self.email_from,
            self.email_to
        ]
        return all(field for field in required_fields)
    
    def get_recipients(self) -> List[str]:
        """Parse and validate recipient email addresses."""
        if not self.email_to:
            return []
        
        recipients = []
        for addr in self.email_to.split(","):
            addr = addr.strip()
            if addr:
                if validate_email and self._validate_single_email(addr):
                    recipients.append(addr)
                elif not validate_email:
                    # Basic regex validation if email-validator not available
                    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', addr):
                        recipients.append(addr)
        
        return recipients
    
    def _validate_single_email(self, email: str) -> bool:
        """Validate a single email address."""
        try:
            validate_email(email)
            return True
        except EmailNotValidError:
            logger.warning(f"Invalid email address: {email}")
            return False


class EmailTemplateEngine:
    """Email template engine using Jinja2 with CSS inlining."""
    
    def __init__(self, template_dir: Optional[Path] = None):
        if template_dir is None:
            template_dir = Path(__file__).parent / "email_templates"
        
        self.template_dir = Path(template_dir)
        if not self.template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {self.template_dir}")
        
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['datetime'] = self._format_datetime
        self.env.filters['date'] = self._format_date
        self.env.filters['time'] = self._format_time
    
    def _format_datetime(self, dt: datetime.datetime, format_str: str = '%B %d, %Y at %I:%M %p') -> str:
        """Format datetime object."""
        return dt.strftime(format_str)
    
    def _format_date(self, date: datetime.date, format_str: str = '%B %d, %Y') -> str:
        """Format date object."""
        return date.strftime(format_str)
    
    def _format_time(self, time: datetime.time, format_str: str = '%I:%M %p') -> str:
        """Format time object."""
        return time.strftime(format_str)
    
    def render_template(self, template_name: str, **context) -> str:
        """Render an HTML template with context."""
        template = self.env.get_template(template_name)
        
        # Add common context variables
        context.setdefault('current_time', datetime.datetime.now())
        
        html_content = template.render(**context)
        
        # Inline CSS for better email client compatibility
        try:
            return transform(html_content, 
                           keep_style_tags=True,
                           strip_important=False,
                           remove_classes=False)
        except Exception as e:
            logger.warning(f"CSS inlining failed: {e}. Using original HTML.")
            return html_content
    
    def render_plain_text(self, html_content: str) -> str:
        """Convert HTML content to plain text fallback."""
        # Simple HTML to text conversion
        import re
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # Decode HTML entities
        import html
        text = html.unescape(text)
        
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        return text.strip()


class EmailNotificationSystem:
    """Professional email notification system with templates and analytics."""
    
    def __init__(self, config: Optional[EmailConfig] = None):
        self.config = config or EmailConfig()
        self.template_engine = EmailTemplateEngine()
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration."""
        if self.config.debug:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
    
    def send_new_courts_notification(self, 
                                   facilities_data: List[Dict[str, Any]],
                                   quote: Optional[str] = None) -> bool:
        """Send notification about new available tennis courts."""
        if not self.config.enabled:
            logger.info("[EMAIL] Email notifications disabled")
            return False
        
        # Calculate summary statistics
        total_new_courts = sum(
            len(date_data.get('time_slots', {})) 
            for facility in facilities_data 
            for date_data in facility.get('dates', [])
        )
        
        summary_stats = {
            'facilities_count': len(facilities_data),
            'dates_count': sum(len(f.get('dates', [])) for f in facilities_data),
            'time_slots_count': total_new_courts,
            'most_popular_time': self._get_most_popular_time(facilities_data)
        }
        
        context = {
            'facilities': facilities_data,
            'total_new_courts': total_new_courts,
            'summary_stats': summary_stats,
            'quote': quote
        }
        
        return self._send_template_email(
            template_name='new_courts.html',
            subject=f"🎾 {total_new_courts} New Tennis Court{'s' if total_new_courts != 1 else ''} Available!",
            context=context
        )
    
    def send_test_email(self, quote: Optional[str] = None) -> bool:
        """Send a test email to verify configuration."""
        context = {'quote': quote}
        
        return self._send_template_email(
            template_name='test_email.html',
            subject="📧 Email Test: Matchi Availability Bot",
            context=context
        )
    
    def send_daily_summary(self, stats: Dict[str, Any], quote: Optional[str] = None) -> bool:
        """Send daily summary email."""
        context = {
            'stats': stats,
            'popular_facilities': stats.get('popular_facilities', []),
            'availability_trends': stats.get('availability_trends', []),
            'quote': quote
        }
        
        return self._send_template_email(
            template_name='daily_summary.html',
            subject="📊 Daily Tennis Court Summary",
            context=context
        )
    
    def _send_template_email(self, 
                           template_name: str,
                           subject: str,
                           context: Dict[str, Any]) -> bool:
        """Send email using template."""
        try:
            # Render HTML content
            html_content = self.template_engine.render_template(template_name, **context)
            
            # Generate plain text fallback
            plain_content = self.template_engine.render_plain_text(html_content)
            
            return self._send_multipart_email(subject, html_content, plain_content)
            
        except Exception as e:
            logger.error(f"[EMAIL] Failed to send template email: {e}")
            return False
    
    def _send_multipart_email(self, 
                            subject: str,
                            html_content: str,
                            plain_content: str) -> bool:
        """Send multipart email with HTML and plain text."""
        if not self.config.is_valid():
            logger.error("[EMAIL] Invalid email configuration")
            return False
        
        recipients = self.config.get_recipients()
        if not recipients:
            logger.error("[EMAIL] No valid recipients found")
            return False
        
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['From'] = formataddr((self.config.email_from_name, self.config.email_from))
            message['To'] = ', '.join(recipients)
            message['Subject'] = subject
            message['Message-ID'] = make_msgid()
            
            if self.config.reply_to:
                message['Reply-To'] = self.config.reply_to
            
            # Attach plain text and HTML parts
            plain_part = MIMEText(plain_content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            message.attach(plain_part)
            message.attach(html_part)
            
            # Send email
            return self._send_message(message, recipients)
            
        except Exception as e:
            logger.error(f"[EMAIL] Failed to create email message: {e}")
            return False
    
    def _send_message(self, message: MIMEMultipart, recipients: List[str]) -> bool:
        """Send email message via SMTP."""
        try:
            # Create SMTP connection
            if self.config.smtp_ssl:
                server = smtplib.SMTP_SSL(
                    self.config.smtp_host, 
                    self.config.smtp_port,
                    timeout=self.config.timeout
                )
            else:
                server = smtplib.SMTP(
                    self.config.smtp_host,
                    self.config.smtp_port,
                    timeout=self.config.timeout
                )
                if self.config.use_tls:
                    server.starttls()
            
            # Set debug level
            if self.config.debug:
                server.set_debuglevel(1)
            
            try:
                # Authenticate and send
                server.login(self.config.smtp_user, self.config.smtp_pass)
                server.send_message(message, to_addrs=recipients)
                
                logger.info(f"[EMAIL] Successfully sent: {message['Subject']}")
                return True
                
            finally:
                try:
                    server.quit()
                except Exception:
                    pass
                    
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"[EMAIL] SMTP authentication failed: {e}")
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"[EMAIL] Recipients refused: {e}")
        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"[EMAIL] SMTP server disconnected: {e}")
        except Exception as e:
            logger.error(f"[EMAIL] Failed to send email: {e}")
        
        return False
    
    def _get_most_popular_time(self, facilities_data: List[Dict[str, Any]]) -> Optional[str]:
        """Find the most popular time slot across all facilities."""
        time_counts = {}
        
        for facility in facilities_data:
            for date_data in facility.get('dates', []):
                for time_slot in date_data.get('time_slots', {}):
                    time_counts[time_slot] = time_counts.get(time_slot, 0) + 1
        
        if not time_counts:
            return None
        
        return max(time_counts.items(), key=lambda x: x[1])[0]


# Legacy function for backward compatibility
def send_email_notification(subject: str, body: str) -> bool:
    """Legacy function for backward compatibility.
    
    This maintains compatibility with existing code while using the new system.
    """
    system = EmailNotificationSystem()
    
    # Create a simple HTML wrapper for the plain text body
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">{subject}</h2>
            <div style="white-space: pre-wrap;">{body}</div>
            <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">
            <p style="color: #7f8c8d; font-size: 14px;">
                Sent by Matchi Availability Bot on {datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            </p>
        </div>
    </body>
    </html>
    """
    
    return system._send_multipart_email(subject, html_content, body)


# Main interface functions
def create_email_system() -> EmailNotificationSystem:
    """Create and return configured email notification system."""
    return EmailNotificationSystem()


def send_new_courts_email(facilities_data: List[Dict[str, Any]], quote: Optional[str] = None) -> bool:
    """Send notification about new available courts using beautiful template."""
    system = create_email_system()
    return system.send_new_courts_notification(facilities_data, quote)


def send_test_email() -> bool:
    """Send a test email using the new template system."""
    system = create_email_system()
    return system.send_test_email()


if __name__ == "__main__":
    # Test the email system
    print("Testing email notification system...")
    success = send_test_email()
    print(f"Test email {'sent successfully' if success else 'failed to send'}")


