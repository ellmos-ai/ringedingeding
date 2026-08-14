"""ASCII umlaut substitutes get spoken literally, not corrected.

Measured 2026-08-11 (operator field trial, Block C): a task text containing
"fuer" was spoken aloud as "fuer", not "für" — CALL-E's voice agent reads
exactly what it is given, the same verbatim behaviour FINDINGS.md section 4
already measured for whole quoted sentences, now confirmed at the level of a
single substituted letter too.

This module only detects and warns. It never rewrites anything: "Feuer",
"teuer" and "neue" are real German words that legitimately contain the same
three letters a substitute umlaut does, so an automatic fix — or a bare
letter-pattern regex over "ae"/"oe"/"ue" — would be wrong often enough to
make the warning itself untrustworthy. The decision stays with the operator.
The word list below is therefore closed and specific on purpose, extendable
with one line rather than turned into a heuristic.
"""

from __future__ import annotations

import re
from collections.abc import Callable

__all__ = ["find_umlaut_substitutes", "umlaut_warning", "warn_if_german"]

# (ascii substitute, correct spelling) — case-insensitive, whole-word match
# only, so "Feuer" never triggers on "fuer" inside it. Extend with one line;
# do not turn this into a pattern (see the module docstring for why).
_SUBSTITUTE_WORDS: tuple[tuple[str, str], ...] = (
    ("fuer", "für"),
    ("ueber", "über"),
    ("moechte", "möchte"),
    ("waere", "wäre"),
    ("koennen", "können"),
    ("muessen", "müssen"),
    ("groesse", "größe"),
    ("strasse", "straße"),
    ("zurueck", "zurück"),
    ("natuerlich", "natürlich"),
    ("spaeter", "später"),
    ("gespraech", "Gespräch"),
    ("aenderung", "Änderung"),
    ("oeffnung", "Öffnung"),
)

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(rf"\b{re.escape(substitute)}\b", re.IGNORECASE), correct)
    for substitute, correct in _SUBSTITUTE_WORDS
)


def find_umlaut_substitutes(*texts: str) -> list[tuple[str, str]]:
    """Every ``(found substitute, correct spelling)`` pair across ``texts``.

    Deduplicated (case-insensitively) and in the order first seen. Only
    meant to be called for German text — there is no reason to warn about
    "fuer" appearing in an English poll.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for pattern, correct in _PATTERNS:
            match = pattern.search(text)
            if match and match.group(0).lower() not in seen:
                seen.add(match.group(0).lower())
                found.append((match.group(0), correct))
    return found


def umlaut_warning(findings: list[tuple[str, str]]) -> str:
    """One printable, multi-line warning — or ``""`` if there is nothing to say."""
    if not findings:
        return ""
    lines = [
        f'  "{found}" wird sonst wörtlich als "{found}" vorgelesen, nicht als "{correct}"'
        for found, correct in findings
    ]
    return "\n".join(
        [
            "WARNUNG: mögliche Ersatz-Umlaute gefunden — keine automatische "
            "Korrektur, bitte von Hand mit echten Umlauten (ä ö ü ß) prüfen:",
            *lines,
        ]
    )


def warn_if_german(language: str, *texts: str, out: Callable[[str], None]) -> None:
    """Print the warning (via ``out``) when ``language`` is German and any of
    ``texts`` contains a known substitute word. A no-op otherwise — there is
    no reason to flag "fuer" in an English poll, and nothing is printed when
    nothing was found.

    The one shared gate for every CLI entry point below (``create``,
    ``project new``, ``project question``, ``project wording``), so "is this
    German?" is decided in exactly one place rather than reimplemented at
    each call site.
    """
    if not str(language).strip().lower().startswith("de"):
        return
    warning = umlaut_warning(find_umlaut_substitutes(*texts))
    if warning:
        out(warning)
