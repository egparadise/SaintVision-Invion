"""Re-derive the VF-CL registry's implementation claims from the tree.

The registry is what the coordinator reads to pick the next card, so a stale entry does
not just misdescribe the work -- it sends somebody to do work that is already done, or
to wait for something that already happened. Both had happened by the time this was
written:

* ``VF-CL-03`` still said ``implemented: partial`` with an open
  ``import-adapter-has-no-request-path-contract``, while the request path had landed:
  the release route is mounted on the projects router and calls the adapter.
* ``VF-CL-04`` said the restore drill was skipping
  ``until-pr-126`` -- and PR #126 had merged. Anyone waiting for it would wait forever.
  The 19 skips are real but they are waiting for container inputs, not for that PR.

Nothing validated that file, which is why it drifted quietly. This does, and it is
deliberately mechanical: it re-derives facts rather than reading prose.

Three rules:

1. **Shape.** Every card carries the six state fields, ``implemented`` is one of
   ``true``/``false``/``"partial"``, and every blocker is a non-empty string.
2. **No blocker may name a merged pull request.** A blocker whose text contains
   ``pr-<n>`` or ``#<n>`` claims to be waiting for it. If that PR is already merged in
   this history the blocker is misstated, which is how #126 slipped through. This is
   the rule that generalises the mistake.
3. **Every closed blocker must still be closed.** A ``closedBlockers`` entry carries
   ``checks``, and each check is re-run against the tree. Prose in ``evidence`` is for
   people; the checks are what this tool believes.

The check vocabulary is small on purpose -- a large one invites claims nobody verifies:

``{"kind": "references", "path": ..., "text": ...}``
    that file contains that literal text.
``{"kind": "absent", "path": ..., "text": ...}``
    that file does not.
``{"kind": "path-exists", "path": ...}``
    the file is in the tree.

Exit codes: 0 the registry matches the tree, 1 it does not (every mismatch is listed),
2 the registry itself is unusable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO_ROOT / "docs/vf-cl-task-registry.json"

STATE_FIELDS = (
    "implemented",
    "locallyVerified",
    "ciVerified",
    "independentlyReviewed",
    "operationallyAccepted",
)
#: A blocker that names a pull request is claiming to wait for it.
PULL_REQUEST = re.compile(r"(?:\bpr-|#)(\d{1,5})\b")
CHECK_KINDS = ("references", "absent", "path-exists")


class RegistryUnusable(ValueError):
    """The registry cannot be judged, which is not the same as it being wrong."""


def merged_pull_requests(root: Path) -> set[int]:
    """Pull request numbers this history records as merged.

    Read once: a subprocess per blocker would be slower and no more accurate.
    """
    result = subprocess.run(
        ["git", "log", "--format=%s%n%b"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RegistryUnusable("git log failed; cannot tell which pull requests merged")
    merged: set[int] = set()
    for line in result.stdout.splitlines():
        lowered = line.lower()
        if "merge" not in lowered and "landed" not in lowered:
            continue
        for match in re.finditer(r"#(\d{1,5})\b", line):
            merged.add(int(match.group(1)))
    return merged


def run_check(check: dict, root: Path) -> str | None:
    """None when the check holds, otherwise why it does not."""
    kind = check.get("kind")
    if kind not in CHECK_KINDS:
        raise RegistryUnusable(f"unknown check kind: {kind!r}")
    relative = check.get("path")
    if not isinstance(relative, str) or not relative:
        raise RegistryUnusable("a check needs a path")
    target = root / relative
    if kind == "path-exists":
        return None if target.is_file() else f"{relative} is not in the tree"
    if not target.is_file():
        return f"{relative} is not in the tree"
    text = check.get("text")
    if not isinstance(text, str) or not text:
        raise RegistryUnusable("a references/absent check needs text")
    body = target.read_text(encoding="utf-8", errors="replace")
    if kind == "references":
        return None if text in body else f"{relative} no longer contains {text!r}"
    return None if text not in body else f"{relative} now contains {text!r}"


def audit(registry: dict, root: Path) -> list[str]:
    """Every way the registry disagrees with the tree, in one list."""
    if not isinstance(registry, dict) or not isinstance(registry.get("cards"), list):
        raise RegistryUnusable("the registry must be an object with a cards array")
    findings: list[str] = []
    merged = merged_pull_requests(root)

    verified = registry.get("verifiedAgainst")
    if not isinstance(verified, dict) or not verified.get("tree"):
        findings.append("the registry does not say which tree it was verified against")
    else:
        tree = str(verified["tree"])
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", tree, "HEAD"],
            cwd=root, capture_output=True, text=True,
        )
        if result.returncode != 0:
            # A claim about a tree this branch does not contain is a claim about
            # something else. The numbers may be right; they are not about here.
            findings.append(f"verifiedAgainst.tree {tree} is not an ancestor of HEAD")

    seen: set[str] = set()
    for card in registry["cards"]:
        if not isinstance(card, dict) or not isinstance(card.get("id"), str):
            raise RegistryUnusable("every card needs a string id")
        identifier = card["id"]
        if identifier in seen:
            findings.append(f"{identifier} appears more than once")
        seen.add(identifier)

        for field in STATE_FIELDS:
            if field not in card:
                findings.append(f"{identifier} does not say {field}")
        implemented = card.get("implemented")
        # Identity, not equality: `1 in (True, False, "partial")` is True in Python, so
        # a card could say `implemented: 1` and be read as done.
        if implemented is not True and implemented is not False and implemented != "partial":
            findings.append(f"{identifier}.implemented is {implemented!r}")

        for blocker in card.get("blockers") or []:
            if not isinstance(blocker, str) or not blocker.strip():
                findings.append(f"{identifier} has an empty blocker")
                continue
            for match in PULL_REQUEST.finditer(blocker):
                number = int(match.group(1))
                if number in merged:
                    findings.append(
                        f"{identifier} waits for PR #{number}, which this history records "
                        f"as merged: {blocker}"
                    )

        for entry in card.get("closedBlockers") or []:
            if not isinstance(entry, dict) or not entry.get("blocker"):
                raise RegistryUnusable(f"{identifier} has a closedBlockers entry with no blocker")
            name = entry["blocker"]
            if name in (card.get("blockers") or []):
                findings.append(f"{identifier} lists {name} as both open and closed")
            checks = entry.get("checks")
            if not isinstance(checks, list) or not checks:
                # Prose alone is how the last two entries went stale unnoticed.
                findings.append(f"{identifier}: closed blocker {name} carries no checks")
                continue
            for check in checks:
                problem = run_check(check, root)
                if problem:
                    findings.append(f"{identifier}: {name} is marked closed but {problem}")

    return findings


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    result.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    result.add_argument("--root", type=Path, default=REPO_ROOT)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        findings = audit(registry, args.root)
    except RegistryUnusable as error:
        print(f"unusable: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"unusable: {type(error).__name__}", file=sys.stderr)
        return 2
    if findings:
        for finding in findings:
            print(f"drift: {finding}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "registry": str(args.registry.relative_to(args.root)),
                "cards": len(registry["cards"]),
                "verifiedAgainst": registry.get("verifiedAgainst", {}).get("tree"),
                "status": "every implementation claim re-derived from the tree",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
