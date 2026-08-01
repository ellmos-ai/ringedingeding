"""Number validation and, more importantly, that numbers never reach output."""

from __future__ import annotations

import pytest

from ringedingeding.phone import InvalidPhoneNumber, is_e164, mask, mask_text, normalize_e164


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("+15555550100", "+15555550100"),
        ("+1 555 555 0100", "+15555550100"),
        ("+49 (0)30 1111-0001", "+4903011110001"),
        ("  +15555550100  ", "+15555550100"),
        ("+1-555-555-0100", "+15555550100"),
    ],
)
def test_normalize_accepts_human_separators(raw, expected):
    assert normalize_e164(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "5555550100",  # no country code
        "004915112345678",  # international prefix instead of '+'
        "+0155512345",  # country code may not start with zero
        "+1555",  # too short
        "+1234567890123456789",  # too long
        "not a number",
    ],
)
def test_normalize_rejects_everything_else(raw):
    with pytest.raises(InvalidPhoneNumber):
        normalize_e164(raw)


def test_error_message_never_contains_the_full_number():
    with pytest.raises(InvalidPhoneNumber) as excinfo:
        normalize_e164("+1555")
    assert "+1555" not in str(excinfo.value)


def test_is_e164():
    assert is_e164("+15555550100")
    assert not is_e164("+1 555 555 0100")
    assert not is_e164(None)


def test_mask_hides_digits_and_length():
    short = mask("+15555550100")
    long = mask("+4915112345678999")
    assert short.startswith("+15")
    assert short.endswith("00")
    assert "5555550" not in short
    # A mask must not let you count digits.
    assert len(short) == len(long)


def test_mask_survives_junk():
    assert mask("") == "+*****"
    assert mask(None) == "+*****"


def test_mask_text_scrubs_numbers_out_of_free_text():
    text = "Call me back on +1 555 555 0100 or +4915112345678, thanks"
    scrubbed = mask_text(text)
    assert "5555550100" not in scrubbed
    assert "15112345678" not in scrubbed
    assert "thanks" in scrubbed


def test_mask_text_leaves_normal_text_alone():
    assert mask_text("no numbers here") == "no numbers here"
    assert mask_text("2 + 2 = 4") == "2 + 2 = 4"
