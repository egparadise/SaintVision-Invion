"""Emit JSON Schema for the /v1 contracts.

PLAN-BACKEND-001 makes JSON Schema the single source and forbids hand-editing
generated artefacts. This script generates in one direction only — Pydantic
models in ``saintvision.api.schemas`` produce ``contracts/*.schema.json`` — so
the two cannot drift apart silently.

``--check`` re-generates into memory and compares, so CI fails when a model
changes without the schema being regenerated.

Usage:
    python tools/export_schemas.py            # write
    python tools/export_schemas.py --check    # verify, exit 1 on drift
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from saintvision.api import schemas  # noqa: E402

OUT_DIR = ROOT / "contracts"

def _contract_name(class_name: str) -> str:
    """``NodeEnrollRequest`` -> ``node-enroll-request``."""
    out = []
    for index, char in enumerate(class_name):
        if char.isupper() and index:
            out.append("-")
        out.append(char.lower())
    return "".join(out)


def exported() -> dict[str, type]:
    """Every request and response contract, found rather than listed.

    This was a hand-written dictionary, which is the fourth hardcoded list in
    this repository to go stale — and the failure mode here is the quietest of
    them: a new endpoint's schema is simply never generated, so there is no
    contract to drift from and ``--check`` passes.

    The rule is the one the models already follow: a ``Strict`` subclass whose
    name ends in Request or Response is part of the wire contract. Everything
    else in the module — the nested payloads — appears inline inside the
    contract that carries it, which is where a caller needs to see it.
    """
    found: dict[str, type] = {}
    for name in dir(schemas):
        model = getattr(schemas, name)
        if (
            isinstance(model, type)
            and issubclass(model, schemas.Strict)
            and model is not schemas.Strict
            and (name.endswith("Request") or name.endswith("Response"))
        ):
            found[_contract_name(name)] = model
    return found


EXPORTED = exported()


def render(model) -> str:
    document = model.model_json_schema(by_alias=True)
    document["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    drift: list[str] = []
    for name, model in sorted(EXPORTED.items()):
        target = OUT_DIR / f"{name}.schema.json"
        rendered = render(model)
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != rendered:
                drift.append(target.name)
        else:
            # Keep generated schema bytes aligned with .gitattributes (LF on disk).
            # Path.write_text translates ``\n`` to CRLF on Windows and leaves every
            # schema dirty after a successful generation even when content matches.
            target.write_bytes(rendered.encode("utf-8"))

    if args.check:
        if drift:
            print(f"FAIL: {len(drift)} schema file(s) out of date: {', '.join(drift)}")
            print("Run: python tools/export_schemas.py")
            return 1
        print(f"PASS: {len(EXPORTED)} contract schemas match their models.")
        return 0

    print(f"WROTE: {len(EXPORTED)} contract schemas to {OUT_DIR.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
