"""Whose key pays for the call — and how a borrowed one is handled.

In ``huckepack-only-host`` the key belongs to the visitor. It arrives in one
request header, is used for that visitor's calls, and is gone afterwards: never
in the database, never in a file, never in a log line, never in a response
except as its last four characters.

Two details of this application make that harder than it sounds, and both are
handled here rather than left to chance:

* **A round outlives its request.** The calls run in a background thread
  (``web/jobs.py``), and a thread does not inherit a ``ContextVar``. The key is
  therefore handed to the job explicitly and re-bound inside it — an ambient
  value would simply be absent when the first number is dialled.
* **The host may have a key of its own.** ``load_calle_settings`` searches the
  environment, ``.env`` and the project config. In only-host that search must
  not happen: it would quietly charge the host for a visitor's call. The
  visitor's key therefore *outranks* the resolver, and its absence stops the
  round instead of falling back.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Optional

from .server_mode import ServerMode, current_mode, require_implemented

#: The header the browser sends. Never a query parameter: those end up in
#: access logs and in browser history.
KEY_HEADER = "X-Calle-Key"

_KEY_PATTERN = re.compile(r"^[!-~]{8,512}$")

_request_key: ContextVar[Optional[str]] = ContextVar("huckepack_request_key", default=None)


class UserKeyError(RuntimeError):
    """A missing or unusable visitor key. Never contains the key itself."""


def mask_key(value: Optional[str]) -> str:
    """The only representation of a key that may be shown, stored or logged."""
    if not value:
        return ""
    if len(value) <= 4:
        return "••••"
    return f"••••{value[-4:]}"


def describe_key(value: Optional[str]) -> str:
    if not value:
        return "no key"
    return f"key {mask_key(value)} ({len(value)} characters)"


def validate_key(raw: Optional[str]) -> str:
    value = (raw or "").strip()
    if not value:
        raise UserKeyError(
            "No CALL-E key was supplied. In this mode the calls are placed with "
            "your own key; enter it in the bar at the top of the page."
        )
    if not _KEY_PATTERN.match(value):
        raise UserKeyError(
            "The supplied CALL-E key has an unusable shape "
            "(8 to 512 characters, no spaces or control characters)."
        )
    return value


def bind_request_key(raw: Optional[str]):
    """Hold a visitor key for the current request or job. Returns the reset token."""
    value = (raw or "").strip() or None
    return _request_key.set(value)


def unbind_request_key(reset_token) -> None:
    _request_key.reset(reset_token)


def current_request_key() -> Optional[str]:
    return _request_key.get()


def credential_override(mode: Optional[ServerMode] = None) -> Optional[str]:
    """The key that must be used, or ``None`` when the host's resolver applies.

    ``None`` is not "no key": it means the ordinary configuration path — the
    one this project has always documented — stays in charge.
    """
    mode = require_implemented(mode or current_mode())
    if not mode.key_from_browser:
        return None
    return validate_key(current_request_key())


def host_may_store_a_key(mode: Optional[ServerMode] = None) -> bool:
    """False where the settings page must refuse to write a key to the host.

    In only-host, saving a key on the server would defeat the mode: the next
    visitor would place calls on the previous visitor's account.
    """
    return not (mode or current_mode()).key_from_browser
