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
* ``VF-CL-04``'s ``ciVerified`` stayed ``false`` with a note whose stated reason was
  "no workflow runs ``tools/collect_s12_acceptance_evidence.py``". By the time this was
  written one does -- ``.github/workflows/s12-acceptance-evidence.yml`` landed with
  ``#283`` -- so the registry was again telling a reader to wait for something that had
  happened. That is rule 7, and it is the same mistake in a field rule 4 did not reach.

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
8. **A candidate tree does not inherit its verification.** ``verifiedAgainst`` may name
   a pre-landing candidate, and then it must say so (``candidate: true``) and name where
   re-verification is due (``reverifyAt``). Once that tree has reached the integration ref
   -- when it is an ancestor of the local ``origin/<reverifyAt>`` tip -- the claim must be
   **re-verified and re-recorded at the landed SHA**, and until it is, this reports. An
   ancestry relation is not a licence to carry a candidate's evidence forward forever.

2. **No blocker may name a merged pull request.** A blocker whose text contains
   ``pr-<n>`` or ``#<n>`` claims to be waiting for it. If that PR is already merged in
   this history the blocker is misstated, which is how #126 slipped through. This is
   the rule that generalises the mistake.
0. **The checkout must be able to answer.** Rules 2 and 4's ancestry read history, and a
   shallow clone has none: the ancestry check fails for want of the commit and the
   merged-pull-request scan sees only the tip. That is reported as itself rather than as
   drift, and never passes quietly.
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
7. **The tree decides ``ciVerified`` too, and a true one must name its run.** Rule 4
   covers ``implemented``; nothing covered the field that said whether CI re-derives the
   card. So the manifest carries ``impliesCiVerified`` with its own ``ciVerifiedChecks``,
   compared the same way -- and a ``null`` must say ``whyCiVerified`` rather than leave a
   gap that reads as coverage. Where it is asserted ``true``, the card must be backed by a **receipt**
   (``tools/record_vf_cl_ci_receipt.py``) that was built from GitHub's own answers about
   one run, and the registry's ``ciVerifiedRun`` must agree with it field for field.

   **The first version of that second half checked the shape of a sentence, and Codex
   showed what that is worth**: an invented run id, a different 40-hex head, a workflow
   nobody runs, invented step names, and all four at once -- five fabrications, zero
   findings. A numeric-looking ``runId`` is not a run. So the rule now compares the
   registry against a file whose fields came from ``gh api``, carries the digests of those
   three documents, and re-measures the one thing a file cannot be trusted about: whether
   the run's head is really in the claimed tree. The artifact's expiry is read too -- a
   claim whose evidence can no longer be fetched has stopped being re-checkable, which is
   the same standard ``aggregate_ac11_evidence.py`` applies with its freshness window.

   **And that is still not enough to say ``true``** (#295 r2 F1). The receipt is built
   offline from JSON the caller passed in, and ``receiptSha256`` is a digest rather than a
   signature: Codex forged a run id in the receipt *and* the registry, recomputed the hash,
   and this tool exited 0. Binding two files to each other proves they agree; it does not
   prove either describes a run that happened. So ``impliesCiVerified: true`` is
   **refused** until an entry carries ``receiptIsAttested`` -- which nothing can yet,
   because the attestation does not exist. A receipt is still read and bound wherever one
   is named, so the facts stay re-checkable as a *measurement record* while the claim stays
   ``false``. Making the claim honest is the follow-up card; the receipt's inputs being an
   authenticated caller's ``gh api`` output (the same boundary
   ``tools/import_ac11_security_scan.py`` declares) is what that card has to close, by
   having CI produce and attest the receipt under ``actions: read``.

   What it does **not** reach: a card whose tests merely ride a whole-directory lane.
   ``pytest tests/core`` says nothing about *which* card's behaviour ran, so a check
   pointing at a lane that runs a directory would read as coverage while asserting
   nothing. Those cards state ``impliesCiVerified: null`` and say that out loud.

6. **A local gap is not a blocker.** ``localUnmeasured`` entries say what was not measured
   here and **where it is measured instead**; the same subject may not also be a blocker.
   The restore drill was filed as an external precondition when it was measured in hosted
   CI all along -- that is the mistake this rule exists for.

   Comparing the gap's subject against blocker text was not enough. The subject is a file
   path and the blocker was a sentence about it, so re-inserting the exact retired string
   ``restore-drill-19-skips-need-CX01_CONTAINER-17-and-INV_TEST_ARCHIVER_IMAGE-2`` matched
   nothing and passed. The manifest therefore names ``forbiddenBlockers`` per card -- every
   id a correction retired -- and any of them open again is drift. It lives in the manifest
   because a file that can edit the list of things it may not say has not been stopped from
   saying them. Each gap also lists ``blockerIdsThisReplaces``, which must be backed by
   that list, so the registry cannot claim a retirement the manifest does not record.

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
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO_ROOT / "docs/vf-cl-task-registry.json"
DEFAULT_MANIFEST = REPO_ROOT / "docs/vf-cl-registry-manifest.json"
MANIFEST_SCHEMA = "vf-cl-registry-manifest:1"
#: What ``tools/record_vf_cl_ci_receipt.py`` writes. Pinned here so a receipt from another
#: shape cannot be read as this one.
RECEIPT_SCHEMA = "vf-cl-ci-receipt:1"
RECEIPT_REPOSITORY = "egparadise/SaintVision-Invion"
#: The receipt's key set, exactly. Not a minimum: a document that may carry extra keys is a
#: document whose digest covers fields nobody reads, and Codex got an unknown top-level key
#: past the first version by re-hashing (#295 r2 F2). Nested shapes are pinned too.
RECEIPT_KEYS = frozenset({
    "schemaVersion", "card", "repository", "workflowPath", "runId", "event", "conclusion",
    "headSha", "headBranch", "claimedTree", "headRelationToClaimedTree", "requiredSteps",
    "artifact", "inputDigests", "recordedAt", "receiptSha256",
})
RECEIPT_ARTIFACT_KEYS = frozenset({"id", "name", "digest", "expiresAt"})
RECEIPT_INPUT_KEYS = frozenset({
    "runMetadataSha256", "jobsMetadataSha256", "artifactMetadataSha256",
})
#: Why no card may derive ``ciVerified: true`` yet (#295 r2 F1, coordinator's call).
#:
#: The receipt is built offline from JSON the caller passed in, and its ``receiptSha256`` is
#: a digest, not a signature -- Codex forged a run id in the receipt *and* the registry,
#: recomputed the hash, and the checker exited 0. Binding two files to each other proves
#: they agree; it does not prove either is about a run that happened. Until a receipt
#: carries something this tool can verify it did not write -- a CI-produced attestation --
#: the honest value is ``false``, and this makes ``true`` unreachable rather than
#: discouraged.
UNATTESTED_RECEIPT = (
    "a receipt built from passed-in JSON cannot carry ciVerified=true: its digest is not a "
    "signature, so a forged run id survives re-hashing. An attested CI-produced receipt is "
    "the follow-up card; until then the honest value is false"
)
#: A receipt names a full commit, like every other sha in this file.
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")

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
#: Fields that must be exactly booleans, and counts that must be exactly whole numbers.
#: `True == 1` and `False == 0` in Python, so `acceptedCards: false` compared equal to the
#: count 0, and `operationallyAccepted: 1` is not `True` by identity, so the card was not
#: counted as accepted while reading as accepted to a person. Both produced no findings.
#: `type(True) is int` is False, so comparing by type covers the counts as well.
BOOLEAN_FIELDS = (
    "locallyVerified",
    "ciVerified",
    "independentlyReviewed",
    "operationallyAccepted",
)
COUNT_FIELDS = ("acceptedCards", "acceptanceDenominator")


class RegistryUnusable(ValueError):
    """The registry cannot be judged, which is not the same as it being wrong."""


def shallow_repository(root: Path) -> bool:
    """Whether this checkout has been truncated.

    Two of the rules read history: the ancestry of ``verifiedAgainst.tree`` and which pull
    requests merged. In a shallow clone the first fails for want of the commit -- which
    read as "not an ancestor", a wrong reason -- and the second silently sees only the tip,
    so a blocker naming a merged pull request goes unnoticed. Neither may pass quietly.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=root, capture_output=True, text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def ancestry(candidate: str, descendant: str, root: Path) -> bool | None:
    """Whether ``candidate`` is in ``descendant``'s history. ``None`` = cannot answer.

    The distinction matters here for the same reason it does for the shallow rule: a
    missing commit answers "no" to ``merge-base`` and that reads as drift. A question this
    clone cannot answer has to be reported as itself.
    """
    for sha in (candidate, descendant):
        if subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            cwd=root, capture_output=True, text=True,
        ).returncode != 0:
            return None
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", candidate, descendant],
        cwd=root, capture_output=True, text=True,
    ).returncode == 0


def remote_tip(ref: str, root: Path) -> str | None:
    """The local clone's answer for ``origin/<ref>``, or None when it does not know.

    Local on purpose: this tool answers questions about files, and reaching the network to
    answer one would make it need a token in lanes that run with ``contents: read``. The
    cost is that a stale clone cannot see a landing yet, which is why not knowing is
    reported rather than treated as "has not landed".
    """
    done = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{ref}"],
        cwd=root, capture_output=True, text=True,
    )
    tip = done.stdout.strip()
    return tip if done.returncode == 0 and tip else None


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
        # Rule 7's half of the entry. Required by key, not by presence of a value: a
        # deleted entry has to be a failure, like every other assertion here.
        if "impliesCiVerified" not in entry:
            raise RegistryUnusable(f"{name} does not say impliesCiVerified")
        ci_implied = entry["impliesCiVerified"]
        if ci_implied is not True and ci_implied is not False and ci_implied is not None:
            raise RegistryUnusable(f"{name}.impliesCiVerified is {ci_implied!r}")
        ci_checks = entry.get("ciVerifiedChecks")
        if not isinstance(ci_checks, list):
            raise RegistryUnusable(f"{name} needs a ciVerifiedChecks array, even an empty one")
        if ci_implied is None and not str(entry.get("whyCiVerified") or "").strip():
            raise RegistryUnusable(f"{name} asserts nothing about ciVerified and does not "
                                   f"say why")
        if ci_implied is not None and not ci_checks:
            raise RegistryUnusable(
                f"{name} claims ciVerified={ci_implied!r} with no ciVerifiedChecks"
            )
        if ci_implied is True:
            # Rule 7c, unconditional on purpose. An opt-out flag here would be a second
            # place to assert the thing the rule exists to stop being asserted; when an
            # attestation this tool can verify exists, this branch is what that card edits.
            raise RegistryUnusable(f"{name}: {UNATTESTED_RECEIPT}")
        if ci_implied is not None and entry.get("ciVerifiedReceipt") is not None:
            # The expectations live here, not in the registry: a file that can choose which
            # workflow and which steps count has not been held to anything.
            expectation = entry.get("ciVerifiedReceipt")
            if not isinstance(expectation, dict):
                raise RegistryUnusable(
                    f"{name}.ciVerifiedReceipt is not an object"
                )
            for field in ("path", "workflowPath", "artifactNamePrefix"):
                if not str(expectation.get(field) or "").strip():
                    raise RegistryUnusable(f"{name}.ciVerifiedReceipt needs {field}")
            steps = expectation.get("requiredSteps")
            if not isinstance(steps, list) or not steps or not all(
                isinstance(step, str) and step.strip() for step in steps
            ):
                raise RegistryUnusable(
                    f"{name}.ciVerifiedReceipt.requiredSteps must name at least one step"
                )
        if not isinstance(entry.get("closedBlockers", {}), dict):
            raise RegistryUnusable(f"{name}.closedBlockers must be an object")
        forbidden = entry.get("forbiddenBlockers", [])
        if not isinstance(forbidden, list) or not all(
            isinstance(value, str) and value.strip() for value in forbidden
        ):
            raise RegistryUnusable(f"{name}.forbiddenBlockers must be a list of ids")
    return manifest


def ci_run_findings(
    identifier: str,
    recorded: object,
    expectation: dict[str, Any],
    claimed_tree: str,
    root: Path,
    now: dt.datetime,
) -> list[str]:
    """Rule 7's second half: the registry's run block must agree with a built receipt.

    Three things are compared, and each closes one of the five fabrications that passed the
    first version:

    * the **receipt** itself -- schema, card, and its own canonical digest, so a value
      edited in one place and not the other is visible;
    * the **expectation** the manifest holds -- which workflow file and which steps count,
      kept out of the registry because a file that chooses its own standard is not held to
      one;
    * the **registry's own block**, field for field against the receipt: a fabricated run
      id or head no longer matches anything.

    And one thing is re-measured rather than read: whether the run's head is really the
    claimed tree or an ancestor of it. The receipt states the relation, but a file's claim
    about ancestry is exactly what git can answer here.
    """
    findings: list[str] = []
    relative = str(expectation.get("path") or "")
    receipt_path = root / relative
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [f"{identifier}.ciVerified is derived true but its receipt {relative} is "
                f"unusable: {type(error).__name__}"]
    if not isinstance(receipt, dict):
        return [f"{identifier}: the receipt {relative} is not an object"]
    if receipt.get("schemaVersion") != RECEIPT_SCHEMA:
        findings.append(f"{identifier}: the receipt declares schemaVersion "
                        f"{receipt.get('schemaVersion')!r}")
    # Strict, and in both directions. An unknown key passed the first version once its
    # digest was recomputed, and a missing nested key simply read as absent (#295 r2 F2).
    if set(receipt) != RECEIPT_KEYS:
        unexpected = sorted(set(receipt) - RECEIPT_KEYS)
        missing = sorted(RECEIPT_KEYS - set(receipt))
        findings.append(
            f"{identifier}: the receipt's key set is not exact"
            + (f"; unexpected {unexpected}" if unexpected else "")
            + (f"; missing {missing}" if missing else "")
        )
    nested = receipt.get("artifact")
    if isinstance(nested, dict) and set(nested) != RECEIPT_ARTIFACT_KEYS:
        findings.append(f"{identifier}: the receipt's artifact key set is not exact: "
                        f"{sorted(set(nested) ^ RECEIPT_ARTIFACT_KEYS)}")
    digests = receipt.get("inputDigests")
    if not isinstance(digests, dict) or set(digests) != RECEIPT_INPUT_KEYS:
        findings.append(f"{identifier}: the receipt's inputDigests key set is not exact")
    elif not all(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in digests.values()
    ):
        findings.append(f"{identifier}: an inputDigests value is not a sha256")
    if receipt.get("card") != identifier:
        findings.append(f"{identifier}: the receipt is for {receipt.get('card')!r}")
    body = {key: value for key, value in receipt.items()
            if key not in ("receiptSha256", "recordedAt")}
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        .encode("utf-8")
    ).hexdigest()
    if receipt.get("receiptSha256") != digest:
        findings.append(f"{identifier}: the receipt's own digest does not match its "
                        f"contents, so it was edited after it was built")
    if receipt.get("repository") != RECEIPT_REPOSITORY:
        findings.append(f"{identifier}: the receipt names repository "
                        f"{receipt.get('repository')!r}")
    if receipt.get("conclusion") != "success":
        findings.append(f"{identifier}: the receipt's run concluded "
                        f"{receipt.get('conclusion')!r}")
    if receipt.get("workflowPath") != expectation.get("workflowPath"):
        findings.append(f"{identifier}: the receipt is a run of "
                        f"{receipt.get('workflowPath')!r}, not "
                        f"{expectation.get('workflowPath')!r}")
    wanted = sorted(expectation.get("requiredSteps") or [])
    if sorted(receipt.get("requiredSteps") or []) != wanted:
        findings.append(f"{identifier}: the receipt's required steps are not the ones the "
                        f"manifest names")
    head = str(receipt.get("headSha") or "")
    if not COMMIT_PATTERN.fullmatch(head):
        findings.append(f"{identifier}: the receipt's headSha is {receipt.get('headSha')!r}")
    artifact = receipt.get("artifact")
    if not isinstance(artifact, dict):
        findings.append(f"{identifier}: the receipt carries no artifact")
        artifact = {}
    else:
        prefix = str(expectation.get("artifactNamePrefix") or "")
        if artifact.get("name") != f"{prefix}{head}":
            findings.append(f"{identifier}: the artifact name {artifact.get('name')!r} is "
                            f"not {prefix}<the run's head>")
        digest_value = str(artifact.get("digest") or "")
        if not digest_value.startswith("sha256:") or not re.fullmatch(
            r"[0-9a-f]{64}", digest_value.removeprefix("sha256:")
        ):
            findings.append(f"{identifier}: the artifact digest is "
                            f"{artifact.get('digest')!r}")
        expires = artifact.get("expiresAt")
        try:
            moment = dt.datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
        except ValueError:
            findings.append(f"{identifier}: the artifact expiresAt is {expires!r}")
        else:
            if moment.tzinfo is None or moment.astimezone(dt.timezone.utc) <= now:
                # Not pedantry: the claim is "CI showed this", and an artifact nobody can
                # fetch any more cannot show it again. Re-derive and re-record.
                findings.append(f"{identifier}: the artifact that backs this claim expired "
                                f"at {expires}, so the claim is no longer re-checkable")

    # The relation to the tree the registry is about, measured here rather than believed.
    if claimed_tree and head and COMMIT_PATTERN.fullmatch(head):
        stated = str(receipt.get("claimedTree") or "")
        if not stated.startswith(claimed_tree) and not claimed_tree.startswith(stated):
            findings.append(f"{identifier}: the receipt is about tree {stated[:12]!r}, not "
                            f"the registry's {claimed_tree[:12]!r}")
        else:
            relation = ancestry(head, stated or claimed_tree, root)
            if relation is None:
                findings.append(f"{identifier}: this clone cannot tell whether the run's "
                                f"head is in the claimed tree")
            elif not relation:
                findings.append(f"{identifier}: the run's head is not in the claimed tree")

    # And the registry's own block, which is what a reader sees first.
    if not isinstance(recorded, dict):
        findings.append(f"{identifier}.ciVerified is derived true but it names no "
                        f"ciVerifiedRun")
        return findings
    for field, expected in (
        ("runId", receipt.get("runId")),
        ("headSha", receipt.get("headSha")),
        ("workflowPath", receipt.get("workflowPath")),
        ("conclusion", receipt.get("conclusion")),
        ("receipt", relative),
    ):
        if recorded.get(field) != expected:
            findings.append(f"{identifier}.ciVerifiedRun.{field} is "
                            f"{recorded.get(field)!r} but the receipt says {expected!r}")
    if sorted(recorded.get("requiredSteps") or []) != sorted(receipt.get("requiredSteps") or []):
        findings.append(f"{identifier}.ciVerifiedRun.requiredSteps differs from the receipt")
    block_artifact = recorded.get("artifact")
    if not isinstance(block_artifact, dict):
        findings.append(f"{identifier}.ciVerifiedRun names no artifact")
    else:
        for field in ("id", "digest"):
            if block_artifact.get(field) != artifact.get(field):
                findings.append(f"{identifier}.ciVerifiedRun.artifact.{field} differs from "
                                f"the receipt")
    return findings


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
    # Reported, not worked around: a truncated checkout cannot re-derive history, and
    # saying so is the honest outcome. The hosted job that runs this check is configured
    # with full history so the rules below actually run.
    truncated = shallow_repository(root)
    if truncated:
        findings.append(
            "this is a shallow checkout, so the two history rules could not be "
            "re-derived: neither the ancestry of verifiedAgainst.tree nor which pull "
            "requests merged is knowable here. Check out with full history "
            "(actions/checkout fetch-depth: 0)."
        )
    merged = set() if truncated else merged_pull_requests(root)

    verified = registry.get("verifiedAgainst")
    if not isinstance(verified, dict) or not verified.get("tree"):
        findings.append("the registry does not say which tree it was verified against")
    elif truncated:
        # Already reported above. Adding "not an ancestor" here would name a wrong reason
        # for a missing commit, which is what sent this check to CI as a false drift.
        pass
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

    # Rule 8: a candidate tree does not inherit its verification.
    if isinstance(verified, dict) and verified.get("candidate") is not None:
        if verified.get("candidate") is not True:
            findings.append(
                f"verifiedAgainst.candidate is {verified.get('candidate')!r}, which is not "
                f"true or absent"
            )
        else:
            reverify = str(verified.get("reverifyAt") or "")
            tree = str(verified.get("tree") or "")
            if not reverify:
                findings.append(
                    "verifiedAgainst is a pre-landing candidate and does not say "
                    "reverifyAt"
                )
            elif truncated:
                pass                                    # already reported, same reason
            else:
                tip = remote_tip(reverify, root)
                if tip is None:
                    findings.append(
                        f"verifiedAgainst.candidate cannot be judged: this clone does not "
                        f"know origin/{reverify}"
                    )
                else:
                    landed = ancestry(tree, tip, root)
                    if landed is None:
                        findings.append(
                            f"verifiedAgainst.candidate cannot be judged: the tree or "
                            f"origin/{reverify} is missing from this clone"
                        )
                    elif landed:
                        findings.append(
                            f"verifiedAgainst.tree {tree} has reached origin/{reverify}, so "
                            f"it is no longer a candidate: re-verify at the landed SHA and "
                            f"re-record (an ancestry relation does not carry the "
                            f"verification forward)"
                        )

    for field in COUNT_FIELDS:
        value = registry.get(field)
        if type(value) is not int:
            findings.append(f"{field} is {value!r}, which is not a whole number")

    accepted = [card for card in registry["cards"]
                if card.get("operationallyAccepted") is True]
    declared = registry.get("acceptedCards")
    if type(declared) is int and declared != len(accepted):
        # Stated rather than counted, this is the one number a reader takes at face value.
        findings.append(
            f"acceptedCards says {declared!r} but {len(accepted)} card(s) are "
            f"operationallyAccepted"
        )
    denominator = registry.get("acceptanceDenominator")
    if type(denominator) is int and denominator != len(registry["cards"]):
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
        for field in BOOLEAN_FIELDS:
            if field in card and type(card[field]) is not bool:
                findings.append(
                    f"{identifier}.{field} is {card[field]!r}, which is not true or false"
                )
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

        # Rule 7: the same comparison for the field that says whether CI re-derives this
        # card. Separate checks, because the files that show a thing is implemented are not
        # the files that show CI runs it.
        ci_implied = entry["impliesCiVerified"]
        ci_broken = [problem for problem in
                     (run_check(check, root) for check in entry.get("ciVerifiedChecks") or [])
                     if problem]
        if ci_broken:
            findings.append(
                f"{identifier}: the manifest's ciVerified assertion no longer holds in the "
                f"tree: " + "; ".join(ci_broken)
            )
        elif ci_implied is not None and card.get("ciVerified") is not ci_implied:
            findings.append(
                f"{identifier}: the tree shows ciVerified={ci_implied!r} but the registry "
                f"says {card.get('ciVerified')!r}"
            )
        if (entry.get("ciVerifiedReceipt") or {}).get("path"):
            findings.extend(ci_run_findings(
                identifier,
                card.get("ciVerifiedRun"),
                entry.get("ciVerifiedReceipt") or {},
                str((registry.get("verifiedAgainst") or {}).get("tree") or ""),
                root,
                dt.datetime.now(dt.timezone.utc),
            ))

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
        forbidden = entry.get("forbiddenBlockers") or []
        for blocker in sorted(set(forbidden) & set(open_blockers)):
            findings.append(
                f"{identifier}: {blocker} was retired by a correction and is open again"
            )
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
            # The ids this gap retired. Checked against the manifest, so the registry cannot
            # shorten its own list of retired blockers, and against the open ones, so a
            # revival is reported beside the gap it contradicts.
            replaces = gap.get("blockerIdsThisReplaces")
            if not isinstance(replaces, list) or not replaces:
                findings.append(
                    f"{identifier}: the local gap for {subject} does not say which blocker "
                    f"ids it replaced"
                )
                continue
            unbacked = sorted(set(replaces) - set(forbidden))
            if unbacked:
                findings.append(
                    f"{identifier}: the local gap for {subject} claims to replace "
                    f"{', '.join(unbacked)}, which the manifest does not list as retired"
                )
            still_open = sorted(set(replaces) & set(open_blockers))
            if still_open:
                findings.append(
                    f"{identifier}: {subject} is recorded as measured in {where} while "
                    f"{', '.join(still_open)} is still open"
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
                "status": "every implementation and ciVerified claim re-derived from the tree",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
