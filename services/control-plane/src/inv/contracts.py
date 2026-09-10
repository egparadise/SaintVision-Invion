"""JSON Schema is authoritative. Generated types never replace boundary validation."""

from functools import lru_cache
from importlib.resources import files
import json
from jsonschema import Draft202012Validator, FormatChecker
from .errors import DomainError


@lru_cache
def catalog() -> dict:
    schema = json.loads(
        files("inv").joinpath("generated/core.schema.json").read_text("utf-8")
    )
    if "date-time" not in FormatChecker().checkers:
        raise RuntimeError(
            "Install jsonschema[format]; date-time validation is required"
        )
    Draft202012Validator.check_schema(schema)
    return schema


def validate_contract(name: str, value: object) -> None:
    schema = catalog()
    if name not in schema["$defs"]:
        raise DomainError("VAL-0001", "Unknown contract", 400)
    selected = {**schema, "$ref": f"#/$defs/{name}"}
    selected.pop("oneOf", None)
    errors = list(
        Draft202012Validator(selected, format_checker=FormatChecker()).iter_errors(
            value
        )
    )
    if errors:
        # Do not interpolate input values or validator errors, which can include secrets.
        raise DomainError("VAL-0002", f"{name}: invalid contract", 422)
