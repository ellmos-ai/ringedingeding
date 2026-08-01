"""Content limits, idempotency, and the live gate."""

from __future__ import annotations

import pytest

from ringedingeding.safety import (
    SensitiveContent,
    assert_question_allowed,
    check_question,
    idempotency_key,
)


@pytest.mark.parametrize(
    "question",
    [
        "Sollen wir Oma zum Geburtstag ein Fotobuch schenken oder einen Gutschein?",
        "Wann kannst du am Wochenende zum Familienessen?",
        "Ja, aber nur wenn es unter 50 Euro bleibt",
        "What is the one thing you would change about our weekly meeting?",
        "Should we book the restaurant for 8pm?",
        "Kommst du mit ins Kino?",
    ],
)
def test_ordinary_questions_pass(question):
    """The keyword lists must not be trigger-happy; a price is not finance."""
    assert check_question(question) == []
    assert_question_allowed(question)


@pytest.mark.parametrize(
    "question, category",
    [
        ("Welche Dosierung soll ich nehmen?", "medical"),
        ("What medication should I take?", "medical"),
        ("Ist das ein Notfall?", "emergency"),
        ("Should I call an ambulance?", "emergency"),
        ("Brauche ich eine Rechtsberatung?", "legal"),
        ("Can you give me legal advice?", "legal"),
        ("Wie lauten deine Kontodaten?", "financial"),
        ("Give me your bank details", "financial"),
    ],
)
def test_sensitive_questions_are_refused(question, category):
    findings = check_question(question)
    assert [finding.category for finding in findings] == [category]
    with pytest.raises(SensitiveContent):
        assert_question_allowed(question)


def test_options_are_checked_too_not_only_the_question():
    with pytest.raises(SensitiveContent):
        assert_question_allowed("Which one do you prefer?", "IBAN transfer")


def test_refusal_explains_itself_and_offers_no_override():
    with pytest.raises(SensitiveContent) as excinfo:
        assert_question_allowed("Welche Dosierung?")
    message = str(excinfo.value)
    assert "medical" in message
    assert "no override flag" in message


def test_idempotency_key_is_deterministic():
    first = idempotency_key("poll_1", "p_1")
    second = idempotency_key("poll_1", "p_1")
    assert first == second


def test_idempotency_key_separates_people_polls_and_attempts():
    base = idempotency_key("poll_1", "p_1")
    assert base != idempotency_key("poll_1", "p_2")
    assert base != idempotency_key("poll_2", "p_1")
    assert base != idempotency_key("poll_1", "p_1", attempt=2)


def test_idempotency_key_does_not_leak_the_inputs():
    key = idempotency_key("poll_secret", "p_secret")
    assert "secret" not in key
    assert key.startswith("rdd_")
