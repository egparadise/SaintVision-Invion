"""Report-only: which freshness-critical responses carry an observation-time field.

The time axis (does a value say WHEN it was true) is the one revival is weak at: a test runs in a
single instant, so a missing observedAt looks fine at t=0. What CAN be automated is the STRUCTURAL
half -- a freshness-critical response must declare a time field -- checked against an INDEPENDENT
pinned map (rule 6: a value that expresses a contract is fixed, not derived from the schema being
checked; deriving "which fields are times" from the schema would let a field's removal erase its own
expectation).

What this does NOT and CANNOT automate: (a) whether the served value is actually stale (that is a
behavioural, clock-advance question -- and where the backend derives a stale state it does so in SQL
via clock_timestamp(), so it needs real PG, not this); (b) whether a NEWLY added response is
freshness-critical and belongs in this map -- that is human judgment, and a new response left off the
map is silently unchecked (the same forgets-limitation as the migration prior list). So this check is
a floor, not a ceiling: it holds the known set and must be reviewed when responses are added.

Report-only: ShardObservation is a known pending gap (observedAt recommended to Codex); a gate would
fail on it. Present/missing is printed for review.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "contracts" / "v1alpha1" / "core.schema.json"
SCHEMAS = ROOT / "src" / "saintvision" / "api" / "schemas.py"

# INDEPENDENT pinned map: freshness-critical response -> the time field it must carry, and where.
# Curated by hand (which responses are freshness-critical is judgment). Reviewed when responses are
# added. "kernel" = core.schema.json $def; "saintvision" = a schemas.py class.
REQUIRED_TIME_FIELD = {
    ("kernel", "RunResultView"): "completedAt",            # terminal state truth-time
    ("kernel", "ModelCommitObservation"): "committedAt",
    ("kernel", "StorageObservationView"): "createdAt",
    ("saintvision", "NodeResponse"): "lastHeartbeatAt",    # node liveness truth-time
    ("saintvision", "ReplicaObservationResponse"): "observedAt",
    # Known GAP (freshness-critical, no time field yet -- recommended to Codex, kernel lane):
    ("kernel", "ShardObservation"): "observedAt",
}


def kernel_fields(name: str) -> set[str]:
    defs = json.loads(CORE.read_text(encoding="utf-8")).get("$defs", {})
    return set((defs.get(name, {}).get("properties") or {}).keys())


def saintvision_fields(name: str) -> set[str]:
    """Field aliases declared on a schemas.py class (alias="X" or bare field name until next class)."""
    text = SCHEMAS.read_text(encoding="utf-8")
    m = re.search(rf"class {name}\b.*?(?=\nclass |\Z)", text, re.S)
    if not m:
        return set()
    body = m.group(0)
    aliases = set(re.findall(r'alias="([A-Za-z0-9_]+)"', body))
    names = set(re.findall(r"^\s{4}([a-z_][a-z0-9_]*)\s*[:=]", body, re.M))
    return aliases | names


def check() -> tuple[list[str], list[str]]:
    present, missing = [], []
    for (source, name), field in sorted(REQUIRED_TIME_FIELD.items()):
        fields = kernel_fields(name) if source == "kernel" else saintvision_fields(name)
        if field in fields:
            present.append(f"{source}:{name}.{field}")
        else:
            missing.append(f"{source}:{name}.{field}")
    return present, missing


def main() -> int:
    present, missing = check()
    print(
        f"REPORT check_response_freshness (advisory): "
        f"{len(present)}/{len(present) + len(missing)} freshness-critical responses carry their time field."
    )
    for p in present:
        print(f"  ok      {p}")
    for m in missing:
        print(f"  MISSING {m}  (freshness-critical; screen cannot show truth-time without it)")
    print(
        "  (structural floor only. Whether a NEW response is freshness-critical is human judgment -- "
        "review this map when responses are added. Staleness behaviour needs a clock-advance test with PG.)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
