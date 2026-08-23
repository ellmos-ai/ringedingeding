"""Run the web interface as an AWS Lambda function behind a Function URL.

The target for the public dry-run demo is a Lambda Function URL, following the
same pattern already deployed for `roshambo` (`roshambo/demo/lambda_entry.py`).
This module is the whole of the adaptation: one Mangum wrapper over the same
`ringedingeding.web.app:create_app` the command line's `--web` mode and every
local `START-WEB.bat` use. There is deliberately no second code path.

    # Lambda handler:  demo.lambda_entry.handler
    # Local:            python -m ringedingeding --web   (see ringedingeding/__main__.py)

What this deployment must never do
-----------------------------------

No `CALLE_API_KEY` (or any `CALLE_*` credential) is ever set in this Lambda's
environment — the deploy script (`infra/deploy_demo_lambda.py`) does not pass
one. That alone would already make every live-call construction fail with "no
key configured". On top of it, the deploy script sets `DEMO_MODE=1` in the
Lambda's own environment configuration, which
`ringedingeding.transports.calle.CalleTransport.__init__` checks *before*
anything else — before the confirmation check, before the credential
resolver — and refuses unconditionally. Two independent locks on the same
door: losing one of them (a misconfigured env, a future refactor of the
credential resolver) still leaves the other standing.
`tests/test_live_guard.py` proves both the block itself and that it never
reaches the network.

Deliberately, **this module never sets `DEMO_MODE` itself** — only reads it
indirectly through `CalleTransport`. Importing it must stay free of global
`os.environ` side effects: a `setdefault` here once leaked `DEMO_MODE=1`
across the whole pytest process (every test file is imported during
collection, before any test runs), silently blocking unrelated
`CalleBatchTransport` construction in other test files. The real Lambda gets
`DEMO_MODE=1` from its environment configuration, not from this file; a local
test sets it itself, in its own scope, and restores it afterward.

What a judge sees on cold start
--------------------------------

`_seed_if_empty` runs once per fresh execution environment and builds one
complete example project from the bundled `team-retro` fixture — an English
open question, four participants with fictional `+1 555…` numbers, a mix of
answered / declined / voicemail outcomes (`ringedingeding/fixtures/team-retro.json`).
Every phone number involved is a placeholder from that fixture; the live path
independently refuses to dial any of them even if DEMO_MODE were somehow
absent (`refuse_placeholder_numbers` in `ringedingeding/service.py`). The
seeded round is placed through `RunMode.SCRIPT` — a `FixtureTransport` replay,
not a network call — so the demo shows a project with real-looking, already
merged results the moment the page loads, instead of an empty list a judge
would have to fill in themselves.

A seeding failure never takes the Lambda down: it is caught and swallowed, and
the homepage still renders (with an empty project list) either way.

Ephemeral by design
--------------------

The database lives in the execution environment's own scratch space
(`tempfile.gettempdir()`, which resolves to Lambda's `/tmp` and to a normal
OS temp directory on a developer machine — see the README demo paragraph).
State therefore resets whenever AWS recycles the sandbox; nothing here is
meant to persist across cold starts. See `_db_path` for the one override
point that lets `tests/test_lambda_entry.py` point this at a private file
instead of writing into a shared temp path.

`lifespan="off"` because Lambda never delivers a startup or shutdown event
between invocations of a frozen execution environment: the only lifespan hook
`create_app` registers is `application.state.jobs.shutdown()` on shutdown,
which nothing here would ever trigger anyway.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mangum import Mangum  # noqa: E402

from ringedingeding.projects import ProjectMode, ProjectStore  # noqa: E402
from ringedingeding.service import (  # noqa: E402
    RunMode,
    availability_round,
    fixture_for,
    make_transport,
    roundtable_round,
    run_round,
    seed_from_fixture,
)
from ringedingeding.store import Store  # noqa: E402
from ringedingeding.web.app import create_app  # noqa: E402

DEMO_DB_PATH_ENV = "RINGEDINGEDING_DEMO_DB_PATH"
"""Override point. Left unset, the database goes to the platform temp
directory — correct on Lambda (`/tmp`) and on a developer machine alike,
without ever hard-coding a POSIX-only path. Set explicitly by the test that
imports this module, so it never touches a shared temp file."""

DEMO_FIXTURE_NAME = "team-retro"
"""English, one open question, four participants, a mix of outcomes — chosen
over the richer `grandma-gift` fixture specifically because it is English:
most judges reading this demo will not read German."""


def _db_path() -> str:
    override = os.environ.get(DEMO_DB_PATH_ENV)
    if override:
        return override
    return str(Path(tempfile.gettempdir()) / "ringedingeding-demo.db")


def _seed_if_empty(db_path: str) -> None:
    """Build one example project from the bundled fixture, once per fresh
    database. Never raises: a broken seed must not take the homepage down
    with it."""
    store = Store(db_path)
    try:
        projects = ProjectStore(store)
        if projects.projects():
            return  # already seeded — warm start, or a reused container
        try:
            project = seed_from_fixture(store, projects, DEMO_FIXTURE_NAME)
            poll = (
                roundtable_round(store, projects, project)
                if project.mode == ProjectMode.ROUNDTABLE
                else availability_round(store, projects, project)
            )
            if poll is not None:
                fixture = fixture_for(project)
                transport = make_transport(RunMode.SCRIPT, project=project, fixture=fixture)
                run_round(store, projects, project, poll, transport)
        except Exception:
            # Broad on purpose: a broken cold-start seed must never take the
            # whole Lambda down with it — the homepage still has to render,
            # even with an empty project list, if this fails for any reason.
            pass
    finally:
        store.close()


def _build_demo_app(db_path: str):
    """Factory kept separate from module scope so a test can build the app
    against a private database path without re-importing the module.

    Does not touch ``DEMO_MODE`` — see the module docstring for why setting it
    here, even as a "friendly default", is the wrong place for it."""
    _seed_if_empty(db_path)
    return create_app(db_path)


handler = Mangum(_build_demo_app(_db_path()), lifespan="off")
