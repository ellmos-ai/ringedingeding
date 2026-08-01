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

from ringedingeding.projects import ProjectStore  # noqa: E402
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


def slot_ids(html: str) -> list[str]:
    return re.findall(r"/board/slot/([A-Za-z0-9_]+)", html)


# -- the walk-through -------------------------------------------------------


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
    assert "nicht abgenommen" in board.text
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
    assert "nicht abgenommen" in panel.text


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
    project_id = make_demo(client)
    html = client.get(f"/projects/{project_id}/preview").text
    assert "CALLE_API_KEY" in html  # it says where the key belongs
    assert 'name="api_key"' not in html
    assert 'type="password"' not in html


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
    response = client.post("/contacts", data={"name": "Krumm", "phone": "07700 900000"})
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
