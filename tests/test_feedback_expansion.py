"""Regression coverage for the six user-feedback expansion points."""

from __future__ import annotations

import time
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from conftest import answer, make_participant, make_poll
from manage_translations import source_keys
from ringedingeding.calendar_export import calendar_entries, render_ics, render_xlsx
from ringedingeding.merge import ChoiceMerge, OpenMerge, merge_poll
from ringedingeding.models import PollKind
from ringedingeding.projects import ProjectMode, ProjectStore
from ringedingeding.service import create_project, decide, set_advisor_question, set_dates
from ringedingeding.store import Store
from ringedingeding.translator import TranslationSystem


def test_arbitrary_group_is_reusable_project_configuration(store):
    projects = ProjectStore(store)
    anna = projects.create_contact(name="Anna", phone="+15555550101")
    ben = projects.create_contact(name="Ben", phone="+15555550102")
    group = projects.create_group(
        name="Donnerstagsdenker", contact_ids=[anna.id, ben.id], note="not a fixed preset"
    )

    project = create_project(
        projects,
        occasion="Neue Vereinsidee",
        organizer="Lukas",
        mode=ProjectMode.ROUNDTABLE,
        group_id=group.id,
    )

    assert projects.group(group.id).name == "Donnerstagsdenker"
    assert [invitee.name for invitee in projects.invitees(project.id)] == ["Anna", "Ben"]
    assert project.group_id == group.id


def test_open_advice_reports_tendency_countervoices_and_reasons():
    poll = make_poll(kind=PollKind.OPEN, slots=(), question="Should we expand?")
    people = [make_participant(ref) for ref in ("a", "b", "c")]
    merged = merge_poll(
        poll,
        people,
        {
            "p_a": answer("p_a", reachable=True, refused=False, answer="Yes", stance="support", reasons=["More room"]),
            "p_b": answer("p_b", reachable=True, refused=False, answer="Yes, carefully", stance="support", reasons=["Demand"]),
            "p_c": answer("p_c", reachable=True, refused=False, answer="No", stance="against", reasons=["Cost"], concerns=["Debt"]),
        },
    )

    assert isinstance(merged, OpenMerge)
    assert merged.primary_tendency and merged.primary_tendency.stance == "support"
    assert [entry.name for entry in merged.countervoices] == ["C"]
    assert merged.entries[2].reasons == ("Cost",)
    assert "countervoice" in merged.headline


def test_advisor_options_create_a_reasoned_vote(store):
    projects = ProjectStore(store)
    project = create_project(
        projects, occasion="Logo direction", organizer="Mira", mode=ProjectMode.ROUNDTABLE
    )
    configured = set_advisor_question(
        projects, project, "Which direction?", options=["Bold", "Calm", "Bold"]
    )
    poll = make_poll(kind=PollKind.CHOICE, options=configured.options, slots=())
    merged = merge_poll(
        poll,
        [make_participant("a")],
        {"p_a": answer("p_a", reachable=True, refused=False, choice="Bold", reason="Memorable", concerns=["May polarise"])},
    )

    assert configured.kind == "choice"
    assert configured.options == ("Bold", "Calm")
    assert isinstance(merged, ChoiceMerge)
    assert merged.reasons == (("A", "Memorable"),)
    assert merged.concerns == (("A", "May polarise"),)


def test_filtered_calendar_is_the_single_source_for_ics_and_xlsx(store):
    projects = ProjectStore(store)
    first = create_project(projects, occasion="Tennis", organizer="Lukas")
    second = create_project(projects, occasion="Running", organizer="Lukas")
    advisor = create_project(
        projects, occasion="Club idea", organizer="Lukas", mode=ProjectMode.ROUNDTABLE
    )
    first_slots = set_dates(
        store,
        projects,
        first,
        [{"day_date": "2026-08-08", "start_time": "18:00", "end_time": "20:00"}],
    )
    set_dates(
        store,
        projects,
        second,
        [{"day_date": "2026-08-09", "all_day": True}],
    )
    decide(projects, first, first_slots[0].id)

    entries = calendar_entries(projects, [first.id])
    ics = render_ics(entries).decode("utf-8")
    xlsx = render_xlsx(entries)

    assert [entry.project_title for entry in entries] == ["Tennis"]
    assert entries[0].decided
    assert "SUMMARY:Tennis" in ics and "STATUS:CONFIRMED" in ics
    assert "Running" not in ics and advisor.occasion not in ics
    assert xlsx.startswith(b"PK")
    with ZipFile(BytesIO(xlsx)) as workbook:
        sheet = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "Tennis" in sheet and "Running" not in sheet
    long_ics = render_ics((replace(entries[0], project_title="Überlanger Termin " * 10),))
    assert all(len(line) <= 75 for line in long_ics.split(b"\r\n"))


def test_explicit_empty_calendar_filter_exports_nothing(store):
    projects = ProjectStore(store)
    project = create_project(projects, occasion="Dinner", organizer="Lukas")
    set_dates(store, projects, project, [{"day_date": "2026-08-10", "all_day": True}])
    assert calendar_entries(projects, []) == ()
    assert b"BEGIN:VEVENT" not in render_ics(())


def test_pythonbox_catalog_contract_covers_every_template_key():
    from ringedingeding.models import CallStatus
    from ringedingeding.web.ui import status_word

    translator = TranslationSystem(language="en")
    assert not (source_keys() - translator.translations.keys())
    assert all(entry.get("en", "").strip() for entry in translator.translations.values())
    assert translator.t("Kalender") == "Calendar"
    translator.set_language("de")
    assert translator.t("Kalender") == "Kalender"
    assert status_word(CallStatus.COMPLETED, "en") == "answered"
    assert status_word(CallStatus.NO_ANSWER, "de") == "niemand da"


def test_english_web_surface_and_product_split(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ringedingeding.web.app import create_app

    with TestClient(create_app(tmp_path / "english.db")) as client:
        response = client.get("/language/en?next=/")
        assert response.status_code == 200
        assert "What should we find out together?" in response.text
        assert "Find a Date" in response.text
        assert "Ask Your Advisor" in response.text
        assert "Was sollen wir gemeinsam herausfinden?" not in response.text
        assert '<html lang="en">' in response.text


def test_calendar_route_exports_exactly_its_checked_project(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ringedingeding.web.app import create_app

    database = tmp_path / "calendar.db"
    with Store(database) as store:
        projects = ProjectStore(store)
        tennis = create_project(projects, occasion="Tennisabend", organizer="Mira")
        running = create_project(projects, occasion="Lauftreff", organizer="Mira")
        set_dates(store, projects, tennis, [{"day_date": "2026-09-01", "all_day": True}])
        set_dates(store, projects, running, [{"day_date": "2026-09-02", "all_day": True}])

    with TestClient(create_app(database)) as client:
        page = client.get(f"/calendar?filtered=1&project={tennis.id}")
        # Every project remains available as a checkbox; only Tennis has a
        # second occurrence in the visible event list.
        assert page.text.count("Tennisabend") == 2
        assert page.text.count("Lauftreff") == 1
        ics = client.get(f"/calendar.ics?project={tennis.id}")
        assert "SUMMARY:Tennisabend" in ics.text and "Lauftreff" not in ics.text
        xlsx = client.get(f"/calendar.xlsx?project={tennis.id}")
        with ZipFile(BytesIO(xlsx.content)) as workbook:
            sheet = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert "Tennisabend" in sheet and "Lauftreff" not in sheet


def test_advisor_web_flow_runs_fully_offline(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ringedingeding.web.app import create_app

    with TestClient(create_app(tmp_path / "advisor.db")) as client:
        client.post("/contacts", data={"name": "Anna", "phone": "+15555550101"})
        created_group = client.post(
            "/groups", data={"name": "Ideenrat", "contact": []}, follow_redirects=False
        )
        assert created_group.status_code == 303
        with Store(tmp_path / "advisor.db") as store:
            projects = ProjectStore(store)
            group = projects.groups()[0]
            anna = projects.contacts()[0]
            projects.set_group_members(group.id, [anna.id])

        created = client.post(
            "/projects",
            data={"occasion": "Sommerfest", "organizer": "Mira", "mode": "roundtable", "group_id": group.id},
            follow_redirects=False,
        )
        project_id = created.headers["location"].split("/")[2]
        assert created.headers["location"].endswith("/advisor")
        saved = client.post(
            f"/projects/{project_id}/advisor",
            data={"question": "Sollen wir größer planen?", "option": ["Ja", "Nein"]},
            follow_redirects=False,
        )
        assert saved.status_code == 303
        client.post(f"/projects/{project_id}/people", data={"contact": [anna.id]})
        preview = client.get(f"/projects/{project_id}/preview")
        assert "Sollen wir größer planen?" in preview.text
        started = client.post(f"/projects/{project_id}/run", data={"mode": "rehearsal"})
        assert started.status_code == 200
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            job = client.app.state.jobs.get(project_id)
            if job and not job.running:
                break
            time.sleep(0.03)
        board = client.get(f"/projects/{project_id}/board")
        assert board.status_code == 200
        assert "Was die Runde meint" in board.text
        assert "Erfundene Antworten" in board.text


def test_design_accents_are_local_and_mode_specific():
    css = (Path(__file__).parents[1] / "ringedingeding/web/static/app.css").read_text(encoding="utf-8")
    assert ".mode-card" in css
    assert ".advisor-summary" in css
    assert "linear-gradient" in css
    assert "url(http" not in css
