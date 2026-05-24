from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

import requests

from src.auth import OtpChallenge, mask_email, mask_phone


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeliveryResult:
    email_sent: bool
    sms_sent: bool
    demo_enabled: bool
    message: str


def send_otp(challenge: OtpChallenge) -> DeliveryResult:
    email_sent, email_message = _send_email_otp(challenge)
    sms_sent, sms_message = _send_sms_otp(challenge)
    demo_setting = _get_setting("DEMO_OTP", "auto").lower()
    demo_enabled = demo_setting in {"1", "true", "yes", "on", "auto"} and not (email_sent or sms_sent)

    messages = [message for message in (email_message, sms_message) if message]
    if not email_sent and not sms_sent and demo_enabled:
        messages.append("Demo OTP fallback is enabled because no real OTP provider is configured.")

    return DeliveryResult(
        email_sent=email_sent,
        sms_sent=sms_sent,
        demo_enabled=demo_enabled,
        message=" ".join(messages),
    )


def _send_email_otp(challenge: OtpChallenge) -> tuple[bool, str]:
    host = _get_setting("SMTP_HOST")
    port = int(_get_setting("SMTP_PORT", "587"))
    username = _get_setting("SMTP_USERNAME")
    password = _get_setting("SMTP_PASSWORD")
    sender = _get_setting("SMTP_FROM", username)
    use_tls = _get_setting("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}

    if not all([host, username, password, sender]):
        return False, "Email OTP not sent: SMTP secrets are missing."

    message = EmailMessage()
    message["Subject"] = "Your GST Invoice Intelligence OTP"
    message["From"] = sender
    message["To"] = challenge.email
    message.set_content(
        f"Your GST Invoice Intelligence OTP is {challenge.otp}.\n\n"
        "This code expires in 5 minutes. Do not share it with anyone."
    )

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            if use_tls:
                server.starttls()
            server.login(username, password)
            server.send_message(message)
        logger.info("Email OTP sent to %s", mask_email(challenge.email))
        return True, f"Email OTP sent to {mask_email(challenge.email)}."
    except Exception as exc:
        logger.exception("Email OTP delivery failed")
        return False, f"Email OTP failed: {exc}"


def _send_sms_otp(challenge: OtpChallenge) -> tuple[bool, str]:
    account_sid = _get_setting("TWILIO_ACCOUNT_SID")
    auth_token = _get_setting("TWILIO_AUTH_TOKEN")
    from_number = _get_setting("TWILIO_FROM_NUMBER")

    if not all([account_sid, auth_token, from_number]):
        return False, "SMS OTP not sent: Twilio secrets are missing."

    to_number = f"+91{challenge.phone}"
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    payload = {
        "From": from_number,
        "To": to_number,
        "Body": f"Your GST Invoice Intelligence OTP is {challenge.otp}. It expires in 5 minutes.",
    }

    try:
        response = requests.post(url, data=payload, auth=(account_sid, auth_token), timeout=20)
        response.raise_for_status()
        logger.info("SMS OTP sent to %s", mask_phone(challenge.phone))
        return True, f"SMS OTP sent to {mask_phone(challenge.phone)}."
    except Exception as exc:
        logger.exception("SMS OTP delivery failed")
        return False, f"SMS OTP failed: {exc}"


def _get_setting(key: str, default: str = "") -> str:
    env_value = os.getenv(key)
    if env_value not in (None, ""):
        return str(env_value)

    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        return default

    return default
