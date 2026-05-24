from __future__ import annotations

import re
from dataclasses import dataclass


GSTIN_PATTERN = re.compile(r"^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


@dataclass(frozen=True)
class GstValidation:
    is_valid: bool
    message: str


def validate_gstin(gstin: str | None) -> GstValidation:
    if not gstin:
        return GstValidation(False, "GSTIN not found")

    normalized = gstin.strip().upper().replace(" ", "")
    if len(normalized) != 15:
        return GstValidation(False, "GSTIN must be 15 characters")
    if not GSTIN_PATTERN.match(normalized):
        return GstValidation(False, "GSTIN format is invalid")
    if not _is_valid_check_digit(normalized):
        return GstValidation(False, "GSTIN checksum is invalid")
    return GstValidation(True, "GSTIN is valid")


def _is_valid_check_digit(gstin: str) -> bool:
    charset = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    factor = 2
    total = 0
    mod = 36

    for char in reversed(gstin[:14]):
        code_point = charset.find(char)
        if code_point == -1:
            return False
        addend = factor * code_point
        factor = 1 if factor == 2 else 2
        addend = (addend // mod) + (addend % mod)
        total += addend

    check_code_point = (mod - (total % mod)) % mod
    return charset[check_code_point] == gstin[-1]
