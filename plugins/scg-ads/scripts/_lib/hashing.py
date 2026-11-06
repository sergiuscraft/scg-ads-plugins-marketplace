"""Normalise + SHA-256 hash PII exactly as Google requires for Customer Match / enhanced conversions.

PII is hashed locally; plain values are never sent or logged.
"""

from __future__ import annotations

import hashlib
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str | None:
    e = (email or "").strip().lower()
    if not _EMAIL_RE.match(e):
        return None
    local, domain = e.rsplit("@", 1)
    if domain in {"gmail.com", "googlemail.com"}:
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def normalize_phone(phone: str, default_country_code: str | None = None) -> str | None:
    """E.164. Needs a leading '+' or a default country code (digits, e.g. '380')."""
    raw = (phone or "").strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    if raw.startswith("+"):
        out = "+" + digits
    elif raw.startswith("00"):
        out = "+" + digits[2:]
    elif default_country_code:
        cc = re.sub(r"\D", "", default_country_code)
        out = "+" + (digits if digits.startswith(cc) and len(digits) > 10 else cc + digits.lstrip("0"))
    else:
        return None
    return out if 8 <= len(out) - 1 <= 15 else None


def hash_email(email: str) -> str | None:
    n = normalize_email(email)
    return sha256_hex(n) if n else None


def hash_phone(phone: str, default_country_code: str | None = None) -> str | None:
    n = normalize_phone(phone, default_country_code)
    return sha256_hex(n) if n else None
