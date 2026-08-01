"""Result schemas and call instructions.

CALL-E offers no field for tone, persona or script — the conversation is steered
by two things only: the ``task`` free text and the ``recipient_result_schema``.
The schema is the stronger lever. Whatever the agent is required to fill in, it
has to find out during the call. So the schema is designed first and the prose
is written to match it, not the other way round.

Every schema here carries three fields that exist purely to keep the merge
honest:

``reachable``
    False when the line was answered but not by the person we wanted.
``refused``
    True when the person was reached and chose not to answer. A valid outcome.
``note``
    The qualifier a tally would otherwise flatten ("yes, but under 50 euros").
"""

from __future__ import annotations

from typing import Any

from .models import Poll, PollKind

__all__ = [
    "recipient_result_schema",
    "aggregate_result_schema",
    "build_task_text",
    "OTHER_CHOICE_FIELD",
]

OTHER_CHOICE_FIELD = "other_choice"

_COMMON_PROPERTIES: dict[str, Any] = {
    "reachable": {
        "type": "boolean",
        "description": (
            "true if you actually spoke with the person you were asked for. "
            "false if somebody else answered, if it was a mailbox, or if you "
            "could not confirm who you were talking to."
        ),
    },
    "refused": {
        "type": "boolean",
        "description": (
            "true if the person understood the question and chose not to answer. "
            "This is a valid outcome. Do not try to change their mind."
        ),
    },
}


def _slot_item(poll: Poll) -> dict[str, Any]:
    item: dict[str, Any] = {"type": "string"}
    if poll.has_window:
        item["enum"] = list(poll.slots)
    return item


def recipient_result_schema(poll: Poll) -> dict[str, Any]:
    """JSON schema the voice agent must fill in per recipient."""
    if poll.kind is PollKind.SLOT:
        properties = {
            **_COMMON_PROPERTIES,
            "available_slots": {
                "type": "array",
                "items": _slot_item(poll),
                "description": (
                    "Every proposed slot the person can make. "
                    + (
                        "Use the exact wording of the proposed slots."
                        if poll.has_window
                        else "Use the person's own wording, one entry per slot."
                    )
                ),
            },
            "cannot": {
                "type": "array",
                "items": _slot_item(poll),
                "description": (
                    "Every proposed slot the person cannot make. Ask explicitly; "
                    "do not infer it from what they did not mention."
                ),
            },
            "note": {
                "type": "string",
                "description": (
                    "Any condition or qualifier in the person's own words, "
                    "for example 'only if we finish by 4'. Empty if there is none."
                ),
            },
        }
        required = ["reachable", "refused"]

    elif poll.kind is PollKind.CHOICE:
        properties = {
            **_COMMON_PROPERTIES,
            "choice": {
                "type": "string",
                "enum": list(poll.options),
                "description": (
                    "The option the person picked. Leave this out entirely if "
                    "they named something that is not on the list."
                ),
            },
            OTHER_CHOICE_FIELD: {
                "type": "string",
                "description": (
                    "Filled only when the person named something outside the "
                    "list. Their own words. Never squeeze it into 'choice'."
                ),
            },
            "abstained": {
                "type": "boolean",
                "description": (
                    "true if the person explicitly has no preference. "
                    "Different from 'refused' and different from not reached."
                ),
            },
            "condition": {
                "type": "string",
                "description": (
                    "A condition attached to the answer, in the person's own "
                    "words, for example 'yes, but only under 50 euros'."
                ),
            },
        }
        required = ["reachable", "refused"]

    else:  # PollKind.OPEN
        properties = {
            **_COMMON_PROPERTIES,
            "answer": {
                "type": "string",
                "description": (
                    "The person's answer in their own words, condensed to at "
                    "most two sentences. Do not interpret, do not judge."
                ),
            },
            "note": {"type": "string", "description": "Anything else worth passing on."},
        }
        required = ["reachable", "refused"]

    return {
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": False,
    }


def aggregate_result_schema(poll: Poll) -> dict[str, Any]:
    """Batch-level schema.

    Deliberately thin. The merge happens locally in :mod:`ringedingeding.merge`
    where it can be inspected and tested; asking the call agent to do the
    counting would move the one part that must be auditable off this machine.
    """
    return {
        "type": "object",
        "required": ["reached_count"],
        "properties": {
            "reached_count": {
                "type": "integer",
                "description": "How many recipients you actually spoke with.",
            }
        },
        "additionalProperties": False,
    }


def _question_block_en(poll: Poll) -> str:
    if poll.kind is PollKind.SLOT and poll.has_window:
        slots = "; ".join(poll.slots)
        return (
            f'Ask: "{poll.question}"\n'
            f"Go through these proposed slots one by one and ask for each whether "
            f"it works: {slots}.\n"
            "Record every slot that works and every slot that does not. "
            "Do not assume a slot works just because they did not mention it."
        )
    if poll.kind is PollKind.SLOT:
        return (
            f'Ask: "{poll.question}"\n'
            "Let them name the times that work. Then ask explicitly which times "
            "do not work. Write both down in their own words."
        )
    if poll.kind is PollKind.CHOICE:
        options = "; ".join(poll.options)
        return (
            f'Ask: "{poll.question}"\n'
            f"Read out these options: {options}.\n"
            "If they pick one, record it. If they name something else, record "
            "that separately in their own words. If they have no preference, "
            "record that as an abstention — do not push for a pick."
        )
    return (
        f'Ask: "{poll.question}"\n'
        "Let them answer freely. Record what they said, do not interpret it."
    )


def _question_block_de(poll: Poll) -> str:
    if poll.kind is PollKind.SLOT and poll.has_window:
        slots = "; ".join(poll.slots)
        return (
            f'Stelle die Frage: "{poll.question}"\n'
            f"Gehe diese Vorschläge einzeln durch und frage zu jedem, ob er passt: {slots}.\n"
            "Halte fest, welche Zeiten passen und welche nicht. Nimm nicht an, "
            "dass eine Zeit passt, nur weil sie nicht erwähnt wurde."
        )
    if poll.kind is PollKind.SLOT:
        return (
            f'Stelle die Frage: "{poll.question}"\n'
            "Lass die Person die passenden Zeiten nennen. Frage danach "
            "ausdrücklich, welche Zeiten nicht gehen. Halte beides in ihren "
            "eigenen Worten fest."
        )
    if poll.kind is PollKind.CHOICE:
        options = "; ".join(poll.options)
        return (
            f'Stelle die Frage: "{poll.question}"\n'
            f"Lies diese Möglichkeiten vor: {options}.\n"
            "Wenn eine davon gewählt wird, halte sie fest. Wird etwas anderes "
            "genannt, halte das getrennt in eigenen Worten fest. Gibt es keine "
            "Präferenz, ist das eine Enthaltung — dränge nicht auf eine Wahl."
        )
    return (
        f'Stelle die Frage: "{poll.question}"\n'
        "Lass die Person frei antworten. Halte fest, was gesagt wurde, ohne es "
        "zu deuten."
    )


_RULES_EN = """\
Rules for this call, in this order:

1. In your very first sentence, unprompted, say that you are an automated
   assistant calling on behalf of {organizer}, and say why you are calling.
   Do not wait to be asked.
2. Ask whether now is a good moment. If it is not, say you will not call back
   automatically and end the call politely.
3. {question_block}
4. If the person does not want to answer, accept it immediately, thank them and
   end the call. Do not persuade, do not ask twice, do not offer reasons.
5. Give no medical, legal or financial advice, and ask for none. If anything
   sounds like an emergency, end the poll immediately and tell the person to
   contact the local emergency services.
6. Never reveal who else is being called, what anyone else answered, or any
   phone number.
7. Keep it short. Two minutes is plenty. Then fill in the result fields.
"""

_RULES_DE = """\
Regeln für dieses Gespräch, in dieser Reihenfolge:

1. Sage im allerersten Satz von dir aus, dass du ein automatischer Assistent
   bist, der im Auftrag von {organizer} anruft, und nenne den Grund des Anrufs.
   Warte nicht, bis jemand nachfragt.
2. Frage, ob es gerade passt. Wenn nicht: sage, dass du nicht automatisch
   erneut anrufst, und beende das Gespräch freundlich.
3. {question_block}
4. Will die Person nicht antworten, akzeptiere das sofort, bedanke dich und
   beende das Gespräch. Nicht überreden, nicht nachfragen, keine Gründe anbieten.
5. Gib keine medizinischen, rechtlichen oder finanziellen Ratschläge und frage
   auch nicht danach. Klingt etwas nach einem Notfall, beende die Umfrage sofort
   und verweise auf den Notruf.
6. Verrate nie, wer sonst noch angerufen wird, was andere geantwortet haben,
   oder irgendeine Rufnummer.
7. Fasse dich kurz. Zwei Minuten reichen. Fülle danach die Ergebnisfelder aus.
"""


def build_task_text(poll: Poll, given_name: str | None = None) -> str:
    """The ``task`` free text sent to CALL-E for one recipient.

    Only the given name is passed on — never the full name, never the phone
    number in the prose, never anything about the other participants. That is
    the whole payload the voice agent gets about the person.
    """
    german = str(poll.language).lower().startswith("de")
    template = _RULES_DE if german else _RULES_EN
    block = _question_block_de(poll) if german else _question_block_en(poll)
    # The block sits inside a numbered list, so continuation lines get indented
    # to match. This text is read out loud by an agent; layout is part of it.
    block = "\n   ".join(block.splitlines())
    text = template.format(organizer=poll.organizer, question_block=block)
    if given_name:
        greeting = (
            f"Du rufst {given_name} an.\n\n" if german else f"You are calling {given_name}.\n\n"
        )
        text = greeting + text
    return text
