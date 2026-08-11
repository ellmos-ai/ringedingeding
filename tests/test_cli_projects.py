"""The project commands — the ones ``SKILL.md`` hands to somebody else's agent.

If these drift from the web interface, the promise of one flow with three ways
in is broken. They are tested through :func:`ringedingeding.cli.main`, exactly
as an agent would invoke them.
"""

from __future__ import annotations

import pytest

from ringedingeding.cli import main
from ringedingeding.projects import ProjectStore
from ringedingeding.store import Store


@pytest.fixture()
def run(tmp_path, capsys):
    """Invoke the CLI against a throwaway database and return its output."""
    db = tmp_path / "cli.db"

    def invoke(*args: str) -> tuple[int, str]:
        code = main(["--db", str(db), *args])
        captured = capsys.readouterr()
        return code, captured.out + captured.err

    return invoke


@pytest.fixture()
def project(run):
    """A project with four callable people and one without a number."""
    for name, phone in (
        ("Anna", "+15555550101"),
        ("Ben", "+15555550102"),
        ("Clara", "+15555550103"),
        ("David", "+15555550104"),
    ):
        run("contact", "add", "--name", name, "--phone", phone)
    run("contact", "add", "--name", "Erik")
    run("project", "new", "--occasion", "Familienessen", "--organizer", "Lukas")
    _, listing = run("project", "list")
    project_id = listing.split()[0]
    run(
        "project", "dates", "--project", project_id,
        "--day", "2026-08-08", "--day", "2026-08-09", "--time", "14:00-18:00",
    )
    run("project", "people", "--project", project_id, "--all")
    return project_id


def test_the_flow_in_the_order_an_agent_would_ask(run, project):
    code, output = run("project", "plan", "--project", project, "--show-task")
    assert code == 0
    assert "would call Anna" in output
    assert "NOT called Erik - no phone number" in output
    assert "4 call(s), about $0.20" in output
    assert "automatischer Assistent im Auftrag von Lukas" in output


def test_plan_shows_masked_numbers_only(run, project):
    _, output = run("project", "plan", "--project", project)
    assert "+15*****01" in output
    assert "+15555550101" not in output


def test_a_rehearsal_says_it_invented_the_answers(run, project):
    code, output = run("project", "call", "--project", project, "--mode", "rehearsal")
    assert code == 0
    assert "SIMULATED" in output
    assert "invented locally, no call was made" in output


def test_the_board_keeps_the_four_states_apart(run, project):
    run("project", "call", "--project", project, "--mode", "rehearsal")
    _, output = run("project", "board", "--project", project)
    assert "no phone    : Erik" in output
    assert "add a number and run again to catch up" in output
    assert "never counted as 'doesn't mind'" in output


def test_a_late_number_is_caught_up_without_calling_anybody_twice(run, project):
    run("project", "call", "--project", project, "--mode", "rehearsal")
    _, added = run("contact", "phone", "Erik", "+15555550199")
    assert "added to 1 running round(s)" in added

    _, output = run("project", "call", "--project", project, "--mode", "rehearsal")
    assert output.count("-> erik") == 1
    assert "-> anna" not in output


def test_criteria_are_reported_as_met_of_configured(run, project):
    run("project", "call", "--project", project, "--mode", "rehearsal")
    _, output = run(
        "project", "criteria", "--project", project, "--favourite", "1", "--must", "Anna"
    )
    assert "von 2 criteria" in output


def test_deciding_then_inviting(run, project):
    run("project", "call", "--project", project, "--mode", "rehearsal")
    code, output = run("project", "decide", "--project", project, "--slot", "1")
    assert code == 0
    assert "decided: Sa 08.08. 14:00-18:00" in output

    code, output = run("project", "invite", "--project", project)
    assert code == 0
    assert "Wir haben einen Termin gefunden" in output
    assert "Sa 08.08. 14:00-18:00" in output


def test_inviting_before_deciding_says_so(run, project):
    code, output = run("project", "invite", "--project", project)
    assert code == 1
    assert "no date has been decided" in output


def test_a_scripted_run_needs_a_fixture_backed_project(run, project):
    code, output = run("project", "call", "--project", project, "--mode", "script")
    assert code == 1
    assert "needs a fixture" in output


def test_the_demo_project_runs_from_the_bundled_fixture(run):
    run("project", "demo", "--fixture", "family-dinner")
    _, listing = run("project", "list")
    project_id = listing.split()[0]
    code, output = run("project", "call", "--project", project_id, "--mode", "script")
    assert code == 0
    assert "4 of 6 answered" in output
    assert "not reached : " in output
    assert "SIMULATED" not in output  # scripted answers are not invented ones


def test_a_refused_subject_is_stopped_at_creation(run):
    code, output = run(
        "project", "new", "--occasion", "Notfall im Haus", "--organizer", "Lukas"
    )
    assert code == 2
    assert "emergency" in output


def test_project_new_with_only_language_derives_a_matching_region_and_locale(run, tmp_path):
    """Field finding, 2026-08-11, the ``project`` half of the same bug:
    ``--language`` alone used to leave region/locale at ``project new``'s own
    independent defaults instead of following the chosen language."""
    code, _ = run("project", "new", "--occasion", "Meeting", "--organizer", "Lukas",
                  "--language", "en")
    assert code == 0

    store = Store(tmp_path / "cli.db")
    project = list(ProjectStore(store).projects())[0]
    assert project.language == "en"
    assert project.region == "US"
    assert project.locale == "en-US"


def test_project_new_with_an_explicit_region_and_locale_still_wins(run, tmp_path):
    code, _ = run("project", "new", "--occasion", "Meeting", "--organizer", "Lukas",
                  "--language", "de", "--region", "CH", "--locale", "de-CH")
    assert code == 0

    store = Store(tmp_path / "cli.db")
    project = list(ProjectStore(store).projects())[0]
    assert project.region == "CH"
    assert project.locale == "de-CH"


def test_contact_add_warns_about_a_substitute_umlaut_in_the_given_name(run):
    """No realistic first name is one of the fourteen listed words — this
    proves the mechanism (first token only, checked, printed) with a
    synthetic name rather than claiming real-world name coverage the
    word-list approach cannot actually offer (see FINDINGS.md)."""
    code, out = run("contact", "add", "--name", "Waere Beispiel", "--phone", "+15555550199")
    assert code == 0
    assert "WARNUNG" in out
    assert '"Waere"' in out


def test_contact_add_says_nothing_about_the_surname_which_is_never_spoken(run):
    """Only the first token (Participant.given_name) ever reaches the voice
    agent — a substitute umlaut in the surname alone must not warn."""
    code, out = run("contact", "add", "--name", "Anna Ueberacker", "--phone", "+15555550198")
    assert code == 0
    assert "WARNUNG" not in out


def test_project_new_warns_about_substitute_umlauts_in_occasion_and_organizer(run):
    code, out = run(
        "project", "new", "--occasion", "Feier fuer alle zurueck im Garten",
        "--organizer", "Lukas", "--language", "de",
    )
    assert code == 0
    assert "WARNUNG" in out
    assert '"fuer"' in out
    assert '"zurueck"' in out


def test_project_new_says_nothing_for_an_english_project(run):
    code, out = run(
        "project", "new", "--occasion", "We would like fuer to celebrate",
        "--organizer", "Lukas", "--language", "en",
    )
    assert code == 0
    assert "WARNUNG" not in out


def test_project_question_warns_about_substitute_umlauts(run, tmp_path):
    run("project", "new", "--occasion", "Feiertag", "--organizer", "Lukas", "--mode", "roundtable")
    _, listing = run("project", "list")
    project_id = listing.split()[0]
    code, out = run(
        "project", "question", "--project", project_id,
        "--question", "Was koennen wir spaeter besprechen?",
    )
    assert code == 0
    assert "WARNUNG" in out
    assert '"koennen"' in out
    assert '"spaeter"' in out


def test_project_wording_warns_about_substitute_umlauts(run, project):
    code, out = run(
        "project", "wording", "--project", project,
        "--greeting", "Natuerlich freuen wir uns, von dir zu hoeren.",
    )
    assert code == 0
    assert "WARNUNG" in out
    assert '"Natuerlich"' in out


def test_an_unusable_number_is_explained(run):
    code, output = run("contact", "add", "--name", "Krumm", "--phone", "0151 2345678")
    assert code == 1
    assert "E.164" in output


def test_a_project_id_prefix_is_enough(run, project):
    code, output = run("project", "board", "--project", project[:12])
    assert code == 0
    assert "Familienessen" in output
