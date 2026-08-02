"""Calling in the background, so the browser can be closed.

This module is the architectural decision of the web interface made concrete:
**the browser displays, the server drives.**

A round takes roughly a minute and a half per person (measured — see
``FINDINGS.md``), which is long enough that somebody will switch tabs, close the
window or put the laptop down. If the polling loop lived in the page, all three
of those would abandon the round halfway through and leave people half-called.
So the loop lives here, in a thread inside the server process, and the page is a
window onto it. Close the window, open it again an hour later: the round either
finished without you or is still going, and either way the state came out of
SQLite.

Three rules hold this together:

**Each job opens its own database connection.**
    SQLite connections are not shared between threads. The job takes a path,
    not a handle.

**One job per project.**
    A second run while the first is in flight would dial people twice. The
    registry refuses it rather than relying on the idempotency key to clean up
    afterwards.

**A job ends.**
    There is no scheduler, no retry timer and no daemon here — ``AGENTS.md``
    forbids hidden recurring work, and a web interface is not an exemption.
    When the calls are done the thread exits.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import huckepack_key, huckepack_storage
from ..activity import ActivityLine
from ..server_mode import current_mode
from ..projects import ProjectStore
from ..service import RunMode, fixture_for, make_transport, run_round
from ..store import Store

__all__ = ["JobEvent", "Job", "JobRegistry", "JobBusy"]


class JobBusy(RuntimeError):
    """A round of this project is already running."""


@dataclass(frozen=True)
class JobEvent:
    """One thing that happened, in the order it happened."""

    kind: str
    """``run_start`` | ``dialing`` | ``simulating`` | ``outcome`` | ``rejected``
    | ``speech`` | ``done`` | ``error``"""

    text: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    at: float = field(default_factory=time.time)


class Job:
    """One run of one round, executing in its own thread."""

    def __init__(
        self,
        *,
        project_id: str,
        poll_id: str,
        mode: str,
        db_path: str,
        session: str | None = None,
    ) -> None:
        self.project_id = project_id
        self.poll_id = poll_id
        self.mode = mode
        self.db_path = db_path
        # Which browser session started this round. In a huckepack mode the
        # registry hands a job out only to that session again: a project id is
        # an identifier, not a permission, and the registry lives in one
        # process that several visitors share.
        self.session = session
        self.started_at = time.time()
        self.finished_at: float | None = None
        self.error: str | None = None
        self.cancel = threading.Event()
        self._events: list[JobEvent] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    # -- state ---------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self.finished_at is None

    @property
    def live(self) -> bool:
        return self.mode == RunMode.LIVE

    def events(self, after: int = 0) -> list[JobEvent]:
        with self._lock:
            return list(self._events[after:])

    @property
    def event_count(self) -> int:
        with self._lock:
            return len(self._events)

    def _append(self, event: JobEvent) -> None:
        with self._lock:
            self._events.append(event)

    @property
    def current_ref(self) -> str | None:
        """Who is being called right now — the moving telephone symbol.

        Read backwards through the events: the last person dialed who has not
        produced an outcome yet.
        """
        dialing: str | None = None
        done: set[str] = set()
        for event in self.events():
            if event.kind in ("dialing", "simulating"):
                dialing = str(event.fields.get("ref") or "")
            elif event.kind == "outcome":
                done.add(str(event.fields.get("ref") or ""))
        if dialing and dialing not in done:
            return dialing
        return None

    # -- execution -----------------------------------------------------------

    def start(
        self,
        *,
        confirmation: str = "",
        session: str | None = None,
        calle_key: str | None = None,
    ) -> None:
        """Begin the round in a thread of its own.

        ``session`` and ``calle_key`` are handed over explicitly instead of
        being read from the request context: a thread does not inherit a
        ``ContextVar``, so in a huckepack mode the job would otherwise open an
        empty database and, in only-host, find no key at the first number.
        """
        thread = threading.Thread(
            target=self._run,
            kwargs={
                "confirmation": confirmation,
                "session": session,
                "calle_key": calle_key,
            },
            name=f"ringedingeding-{self.project_id}",
            daemon=True,
        )
        self._thread = thread
        thread.start()

    def join(self, timeout: float | None = None) -> None:
        """Wait for the round. Used by the tests, never by a request handler."""
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(
        self,
        *,
        confirmation: str,
        session: str | None = None,
        calle_key: str | None = None,
    ) -> None:
        store: Store | None = None
        session_reset = huckepack_storage.bind_session(session)
        key_reset = huckepack_key.bind_request_key(calle_key)
        try:
            store = Store(self.db_path)
            projects = ProjectStore(store)
            project = projects.project(self.project_id)
            poll = store.get_poll(self.poll_id)

            transport = make_transport(
                self.mode,
                project=project,
                fixture=fixture_for(project) if self.mode == RunMode.SCRIPT else None,
                confirmation=confirmation,
                cancel=self.cancel,
                on_activity=self._on_activity,
            )
            with transport:
                run_round(
                    store,
                    projects,
                    project,
                    poll,
                    transport,
                    cancel=self.cancel,
                    on_event=self._on_event,
                )
            self._append(JobEvent(kind="done", text="Runde beendet."))
        except Exception as error:  # noqa: BLE001 - the page has to show it
            self.error = f"{type(error).__name__}: {error}"
            self._append(JobEvent(kind="error", text=self.error))
        finally:
            self.finished_at = time.time()
            if store is not None:
                store.close()
            huckepack_key.unbind_request_key(key_reset)
            huckepack_storage.unbind_session(session_reset)

    def _on_event(self, event: str, **fields: Any) -> None:
        self._append(JobEvent(kind=event, fields=dict(fields)))

    def _on_activity(self, line: ActivityLine) -> None:
        # ``display()`` masks anything that looks like a phone number. These
        # lines are what the other side said; they are never trusted as ours.
        self._append(JobEvent(kind="speech", text=line.display(), fields={"ref": ""}))


class JobRegistry:
    """The jobs of this server process, one per project at most."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def visible(self, job: Job | None) -> bool:
        """Whether the current request may see this job.

        In host-storage modes nothing changes — one installation, one user. In
        a huckepack mode the job belongs to the browser session that started
        it, and to no other.
        """
        if job is None:
            return False
        if not current_mode().stores_in_browser:
            return True
        return job.session == huckepack_storage.current_session()

    def get(self, project_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(project_id)
        return job if self.visible(job) else None

    def start(
        self,
        *,
        project_id: str,
        poll_id: str,
        mode: str,
        confirmation: str = "",
        session: str | None = None,
        calle_key: str | None = None,
    ) -> Job:
        with self._lock:
            existing = self._jobs.get(project_id)
            if existing is not None and existing.running:
                raise JobBusy(
                    "Für dieses Projekt läuft bereits eine Runde. Warte, bis sie "
                    "fertig ist — sonst würden Menschen zweimal angerufen."
                )
            job = Job(
                project_id=project_id,
                poll_id=poll_id,
                mode=mode,
                db_path=self.db_path,
                session=session,
            )
            self._jobs[project_id] = job
        job.start(confirmation=confirmation, session=session, calle_key=calle_key)
        return job

    def cancel(self, project_id: str) -> bool:
        """Stop starting new calls. Calls in progress are left to finish."""
        job = self.get(project_id)  # visibility-filtered on purpose
        if job is None or not job.running:
            return False
        job.cancel.set()
        return True

    def shutdown(self, timeout: float = 5.0) -> None:
        for job in list(self._jobs.values()):
            job.cancel.set()
        for job in list(self._jobs.values()):
            job.join(timeout)
