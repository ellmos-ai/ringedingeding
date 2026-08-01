"""A very small JSON-Schema checker for the subset this project emits.

Not a general implementation and not trying to be one. It covers exactly what
:mod:`ringedingeding.schemas` produces — ``type``, ``required``, ``properties``,
``enum``, ``items``, ``additionalProperties: false`` — so that the dry run can
prove one specific thing: the fixture answers really do satisfy the schema the
voice agent would have been handed. Without that check, a dry run could pass on
data no real call could ever have returned.

Adding ``jsonschema`` as a dependency would have worked too, but the dry run is
supposed to survive on a machine with nothing installed.
"""

from __future__ import annotations

from typing import Any

__all__ = ["validate", "SchemaViolation"]

_TYPES: dict[str, tuple[type, ...] | type] = {
    "object": dict,
    "array": (list, tuple),
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
}


class SchemaViolation(ValueError):
    """Raised by :func:`validate` when ``strict`` is set."""


def _type_ok(value: Any, expected: str) -> bool:
    python_type = _TYPES.get(expected)
    if python_type is None:
        return True
    if expected in ("integer", "number") and isinstance(value, bool):
        # bool is an int in Python; for schema purposes it is not a number.
        return False
    return isinstance(value, python_type)


def validate(instance: Any, schema: dict[str, Any], *, path: str = "$", strict: bool = False) -> list[str]:
    """Return a list of human-readable violations (empty means valid)."""
    errors: list[str] = []

    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _type_ok(instance, expected_type):
        errors.append(f"{path}: expected {expected_type}, got {type(instance).__name__}")
        if strict and errors:
            raise SchemaViolation("; ".join(errors))
        return errors

    enum = schema.get("enum")
    if isinstance(enum, list) and instance not in enum:
        errors.append(f"{path}: {instance!r} is not one of {enum}")

    if expected_type == "object" and isinstance(instance, dict):
        properties: dict[str, Any] = schema.get("properties") or {}
        for key in schema.get("required") or []:
            if key not in instance:
                errors.append(f"{path}: missing required field {key!r}")
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(f"{path}: unexpected field {key!r}")
        for key, value in instance.items():
            subschema = properties.get(key)
            if isinstance(subschema, dict):
                errors.extend(validate(value, subschema, path=f"{path}.{key}"))

    if expected_type == "array" and isinstance(instance, (list, tuple)):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for position, item in enumerate(instance):
                errors.extend(validate(item, item_schema, path=f"{path}[{position}]"))

    if strict and errors:
        raise SchemaViolation("; ".join(errors))
    return errors
