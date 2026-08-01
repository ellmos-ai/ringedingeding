"""Command line interface.

The default of every command is the dry run. ``--live`` is the only way to
reach a telephone, and it additionally requires a typed confirmation — see
:func:`confirm_live`.

Exit codes
----------
0   success
1   an error
2   refused: sensitive content
3   refused: live calling blocked or not confirmed
130 interrupted by the user (Ctrl-C), state on disk is consistent
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .activity import ActivityLine
from .fixtures import (
    Fixture,
    FixtureError,
    bundled_fixtures,
    load_fixture,
    placeholder_numbers,
    resolve_fixture,
)
from .merge import merge_poll
from .models import Poll, PollKind
from .phone import InvalidPhoneNumber
from .render import render_markdown, render_plan, render_result
from .runner import build_requests, run_poll
from .safety import (
    LIVE_CONFIRMATION_PHRASE,
    LiveCallBlocked,
    SensitiveContent,
    assert_question_allowed,
)
from .store import DEFAULT_DB_PATH, Store
from .timings import LEAD_SECONDS, estimate_seconds, format_duration
from .transports.base import CallTransport
from .transports.fixture import FixtureTransport

__all__ = ["main", "build_parser"]

COST_PER_CALL_USD = 0.05
"""Documented CALL-E price: per call, not per minute."""

LIVE_ACK_ENV = "RINGEDINGEDING_LIVE_CONFIRM"
DATA_REGION_NOTE = (
    "Everything in the call instructions leaves this machine and is processed by "
    "CALL-E / AiRudder in Singapore."
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_SENSITIVE = 2
EXIT_LIVE_BLOCKED = 3
EXIT_INTERRUPTED = 130


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def _out(text: str = "") -> None:
    print(text)


def _err(text: str) -> None:
    print(text, file=sys.stderr)


def _configure_stdout() -> None:
    """Make non-ASCII output survive a legacy Windows console."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # pragma: no cover - platform dependent
                pass


def parse_participant(spec: str) -> tuple[str, str]:
    """Parse ``"Anna = +15555550100"`` into ``("Anna", "+15555550100")``."""
    text = spec.strip()
    index = text.rfind("+")
    if index <= 0:
        raise argparse.ArgumentTypeError(
            f"cannot read participant {spec!r}. Expected 'Name=+E164', "
            "for example 'Anna=+15555550100'."
        )
    name = text[:index].rstrip(" \t,;:=")
    phone = text[index:].strip()
    if not name:
        raise argparse.ArgumentTypeError(f"participant {spec!r} has no name")
    return name, phone


def _event_printer(verbose: bool = True):
    def sink(event: str, **fields: Any) -> None:
        if not verbose:
            return
        if event == "run_start":
            mode = "LIVE CALLS" if fields.get("live") else "dry run"
            _out(
                f"[{mode}] transport={fields.get('transport')} "
                f"calls={fields.get('count')} concurrency={fields.get('concurrency')}"
            )
        elif event in ("dialing", "simulating"):
            verb = "dialing " if event == "dialing" else "would call"
            _out(f"  {verb} {fields.get('ref')} ({fields.get('phone')})")
        elif event == "outcome":
            detail = f" - {fields['error']}" if fields.get("error") else ""
            _out(f"  <- {fields.get('ref')}: {fields.get('status')}{detail}")
        elif event == "rejected":
            _out(f"  !! {fields.get('ref')} not called: {fields.get('reason')}")
        elif event == "aborted":
            _out(
                f"  aborted: {fields.get('placed')} finished, "
                f"{fields.get('remaining')} never started"
            )
        elif event == "nothing_to_do":
            _out("  nothing to do - every participant already has an answer (use --retry)")

    return sink


def _activity_printer(verbose: bool = True):
    """Print the conversation while it happens.

    This exists because ``status`` is useless as a progress indicator — it was
    measured sitting on ``PREPARING`` while both sides were already talking.
    Without these lines a live run looks frozen for a minute and a half.
    """

    def sink(line: ActivityLine) -> None:
        if verbose:
            _out(f"     {line.display()}")

    return sink


def _install_sigint(cancel: threading.Event) -> None:
    """First Ctrl-C stops new calls, second one gives up immediately."""
    state = {"count": 0}

    def handler(signum: int, frame: Any) -> None:
        state["count"] += 1
        if state["count"] == 1:
            cancel.set()
            _err(
                "\nInterrupted. No new calls will be started; calls already in "
                "progress are allowed to finish. Press Ctrl-C again to give up now."
            )
        else:
            _err("\nGiving up. Answers already received are saved.")
            raise KeyboardInterrupt

    try:
        signal.signal(signal.SIGINT, handler)
    except ValueError:  # pragma: no cover - not on the main thread
        pass


# --------------------------------------------------------------------------
# poll construction
# --------------------------------------------------------------------------


def fixture_poll_id(fixture: Fixture) -> str:
    """Deterministic id so re-running a fixture reuses the same poll."""
    return f"poll_fx_{fixture.name}"


def ensure_fixture_poll(store: Store, fixture: Fixture, *, fresh: bool = False) -> Poll:
    """Create (or reuse) the poll described by a fixture."""
    poll_id = fixture_poll_id(fixture)
    try:
        poll = store.get_poll(poll_id)
        if fresh:
            store.clear_answers(poll.id)
        return poll
    except KeyError:
        pass

    spec = fixture.poll
    assert_question_allowed(
        str(spec.get("question", "")),
        " ".join(str(option) for option in spec.get("options") or []),
    )
    poll = store.create_poll(
        poll_id=poll_id,
        question=str(spec["question"]),
        kind=PollKind.parse(spec.get("kind", "open")),
        organizer=str(spec.get("organizer", "the organizer")),
        language=str(spec.get("language", "en")),
        region=str(spec.get("region", "US")),
        locale=str(spec.get("locale", "en-US")),
        options=[str(option) for option in spec.get("options") or []],
        slots=[str(slot) for slot in spec.get("slots") or []],
    )
    for name, phone, ref in fixture.people:
        store.add_participant(poll.id, name=name, phone=phone, ref=ref)
    return poll


def _load_poll(store: Store, args: argparse.Namespace) -> tuple[Poll, Fixture | None]:
    """Resolve ``--poll`` or ``--fixture`` into a stored poll."""
    if getattr(args, "fixture", None):
        fixture = load_fixture(resolve_fixture(args.fixture))
        poll = ensure_fixture_poll(store, fixture, fresh=getattr(args, "fresh", False))
        return poll, fixture
    poll_id = getattr(args, "poll", None)
    if not poll_id:
        raise ValueError("give either --poll <id> or --fixture <name>")
    return store.get_poll(poll_id), None


def _transport_for(
    args: argparse.Namespace,
    fixture: Fixture | None,
    cancel: threading.Event,
) -> CallTransport:
    """Pick a transport. Live is only reachable through the confirmation gate."""
    if not getattr(args, "live", False):
        if fixture is None:
            raise ValueError(
                "a dry run needs scripted answers: pass --fixture <name>, or "
                "pass --live to place real calls. A poll of real people cannot "
                "be simulated - there is nothing to simulate it from."
            )
        return FixtureTransport(
            fixture.outcomes, latency_seconds=getattr(args, "simulate_latency", 0.0)
        )

    # ---- from here on real telephones are involved ----
    from .transports.calle import CalleBatchTransport, CalleTransport

    confirm_live(args)
    transport_class = CalleTransport if getattr(args, "serial", False) else CalleBatchTransport
    return transport_class(
        live_confirmed=True,
        cancel=cancel,
        on_activity=_activity_printer(not getattr(args, "quiet", False)),
    )


def confirm_live(args: argparse.Namespace) -> None:
    """Explicit intent gate. Raises :class:`LiveCallBlocked` when not confirmed."""
    if os.environ.get(LIVE_ACK_ENV, "").strip() == LIVE_CONFIRMATION_PHRASE:
        if not getattr(args, "yes", False):
            raise LiveCallBlocked(
                f"{LIVE_ACK_ENV} is set, but --yes was not passed. "
                "Both are required for an unattended live run."
            )
        _out(f"Live calling confirmed via {LIVE_ACK_ENV} and --yes.")
        return

    if getattr(args, "yes", False):
        raise LiveCallBlocked(
            f"--yes only works together with {LIVE_ACK_ENV}={LIVE_CONFIRMATION_PHRASE!r} "
            "in the environment. There is no silent live mode."
        )
    if not sys.stdin.isatty():
        raise LiveCallBlocked(
            "Live calling needs a confirmation, but this is not an interactive "
            f"terminal. For unattended runs set {LIVE_ACK_ENV}="
            f"{LIVE_CONFIRMATION_PHRASE!r} and pass --yes."
        )

    _out("")
    _out("About to place REAL phone calls to REAL people.")
    _out(f"  * {DATA_REGION_NOTE}")
    _out(f"  * Cost is about ${COST_PER_CALL_USD:.2f} per call.")
    _out("  * Everyone you call should know beforehand that this may happen.")
    _out("")
    try:
        typed = input(f"Type {LIVE_CONFIRMATION_PHRASE!r} to continue: ").strip()
    except EOFError:
        raise LiveCallBlocked("no confirmation received") from None
    if typed != LIVE_CONFIRMATION_PHRASE:
        raise LiveCallBlocked("confirmation did not match - nothing was dialed")


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def cmd_fixtures(args: argparse.Namespace, store: Store) -> int:
    fixtures = bundled_fixtures()
    if not fixtures:
        _out("no bundled fixtures found")
        return EXIT_OK
    for name, path in fixtures.items():
        try:
            fixture = load_fixture(path)
        except FixtureError as error:
            _out(f"{name}: BROKEN - {error}")
            continue
        _out(f"{name}  [{fixture.kind.value}, {len(fixture.participants)} people]")
        if fixture.description:
            _out(f"    {fixture.description}")
    return EXIT_OK


def cmd_create(args: argparse.Namespace, store: Store) -> int:
    assert_question_allowed(args.question, " ".join(args.option or []))
    poll = store.create_poll(
        question=args.question,
        kind=args.kind,
        organizer=args.organizer,
        language=args.language,
        region=args.region,
        locale=args.locale,
        options=args.option or [],
        slots=args.slot or [],
    )
    for spec in args.participant or []:
        name, phone = parse_participant(spec)
        store.add_participant(poll.id, name=name, phone=phone)
    people = store.participants(poll.id)
    _out(f"created poll {poll.id} with {len(people)} participant(s)")
    _out(f"next: ringedingeding plan --poll {poll.id}")
    return EXIT_OK


def cmd_list(args: argparse.Namespace, store: Store) -> int:
    polls = store.list_polls()
    if not polls:
        _out("no polls yet")
        return EXIT_OK
    for poll in polls:
        answers = store.answers(poll.id)
        people = store.participants(poll.id)
        _out(
            f"{poll.id}  [{poll.kind.value}] {len(answers)}/{len(people)} answered  "
            f"- {poll.question}"
        )
    return EXIT_OK


def cmd_plan(args: argparse.Namespace, store: Store) -> int:
    poll, _fixture = _load_poll(store, args)
    participants = store.participants(poll.id)
    requests, skipped, rejected = build_requests(
        poll,
        participants,
        existing=store.answers(poll.id),
        retry=args.retry,
        include_names=not args.no_names,
    )
    _out(render_plan(poll, requests, show_payload=args.show_payload))
    if skipped:
        _out(f"Already answered, would not be called again: {len(skipped)}")
    for participant, reason in rejected:
        _out(f"Would NOT be called - {participant.ref}: {reason}")
    _out("")
    _out(f"Estimated cost if run live: ${len(requests) * COST_PER_CALL_USD:.2f} "
         f"({len(requests)} x ${COST_PER_CALL_USD:.2f})")
    _out(_time_estimate(len(requests)))
    _out(DATA_REGION_NOTE)
    return EXIT_OK


def _time_estimate(calls: int) -> str:
    """How long a live run would take — and how uncertain that is.

    Worth printing next to the price because the two behave differently: the
    cost is per call however they are placed, the time is not. About 40 seconds
    of every call is dialling and connecting, measured and independent of how
    long anybody talks, so six people take six times that serially and once
    that in parallel — *if* parallel calls are permitted at all, which has
    never been tested.
    """
    if calls <= 0:
        return "Estimated time if run live: nothing to do."
    serial = format_duration(estimate_seconds(calls, concurrency=1))
    parallel = format_duration(estimate_seconds(calls, concurrency=calls))
    if calls == 1:
        return f"Estimated time if run live: {serial} (~{LEAD_SECONDS:.0f} s of it is dialling)."
    return (
        f"Estimated time if run live: {serial} one after another, {parallel} if "
        f"they run at once. Roughly {LEAD_SECONDS:.0f} s per call is dialling "
        "before a word is spoken. Whether CALL-E permits calls at once is "
        "UNVERIFIED - the serial figure is the one to trust."
    )


def _refuse_placeholder_numbers(store: Store, poll: Poll) -> None:
    """Never dial an example number, whatever the operator typed."""
    forbidden = placeholder_numbers()
    hits = [
        participant
        for participant in store.participants(poll.id)
        if participant.phone_e164 in forbidden
    ]
    if hits:
        listed = ", ".join(f"{p.ref} ({p.phone_masked})" for p in hits)
        raise LiveCallBlocked(
            f"This poll uses example numbers from a bundled fixture: {listed}. "
            "They are placeholders and are never dialed. Create your own poll "
            "with 'ringedingeding create' and the real numbers of people who "
            "know they will be called."
        )


def cmd_run(args: argparse.Namespace, store: Store) -> int:
    poll, fixture = _load_poll(store, args)
    if getattr(args, "live", False):
        _refuse_placeholder_numbers(store, poll)

    cancel = threading.Event()
    _install_sigint(cancel)

    transport = _transport_for(args, fixture, cancel)
    with transport:
        report = run_poll(
            store,
            poll,
            transport,
            concurrency=max(1, args.concurrency),
            cancel=cancel,
            on_event=_event_printer(not args.quiet),
            retry=args.retry,
            include_names=not args.no_names,
        )

    _out("")
    merge = merge_poll(poll, store.participants(poll.id), store.answers(poll.id))
    _out(render_result(merge))

    if args.markdown:
        path = Path(args.markdown)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(merge), encoding="utf-8")
        _out("")
        _out(f"Markdown report written to {path}")

    return EXIT_INTERRUPTED if report.aborted else EXIT_OK


def cmd_report(args: argparse.Namespace, store: Store) -> int:
    poll, _fixture = _load_poll(store, args)
    merge = merge_poll(poll, store.participants(poll.id), store.answers(poll.id))
    _out(render_result(merge))
    if args.markdown:
        path = Path(args.markdown)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(merge), encoding="utf-8")
        _out("")
        _out(f"Markdown report written to {path}")
    return EXIT_OK


def cmd_demo(args: argparse.Namespace, store: Store) -> int:
    """Run every bundled fixture end to end. No account, no network."""
    fixtures = bundled_fixtures()
    if not fixtures:
        _err("no bundled fixtures to demo")
        return EXIT_ERROR

    out_dir = Path(args.out)
    for index, (name, path) in enumerate(fixtures.items(), start=1):
        fixture = load_fixture(path)
        poll = ensure_fixture_poll(store, fixture, fresh=True)
        participants = store.participants(poll.id)

        _out("")
        _out("#" * 70)
        _out(f"# {index}/{len(fixtures)}  {fixture.name}")
        if fixture.description:
            _out(f"# {fixture.description}")
        _out("#" * 70)
        _out("")

        requests, _skipped, _rejected = build_requests(poll, participants)
        _out(render_plan(poll, requests, show_payload=args.show_payload))

        transport = FixtureTransport(fixture.outcomes)
        with transport:
            run_poll(store, poll, transport, on_event=_event_printer(not args.quiet))

        _out("")
        merge = merge_poll(poll, participants, store.answers(poll.id))
        _out(render_result(merge))

        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / f"{fixture.name}.md"
        report_path.write_text(render_markdown(merge), encoding="utf-8")
        _out("")
        _out(f"Markdown report written to {report_path}")

    _out("")
    _out("Dry run complete. No call was placed and no account was used.")
    return EXIT_OK


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------


def _add_selector(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--poll", help="id of a stored poll")
    parser.add_argument("--fixture", help="bundled fixture name or path to a fixture file")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ringedingeding",
        description="Ask one question to several people by phone, get one answer. "
        "Runs as a dry run against fixtures unless --live is given.",
    )
    parser.add_argument("--version", action="version", version=f"ringedingeding {__version__}")
    parser.add_argument(
        "--db", default=str(DEFAULT_DB_PATH), help=f"SQLite file (default: {DEFAULT_DB_PATH})"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="run every bundled fixture end to end (dry run)")
    demo.add_argument("--out", default="out", help="directory for the Markdown reports")
    demo.add_argument("--show-payload", action="store_true", help="also print the request body")
    demo.add_argument("--quiet", action="store_true")
    demo.set_defaults(func=cmd_demo)

    fixtures = subparsers.add_parser("fixtures", help="list the bundled fixtures")
    fixtures.set_defaults(func=cmd_fixtures)

    create = subparsers.add_parser("create", help="create a poll")
    create.add_argument("--question", required=True)
    create.add_argument("--kind", required=True, choices=[kind.value for kind in PollKind])
    create.add_argument("--organizer", required=True, help="whose name the call is made in")
    create.add_argument("--participant", action="append", metavar="NAME=+E164")
    create.add_argument("--option", action="append", help="answer option (choice polls)")
    create.add_argument("--slot", action="append", help="proposed time slot (slot polls)")
    create.add_argument("--language", default="en")
    create.add_argument("--region", default="US")
    create.add_argument("--locale", default="en-US")
    create.set_defaults(func=cmd_create)

    listing = subparsers.add_parser("list", help="list stored polls")
    listing.set_defaults(func=cmd_list)

    plan = subparsers.add_parser("plan", help="show who would be called, and with what")
    _add_selector(plan)
    plan.add_argument("--retry", action="store_true", help="include already answered participants")
    plan.add_argument("--no-names", action="store_true", help="do not send any name at all")
    plan.add_argument("--show-payload", action="store_true")
    plan.add_argument("--fresh", action="store_true", help="drop earlier answers of this fixture")
    plan.set_defaults(func=cmd_plan)

    run = subparsers.add_parser("run", help="place the calls (dry run unless --live)")
    _add_selector(run)
    run.add_argument(
        "--live",
        action="store_true",
        help="place REAL calls. Requires a typed confirmation on top of this flag.",
    )
    run.add_argument(
        "--yes",
        action="store_true",
        help=f"skip the prompt; only works with {LIVE_ACK_ENV} set in the environment",
    )
    run.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="how many calls at a time (1 = serial). Parallel behaviour of CALL-E is unverified.",
    )
    run.add_argument(
        "--serial",
        action="store_true",
        help="live only: one API request per person instead of one batch request",
    )
    run.add_argument("--retry", action="store_true", help="call people who already have an answer")
    run.add_argument("--no-names", action="store_true", help="do not send any name at all")
    run.add_argument("--fresh", action="store_true", help="drop earlier answers of this fixture")
    run.add_argument("--markdown", help="also write the report to this path")
    run.add_argument(
        "--simulate-latency",
        type=float,
        default=0.0,
        help="dry run only: pause this many seconds per simulated call",
    )
    run.add_argument("--quiet", action="store_true")
    run.set_defaults(func=cmd_run)

    report = subparsers.add_parser("report", help="show the merged result of a poll")
    _add_selector(report)
    report.add_argument("--markdown", help="write the report to this path")
    report.set_defaults(func=cmd_report)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)

    store = Store(args.db)
    try:
        return int(args.func(args, store))
    except SensitiveContent as error:
        _err(f"Refused: {error}")
        return EXIT_SENSITIVE
    except LiveCallBlocked as error:
        _err(f"Live calling blocked: {error}")
        return EXIT_LIVE_BLOCKED
    except (FixtureError, InvalidPhoneNumber, ValueError) as error:
        _err(f"Error: {error}")
        return EXIT_ERROR
    except KeyError as error:
        _err(f"Not found: {error}")
        return EXIT_ERROR
    except KeyboardInterrupt:
        _err("Interrupted. Answers already received are saved.")
        return EXIT_INTERRUPTED
    finally:
        store.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
