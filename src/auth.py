from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"^[6-9][0-9]{9}$")
OTP_TTL_MINUTES = 5


@dataclass(frozen=True)
class OtpChallenge:
    email: str
    phone: str
    otp: str
    expires_at: datetime


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D+", "", phone)
    if digits.startswith("91") and len(digits) == 12:
        return digits[2:]
    return digits


def validate_login_identity(email: str, phone: str) -> tuple[bool, str]:
    if not EMAIL_PATTERN.match(email.strip()):
        return False, "Enter a valid email address."

    normalized_phone = normalize_phone(phone)
    if not PHONE_PATTERN.match(normalized_phone):
        return False, "Enter a valid 10-digit Indian mobile number."

    return True, ""


def create_otp_challenge(email: str, phone: str) -> OtpChallenge:
    otp = f"{random.SystemRandom().randint(100000, 999999)}"
    challenge = OtpChallenge(
        email=email.strip().lower(),
        phone=normalize_phone(phone),
        otp=otp,
        expires_at=datetime.now() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    logger.info("OTP generated for %s / %s", challenge.email, mask_phone(challenge.phone))
    return challenge


def verify_otp(challenge: OtpChallenge | None, entered_otp: str) -> tuple[bool, str]:
    if challenge is None:
        return False, "Generate an OTP first."

    if datetime.now() > challenge.expires_at:
        return False, "OTP expired. Please request a new OTP."

    if re.sub(r"\D+", "", entered_otp) != challenge.otp:
        return False, "Incorrect OTP. Please try again."

    return True, "OTP verified successfully."


def mask_phone(phone: str) -> str:
    if len(phone) < 4:
        return phone
    return f"******{phone[-4:]}"


def mask_email(email: str) -> str:
    username, _, domain = email.partition("@")
    if len(username) <= 2:
        masked_user = username[:1] + "*"
    else:
        masked_user = username[:2] + "*" * max(len(username) - 2, 1)
    return f"{masked_user}@{domain}"
