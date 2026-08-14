"""Server modes: where the data lives, and whose key pays for the call.

The mode is a property of the *installation*, not of a session. It is read once
from ``RINGEDINGEDING_SERVER_MODE`` and cannot be switched at runtime; a visitor
cannot talk the host into giving away calls by sending a header.

    local                 everything as before: SQLite file on this machine,
                          key from the environment.
    huckepack-gift        the host lends its key and pays for the call; every
                          record the user produces stays in the user's browser.
    huckepack-only-host   the user brings the key in their own browser; the
                          host neither pays nor stores.
    pay-membership        stub. Accounts, billing and server-side storage —
                          deliberately not built, only kept visible.

Unset means ``local``. Whoever configures nothing gets today's behaviour.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

ENV_VAR = "RINGEDINGEDING_SERVER_MODE"


class ServerModeError(RuntimeError):
    """An unusable mode: unknown name, or a mode that is only a stub."""


class ServerMode(StrEnum):
    LOCAL = "local"
    HUCKEPACK_GIFT = "huckepack-gift"
    HUCKEPACK_ONLY_HOST = "huckepack-only-host"
    PAY_MEMBERSHIP = "pay-membership"

    # -- what the mode decides -------------------------------------------

    @property
    def stores_in_browser(self) -> bool:
        """True when the host keeps no database file for this installation."""
        return self in (ServerMode.HUCKEPACK_GIFT, ServerMode.HUCKEPACK_ONLY_HOST)

    @property
    def stores_on_host(self) -> bool:
        return not self.stores_in_browser

    @property
    def key_from_browser(self) -> bool:
        """True when the live key arrives per request and is never stored."""
        return self is ServerMode.HUCKEPACK_ONLY_HOST

    @property
    def key_from_host(self) -> bool:
        """True when the host's own credential is used for live calls."""
        return self in (ServerMode.LOCAL, ServerMode.HUCKEPACK_GIFT)

    @property
    def host_pays(self) -> bool:
        return self is ServerMode.HUCKEPACK_GIFT

    @property
    def implemented(self) -> bool:
        """``pay-membership`` exists as a name so the switch knows it."""
        return self is not ServerMode.PAY_MEMBERSHIP

    @property
    def needs_user_accounts(self) -> bool:
        return self is ServerMode.PAY_MEMBERSHIP


DEFAULT_MODE = ServerMode.LOCAL

_cached: ServerMode | None = None


def parse_mode(raw: str | None) -> ServerMode:
    """Turn the configured string into a mode, or say precisely what is wrong."""
    text = (raw or "").strip().lower()
    if not text:
        return DEFAULT_MODE
    try:
        return ServerMode(text)
    except ValueError:
        known = ", ".join(mode.value for mode in ServerMode)
        raise ServerModeError(
            f"{ENV_VAR}={raw!r} is not a server mode. Known modes: {known}."
        ) from None


def resolve_mode(environ: Mapping[str, str] | None = None) -> ServerMode:
    """Read the mode from an environment mapping without touching the cache."""
    source = os.environ if environ is None else environ
    return parse_mode(source.get(ENV_VAR))


def current_mode() -> ServerMode:
    """The mode of this process, resolved once and then held.

    Held on purpose: a mode that could change between two requests would be a
    runtime switch, and the whole point is that it is not one.
    """
    global _cached
    if _cached is None:
        _cached = resolve_mode()
    return _cached


def reset_mode_cache() -> None:
    """Forget the resolved mode. For tests, which run several modes in one process."""
    global _cached
    _cached = None


def describe_mode(mode: ServerMode | None = None) -> dict[str, Any]:
    """The machine-readable descriptor the browser asks for on page load.

    Deliberately free of wording: the interface holds its own sentences, so a
    new translation does not need a server change.
    """
    mode = mode or current_mode()
    return {
        "mode": mode.value,
        "storage": "browser" if mode.stores_in_browser else "host",
        "key_field": mode.key_from_browser,
        "host_pays_calls": mode.host_pays,
        "implemented": mode.implemented,
        "accounts_required": mode.needs_user_accounts,
        "export_import": mode.stores_in_browser,
    }


def require_implemented(mode: ServerMode | None = None) -> ServerMode:
    """Refuse to serve a stub mode instead of pretending it works."""
    mode = mode or current_mode()
    if not mode.implemented:
        raise ServerModeError(
            f"Server mode {mode.value!r} is a placeholder, not a working mode. "
            "It would need accounts, billing and server-side storage; none of "
            "that is built. Use local, huckepack-gift or huckepack-only-host."
        )
    return mode
