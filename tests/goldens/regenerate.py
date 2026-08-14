"""Regenerate the golden task-text files for tests/test_conversation_tree_scenarios.py.

Deliberately NOT collected by pytest (does not match ``test_*.py``) and NOT run
automatically by any test. A red scenario test must never be "fixed" by silently
overwriting the golden it disagrees with -- regenerating is a conscious,
reviewed action:

    python tests/goldens/regenerate.py

This prints a diff-shaped summary of every file it changes or creates. Review
that output (and ``git diff tests/goldens/``) before committing -- an
unexpected change here usually means the task text changed, which is exactly
the kind of thing this suite exists to make visible.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_conversation_tree_scenarios import GOLDENS_DIR, LANGUAGES, SCENARIOS

from ringedingeding.schemas import build_task_text


def main() -> int:
    GOLDENS_DIR.mkdir(parents=True, exist_ok=True)
    created, changed, unchanged = [], [], []

    for name in sorted(SCENARIOS):
        factory, given_name, opening, closing, urgency = SCENARIOS[name]
        for language in LANGUAGES:
            poll = factory(language)
            text = build_task_text(poll, given_name, opening=opening, closing=closing, urgency=urgency)
            path = GOLDENS_DIR / f"{name}.{language}.txt"
            if not path.exists():
                path.write_text(text, encoding="utf-8")
                created.append(path.name)
                continue
            previous = path.read_text(encoding="utf-8")
            if previous == text:
                unchanged.append(path.name)
                continue
            diff = "\n".join(difflib.unified_diff(
                previous.splitlines(), text.splitlines(),
                fromfile=f"{path.name} (old)", tofile=f"{path.name} (new)",
                lineterm="",
            ))
            print(f"--- CHANGED: {path.name} ---\n{diff}\n")
            path.write_text(text, encoding="utf-8")
            changed.append(path.name)

    print(f"{len(created)} created, {len(changed)} changed, {len(unchanged)} unchanged.")
    if created:
        print("Created:", ", ".join(sorted(created)))
    if changed:
        print("Changed:", ", ".join(sorted(changed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
