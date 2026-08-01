"""The optional web interface.

Installed with ``pip install -e ".[web]"``. The command line has no dependency
on any of this — importing it without FastAPI present raises here rather than
somewhere confusing.
"""

from __future__ import annotations

__all__ = ["create_app", "run"]


def __getattr__(name: str):  # pragma: no cover - thin import shim
    if name in __all__:
        try:
            from . import app as _app
        except ModuleNotFoundError as error:  # pragma: no cover - depends on env
            raise ModuleNotFoundError(
                "The web interface needs its extra dependencies: "
                'pip install -e ".[web]"'
            ) from error
        return getattr(_app, name)
    raise AttributeError(name)
