"""Resolve and store CALL-E credentials without exposing their values.

The public configuration contract is deliberately small and shared with the
other CALL-E projects: process environment, project ``.env``, then the local
project config.  Merely importing this module never requires a key, which keeps
every offline and rehearsal path usable on a clean machine.
"""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

API_KEY_ENV = "CALLE_API_KEY"
BASE_URL_ENV = "CALLE_BASE_URL"
ENV_FILE_ENV = "CALLE_ENV_FILE"
CONFIG_FILE_ENV = "CALLE_CONFIG_FILE"
DEFAULT_BASE_URL = "https://api.heycall-e.com"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_CONFIG_FILE = PROJECT_ROOT / "config.local.json"


class CalleCredentialError(RuntimeError):
    """Raised when live mode has no configured CALL-E credential."""


@dataclass(frozen=True)
class CalleSettings:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    source: str = ""
    env_file: Path = DEFAULT_ENV_FILE
    config_file: Path = DEFAULT_CONFIG_FILE

    @property
    def masked_key(self) -> str:
        """Return a display-safe fingerprint; short values stay fully hidden."""
        if len(self.api_key) <= 4:
            return "••••"
        return f"••••{self.api_key[-4:]}"


def _clean(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _path(value: str | os.PathLike[str] | None, fallback: Path) -> Path:
    return Path(value).expanduser().resolve() if value else fallback


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name] = value
    return values


def _read_config(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CalleCredentialError(
            f"CALL-E config file {path} cannot be read as JSON: {type(error).__name__}."
        ) from None
    if not isinstance(payload, dict):
        raise CalleCredentialError(f"CALL-E config file {path} must contain a JSON object.")
    return {str(name): value for name, value in payload.items() if isinstance(value, str)}


def missing_key_message(env_file: Path, config_file: Path) -> str:
    return (
        "No CALL-E API key is configured. For live calls, use one of these paths "
        "(highest priority first): (1) environment variable CALLE_API_KEY; "
        f"(2) CALLE_API_KEY in .env at {env_file} "
        "(override its path with CALLE_ENV_FILE); "
        f"(3) CALLE_API_KEY in project config {config_file} "
        "(override its path with CALLE_CONFIG_FILE, or save it on the Settings page). "
        "Dry runs work without a key; nothing was dialed."
    )


def load_calle_settings(
    *,
    environ: Mapping[str, str] | None = None,
    env_file: str | os.PathLike[str] | None = None,
    config_file: str | os.PathLike[str] | None = None,
    required: bool = True,
) -> CalleSettings | None:
    """Resolve settings in the documented priority order."""
    current = os.environ if environ is None else environ
    env_path = _path(env_file or _clean(current.get(ENV_FILE_ENV)), DEFAULT_ENV_FILE)
    config_path = _path(
        config_file or _clean(current.get(CONFIG_FILE_ENV)), DEFAULT_CONFIG_FILE
    )
    environment_key = _clean(current.get(API_KEY_ENV))
    if environment_key:
        return CalleSettings(
            api_key=environment_key,
            base_url=(_clean(current.get(BASE_URL_ENV)) or DEFAULT_BASE_URL).rstrip("/"),
            source="environment",
            env_file=env_path,
            config_file=config_path,
        )

    dotenv = _read_env_file(env_path)
    dotenv_key = _clean(dotenv.get(API_KEY_ENV))
    if dotenv_key:
        return CalleSettings(
            api_key=dotenv_key,
            base_url=(
                _clean(current.get(BASE_URL_ENV))
                or _clean(dotenv.get(BASE_URL_ENV))
                or DEFAULT_BASE_URL
            ).rstrip("/"),
            source=".env",
            env_file=env_path,
            config_file=config_path,
        )

    config = _read_config(config_path)
    config_key = _clean(config.get(API_KEY_ENV))
    if config_key:
        return CalleSettings(
            api_key=config_key,
            base_url=(
                _clean(current.get(BASE_URL_ENV))
                or _clean(dotenv.get(BASE_URL_ENV))
                or _clean(config.get(BASE_URL_ENV))
                or DEFAULT_BASE_URL
            ).rstrip("/"),
            source="project config",
            env_file=env_path,
            config_file=config_path,
        )
    if required:
        raise CalleCredentialError(missing_key_message(env_path, config_path))
    return None


def save_project_api_key(
    api_key: str,
    *,
    config_file: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Store a key in the ignored local config without returning its value."""
    key = api_key.strip()
    if not key:
        raise ValueError("The CALL-E API key must not be empty.")
    current = os.environ if environ is None else environ
    path = _path(config_file or _clean(current.get(CONFIG_FILE_ENV)), DEFAULT_CONFIG_FILE)
    payload = _read_config(path)
    payload[API_KEY_ENV] = key
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temporary = handle.name
        os.replace(temporary, path)
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)
    finally:
        if temporary:
            with contextlib.suppress(OSError):
                Path(temporary).unlink(missing_ok=True)
    return path
