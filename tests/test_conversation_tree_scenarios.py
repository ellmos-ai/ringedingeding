"""Scenario matrix for the generated task text: "what must the text actually say?"

Companion to ``CONVERSATION-TREE.md`` — every scenario here is one path through that
document's tree, and every substring assertion cites the section (Sec.) that names the
fragment it is checking. Two complementary checks run:

1. **Substring/flip assertions**: the specific fragments a scenario must (or must
   not) contain, and — for the branching settings (poll kind, has_window,
   given_name, opening/closing wording, language) — a flip test proving the
   *other* branch produces genuinely different text, not just a passing
   coincidence.
2. **Golden files** (``tests/goldens/<scenario>.<lang>.txt``): the complete
   expected ``build_task_text`` output for a handful of core scenarios, so a
   change to the wording is a visible, reviewable diff, not only a silent
   pass/fail on the substrings above.

Golden files are never written by this test file or by pytest. Regenerate them
explicitly and deliberately with::

    python tests/goldens/regenerate.py

which prints a diff-like summary of what changed. A red pytest run must never be
"fixed" by silently overwriting the golden it disagrees with — review the diff,
then decide whether the golden was wrong or the code is.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_poll
from ringedingeding.models import PollKind
from ringedingeding.schemas import build_task_text

GOLDENS_DIR = Path(__file__).parent / "goldens"

KINDS = (PollKind.SLOT, PollKind.CHOICE, PollKind.OPEN)
LANGUAGES = ("en", "de")

_GIVEN_NAME = "Anna"
_OPENING = ("Hallo zusammen und danke fürs Rangehen!",)
_CLOSING = ("Schönen Tag noch, bis bald.",)
_URGENCY = "wirklich dringend"


def _poll(kind: PollKind, *, language: str, with_window: bool = True, **overrides) -> object:
    defaults: dict = dict(kind=kind, language=language, organizer="Lukas")
    if kind is PollKind.SLOT:
        defaults["slots"] = ("Sat 14-18", "Sun 10-14") if with_window else ()
        defaults["question"] = "When can you make it?"
    elif kind is PollKind.CHOICE:
        defaults["options"] = ("Pizza", "Sushi")
        defaults["question"] = "What should we order?"
    else:
        defaults["question"] = "Should we expand?"
    defaults.update(overrides)
    return make_poll(**defaults)


# --------------------------------------------------------------------------
# 1. Every poll kind's fixed question-block fragment (CONVERSATION-TREE.md Sec.1.2-1.4)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("language", LANGUAGES)
def test_question_is_asked_verbatim_and_quoted(kind: PollKind, language: str):
    poll = _poll(kind, language=language)
    text = build_task_text(poll)
    quoted = f'"{poll.question}"'
    assert quoted in text


@pytest.mark.parametrize("language", LANGUAGES)
def test_slot_with_window_enumerates_every_slot_by_label(language: str):
    """Sec.1.2, has_window=True branch: every slot label is named, one by one."""
    poll = _poll(PollKind.SLOT, language=language, with_window=True)
    text = build_task_text(poll)
    for slot in poll.slots:
        assert slot in text


@pytest.mark.parametrize("language", LANGUAGES)
def test_slot_without_window_lets_them_name_times_freely(language: str):
    """Sec.1.2, has_window=False branch -- the flip side of the test above."""
    with_window = build_task_text(_poll(PollKind.SLOT, language=language, with_window=True))
    without_window = build_task_text(_poll(PollKind.SLOT, language=language, with_window=False))
    assert with_window != without_window
    free_form = "Let them name the times that work" if language == "en" else "Lass die Person die passenden Zeiten nennen"
    assert free_form in without_window
    assert free_form not in with_window


@pytest.mark.parametrize("language", LANGUAGES)
def test_choice_options_are_all_read_out_by_name(language: str):
    """Sec.1.3: every option is enumerated. Flip test: changing the options changes the text."""
    poll_a = _poll(PollKind.CHOICE, language=language, options=("Pizza", "Sushi"))
    poll_b = _poll(PollKind.CHOICE, language=language, options=("Ramen", "Salad"))
    text_a = build_task_text(poll_a)
    text_b = build_task_text(poll_b)
    assert "Pizza" in text_a and "Sushi" in text_a
    assert "Pizza" not in text_b and "Ramen" in text_b
    assert text_a != text_b


@pytest.mark.parametrize("language", LANGUAGES)
def test_open_classifies_direction_for_local_tendency(language: str):
    """Sec.1.4: the stance-classification instruction is present. The merge-time
    correction for what that classification alone cannot guarantee is
    FINDINGS.md #12 / merge.py -- not re-tested here, tested at the merge layer."""
    poll = _poll(PollKind.OPEN, language=language)
    text = build_task_text(poll)
    marker = "support, against, mixed" if language == "en" else "Zustimmung, Ablehnung, gemischt"
    assert marker in text


# --------------------------------------------------------------------------
# 2. Identity gate: with / without a name (CONVERSATION-TREE.md Sec.1.1, Sec.3)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_identity_question_is_asked_verbatim_when_a_name_is_given(language: str):
    poll = _poll(PollKind.OPEN, language=language)
    text = build_task_text(poll, _GIVEN_NAME)
    quoted = (
        f'"Am I speaking with {_GIVEN_NAME}?"'
        if language == "en"
        else f'"Spreche ich mit {_GIVEN_NAME}?"'
    )
    assert quoted in text


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_name_skips_the_identity_check_entirely(language: str):
    """Flip side of the test above -- this is what --no-names produces (row 8)."""
    with_name = build_task_text(_poll(PollKind.OPEN, language=language), _GIVEN_NAME)
    without_name = build_task_text(_poll(PollKind.OPEN, language=language), None)
    assert with_name != without_name
    skip_marker = (
        "No name was given, so identity cannot be confirmed"
        if language == "en"
        else "Ohne Namen kann die Identität nicht geprüft werden"
    )
    assert skip_marker in without_name
    assert skip_marker not in with_name
    assert _GIVEN_NAME not in without_name


# --------------------------------------------------------------------------
# 3. Wording: opening/closing present vs. absent (CONVERSATION-TREE.md Sec.4)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_opening_wording_is_spoken_verbatim_when_set(language: str):
    poll = _poll(PollKind.OPEN, language=language)
    text = build_task_text(poll, opening=_OPENING)
    assert f'"{_OPENING[0]}"' in text


@pytest.mark.parametrize("language", LANGUAGES)
def test_empty_opening_wording_leaves_no_trace(language: str):
    """Sec.4: an empty wording field produces no trace at all, not an empty line."""
    with_opening = build_task_text(_poll(PollKind.OPEN, language=language), opening=_OPENING)
    without_opening = build_task_text(_poll(PollKind.OPEN, language=language), opening=())
    assert with_opening != without_opening
    lead = "Then say, word for word:" if language == "en" else "Sage danach wörtlich:"
    assert lead in with_opening
    assert lead not in without_opening


@pytest.mark.parametrize("language", LANGUAGES)
def test_closing_wording_is_spoken_verbatim_when_set(language: str):
    poll = _poll(PollKind.OPEN, language=language)
    text = build_task_text(poll, closing=_CLOSING)
    assert f'"{_CLOSING[0]}"' in text


@pytest.mark.parametrize("language", LANGUAGES)
def test_empty_closing_wording_leaves_no_trace(language: str):
    with_closing = build_task_text(_poll(PollKind.OPEN, language=language), closing=_CLOSING)
    without_closing = build_task_text(_poll(PollKind.OPEN, language=language), closing=())
    assert with_closing != without_closing
    lead = "Close the call with these words, exactly:" if language == "en" else "Verabschiede dich am Ende wörtlich mit:"
    assert lead in with_closing
    assert lead not in without_closing


@pytest.mark.parametrize("language", LANGUAGES)
def test_wording_is_unaffected_by_no_names(language: str):
    """Sec.4's second explicit check: wording survives --no-names untouched."""
    poll = _poll(PollKind.OPEN, language=language)
    with_name = build_task_text(poll, _GIVEN_NAME, opening=_OPENING, closing=_CLOSING)
    without_name = build_task_text(poll, None, opening=_OPENING, closing=_CLOSING)
    assert f'"{_OPENING[0]}"' in with_name
    assert f'"{_OPENING[0]}"' in without_name
    assert f'"{_CLOSING[0]}"' in with_name
    assert f'"{_CLOSING[0]}"' in without_name


# --------------------------------------------------------------------------
# 4. Urgency present vs. absent (CONVERSATION-TREE.md row 11)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_urgency_changes_tone_guidance_when_set(language: str):
    poll = _poll(PollKind.OPEN, language=language)
    with_urgency = build_task_text(poll, urgency=_URGENCY)
    without_urgency = build_task_text(poll, urgency="")
    assert with_urgency != without_urgency
    assert _URGENCY in with_urgency
    assert _URGENCY not in without_urgency


def test_urgency_is_guidance_not_quoted_verbatim():
    """schemas.py::_urgency_block docstring: unlike opening/closing, urgency is
    NOT wrapped in quotation marks -- it is meta-guidance the agent rephrases."""
    poll = _poll(PollKind.OPEN, language="en")
    text = build_task_text(poll, urgency=_URGENCY)
    assert f'"{_URGENCY}"' not in text
    assert _URGENCY in text


# --------------------------------------------------------------------------
# 5. Negative tests: no language ever leaks into the other language's call
# --------------------------------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
def test_german_poll_never_speaks_the_english_disclosure(kind: PollKind):
    poll = _poll(kind, language="de")
    text = build_task_text(poll, _GIVEN_NAME, opening=_OPENING, closing=_CLOSING, urgency=_URGENCY)
    assert "Hello, this is an automated assistant" not in text
    assert "Conduct the entire conversation in English" not in text


@pytest.mark.parametrize("kind", KINDS)
def test_english_poll_never_speaks_the_german_disclosure(kind: PollKind):
    poll = _poll(kind, language="en")
    text = build_task_text(poll, _GIVEN_NAME, opening=_OPENING, closing=_CLOSING, urgency=_URGENCY)
    assert "Guten Tag, hier ist ein automatischer Assistent" not in text
    assert "Führe das gesamte Gespräch auf Deutsch" not in text


def test_only_de_prefix_variants_count_as_german():
    """schemas.py:499 -- str(poll.language).lower().startswith('de'). A region
    code like 'de-DE' or a bare 'DE' must also select the German template."""
    for language in ("de", "DE", "de-DE", "de-AT"):
        text = build_task_text(_poll(PollKind.OPEN, language=language))
        assert "Guten Tag, hier ist ein automatischer Assistent" in text, language


# --------------------------------------------------------------------------
# 6. Golden files -- one full text per core scenario x language
# --------------------------------------------------------------------------

# (name, poll, given_name, opening, closing, urgency) -- kept in sync with
# tests/goldens/regenerate.py, which imports this exact dict.
SCENARIOS: dict[str, tuple] = {
    "slot_with_window": (
        lambda language: _poll(PollKind.SLOT, language=language, with_window=True),
        _GIVEN_NAME,
        _OPENING,
        _CLOSING,
        "",
    ),
    "slot_without_window": (
        lambda language: _poll(PollKind.SLOT, language=language, with_window=False),
        _GIVEN_NAME,
        (),
        (),
        "",
    ),
    "choice": (
        lambda language: _poll(PollKind.CHOICE, language=language),
        _GIVEN_NAME,
        _OPENING,
        _CLOSING,
        "",
    ),
    "open": (
        lambda language: _poll(PollKind.OPEN, language=language),
        None,
        (),
        (),
        _URGENCY,
    ),
}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
@pytest.mark.parametrize("language", LANGUAGES)
def test_golden_task_text_matches(name: str, language: str):
    factory, given_name, opening, closing, urgency = SCENARIOS[name]
    poll = factory(language)
    text = build_task_text(poll, given_name, opening=opening, closing=closing, urgency=urgency)
    golden_path = GOLDENS_DIR / f"{name}.{language}.txt"
    assert golden_path.exists(), (
        f"Missing golden file {golden_path}. Run `python tests/goldens/regenerate.py` "
        "and review the diff before committing."
    )
    expected = golden_path.read_text(encoding="utf-8")
    assert text == expected, (
        f"{golden_path} is out of date. If this change is intentional, run "
        "`python tests/goldens/regenerate.py`, review the diff, then commit "
        "both the code change and the updated golden together."
    )
