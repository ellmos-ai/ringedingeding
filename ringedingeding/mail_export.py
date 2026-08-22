"""Locally generated invitation e-mail — the second distribution channel.

Live finding, 2026-08-22 (R7): the invitation phase offered a call and
nothing else — no channel choice, and no way to reach somebody who prefers
e-mail. This module is the "genügt als erster Schritt" (a first step is
enough) answer: it never sends anything and never talks to a mail server.
It only *renders* two things a person can hand to their own mail client:

* :func:`mailto_link` — a ``mailto:`` URI with subject and body pre-filled,
  for a quick "open my mail app with this ready to send". ``mailto:`` has no
  attachment mechanism (RFC 6068), so this carries no calendar file.
* :func:`render_invitation_eml` — a standalone ``.eml`` file (RFC 5322,
  ``multipart/mixed``) with the same text as the body **and** the decided
  slot attached as an ``.ics`` file. Opening it in a desktop mail client
  ordinarily loads it as an editable draft — the person still presses send
  themselves.

Standard-library only, like :mod:`ringedingeding.calendar_export` — a dry
run stays a complete offline path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime
from urllib.parse import quote

__all__ = ["mailto_link", "render_invitation_eml"]

_FIXED_STAMP = datetime(2000, 1, 1, tzinfo=UTC)
"""Deterministic output, like calendar_export.render_ics's DTSTAMP — this is
not a claim about when the file was actually generated."""


def mailto_link(*, to_email: str, subject: str, body: str) -> str:
    """A ``mailto:`` URI that opens the person's own mail app, pre-filled.

    No attachment travels with it — that is a limit of ``mailto:`` itself,
    not of this function. Use :func:`render_invitation_eml` when the ``.ics``
    has to go along.
    """
    query = f"subject={quote(subject)}&body={quote(body)}"
    return f"mailto:{quote(to_email)}?{query}"


def render_invitation_eml(
    *,
    to_email: str,
    to_name: str,
    subject: str,
    body: str,
    ics_bytes: bytes | None = None,
    ics_filename: str = "termin.ics",
) -> bytes:
    """Render one invitation as a standalone ``.eml`` file.

    No ``From`` header is set: this program has no notion of the
    organizer's own e-mail account (AGENTS.md's data minimisation — only
    what one call, or one message, needs is ever collected), and inventing
    one would look like the organizer's real address without being it. A
    mail client opening this as a draft fills its own account in; a person
    reading the raw file sees an honest gap instead of a fabricated sender.
    """
    message = EmailMessage()
    message["To"] = f"{to_name} <{to_email}>" if to_name.strip() else to_email
    message["Subject"] = subject
    message["Date"] = format_datetime(_FIXED_STAMP)
    message.set_content(body)
    if ics_bytes is not None:
        message.add_attachment(
            ics_bytes,
            maintype="text",
            subtype="calendar",
            filename=ics_filename,
        )
    return message.as_bytes()
