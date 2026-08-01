"""Command line for the project layer — the same flow the browser drives.

Every command here is a thin wrapper around :mod:`ringedingeding.service`, in
the order of the questions:

    contact add → project new → dates → people → wording → plan → call →
    board → criteria → decide → invite

That ordering is not decoration. ``SKILL.md`` hands these commands to somebody
else's agent, and an agent that can only ask questions in the order a person
would ask them cannot get the flow wrong. The web interface walks the same
path with the same functions.

Nothing here can dial a telephone without ``--mode live`` **and** the same typed
confirmation the rest of the program insists on.
"""

from __future__ import annotations

import argparse
import threading
from typing import Any, Sequence

from .projects import ChannelKind, DateKind, ProjectStore, RoundKind
from .service import (
    COST_PER_CALL_USD,
    RunMode,
    availability_round,
    board,
    day_slot_specs,
    decide,
    default_invitation_text,
    fixture_for,
    invitation_round,
    make_transport,
    preview,
    resync_contact,
    run_round,
    seed_from_fixture,
    set_criteria,
    set_dates,
    set_invitees,
    set_wording,
    uncallable,
)
from .store import Store

__all__ = ["add_parsers"]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _out(text: str = "") -> None:
    print(text)


def _projects(store: Store) -> ProjectStore:
    return ProjectStore(store)


def _resolve_project(projects: ProjectStore, needle: str):
    """Accept a full id or a unique prefix — ids are long and typed by hand."""
    try:
        return projects.project(needle)
    except KeyError:
        pass
    matches = [p for p in projects.projects() if p.id.startswith(needle)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise KeyError(f"no project matching {needle!r}")
    raise ValueError(f"{needle!r} matches {len(matches)} projects; be more specific")


def _resolve_slot(projects: ProjectStore, project, needle: str) -> str:
    """Accept a slot id, a 1-based number, or the exact label."""
    slots = projects.slots(project.id)
    text = str(needle).strip()
    if text.isdigit():
        index = int(text) - 1
        if 0 <= index < len(slots):
            return slots[index].id
        raise ValueError(f"there is no candidate date number {text}")
    for slot in slots:
        if slot.id == text or slot.label == text:
            return slot.id
    raise ValueError(f"no candidate date matching {needle!r}")


def _resolve_contacts(projects: ProjectStore, needles: Sequence[str]) -> list[str]:
    """Accept contact ids or names. Names are what a person types."""
    contacts = projects.contacts()
    by_id = {contact.id: contact for contact in contacts}
    resolved: list[str] = []
    for needle in needles:
        text = str(needle).strip()
        if text in by_id:
            resolved.append(text)
            continue
        matches = [c for c in contacts if c.name.lower() == text.lower()]
        if not matches:
            matches = [c for c in contacts if text.lower() in c.name.lower()]
        if len(matches) == 1:
            resolved.append(matches[0].id)
        elif not matches:
            raise ValueError(f"no contact matching {needle!r}")
        else:
            names = ", ".join(c.name for c in matches)
            raise ValueError(f"{needle!r} matches several contacts: {names}")
    return resolved


def _time_range(text: str) -> tuple[str, str]:
    """``"18:00-21:00"`` -> ``("18:00", "21:00")``."""
    parts = str(text).replace("–", "-").split("-")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise argparse.ArgumentTypeError(
            f"cannot read time range {text!r}. Expected something like 18:00-21:00."
        )
    return parts[0].strip(), parts[1].strip()


# --------------------------------------------------------------------------
# contacts
# --------------------------------------------------------------------------


def cmd_contact_add(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    contact = projects.create_contact(
        name=args.name, phone=args.phone, email=args.email, note=args.note or ""
    )
    state = contact.phone_masked if contact.callable else "no phone — cannot be called"
    _out(f"added {contact.name}  [{contact.id}]  {state}")
    return 0


def cmd_contact_list(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    contacts = projects.contacts()
    if not contacts:
        _out("no contacts yet — add one with 'ringedingeding contact add'")
        return 0
    for contact in contacts:
        mark = " " if contact.callable else "!"
        _out(f"{mark} {contact.name:<24} {contact.phone_masked:<12} {contact.id}")
    missing = [c for c in contacts if not c.callable]
    if missing:
        _out("")
        _out(f"! {len(missing)} contact(s) have no phone number and will not be called.")
    return 0


def cmd_contact_phone(args: argparse.Namespace, store: Store) -> int:
    """Add a number afterwards — the call is then picked up on the next run."""
    projects = _projects(store)
    contact_id = _resolve_contacts(projects, [args.who])[0]
    projects.set_channel(contact_id, ChannelKind.PHONE, args.phone)
    contact = projects.contact(contact_id)
    touched = resync_contact(store, projects, contact_id)
    _out(f"{contact.name}: {contact.phone_masked}")
    if touched:
        names = ", ".join(project.occasion for project in touched)
        _out(f"added to {len(touched)} running round(s): {names}")
    _out("Run the round again to catch up on this call; nobody else is called twice.")
    return 0


# --------------------------------------------------------------------------
# the flow
# --------------------------------------------------------------------------


def cmd_project_new(args: argparse.Namespace, store: Store) -> int:
    from .service import create_project

    projects = _projects(store)
    project = create_project(
        projects,
        occasion=args.occasion,
        organizer=args.organizer,
        date_kind=args.date_kind,
        urgency=args.urgency or "",
        language=args.language,
        region=args.region,
        locale=args.locale,
    )
    _out(f"created project {project.id}")
    _out(f"next: ringedingeding project dates --project {project.id} --day YYYY-MM-DD --time 18:00-21:00")
    return 0


def cmd_project_list(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    items = projects.projects()
    if not items:
        _out("no projects yet")
        return 0
    for project in items:
        slots = len(projects.slots(project.id))
        people = len(projects.invitees(project.id))
        _out(f"{project.id}  [{project.state}] {slots} date(s), {people} people - {project.occasion}")
    return 0


def cmd_project_demo(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    project = seed_from_fixture(store, projects, args.fixture)
    _out(f"created demo project {project.id} from fixture {args.fixture!r}")
    _out(f"next: ringedingeding project call --project {project.id} --mode script")
    return 0


def cmd_project_dates(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    project = _resolve_project(projects, args.project)
    specs = day_slot_specs(
        project,
        days=args.day,
        default_times=[_time_range(value) for value in (args.time or [])],
        whole_day=args.whole_day,
    )
    if not specs:
        raise ValueError("that produces no candidate date at all")
    slots = set_dates(store, projects, project, specs)
    for index, slot in enumerate(slots, start=1):
        _out(f"{index:>2}. {slot.label}")
    _out("")
    _out(f"{len(slots)} candidate date(s).")
    return 0


def cmd_project_people(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    project = _resolve_project(projects, args.project)
    if args.all:
        chosen = [contact.id for contact in projects.contacts()]
    else:
        chosen = _resolve_contacts(projects, args.who or [])
    invitees = set_invitees(store, projects, project, chosen)
    for invitee in invitees:
        mark = " " if invitee.callable else "!"
        _out(f"{mark} {invitee.name}")
    blocked = uncallable(invitees)
    if blocked:
        _out("")
        _out(
            f"! {len(blocked)} of them have no phone number and are not called: "
            + ", ".join(contact.name for contact in blocked)
        )
        _out("  Add one with 'ringedingeding contact phone' and run the round again.")
    return 0


def cmd_project_wording(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    project = _resolve_project(projects, args.project)
    greeting, closing = set_wording(
        projects, project, greeting=args.greeting or [], closing=args.closing or []
    )
    _out(f"greeting: {greeting or '(none)'}")
    _out(f"closing : {closing or '(none)'}")
    _out("These sentences are spoken word for word.")
    return 0


def cmd_project_plan(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    project = _resolve_project(projects, args.project)
    poll = _poll_for(store, projects, project, args.round)
    view = preview(store, projects, project, poll, retry=args.retry)

    _out(f"Occasion : {project.occasion}")
    _out(f"Asking   : {poll.question}")
    _out(f"Round    : {poll.round_kind}")
    _out("")
    for request in view.requests:
        _out(f"  would call {request.participant.name} ({request.participant.phone_masked})")
    for contact in view.uncallable:
        _out(f"  NOT called {contact.name} - no phone number")
    if view.skipped:
        _out(f"  {len(view.skipped)} already answered, not called again")
    _out("")
    _out(
        f"{view.call_count} call(s), about ${view.cost_usd:.2f} if run live "
        f"(${COST_PER_CALL_USD:.2f} each), {view.serial_duration} one after another."
    )
    if args.show_task and view.task_text:
        _out("")
        _out("--- task text, verbatim ---")
        _out(view.task_text)
    return 0


def cmd_project_call(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    project = _resolve_project(projects, args.project)
    poll = _poll_for(store, projects, project, args.round)

    if args.mode == RunMode.LIVE:
        from .cli import confirm_live

        confirm_live(args)

    cancel = threading.Event()
    transport = make_transport(
        args.mode,
        project=project,
        fixture=fixture_for(project) if args.mode == RunMode.SCRIPT else None,
        confirmation=_confirmation_for(args),
        cancel=cancel,
    )

    def sink(event: str, **fields: Any) -> None:
        if event == "run_start":
            mode = "LIVE CALLS" if fields.get("live") else f"{args.mode} run"
            _out(f"[{mode}] {fields.get('count')} call(s)")
        elif event in ("dialing", "simulating"):
            _out(f"  -> {fields.get('ref')} ({fields.get('phone')})")
        elif event == "outcome":
            detail = f" - {fields['error']}" if fields.get("error") else ""
            _out(f"  <- {fields.get('ref')}: {fields.get('status')}{detail}")
        elif event == "rejected":
            _out(f"  !! {fields.get('ref')}: {fields.get('reason')}")
        elif event == "nothing_to_do":
            _out("  nothing to do - everybody already answered (use --retry)")

    with transport:
        run_round(
            store,
            projects,
            project,
            poll,
            transport,
            concurrency=max(1, args.concurrency),
            cancel=cancel,
            on_event=sink,
            retry=args.retry,
        )
    _out("")
    return cmd_project_board(args, store)


def cmd_project_board(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    project = _resolve_project(projects, args.project)
    view = board(store, projects, project)

    _out(f"# {project.occasion}")
    if view.simulated:
        _out("!! SIMULATED - these answers were invented locally, no call was made.")
    if view.poll is None:
        _out("No round has been run yet.")
        return 0

    _out(f"{view.answered_count} of {view.total_count} answered.")
    _out("")
    for index, slot in enumerate(view.slots, start=1):
        score = f"  [{slot.score_label} criteria]" if slot.criteria_total else ""
        mark = "*" if view.decision and view.decision.slot_id == slot.slot.id else " "
        _out(f"{mark}{index:>2}. {slot.slot.label:<28} {slot.count} can{score}")
        if slot.can:
            _out(f"       can   : {', '.join(p.name for p in slot.can)}")
        if slot.cannot:
            _out(f"       cannot: {', '.join(p.name for p in slot.cannot)}")
        if slot.unknown:
            _out(f"       silent: {', '.join(p.name for p in slot.unknown)} (not a no)")
    _out("")
    if view.unreached:
        _out(
            "not reached : "
            + ", ".join(f"{p.name} ({p.status.value})" for p in view.unreached)
        )
    if view.coverage.refused:
        _out("declined    : " + ", ".join(p.name for p in view.coverage.refused))
    if view.uncallable:
        _out(
            "no phone    : "
            + ", ".join(contact.name for contact in view.uncallable)
            + "  <- add a number and run again to catch up"
        )
    if view.unreached or view.uncallable or view.coverage.refused:
        _out("These are never counted as 'doesn't mind'.")
    if view.best and view.criteria and not view.criteria.is_empty:
        _out("")
        _out(f"best fit    : {view.best.slot.label} ({view.best.score_label} criteria)")
    return 0


def cmd_project_criteria(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    project = _resolve_project(projects, args.project)
    favourite = _resolve_slot(projects, project, args.favourite) if args.favourite else None
    must = _resolve_contacts(projects, args.must or [])
    set_criteria(
        projects, project, favourite_slot_id=favourite, must_have=must, min_count=args.count
    )
    return cmd_project_board(args, store)


def cmd_project_decide(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    project = _resolve_project(projects, args.project)
    slot_id = _resolve_slot(projects, project, args.slot)
    decide(projects, project, slot_id, args.note or "")
    slot = next(s for s in projects.slots(project.id) if s.id == slot_id)
    _out(f"decided: {slot.label}")
    _out(f"next: ringedingeding project invite --project {project.id}")
    return 0


def cmd_project_invite(args: argparse.Namespace, store: Store) -> int:
    projects = _projects(store)
    project = _resolve_project(projects, args.project)
    decision = projects.decision(project.id)
    if decision is None:
        raise ValueError("no date has been decided yet — run 'project decide' first")
    slot = next((s for s in projects.slots(project.id) if s.id == decision.slot_id), None)

    if args.show:
        existing = invitation_round(store, projects, project, create=False)
        _out(existing.question if existing else default_invitation_text(project, slot))
        return 0

    poll = invitation_round(store, projects, project, text=args.text)
    _out(f"invitation round ready: {poll.id}")
    _out(f'  "{poll.question}"')
    _out("")
    _out(
        f"next: ringedingeding project call --project {project.id} "
        "--round invitation --mode rehearsal"
    )
    return 0


def _poll_for(store: Store, projects: ProjectStore, project, round_kind: str):
    if round_kind == RoundKind.INVITATION:
        poll = invitation_round(store, projects, project, create=False)
        if poll is None:
            raise ValueError(
                "there is no invitation round yet — run 'project invite' first"
            )
        return poll
    return availability_round(store, projects, project)


def _confirmation_for(args: argparse.Namespace) -> str:
    """The typed phrase, once :func:`ringedingeding.cli.confirm_live` is happy.

    ``confirm_live`` has already done the asking by this point; repeating the
    phrase here keeps :func:`make_transport` the single place that decides
    whether a live transport may exist at all.
    """
    from .safety import LIVE_CONFIRMATION_PHRASE

    return LIVE_CONFIRMATION_PHRASE if getattr(args, "mode", "") == RunMode.LIVE else ""


# --------------------------------------------------------------------------
# parsers
# --------------------------------------------------------------------------


def _add_project_selector(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", required=True, help="project id (a prefix is enough)")


def add_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register ``contact`` and ``project`` under an existing CLI."""

    # -- contacts ----------------------------------------------------------
    contact = subparsers.add_parser("contact", help="the address book")
    contact_sub = contact.add_subparsers(dest="contact_command", required=True)

    add = contact_sub.add_parser("add", help="add a contact")
    add.add_argument("--name", required=True)
    add.add_argument(
        "--phone", help="E.164: a '+', the country code, then the number without its leading 0"
    )
    add.add_argument("--email", help="stored for stage 2; not used for calling yet")
    add.add_argument("--note")
    add.set_defaults(func=cmd_contact_add)

    listing = contact_sub.add_parser("list", help="list contacts")
    listing.set_defaults(func=cmd_contact_list)

    phone = contact_sub.add_parser("phone", help="add or replace a phone number")
    phone.add_argument("who", help="contact id or name")
    phone.add_argument("phone")
    phone.set_defaults(func=cmd_contact_phone)

    # -- projects ----------------------------------------------------------
    project = subparsers.add_parser(
        "project", help="find one date with several people (the full flow)"
    )
    project_sub = project.add_subparsers(dest="project_command", required=True)

    new = project_sub.add_parser("new", help="1. what is it about?")
    new.add_argument("--occasion", required=True, help="'Familienessen am Wochenende'")
    new.add_argument("--organizer", required=True, help="whose name the call is made in")
    new.add_argument(
        "--date-kind", default=DateKind.DAY_SLOTS, choices=list(DateKind.IMPLEMENTED)
    )
    new.add_argument(
        "--urgency",
        help="how pressing it is, in the organizer's words ('wirklich dringend'). "
             "Changes the tone of the call, never the flow.",
    )
    new.add_argument("--language", default="de")
    new.add_argument("--region", default="DE")
    new.add_argument("--locale", default="de-DE")
    new.set_defaults(func=cmd_project_new)

    listing = project_sub.add_parser("list", help="list projects")
    listing.set_defaults(func=cmd_project_list)

    demo = project_sub.add_parser("demo", help="build a whole project from a fixture")
    demo.add_argument("--fixture", required=True)
    demo.set_defaults(func=cmd_project_demo)

    dates = project_sub.add_parser("dates", help="2. which days, which times?")
    _add_project_selector(dates)
    dates.add_argument("--day", action="append", required=True, metavar="YYYY-MM-DD")
    dates.add_argument(
        "--time", action="append", metavar="HH:MM-HH:MM",
        help="standard time applied to every day; repeat for several slots",
    )
    dates.add_argument("--whole-day", action="store_true", help="no time of day")
    dates.set_defaults(func=cmd_project_dates)

    people = project_sub.add_parser("people", help="3. whom do you want to invite?")
    _add_project_selector(people)
    people.add_argument("who", nargs="*", help="contact ids or names")
    people.add_argument("--all", action="store_true", help="everybody in the address book")
    people.set_defaults(func=cmd_project_people)

    wording = project_sub.add_parser("wording", help="4. greeting and closing words")
    _add_project_selector(wording)
    wording.add_argument("--greeting", action="append")
    wording.add_argument("--closing", action="append")
    wording.set_defaults(func=cmd_project_wording)

    plan = project_sub.add_parser("plan", help="5. what would happen (nothing is dialed)")
    _add_project_selector(plan)
    plan.add_argument("--round", default=RoundKind.AVAILABILITY,
                      choices=[RoundKind.AVAILABILITY, RoundKind.INVITATION])
    plan.add_argument("--retry", action="store_true")
    plan.add_argument("--show-task", action="store_true", help="print the order text")
    plan.set_defaults(func=cmd_project_plan)

    call = project_sub.add_parser("call", help="6. place the calls")
    _add_project_selector(call)
    call.add_argument(
        "--mode", default=RunMode.REHEARSAL,
        choices=[RunMode.SCRIPT, RunMode.REHEARSAL, RunMode.LIVE],
        help="script = replay a fixture, rehearsal = invent answers locally, "
             "live = real telephones (needs the typed confirmation)",
    )
    call.add_argument("--round", default=RoundKind.AVAILABILITY,
                      choices=[RoundKind.AVAILABILITY, RoundKind.INVITATION])
    call.add_argument("--concurrency", type=int, default=1)
    call.add_argument("--retry", action="store_true")
    call.add_argument("--yes", action="store_true", help="see 'run --yes'")
    call.set_defaults(func=cmd_project_call)

    board_parser = project_sub.add_parser("board", help="7. who can when")
    _add_project_selector(board_parser)
    board_parser.set_defaults(func=cmd_project_board)

    criteria = project_sub.add_parser("criteria", help="8. what matters to you")
    _add_project_selector(criteria)
    criteria.add_argument("--favourite", help="candidate date number, id or label")
    criteria.add_argument("--must", action="append", help="contact who has to be there")
    criteria.add_argument("--count", type=int, help="how many people are enough")
    criteria.set_defaults(func=cmd_project_criteria)

    decide_parser = project_sub.add_parser("decide", help="9. settle on a date")
    _add_project_selector(decide_parser)
    decide_parser.add_argument("--slot", required=True, help="number, id or label")
    decide_parser.add_argument("--note")
    decide_parser.set_defaults(func=cmd_project_decide)

    invite = project_sub.add_parser("invite", help="10. tell everybody")
    _add_project_selector(invite)
    invite.add_argument("--text", help="override the default announcement")
    invite.add_argument("--show", action="store_true", help="only print the text")
    invite.set_defaults(func=cmd_project_invite)
