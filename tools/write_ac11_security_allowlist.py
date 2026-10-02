#!/usr/bin/env python3
"""Generate the reviewed AC-11 security allowlist; never edit the output by hand.

The input is the reviewer-owned decision record.  This writer refuses to emit an
allowlist unless its SECURITY DEFINER signatures exactly equal ``definer-policy.json``
and its RLS dispositions exactly cover ``rls-boundary-baseline.json``.  The generated
allowlist is therefore a mechanical projection of reviewed decisions, not a second place
where a signature or exception may be silently added.

Exit 0: generated (or ``--check`` matched); 2: source/policy/baseline is inconsistent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT
    / "docs/vault/30_Development/Evidence/"
    "s11-security-allowlist-reviewed-source-v1.json"
)
DEFAULT_POLICY = ROOT / "tools/definer-policy.json"
DEFAULT_BASELINE = ROOT / "tools/rls-boundary-baseline.json"
DEFAULT_OUTPUT = (
    ROOT / "docs/vault/30_Development/Evidence/s11-security-allowlist-v0.json"
)


def _identity(row: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    rules = row.get("rules")
    if not isinstance(rules, list) or not rules or len(set(rules)) != len(rules):
        raise ValueError("each RLS decision requires distinct non-empty rules")
    return str(row.get("role")), str(row.get("table")), tuple(sorted(rules))


def build_allowlist(
    source: Any, policy: Any, baseline: Any, *, root: Path = ROOT
) -> dict[str, Any]:
    if not isinstance(source, dict) or set(source) != {
        "schemaVersion",
        "verifiedAt",
        "definerReview",
        "secVf001",
        "rlsAcceptedDispositions",
    }:
        raise ValueError("review source has unknown or missing top-level fields")
    if source["schemaVersion"] != "1.0.0":
        raise ValueError("review source schemaVersion is unknown")
    review = source.get("definerReview")
    if not isinstance(review, dict) or set(review) != {
        "policyRevision", "reviewDocument", "signatures"
    }:
        raise ValueError("definerReview must carry policyRevision, reviewDocument and signatures")
    document = review.get("reviewDocument")
    if (
        not isinstance(document, str)
        or Path(document).is_absolute()
        or not (root / document).is_file()
    ):
        raise ValueError("definer reviewDocument must be a repository file")
    if not isinstance(policy, dict) or not isinstance(policy.get("functions"), dict):
        raise ValueError("definer policy has no function map")
    if review.get("policyRevision") != policy.get("revision"):
        raise ValueError("reviewed definer revision differs from definer-policy.json")
    signatures = review.get("signatures")
    declared = sorted(policy["functions"])
    if (
        not isinstance(signatures, list)
        or signatures != sorted(signatures)
        or len(signatures) != len(set(signatures))
        or signatures != declared
    ):
        raise ValueError("reviewed definer signatures must exactly equal the policy function set")

    baseline_rows = baseline.get("accepted") if isinstance(baseline, dict) else None
    decisions = source.get("rlsAcceptedDispositions")
    if not isinstance(baseline_rows, list) or not isinstance(decisions, list):
        raise ValueError("RLS baseline and decisions must be lists")
    baseline_ids = {_identity(row) for row in baseline_rows if isinstance(row, dict)}
    decision_ids = {_identity(row) for row in decisions if isinstance(row, dict)}
    if len(baseline_ids) != len(baseline_rows) or len(decision_ids) != len(decisions):
        raise ValueError("RLS baseline or decisions contain duplicate/non-object entries")
    if decision_ids != baseline_ids:
        raise ValueError("RLS decisions must exactly cover the reviewed collector baseline")

    return {
        "schemaVersion": source["schemaVersion"],
        "verifiedAt": source["verifiedAt"],
        "definerPolicySignatures": signatures,
        "secVf001": source["secVf001"],
        "rlsAcceptedDispositions": decisions,
    }


def render(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def canonical_sha256(document: dict[str, Any]) -> str:
    raw = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        document = build_allowlist(
            _load(args.source), _load(args.policy), _load(args.baseline)
        )
        rendered = render(document)
        if args.check:
            if args.out.read_text(encoding="utf-8") != rendered:
                raise ValueError("generated allowlist differs from the committed output")
        else:
            args.out.write_text(rendered, encoding="utf-8", newline="\n")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"security allowlist generation refused: {error}", file=sys.stderr)
        return 2
    raw = rendered.encode("utf-8")
    print(f'ALLOWLIST_BLOB = "{git_blob(raw)}"')
    print(f'ALLOWLIST_CANONICAL_SHA256 = "{canonical_sha256(document)}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
