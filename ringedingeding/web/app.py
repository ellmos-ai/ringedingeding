"""The web interface: server-rendered HTML, no build step, no npm.

What the browser does and does not do
-------------------------------------

It displays. Forms post and the server answers with a page; ``htmx`` swaps a
fragment where a full reload would lose your place; the live view listens on a
Server-Sent-Events stream. **No call is driven from the browser** — see
:mod:`ringedingeding.web.jobs` — so closing the window is harmless and the live
view is also complete without any JavaScript at all (it carries a meta refresh).

Every route is a thin wrapper around :mod:`ringedingeding.service`. If a rule
appears here that the command line does not have, that is a bug.

Safety, restated for this surface
---------------------------------

* Phone numbers are **never** rendered in full. Not in a list, not in a form.
* The order text is shown in full **before** anything is sent.
* Live calling needs the confirmation phrase typed into the page, exactly as
  the command line needs it typed into the terminal.
* The settings page accepts a key for the ignored local config and displays
  only a masked fingerprint. It never sends the value back to the browser.
* The server binds to ``127.0.0.1``. There is no login because there is no
  network exposure to protect.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from datetime import datetime

from .. import huckepack_key, huckepack_storage, huckepack_web
from .. import __version__
from ..calendar_export import calendar_entries, render_ics, render_xlsx
from ..calle_credentials import (
    CalleCredentialError,
    DEFAULT_CONFIG_FILE,
    DEFAULT_ENV_FILE,
    load_calle_settings,
    save_project_api_key,
)
from ..fixtures import bundled_fixtures
from ..phone import InvalidPhoneNumber
from ..projects import (
    ChannelKind,
    DateKind,
    ProjectMode,
    ProjectState,
    ProjectStore,
    RoundKind,
)
from ..safety import LIVE_CONFIRMATION_PHRASE, LiveCallBlocked, SensitiveContent
from ..service import (
    COST_PER_CALL_USD,
    RunMode,
    advisor_board,
    advisor_question,
    availability_round,
    board,
    day_slot_specs,
    decide,
    default_invitation_text,
    api_key_present,
    create_project,
    invitation_round,
    preview,
    resync_contact,
    roundtable_round,
    seed_from_fixture,
    set_advisor_question,
    set_criteria,
    set_dates,
    set_invitees,
    set_wording,
    wording,
)
from ..store import DEFAULT_DB_PATH, Store
from ..calle_translator import TranslationSystem
from .jobs import Job, JobBusy, JobRegistry
from .ui import (
    avatar_colour,
    calendar_days,
    live_rows,
    person_colour,
    status_word,
)

__all__ = ["create_app", "run"]

HERE = Path(__file__).parent
DATA_NOTE = (
    "Alles, was im Auftragstext steht, verlässt diesen Rechner und wird von "
    "CALL-E / AiRudder in Singapur verarbeitet."
)
MAX_PHOTO_BYTES = 2 * 1024 * 1024
_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


class Ctx:
    """One request's database handles. Opened per request, closed after it.

    Not a shared connection on purpose: the background jobs run in their own
    threads with their own handles, and SQLite does not share one between them.
    """

    def __init__(self, db_path: str) -> None:
        self.store = Store(db_path)
        self.projects = ProjectStore(self.store)

    def close(self) -> None:
        self.store.close()


def create_app(db_path: str | Path = DEFAULT_DB_PATH) -> FastAPI:
    db = str(db_path)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        yield
        # Stopping the server stops starting new calls; conversations already in
        # progress are given a moment to finish rather than cut off mid-sentence.
        application.state.jobs.shutdown()

    app = FastAPI(
        title="Ringedingeding",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.db_path = db
    app.state.jobs = JobRegistry(db)

    # Server modes: descriptor, browser snapshot, per-request session and key.
    huckepack_web.install(app)

    templates = Jinja2Templates(directory=str(HERE / "templates"))
    templates.env.globals.update(
        avatar_colour=avatar_colour,
        person_colour=person_colour,
        status_word=status_word,
        cost_per_call=COST_PER_CALL_USD,
        live_phrase=LIVE_CONFIRMATION_PHRASE,
        data_note=DATA_NOTE,
        version=__version__,
        t=lambda text, **values: text.format(**values) if values else text,
    )
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    # -- plumbing -----------------------------------------------------------

    def ctx() -> Ctx:
        return Ctx(db)

    def page(
        request: Request, name: str, *, status_code: int = 200, **values: Any
    ) -> HTMLResponse:
        language = _ui_language(request)
        translator = TranslationSystem(language=language)
        values.update(
            t=translator.t,
            status_word=lambda status: status_word(status, language),
            ui_language=language,
            html_language=language,
        )
        return templates.TemplateResponse(request, name, values, status_code=status_code)

    def back(project_id: str, step: str = "") -> RedirectResponse:
        target = f"/projects/{project_id}" + (f"/{step}" if step else "")
        return RedirectResponse(target, status_code=303)

    @app.exception_handler(SensitiveContent)
    async def _sensitive(request: Request, error: SensitiveContent) -> Response:
        return page(request, "error.html", title=_t(request, "Abgelehnt"), detail=str(error), status_code=422)

    @app.exception_handler(LiveCallBlocked)
    async def _blocked(request: Request, error: LiveCallBlocked) -> Response:
        return page(request, "error.html", title=_t(request, "Echte Anrufe blockiert"), detail=str(error), status_code=403)

    @app.exception_handler(InvalidPhoneNumber)
    async def _phone(request: Request, error: InvalidPhoneNumber) -> Response:
        return page(request, "error.html", title=_t(request, "Rufnummer"), detail=str(error), status_code=422)

    @app.exception_handler(JobBusy)
    async def _busy(request: Request, error: JobBusy) -> Response:
        return page(request, "error.html", title=_t(request, "Läuft schon"), detail=str(error), status_code=409)

    # -- home ---------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> Response:
        context = ctx()
        try:
            projects = context.projects.projects()
            contacts = context.projects.contacts()
            return page(
                request,
                "index.html",
                projects=projects,
                contact_count=len(contacts),
                groups=context.projects.groups(),
                fixtures=sorted(bundled_fixtures()),
                today=_today(),
            )
        finally:
            context.close()

    @app.get("/language/{language}")
    def change_language(language: str, next: str = "/") -> Response:
        if language not in TranslationSystem.SUPPORTED_LANGUAGES:
            raise HTTPException(status_code=404, detail="language not supported")
        target = next if next.startswith("/") and not next.startswith("//") else "/"
        response = RedirectResponse(target, status_code=303)
        response.set_cookie("rd_lang", language, max_age=31_536_000, samesite="lax")
        return response

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request, saved: bool = False) -> Response:
        error = ""
        try:
            settings = load_calle_settings(required=False)
        except CalleCredentialError as caught:
            settings = None
            error = str(caught)
        return page(
            request,
            "settings.html",
            settings=settings,
            masked_key=settings.masked_key if settings else "",
            source=settings.source if settings else "",
            env_file=settings.env_file if settings else DEFAULT_ENV_FILE,
            config_file=settings.config_file if settings else DEFAULT_CONFIG_FILE,
            saved=saved,
            error=error,
        )

    @app.post("/settings")
    def settings_save(api_key: str = Form(...)) -> Response:
        if not huckepack_key.host_may_store_a_key():
            # In huckepack-only-host the key belongs in the visitor's browser.
            # Writing it here would hand the next visitor's calls to this one's
            # account — the exact confusion the mode exists to prevent.
            raise HTTPException(
                status_code=409,
                detail=(
                    "This installation runs in huckepack-only-host: your key stays "
                    "in your browser and is never stored on the server. Enter it in "
                    "the bar at the top of the page."
                ),
            )
        try:
            save_project_api_key(api_key)
        except (CalleCredentialError, OSError, ValueError) as error:
            # Credential helpers never include the submitted key in errors.
            raise HTTPException(status_code=422, detail=str(error)) from None
        return RedirectResponse("/settings?saved=true", status_code=303)

    @app.post("/projects")
    def create(
        request: Request,
        occasion: str = Form(...),
        organizer: str = Form(...),
        mode: str = Form(ProjectMode.SCHEDULE),
        date_kind: str = Form(DateKind.DAY_SLOTS),
        urgency: str = Form(""),
        group_id: str = Form(""),
        language: str = Form(""),
    ) -> Response:
        context = ctx()
        try:
            project = create_project(
                context.projects,
                occasion=occasion,
                organizer=organizer,
                mode=mode,
                date_kind=date_kind,
                urgency=urgency,
                group_id=group_id or None,
                language=language or _ui_language(request),
                locale="en-US" if (language or _ui_language(request)) == "en" else "de-DE",
            )
            return back(project.id, "advisor" if mode == ProjectMode.ROUNDTABLE else "dates")
        finally:
            context.close()

    @app.post("/demo")
    def demo(fixture: str = Form(...)) -> Response:
        """Build a whole project from a bundled fixture — offline, in one click."""
        context = ctx()
        try:
            project = seed_from_fixture(context.store, context.projects, fixture)
            return back(project.id, "preview")
        finally:
            context.close()

    # -- the wizard ---------------------------------------------------------

    @app.get("/projects/{project_id}", response_class=HTMLResponse)
    def project_home(project_id: str) -> Response:
        context = ctx()
        try:
            project = context.projects.project(project_id)
            if project.mode == ProjectMode.ROUNDTABLE:
                if context.projects.round_ids(project_id, RoundKind.ROUNDTABLE):
                    return back(project_id, "board")
                return back(project_id, "advisor")
            if project.state in (ProjectState.DECIDED, ProjectState.INVITED):
                return back(project_id, "board")
            if context.projects.round_ids(project_id, RoundKind.AVAILABILITY):
                return back(project_id, "board")
            return back(project_id, "dates")
        except KeyError:
            raise HTTPException(status_code=404, detail="Projekt nicht gefunden") from None
        finally:
            context.close()

    @app.get("/projects/{project_id}/advisor", response_class=HTMLResponse)
    def advisor_form(request: Request, project_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            if project.mode != ProjectMode.ROUNDTABLE:
                return back(project_id, "dates")
            configured = advisor_question(context.projects, project)
            return page(
                request,
                "advisor.html",
                project=project,
                question=configured,
                step="advisor",
            )
        finally:
            context.close()

    @app.post("/projects/{project_id}/advisor")
    async def advisor_save(request: Request, project_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            form = await request.form()
            set_advisor_question(
                context.projects,
                project,
                str(form.get("question") or ""),
                options=[str(value) for value in form.getlist("option")],
            )
            return back(project_id, "people")
        except ValueError as error:
            return page(
                request,
                "error.html",
                title="Advisor-Frage",
                detail=str(error),
                back=f"/projects/{project_id}/advisor",
                status_code=422,
            )
        finally:
            context.close()

    @app.get("/projects/{project_id}/dates", response_class=HTMLResponse)
    def dates_form(request: Request, project_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            slots = context.projects.slots(project_id)
            days = sorted({slot.day_date for slot in slots if slot.day_date})
            return page(
                request,
                "dates.html",
                project=project,
                slots=slots,
                chosen_days=days,
                today=_today(),
                step="dates",
            )
        finally:
            context.close()

    @app.post("/projects/{project_id}/dates")
    async def dates_save(request: Request, project_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            form = await request.form()
            days = [value for value in form.getlist("day") if str(value).strip()]
            if not days:
                raise ValueError("Bitte mindestens einen Tag auswählen.")

            whole_day = form.get("date_kind") == DateKind.WHOLE_DAY
            default_times = _time_pairs(form.getlist("start"), form.getlist("end"))
            if not whole_day and not default_times:
                raise ValueError(
                    "Bitte mindestens einen Zeitraum angeben — oder „ganzer Tag“ wählen."
                )
            overrides = _overrides(form, days)

            specs = day_slot_specs(
                project,
                days=days,
                default_times=default_times,
                overrides=overrides,
                whole_day=whole_day,
            )
            if not specs:
                raise ValueError("Daraus ergibt sich kein einziger Termin-Vorschlag.")
            set_dates(context.store, context.projects, project, specs)
            return back(project_id, "people")
        except ValueError as error:
            return page(
                request, "error.html", title=_t(request, "Termine"), detail=str(error),
                back=f"/projects/{project_id}/dates", status_code=422,
            )
        finally:
            context.close()

    @app.post("/projects/{project_id}/dates/adjust")
    async def dates_adjust(request: Request, project_id: str) -> Response:
        """Per-day exceptions: every slot spelled out, one row each.

        The standard times above are the quick way in; this is where a single
        Tuesday gets moved without touching the other four days. A row whose
        times are blank disappears — that is how a slot is deleted without a
        separate button for it.
        """
        context = ctx()
        try:
            project = _project(context, project_id)
            form = await request.form()
            days = [str(v).strip() for v in form.getlist("row_day")]
            starts = [str(v).strip() for v in form.getlist("row_start")]
            ends = [str(v).strip() for v in form.getlist("row_end")]
            whole_day = project.date_kind == DateKind.WHOLE_DAY

            specs: list[dict[str, Any]] = []
            for index, day in enumerate(days):
                if not day:
                    continue
                start = starts[index] if index < len(starts) else ""
                end = ends[index] if index < len(ends) else ""
                if whole_day:
                    specs.append({"day_date": day, "all_day": True})
                elif start and end:
                    specs.append(
                        {"day_date": day, "start_time": start, "end_time": end, "all_day": False}
                    )
            if not specs:
                raise ValueError("So bliebe kein einziger Terminvorschlag übrig.")
            set_dates(context.store, context.projects, project, specs)
            return back(project_id, "dates")
        except ValueError as error:
            return page(
                request, "error.html", title=_t(request, "Termine"), detail=str(error),
                back=f"/projects/{project_id}/dates", status_code=422,
            )
        finally:
            context.close()

    @app.get("/projects/{project_id}/people", response_class=HTMLResponse)
    def people_form(request: Request, project_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            chosen = {inv.contact_id for inv in context.projects.invitees(project_id)}
            return page(
                request,
                "people.html",
                project=project,
                contacts=context.projects.contacts(),
                chosen=chosen,
                step="people",
            )
        finally:
            context.close()

    @app.post("/projects/{project_id}/people")
    async def people_save(request: Request, project_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            form = await request.form()
            ids = [str(value) for value in form.getlist("contact") if str(value).strip()]
            set_invitees(context.store, context.projects, project, ids)
            return back(project_id, "wording")
        finally:
            context.close()

    @app.get("/projects/{project_id}/wording", response_class=HTMLResponse)
    def wording_form(request: Request, project_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            greeting, closing = wording(context.projects, project)
            return page(
                request,
                "wording.html",
                project=project,
                greeting=greeting,
                closing=closing,
                step="wording",
            )
        finally:
            context.close()

    @app.post("/projects/{project_id}/wording")
    async def wording_save(request: Request, project_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            form = await request.form()
            set_wording(
                context.projects,
                project,
                greeting=[str(v) for v in form.getlist("greeting")],
                closing=[str(v) for v in form.getlist("closing")],
            )
            return back(project_id, "preview")
        finally:
            context.close()

    # -- preview and running ------------------------------------------------

    @app.get("/projects/{project_id}/preview", response_class=HTMLResponse)
    def preview_page(request: Request, project_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            poll = (
                roundtable_round(context.store, context.projects, project)
                if project.mode == ProjectMode.ROUNDTABLE
                else availability_round(context.store, context.projects, project)
            )
            view = preview(context.store, context.projects, project, poll)
            job = app.state.jobs.get(project_id)
            return page(
                request,
                "preview.html",
                project=project,
                preview=view,
                job=job,
                has_fixture=bool(project.fixture_name),
                api_key=api_key_present(),
                step="preview",
            )
        finally:
            context.close()

    @app.post("/projects/{project_id}/run")
    def run_round_route(
        project_id: str,
        mode: str = Form(...),
        confirmation: str = Form(""),
        round_kind: str = Form(RoundKind.AVAILABILITY),
    ) -> Response:
        if mode not in (RunMode.SCRIPT, RunMode.REHEARSAL, RunMode.LIVE):
            raise HTTPException(status_code=400, detail=f"unbekannter Modus {mode!r}")
        context = ctx()
        try:
            project = _project(context, project_id)
            if round_kind == RoundKind.INVITATION:
                poll = invitation_round(context.store, context.projects, project, create=False)
            elif round_kind == RoundKind.ROUNDTABLE or project.mode == ProjectMode.ROUNDTABLE:
                round_kind = RoundKind.ROUNDTABLE
                poll = roundtable_round(context.store, context.projects, project)
            else:
                poll = availability_round(context.store, context.projects, project)
            if poll is None:
                raise HTTPException(status_code=400, detail="Diese Runde gibt es noch nicht.")
            if mode == RunMode.LIVE and confirmation.strip() != LIVE_CONFIRMATION_PHRASE:
                raise LiveCallBlocked(
                    f"Zum Telefonieren muss {LIVE_CONFIRMATION_PHRASE!r} genau so "
                    "eingetippt werden. Es wurde nichts gewählt."
                )
            app.state.jobs.start(
                project_id=project_id,
                poll_id=poll.id,
                mode=mode,
                confirmation=confirmation,
                # The round outlives this request; both values have to travel
                # with it, because a thread inherits no request context.
                session=huckepack_storage.current_session(),
                calle_key=huckepack_key.current_request_key(),
            )
            return RedirectResponse(
                f"/projects/{project_id}/live?round={round_kind}", status_code=303
            )
        finally:
            context.close()

    @app.post("/projects/{project_id}/stop")
    def stop_round(project_id: str) -> Response:
        app.state.jobs.cancel(project_id)
        return RedirectResponse(f"/projects/{project_id}/live", status_code=303)

    @app.get("/projects/{project_id}/live", response_class=HTMLResponse)
    def live_page(
        request: Request, project_id: str, round: str = RoundKind.AVAILABILITY
    ) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            job = app.state.jobs.get(project_id)
            return page(
                request,
                "live.html",
                project=project,
                job=job,
                round_kind=round,
                panel=_panel_html(request, context, project_id, round, job),
                step="live",
            )
        finally:
            context.close()

    @app.get("/projects/{project_id}/live/panel", response_class=HTMLResponse)
    def live_panel(
        request: Request, project_id: str, round: str = RoundKind.AVAILABILITY
    ) -> Response:
        context = ctx()
        try:
            job = app.state.jobs.get(project_id)
            return HTMLResponse(_panel_html(request, context, project_id, round, job))
        finally:
            context.close()

    def _panel_html(
        request: Request, context: Ctx, project_id: str, round_kind: str, job: Job | None
    ) -> str:
        """Render the live list from the database, plus who is on the phone now.

        Database first, job second — that is what makes a reloaded page correct
        even when the job that produced the answers finished an hour ago, or ran
        in a server process that has since been restarted.
        """
        project = context.projects.project(project_id)
        poll_ids = context.projects.round_ids(project_id, round_kind)
        if not poll_ids:
            return f"<p class='muted'>{_t(request, 'Diese Runde wurde noch nicht gestartet.')}</p>"
        poll = context.store.get_poll(poll_ids[0])
        contacts = {c.id: c for c in context.projects.contacts()}
        language = _ui_language(request)
        rows = live_rows(
            context.store.participants(poll.id),
            context.store.answers(poll.id),
            contacts,
            job.current_ref if job and job.running else None,
            language,
        )
        speech = [event.text for event in (job.events() if job else []) if event.kind == "speech"]
        template = templates.get_template("_live_panel.html")
        return template.render(
            request=request,
            project=project,
            poll=poll,
            rows=rows,
            job=job,
            speech=speech[-40:],
            round_kind=round_kind,
            avatar_colour=avatar_colour,
            status_word=lambda status: status_word(status, language),
            t=TranslationSystem(language=language).t,
            ui_language=language,
        )

    @app.get("/projects/{project_id}/live/stream")
    async def live_stream(
        request: Request, project_id: str, round: str = RoundKind.AVAILABILITY
    ) -> StreamingResponse:
        """Push the panel to an open page while a round is running.

        The stream is a convenience, never the source of truth: it sends whole
        rendered panels (which come from the database) rather than deltas, and
        it closes as soon as the round is over. A page that missed the stream
        entirely still shows the right thing after a reload.
        """

        async def events() -> Any:
            seen = -1
            while True:
                if await request.is_disconnected():
                    return
                job = app.state.jobs.get(project_id)
                count = job.event_count if job else 0
                if count != seen:
                    seen = count
                    context = ctx()
                    try:
                        html = _panel_html(request, context, project_id, round, job)
                    finally:
                        context.close()
                    yield _sse("panel", {"html": html})
                if job is None or not job.running:
                    yield _sse("done", {"ok": True})
                    return
                await asyncio.sleep(0.4)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # -- the board ----------------------------------------------------------

    @app.get("/projects/{project_id}/board", response_class=HTMLResponse)
    def board_page(request: Request, project_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            if project.mode == ProjectMode.ROUNDTABLE:
                view = advisor_board(context.store, context.projects, project)
                translator = TranslationSystem(language=_ui_language(request))
                return page(
                    request,
                    "advisor_board.html",
                    project=project,
                    board=view,
                    advisor_summary=_advisor_summary(view.merge, translator),
                    invitees=context.projects.invitees(project_id),
                    job=app.state.jobs.get(project_id),
                    step="board",
                )
            view = board(context.store, context.projects, project)
            invitation = invitation_round(
                context.store, context.projects, project, create=False
            )
            return page(
                request,
                "board.html",
                project=project,
                board=view,
                days=calendar_days(view, _ui_language(request)),
                invitees=context.projects.invitees(project_id),
                invitation=invitation,
                job=app.state.jobs.get(project_id),
                huckepack_receipt=_board_receipt(project, view),
                step="board",
            )
        finally:
            context.close()

    def _board_receipt(project, view) -> str:
        """The result of a round, as a file the organiser can keep.

        Built from the board that is already on screen, with names but without
        numbers: a receipt is a record of what was agreed, not a copy of the
        address book.
        """
        decided = view.decided_slot
        return huckepack_web.receipt_script_tag(
            {
                "kind": "round-receipt",
                "app": "ringedingeding",
                "order_id": project.id,
                "business": project.occasion,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "summary": (
                    f"{decided.slot.label}: {len(decided.can)} " + "können"
                    if decided
                    else "Noch nicht terminiert."
                ),
                "transcript": "\n".join(
                    f"{slot.slot.label}: "
                    + ", ".join(person.name for person in slot.can)
                    for slot in view.slots
                ),
                "third_party_notice": (
                    "Die Namen stammen von den angerufenen Personen selbst."
                ),
            }
        )

    @app.get("/projects/{project_id}/board/slot/{slot_id}", response_class=HTMLResponse)
    def slot_detail(request: Request, project_id: str, slot_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            view = board(context.store, context.projects, project)
            found = next((s for s in view.slots if s.slot.id == slot_id), None)
            if found is None:
                raise HTTPException(status_code=404, detail="Termin nicht gefunden")
            return page(
                request, "_slot_detail.html", project=project, board=view, view=found
            )
        finally:
            context.close()

    @app.post("/projects/{project_id}/criteria")
    async def criteria_save(request: Request, project_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            form = await request.form()
            raw_count = str(form.get("min_count") or "").strip()
            set_criteria(
                context.projects,
                project,
                favourite_slot_id=str(form.get("favourite") or "") or None,
                must_have=[str(v) for v in form.getlist("must_have") if str(v).strip()],
                min_count=int(raw_count) if raw_count.isdigit() else None,
            )
            return back(project_id, "board")
        finally:
            context.close()

    @app.post("/projects/{project_id}/decide")
    def decide_route(project_id: str, slot_id: str = Form(...)) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            decide(context.projects, project, slot_id)
            return back(project_id, "invite")
        finally:
            context.close()

    @app.post("/projects/{project_id}/undecide")
    def undecide(project_id: str) -> Response:
        context = ctx()
        try:
            _project(context, project_id)
            context.projects.clear_decision(project_id)
            context.projects.set_state(project_id, ProjectState.ASKING)
            return back(project_id, "board")
        finally:
            context.close()

    # -- invitation ---------------------------------------------------------

    @app.get("/projects/{project_id}/invite", response_class=HTMLResponse)
    def invite_form(request: Request, project_id: str) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            view = board(context.store, context.projects, project)
            decided = view.decided_slot
            existing = invitation_round(context.store, context.projects, project, create=False)
            text = existing.question if existing else default_invitation_text(
                project, decided.slot if decided else None
            )
            invitation_preview = None
            if existing is not None:
                invitation_preview = preview(
                    context.store, context.projects, project, existing
                )
            return page(
                request,
                "invite.html",
                project=project,
                board=view,
                decided=decided,
                text=text,
                invitation=existing,
                invitation_preview=invitation_preview,
                has_fixture=bool(project.fixture_name),
                api_key=api_key_present(),
                step="invite",
            )
        finally:
            context.close()

    @app.post("/projects/{project_id}/invite")
    def invite_save(project_id: str, text: str = Form(...)) -> Response:
        context = ctx()
        try:
            project = _project(context, project_id)
            invitation_round(context.store, context.projects, project, text=text)
            context.projects.set_state(project_id, ProjectState.INVITED)
            return back(project_id, "invite")
        finally:
            context.close()

    # -- contacts -----------------------------------------------------------

    @app.get("/groups", response_class=HTMLResponse)
    def groups_page(request: Request) -> Response:
        context = ctx()
        try:
            return page(
                request,
                "groups.html",
                groups=context.projects.groups(),
                contacts=context.projects.contacts(),
            )
        finally:
            context.close()

    @app.post("/groups")
    async def group_create(request: Request) -> Response:
        context = ctx()
        try:
            form = await request.form()
            group = context.projects.create_group(
                name=str(form.get("name") or ""), note=str(form.get("note") or "")
            )
            context.projects.set_group_members(
                group.id, [str(value) for value in form.getlist("contact")]
            )
            return RedirectResponse("/groups", status_code=303)
        finally:
            context.close()

    @app.post("/groups/{group_id}")
    async def group_update(request: Request, group_id: str) -> Response:
        context = ctx()
        try:
            form = await request.form()
            context.projects.set_group_members(
                group_id, [str(value) for value in form.getlist("contact")]
            )
            return RedirectResponse("/groups", status_code=303)
        finally:
            context.close()

    @app.post("/groups/{group_id}/delete")
    def group_delete(group_id: str) -> Response:
        context = ctx()
        try:
            context.projects.delete_group(group_id)
            return RedirectResponse("/groups", status_code=303)
        finally:
            context.close()

    @app.get("/calendar", response_class=HTMLResponse)
    def calendar_page(request: Request) -> Response:
        context = ctx()
        try:
            candidates = [
                project for project in context.projects.projects()
                if project.mode == ProjectMode.SCHEDULE
            ]
            filtered = request.query_params.get("filtered") == "1"
            selected = request.query_params.getlist("project") if filtered else None
            entries = calendar_entries(context.projects, selected)
            selected_ids = {project.id for project in candidates} if selected is None else set(selected)
            return page(
                request,
                "calendar.html",
                projects=candidates,
                selected_ids=selected_ids,
                entries=entries,
                export_query=_calendar_query(selected_ids),
            )
        finally:
            context.close()

    @app.get("/calendar.ics")
    def calendar_ics(request: Request) -> Response:
        context = ctx()
        try:
            selected = request.query_params.getlist("project")
            entries = calendar_entries(context.projects, selected)
            return Response(
                render_ics(entries),
                media_type="text/calendar; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="ringedingeding.ics"'},
            )
        finally:
            context.close()

    @app.get("/calendar.xlsx")
    def calendar_xlsx(request: Request) -> Response:
        context = ctx()
        try:
            selected = request.query_params.getlist("project")
            entries = calendar_entries(context.projects, selected)
            return Response(
                render_xlsx(entries),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": 'attachment; filename="ringedingeding.xlsx"'},
            )
        finally:
            context.close()

    # -- contacts -----------------------------------------------------------

    @app.get("/contacts", response_class=HTMLResponse)
    def contacts_page(request: Request, project: str = "") -> Response:
        context = ctx()
        try:
            return page(
                request,
                "contacts.html",
                contacts=context.projects.contacts(),
                back_to=project,
            )
        finally:
            context.close()

    @app.post("/contacts")
    async def contact_create(
        request: Request,
        name: str = Form(...),
        phone: str = Form(""),
        email: str = Form(""),
        note: str = Form(""),
        photo: UploadFile | None = None,
        project: str = Form(""),
    ) -> Response:
        context = ctx()
        try:
            contact = context.projects.create_contact(
                name=name, phone=phone or None, email=email or None, note=note
            )
            await _attach_photo(context, contact.id, photo)
            return RedirectResponse(_contacts_target(project), status_code=303)
        finally:
            context.close()

    @app.post("/contacts/{contact_id}")
    async def contact_update(
        request: Request,
        contact_id: str,
        name: str = Form(...),
        phone: str = Form(""),
        email: str = Form(""),
        note: str = Form(""),
        photo: UploadFile | None = None,
        project: str = Form(""),
    ) -> Response:
        context = ctx()
        try:
            context.projects.update_contact(contact_id, name=name, note=note)
            # An empty field means "leave it alone", never "delete it" — the
            # form shows the number masked, so an empty box is the normal state.
            if phone.strip():
                context.projects.set_channel(contact_id, ChannelKind.PHONE, phone)
            if email.strip():
                context.projects.set_channel(contact_id, ChannelKind.EMAIL, email)
            await _attach_photo(context, contact_id, photo)
            # A number added afterwards has to reach the rounds that already
            # invited this person, otherwise they vanish from the report
            # instead of being called next time.
            resync_contact(context.store, context.projects, contact_id)
            return RedirectResponse(_contacts_target(project), status_code=303)
        finally:
            context.close()

    @app.post("/contacts/{contact_id}/delete")
    def contact_delete(contact_id: str, project: str = Form("")) -> Response:
        context = ctx()
        try:
            context.projects.delete_contact(contact_id)
            return RedirectResponse(_contacts_target(project), status_code=303)
        finally:
            context.close()

    @app.get("/contacts/{contact_id}/photo")
    def contact_photo(contact_id: str) -> Response:
        context = ctx()
        try:
            found = context.projects.photo(contact_id)
            if found is None:
                raise HTTPException(status_code=404, detail="kein Bild")
            blob, mime = found
            return Response(content=blob, media_type=mime)
        finally:
            context.close()

    async def _attach_photo(context: Ctx, contact_id: str, photo: UploadFile | None) -> None:
        if photo is None or not photo.filename:
            return
        if photo.content_type not in _IMAGE_TYPES:
            raise ValueError(f"{photo.content_type} ist kein unterstütztes Bildformat")
        blob = await photo.read()
        if len(blob) > MAX_PHOTO_BYTES:
            raise ValueError("Das Bild ist größer als 2 MB.")
        if blob:
            context.projects.set_photo(contact_id, blob, photo.content_type or "image/png")

    # -- housekeeping -------------------------------------------------------

    @app.post("/projects/{project_id}/reset")
    def reset(project_id: str) -> Response:
        """Throw away the answers of a rehearsal. Real answers are kept."""
        context = ctx()
        try:
            _project(context, project_id)
            for kind in (RoundKind.AVAILABILITY, RoundKind.ROUNDTABLE, RoundKind.INVITATION):
                for poll_id in context.projects.round_ids(project_id, kind):
                    poll = context.store.get_poll(poll_id)
                    if poll.simulated:
                        context.store.clear_answers(poll_id)
                        context.store.set_poll_simulated(poll_id, False)
            return back(project_id, "preview")
        finally:
            context.close()

    @app.post("/projects/{project_id}/delete")
    def project_delete(project_id: str) -> Response:
        context = ctx()
        try:
            context.projects.delete_project(project_id)
            return RedirectResponse("/", status_code=303)
        finally:
            context.close()

    return app


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _project(context: Ctx, project_id: str):
    try:
        return context.projects.project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden") from None


def _contacts_target(project_id: str) -> str:
    """Back to the address book, keeping the project the person came from."""
    return f"/contacts?project={project_id}" if project_id else "/contacts"


def _ui_language(request: Request) -> str:
    language = request.cookies.get("rd_lang", "de")
    return language if language in TranslationSystem.SUPPORTED_LANGUAGES else "de"


def _t(request: Request, text: str) -> str:
    return TranslationSystem(language=_ui_language(request)).t(text)


def _calendar_query(project_ids: set[str]) -> str:
    from urllib.parse import urlencode

    return urlencode([("project", project_id) for project_id in sorted(project_ids)])


def _advisor_summary(merge: Any, translator: TranslationSystem) -> str:
    if merge is None or not getattr(merge, "entries", None) and not getattr(merge, "tally", None):
        return translator.t("Keine auswertbare Antwort.")
    if getattr(merge, "tally", None) is not None:
        votes = sum(item.count for item in merge.tally)
        if votes == 0:
            return translator.t("Keine Stimme abgegeben.")
        leaders = merge.leaders
        if merge.is_tie:
            names = ", ".join(item.option for item in leaders)
            return f"{translator.t('Gleichstand:')} {names} ({leaders[0].count})"
        leader = leaders[0]
        return f"{translator.t('Vorne:')} {leader.option} ({leader.count} {translator.t('von')} {votes})"
    primary = merge.primary_tendency
    if primary is None:
        return translator.t("Keine eindeutige Tendenz; die Stimmen liegen auseinander.")
    summary = (
        f"{translator.t('Tendenz:')} {translator.t(primary.stance)} "
        f"({primary.count} {translator.t('von')} {len(merge.entries)})"
    )
    if merge.countervoices:
        summary += f"; {len(merge.countervoices)} {translator.t('Gegenstimme(n)')}"
    return summary


def _today() -> str:
    from datetime import date

    return date.today().isoformat()


def _time_pairs(starts: list[Any], ends: list[Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for index, start in enumerate(starts):
        start_text = str(start).strip()
        end_text = str(ends[index]).strip() if index < len(ends) else ""
        if start_text and end_text:
            pairs.append((start_text, end_text))
    return pairs


def _overrides(form: Any, days: list[str]) -> dict[str, list[tuple[str, str]]]:
    """Read the per-day exceptions out of the form.

    A day appears here only when it was ticked as deviating. Its own time list
    then replaces the standard times for that day — including the case where the
    list is empty, which means "that day, but no times after all".
    """
    result: dict[str, list[tuple[str, str]]] = {}
    for day in days:
        if not form.get(f"override-{day}"):
            continue
        result[day] = _time_pairs(
            form.getlist(f"start-{day}"), form.getlist(f"end-{day}")
        )
    return result


def _sse(event: str, payload: dict[str, Any]) -> str:
    """One Server-Sent Event. JSON keeps newlines out of the wire format."""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def run(
    db_path: str | Path = DEFAULT_DB_PATH, *, host: str = "127.0.0.1", port: int = 8765
) -> None:
    """Start the server. Binds to the loopback interface only."""
    import uvicorn

    uvicorn.run(create_app(db_path), host=host, port=port, log_level="warning")
