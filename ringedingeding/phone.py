"""E.164 validation and masking.

Two rules from AGENTS.md live here:

* numbers are validated as E.164 *before* anything is dialed, and
* no raw phone number ever reaches an output surface — console, Markdown
  export, log line or error message.

``mask()`` is deliberately lossy and fixed-width: it hides the length of the
number as well as its digits, so the mask cannot be used to narrow a number
down by counting characters.
"""

from __future__ import annotations

import re

__all__ = [
    "InvalidPhoneNumber",
    "is_e164",
    "mask",
    "mask_text",
    "normalize_e164",
]

# E.164: a leading '+', a non-zero country code digit, then 7..14 more digits.
_E164 = re.compile(r"^\+[1-9]\d{7,14}$")

# Characters humans put into phone numbers that carry no information.
_NOISE = re.compile(r"[\s\-./() ‑–—]")

# Anything that structurally looks like a phone number, for the output scrubber.
_PHONE_LIKE = re.compile(r"\+[0-9\s\-./()]{7,}[0-9]")

_MASK_BODY = "*" * 5  # fixed width, so the real length does not leak; ASCII on purpose
_KEEP_PREFIX = 3  # '+' plus two digits
_KEEP_SUFFIX = 2


class InvalidPhoneNumber(ValueError):
    """Raised when a number is not usable as an E.164 destination."""


def normalize_e164(raw: str) -> str:
    """Return ``raw`` as a canonical E.164 string.

    Separators commonly typed by humans are removed first. Anything that is
    still not E.164 afterwards is rejected — we never guess a country code.
    """
    if not isinstance(raw, str):
        raise InvalidPhoneNumber(f"phone number must be a string, got {type(raw).__name__}")
    candidate = _NOISE.sub("", raw.strip())
    if not candidate:
        raise InvalidPhoneNumber("phone number is empty")
    if candidate.startswith("00"):
        raise InvalidPhoneNumber(
            f"{mask_candidate(candidate)} uses an international prefix (00…); "
            "write it as E.164 with a leading '+'"
        )
    if not candidate.startswith("+"):
        raise InvalidPhoneNumber(
            f"{mask_candidate(candidate)} has no country code; "
            "E.164 is required (for example +49…)"
        )
    if not _E164.match(candidate):
        raise InvalidPhoneNumber(
            f"{mask_candidate(candidate)} is not a valid E.164 number "
            "(expected '+' followed by 8 to 15 digits)"
        )
    return candidate


def is_e164(raw: str) -> bool:
    """True when ``raw`` is already canonical E.164."""
    return isinstance(raw, str) and bool(_E164.match(raw))


def mask(phone: str) -> str:
    """Mask a phone number for display: ``+4915112345678`` -> ``+49*****78``."""
    if not isinstance(phone, str) or not phone:
        return "+" + _MASK_BODY
    return mask_candidate(phone)


def mask_candidate(candidate: str) -> str:
    """Mask an arbitrary phone-ish string, valid or not."""
    stripped = _NOISE.sub("", candidate.strip())
    head = stripped[:_KEEP_PREFIX]
    tail = stripped[-_KEEP_SUFFIX:] if len(stripped) > _KEEP_PREFIX + _KEEP_SUFFIX else ""
    return f"{head}{_MASK_BODY}{tail}"


def mask_text(text: str) -> str:
    """Mask every phone-number-like substring inside free text.

    Used as a last line of defence on text we did not compose ourselves —
    transcripts, summaries and third-party error messages.
    """
    if not isinstance(text, str) or "+" not in text:
        return text
    return _PHONE_LIKE.sub(lambda m: mask_candidate(m.group(0)), text)
