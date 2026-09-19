"""List or explicitly prune aged, labelled SaintVision test Docker resources.

The default is read-only inventory. ``--delete`` is required for removal.
Only resources carrying one of the known run-ownership labels are eligible;
unlabelled resources and protected project prefixes are always preserved.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
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
ANONYMOUS_VOLUME_PATTERN = re.compile(r"^[0-9a-f]{64}$")


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


def _engine_get(path: str):
    """Read one Docker Engine API endpoint through the CLI's daemon channel."""
    process = subprocess.Popen(["docker", "system", "dial-stdio"], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    request = f"GET {path} HTTP/1.1\r\nHost: docker\r\nConnection: close\r\n\r\n".encode()
    stdout, stderr = process.communicate(request, timeout=30)
    if process.returncode:
        raise RuntimeError(stderr.decode("utf-8", "replace").strip()[-240:] or "Docker Engine channel failed")
    header, separator, body = stdout.partition(b"\r\n\r\n")
    if not separator or not header.startswith(b"HTTP/") or b" 200 " not in header.splitlines()[0]:
        raise RuntimeError("Docker Engine API request failed")
    headers = header.lower()
    if b"transfer-encoding: chunked" in headers:
        decoded = bytearray()
        while body:
            line, _, body = body.partition(b"\r\n")
            size = int(line.split(b";", 1)[0], 16)
            if size == 0:
                break
            decoded.extend(body[:size])
            body = body[size + 2:]
        body = bytes(decoded)
    return json.loads(body.decode("utf-8"))


def _engine_counts():
    """Return daemon-owned counts, independent of any `docker * ls` flags."""
    return {
        "container": len(_engine_get("/containers/json?all=1")),
        "volume": len((_engine_get("/volumes") or {}).get("Volumes") or []),
        "network": len(_engine_get("/networks")),
    }


def _resources():
    resources, unavailable, counts = [], [], {}
    specs = {
        # Containers need -a; volumes and networks are already fully listed by
        # their ls commands and reject that flag.
        "container": ["docker", "container", "ls", "-a", "-q"],
        "volume": ["docker", "volume", "ls", "-q"],
        "network": ["docker", "network", "ls", "-q"],
    }
    try:
        daemon_counts = _engine_counts()
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError, TypeError, json.JSONDecodeError) as error:
        daemon_counts = None
        unavailable.append({"kind": "inventory", "reason": "independent Docker Engine count unavailable: " + str(error)[-240:]})
    for kind, list_args in specs.items():
        listed = _run(list_args)
        if listed.returncode != 0:
            unavailable.append({"kind": kind, "reason": "inventory query failed: " + (listed.stderr.strip()[-240:] or "unknown error")})
            continue
        identifiers = [value.strip() for value in listed.stdout.splitlines() if value.strip()]
        independent = daemon_counts.get(kind) if daemon_counts is not None else None
        if independent is None:
            unavailable.append({"kind": kind, "reason": "independent Docker Engine count unavailable"})
            continue
        counts[kind] = {"enumerated": len(identifiers), "independent": independent}
        if len(identifiers) != independent:
            unavailable.append({"kind": kind, "reason": f"inventory count mismatch: enumerated={len(identifiers)} independent={independent}"})
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
                   "anonymousVolume": kind == "volume" and bool(ANONYMOUS_VOLUME_PATTERN.fullmatch(name)),
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
    if resource.get("anonymousVolume"):
        return False, "anonymous Docker volume; preserve by explicit user decision (ownership unavailable)"
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
        # -v removes anonymous volumes declared by images (for example
        # postgres:16's /var/lib/postgresql/data) along with the owned
        # container, preventing cleanup from creating new orphan volumes.
        command = ["docker", "container", "rm", "-f", "-v", resource["id"]]
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
              "anonymousVolumePolicy": {
                  "status": "preserve-by-user-decision",
                  "decision": "Preserve the currently inventoried anonymous Docker volumes; do not delete without a new explicit user instruction.",
                  "ownership": "unproven; 64-hex Docker-generated names carry no run ownership label",
              },
              "removed": [], "retained": [], "anonymousVolumes": []}
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
            entry = {"kind": resource["kind"], "name": resource["name"], "reason": reason}
            result["retained"].append(entry)
            if resource.get("anonymousVolume"):
                result["anonymousVolumes"].append({"name": resource["name"], "reason": reason})
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
