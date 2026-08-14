"""Timing constants — measured against the real service, not guessed.

All numbers here come from one observed call (FINDINGS.md section 6). They are
kept in one place because two very different parts of the program depend on
them: the planner, which tells the user how long a poll will take, and the
poller, which decides when it is worth asking the API anything at all.

    event                                   offset from starting the call
    ------------------------------------------------------------------
    bot created                             +2 s
    telephone rings                        +39 s
    connected                              +43 s
    conversation over (32 s of talking)    +75 s
    status finally reads COMPLETED         +99 s

The important part is the shape, not the exact seconds: **roughly 40 seconds of
lead time before anything happens, independent of how long the conversation
lasts.** A one-minute chat therefore costs about a minute and a half.

One observation is not a distribution. These are working figures for estimates
and poll scheduling, never promises.
"""

from __future__ import annotations

__all__ = [
    "LEAD_SECONDS",
    "SETTLE_SECONDS",
    "TYPICAL_CONVERSATION_SECONDS",
    "estimate_seconds",
    "format_duration",
]

LEAD_SECONDS = 40.0
"""Dialling and connecting, before a word is spoken. Measured: +39 s to ringing."""

TYPICAL_CONVERSATION_SECONDS = 90.0
"""Working assumption for a short poll question. The instructions ask the agent
to keep it under two minutes; the one measured call took 32 s."""

SETTLE_SECONDS = 25.0
"""Between the end of the conversation and the API admitting it is over.
Measured: conversation ended at +75 s, status flipped at +99 s."""


def estimate_seconds(calls: int, *, concurrency: int = 1) -> float:
    """Rough wall-clock estimate for ``calls`` calls.

    With ``concurrency > 1`` the lead time overlaps, which is the entire reason
    the parallel path exists. Whether CALL-E actually permits it is **not
    verified** — the caller has to say so when showing this number.
    """
    if calls <= 0:
        return 0.0
    per_call = LEAD_SECONDS + TYPICAL_CONVERSATION_SECONDS
    batches = -(-calls // max(1, concurrency))  # ceiling division
    return batches * per_call + SETTLE_SECONDS


def format_duration(seconds: float) -> str:
    """``95.0`` -> ``"about 2 min"``. Deliberately coarse."""
    if seconds <= 0:
        return "no time at all"
    minutes = seconds / 60.0
    if minutes < 1.5:
        return f"about {round(seconds / 10) * 10:.0f} s"
    return f"about {minutes:.0f} min"
