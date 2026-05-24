from __future__ import annotations

import re
from dataclasses import dataclass


GSTIN_CANDIDATE = re.compile(r"\b[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", re.IGNORECASE)
INVOICE_NUMBER_PATTERNS = [
    re.compile(r"(?:invoice|inv)\s*(?:number|no|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\/\-_.]{2,})", re.IGNORECASE),
    re.compile(r"\bbill\s*(?:number|no)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\/\-_.]{2,})", re.IGNORECASE),
]
DATE_PATTERN = re.compile(r"\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}|\d{4}[\/\-.]\d{1,2}[\/\-.]\d{1,2})\b")
AMOUNT_PATTERN = re.compile(r"(?:rs\.?|inr|₹)?\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)", re.IGNORECASE)


@dataclass(frozen=True)
class InvoiceFields:
    gstin: str
    invoice_number: str
    invoice_date: str
    vendor: str
    total_amount: float | None
    taxable_amount: float | None
    cgst: float | None
    sgst: float | None
    igst: float | None
    total_tax: float | None
    confidence: float


def extract_invoice_fields(raw_text: str) -> InvoiceFields:
    text = normalize_text(raw_text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    gstin = _first_match(GSTIN_CANDIDATE, text)
    invoice_number = _extract_invoice_number(text)
    invoice_date = _first_match(DATE_PATTERN, text)
    vendor = _extract_vendor(lines, gstin)
    taxable_amount = _extract_labeled_amount(text, ["taxable value", "taxable amount", "sub total", "subtotal"])
    cgst = _extract_labeled_amount(text, ["cgst", "central tax"])
    sgst = _extract_labeled_amount(text, ["sgst", "state tax"])
    igst = _extract_labeled_amount(text, ["igst", "integrated tax"])
    total_tax = _extract_labeled_amount(text, ["total tax", "tax amount"])
    total_amount = _extract_labeled_amount(
        text,
        ["grand total", "invoice total", "total amount", "amount payable", "net payable", "total"],
    )

    if total_tax is None:
        tax_parts = [value for value in (cgst, sgst, igst) if value is not None]
        total_tax = round(sum(tax_parts), 2) if tax_parts else None

    confidence = _confidence_score(
        {
            "gstin": gstin,
            "invoice_number": invoice_number,
            "vendor": vendor,
            "total_amount": total_amount,
            "tax": total_tax,
        }
    )

    return InvoiceFields(
        gstin=gstin,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        vendor=vendor,
        total_amount=total_amount,
        taxable_amount=taxable_amount,
        cgst=cgst,
        sgst=sgst,
        igst=igst,
        total_tax=total_tax,
        confidence=confidence,
    )


def normalize_text(raw_text: str) -> str:
    text = raw_text.replace("\x0c", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1 if pattern.groups else 0).upper().strip() if match else ""


def _extract_invoice_number(text: str) -> str:
    for pattern in INVOICE_NUMBER_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip().upper()
    return ""


def _extract_vendor(lines: list[str], gstin: str) -> str:
    ignore_terms = ("tax invoice", "invoice", "gstin", "original", "duplicate", "bill of supply")
    for line in lines[:12]:
        clean = re.sub(r"[^A-Za-z0-9&.,() -]", "", line).strip()
        if len(clean) < 3:
            continue
        if gstin and gstin in clean.upper():
            continue
        if any(term in clean.lower() for term in ignore_terms):
            continue
        if re.search(r"[A-Za-z]", clean):
            return clean[:120]
    return ""


def _extract_labeled_amount(text: str, labels: list[str]) -> float | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    best_value: float | None = None

    for line in lines:
        lower_line = line.lower()
        if not any(label in lower_line for label in labels):
            continue
        values = [_parse_amount(match.group(1)) for match in AMOUNT_PATTERN.finditer(line)]
        values = [value for value in values if value is not None]
        if values:
            best_value = max(values)

    return best_value


def _parse_amount(value: str) -> float | None:
    try:
        return round(float(value.replace(",", "")), 2)
    except ValueError:
        return None


def _confidence_score(fields: dict[str, object]) -> float:
    weights = {
        "gstin": 25,
        "invoice_number": 20,
        "vendor": 15,
        "total_amount": 25,
        "tax": 15,
    }
    score = 0
    for key, weight in weights.items():
        if fields.get(key) not in (None, ""):
            score += weight
    return float(score)
