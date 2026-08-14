from __future__ import annotations

import pytest

from ringedingeding.models import Answer, CallStatus, Participant, Poll, PollKind
from ringedingeding.store import Store


@pytest.fixture()
def store(tmp_path):
    with Store(tmp_path / "test.db") as opened:
        yield opened


def make_poll(**overrides) -> Poll:
    defaults = {
        "id": "poll_test",
        "question": "When can you make it?",
        "kind": PollKind.SLOT,
        "organizer": "Lukas",
        "language": "en",
        "region": "US",
        "locale": "en-US",
        "options": (),
        "slots": ("Sat 14-18", "Sun 10-14"),
    }
    defaults.update(overrides)
    return Poll(**defaults)


def make_participant(ref: str, phone: str = "+15555550100", name: str | None = None) -> Participant:
    return Participant(
        id=f"p_{ref}",
        poll_id="poll_test",
        ref=ref,
        name=name or ref.capitalize(),
        phone_e164=phone,
    )


def answer(participant_id: str, status: CallStatus = CallStatus.COMPLETED, **structured) -> Answer:
    return Answer(
        participant_id=participant_id,
        call_status=status,
        structured=structured,
    )
