"""The web app answering AWS Lambda Function URL events (demo/lambda_entry.py).

`mangum` is a deployment-only dependency (the `lambda` extra in
`pyproject.toml`), not something the dry run needs — so this whole file is
skipped rather than failing on a machine that never installed it, matching how
`tests/test_web.py` already skips when `fastapi` is absent.

Two things this proves, in order: (1) the handler turns a Function-URL-shaped
event into the same response the local web server would give, and (2) the
cold-start seed actually ran — the homepage has to show a real project, not
an empty list, or a judge opening the link sees nothing.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="web app dependencies not installed")
pytest.importorskip("mangum", reason="mangum is only needed for the Lambda entry point")

# Set before the module-level import below runs its own module-level code
# (building `handler` eagerly, exactly like roshambo's lambda_entry.py does) —
# otherwise this test would seed into the shared platform temp file that a
# real deployment or another test run might also be using.
#
# Nothing outside this file reads RINGEDINGEDING_DEMO_DB_PATH, so leaving it
# set for the rest of the pytest process is harmless. DEMO_MODE is different —
# CalleTransport.__init__ reads it — and is deliberately *not* set here at
# module scope: pytest imports every test file during collection, before any
# test runs, so a bare `os.environ["DEMO_MODE"] = "1"` at this point would
# leak into every other test file's execution window regardless of any
# teardown in this one. It is set (and restored) per test function instead,
# by the `_demo_mode` fixture below.
_TEST_DB = Path(tempfile.gettempdir()) / f"ringedingeding-demo-test-{uuid.uuid4().hex}.db"
os.environ["RINGEDINGEDING_DEMO_DB_PATH"] = str(_TEST_DB)

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from demo.lambda_entry import DEMO_FIXTURE_NAME, handler  # noqa: E402


@pytest.fixture(autouse=True)
def _demo_mode():
    """Simulate the Lambda's own environment (set by the deploy script, not by
    `demo/lambda_entry.py` itself — see that module's docstring) for the
    duration of one test function only, then restore whatever was there
    before. Scoped this narrowly on purpose: it must never be visible during
    another test file's collection or execution."""
    prior = os.environ.get("DEMO_MODE")
    os.environ["DEMO_MODE"] = "1"
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop("DEMO_MODE", None)
        else:
            os.environ["DEMO_MODE"] = prior


def function_url_event(path: str, method: str = "GET") -> dict:
    """A request as AWS delivers it to a Function URL (payload format 2.0).

    Shape per the AWS Lambda developer guide's "Payload format version 2.0":
    `rawPath` and `requestContext.http.method` are what Mangum reads to build
    the ASGI scope.
    """
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "example.lambda-url.eu-central-1.on.aws", "accept": "text/html"},
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.7",
                "userAgent": "pytest",
            },
            "stage": "$default",
        },
        "isBase64Encoded": False,
    }


def test_demo_mode_fixture_actually_sets_the_variable() -> None:
    # Not a test of demo/lambda_entry.py itself (it deliberately never touches
    # this variable) — a guard against this file's own fixture silently
    # becoming a no-op, which would make every other test in this module pass
    # for the wrong reason.
    assert os.environ.get("DEMO_MODE") == "1"


def test_index_shows_the_seeded_project() -> None:
    response = handler(function_url_event("/"), None)

    assert response["statusCode"] == 200
    body = response["body"]
    assert "text/html" in response["headers"]["content-type"]
    # The exact question text from ringedingeding/fixtures/team-retro.json —
    # present only if seed_from_fixture -> roundtable_round -> run_round all
    # actually ran during cold start, not merely "the homepage loaded".
    assert "weekly meeting" in body
    assert DEMO_FIXTURE_NAME  # sanity: the constant the seed used is not empty


def test_unknown_path_is_a_404_not_a_crash() -> None:
    response = handler(function_url_event("/does-not-exist"), None)

    assert response["statusCode"] == 404


def test_settings_page_renders_without_a_configured_key() -> None:
    # A route that touches load_calle_settings(required=False) — proves the
    # adapter survives a page that is not the seeded project at all.
    response = handler(function_url_event("/settings"), None)

    assert response["statusCode"] == 200


def teardown_module(_module: object) -> None:
    # Best-effort: a leftover per-run temp DB is harmless (unique filename,
    # next run gets its own), and failing the suite over a locked file on
    # Windows would be a worse outcome than leaving one file behind.
    with contextlib.suppress(OSError):
        _TEST_DB.unlink(missing_ok=True)
