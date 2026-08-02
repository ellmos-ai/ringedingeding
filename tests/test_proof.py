"""The core sample has to keep proving what it claims to prove.

These tests are deliberately not a second implementation of the checks in
:mod:`ringedingeding.proof`. They assert three different things:

1. the command runs, passes all of its own checks and exits 0,
2. each check really *can* fail — a check that cannot fail proves nothing,
3. the run leaves no trace: no database outside its own temporary directory,
   no network, no full phone number in the output.
"""

from __future__ import annotations

import re

import pytest

from ringedingeding import proof
from ringedingeding.cli import main
from ringedingeding.fixtures import load_fixture, resolve_fixture
from ringedingeding.store import Store


@pytest.fixture(scope="module")
def result() -> proof.ProofResult:
    """One run, shared: it is deterministic, so running it eight times is waste."""
    return proof.run_proof()


def test_the_core_sample_passes_every_one_of_its_own_checks(result):
    failed = [check.name for check in result.failed]
    assert failed == [], f"core sample failed its own checks: {failed}"
    assert len(result.checks) == 8


def test_the_command_exits_zero_and_says_nothing_was_dialled(tmp_path, capsys):
    code = main(["--db", str(tmp_path / "untouched.db"), "proof"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Nothing was dialled" in out
    assert "8 of 8 checks passed" in out


def test_the_command_does_not_touch_the_database_it_was_given(tmp_path):
    db = tmp_path / "mine.db"
    Store(db).close()
    before = db.read_bytes()
    assert main(["--db", str(db), "proof"]) == 0
    assert db.read_bytes() == before


def test_no_full_phone_number_reaches_the_output(result):
    assert not re.search(r"\+\d{6,}", "\n".join(result.lines))


def test_every_state_the_scenario_provokes_is_named_in_the_output(result):
    text = "\n".join(result.lines)
    for expected in (
        "cannot : Paul",          # disagreement
        "silent : Rike",          # half a commitment
        "Tara (NO_ANSWER)",       # nobody picked up
        "Uwe (BUSY)",             # line busy
        "declined    : Sven",     # reached, declined to answer
        "no phone    : Vera",     # never callable at all
    ):
        assert expected in text, f"missing from the core sample output: {expected!r}"


def test_the_answer_that_arrived_late_overturns_the_earlier_result(result):
    text = "\n".join(result.lines)
    assert "=> Works for all 3 who answered: Sat 09-13" in text
    assert "=> No slot works for all 4 who answered." in text


# --------------------------------------------------------------------------
# a check that cannot fail proves nothing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ref, patch",
    [
        # Turn the disagreement into agreement.
        ("paul", {"cannot": [], "available_slots": ["Sat 09-13", "Sat 14-18", "Sun 09-13"]}),
        # Turn silence into an explicit "no" to the two unmentioned slots.
        ("rike", {"cannot": ["Sat 14-18", "Sun 09-13"]}),
        # Let the answer that arrived late agree with everybody else, so that
        # catching Vera up would have changed nothing after all.
        ("vera", {"cannot": [], "available_slots": ["Sat 09-13", "Sat 14-18", "Sun 09-13"]}),
    ],
)
def test_a_broken_scenario_makes_the_core_sample_fail(monkeypatch, ref, patch):
    """Sabotage one scripted answer and the checks must notice.

    Without this, "8 of 8 passed" could just mean the assertions are toothless.
    """
    original = load_fixture(resolve_fixture(proof.FIXTURE_NAME))
    outcomes = {key: dict(spec) for key, spec in original.outcomes.items()}
    structured = dict(outcomes[ref].get("structured_result") or {})
    structured.update(patch)
    outcomes[ref]["structured_result"] = structured
    tampered = type(original)(
        name=original.name,
        description=original.description,
        poll=original.poll,
        participants=original.participants,
        outcomes=outcomes,
        source=original.source,
    )

    monkeypatch.setattr(proof, "load_fixture", lambda _path: tampered)
    sabotaged = proof.run_proof()
    assert not sabotaged.ok, f"tampering with {ref} went unnoticed"


def test_the_scenario_file_is_the_one_the_command_names(result):
    """The output tells a reader where the answers come from; it has to be true."""
    fixture = load_fixture(resolve_fixture(proof.FIXTURE_NAME))
    assert fixture.name == proof.FIXTURE_NAME
    assert f"fixtures/{proof.FIXTURE_NAME}.json" in "\n".join(result.lines)
    # Seven scripted people, and the one held back is really in the file.
    assert len(fixture.participants) == 7
    assert proof.CATCH_UP_REF in fixture.outcomes
