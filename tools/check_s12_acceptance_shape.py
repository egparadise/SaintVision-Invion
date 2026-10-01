"""Hold a CI-derived S12 acceptance bundle to its shape and its derivation, never to its answer.

``tools/collect_s12_acceptance_evidence.py`` sorts the AC-12 items into PASS / FAIL /
NOT_OBSERVED / BLOCKED_EXTERNAL. Until the external waits clear, the honest verdict is
``FAIL`` or ``PASS_MEASURED_PARTIAL`` -- so a gate that demanded a good verdict would be red
forever and would be deleted, and a gate that demanded nothing would pass on a bundle with
items missing. This one asserts what must be true of any bundle whatever the answer.

**Why it got stricter.** The first version checked the item set and nothing else, and Codex
measured the hole: a hand-written bundle carrying ``verdict: FABRICATED_PASS``, no ``codeSha``,
no ``provenance``, and all seventeen items PASS with ``source: typed-by-human`` was *accepted*.
The checker was asserting that a file listed the right seventeen names -- which a person can
type. A gate on a derived artefact has to bind the artefact to the derivation:

* **the verdict is one the collector can emit, and is the one the collector's own rule produces
  from these items.** ``overall_verdict`` is imported rather than restated, so the claim is
  "this is what this collector would have concluded from these items", not "this matches a rule
  someone copied here". An invented word dies, and so does a real ``PASS`` over FAILing items;
* **the reader-facing ``scope`` lists are recomputed from the items too.** Those lists are what
  a summary quotes, and an item moved between them without moving its status is a lie no reader
  can see;
* **every item's ``source`` is the tool the collector's catalogue names for it**, and the two
  the VF-CL registry singled out are additionally checked against literals here and must name a
  tool that exists in this tree. ``typed-by-human`` dies;
* **``codeSha``, ``provenance.commit_sha`` and the file's own name agree with the head CI
  checked out** (``--expected-head``). A bundle describing another commit cannot be presented as
  this head's evidence, and the gate cannot be pointed at a different file in the directory;
* **the provenance says a clean, pushed checkout with no opt-out used** -- the collector refuses
  a dirty tree or an unreachable head unless told otherwise, and records the override when told;
  this gate refuses the override. Evidence nobody can check out is not evidence;
* **``provenance.collectorSha256`` is the digest of the collector in this tree.** The bundle
  names the bytes that produced it, and the gate reads those bytes.

**What this cannot prove.** It cannot prove the file came out of the collector rather than being
typed to look as though it had: every field above is computable by whoever wants to forge one.
What makes the bundle evidence is that CI runs the collector and this gate in the same job on a
checkout of the head, and the bindings make a forgery require a code change that review sees.
A gate claiming more than that would be the same mistake in a new place.

It still judges nothing about *which* status an item has, and nothing about whether the verdict
is good. That is the measurement, and the point of running the collector in CI is that CI
derives it rather than a person typing the answer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:  # run as a script, imported by a test, either way
    sys.path.insert(0, str(TOOLS))

from collect_s12_acceptance_evidence import (  # noqa: E402
    AC12_ITEMS,
    EXIT_BY_VERDICT,
    EXTERNAL_ITEMS,
    overall_verdict,
    scope as status_scope,
)

#: The collector whose output this checks. Its bytes are hashed, so the bundle names the
#: program that produced it and this gate reads that program.
COLLECTOR = TOOLS / "collect_s12_acceptance_evidence.py"

SCHEMA = "s12-db-acceptance-evidence:1"
STATUSES = frozenset({"PASS", "FAIL", "NOT_OBSERVED", "BLOCKED_EXTERNAL"})

#: PASS / PASS_MEASURED_PARTIAL / FAIL / NOT_OBSERVED, taken from the collector's exit table
#: rather than retyped: ``main`` ends with ``EXIT_BY_VERDICT[verdict]``, so a verdict outside
#: this set is one the collector could not have reached without raising on its way out.
VERDICTS = frozenset(EXIT_BY_VERDICT)

HEX40 = re.compile(r"^[0-9a-f]{40}$")

#: The seventeen AC-12 items the collector sorts. Written out rather than counted so a
#: removal fails here instead of changing a number nobody reads. Measured at 8d5a7d9b.
EXPECTED_ITEMS = (
    "admission-gates-observed-open",
    "authenticated-browser-acceptance-on-physical-node",
    "contributed-folders-checked",
    "database-recovery-drill-passed-with-targets",
    "five-node-full-journey",
    "known-limitations-recorded",
    "offer-agreement",
    "operational-inputs-present",
    "operational-rpo-rto-measured",
    "pitr-configuration-possible",
    "pitr-rehearsal-dry-run-observed",
    "real-pitr-target-time-recovery",
    "release-manifest-recorded",
    "user-acceptance-record-ac12",
    "verified-backup-in-retention",
    "verified-off-site-backup",
    "web-smoke-journeys",
)

#: Which tool each item's answer comes from, read from the collector's own catalogue so a
#: renamed source does not need editing in two places. External items name none: nothing in
#: this repository can observe five physical nodes, and a source string there would imply
#: something had.
EXPECTED_SOURCES: dict[str, str | None] = {
    **{spec["id"]: spec.get("source") for spec in AC12_ITEMS},
    **{spec["id"]: None for spec in EXTERNAL_ITEMS},
}

#: The two observations the VF-CL registry recorded as "produced by hand; CI never re-derives
#: them". Their exact source tools are literals here, independent of the catalogue above, and
#: each must be a file in ``tools/``: this checker is the evidence for that specific claim, so
#: it does not get to take the claim from the thing it is checking.
CI_DERIVED_CLAIM = {
    "pitr-configuration-possible": "pitr_readiness",
    "pitr-rehearsal-dry-run-observed": "pitr_opt_in_dry_run",
}

#: What the provenance must say for the bundle to describe a checkout a reader can reproduce.
#: The collector refuses a dirty tree and an unreachable head unless given an explicit
#: opt-out, and records the opt-out when given one; CI is where no opt-out is acceptable.
CLEAN_PROVENANCE = {
    "working_tree_clean_status": True,
    "content_clean_diff": True,
    "dirtyTreeAllowed": False,
    "unpushedHeadAllowed": False,
    "remoteReachable": True,
}

#: A libpq DSN or a bare password in a URL. The collector redacts before serialising and
#: re-checks its own text; this is the independent re-read of the file that shipped.
SECRET = re.compile(
    r"postgres(?:ql)?://[^\s\"\\]*:[^\s\"\\@]+@|password=[^\s\"\\&]+",
    re.IGNORECASE,
)


class ShapeRefused(SystemExit):
    """The bundle cannot be accepted as a bundle. Not a judgement on its verdict."""

    def __init__(self, message: str) -> None:
        super().__init__(f"REFUSED: {message}")


def collector_digest(collector: Path = COLLECTOR) -> str:
    """The sha256 the collector writes into its own provenance, read from the file."""

    return hashlib.sha256(collector.read_bytes()).hexdigest()


def _check_items(items: dict) -> None:
    missing = [name for name in EXPECTED_ITEMS if name not in items]
    if missing:
        raise ShapeRefused(
            "these AC-12 items are absent, which removes them from the scope lists and reads "
            f"as progress: {sorted(missing)}"
        )
    unknown = sorted(set(items) - set(EXPECTED_ITEMS))
    if unknown:
        raise ShapeRefused(
            f"these items are not in the expected set, so the checker cannot say the scope is "
            f"complete: {unknown}"
        )
    unrecognised = sorted(
        name for name, item in items.items()
        if not isinstance(item, dict) or item.get("status") not in STATUSES
    )
    if unrecognised:
        raise ShapeRefused(f"these items carry no recognised status: {unrecognised}")


def _check_sources(items: dict) -> None:
    for name, expected in CI_DERIVED_CLAIM.items():
        source = items[name].get("source")
        if source in (None, ""):
            raise ShapeRefused(
                f"{name} names no source tool, so nothing says CI derived it rather than a "
                f"person typing the answer"
            )
        if source != expected:
            raise ShapeRefused(
                f"{name} says it came from {source!r}, but the registry's claim is that CI "
                f"derives it with {expected!r}; any other string is somebody's word for it"
            )
        if not (TOOLS / f"{expected}.py").exists():
            raise ShapeRefused(
                f"{name} names {expected!r}, which is not a tool in this tree, so the source "
                f"cannot have run here"
            )
    wrong = sorted(
        f"{name}: {items[name].get('source')!r} != {EXPECTED_SOURCES[name]!r}"
        for name in EXPECTED_ITEMS
        if items[name].get("source") != EXPECTED_SOURCES[name]
    )
    if wrong:
        raise ShapeRefused(
            "these items do not come from the tool the collector's catalogue names for them, "
            f"so the bundle describes a derivation that did not happen: {wrong}"
        )


def _check_verdict(document: dict, items: dict) -> str:
    verdict = document.get("verdict")
    if verdict not in VERDICTS:
        raise ShapeRefused(
            f"verdict is {verdict!r}, which is not one the collector can emit "
            f"({sorted(VERDICTS)}); a word outside that set was written by something else"
        )
    recomputed = overall_verdict(items)
    if verdict != recomputed:
        raise ShapeRefused(
            f"verdict says {verdict!r} but these items produce {recomputed!r}; the verdict is "
            "not judged here, and it still has to be the one the items add up to"
        )
    stated = document.get("scope")
    if not isinstance(stated, dict):
        raise ShapeRefused("scope must be an object listing the items under each status")
    expected = {status: sorted(names) for status, names in status_scope(items).items()}
    narrowed = {status: sorted(stated.get(status) or []) for status in expected}
    if narrowed != expected:
        differs = sorted(status for status in expected if narrowed[status] != expected[status])
        raise ShapeRefused(
            f"the scope lists disagree with the item statuses under {differs}; those lists are "
            "what a summary quotes, so an item moved between them is a claim no reader can check"
        )
    return recomputed


def _check_code_sha(document: dict) -> str:
    code_sha = document.get("codeSha")
    if not isinstance(code_sha, str) or not HEX40.fullmatch(code_sha):
        raise ShapeRefused(
            f"codeSha is {code_sha!r}; evidence that does not say which commit it describes "
            "cannot be checked against anything"
        )
    return code_sha


def _check_head(code_sha: str, provenance: dict, expected_head: str | None) -> None:
    if provenance.get("commit_sha") != code_sha:
        raise ShapeRefused(
            f"provenance.commit_sha is {provenance.get('commit_sha')!r} but codeSha is "
            f"{code_sha!r}; the bundle names two different heads"
        )
    if expected_head is not None and code_sha != expected_head.lower():
        raise ShapeRefused(
            f"this bundle describes {code_sha} but the head under test is {expected_head}; "
            "evidence for one commit is not evidence for another"
        )


def _check_provenance(provenance: dict, collector: Path) -> None:
    for key, required in CLEAN_PROVENANCE.items():
        if provenance.get(key) is not required:
            raise ShapeRefused(
                f"provenance.{key} is {provenance.get(key)!r}, expected {required!r}: CI "
                "evidence must come from a clean, pushed checkout with no opt-out recorded"
            )
    if provenance.get("modified_paths"):
        raise ShapeRefused(
            f"provenance.modified_paths is {provenance.get('modified_paths')!r}; the tree that "
            "produced this bundle was not the tree at that commit"
        )
    for key in ("executor", "timestamp_kst"):
        if not provenance.get(key):
            raise ShapeRefused(f"provenance.{key} is empty, so nothing says who ran this or when")
    digest = provenance.get("collectorSha256")
    actual = collector_digest(collector)
    if digest != actual:
        raise ShapeRefused(
            f"provenance.collectorSha256 is {digest!r} but {collector.name} in this tree hashes "
            f"to {actual}; the bundle was not produced by the collector being reviewed"
        )


def check(
    document: dict,
    raw: str,
    *,
    expected_head: str | None = None,
    collector: Path = COLLECTOR,
) -> dict:
    if document.get("schemaVersion") != SCHEMA:
        raise ShapeRefused(f"schemaVersion is {document.get('schemaVersion')!r}, expected {SCHEMA!r}")
    if document.get("acceptanceClaim") is not False:
        raise ShapeRefused(
            "acceptanceClaim must be exactly false; this bundle feeds a review and does not "
            f"close AC-12 (saw {document.get('acceptanceClaim')!r})"
        )
    items = document.get("items")
    if not isinstance(items, dict):
        raise ShapeRefused("items must be an object keyed by item id")
    _check_items(items)
    _check_sources(items)
    recomputed = _check_verdict(document, items)
    code_sha = _check_code_sha(document)
    provenance = document.get("provenance")
    if not isinstance(provenance, dict):
        raise ShapeRefused(
            "provenance is absent, so the bundle says nothing about the checkout it came from"
        )
    _check_head(code_sha, provenance, expected_head)
    _check_provenance(provenance, collector)
    leak = SECRET.search(raw)
    if leak:
        raise ShapeRefused("a connection string or password reached the evidence file")
    counted = {name: item["status"] for name, item in items.items()}
    return {
        "schemaVersion": SCHEMA,
        "codeSha": document.get("codeSha"),
        "expectedHead": expected_head,
        "verdict": document.get("verdict"),
        "verdictRecomputedFromItems": recomputed,
        "acceptanceClaim": document.get("acceptanceClaim"),
        "items": len(items),
        "byStatus": {
            status: sorted(name for name, value in counted.items() if value == status)
            for status in sorted(STATUSES)
        },
        "ciDerived": {name: counted[name] for name in CI_DERIVED_CLAIM},
        "ciDerivedSources": {name: items[name].get("source") for name in CI_DERIVED_CLAIM},
        "collectorSha256": provenance.get("collectorSha256"),
        "provenance": {key: provenance.get(key) for key in (*CLEAN_PROVENANCE, "executor", "timestamp_kst")},
        "status": (
            "shape accepted: items complete, sources named, verdict equals the collector's own "
            "rule over these items, head and provenance bound. Whether the verdict is good is "
            "the measurement and is not judged here"
        ),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    result.add_argument("evidence", type=Path, help="the collector's JSON bundle")
    result.add_argument(
        "--expected-head",
        default=None,
        help="the commit CI checked out; the bundle's codeSha, provenance.commit_sha and file "
             "name must all be this commit (required unless --allow-unbound-head)",
    )
    result.add_argument(
        "--allow-unbound-head",
        action="store_true",
        help="explicit opt-out: check a bundle without binding it to a head (recorded in the "
             "output). CI always passes --expected-head",
    )
    result.add_argument(
        "--collector",
        type=Path,
        default=COLLECTOR,
        help="the collector whose digest the bundle must carry (default: the one beside this "
             "checker; name another when checking a bundle an older collector produced)",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.expected_head and not args.allow_unbound_head:
        print(
            "REFUSED: --expected-head is required so the bundle is bound to the commit under "
            "test (pass --allow-unbound-head to record an explicit opt-out)",
            file=sys.stderr,
        )
        return 2
    head = (args.expected_head or "").lower().strip() or None
    if head and not HEX40.fullmatch(head):
        print(f"REFUSED: --expected-head {args.expected_head!r} is not a 40-hex commit", file=sys.stderr)
        return 2
    # The file, not only its contents: the workflow picks the bundle with a glob, and a bundle
    # for another commit sitting in the same directory would otherwise be checked and passed.
    if head and head[:12] not in args.evidence.stem:
        raise ShapeRefused(
            f"{args.evidence.name} is not named for {head[:12]}, so the glob did not find this "
            "head's bundle"
        )
    raw = args.evidence.read_text(encoding="utf-8")
    summary = check(json.loads(raw), raw, expected_head=head, collector=args.collector)
    if head is None:
        summary["status"] = "head binding NOT checked (--allow-unbound-head); " + summary["status"]
    print(json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
