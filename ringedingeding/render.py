"""Console and Markdown output.

Two design rules:

* **Nothing is printed that a family member could not read.** The console view
  and the Markdown export carry the same information; the Markdown file is what
  you send round afterwards.
* **The gaps are as prominent as the result.** An intersection over four of six
  people is printed as an intersection over four of six, with the two missing
  names and their status right underneath. It is never a footnote.

Rendered by hand rather than with a table library, because the dry run has to
work on a machine where nothing is installed.
"""

from __future__ import annotations

from collections.abc import Sequence

from .locales import region_locale_for
from .merge import ChoiceMerge, Coverage, MergeResult, OpenMerge, SlotMerge
from .models import Poll, PollKind
from .phone import mask_text
from .transports.base import CallRequest

__all__ = ["render_markdown", "render_plan", "render_result", "table"]

_NOBODY = "-"


def table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """A plain ASCII table. Empty input renders as a single dash."""
    if not rows:
        return _NOBODY
    columns = len(headers)
    cells = [[str(cell) for cell in row] + [""] * (columns - len(row)) for row in rows]
    widths = [
        max(len(str(headers[index])), *(len(row[index]) for row in cells))
        for index in range(columns)
    ]
    divider = "+" + "+".join("-" * (width + 2) for width in widths) + "+"

    def line(values: Sequence[str]) -> str:
        padded = [f" {str(value).ljust(widths[index])} " for index, value in enumerate(values)]
        return "|" + "|".join(padded) + "|"

    out = [divider, line(headers), divider]
    out.extend(line(row) for row in cells)
    out.append(divider)
    return "\n".join(out)


def _names(values: Sequence[str]) -> str:
    return ", ".join(values) if values else _NOBODY


def _poll_header(poll: Poll) -> list[str]:
    lines = [
        f"Question : {poll.question}",
        f"Kind     : {poll.kind.value}",
        f"Organizer: {poll.organizer}",
        f"Language : {poll.language} ({poll.locale}, region {poll.region})",
    ]
    expected_region, expected_locale = region_locale_for(poll.language)
    if poll.region != expected_region or poll.locale != expected_locale:
        # Field finding, 2026-08-11: language, region and locale used to be
        # three independent defaults with no relationship — this stored poll
        # predates the fix, or somebody deliberately overrode region/locale.
        # Either way the voice CALL-E uses may not match the spoken text.
        lines.append(
            f"WARNING  : region/locale ({poll.region}, {poll.locale}) do not "
            f"match language {poll.language!r} — expected "
            f"({expected_region}, {expected_locale}). The voice may not "
            "match the text being read out."
        )
    if poll.kind is PollKind.SLOT:
        lines.append(f"Slots    : {'; '.join(poll.slots) if poll.slots else '(open question)'}")
    if poll.kind is PollKind.CHOICE:
        lines.append(f"Options  : {'; '.join(poll.options)}")
    return lines


# --------------------------------------------------------------------------
# plan (dry-run preview)
# --------------------------------------------------------------------------


def render_plan(poll: Poll, requests: Sequence[CallRequest], *, show_payload: bool = False) -> str:
    """What would happen — before anything happens."""
    import json

    out: list[str] = []
    out.append("PLAN - nothing is dialed by this command")
    out.append("=" * 60)
    out.extend(_poll_header(poll))
    out.append("")

    out.append(f"Who would be called ({len(requests)}):")
    out.append(
        table(
            ["#", "Ref", "Name", "Number (masked)", "Idempotency-Key"],
            [
                [
                    str(index),
                    request.participant.ref,
                    request.participant.name,
                    request.participant.phone_masked,
                    request.idempotency_key,
                ]
                for index, request in enumerate(requests, start=1)
            ],
        )
    )
    out.append("")

    if requests:
        first = requests[0]
        out.append("Call instructions (task text), example for the first recipient:")
        out.append("-" * 60)
        out.append(first.task_text.rstrip())
        out.append("-" * 60)
        out.append("")
        out.append("Result schema the voice agent must fill in (recipient_result_schema):")
        out.append(json.dumps(first.recipient_schema, indent=2, ensure_ascii=False))
        out.append("")
        if show_payload:
            out.append("Request body for POST /v1/calls (phone masked for display):")
            out.append(json.dumps(first.payload(), indent=2, ensure_ascii=False))
            out.append("")

    return "\n".join(out)


# --------------------------------------------------------------------------
# results
# --------------------------------------------------------------------------


def _callback_detail(structured: dict[str, object]) -> str:
    """R19: surface a requested callback time, whatever bucket the answer
    landed in -- asking for one is no longer limited to the identity-mismatch
    case (schemas.py, ``callback_requested``)."""
    callback = structured.get("callback_requested")
    if not callback:
        return ""
    return f"asked for a callback: {mask_text(str(callback))}"


def _detail(base: str, structured: dict[str, object]) -> str:
    callback = _callback_detail(structured)
    if not callback:
        return base
    return f"{base}; {callback}" if base else callback


def _coverage_block(coverage: Coverage) -> list[str]:
    out = [f"Answers  : {coverage.basis} participants"]
    if coverage.caveat:
        out.append(f"NOTE     : {coverage.caveat}")
    out.append("")
    out.append("Who answered, and who did not:")
    rows = []
    for result in coverage.answered:
        rows.append(
            [
                result.label,
                result.phone_masked,
                "answered",
                result.status_label,
                _detail("", result.structured),
            ]
        )
    for result in coverage.refused:
        rows.append(
            [
                result.label,
                result.phone_masked,
                "declined to answer",
                result.status_label,
                _detail("", result.structured),
            ]
        )
    for result in coverage.unreached:
        rows.append(
            [
                result.label,
                result.phone_masked,
                "NOT REACHED",
                result.status_label,
                _detail(mask_text(result.error or ""), result.structured),
            ]
        )
    for result in coverage.shared_call:
        rows.append(
            [
                result.label,
                result.phone_masked,
                f"shares a call with {result.shares_call_with} - not counted separately",
                result.status_label,
                _detail("", result.structured),
            ]
        )
    for result in coverage.pending:
        rows.append(
            [
                result.label,
                result.phone_masked,
                "not called yet",
                result.status_label,
                _detail("", result.structured),
            ]
        )
    out.append(table(["Name", "Number", "Counts as", "Call status", "Detail"], rows))
    transcribed = coverage.transcribed
    if transcribed:
        out.append("")
        out.append(
            f"Transcripts available for {len(transcribed)} call(s): "
            + ", ".join(result.label for result in transcribed)
            + ". They are in the Markdown report - the categories above are the "
            "voice agent's reading of them."
        )
    everybody = (
        coverage.answered
        + coverage.refused
        + coverage.unreached
        + coverage.pending
        + coverage.shared_call
    )
    asked_for_callback = [r for r in everybody if r.structured.get("callback_requested")]
    if asked_for_callback:
        out.append("")
        out.append(
            f"{len(asked_for_callback)} asked for a callback: "
            + ", ".join(result.label for result in asked_for_callback)
            + ". This is not called back automatically - run with --retry to call them again."
        )
    return out


def _transcript_block(coverage: Coverage) -> list[str]:
    """The verbatim conversations, for checking the categories against.

    The voice agent interprets: a measured call turned "2. Yes, dissatisfied."
    into the category *dissatisfied* by itself, with a confidence score and
    three supporting quotes. That is useful, and it is also exactly why the
    wording has to stay readable underneath.
    """
    transcribed = coverage.transcribed
    if not transcribed:
        return []
    out = [
        "## What was actually said",
        "",
        "The results above are the voice agent's reading of these conversations. "
        "They are printed verbatim so that reading can be checked.",
        "",
    ]
    for result in transcribed:
        out += [f"### {result.label} ({result.status_label})", "", "```"]
        out += [mask_text(line) for line in result.transcript.splitlines()]
        out += ["```", ""]
    return out


def _callback_block(coverage: Coverage) -> list[str]:
    """R19: the Markdown table above has no Detail column, so a requested
    callback time gets its own section instead -- the same information the
    console report puts in the Detail column (render.py, ``_detail``)."""
    everybody = (
        coverage.answered
        + coverage.refused
        + coverage.unreached
        + coverage.pending
        + coverage.shared_call
    )
    asked = [(r, r.structured.get("callback_requested")) for r in everybody]
    asked = [(r, callback) for r, callback in asked if callback]
    if not asked:
        return []
    out = [
        "## Asked for a callback",
        "",
        "This is not called back automatically - run with `--retry` to call "
        "them again.",
        "",
    ]
    for result, callback in asked:
        out.append(f"- **{result.label}**: {mask_text(str(callback))}")
    out.append("")
    return out


def _slot_body(merge: SlotMerge) -> list[str]:
    out = [f"RESULT   : {merge.headline}", ""]
    out.append("Slot by slot (blank means the person was not asked or did not say):")
    rows = [
        [
            row.label,
            str(len(row.can)),
            _names(row.can),
            _names(row.cannot),
            _names(row.unknown),
        ]
        for row in merge.ranked
    ]
    out.append(table(["Slot", "Can", "Who can", "Who cannot", "Unclear"], rows))
    return out


def _choice_body(merge: ChoiceMerge) -> list[str]:
    out = [f"RESULT   : {merge.headline}", ""]
    rows = [
        [entry.option, str(entry.count), _names(entry.voters)]
        for entry in sorted(merge.tally, key=lambda item: -item.count)
    ]
    out.append(table(["Option", "Votes", "Who"], rows))
    out.append("")
    out.append(f"Abstained (reached, no preference): {_names(merge.abstained)}")
    if merge.other:
        out.append("")
        out.append("Answers outside the offered options - kept separate, not counted:")
        out.append(table(["Name", "Said"], [[name, mask_text(text)] for name, text in merge.other]))
    if merge.conditions:
        out.append("")
        out.append("Conditions attached to a vote - the tally does not carry these:")
        out.append(
            table(["Name", "Condition"], [[name, mask_text(text)] for name, text in merge.conditions])
        )
    if merge.reasons:
        out.append("")
        out.append("Reasons given for the choices:")
        out.append(table(["Name", "Reason"], [[name, mask_text(text)] for name, text in merge.reasons]))
    if merge.concerns:
        out.append("")
        out.append("Reservations and counterarguments:")
        out.append(table(["Name", "Concern"], [[name, mask_text(text)] for name, text in merge.concerns]))
    if merge.unclear:
        out.append("")
        out.append(f"Reached but no usable answer recorded: {_names(merge.unclear)}")
    return out


def _open_body(merge: OpenMerge) -> list[str]:
    out = [f"RESULT   : {merge.headline}", ""]
    if merge.tendencies:
        out.append(
            table(
                ["Tendency", "Count", "Who"],
                [[entry.stance, str(entry.count), _names(entry.people)] for entry in merge.tendencies],
            )
        )
        out.append("")
    rows = [
        [
            entry.name,
            entry.stance,
            mask_text(entry.answer),
            mask_text("; ".join(entry.reasons)),
            mask_text("; ".join(entry.concerns)),
            mask_text(entry.note),
        ]
        for entry in merge.entries
    ]
    out.append(table(["Name", "Tendency", "Answer", "Reasons", "Concerns", "Note"], rows))
    if merge.countervoices:
        out += ["", f"Countervoices: {_names(tuple(entry.name for entry in merge.countervoices))}"]
    return out


def render_result(merge: MergeResult) -> str:
    """The console report."""
    out = ["RESULT", "=" * 60]
    out.extend(_poll_header(merge.poll))
    out.append("")
    if isinstance(merge, SlotMerge):
        out.extend(_slot_body(merge))
    elif isinstance(merge, ChoiceMerge):
        out.extend(_choice_body(merge))
    else:
        out.extend(_open_body(merge))
    out.append("")
    out.extend(_coverage_block(merge.coverage))
    return "\n".join(out)


# --------------------------------------------------------------------------
# markdown export
# --------------------------------------------------------------------------


def _md_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return "_none_"
    head = "| " + " | ".join(headers) + " |"
    rule = "| " + " | ".join("---" for _ in headers) + " |"
    body = [
        "| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |" for row in rows
    ]
    return "\n".join([head, rule, *body])


def render_markdown(merge: MergeResult) -> str:
    """The shareable report. Same content as the console view."""
    poll = merge.poll
    coverage = merge.coverage
    out = [
        f"# {poll.question}",
        "",
        f"- **Asked by:** {poll.organizer}",
        f"- **Kind:** {poll.kind.value}",
        f"- **Answers:** {coverage.basis} participants",
        "",
        "## Result",
        "",
        merge.headline,
        "",
    ]
    if coverage.caveat:
        out += [f"> **{coverage.caveat}**", ""]

    if isinstance(merge, SlotMerge):
        out += [
            "### Slot by slot",
            "",
            _md_table(
                ["Slot", "Can", "Who can", "Who cannot", "Unclear"],
                [
                    [row.label, len(row.can), _names(row.can), _names(row.cannot), _names(row.unknown)]
                    for row in merge.ranked
                ],
            ),
            "",
        ]
    elif isinstance(merge, ChoiceMerge):
        out += [
            "### Tally",
            "",
            _md_table(
                ["Option", "Votes", "Who"],
                [
                    [entry.option, entry.count, _names(entry.voters)]
                    for entry in sorted(merge.tally, key=lambda item: -item.count)
                ],
            ),
            "",
            f"**Abstained (reached, no preference):** {_names(merge.abstained)}",
            "",
        ]
        if merge.other:
            out += [
                "### Answers outside the offered options",
                "",
                "These are not folded into the tally.",
                "",
                _md_table(["Name", "Said"], [[n, mask_text(t)] for n, t in merge.other]),
                "",
            ]
        if merge.conditions:
            out += [
                "### Conditions",
                "",
                _md_table(["Name", "Condition"], [[n, mask_text(t)] for n, t in merge.conditions]),
                "",
            ]
        if merge.reasons:
            out += [
                "### Reasons",
                "",
                _md_table(["Name", "Reason"], [[n, mask_text(t)] for n, t in merge.reasons]),
                "",
            ]
        if merge.concerns:
            out += [
                "### Reservations and counterarguments",
                "",
                _md_table(["Name", "Concern"], [[n, mask_text(t)] for n, t in merge.concerns]),
                "",
            ]
        if merge.unclear:
            out += [f"**Reached but no usable answer:** {_names(merge.unclear)}", ""]
    else:
        out += [
            "### Tendency",
            "",
            _md_table(
                ["Tendency", "Count", "Who"],
                [[e.stance, e.count, _names(e.people)] for e in merge.tendencies],
            ),
            "",
            "### Answers",
            "",
            _md_table(
                ["Name", "Tendency", "Answer", "Reasons", "Concerns", "Note"],
                [
                    [
                        e.name,
                        e.stance,
                        mask_text(e.answer),
                        mask_text("; ".join(e.reasons)),
                        mask_text("; ".join(e.concerns)),
                        mask_text(e.note),
                    ]
                    for e in merge.entries
                ],
            ),
            "",
        ]
        if merge.countervoices:
            out += [
                f"**Countervoices:** {_names(tuple(entry.name for entry in merge.countervoices))}",
                "",
            ]

    out += [
        "## Who answered, and who did not",
        "",
        _md_table(
            ["Name", "Number", "Counts as", "Call status"],
            [
                *[[r.label, r.phone_masked, "answered", r.status_label] for r in coverage.answered],
                *[
                    [r.label, r.phone_masked, "declined to answer", r.status_label]
                    for r in coverage.refused
                ],
                *[
                    [r.label, r.phone_masked, "**not reached**", r.status_label]
                    for r in coverage.unreached
                ],
                *[
                    [
                        r.label,
                        r.phone_masked,
                        f"**shares a call with {r.shares_call_with}** - not counted separately",
                        r.status_label,
                    ]
                    for r in coverage.shared_call
                ],
                *[
                    [r.label, r.phone_masked, "not called yet", r.status_label]
                    for r in coverage.pending
                ],
            ],
        ),
        "",
    ]

    out += _callback_block(coverage)
    out += _transcript_block(coverage)

    out += [
        "---",
        "",
        "_Phone numbers are masked. People who were not reached are listed with "
        "their call status and are never counted as indifferent._",
        "",
        "_Generated by Ringedingeding._",
        "",
    ]
    return "\n".join(out)
