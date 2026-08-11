"""Region/locale derivation — the fix for the 2026-08-11 field finding.

``create --language de`` produced a plan header reading "de (en-US, region
US)": the German language and the American voice were three independent
defaults with no relationship. Everything below pins the one function that
now closes that gap.
"""

from __future__ import annotations

from ringedingeding.locales import region_locale_for


def test_german_language_derives_german_region_and_locale():
    assert region_locale_for("de") == ("DE", "de-DE")


def test_english_language_derives_the_existing_default():
    assert region_locale_for("en") == ("US", "en-US")


def test_an_explicit_region_still_wins_over_the_derived_one():
    assert region_locale_for("de", region="CH") == ("CH", "de-DE")


def test_an_explicit_locale_still_wins_over_the_derived_one():
    assert region_locale_for("de", locale="de-CH") == ("DE", "de-CH")


def test_both_explicit_values_win_together():
    assert region_locale_for("en", region="GB", locale="en-GB") == ("GB", "en-GB")


def test_an_empty_string_counts_as_unset_the_way_a_blank_html_field_does():
    """``Form(...)`` fields arrive as ``""``, never ``None``, when left blank."""
    assert region_locale_for("de", region="", locale="") == ("DE", "de-DE")


def test_an_unrecognised_language_falls_back_to_the_long_standing_default():
    assert region_locale_for("fr") == ("US", "en-US")


def test_language_matching_is_case_and_whitespace_insensitive():
    assert region_locale_for(" DE ") == ("DE", "de-DE")
