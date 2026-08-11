"""Region and locale, derived from the chosen language when not set explicitly.

Measured 2026-08-11 (operator field trial, Block C): ``create --language de``
alone produced a plan header reading "de (en-US, region US)" — German prose
that CALL-E would have read out in a US-region, en-US voice. ``language``,
``region`` and ``locale`` were three independent defaults with no relationship
between them, scattered across every poll- and project-creation entry point
in this project, each with its own hardcoded triple.

Every one of those entry points now goes through this single function
instead. An explicit ``region``/``locale`` — one the caller actually typed —
still wins; only an unset one (``None``, or ``""`` the way an empty HTML form
field arrives) is derived from the language.
"""

from __future__ import annotations

__all__ = ["region_locale_for"]

# The only two languages this project's UI offers today (see
# TranslationSystem.SUPPORTED_LANGUAGES in web/app.py). A language this table
# does not know falls back to the long-standing project default rather than
# guessing — the same US/en-US pair every entry point already defaulted to
# before this function existed.
_REGION_LOCALE_BY_LANGUAGE: dict[str, tuple[str, str]] = {
    "de": ("DE", "de-DE"),
    "en": ("US", "en-US"),
}
_FALLBACK_REGION_LOCALE: tuple[str, str] = ("US", "en-US")


def region_locale_for(
    language: str, *, region: str | None = None, locale: str | None = None
) -> tuple[str, str]:
    """The ``(region, locale)`` pair to store for ``language``.

    ``region``/``locale`` count as "not set" whether they arrive as ``None``
    (never asked for — a Python default) or as ``""`` (an HTML form field the
    operator left blank) — both shapes occur across this project's entry
    points. Anything else is an explicit choice and is returned unchanged.
    """
    derived_region, derived_locale = _REGION_LOCALE_BY_LANGUAGE.get(
        str(language).strip().lower(), _FALLBACK_REGION_LOCALE
    )
    return (region or derived_region, locale or derived_locale)
