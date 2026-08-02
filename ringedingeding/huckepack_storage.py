"""The same database, at one of two addresses.

In ``local`` (and in the ``pay-membership`` stub) the database is a file on the
host, exactly as before. In the huckepack modes the durable copy lives in the
user's browser and the host holds it only in memory, for the length of one
browser session, and never writes it to disk.

Why not SQLite-WASM in the browser
----------------------------------
The concept names SQLite-WASM with OPFS as the first choice. What is built here
keeps its central promise — *the same schema and the same queries* — while
moving only the file, not the query engine:

* the browser keeps the real SQLite file (bytes in IndexedDB), and can hand it
  out as a ``.sqlite`` file for export;
* the host loads those bytes into an in-memory database
  (:meth:`sqlite3.Connection.deserialize`, Python 3.11+) and runs the queries
  that are already written and already tested in Python;
* after a change the browser fetches the new bytes back.

The alternative would have meant vendoring ~1.2 MB of WebAssembly into three
repositories, moving every query out of Python into the browser, and living
with OPFS availability differences. The honest trade-off of the chosen route:
the database passes through the host's memory on each request. It is never
written to disk, and the application sends the data to a call provider anyway —
persistence, not transit, is what the huckepack modes are about.

Nothing here reaches for a file when the mode says browser. That is asserted in
the tests, not merely intended.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from contextvars import ContextVar
from typing import Dict, Optional

from .server_mode import ServerMode, current_mode

SQLITE_MAGIC = b"SQLite format 3\x00"

#: A snapshot larger than this is refused rather than parked in RAM.
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
#: Sessions nobody touched for this long are dropped by the next sweep.
SESSION_TTL_SECONDS = 2 * 60 * 60
#: Upper bound on parked sessions; the least recently used one goes first.
MAX_SESSIONS = 64

_session_token: ContextVar[Optional[str]] = ContextVar("huckepack_session", default=None)


class SnapshotError(ValueError):
    """A snapshot that is not a SQLite file, or is too large to accept."""


class _SessionConnection(sqlite3.Connection):
    """A connection whose ``close()`` does not throw the session away.

    The existing data layer opens a connection, writes, and closes it. For a
    file that is right. For the one in-memory database that *is* the session,
    closing would delete the user's data mid-request, so ``close()`` is a no-op
    here and only :meth:`discard` really closes.
    """

    def close(self) -> None:  # noqa: D102 - deliberate no-op, see class docstring
        return None

    def discard(self) -> None:
        super().close()


class SessionDatabases:
    """In-memory databases, one per browser session. Never written to disk."""

    def __init__(
        self,
        *,
        ttl_seconds: int = SESSION_TTL_SECONDS,
        max_sessions: int = MAX_SESSIONS,
        max_snapshot_bytes: int = MAX_SNAPSHOT_BYTES,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_sessions = max_sessions
        self._max_snapshot_bytes = max_snapshot_bytes
        self._lock = threading.RLock()
        self._connections: Dict[str, _SessionConnection] = {}
        self._touched: Dict[str, float] = {}

    # -- lifecycle --------------------------------------------------------

    def connection(self, token: str) -> _SessionConnection:
        """The session's database, created empty when it is new."""
        with self._lock:
            self._sweep_locked()
            conn = self._connections.get(token)
            if conn is None:
                conn = sqlite3.connect(
                    ":memory:", check_same_thread=False, factory=_SessionConnection
                )
                self._connections[token] = conn
                self._evict_locked()
            self._touched[token] = time.monotonic()
            return conn

    def load(self, token: str, blob: bytes) -> None:
        """Replace the session's database with the bytes the browser sent."""
        self._verify(blob)
        with self._lock:
            self.drop(token)
            conn = self.connection(token)
            conn.deserialize(blob)

    def snapshot(self, token: str) -> bytes:
        """The session's database as file bytes, for the browser to keep."""
        with self._lock:
            return bytes(self.connection(token).serialize())

    def drop(self, token: str) -> None:
        with self._lock:
            conn = self._connections.pop(token, None)
            self._touched.pop(token, None)
            if conn is not None:
                conn.discard()

    def clear(self) -> None:
        with self._lock:
            for token in list(self._connections):
                self.drop(token)

    def known(self, token: str) -> bool:
        with self._lock:
            return token in self._connections

    def __len__(self) -> int:
        with self._lock:
            return len(self._connections)

    # -- housekeeping -----------------------------------------------------

    def _verify(self, blob: bytes) -> None:
        if len(blob) > self._max_snapshot_bytes:
            raise SnapshotError(
                f"Snapshot of {len(blob)} bytes exceeds the accepted "
                f"{self._max_snapshot_bytes} bytes."
            )
        if blob and not blob.startswith(SQLITE_MAGIC):
            raise SnapshotError("Snapshot is not a SQLite database file.")

    def _sweep_locked(self) -> None:
        deadline = time.monotonic() - self._ttl
        for token, touched in list(self._touched.items()):
            if touched < deadline:
                self.drop(token)

    def _evict_locked(self) -> None:
        while len(self._connections) > self._max_sessions:
            oldest = min(self._touched, key=self._touched.get, default=None)
            if oldest is None:
                return
            self.drop(oldest)


SESSIONS = SessionDatabases()


# -- the session a request belongs to -------------------------------------

def bind_session(token: Optional[str]):
    """Bind the browser session for the current request; returns the reset token."""
    return _session_token.set(token or None)


def unbind_session(reset_token) -> None:
    _session_token.reset(reset_token)


def current_session() -> Optional[str]:
    return _session_token.get()


#: Requests without a session token share this one. It is still memory-only, so
#: nothing is written to disk — but nothing survives either, which is why the
#: interface always sends a token.
ANONYMOUS_SESSION = "__no-session__"


# -- the single choke point -----------------------------------------------

def open_connection(path: str, *, mode: Optional[ServerMode] = None) -> sqlite3.Connection:
    """Open the database this installation is supposed to use.

    In host-storage modes this is ``sqlite3.connect(path)`` and nothing else.
    In browser modes the path is *not touched*: the session's in-memory
    database is returned instead.
    """
    mode = mode or current_mode()
    if mode.stores_on_host:
        return sqlite3.connect(path)
    return SESSIONS.connection(current_session() or ANONYMOUS_SESSION)


def snapshot_for_current_session() -> bytes:
    return SESSIONS.snapshot(current_session() or ANONYMOUS_SESSION)


def load_snapshot_for_current_session(blob: bytes) -> None:
    SESSIONS.load(current_session() or ANONYMOUS_SESSION, blob)


def drop_current_session() -> None:
    SESSIONS.drop(current_session() or ANONYMOUS_SESSION)
