"""Ways to place a call.

``FixtureTransport`` is the default and needs neither an account nor a network.
The live transports are only ever constructed by the CLI, and only after an
explicit ``--live`` flag plus a typed confirmation.
"""

from __future__ import annotations

from .base import CallOutcome, CallRequest, CallTransport
from .fixture import FixtureTransport

__all__ = [
    "CallOutcome",
    "CallRequest",
    "CallTransport",
    "FixtureTransport",
]
