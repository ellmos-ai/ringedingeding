"""Result schemas and call instructions.

CALL-E offers no field for tone, persona or script — the conversation is steered
by two things only: the ``task`` free text and the ``recipient_result_schema``.
The schema is the stronger lever. Whatever the agent is required to fill in, it
has to find out during the call. So the schema is designed first and the prose
is written to match it, not the other way round.

The free text has one measured property worth knowing (FINDINGS.md section 4):
**quotation marks are honoured to the letter.** A question written in quotes
came out of the loudspeaker character for character, including a deliberate
typo that any rephrasing agent would have fixed. Text *outside* quotes is
rephrased, and extended — the planner adds behaviour of its own that was never
asked for. So the two things that must not drift, the question itself and the
sentence disclosing that this is an automated call, are quoted below; the rest
is left as guidance on purpose.

Every schema here carries these fields that exist purely to keep the merge
honest:

``reachable``
    False when the line was answered but not by the person we wanted — including
    when identity could never be confirmed at all (see the identity check in
    ``build_task_text`` below). Checked before ``refused`` in ``models.py`` on
    purpose: nothing said on a call where the wrong person picked up is this
    participant's answer.
``refused``
    True when the person was reached and chose not to answer. A valid outcome.
``callback_requested``
    Only set when ``reachable`` is false because the right person could not
    come to the phone: a good time to call back, if one was offered. Omitted,
    never null, when it does not apply — see the schema note on nullable
    types below.
``note``
    The qualifier a tally would otherwise flatten ("yes, but under 50 euros").

No schema sent to the CALL-E API may use a nullable union type anywhere
(``{"type": ["string", "null"]}``, ``"type": "null"``, or ``null`` inside an
``enum``): the API rejects the entire call-create request for it
(``result_schema_invalid``, upstream issue #120). "Not applicable" is
therefore always expressed as an *absent* optional field, never as an
explicit null — both in the schemas below and in the guidance that tells the
agent what to do with an optional field it has nothing to put in.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .models import Poll, PollKind

__all__ = [
    "OTHER_CHOICE_FIELD",
    "aggregate_result_schema",
    "build_task_text",
    "recipient_result_schema",
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
    "callback_requested": {
        "type": "string",
        "description": (
            "Only when the right person could not be reached: what they said "
            "about a good time to call back, in their own words. Leave this "
            "out entirely when it does not apply — do not send an empty "
            "string or null for it."
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
            "reason": {
                "type": "string",
                "description": (
                    "Why the person prefers this option, in their own words. "
                    "Empty if they gave no reason."
                ),
            },
            "concerns": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Reservations or counterarguments the person raised, each "
                    "kept in their own words."
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
            "stance": {
                "type": "string",
                "enum": ["support", "against", "mixed", "neutral", "unclear"],
                "description": (
                    "The direction of the answer for a local tendency count. "
                    "Use mixed when support and opposition are both material, "
                    "neutral for no preference, and unclear when no direction can be justified."
                ),
            },
            "reasons": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Reasons supporting the person's position, in their own words.",
            },
            "concerns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Reservations and counterarguments, in their own words.",
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
        # Nutzer-Vorgabe, live 2026-08-22 (R6): the list itself is already
        # in the right order (Project.replace_slots sorts it chronologically,
        # day by day, earlier time window before the later one, regardless
        # of the order it was typed into the form in — see projects.py). The
        # instruction below spells that order out explicitly rather than
        # relying on it being followed just because the list happens to be
        # sorted that way.
        return (
            f'Ask: "{poll.question}"\n'
            f"Go through these proposed slots one at a time, in exactly this "
            f"order, never several at once: {slots}.\n"
            "Finish one day — all of its time windows, earliest first — before "
            "moving on to the next day. "
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
            "record that as an abstention — do not push for a pick. Ask briefly "
            "why, and record any reservation or counterargument separately."
        )
    return (
        f'Ask: "{poll.question}"\n'
        "Let them answer freely. Record what they said, their reasons and concerns. "
        "Classify only the direction of the answer as support, against, mixed, "
        "neutral or unclear so the local report can show a tendency and countervoices."
    )


def _question_block_de(poll: Poll) -> str:
    if poll.kind is PollKind.SLOT and poll.has_window:
        slots = "; ".join(poll.slots)
        # Nutzer-Vorgabe, live 2026-08-22 (R6): Die Liste selbst ist schon in
        # der richtigen Reihenfolge (Project.replace_slots sortiert
        # chronologisch, Tag für Tag, frueheres Zeitfenster vor dem
        # spaeteren — unabhaengig von der Eingabereihenfolge in der Maske,
        # siehe projects.py). Die Anweisung unten macht diese Reihenfolge
        # zusaetzlich explizit, statt sich allein darauf zu verlassen, dass
        # sie befolgt wird, nur weil die Liste zufaellig so sortiert ist.
        return (
            f'Stelle die Frage: "{poll.question}"\n'
            f"Gehe diese Vorschläge einzeln durch, in genau dieser Reihenfolge, "
            f"nie mehrere gleichzeitig: {slots}.\n"
            "Schließe einen Tag — alle seine Zeitfenster, das früheste zuerst — "
            "ab, bevor du zum nächsten Tag übergehst. "
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
            "Präferenz, ist das eine Enthaltung — dränge nicht auf eine Wahl. "
            "Frage kurz nach dem Grund und halte Bedenken oder Gegenargumente getrennt fest."
        )
    return (
        f'Stelle die Frage: "{poll.question}"\n'
        "Lass die Person frei antworten. Halte Antwort, Gründe und Bedenken in "
        "ihren eigenen Worten fest. Ordne nur die Richtung als Zustimmung, "
        "Ablehnung, gemischt, neutral oder unklar ein, damit der lokale Bericht "
        "Tendenz und Gegenstimmen zeigen kann."
    )


_RULES_EN = """\
Anything in quotation marks is spoken exactly as written, word for word.
Everything outside quotation marks is guidance you put into your own words.

Conduct the entire conversation in English. Every sentence you speak aloud
must be English, even a sentence given to you here in quotation marks.

Rules for this call, in this order:

1. Open with this sentence, before anything else and unprompted:
   "Hello, this is an automated assistant calling on behalf of {organizer}.
   I have one short question." Do not wait to be asked.
{opening_block}2. {identity_block}
3. Ask whether now is a good moment. If it is not, say you will not call back
   automatically and end the call politely.
4. {question_block}
5. If the person does not want to answer, accept it immediately, thank them and
   end the call. Do not persuade, do not ask twice, do not offer reasons.
6. Give no medical, legal or financial advice, and ask for none. If anything
   sounds like an emergency, end the poll immediately and tell the person to
   contact the local emergency services.
7. Never reveal who else is being called, what anyone else answered, or any
   phone number.
8. Keep it short. Two minutes is plenty. Then fill in the result fields.
{closing_block}"""

_RULES_DE = """\
Alles in Anführungszeichen wird wortwörtlich so gesprochen, wie es dasteht.
Alles außerhalb der Anführungszeichen formulierst du selbst.

Führe das gesamte Gespräch auf Deutsch. Jeder Satz, den du laut sprichst, muss
Deutsch sein — auch ein Satz, der dir hier in Anführungszeichen vorgegeben ist.

Regeln für dieses Gespräch, in dieser Reihenfolge:

1. Beginne von dir aus mit genau diesem Satz, vor allem anderen:
   "Guten Tag, hier ist ein automatischer Assistent im Auftrag von {organizer}.
   Ich habe eine kurze Frage." Warte nicht, bis jemand nachfragt.
{opening_block}2. {identity_block}
3. Frage, ob es gerade passt. Wenn nicht: sage, dass du nicht automatisch
   erneut anrufst, und beende das Gespräch freundlich.
4. {question_block}
5. Will die Person nicht antworten, akzeptiere das sofort, bedanke dich und
   beende das Gespräch. Nicht überreden, nicht nachfragen, keine Gründe anbieten.
6. Gib keine medizinischen, rechtlichen oder finanziellen Ratschläge und frage
   auch nicht danach. Klingt etwas nach einem Notfall, beende die Umfrage sofort
   und verweise auf den Notruf.
7. Verrate nie, wer sonst noch angerufen wird, was andere geantwortet haben,
   oder irgendeine Rufnummer.
8. Fasse dich kurz. Zwei Minuten reichen. Fülle danach die Ergebnisfelder aus.
{closing_block}"""


def _quote(text: str) -> str:
    """Wrap a user's own sentence so it is spoken exactly as written.

    Quotation marks are the only lever there is for verbatim speech
    (FINDINGS.md section 4), so a greeting somebody typed has to arrive inside
    them. Any quotation marks already in the sentence are turned into typographic
    ones, because a stray ``"`` would close the quotation early and hand the rest
    of the sentence back to the rephrasing agent.
    """
    return '"' + " ".join(str(text).replace('"', "”").split()) + '"'


def _opening_block(lines: Sequence[str], german: bool) -> str:
    """The organizer's own greeting, spoken *after* the mandatory disclosure.

    Deliberately after, never instead of: the sentence that says this is an
    automated call on somebody's behalf is not negotiable, and a friendly
    greeting in front of it would bury it.
    """
    said = [line for line in lines if str(line).strip()]
    if not said:
        return ""
    lead = "   Sage danach wörtlich:" if german else "   Then say, word for word:"
    return "\n".join([lead] + [f"   {_quote(line)}" for line in said]) + "\n"


def _closing_block(lines: Sequence[str], german: bool) -> str:
    said = [line for line in lines if str(line).strip()]
    if not said:
        return ""
    lead = (
        "9. Verabschiede dich am Ende wörtlich mit:"
        if german
        else "9. Close the call with these words, exactly:"
    )
    return "\n".join([lead] + [f"   {_quote(line)}" for line in said]) + "\n"


def _identity_block(given_name: str | None, german: bool) -> str:
    """Confirm identity right after the disclosure, before anything else.

    Nutzer-Testdesign 2026-08-11: a call must never be scored as the intended
    participant having answered just because *somebody* picked up. This step
    forces the check before the real question is asked. The result travels
    back through the required ``reachable`` field (see ``_COMMON_PROPERTIES``
    above) — the agent is told explicitly, below, to leave it false whenever
    identity was never confirmed, regardless of what the other person then
    says or agrees to. ``models.py`` checks ``reachable`` before ``refused``
    for exactly this reason: nothing a stranger says on this call is this
    participant's answer.

    Skipped, honestly, when there is no name to ask for — ``--no-names``
    withholds the name from CALL-E by design, so there is nothing to confirm
    against. That is a known, deliberate limitation of this gate, not an
    oversight: a caller must choose between the privacy of ``--no-names`` and
    the identity check, it cannot have both at once.
    """
    if not given_name:
        if german:
            return (
                "Ohne Namen kann die Identität nicht geprüft werden — fahre "
                "direkt mit der nächsten Frage fort."
            )
        return (
            "No name was given, so identity cannot be confirmed — proceed "
            "directly to the next question."
        )
    if german:
        question = _quote(f"Spreche ich mit {given_name}?")
        return (
            f"Frage als Erstes {question} Ist es nicht {given_name}: bitte "
            f"höflich darum, {given_name} ans Telefon zu holen. Geht das "
            "nicht, frage nach einem guten Zeitpunkt für einen Rückruf und "
            "halte ihn in callback_requested fest (weglassen, falls nicht "
            "zutreffend), bedanke dich und beende das Gespräch, ohne die "
            "eigentliche Frage zu stellen. Ohne bestätigte Identität bleibt "
            "reachable false — unabhängig davon, was die andere Person sagt "
            "oder antwortet."
        )
    question = _quote(f"Am I speaking with {given_name}?")
    return (
        f"First ask {question} If this is not {given_name}: politely ask "
        f"them to bring {given_name} to the phone. If that is not possible, "
        "ask for a good time to call back and record it in "
        "callback_requested (leave it out when it does not apply), thank "
        "them and end the call without asking the actual question. Without "
        "confirmed identity, reachable stays false — regardless of what the "
        "other person says or answers."
    )


def _urgency_block(urgency: str, german: bool) -> str:
    """How pressing it is — guidance, and deliberately *not* quoted.

    Quotation marks would make the agent read the organizer's private note about
    urgency out loud. What is wanted is a change of tone, so this goes in as
    unquoted guidance, which the measured behaviour says will be rephrased and
    acted on rather than recited.

    Urgency changes the tone and nothing else. It is not a licence to ask twice,
    to press for an answer, or to keep somebody on the telephone — rule 4 above
    still holds and says so first.
    """
    text = " ".join(str(urgency).split())
    if not text:
        return ""
    if german:
        return (
            f"   Es eilt ({text}). Komm entsprechend zügig zur Sache — aber "
            "dränge trotzdem niemanden und akzeptiere ein Nein sofort.\n"
        )
    return (
        f"   This is time-sensitive ({text}). Come to the point accordingly — "
        "but still press nobody, and accept a no immediately.\n"
    )


def build_task_text(
    poll: Poll,
    given_name: str | None = None,
    *,
    opening: Sequence[str] = (),
    closing: Sequence[str] = (),
    urgency: str = "",
) -> str:
    """The ``task`` free text sent to CALL-E for one recipient.

    Only the given name is passed on — never the full name, never the phone
    number in the prose, never anything about the other participants. That is
    the whole payload the voice agent gets about the person.

    ``opening`` and ``closing`` are the organizer's own sentences. They are
    inserted in quotation marks, which is what makes them survive verbatim, and
    they are placed around the fixed rules rather than replacing any of them.
    """
    german = str(poll.language).lower().startswith("de")
    template = _RULES_DE if german else _RULES_EN
    block = _question_block_de(poll) if german else _question_block_en(poll)
    # The block sits inside a numbered list, so continuation lines get indented
    # to match. This text is read out loud by an agent; layout is part of it.
    block = "\n   ".join(block.splitlines())
    text = template.format(
        organizer=poll.organizer,
        question_block=block,
        opening_block=_opening_block(opening, german) + _urgency_block(urgency, german),
        closing_block=_closing_block(closing, german),
        identity_block=_identity_block(given_name, german),
    )
    if given_name:
        greeting = (
            f"Du rufst {given_name} an.\n\n" if german else f"You are calling {given_name}.\n\n"
        )
        text = greeting + text
    return text
