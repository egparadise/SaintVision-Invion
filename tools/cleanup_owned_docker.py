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
    for kind, list_kind in (("container", "container"), ("volume", "volume"), ("network", "network")):
        listed = _run(["docker", list_kind, "ls", "-a", "-q"] if kind != "network" else ["docker", "network", "ls", "-q"])
        if listed.returncode != 0:
            continue
        for identifier in filter(None, listed.stdout.splitlines()):
            value = _inspect(kind, identifier.strip())
            if value is None:
                continue
            name = value.get("Name", "").lstrip("/")
            labels = (value.get("Config", {}).get("Labels", {}) if kind == "container" else value.get("Labels", {})) or {}
            owner = next(((key, labels[key]) for key in OWNERSHIP_LABELS if labels.get(key)), None)
            created = value.get("Created")
            yield {"kind": kind, "id": value.get("Id", identifier.strip()), "name": name,
                   "labels": labels, "owner": owner, "created": created,
                   "running": bool(value.get("State", {}).get("Running")) if kind == "container" else False,
                   "networkContainers": bool(value.get("Containers")) if kind == "network" else False}


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
    if age is None or age < minimum_age:
        return False, "younger than age threshold"
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
              "removed": [], "retained": []}
    for resource in _resources():
        eligible, reason = _eligible(resource, args.min_age_minutes)
        if not eligible:
            result["retained"].append({"kind": resource["kind"], "name": resource["name"], "reason": reason})
            continue
        if not args.delete:
            result["retained"].append({"kind": resource["kind"], "name": resource["name"], "reason": "eligible; deletion requires --delete"})
            continue
        ok, detail = _remove(resource)
        (result["removed"] if ok else result["retained"]).append({"kind": resource["kind"], "name": resource["name"], "reason": detail})
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
