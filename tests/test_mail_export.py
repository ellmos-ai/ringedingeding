"""The invitation's second channel: a locally rendered mailto: link and .eml.

Nothing here ever talks to a mail server -- see the module docstring in
ringedingeding/mail_export.py for why. These tests only check what gets
rendered, the same way test_calendar_export-style tests elsewhere check
what render_ics produces without any network involved.
"""

from __future__ import annotations

from email import message_from_bytes, policy
from email.utils import parseaddr

from ringedingeding.mail_export import mailto_link, render_invitation_eml


def test_mailto_link_percent_encodes_subject_and_body():
    link = mailto_link(
        to_email="anna@example.org",
        subject="Einladung: Hochzeit",
        body="Bist du dabei?\nMi 30.09. 18:00-21:00",
    )
    assert link.startswith("mailto:anna%40example.org?")
    assert "subject=Einladung%3A%20Hochzeit" in link
    # A newline in the body must survive percent-encoded, not raw -- a raw
    # newline in a mailto: URI is invalid and some clients choke on it.
    assert "%0A" in link
    assert "\n" not in link


def test_mailto_link_never_carries_an_attachment():
    """mailto: has no attachment mechanism (RFC 6068) -- the function must
    not silently drop one, it must never be asked to carry one at all."""
    import inspect

    assert "ics" not in inspect.signature(mailto_link).parameters


def test_eml_has_no_from_header():
    """No organizer e-mail address is ever collected (AGENTS.md data
    minimisation) -- inventing one would look like a real sender without
    being it."""
    raw = render_invitation_eml(
        to_email="anna@example.org", to_name="Anna", subject="Einladung", body="Text"
    )
    message = message_from_bytes(raw, policy=policy.default)
    assert message["From"] is None


def test_eml_carries_the_recipient_subject_and_body_verbatim():
    raw = render_invitation_eml(
        to_email="anna@example.org",
        to_name="Anna Beispiel",
        subject="Einladung: Hochzeit",
        body="Bist du dabei? Mi 30.09. 18:00-21:00",
    )
    message = message_from_bytes(raw, policy=policy.default)
    assert message["Subject"] == "Einladung: Hochzeit"
    name, address = parseaddr(message["To"])
    assert name == "Anna Beispiel"
    assert address == "anna@example.org"
    body_part = message.get_body(preferencelist=("plain",))
    assert body_part is not None
    assert body_part.get_content().strip() == "Bist du dabei? Mi 30.09. 18:00-21:00"


def test_eml_without_an_ics_has_no_attachment():
    raw = render_invitation_eml(
        to_email="anna@example.org", to_name="Anna", subject="Einladung", body="Text"
    )
    message = message_from_bytes(raw, policy=policy.default)
    assert list(message.iter_attachments()) == []


def test_eml_with_an_ics_attaches_it_with_the_given_filename():
    ics = b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n"
    raw = render_invitation_eml(
        to_email="anna@example.org",
        to_name="Anna",
        subject="Einladung",
        body="Text",
        ics_bytes=ics,
        ics_filename="hochzeit.ics",
    )
    message = message_from_bytes(raw, policy=policy.default)
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    attachment = attachments[0]
    assert attachment.get_filename() == "hochzeit.ics"
    assert attachment.get_content_type() == "text/calendar"
    assert attachment.get_content() == ics.decode("utf-8")


def test_rendering_is_otherwise_deterministic():
    """Only the MIME boundary is allowed to vary between calls (Python's
    email module generates it fresh each time) -- everything else, byte for
    byte, must be reproducible so a diff between two runs is meaningful."""
    kwargs = {"to_email": "a@example.org", "to_name": "A", "subject": "S", "body": "B"}
    first = message_from_bytes(render_invitation_eml(**kwargs), policy=policy.default)
    second = message_from_bytes(render_invitation_eml(**kwargs), policy=policy.default)
    assert first["Date"] == second["Date"]
    assert first["Subject"] == second["Subject"]
    assert first["To"] == second["To"]
    assert first.get_body(("plain",)).get_content() == second.get_body(("plain",)).get_content()
