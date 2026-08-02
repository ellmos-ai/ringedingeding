"""The core sample: one command that shows what this program is for.

`ringedingeding proof` exists for somebody who has no CALL-E account, no API
key and no intention of installing anything — a juror, a reviewer, a colleague.
It builds a seven-person scheduling round in a throwaway database, replays the
scripted answers of ``fixtures/weekend-hike.json``, and then **checks its own
result** instead of describing it.

Why a separate command when ``demo`` exists: ``demo`` shows that the machinery
runs. This shows that the machinery is *honest*, which is the harder and more
interesting claim. The four ways a merge can quietly lie —

* treating disagreement as a majority,
* reading silence about one option as a "no",
* folding "did not pick up", "line busy" and "declined" into one failure,
* dropping somebody who has no phone number at all —

are each provoked on purpose by the scenario and each asserted afterwards.

Nothing here can dial. There is no transport in this module other than the
fixture one, no network call, and the database is a temporary file that is
deleted again when the command returns.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .fixtures import Fixture, load_fixture, resolve_fixture
from .projects import ChannelKind, DateKind, ProjectStore
from .service import (
    COST_PER_CALL_USD,
    Board,
    RunMode,
    availability_round,
    board,
    create_project,
    make_transport,
    preview,
    resync_contact,
    run_round,
    set_invitees,
)
from .store import Store

__all__ = ["FIXTURE_NAME", "CATCH_UP_REF", "Check", "ProofResult", "run_proof"]

FIXTURE_NAME = "weekend-hike"

CATCH_UP_REF = "vera"
"""The person the address book cannot call at the start.

A fixture describes *calls*, so everybody in it has a number. Whether the
address book knows that number is a fact one layer up, and this is where that
layer is exercised: Vera is entered without one, is therefore never dialled,
and is added afterwards.
"""

FULL_NUMBER = re.compile(r"\+\d{6,}")
"""Anything that looks like an unmasked phone number in printed output."""


@dataclass(frozen=True)
class Check:
    """One assertion about the result, phrased so a reader can judge it."""

    name: str
    passed: bool
    detail: str

    @property
    def marker(self) -> str:
        return "ok  " if self.passed else "FAIL"


@dataclass(frozen=True)
class ProofResult:
    checks: tuple[Check, ...]
    lines: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed(self) -> tuple[Check, ...]:
        return tuple(check for check in self.checks if not check.passed)


def _names(people: Any) -> set[str]:
    return {person.name for person in people}


def _slot(view: Board, label: str):
    for slot in view.slots:
        if slot.slot.label == label:
            return slot
    raise KeyError(f"the scenario has no slot {label!r}")


def _headline(view: Board) -> str:
    merge = view.merge
    return merge.headline if merge is not None else ""


def run_proof(emit: Callable[[str], None] | None = None) -> ProofResult:
    """Build, run and check the scenario. Returns every line it printed.

    ``emit`` is where the text goes; the tests pass a collector instead of
    ``print`` so they can assert on the same output a juror sees rather than on
    a parallel code path.
    """
    lines: list[str] = []

    def out(text: str = "") -> None:
        lines.append(text)
        if emit is not None:
            emit(text)

    fixture = load_fixture(resolve_fixture(FIXTURE_NAME))

    with tempfile.TemporaryDirectory(prefix="ringedingeding-proof-") as workspace:
        store = Store(Path(workspace) / "proof.db")
        try:
            checks = _run(store, fixture, out, lines)
        finally:
            store.close()

    return ProofResult(checks=tuple(checks), lines=tuple(lines))


def _run(
    store: Store,
    fixture: Fixture,
    out: Callable[[str], None],
    printed: list[str],
) -> list[Check]:
    projects = ProjectStore(store)
    spec = fixture.poll
    checks: list[Check] = []

    out("RINGEDINGEDING — CORE SAMPLE")
    out("=" * 72)
    out("No account, no API key, no network, no telephone. The answers below are")
    out(f"scripted in ringedingeding/fixtures/{FIXTURE_NAME}.json and replayed.")
    out("")

    # -- 1. the guest list -------------------------------------------------
    project = create_project(
        projects,
        occasion="the hike this weekend",
        organizer=str(spec.get("organizer", "Lukas")),
        date_kind=DateKind.DAY_SLOTS,
        language=str(spec.get("language", "en")),
        region=str(spec.get("region", "US")),
        locale=str(spec.get("locale", "en-US")),
        fixture_name=fixture.name,
    )

    contact_ids: list[str] = []
    catch_up_contact_id = ""
    catch_up_number = ""
    for entry in fixture.participants:
        ref = str(entry.get("ref") or entry["name"]).strip().lower()
        if ref == CATCH_UP_REF:
            # Entered without a number on purpose — see CATCH_UP_REF.
            contact = projects.create_contact(name=str(entry["name"]))
            catch_up_contact_id = contact.id
            catch_up_number = str(entry["phone"])
        else:
            contact = projects.create_contact(
                name=str(entry["name"]), phone=str(entry["phone"])
            )
        contact_ids.append(contact.id)

    set_invitees(store, projects, project, contact_ids)
    projects.replace_slots(
        project,
        [{"label": str(label), "all_day": False} for label in spec.get("slots") or []],
    )

    out("STEP 1  Seven people are invited. Six of them have a phone number.")
    out("")
    for contact in projects.contacts():
        if contact.callable:
            out(f"        {contact.name:<8} {contact.phone_masked}")
        else:
            out(f"        {contact.name:<8} —            no number in the address book")
    out("")

    # -- 2. what would be asked -------------------------------------------
    poll = availability_round(store, projects, project)
    assert poll is not None
    store.set_poll_window(poll.id, [slot.label for slot in projects.slots(project.id)])
    store.set_poll_question(poll.id, str(spec.get("question")))
    poll = store.get_poll(poll.id)

    plan = preview(store, projects, project, poll)
    out("STEP 2  What would be asked, and what it would cost.")
    out("")
    out(f'        question : "{poll.question}"')
    out(f"        times    : {', '.join(poll.slots)}")
    out(
        f"        calls    : {plan.call_count}"
        f"  (${plan.cost_usd:.2f} at ${COST_PER_CALL_USD:.2f} per call,"
        f" {plan.serial_duration} one after another)"
    )
    out(f"        not called: {', '.join(c.name for c in plan.uncallable) or '—'}")
    out("")

    # -- 3. the calls ------------------------------------------------------
    out("STEP 3  The round runs. Scripted answers; nothing is dialled.")
    out("")

    def sink(event: str, **fields: Any) -> None:
        if event in ("dialing", "simulating"):
            out(f"        -> {fields.get('ref')} ({fields.get('phone')})")
        elif event == "outcome":
            out(f"        <- {fields.get('ref')}: {fields.get('status')}")

    transport = make_transport(RunMode.SCRIPT, project=project, fixture=fixture)
    with transport:
        run_round(store, projects, project, poll, transport, on_event=sink)
    out("")

    view = board(store, projects, project)
    first_headline = _headline(view)

    # -- 4. the board ------------------------------------------------------
    out("STEP 4  The result, with the five states kept apart.")
    out("")
    out(f"        {view.answered_count} of {view.total_count} invited people answered.")
    out("")
    for index, slot in enumerate(view.slots, start=1):
        out(f"        {index}. {slot.slot.label:<12} {slot.count} can")
        if slot.can:
            out(f"           can    : {', '.join(p.name for p in slot.can)}")
        if slot.cannot:
            out(f"           cannot : {', '.join(p.name for p in slot.cannot)}")
        if slot.unknown:
            out(
                f"           silent : {', '.join(p.name for p in slot.unknown)}"
                "   (said nothing about this one — not a no)"
            )
    out("")
    if view.unreached:
        out(
            "        not reached : "
            + ", ".join(f"{p.name} ({p.status.value})" for p in view.unreached)
        )
    if view.coverage.refused:
        out(
            "        declined    : "
            + ", ".join(p.name for p in view.coverage.refused)
            + "   (picked up, chose not to answer)"
        )
    if view.uncallable:
        out(
            "        no phone    : "
            + ", ".join(c.name for c in view.uncallable)
            + "   (never called — a number can be added)"
        )
    out("        None of the above is counted as agreement.")
    out("")
    out(f"        => {first_headline}")
    out("")

    sat_morning = _slot(view, "Sat 09-13")
    sat_afternoon = _slot(view, "Sat 14-18")
    sunday = _slot(view, "Sun 09-13")

    checks.append(
        Check(
            "disagreement stays visible",
            "Nora" in _names(sat_afternoon.can) and "Paul" in _names(sat_afternoon.cannot),
            "Sat 14-18: Nora can, Paul cannot — both are on the row, neither wins by count",
        )
    )
    checks.append(
        Check(
            "silence is not a no",
            "Rike" in _names(sat_afternoon.unknown)
            and "Rike" in _names(sunday.unknown)
            and "Rike" not in _names(sat_afternoon.cannot)
            and "Rike" not in _names(sunday.cannot),
            "Rike named only Sat 09-13; the other two are 'silent', not 'cannot'",
        )
    )
    statuses = {p.status.value for p in view.unreached}
    checks.append(
        Check(
            "not-reached is not one state",
            statuses == {"NO_ANSWER", "BUSY"} and len(view.coverage.refused) == 1,
            f"kept apart: {', '.join(sorted(statuses))}, and 'declined' separately from both",
        )
    )
    answered = view.answered_count
    checks.append(
        Check(
            "the denominator is carried",
            answered == 3 and view.total_count == 7 and f"all {answered}" in first_headline,
            f"the result reads '{first_headline}' — over {answered}, not over 7",
        )
    )
    checks.append(
        Check(
            "nobody without a number disappears",
            [c.name for c in view.uncallable] == ["Vera"],
            "Vera has no number, was never called, and is named in the result anyway",
        )
    )
    checks.append(
        Check(
            "no full phone number is printed",
            not FULL_NUMBER.search("\n".join(printed)),
            "the regular expression \\+\\d{6,} finds nothing in everything printed above",
        )
    )

    # -- 5. the catch-up ---------------------------------------------------
    out("STEP 5  Vera's number is added. The same round runs again.")
    out("")
    projects.set_channel(catch_up_contact_id, ChannelKind.PHONE, catch_up_number)
    resync_contact(store, projects, catch_up_contact_id)

    poll = store.get_poll(poll.id)
    second_plan = preview(store, projects, project, poll)
    out(
        f"        outstanding calls: {second_plan.call_count}"
        f"  ({', '.join(r.participant.name for r in second_plan.requests) or '—'})"
    )
    out(
        f"        already answered, not called again: "
        f"{', '.join(p.name for p in second_plan.skipped) or '—'}"
    )
    out("")

    transport = make_transport(RunMode.SCRIPT, project=project, fixture=fixture)
    with transport:
        run_round(store, projects, project, poll, transport, on_event=sink)
    out("")

    after = board(store, projects, project)
    second_headline = _headline(after)
    out(f"        {after.answered_count} of {after.total_count} invited people answered.")
    out(f"        => {second_headline}")
    out("")

    checks.append(
        Check(
            "the catch-up calls exactly one person",
            second_plan.call_count == 1
            and second_plan.requests[0].participant.name == "Vera"
            and len(second_plan.skipped) == 6,
            "one new call; the other six have an outcome and are not dialled again. "
            "Redialling Tara and Uwe is a separate decision (--retry), not a side effect",
        )
    )
    checks.append(
        Check(
            "the late answer changed the result",
            first_headline != second_headline
            and "Sat 09-13" in first_headline
            and "Sat 09-13" not in second_headline,
            "Vera cannot make Sat 09-13 — the slot that 'worked for everyone' no longer does",
        )
    )

    # -- 6. verdict --------------------------------------------------------
    out("STEP 6  What the run just proved about itself.")
    out("")
    for check in checks:
        out(f"        [{check.marker}] {check.name}")
        out(f"                 {check.detail}")
    out("")
    passed = sum(1 for check in checks if check.passed)
    out(f"        {passed} of {len(checks)} checks passed.")
    out("")
    out("This is the whole point of the tool: the person nobody could reach is not")
    out("a person without an opinion. Vera would have been silently outvoted by a")
    out("majority she was never asked to be part of.")
    out("")
    out("Nothing was dialled. No account was used. The database was temporary.")
    return checks
