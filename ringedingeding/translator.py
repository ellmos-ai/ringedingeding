"""JSON translation catalog, adapted from Editor-PythonBox.

The existing project's ``TranslationSystem`` contract is retained: German
source strings are lookup keys, unknown strings fall back unchanged, and the
catalog is a plain UTF-8 JSON file editable by ``manage_translations.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["TranslationSystem"]


class TranslationSystem:
    SUPPORTED_LANGUAGES = ("de", "en")

    def __init__(self, app_dir: str | Path | None = None, language: str = "de") -> None:
        self.app_dir = Path(app_dir) if app_dir else Path(__file__).parent
        self.catalog_path = self.app_dir / "locales" / "translations.json"
        self.translations = self._load()
        self.current_language = language if language in self.SUPPORTED_LANGUAGES else "de"

    def _load(self) -> dict[str, dict[str, str]]:
        try:
            data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def set_language(self, language: str) -> None:
        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language: {language}")
        self.current_language = language

    def t(self, text: str, **values: Any) -> str:
        translated = self.translations.get(text, {}).get(self.current_language, text)
        return translated.format(**values) if values else translated

    def save(self) -> None:
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.catalog_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self.translations, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.catalog_path)
