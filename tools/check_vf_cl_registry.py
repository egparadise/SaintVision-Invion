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

A first version of this tool only looked at the registry's **shape**, and a review
showed what that missed: four edits passed it while making it say something false.

* ``acceptedCards: 5`` beside five cards none of which is accepted.
* every card ``operationallyAccepted: true`` while their blockers were still open.
* ``VF-CL-03`` reverted to its pre-correction state -- internally consistent, and wrong.
* ``VF-CL-04``'s retention blocker re-opened after being closed against the tree.

The first two are contradictions inside the file, so they are cross-checked. The last two
are the harder shape: a registry can be edited into an earlier state that no rule about
its own contents can fault. Judging them needs something outside the file, so the
per-card assertions live in **a separate manifest** (``docs/vf-cl-registry-manifest.json``),
and this tool refuses to run without it, refuses a card it does not cover, and refuses a
closed blocker it carries no checks for. Deleting an entry is a failure, not a silence.

Six rules:

1. **Shape.** Every card carries the six state fields, ``implemented`` is one of
   ``true``/``false``/``"partial"``, and every blocker is a non-empty string.
2. **No blocker may name a merged pull request.** A blocker whose text contains
   ``pr-<n>`` or ``#<n>`` claims to be waiting for it. If that PR is already merged in
   this history the blocker is misstated, which is how #126 slipped through. This is
   the rule that generalises the mistake.
3. **Every closed blocker must still be closed.** The manifest carries its checks and
   each is re-run against the tree. Prose in ``evidence`` is for people; the checks are
   what this tool believes. A blocker the manifest shows closed may not be listed open.
4. **The tree decides ``implemented``.** When every manifest check for a card holds, the
   registry's ``implemented`` must equal the manifest's ``impliesImplemented``. This is
   what a revert cannot survive.
5. **``acceptedCards`` is counted, not stated**, and a card cannot be
   ``operationallyAccepted`` while it has open blockers, is not ``ciVerified`` or
   ``independentlyReviewed`` (unless ``notApplicable`` says why), or is not in state
   ``accepted``.
6. **A local gap is not a blocker.** ``localUnmeasured`` entries say what was not measured
   here and **where it is measured instead**; the same subject may not also be a blocker.
   The restore drill was filed as an external precondition when it was measured in hosted
   CI all along -- that is the mistake this rule exists for.

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
DEFAULT_MANIFEST = REPO_ROOT / "docs/vf-cl-registry-manifest.json"
MANIFEST_SCHEMA = "vf-cl-registry-manifest:1"

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
#: A card may only be called accepted when these hold, or when ``notApplicable`` names the
#: field and says why. Acceptance is the one claim nobody downstream re-checks.
ACCEPTANCE_REQUIRES = ("ciVerified", "independentlyReviewed")


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


def same_claim(left: object, right: object) -> bool:
    """1 == True in Python, so a registry saying 1 must not read as true."""
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    return left == right


def load_manifest(path: Path, identifiers: list[str]) -> dict:
    """The assertions this tool judges the registry by, which the registry cannot edit.

    Missing, malformed, or not covering every card is ``unusable`` rather than drift: a
    check that is not there does not fail, and silence is what this whole tool exists to
    remove.
    """
    if not path.is_file():
        raise RegistryUnusable(f"the re-derivation manifest is missing: {path.name}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise RegistryUnusable(f"the manifest is not readable JSON: {type(error).__name__}")
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != MANIFEST_SCHEMA:
        raise RegistryUnusable(f"the manifest must declare schemaVersion {MANIFEST_SCHEMA}")
    cards = manifest.get("cards")
    if not isinstance(cards, dict):
        raise RegistryUnusable("the manifest must carry a cards object")
    missing = [name for name in identifiers if name not in cards]
    if missing:
        raise RegistryUnusable(f"the manifest does not cover {', '.join(missing)}")
    unknown = [name for name in cards if name not in identifiers]
    if unknown:
        raise RegistryUnusable(f"the manifest covers cards the registry does not have: "
                               f"{', '.join(sorted(unknown))}")
    for name, entry in cards.items():
        if not isinstance(entry, dict):
            raise RegistryUnusable(f"the manifest entry for {name} is not an object")
        implied = entry.get("impliesImplemented")
        if implied is not True and implied is not False and implied is not None \
                and implied != "partial":
            raise RegistryUnusable(f"{name}.impliesImplemented is {implied!r}")
        checks = entry.get("checks")
        if not isinstance(checks, list):
            raise RegistryUnusable(f"{name} needs a checks array, even an empty one")
        if implied is None and not str(entry.get("why") or "").strip():
            # An entry with nothing to assert has to say so. Otherwise it reads as
            # coverage while asserting nothing, which is worse than being absent.
            raise RegistryUnusable(f"{name} asserts nothing and does not say why")
        if implied is not None and not checks:
            raise RegistryUnusable(f"{name} claims implemented={implied!r} with no checks")
        if not isinstance(entry.get("closedBlockers", {}), dict):
            raise RegistryUnusable(f"{name}.closedBlockers must be an object")
    return manifest


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


def audit(registry: dict, root: Path, manifest_path: Path = DEFAULT_MANIFEST) -> list[str]:
    """Every way the registry disagrees with the tree or with itself, in one list."""
    if not isinstance(registry, dict) or not isinstance(registry.get("cards"), list):
        raise RegistryUnusable("the registry must be an object with a cards array")
    for card in registry["cards"]:
        if not isinstance(card, dict) or not isinstance(card.get("id"), str):
            raise RegistryUnusable("every card needs a string id")
    identifiers = [card["id"] for card in registry["cards"]]
    manifest = load_manifest(manifest_path, identifiers)["cards"]
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

    accepted = [card for card in registry["cards"]
                if card.get("operationallyAccepted") is True]
    declared = registry.get("acceptedCards")
    if declared != len(accepted):
        # Stated rather than counted, this is the one number a reader takes at face value.
        findings.append(
            f"acceptedCards says {declared!r} but {len(accepted)} card(s) are "
            f"operationallyAccepted"
        )
    denominator = registry.get("acceptanceDenominator")
    if denominator != len(registry["cards"]):
        findings.append(
            f"acceptanceDenominator says {denominator!r} for {len(registry['cards'])} cards"
        )

    seen: set[str] = set()
    for card in registry["cards"]:
        identifier = card["id"]
        entry = manifest[identifier]
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

        # Rule 4: the tree decides. A card edited back to an earlier state stays
        # internally consistent, so nothing inside the registry can fault it.
        implied = entry.get("impliesImplemented")
        broken = [problem for problem in
                  (run_check(check, root) for check in entry.get("checks") or [])
                  if problem]
        if broken:
            findings.append(
                f"{identifier}: the manifest's assertion no longer holds in the tree: "
                + "; ".join(broken)
            )
        elif implied is not None and not same_claim(implemented, implied):
            findings.append(
                f"{identifier}: the tree shows implemented={implied!r} but the registry "
                f"says {implemented!r}"
            )

        # Rule 5: acceptance is the claim nobody downstream re-checks.
        if card.get("operationallyAccepted") is True:
            excused = {text.split(":", 1)[0].strip()
                       for text in card.get("notApplicable") or []}
            if card.get("blockers"):
                findings.append(
                    f"{identifier} is operationallyAccepted with "
                    f"{len(card['blockers'])} open blocker(s)"
                )
            if card.get("state") != "accepted":
                findings.append(
                    f"{identifier} is operationallyAccepted while its state is "
                    f"{card.get('state')!r}"
                )
            for field in ACCEPTANCE_REQUIRES:
                if card.get(field) is not True and field not in excused:
                    findings.append(
                        f"{identifier} is operationallyAccepted while {field} is "
                        f"{card.get(field)!r}"
                    )

        # Rule 6: a local gap is not a blocker.
        open_blockers = [b for b in card.get("blockers") or [] if isinstance(b, str)]
        for gap in card.get("localUnmeasured") or []:
            if not isinstance(gap, dict):
                raise RegistryUnusable(f"{identifier} has a localUnmeasured entry that is "
                                       f"not an object")
            subject = str(gap.get("what") or "").strip()
            where = str(gap.get("measuredIn") or "").strip()
            if not subject or not where:
                findings.append(
                    f"{identifier}: a localUnmeasured entry must say what was not measured "
                    f"here and where it is measured instead"
                )
                continue
            if subject in open_blockers:
                findings.append(
                    f"{identifier}: {subject} is filed as both a local gap and a blocker; "
                    f"it is measured in {where}"
                )

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

        manifest_closed = entry.get("closedBlockers") or {}
        recorded = []
        for closed in card.get("closedBlockers") or []:
            if not isinstance(closed, dict) or not closed.get("blocker"):
                raise RegistryUnusable(f"{identifier} has a closedBlockers entry with no blocker")
            name = closed["blocker"]
            recorded.append(name)
            if name in open_blockers:
                findings.append(f"{identifier} lists {name} as both open and closed")
            if name not in manifest_closed:
                # Prose alone is how the first two entries went stale unnoticed, and a
                # manifest entry that can be dropped is prose again.
                raise RegistryUnusable(
                    f"{identifier}: the manifest carries no checks for closed blocker {name}"
                )

        for name, checks in manifest_closed.items():
            if not isinstance(checks, list) or not checks:
                raise RegistryUnusable(
                    f"{identifier}: the manifest's closed blocker {name} has no checks"
                )
            problems = [problem for problem in (run_check(check, root) for check in checks)
                        if problem]
            if problems:
                findings.append(
                    f"{identifier}: {name} is recorded closed but " + "; ".join(problems)
                )
                continue
            # The checks hold, so the tree says this is closed. Re-opening it, or quietly
            # dropping the record, both contradict the tree.
            if name in open_blockers:
                findings.append(
                    f"{identifier}: {name} is listed open but the tree still shows it closed"
                )
            if name not in recorded:
                findings.append(
                    f"{identifier}: {name} is closed in the tree but the registry no longer "
                    f"records it"
                )

    return findings


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    result.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    result.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    result.add_argument("--root", type=Path, default=REPO_ROOT)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        findings = audit(registry, args.root, args.manifest)
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
                "manifest": args.manifest.name,
                "verifiedAgainst": registry.get("verifiedAgainst", {}).get("tree"),
                "acceptedCards": registry.get("acceptedCards"),
                "status": "every implementation claim re-derived from the tree",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
