"""The huckepack modes: what is promised, verified.

The promises are the same as in the sibling projects, but this application
makes two of them harder, and that is what most of these tests are about:

* a round runs in a **background thread**, so session and key have to travel
  with it — a thread inherits no request context;
* the settings page can **write a key to the host**, which is exactly what
  ``huckepack-only-host`` must not allow.
"""

from __future__ import annotations

import logging
import sqlite3

import pytest

pytest.importorskip("fastapi", reason="the web interface is an optional extra")

from fastapi.testclient import TestClient

from ringedingeding import huckepack_key, huckepack_storage, server_mode
from ringedingeding.huckepack_storage import SESSIONS, SnapshotError
from ringedingeding.huckepack_web import SESSION_HEADER
from ringedingeding.server_mode import ServerMode, ServerModeError
from ringedingeding.store import Store
from ringedingeding.web.app import create_app

TOKEN = "AAAAAAAAAAAAAAAAAAAAAAAAAAAA"
OTHER_TOKEN = "BBBBBBBBBBBBBBBBBBBBBBBBBBBB"
VISITOR_KEY = "sk-visitor-9999-abcdefgh"


@pytest.fixture(autouse=True)
def clean_slate(monkeypatch):
    monkeypatch.delenv(server_mode.ENV_VAR, raising=False)
    server_mode.reset_mode_cache()
    SESSIONS.clear()
    yield
    SESSIONS.clear()
    server_mode.reset_mode_cache()


def use_mode(monkeypatch, mode: str) -> None:
    monkeypatch.setenv(server_mode.ENV_VAR, mode)
    server_mode.reset_mode_cache()


# ---------------------------------------------------------------- the mode

def test_unset_means_local():
    assert server_mode.current_mode() is ServerMode.LOCAL


@pytest.mark.parametrize(
    "name,browser,key_field",
    [
        ("local", False, False),
        ("huckepack-gift", True, False),
        ("huckepack-only-host", True, True),
        ("pay-membership", False, False),
    ],
)
def test_every_mode_decides_storage_and_key(monkeypatch, name, browser, key_field):
    use_mode(monkeypatch, name)
    mode = server_mode.current_mode()
    assert mode.stores_in_browser is browser
    assert mode.key_from_browser is key_field


def test_an_unknown_mode_is_refused_by_name():
    with pytest.raises(ServerModeError) as error:
        server_mode.parse_mode("huckepack-perhaps")
    assert "huckepack-perhaps" in str(error.value)


# ------------------------------------------------------------- the storage

def test_local_mode_writes_the_file_as_before(monkeypatch, tmp_path):
    use_mode(monkeypatch, "local")
    path = tmp_path / "nested" / "ringedingeding.db"
    with Store(path):
        pass
    assert path.exists()


@pytest.mark.parametrize("mode", ["huckepack-gift", "huckepack-only-host"])
def test_a_huckepack_mode_creates_neither_file_nor_directory(monkeypatch, tmp_path, mode):
    use_mode(monkeypatch, mode)
    path = tmp_path / "nested" / "ringedingeding.db"
    reset = huckepack_storage.bind_session(TOKEN)
    try:
        store = Store(path)
        store.close()
    finally:
        huckepack_storage.unbind_session(reset)
    assert not path.exists()
    assert not path.parent.exists(), "not even the directory should appear"


def test_the_schema_arrives_in_the_session_database(monkeypatch, tmp_path):
    use_mode(monkeypatch, "huckepack-gift")
    reset = huckepack_storage.bind_session(TOKEN)
    try:
        Store(tmp_path / "x.db")
        tables = {
            row[0]
            for row in SESSIONS.connection(TOKEN).execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        huckepack_storage.unbind_session(reset)
    assert {"poll", "participant"} <= tables


def test_two_sessions_do_not_see_each_other(monkeypatch, tmp_path):
    use_mode(monkeypatch, "huckepack-gift")
    for token, question in ((TOKEN, "Ada?"), (OTHER_TOKEN, "Grace?")):
        reset = huckepack_storage.bind_session(token)
        try:
            store = Store(tmp_path / "x.db")
            store.connection.execute(
                "INSERT INTO poll (id, question, kind, organizer, created_at) "
                "VALUES (?, ?, 'slot', 'Lukas', '2026-08-02')",
                (f"poll_{token[:3]}", question),
            )
            store.connection.commit()
        finally:
            huckepack_storage.unbind_session(reset)

    def questions(token):
        return [row[0] for row in SESSIONS.connection(token).execute("SELECT question FROM poll")]

    assert questions(TOKEN) == ["Ada?"]
    assert questions(OTHER_TOKEN) == ["Grace?"]


def test_a_snapshot_carries_the_data_to_another_session(monkeypatch, tmp_path):
    use_mode(monkeypatch, "huckepack-only-host")
    reset = huckepack_storage.bind_session(TOKEN)
    try:
        store = Store(tmp_path / "x.db")
        store.connection.execute(
            "INSERT INTO poll (id, question, kind, organizer, created_at) "
            "VALUES ('poll_1', 'Saturday?', 'slot', 'Lukas', '2026-08-02')"
        )
        store.connection.commit()
        blob = huckepack_storage.snapshot_for_current_session()
    finally:
        huckepack_storage.unbind_session(reset)

    SESSIONS.load(OTHER_TOKEN, blob)
    restored = SESSIONS.connection(OTHER_TOKEN).execute("SELECT question FROM poll").fetchall()
    assert [row[0] for row in restored] == ["Saturday?"]


def test_a_snapshot_that_is_not_a_database_is_refused():
    with pytest.raises(SnapshotError):
        SESSIONS.load(TOKEN, b"definitely not a database")


# ------------------------------------------------------------------ the key

def test_a_key_is_only_ever_shown_masked():
    assert huckepack_key.mask_key(VISITOR_KEY) == "••••efgh"
    assert VISITOR_KEY not in huckepack_key.describe_key(VISITOR_KEY)


def test_local_and_gift_leave_the_documented_resolver_in_charge(monkeypatch):
    for name in ("local", "huckepack-gift"):
        use_mode(monkeypatch, name)
        assert huckepack_key.credential_override() is None


def test_only_host_takes_the_visitors_key_and_nothing_else(monkeypatch):
    use_mode(monkeypatch, "huckepack-only-host")
    monkeypatch.setenv("CALLE_API_KEY", "host-key-that-must-not-be-spent")
    with pytest.raises(huckepack_key.UserKeyError):
        huckepack_key.credential_override()

    reset = huckepack_key.bind_request_key(VISITOR_KEY)
    try:
        assert huckepack_key.credential_override() == VISITOR_KEY
    finally:
        huckepack_key.unbind_request_key(reset)


def test_the_transport_spends_the_visitors_key_not_the_hosts(monkeypatch):
    """The one door to a real telephone must open with the right key."""
    from ringedingeding.transports.calle import CalleTransport

    monkeypatch.setenv("CALLE_API_KEY", "host-key-that-must-not-be-spent")
    transport = CalleTransport(live_confirmed=True, credential_override=VISITOR_KEY)
    assert transport._api_key == VISITOR_KEY


@pytest.mark.parametrize("mode", ["huckepack-only-host", "huckepack-gift"])
def test_the_settings_page_refuses_to_store_a_key_when_hosted(monkeypatch, tmp_path, mode):
    """Audit finding of 2026-08-02: this route rewrites the host's credential.

    Unauthenticated, hosted, that is a stranger replacing the key that pays for
    everyone's calls — in gift mode just as much as in only-host.
    """
    use_mode(monkeypatch, mode)
    with TestClient(create_app(tmp_path / "web.db")) as client:
        response = client.post(
            "/settings",
            data={"api_key": VISITOR_KEY},
            headers={SESSION_HEADER: TOKEN},
            follow_redirects=False,
        )
    assert response.status_code == 409
    assert VISITOR_KEY not in response.text
    assert not (tmp_path / "config.local.json").exists()


def test_the_settings_page_still_works_in_local_mode(monkeypatch, tmp_path):
    use_mode(monkeypatch, "local")
    monkeypatch.setenv("CALLE_CONFIG_FILE", str(tmp_path / "config.local.json"))
    with TestClient(create_app(tmp_path / "web.db")) as client:
        response = client.post(
            "/settings", data={"api_key": VISITOR_KEY}, follow_redirects=False
        )
    assert response.status_code == 303
    assert (tmp_path / "config.local.json").exists()


def test_a_round_carries_session_and_key_into_its_thread(monkeypatch, tmp_path):
    """The job binds both before it opens a database or dials anything."""
    from ringedingeding.web.jobs import Job

    use_mode(monkeypatch, "huckepack-only-host")
    seen = {}

    def spy(**kwargs):
        seen["session"] = huckepack_storage.current_session()
        seen["key"] = huckepack_key.current_request_key()
        raise RuntimeError("far enough — nothing is dialled in a test")

    job = Job(project_id="p1", poll_id="poll_1", mode="live", db_path=str(tmp_path / "x.db"))
    monkeypatch.setattr("ringedingeding.web.jobs.Store", lambda path: spy())
    job.start(confirmation="", session=TOKEN, calle_key=VISITOR_KEY)
    job.join(5)

    assert seen == {"session": TOKEN, "key": VISITOR_KEY}
    # Bound inside the thread, released with it: the request context is clean.
    assert huckepack_storage.current_session() is None
    assert huckepack_key.current_request_key() is None


# ------------------------------------------------------------------ the web

def test_the_browser_is_told_what_kind_of_installation_this_is(monkeypatch, tmp_path):
    use_mode(monkeypatch, "huckepack-gift")
    with TestClient(create_app(tmp_path / "web.db")) as client:
        payload = client.get("/huckepack/mode").json()
    assert payload["mode"] == "huckepack-gift"
    assert payload["storage"] == "browser"
    assert payload["key_field"] is False
    assert payload["host_pays_calls"] is True


def test_a_snapshot_can_be_handed_in_and_taken_back(monkeypatch, tmp_path):
    use_mode(monkeypatch, "huckepack-gift")
    seed = sqlite3.connect(":memory:")
    seed.execute("CREATE TABLE poll (id TEXT, question TEXT)")
    seed.execute("INSERT INTO poll VALUES ('poll_1', 'Saturday?')")
    seed.commit()

    with TestClient(create_app(tmp_path / "web.db")) as client:
        assert client.put(
            "/huckepack/session", content=seed.serialize(), headers={SESSION_HEADER: TOKEN}
        ).status_code == 200
        fetched = client.get("/huckepack/session", headers={SESSION_HEADER: TOKEN})

    back = sqlite3.connect(":memory:")
    back.deserialize(fetched.content)
    assert back.execute("SELECT question FROM poll").fetchall() == [("Saturday?",)]


def test_local_mode_has_no_browser_snapshot(monkeypatch, tmp_path):
    use_mode(monkeypatch, "local")
    with TestClient(create_app(tmp_path / "web.db")) as client:
        response = client.get("/huckepack/session", headers={SESSION_HEADER: TOKEN})
    assert response.status_code == 409


def test_the_stub_mode_says_so_instead_of_serving_pages(monkeypatch, tmp_path):
    use_mode(monkeypatch, "pay-membership")
    with TestClient(create_app(tmp_path / "web.db")) as client:
        assert client.get("/").status_code == 503
        assert client.get("/huckepack/mode").json()["implemented"] is False


def test_the_browser_half_is_shipped_and_never_prints_the_key():
    from pathlib import Path

    script = (
        Path(__file__).resolve().parents[1]
        / "ringedingeding" / "web" / "static" / "huckepack.js"
    ).read_text(encoding="utf-8")
    for needed in ("receiptFilename", "maskKey", "looksLikeSqlite", "showDirectoryPicker"):
        assert needed in script
    assert "console." not in script
    assert "ringedingeding_" in script, "the export file should carry this app's name"


def test_the_board_hands_a_receipt_to_the_browser_without_numbers(monkeypatch, tmp_path):
    """The result of a round is a file worth keeping — names yes, numbers no."""
    import re

    use_mode(monkeypatch, "local")
    with TestClient(create_app(tmp_path / "web.db")) as client:
        created = client.post(
            "/demo", data={"fixture": "family-dinner"}, follow_redirects=False
        )
        project_id = created.headers["location"].split("/")[2]
        page = client.get(f"/projects/{project_id}/board").text
    assert 'id="huckepack-receipt"' in page
    assert '"kind": "round-receipt"' in page
    assert not re.search(r"\+\d{6,}", page), "no dialable number, receipt included"


def test_a_running_round_belongs_to_the_browser_that_started_it(monkeypatch, tmp_path):
    """Audit finding: the job registry is process-wide, a project id is not a key."""
    from ringedingeding.web.jobs import JobRegistry

    use_mode(monkeypatch, "huckepack-gift")
    registry = JobRegistry(tmp_path / "web.db")
    reset = huckepack_storage.bind_session(TOKEN)
    try:
        registry._jobs["proj_1"] = _StoppedJob(session=TOKEN)
        assert registry.get("proj_1") is not None
    finally:
        huckepack_storage.unbind_session(reset)

    reset = huckepack_storage.bind_session(OTHER_TOKEN)
    try:
        assert registry.get("proj_1") is None, "a stranger must not see your round"
        assert registry.cancel("proj_1") is False, "nor stop it"
    finally:
        huckepack_storage.unbind_session(reset)


def test_local_mode_leaves_the_job_registry_alone(monkeypatch, tmp_path):
    from ringedingeding.web.jobs import JobRegistry

    use_mode(monkeypatch, "local")
    registry = JobRegistry(tmp_path / "web.db")
    registry._jobs["proj_1"] = _StoppedJob(session=None)
    assert registry.get("proj_1") is not None


class _StoppedJob:
    """A job that never ran — enough for the registry's visibility rule."""

    def __init__(self, session):
        self.session = session
        self.running = False


# ------------------------------------------- the guarantees the siblings had

# The three huckepack projects make the same promises, so they have to be held
# to the same tests. What follows was written for HungryCall first; a promise
# that is only checked in one of three repositories is a promise about that
# repository, not about the pattern.


def test_closing_a_store_does_not_throw_the_session_away(monkeypatch, tmp_path):
    """A Store closes when it is done. For a session that must not delete it."""
    use_mode(monkeypatch, "huckepack-gift")
    reset = huckepack_storage.bind_session(TOKEN)
    try:
        with Store(tmp_path / "x.db") as store:
            store.connection.execute(
                "INSERT INTO poll (id, question, kind, organizer, created_at) "
                "VALUES ('poll_1', 'Survives?', 'date', 'Ada', '2026-08-02')"
            )
            store.connection.commit()

        with Store(tmp_path / "x.db") as again:
            rows = again.connection.execute("SELECT question FROM poll").fetchall()
    finally:
        huckepack_storage.unbind_session(reset)
    assert [row[0] for row in rows] == ["Survives?"]


def test_sessions_are_dropped_when_they_go_stale():
    registry = huckepack_storage.SessionDatabases(ttl_seconds=-1)
    registry.connection(TOKEN)
    registry.connection(OTHER_TOKEN)  # the sweep runs on the next access
    assert registry.known(TOKEN) is False


def test_an_oversized_snapshot_is_refused_before_it_is_parked():
    """Refused on arrival — an unbounded upload would be RAM the host cannot decline."""
    small = huckepack_storage.SessionDatabases(max_snapshot_bytes=64)
    with pytest.raises(SnapshotError):
        small.load(TOKEN, huckepack_storage.SQLITE_MAGIC + b"x" * 200)


def test_a_token_that_is_not_a_token_is_refused(monkeypatch, tmp_path):
    """A short token would be guessable, and it addresses someone's database."""
    use_mode(monkeypatch, "huckepack-gift")
    with TestClient(create_app(tmp_path / "web.db")) as client:
        assert client.get(
            "/huckepack/session", headers={SESSION_HEADER: "abc"}
        ).status_code == 400


@pytest.mark.parametrize("bad", ["", "   ", "short", "has space in it", "with\nnewline"])
def test_an_unusable_key_is_refused_without_echoing_it(bad):
    """The error explains the shape; it never repeats the key it just rejected."""
    with pytest.raises(huckepack_key.UserKeyError) as error:
        huckepack_key.validate_key(bad)
    assert not bad.strip() or bad.strip() not in str(error.value)


def test_gift_mode_uses_the_hosts_key_and_ignores_a_sent_one(monkeypatch):
    """In gift mode the host pays. A key in the header must not redirect that."""
    use_mode(monkeypatch, "huckepack-gift")
    reset = huckepack_key.bind_request_key(VISITOR_KEY)
    try:
        assert huckepack_key.credential_override() is None
    finally:
        huckepack_key.unbind_request_key(reset)


def test_the_visitors_key_reaches_no_store_and_no_log(monkeypatch, tmp_path, caplog):
    """A full only-host request: the key must leave no trace behind it."""
    use_mode(monkeypatch, "huckepack-only-host")

    with caplog.at_level(logging.DEBUG), TestClient(create_app(tmp_path / "web.db")) as client:
        page = client.get(
            "/", headers={huckepack_key.KEY_HEADER: VISITOR_KEY, SESSION_HEADER: TOKEN}
        )
        assert page.status_code == 200
        assert VISITOR_KEY not in page.text

        snapshot = client.get(
            "/huckepack/session", headers={SESSION_HEADER: TOKEN}
        ).content

    assert VISITOR_KEY.encode() not in snapshot
    assert VISITOR_KEY not in caplog.text
    # The request is over, so the context variable must be empty again.
    assert huckepack_key.current_request_key() is None
    # And nothing about the visitor may have reached the host's disk.
    assert not list(tmp_path.rglob("*.db"))
