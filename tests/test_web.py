"""The web interface.

Two things are worth more than the rest here and are tested first:

* **the browser does not drive** — a round survives the page that started it,
* **no phone number is ever rendered in full**, on any page.
"""

from __future__ import annotations

import re
import time

import pytest

pytest.importorskip("fastapi", reason="the web interface is an optional extra")

from fastapi.testclient import TestClient  # noqa: E402

from ringedingeding.projects import ProjectMode, ProjectStore, RoundKind  # noqa: E402
from ringedingeding.safety import LIVE_CONFIRMATION_PHRASE  # noqa: E402
from ringedingeding.store import Store  # noqa: E402
from ringedingeding.web.app import create_app  # noqa: E402

# Anything that looks like a dialable number in rendered HTML.
RAW_NUMBER = re.compile(r"\+\d{6,}")


@pytest.fixture()
def db(tmp_path):
    return tmp_path / "web.db"


@pytest.fixture()
def client(db):
    with TestClient(create_app(db)) as opened:
        yield opened


def wait_for_round(client, project_id, timeout=10.0):
    """Wait until the background job of this project has finished."""
    app = client.app
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = app.state.jobs.get(project_id)
        if job is not None and not job.running:
            return job
        time.sleep(0.05)
    raise AssertionError("the round never finished")


def make_demo(client) -> str:
    response = client.post("/demo", data={"fixture": "family-dinner"}, follow_redirects=False)
    assert response.status_code == 303
    return response.headers["location"].split("/")[2]


def test_demo_route_seeds_advisor_fixture_as_a_roundtable(client, db):
    response = client.post("/demo", data={"fixture": "team-retro"}, follow_redirects=False)

    assert response.status_code == 303
    project_id = response.headers["location"].split("/")[2]
    with Store(db) as store:
        projects = ProjectStore(store)
        project = projects.project(project_id)
        assert project.mode == ProjectMode.ROUNDTABLE
        assert projects.round_ids(project_id, RoundKind.AVAILABILITY) == []
        assert len(projects.round_ids(project_id, RoundKind.ROUNDTABLE)) == 1


def slot_ids(html: str) -> list[str]:
    return re.findall(r"/board/slot/([A-Za-z0-9_]+)", html)


# -- the walk-through -------------------------------------------------------


def test_home_is_a_cockpit_with_two_prominent_chain_entries(client):
    html = client.get("/").text

    assert 'class="cockpit-hero"' in html
    assert 'class="hero-logo" src="/static/brand/motiv.png"' in html
    assert '<link rel="icon" type="image/png" href="/static/brand/motiv.png">' in html
    assert client.get("/static/brand/motiv.png").status_code == 200
    assert client.get("/static/brand/thumbnail.png").status_code == 200
    assert 'href="/?mode=schedule#new-chain"' in html
    assert 'href="/?mode=roundtable#new-chain"' in html
    assert "Termin-Kette starten" in html
    assert "Advisor-Kette starten" in html


def test_every_cockpit_tile_leads_to_an_existing_area(client):
    html = client.get("/").text

    assert html.count('class="area-tile ') == 5
    for target in ("/calendar", "/contacts", "/groups", "#chains", "/calendar#export"):
        assert f'href="{target}"' in html
    for route in ("/calendar", "/contacts", "/groups"):
        assert client.get(route).status_code == 200
    assert 'id="chains"' in html
    assert 'id="export"' in client.get("/calendar").text


def test_a_prominent_entry_preselects_its_chain_type(client):
    advisor = client.get("/?mode=roundtable").text
    schedule = client.get("/?mode=schedule").text

    assert re.search(r'type="hidden" name="mode"\s+value="roundtable"', advisor)
    assert re.search(r'type="hidden" name="mode"\s+value="schedule"', schedule)
    assert "mode-choice mode-switch" not in advisor
    assert "mode-choice mode-switch" not in schedule


def test_the_start_form_visibly_changes_with_the_selected_product(client):
    advisor = client.get("/?mode=roundtable").text
    schedule = client.get("/?mode=schedule").text

    assert 'data-chain-form data-mode="roundtable"' in advisor
    assert re.search(
        r'<section class="mode-summary" data-mode-panel="roundtable">', advisor
    )
    assert re.search(
        r'<section class="mode-summary" data-mode-panel="schedule" hidden>', advisor
    )
    assert re.search(r'<fieldset data-schedule-only hidden disabled>', advisor)

    assert 'data-chain-form data-mode="schedule"' in schedule
    assert re.search(
        r'<section class="mode-summary" data-mode-panel="schedule">', schedule
    )
    assert re.search(r'<fieldset data-schedule-only>', schedule)
    assert not re.search(r'<fieldset data-schedule-only hidden', schedule)


def test_the_language_picker_marks_the_language_that_is_actually_shown(client):
    german = client.get("/").text
    assert re.search(
        r'<a class="language active"\s+href="/language/de\?next=/"[^>]*'
        r'aria-current="true">DE</a>',
        german,
    )
    assert re.search(r'<a class="language"\s+href="/language/en\?next=/"', german)

    english = client.get("/language/en?next=/").text
    assert '<html lang="en">' in english
    assert re.search(r'<a class="language"\s+href="/language/de\?next=/"', english)
    assert re.search(
        r'<a class="language active"\s+href="/language/en\?next=/"[^>]*'
        r'aria-current="true">EN</a>',
        english,
    )


def test_the_whole_flow_works_offline_from_a_fixture(client):
    project_id = make_demo(client)

    preview = client.get(f"/projects/{project_id}/preview")
    assert preview.status_code == 200
    assert "6" in preview.text
    assert "$0.30" in preview.text  # 6 calls at five cents
    assert "Guten Tag, hier ist ein automatischer Assistent" in preview.text

    started = client.post(
        f"/projects/{project_id}/run", data={"mode": "script"}, follow_redirects=False
    )
    assert started.status_code == 303
    wait_for_round(client, project_id)

    board = client.get(f"/projects/{project_id}/board")
    assert board.status_code == 200
    assert "4 von 6" in board.text
    assert "NO_ANSWER" not in board.text  # statuses are shown in German words
    assert "niemand da" in board.text
    assert "besetzt" in board.text

    ids = slot_ids(board.text)
    detail = client.get(f"/projects/{project_id}/board/slot/{ids[0]}")
    assert detail.status_code == 200
    assert "Kann (4)" in detail.text
    assert "Nicht erreicht (2)" in detail.text

    client.post(
        f"/projects/{project_id}/criteria", data={"favourite": ids[0], "min_count": "4"}
    )
    board = client.get(f"/projects/{project_id}/board")
    assert "2 von 2 Kriterien" in board.text

    client.post(f"/projects/{project_id}/decide", data={"slot_id": ids[0]})
    invite = client.get(f"/projects/{project_id}/invite")
    assert invite.status_code == 200
    assert "Wir haben einen Termin gefunden" in invite.text


def test_creating_a_project_by_hand_and_calling_nobody(client):
    created = client.post(
        "/projects",
        data={"occasion": "Spieleabend", "organizer": "Lukas", "date_kind": "day_slots"},
        follow_redirects=False,
    )
    assert created.status_code == 303
    project_id = created.headers["location"].split("/")[2]

    saved = client.post(
        f"/projects/{project_id}/dates",
        data={
            "date_kind": "day_slots",
            "day": ["2026-08-08", "2026-08-09"],
            "start": ["18:00", ""],
            "end": ["21:00", ""],
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303

    people = client.get(f"/projects/{project_id}/people")
    assert people.status_code == 200
    assert "Kontaktbuch ist leer" in people.text

    preview = client.get(f"/projects/{project_id}/preview")
    assert "Es gibt niemanden anzurufen" in preview.text


def test_dates_without_a_day_are_refused_with_a_readable_message(client):
    project_id = make_demo(client)
    response = client.post(
        f"/projects/{project_id}/dates", data={"date_kind": "day_slots", "day": [""]}
    )
    assert response.status_code == 422
    assert "mindestens einen Tag" in response.text


def test_date_validation_error_uses_the_selected_interface_language(client):
    project_id = make_demo(client)
    client.get("/language/en?next=/")

    response = client.post(
        f"/projects/{project_id}/dates", data={"date_kind": "day_slots", "day": [""]}
    )

    assert response.status_code == 422
    assert "Please select at least one day." in response.text
    assert "Bitte mindestens einen Tag auswählen." not in response.text


# -- the architectural promise ----------------------------------------------


def test_a_round_survives_the_page_that_started_it(client, db):
    """Close the browser: the calls keep going and the state is on disk.

    Simulated by never asking the page for anything again — the answers are read
    straight out of the database afterwards, exactly as a page opened an hour
    later would read them.
    """
    project_id = make_demo(client)
    client.post(f"/projects/{project_id}/run", data={"mode": "script"})
    wait_for_round(client, project_id)

    store = Store(db)
    try:
        projects = ProjectStore(store)
        poll_id = projects.round_ids(project_id, "availability")[0]
        assert len(store.answers(poll_id)) == 6
    finally:
        store.close()


def test_the_live_panel_is_complete_without_the_stream(client):
    """A page with JavaScript switched off still shows the whole truth."""
    project_id = make_demo(client)
    client.post(f"/projects/{project_id}/run", data={"mode": "script"})
    wait_for_round(client, project_id)

    panel = client.get(f"/projects/{project_id}/live/panel")
    assert panel.status_code == 200
    assert "hat geantwortet" in panel.text
    assert "niemand da" in panel.text


def test_the_stream_sends_a_panel_and_then_closes(client):
    project_id = make_demo(client)
    client.post(f"/projects/{project_id}/run", data={"mode": "script"})

    with client.stream("GET", f"/projects/{project_id}/live/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = []
        for line in response.iter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
            if events and events[-1] == "done":
                break
    assert "panel" in events
    assert events[-1] == "done"


def test_a_second_run_of_the_same_project_is_refused(client):
    """Two rounds at once would dial the same people twice."""
    project_id = make_demo(client)
    client.post(f"/projects/{project_id}/run", data={"mode": "rehearsal"})
    second = client.post(f"/projects/{project_id}/run", data={"mode": "rehearsal"})
    # Either the first one is still running (409) or it finished in between and
    # there is simply nothing left to call — never a second set of calls.
    if second.status_code == 409:
        assert "bereits eine Runde" in second.text
    else:
        wait_for_round(client, project_id)


# -- safety on this surface -------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["/", "/contacts", "/projects/{id}/preview", "/projects/{id}/board",
     "/projects/{id}/live", "/projects/{id}/invite"],
)
def test_no_page_ever_renders_a_full_phone_number(client, path):
    project_id = make_demo(client)
    client.post(f"/projects/{project_id}/run", data={"mode": "script"})
    wait_for_round(client, project_id)
    ids = slot_ids(client.get(f"/projects/{project_id}/board").text)
    client.post(f"/projects/{project_id}/decide", data={"slot_id": ids[0]})

    response = client.get(path.format(id=project_id))
    assert response.status_code == 200
    assert not RAW_NUMBER.findall(response.text), f"{path} leaks a phone number"


def test_the_interface_never_asks_for_credentials(client):
    """The working pages take no key, and point at the one page that does.

    The preview page used to name ``CALLE_API_KEY`` itself; it now links to the
    settings page, which is the better place for it. The settings page has a
    key field on purpose — that is what it is for — and refuses to write one in
    ``huckepack-only-host`` mode; see ``test_huckepack.py``.
    """
    project_id = make_demo(client)
    preview = client.get(f"/projects/{project_id}/preview").text
    assert "/settings" in preview  # it says where the key belongs
    assert 'name="api_key"' not in preview
    assert 'type="password"' not in preview

    settings = client.get("/settings").text
    assert "CALLE_API_KEY" in settings  # and there the env variable is named


def test_live_without_the_phrase_dials_nothing(client):
    project_id = make_demo(client)
    response = client.post(
        f"/projects/{project_id}/run", data={"mode": "live", "confirmation": "ja bitte"}
    )
    assert response.status_code == 403
    assert LIVE_CONFIRMATION_PHRASE in response.text
    assert client.app.state.jobs.get(project_id) is None


def test_live_with_the_phrase_still_refuses_example_numbers(client, monkeypatch):
    """The confirmation is not a licence to dial a fixture's placeholders."""
    monkeypatch.setenv("CALLE_API_KEY", "iams_live_not_a_real_key")
    project_id = make_demo(client)
    response = client.post(
        f"/projects/{project_id}/run",
        data={"mode": "live", "confirmation": LIVE_CONFIRMATION_PHRASE},
        follow_redirects=False,
    )
    # The job starts and fails inside; no HTTP request to CALL-E is ever made.
    if response.status_code == 303:
        job = wait_for_round(client, project_id)
        assert job.error and "example numbers" in job.error
    else:
        assert response.status_code == 403


def test_a_refused_subject_never_becomes_a_project(client):
    response = client.post(
        "/projects", data={"occasion": "Notfall im Haus", "organizer": "Lukas"}
    )
    assert response.status_code == 422
    assert "emergency" in response.text
    assert client.get("/").text.count("Notfall im Haus") == 0


def test_a_rehearsal_says_so_on_every_screen(client):
    project_id = make_demo(client)
    client.post(f"/projects/{project_id}/run", data={"mode": "rehearsal"})
    wait_for_round(client, project_id)

    for path in ("live", "board"):
        html = client.get(f"/projects/{project_id}/{path}").text
        assert "Erfundene Antworten" in html, f"{path} does not admit to being a rehearsal"

    client.post(f"/projects/{project_id}/reset")
    assert "Erfundene Antworten" not in client.get(f"/projects/{project_id}/board").text


# -- contacts ---------------------------------------------------------------


def test_a_contact_without_a_number_is_greyed_out_and_not_called(client):
    project_id = make_demo(client)
    client.post("/contacts", data={"name": "Ohne Nummer", "project": project_id})

    people = client.get(f"/projects/{project_id}/people").text
    assert "keine Telefonnummer" in people
    assert "greyed" in people


def test_adding_a_number_afterwards_catches_the_call_up(client, db):
    project_id = make_demo(client)
    client.post("/contacts", data={"name": "Spät Dabei", "project": project_id})

    store = Store(db)
    try:
        projects = ProjectStore(store)
        contact = next(c for c in projects.contacts() if c.name == "Spät Dabei")
        invitees = [i.contact_id for i in projects.invitees(project_id)] + [contact.id]
    finally:
        store.close()

    client.post(f"/projects/{project_id}/people", data={"contact": invitees})
    client.post(f"/contacts/{contact.id}", data={"name": "Spät Dabei", "phone": "+15555550777"})

    preview = client.get(f"/projects/{project_id}/preview").text
    assert "Spät Dabei" in preview
    assert "7 Anrufe" not in preview or "Spät Dabei" in preview


def test_an_unusable_number_is_explained_not_swallowed(client):
    response = client.post("/contacts", data={"name": "Krumm", "phone": "0151 2345678"})
    assert response.status_code == 422
    assert "E.164" in response.text
    assert "Krumm" not in client.get("/contacts").text


def test_a_photo_is_stored_and_served_back(client, db):
    png = bytes.fromhex("89504e470d0a1a0a")
    client.post(
        "/contacts",
        data={"name": "Mit Bild", "phone": "+15555550123"},
        files={"photo": ("face.png", png, "image/png")},
    )
    store = Store(db)
    try:
        contact = next(c for c in ProjectStore(store).contacts() if c.name == "Mit Bild")
    finally:
        store.close()
    served = client.get(f"/contacts/{contact.id}/photo")
    assert served.status_code == 200
    assert served.content == png
    assert served.headers["content-type"] == "image/png"


def test_htmx_is_served_from_this_machine(client):
    """A CDN reference would make the interface useless offline."""
    response = client.get("/static/htmx.min.js")
    assert response.status_code == 200
    assert len(response.content) > 10_000
    for page in ("/", "/contacts"):
        assert "https://unpkg" not in client.get(page).text
        assert "cdn." not in client.get(page).text


# -- the node kinds and end states of ABLAUF.md -----------------------------


def test_the_six_end_states_are_kept_apart(client, db):
    """ABLAUF.md section 2: red means somebody said no, grey means nobody was there.

    Collapsing the two is the mistake this test exists to catch. A struck-out
    name against an unanswered telephone would claim knowledge nobody has.
    """
    from ringedingeding.models import Answer, CallStatus
    from ringedingeding.web.ui import live_rows

    project_id = make_demo(client)
    store = Store(db)
    try:
        projects = ProjectStore(store)
        poll_id = projects.round_ids(project_id, "availability")[0]
        people = store.participants(poll_id)
        statuses = [
            CallStatus.COMPLETED,
            CallStatus.DECLINED,
            CallStatus.NO_ANSWER,
            CallStatus.BUSY,
            CallStatus.VOICEMAIL,
            CallStatus.FAILED,
        ]
        for participant, status in zip(people, statuses):
            store.record_answer(
                Answer(
                    participant_id=participant.id,
                    call_status=status,
                    structured={"reachable": True, "refused": False}
                    if status is CallStatus.COMPLETED
                    else {},
                    error="something went wrong" if status is CallStatus.FAILED else None,
                )
            )
        rows = live_rows(
            store.participants(poll_id), store.answers(poll_id), {}, None
        )
    finally:
        store.close()

    states = {row.ref: row.state for row in rows}
    by_status = dict(zip([p.ref for p in people], statuses))
    for ref, status in by_status.items():
        expected = {
            CallStatus.COMPLETED: "answered",
            CallStatus.DECLINED: "declined",
            CallStatus.NO_ANSWER: "absent",
            CallStatus.BUSY: "absent",
            CallStatus.VOICEMAIL: "absent",
            CallStatus.FAILED: "failed",
        }[status]
        assert states[ref] == expected, f"{status.value} should render as {expected}"

    # "Nobody was there" is uncertain, never a verdict.
    assert all(row.uncertain for row in rows if row.state == "absent")
    assert not any(row.uncertain for row in rows if row.state == "declined")
    # A failure has to say why.
    failure = next(row for row in rows if row.state == "failed")
    assert "something went wrong" in failure.detail


def test_the_panel_marks_absence_with_a_question_mark_not_a_cross(client):
    project_id = make_demo(client)
    client.post(f"/projects/{project_id}/run", data={"mode": "script"})
    wait_for_round(client, project_id)

    panel = client.get(f"/projects/{project_id}/live/panel").text
    assert "caller absent" in panel
    assert "caller answered" in panel
    # The fixture has NO_ANSWER and BUSY, so nothing may be struck through.
    assert "caller declined" not in panel


def test_optional_steps_stay_folded_away(client):
    """ABLAUF.md section 6: an OPTIONAL node is a collapsed section.

    An optional step that sits open gets worked through, and then it was not
    optional.
    """
    project_id = make_demo(client)

    wording = client.get(f"/projects/{project_id}/wording").text
    assert "<details class=\"optional\"" in wording
    assert "<details class=\"optional\" open" not in wording

    board = client.get(f"/projects/{project_id}/board").text
    assert "Was ist dir wichtig?" in board
    assert "<details class=\"optional\"" in board


def test_a_set_optional_step_is_shown_open(client):
    """Folded away when empty, open once it carries something."""
    project_id = make_demo(client)
    client.post(
        f"/projects/{project_id}/wording", data={"greeting": ["Schön, dich zu hören."]}
    )
    wording = client.get(f"/projects/{project_id}/wording").text
    assert "<details class=\"optional\" open" in wording


def test_urgency_changes_the_tone_and_nothing_else(client, db):
    """ABLAUF.md B3 — and it must not become a licence to press somebody."""
    created = client.post(
        "/projects",
        data={
            "occasion": "Spieleabend",
            "organizer": "Lukas",
            "date_kind": "day_slots",
            "urgency": "wirklich dringend",
        },
        follow_redirects=False,
    )
    project_id = created.headers["location"].split("/")[2]
    client.post(
        f"/projects/{project_id}/dates",
        data={"date_kind": "day_slots", "day": ["2026-08-08"],
              "start": ["18:00"], "end": ["21:00"]},
    )
    store = Store(db)
    try:
        projects = ProjectStore(store)
        contact = projects.create_contact(name="Anna", phone="+15555550100")
    finally:
        store.close()
    client.post(f"/projects/{project_id}/people", data={"contact": [contact.id]})

    task = client.get(f"/projects/{project_id}/preview").text
    assert "Es eilt (wirklich dringend)" in task
    assert "dränge trotzdem niemanden" in task
    # Not quoted: the organizer's private note is never read out loud.
    assert '"wirklich dringend"' not in task
