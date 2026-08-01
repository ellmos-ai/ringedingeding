"""End to end through the command line, and the refusals guarding --live.

Every test in this file runs without an account and without a network. Where a
live path is exercised, it stops at a guard before any socket is opened — if one
of these ever reaches the network, the test suite itself becomes a caller.
"""

from __future__ import annotations

import pytest

from ringedingeding.cli import (
    EXIT_ERROR,
    EXIT_LIVE_BLOCKED,
    EXIT_OK,
    EXIT_SENSITIVE,
    LIVE_ACK_ENV,
    main,
    parse_participant,
)


def run(args, tmp_path, extra=()):
    return main(["--db", str(tmp_path / "cli.db"), *args, *extra])


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec, expected",
    [
        ("Anna=+15555550100", ("Anna", "+15555550100")),
        ("Anna, +15555550100", ("Anna", "+15555550100")),
        ("Anna: +15555550100", ("Anna", "+15555550100")),
        ("Anna Meier = +15555550100", ("Anna Meier", "+15555550100")),
    ],
)
def test_participant_spec_accepts_the_obvious_spellings(spec, expected):
    assert parse_participant(spec) == expected


@pytest.mark.parametrize("spec", ["Anna", "+15555550100", ""])
def test_bad_participant_spec_is_rejected(spec):
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        parse_participant(spec)


# --------------------------------------------------------------------------
# the dry run
# --------------------------------------------------------------------------


def test_demo_runs_end_to_end_without_account_or_network(tmp_path, capsys):
    code = run(["demo", "--out", str(tmp_path / "reports")], tmp_path)
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "No call was placed and no account was used" in out
    # all three fixtures ran
    for name in ("family-dinner", "grandma-gift", "team-retro"):
        assert (tmp_path / "reports" / f"{name}.md").is_file()


def test_demo_output_contains_the_merged_answer_and_the_gap(tmp_path, capsys):
    run(["demo", "--out", str(tmp_path / "reports")], tmp_path)
    out = capsys.readouterr().out
    assert "Works for all 4 who answered: Sa 14-18" in out
    assert "Erik (NO_ANSWER)" in out
    assert "Frida (BUSY)" in out
    assert "not counted as indifferent" in out


def test_demo_prints_no_raw_numbers(tmp_path, capsys):
    run(["demo", "--out", str(tmp_path / "reports")], tmp_path)
    out = capsys.readouterr().out
    for number in ("+49010000001", "+15555550101", "010000006"):
        assert number not in out


def test_plan_does_not_change_anything(tmp_path, capsys):
    run(["plan", "--fixture", "family-dinner"], tmp_path)
    out = capsys.readouterr().out
    assert "nothing is dialed" in out
    assert "Estimated cost if run live: $0.30" in out
    assert "Singapore" in out

    # nothing was answered by planning
    code = run(["report", "--fixture", "family-dinner"], tmp_path)
    assert code == EXIT_OK
    assert "0 of 6" in capsys.readouterr().out


def test_a_real_poll_cannot_be_dry_run_without_scripted_answers(tmp_path, capsys):
    """There is nothing honest to simulate a real person's answer with."""
    run(
        [
            "create",
            "--question", "When can you make it?",
            "--kind", "slot",
            "--organizer", "Lukas",
            "--participant", "Anna=+15555550100",
            "--slot", "Sat 14-18",
        ],
        tmp_path,
    )
    poll_id = capsys.readouterr().out.split("created poll ")[1].split(" ")[0]
    assert run(["run", "--poll", poll_id], tmp_path) == EXIT_ERROR
    assert "a dry run needs scripted answers" in capsys.readouterr().err


def test_an_unknown_poll_id_is_an_error_not_a_crash(tmp_path, capsys):
    assert run(["report", "--poll", "poll_missing"], tmp_path) == EXIT_ERROR
    assert "poll_missing" in capsys.readouterr().err


def test_neither_poll_nor_fixture_is_an_error(tmp_path, capsys):
    assert run(["plan"], tmp_path) == EXIT_ERROR
    assert "--poll" in capsys.readouterr().err


def test_create_then_plan(tmp_path, capsys):
    code = run(
        [
            "create",
            "--question", "Photo book or voucher?",
            "--kind", "choice",
            "--organizer", "Lukas",
            "--option", "Photo book",
            "--option", "Voucher",
            "--participant", "Anna=+15555550100",
            "--participant", "Ben=+15555550101",
        ],
        tmp_path,
    )
    assert code == EXIT_OK
    created = capsys.readouterr().out
    assert "2 participant(s)" in created

    poll_id = created.split("created poll ")[1].split(" ")[0]
    assert run(["plan", "--poll", poll_id], tmp_path) == EXIT_OK
    plan = capsys.readouterr().out
    assert "Photo book" in plan
    assert "+15*****00" in plan


def test_rerunning_a_fixture_does_not_call_anyone_twice(tmp_path, capsys):
    run(["run", "--fixture", "family-dinner"], tmp_path)
    capsys.readouterr()
    run(["run", "--fixture", "family-dinner"], tmp_path)
    out = capsys.readouterr().out
    assert "every participant already has an answer" in out


def test_fresh_restarts_a_fixture_poll(tmp_path, capsys):
    run(["run", "--fixture", "family-dinner"], tmp_path)
    capsys.readouterr()
    run(["run", "--fixture", "family-dinner", "--fresh"], tmp_path)
    out = capsys.readouterr().out
    assert "calls=6" in out


def test_markdown_export(tmp_path, capsys):
    target = tmp_path / "nested" / "report.md"
    run(["run", "--fixture", "grandma-gift", "--markdown", str(target)], tmp_path)
    assert target.is_file()
    content = target.read_text(encoding="utf-8")
    assert "Fotobuch" in content
    assert "+49" in content and "010000011" not in content


def test_fixtures_command_lists_what_is_available(tmp_path, capsys):
    assert run(["fixtures"], tmp_path) == EXIT_OK
    out = capsys.readouterr().out
    assert "family-dinner" in out
    assert "grandma-gift" in out


def test_list_shows_progress(tmp_path, capsys):
    run(["run", "--fixture", "team-retro"], tmp_path)
    capsys.readouterr()
    run(["list"], tmp_path)
    assert "4/4 answered" in capsys.readouterr().out


# --------------------------------------------------------------------------
# refusals
# --------------------------------------------------------------------------


def test_a_sensitive_question_is_refused_at_creation(tmp_path, capsys):
    code = run(
        [
            "create",
            "--question", "Welche Dosierung soll Oma nehmen?",
            "--kind", "open",
            "--organizer", "Lukas",
            "--participant", "Anna=+15555550100",
        ],
        tmp_path,
    )
    assert code == EXIT_SENSITIVE
    assert "medical" in capsys.readouterr().err


def test_an_invalid_number_stops_the_whole_create(tmp_path, capsys):
    code = run(
        [
            "create",
            "--question", "Q",
            "--kind", "open",
            "--organizer", "Lukas",
            "--participant", "Anna=+1555",
        ],
        tmp_path,
    )
    assert code == EXIT_ERROR


def test_live_against_a_bundled_fixture_is_refused(tmp_path, capsys):
    """The demo numbers are examples; they must never ring."""
    code = run(["run", "--fixture", "family-dinner", "--live"], tmp_path)
    assert code == EXIT_LIVE_BLOCKED
    err = capsys.readouterr().err
    assert "example numbers" in err
    assert "never dialed" in err


def test_live_without_a_terminal_and_without_the_ack_is_refused(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv(LIVE_ACK_ENV, raising=False)
    run(
        [
            "create",
            "--question", "Q",
            "--kind", "open",
            "--organizer", "Lukas",
            "--participant", "Anna=+15555559999",
        ],
        tmp_path,
    )
    poll_id = capsys.readouterr().out.split("created poll ")[1].split(" ")[0]

    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    code = run(["run", "--poll", poll_id, "--live"], tmp_path)
    assert code == EXIT_LIVE_BLOCKED
    assert "not an interactive terminal" in capsys.readouterr().err


def test_yes_alone_does_not_unlock_live(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv(LIVE_ACK_ENV, raising=False)
    run(
        [
            "create",
            "--question", "Q",
            "--kind", "open",
            "--organizer", "Lukas",
            "--participant", "Anna=+15555559999",
        ],
        tmp_path,
    )
    poll_id = capsys.readouterr().out.split("created poll ")[1].split(" ")[0]

    code = run(["run", "--poll", poll_id, "--live", "--yes"], tmp_path)
    assert code == EXIT_LIVE_BLOCKED
    err = capsys.readouterr().err
    assert "no silent live mode" in err


def test_the_environment_ack_alone_does_not_unlock_live_either(tmp_path, capsys, monkeypatch):
    """Both halves are required: the environment says what, --yes says now."""
    monkeypatch.setenv(LIVE_ACK_ENV, "CALL THEM")
    run(
        [
            "create",
            "--question", "Q",
            "--kind", "open",
            "--organizer", "Lukas",
            "--participant", "Anna=+15555559999",
        ],
        tmp_path,
    )
    poll_id = capsys.readouterr().out.split("created poll ")[1].split(" ")[0]

    code = run(["run", "--poll", poll_id, "--live"], tmp_path)
    assert code == EXIT_LIVE_BLOCKED
    assert "--yes was not passed" in capsys.readouterr().err


def test_a_wrong_confirmation_phrase_dials_nothing(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv(LIVE_ACK_ENV, raising=False)
    run(
        [
            "create",
            "--question", "Q",
            "--kind", "open",
            "--organizer", "Lukas",
            "--participant", "Anna=+15555559999",
        ],
        tmp_path,
    )
    poll_id = capsys.readouterr().out.split("created poll ")[1].split(" ")[0]

    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "yes")
    code = run(["run", "--poll", poll_id, "--live"], tmp_path)
    assert code == EXIT_LIVE_BLOCKED
    assert "nothing was dialed" in capsys.readouterr().err


def test_the_live_prompt_states_cost_and_data_destination(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv(LIVE_ACK_ENV, raising=False)
    run(
        [
            "create",
            "--question", "Q",
            "--kind", "open",
            "--organizer", "Lukas",
            "--participant", "Anna=+15555559999",
        ],
        tmp_path,
    )
    poll_id = capsys.readouterr().out.split("created poll ")[1].split(" ")[0]

    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "no thanks")
    run(["run", "--poll", poll_id, "--live"], tmp_path)
    out = capsys.readouterr().out
    assert "REAL phone calls" in out
    assert "Singapore" in out
    assert "$0.05 per call" in out


# --------------------------------------------------------------------------
# what a live run would cost in time, not just in money
# --------------------------------------------------------------------------


def test_the_plan_states_the_time_as_well_as_the_price(tmp_path, capsys):
    """Money scales with the number of calls; time depends on how they run."""
    run(["plan", "--fixture", "family-dinner"], tmp_path)
    out = capsys.readouterr().out
    assert "Estimated cost if run live: $0.30" in out
    assert "Estimated time if run live:" in out
    assert "one after another" in out


def test_the_plan_admits_that_parallel_calling_is_unverified(tmp_path, capsys):
    run(["plan", "--fixture", "family-dinner"], tmp_path)
    out = capsys.readouterr().out
    assert "UNVERIFIED" in out
    assert "serial figure is the one to trust" in out


def test_the_estimate_is_dominated_by_dialling_not_by_talking():
    """Measured: ~40 s of every call is dialling, whatever is said."""
    from ringedingeding.timings import LEAD_SECONDS, estimate_seconds

    one = estimate_seconds(1)
    six_serial = estimate_seconds(6, concurrency=1)
    six_parallel = estimate_seconds(6, concurrency=6)
    assert six_serial > six_parallel
    assert six_serial - six_parallel > 5 * LEAD_SECONDS
    assert estimate_seconds(0) == 0.0
    assert one < six_serial
