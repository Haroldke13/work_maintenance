"""Email notifications for submitted responses.

Delivery happens on a background thread and every failure is swallowed after
logging: a complaint or a maintenance report must be saved and acknowledged even
when Gmail is slow, misconfigured, or unreachable. Nothing here is allowed to
turn a successful submission into an error for the person filling in the form.
"""

import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from functools import wraps

from flask import current_app


logger = logging.getLogger(__name__)


def notification_recipients(app) -> list[str]:
    """Return only the explicitly configured notification addresses."""
    addresses = list(app.config.get("NOTIFY_EMAILS") or [])
    seen, unique = set(), []
    for address in addresses:
        key = (address or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(address.strip())
    return unique


def best_effort(notification):
    """Notifications must never break the submission they are reporting on.

    The thread in `deliver` only covers delivery; this covers everything before
    it too — composing the message, building URLs, reading config.
    """

    @wraps(notification)
    def wrapped(*args, **kwargs):
        try:
            return notification(*args, **kwargs)
        except Exception:
            logger.exception("Notification %s failed", notification.__name__)
            return False

    return wrapped


def sender_header(app) -> str:
    """`PBORA <account@gmail.com>` — otherwise inboxes show the Gmail account name."""
    configured = app.config.get("MAIL_DEFAULT_SENDER") or app.config.get("MAIL_USERNAME") or ""
    existing_name, address = parseaddr(configured)
    if not address:
        return ""

    name = app.config.get("MAIL_SENDER_NAME") or existing_name
    return formataddr((name, address)) if name else address


def outbox(app) -> list[EmailMessage]:
    """Messages captured instead of sent, when MAIL_SUPPRESS_SEND is on."""
    return app.extensions.setdefault("mail_outbox", [])


def send_email(subject: str, body: str, recipients=None, reply_to=None, attachments=None) -> bool:
    """Queue one plain-text notification. Returns False when nothing was queued."""
    app = current_app._get_current_object()
    recipients = recipients or notification_recipients(app)

    if not recipients:
        logger.warning("No NOTIFY_EMAILS configured; skipping %r", subject)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender_header(app)
    message["To"] = ", ".join(recipients)
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)
    for content, maintype, subtype, filename in attachments or []:
        message.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    if app.config.get("MAIL_SUPPRESS_SEND"):
        outbox(app).append(message)
        return True

    if not app.config.get("MAIL_USERNAME") or not message["From"]:
        logger.warning("Mail credentials are not configured; skipping %r", subject)
        return False

    threading.Thread(target=deliver, args=(app, message), daemon=True).start()
    return True


def deliver(app, message: EmailMessage) -> None:
    config = app.config
    try:
        with smtplib.SMTP(
            config["MAIL_SERVER"], config["MAIL_PORT"], timeout=config["MAIL_TIMEOUT"]
        ) as smtp:
            if config.get("MAIL_USE_TLS"):
                smtp.starttls(context=ssl.create_default_context())
            if config.get("MAIL_PASSWORD"):
                smtp.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
            smtp.send_message(message)
        logger.info("Sent %r to %s", message["Subject"], message["To"])
    except Exception:
        # Never re-raise: the submission itself already succeeded.
        logger.exception("Could not send %r to %s", message["Subject"], message["To"])
