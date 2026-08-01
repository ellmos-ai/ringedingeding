"""Slot label handling for scheduling polls.

**Known limitation, stated up front:** slots are matched as *labels*, not as
time intervals. "Sat 14-18" and "Sat 15-17" are two different slots here; no
overlap arithmetic happens. That is a deliberate trade — inventing an interval
parser for free-form spoken German ("Samstag ab mittags, aber nicht zu spät")
would produce confident nonsense.

The supported way around it is to give the poll an explicit window
(``--slot "Sat 14-18" --slot "Sun 10-14"``). The recipient schema then
constrains answers to that enum, the voice agent has to pick from it, and the
intersection is exact. Open scheduling questions still work, they just match on
normalised text.
"""

from __future__ import annotations

import re

__all__ = ["normalize_slot", "canonical_display", "SlotIndex"]

_DASHES = dict.fromkeys(map(ord, "–—−‐‑­"), "-")
_PUNCT_EDGE = re.compile(r"^[\s.,;:!?]+|[\s.,;:!?]+$")
_WS = re.compile(r"\s+")
_FULL_HOUR = re.compile(r"\b(\d{1,2})[:.]00\b")
_TRAILING_UNIT = re.compile(r"\s*(uhr|o'?clock|h)\b", re.IGNORECASE)
_AROUND_DASH = re.compile(r"\s*-\s*")
_BIS = re.compile(r"\s+(bis|to|till|until)\s+", re.IGNORECASE)


def normalize_slot(label: str) -> str:
    """Return a canonical matching key for a slot label.

    ``"Sa 14:00 – 18:00 Uhr"`` and ``"sa 14-18"`` both become ``"sa 14-18"``.
    Returns ``""`` for empty input; callers must skip those.
    """
    if not isinstance(label, str):
        return ""
    text = label.translate(_DASHES).strip().lower()
    text = _BIS.sub("-", text)
    text = _TRAILING_UNIT.sub("", text)
    text = _FULL_HOUR.sub(r"\1", text)
    text = _AROUND_DASH.sub("-", text)
    text = _WS.sub(" ", text)
    text = _PUNCT_EDGE.sub("", text)
    return text


def canonical_display(label: str) -> str:
    """Tidy a label for display without destroying the original wording."""
    if not isinstance(label, str):
        return ""
    text = label.translate(_DASHES).strip()
    return _WS.sub(" ", text)


class SlotIndex:
    """Maps normalised slot keys back to a stable display label.

    The first spelling seen for a key wins, so a poll's own window labels take
    precedence over whatever wording came back from a call.
    """

    def __init__(self, preferred: list[str] | tuple[str, ...] = ()) -> None:
        self._display: dict[str, str] = {}
        self._order: list[str] = []
        for label in preferred:
            self.add(label)

    def add(self, label: str) -> str:
        """Register ``label`` and return its key. Empty labels are ignored."""
        key = normalize_slot(label)
        if not key:
            return ""
        if key not in self._display:
            self._display[key] = canonical_display(label)
            self._order.append(key)
        return key

    def key(self, label: str) -> str:
        return normalize_slot(label)

    def display(self, key: str) -> str:
        return self._display.get(key, key)

    @property
    def keys(self) -> list[str]:
        """All known keys, in the order they were first registered."""
        return list(self._order)

    def __contains__(self, key: object) -> bool:
        return key in self._display

    def __len__(self) -> int:
        return len(self._order)
