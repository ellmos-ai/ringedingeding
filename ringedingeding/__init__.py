"""Ringedingeding — ask everyone, get one answer.

Ask one question to several people by phone and merge the replies into a single
result. Built on CALL-E (https://github.com/CALLE-AI/call-e-integrations).

The default execution mode is a dry run against fixtures. No phone call is ever
placed unless the caller explicitly passes ``--live`` and confirms.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
