"""Substitute-umlaut detection — the 2026-08-11 field finding.

A task text containing "fuer" was spoken aloud as "fuer", not "für". This
module only ever warns; it must never invent a false positive on a real word
that happens to contain the same three letters ("Feuer", "teuer", "neue").
"""

from __future__ import annotations

from ringedingeding.umlaut_check import find_umlaut_substitutes, umlaut_warning, warn_if_german


def test_a_known_substitute_word_is_found():
    assert find_umlaut_substitutes("Wann passt es fuer dich?") == [("fuer", "für")]


def test_a_clean_sentence_finds_nothing():
    assert find_umlaut_substitutes("Wann passt es für dich?") == []


def test_real_words_containing_the_same_letters_are_not_false_positives():
    """The operator's own named concern: 'Feuer'/'teuer'/'neue' must never
    trigger — none of them are the substitute word 'fuer' as a whole word."""
    assert find_umlaut_substitutes("Das Feuer war teuer, eine neue Sache.") == []


def test_matching_is_case_insensitive_and_whole_word():
    assert find_umlaut_substitutes("GESPRAECH gewuenscht") == [("GESPRAECH", "Gespräch")]
    # "gewuenscht" is not on the list; only listed words are ever flagged.


def test_several_findings_across_multiple_texts_are_all_reported_once():
    findings = find_umlaut_substitutes("Ich moechte spaeter zurueck.", "fuer heute")
    assert ("moechte", "möchte") in findings
    assert ("spaeter", "später") in findings
    assert ("zurueck", "zurück") in findings
    assert ("fuer", "für") in findings
    assert len(findings) == 4


def test_the_same_substitute_word_is_not_reported_twice():
    findings = find_umlaut_substitutes("fuer heute, fuer morgen, FUER immer")
    assert findings == [("fuer", "für")]


def test_empty_or_missing_text_finds_nothing():
    assert find_umlaut_substitutes("") == []
    assert find_umlaut_substitutes() == []


def test_the_warning_names_the_exact_word_and_what_it_will_be_read_as():
    warning = umlaut_warning([("fuer", "für")])
    assert '"fuer" wird sonst wörtlich als "fuer" vorgelesen' in warning
    assert '"für"' in warning


def test_no_findings_means_no_warning():
    assert umlaut_warning([]) == ""


def test_the_warning_itself_carries_real_umlauts_not_the_ascii_substitutes_it_warns_about():
    warning = umlaut_warning([("fuer", "für")])
    assert "ä" in warning or "ö" in warning or "ü" in warning
    assert "moeglich" not in warning.lower()
    assert "woertlich" not in warning.lower()


def test_warn_if_german_prints_for_a_german_poll_with_a_finding():
    printed = []
    warn_if_german("de", "Wann passt es fuer dich?", out=printed.append)
    assert printed
    assert "fuer" in printed[0]


def test_warn_if_german_stays_silent_for_an_english_poll():
    """No reason to flag 'fuer' — it is not even a German poll."""
    printed = []
    warn_if_german("en", "fuer dich", out=printed.append)
    assert printed == []


def test_warn_if_german_stays_silent_when_the_german_text_is_clean():
    printed = []
    warn_if_german("de", "Wann passt es für dich?", out=printed.append)
    assert printed == []
