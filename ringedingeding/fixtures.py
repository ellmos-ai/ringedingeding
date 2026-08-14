"""Loading scripted polls for the dry run.

A fixture is one JSON file holding three things: the poll definition, the people
to call, and what each of them said. It is the whole reason this project can be
reviewed, tested and demonstrated without a CALL-E account.

Every participant needs an entry in ``outcomes``. A missing entry is an error,
not a default — a dry run that silently invents "no answer" for the people the
author forgot would be worse than one that fails.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import PollKind

__all__ = [
    "FIXTURE_DIR",
    "Fixture",
    "bundled_fixtures",
    "load_fixture",
    "placeholder_numbers",
    "resolve_fixture",
]

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class FixtureError(ValueError):
    """The fixture file is missing something or contradicts itself."""


@dataclass(frozen=True)
class Fixture:
    name: str
    description: str
    poll: dict[str, Any]
    participants: tuple[dict[str, str], ...]
    outcomes: dict[str, dict[str, Any]]
    source: Path | None = None

    @property
    def kind(self) -> PollKind:
        return PollKind.parse(self.poll.get("kind", "open"))

    @property
    def people(self) -> list[tuple[str, str, str | None]]:
        """``(name, phone, ref)`` triples in file order."""
        return [
            (str(entry["name"]), str(entry["phone"]), entry.get("ref"))
            for entry in self.participants
        ]


def load_fixture(path: str | Path) -> Fixture:
    """Read and check one fixture file."""
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FixtureError(f"fixture not found: {source}") from None
    except json.JSONDecodeError as error:
        raise FixtureError(f"fixture {source} is not valid JSON: {error}") from None

    if not isinstance(raw, dict):
        raise FixtureError(f"fixture {source} must contain a JSON object")

    poll = raw.get("poll")
    if not isinstance(poll, dict) or not poll.get("question"):
        raise FixtureError(f"fixture {source} has no usable 'poll.question'")

    participants = raw.get("participants")
    if not isinstance(participants, list) or not participants:
        raise FixtureError(f"fixture {source} has no participants")
    for entry in participants:
        if not isinstance(entry, dict) or "name" not in entry or "phone" not in entry:
            raise FixtureError(f"fixture {source}: every participant needs 'name' and 'phone'")

    outcomes = raw.get("outcomes")
    if not isinstance(outcomes, dict):
        raise FixtureError(f"fixture {source} has no 'outcomes' object")

    refs = {str(entry.get("ref") or entry["name"]).strip().lower() for entry in participants}
    missing = sorted(ref for ref in refs if ref not in outcomes)
    if missing:
        raise FixtureError(
            f"fixture {source}: no scripted outcome for {', '.join(missing)}. "
            "Add one (use call_status NO_ANSWER if that is what you meant)."
        )
    unknown = sorted(set(outcomes) - refs)
    if unknown:
        raise FixtureError(
            f"fixture {source}: outcomes for unknown participants: {', '.join(unknown)}"
        )

    return Fixture(
        name=str(raw.get("name") or source.stem),
        description=str(raw.get("description") or ""),
        poll=poll,
        participants=tuple(participants),
        outcomes=outcomes,
        source=source,
    )


def bundled_fixtures() -> dict[str, Path]:
    """The fixtures shipped with the package, by file stem."""
    if not FIXTURE_DIR.is_dir():
        return {}
    return {path.stem: path for path in sorted(FIXTURE_DIR.glob("*.json"))}


def placeholder_numbers() -> set[str]:
    """Every phone number that appears in a bundled fixture.

    These are examples, not people. The live path refuses to dial them, so a
    demo poll cannot turn into a real call by accident — which is also why the
    examples do not need to rely on a nationally reserved "fictional" range
    that, for Germany, does not exist.
    """
    numbers: set[str] = set()
    for path in bundled_fixtures().values():
        try:
            fixture = load_fixture(path)
        except FixtureError:
            continue
        for entry in fixture.participants:
            raw = str(entry.get("phone", "")).strip()
            if raw:
                numbers.add(raw)
    return numbers


def resolve_fixture(name_or_path: str) -> Path:
    """Accept either a bundled fixture name or a path to a JSON file."""
    bundled = bundled_fixtures()
    if name_or_path in bundled:
        return bundled[name_or_path]
    candidate = Path(name_or_path)
    if candidate.is_file():
        return candidate
    available = ", ".join(bundled) or "none"
    raise FixtureError(
        f"unknown fixture {name_or_path!r}. Bundled fixtures: {available}. "
        "You can also pass a path to your own JSON file."
    )
