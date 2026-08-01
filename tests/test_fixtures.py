"""Fixtures and the dry-run transport.

The point of these tests: a dry run must be able to *fail*. A fixture that
could not have come out of a real call has to be rejected, otherwise the dry
run proves nothing.
"""

from __future__ import annotations

import json

import pytest
from conftest import make_participant, make_poll

from ringedingeding.fixtures import (
    FixtureError,
    bundled_fixtures,
    load_fixture,
    placeholder_numbers,
    resolve_fixture,
)
from ringedingeding.models import CallStatus, PollKind
from ringedingeding.safety import idempotency_key
from ringedingeding.schemas import aggregate_result_schema, recipient_result_schema
from ringedingeding.transports.base import CallRequest
from ringedingeding.transports.fixture import FixtureOutcomeMissing, FixtureTransport


def _request(poll, participant):
    return CallRequest(
        poll=poll,
        participant=participant,
        task_text="...",
        recipient_schema=recipient_result_schema(poll),
        aggregate_schema=aggregate_result_schema(poll),
        idempotency_key=idempotency_key(poll.id, participant.id),
    )


# --------------------------------------------------------------------------
# the bundled fixtures
# --------------------------------------------------------------------------


def test_three_fixtures_are_bundled():
    assert set(bundled_fixtures()) == {"family-dinner", "grandma-gift", "team-retro"}


@pytest.mark.parametrize("name", ["family-dinner", "grandma-gift", "team-retro"])
def test_bundled_fixtures_load(name):
    fixture = load_fixture(resolve_fixture(name))
    assert fixture.participants
    assert fixture.outcomes


def test_every_bundled_answer_satisfies_its_own_schema():
    """If this fails, the demo is showing data a real call could not return."""
    from ringedingeding.validate import validate

    for name in bundled_fixtures():
        fixture = load_fixture(resolve_fixture(name))
        poll = make_poll(
            kind=PollKind.parse(fixture.poll.get("kind", "open")),
            options=tuple(fixture.poll.get("options") or []),
            slots=tuple(fixture.poll.get("slots") or []),
        )
        schema = recipient_result_schema(poll)
        for ref, outcome in fixture.outcomes.items():
            structured = outcome.get("structured_result")
            if structured:
                assert validate(structured, schema) == [], f"{name}/{ref}"


def test_the_demo_scenario_matches_the_brief():
    """Six people, a scheduling question, and exactly two who were not reached."""
    fixture = load_fixture(resolve_fixture("family-dinner"))
    assert len(fixture.participants) == 6
    unreached = [
        ref
        for ref, outcome in fixture.outcomes.items()
        if outcome.get("call_status") not in ("COMPLETED", "DECLINED")
    ]
    assert len(unreached) == 2


def test_placeholder_numbers_cover_every_bundled_participant():
    numbers = placeholder_numbers()
    for name in bundled_fixtures():
        fixture = load_fixture(resolve_fixture(name))
        for _name, phone, _ref in fixture.people:
            assert phone in numbers


# --------------------------------------------------------------------------
# fixture file validation
# --------------------------------------------------------------------------


def test_a_participant_without_an_outcome_is_an_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text(
        json.dumps(
            {
                "poll": {"question": "Q", "kind": "open"},
                "participants": [
                    {"ref": "a", "name": "A", "phone": "+15555550100"},
                    {"ref": "b", "name": "B", "phone": "+15555550101"},
                ],
                "outcomes": {"a": {"call_status": "COMPLETED"}},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(FixtureError) as excinfo:
        load_fixture(path)
    assert "no scripted outcome for b" in str(excinfo.value)


def test_an_outcome_without_a_participant_is_an_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text(
        json.dumps(
            {
                "poll": {"question": "Q", "kind": "open"},
                "participants": [{"ref": "a", "name": "A", "phone": "+15555550100"}],
                "outcomes": {"a": {"call_status": "COMPLETED"}, "ghost": {}},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(FixtureError):
        load_fixture(path)


def test_unknown_fixture_name_lists_what_is_available():
    with pytest.raises(FixtureError) as excinfo:
        resolve_fixture("does-not-exist")
    assert "family-dinner" in str(excinfo.value)


# --------------------------------------------------------------------------
# the transport
# --------------------------------------------------------------------------


def test_transport_replays_the_scripted_outcome():
    poll = make_poll()
    participant = make_participant("anna")
    transport = FixtureTransport(
        {
            "anna": {
                "call_status": "COMPLETED",
                "structured_result": {
                    "reachable": True,
                    "refused": False,
                    "available_slots": ["Sat 14-18"],
                },
            }
        }
    )
    outcome = transport.place_one(_request(poll, participant))
    assert outcome.status is CallStatus.COMPLETED
    assert outcome.structured["available_slots"] == ["Sat 14-18"]


def test_missing_outcome_raises_rather_than_inventing_one():
    transport = FixtureTransport({})
    with pytest.raises(FixtureOutcomeMissing):
        transport.place_one(_request(make_poll(), make_participant("ghost")))


def test_an_answer_that_breaks_the_schema_fails_the_dry_run():
    poll = make_poll(slots=("Sat 14-18",))
    transport = FixtureTransport(
        {
            "anna": {
                "call_status": "COMPLETED",
                "structured_result": {
                    "reachable": True,
                    "refused": False,
                    "available_slots": ["whenever, really"],
                },
            }
        }
    )
    outcome = transport.place_one(_request(poll, make_participant("anna")))
    assert outcome.status is CallStatus.FAILED
    assert "violates the recipient schema" in (outcome.error or "")


def test_an_impossible_status_and_answer_combination_fails():
    """A call nobody picked up cannot carry a filled-in result."""
    transport = FixtureTransport(
        {
            "anna": {
                "call_status": "NO_ANSWER",
                "structured_result": {"reachable": True, "refused": False},
            }
        }
    )
    outcome = transport.place_one(_request(make_poll(), make_participant("anna")))
    assert outcome.status is CallStatus.FAILED
    assert "cannot occur" in (outcome.error or "")


def test_the_fixture_transport_is_not_live():
    assert FixtureTransport({}).is_live is False
