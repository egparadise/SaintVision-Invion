"""List or explicitly prune aged, labelled SaintVision test Docker resources.

The default is read-only inventory. ``--delete`` is required for removal.
Only resources carrying one of the known run-ownership labels are eligible;
unlabelled resources and protected project prefixes are always preserved.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import subprocess

OWNERSHIP_LABELS = (
    "ai.saintvision.acceptance",
    "ai.saintvision.bridge-test",
    "ai.saintvision.developer-studio",
    "ai.saintvision.kernel-test",
    "ai.saintvision.remote-test",
    "ai.saintvision.test",
    "ai.saintvision.upgrade-test",
)
PROTECTED_PREFIXES = ("saintvision-lan-db", "saintview-orthanc")
EVIDENCE_RETENTION_MINUTES = {
    "ai.saintvision.acceptance": 14 * 24 * 60,
    "ai.saintvision.developer-studio": 14 * 24 * 60,
    "ai.saintvision.remote-test": 14 * 24 * 60,
    "ai.saintvision.upgrade-test": 14 * 24 * 60,
}


def _run(args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _inspect(kind: str, identifier: str):
    result = _run(["docker", kind, "inspect", identifier])
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)[0]
    except (ValueError, IndexError, TypeError):
        return None


def _resources():
    resources, unavailable, counts = [], [], {}
    specs = {
        # Containers need -a; volumes and networks are already fully listed by
        # their ls commands and reject that flag.
        "container": (["docker", "container", "ls", "-a", "-q"], ["docker", "container", "ls", "-a", "--format", "{{.ID}}"]),
        "volume": (["docker", "volume", "ls", "-q"], ["docker", "volume", "ls", "--format", "{{.Name}}"]),
        "network": (["docker", "network", "ls", "-q"], ["docker", "network", "ls", "--format", "{{.Name}}"]),
    }
    for kind, (list_args, count_args) in specs.items():
        listed = _run(list_args)
        counted = _run(count_args)
        if listed.returncode != 0 or counted.returncode != 0:
            unavailable.append({"kind": kind, "reason": "inventory query failed: " + ((listed.stderr or counted.stderr).strip()[-240:] or "unknown error")})
            continue
        identifiers = [value.strip() for value in listed.stdout.splitlines() if value.strip()]
        independent = [value.strip() for value in counted.stdout.splitlines() if value.strip()]
        counts[kind] = {"enumerated": len(identifiers), "independent": len(independent)}
        if len(identifiers) != len(independent):
            unavailable.append({"kind": kind, "reason": f"inventory count mismatch: enumerated={len(identifiers)} independent={len(independent)}"})
            continue
        for identifier in identifiers:
            value = _inspect(kind, identifier.strip())
            if value is None:
                unavailable.append({"kind": kind, "name": identifier.strip(), "reason": "inspect failed"})
                continue
            name = value.get("Name", "").lstrip("/")
            labels = (value.get("Config", {}).get("Labels", {}) if kind == "container" else value.get("Labels", {})) or {}
            owner = next(((key, labels[key]) for key in OWNERSHIP_LABELS if labels.get(key)), None)
            created = value.get("Created") or value.get("CreatedAt")
            resources.append({"kind": kind, "id": value.get("Id", identifier.strip()), "name": name,
                   "labels": labels, "owner": owner, "created": created,
                   "running": bool(value.get("State", {}).get("Running")) if kind == "container" else False,
                   "networkContainers": bool(value.get("Containers")) if kind == "network" else False})
    return resources, unavailable, counts


def _age_minutes(created: str | None):
    if not created:
        return None
    try:
        value = datetime.fromisoformat(created.replace("Z", "+00:00"))
        return max(0.0, (datetime.now(timezone.utc) - value.astimezone(timezone.utc)).total_seconds() / 60)
    except ValueError:
        return None


def _eligible(resource, minimum_age):
    if resource["name"].startswith(PROTECTED_PREFIXES):
        return False, "protected project prefix"
    if not resource["owner"]:
        return False, "ownership label absent"
    age = _age_minutes(resource["created"])
    policy_age = EVIDENCE_RETENTION_MINUTES.get(resource["owner"][0], minimum_age)
    threshold = max(minimum_age, policy_age)
    if age is None:
        return False, "creation age unavailable; preserved"
    if age < threshold:
        if policy_age > minimum_age:
            return False, f"intentional evidence retention; age {age:.0f}m < policy {threshold}m"
        return False, f"younger than age threshold ({threshold}m)"
    if resource["kind"] == "container" and resource["running"]:
        return False, "running container preserved"
    if resource["kind"] == "network" and resource["networkContainers"]:
        return False, "network has attached containers"
    return True, "eligible"


def _remove(resource):
    if resource["kind"] == "container":
        command = ["docker", "container", "rm", "-f", resource["id"]]
    elif resource["kind"] == "volume":
        command = ["docker", "volume", "rm", resource["id"]]
    else:
        command = ["docker", "network", "rm", resource["id"]]
    result = _run(command)
    if result.returncode != 0:
        return False, result.stderr.strip()[-240:] or "remove failed"
    if _inspect(resource["kind"], resource["id"]) is not None:
        return False, "removal not confirmed by inspect"
    return True, "confirmed-removed"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-age-minutes", type=float, default=30)
    parser.add_argument("--delete", action="store_true", help="remove eligible resources; default is inventory only")
    args = parser.parse_args(argv)
    result = {"mode": "delete" if args.delete else "list", "minAgeMinutes": args.min_age_minutes,
              "evidenceRetentionMinutes": EVIDENCE_RETENTION_MINUTES,
              "removed": [], "retained": []}
    resources, unavailable, counts = _resources()
    result["inventoryCounts"] = counts
    result["unverified"] = unavailable
    if args.delete and unavailable:
        result["deleteAborted"] = "incomplete inventory; no deletion attempted"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    for resource in resources:
        eligible, reason = _eligible(resource, args.min_age_minutes)
        if not eligible:
            result["retained"].append({"kind": resource["kind"], "name": resource["name"], "reason": reason})
            continue
        if not args.delete:
            result["retained"].append({"kind": resource["kind"], "name": resource["name"], "owner": resource["owner"], "reason": "eligible; deletion requires --delete"})
            continue
        ok, detail = _remove(resource)
        (result["removed"] if ok else result["retained"]).append({"kind": resource["kind"], "name": resource["name"], "reason": detail})
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
