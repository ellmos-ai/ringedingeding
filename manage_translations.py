"""Maintain Ringedingeding's catalog using the Editor-PythonBox workflow.

Usage::

    python manage_translations.py list
    python manage_translations.py add "Kalender" "Calendar"
    python manage_translations.py missing

The scanner is the only local extension to PythonBox's script: it also reads
Jinja ``t('...')`` calls because this application is server-rendered HTML, not
Qt.  The catalog and atomic-save behavior stay the same.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from ringedingeding.translator import TranslationSystem

ROOT = Path(__file__).parent
T_CALL = re.compile(r"\bt\(\s*(['\"])(.*?)\1")


def source_keys() -> set[str]:
    keys: set[str] = set()
    for path in (ROOT / "ringedingeding").rglob("*"):
        if path.suffix not in {".py", ".html"}:
            continue
        text = path.read_text(encoding="utf-8")
        keys.update(match.group(2) for match in T_CALL.finditer(text))
    return keys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("missing")
    add = sub.add_parser("add")
    add.add_argument("german")
    add.add_argument("english")
    args = parser.parse_args()

    system = TranslationSystem(ROOT / "ringedingeding")
    if args.command == "list":
        for key in sorted(system.translations):
            print(f"{key} -> {system.translations[key].get('en', '')}")
        return 0
    if args.command == "missing":
        for key in sorted(source_keys() - system.translations.keys()):
            print(key)
        return 0
    system.translations[args.german] = {"de": args.german, "en": args.english}
    system.save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
