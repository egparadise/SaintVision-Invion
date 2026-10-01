"""Assemble the AC-11 aggregator's manifest from the axis envelopes that exist.

``tools/aggregate_ac11_evidence.py`` recomputes all eight AC-11 axes and refuses the
aggregation unless every one of them is present. Nothing has ever called it: the 48-task
rescore records the recomputed PASS count as 0/8 and says why -- there is no CI path, so
the aggregation has not run, which is a different statement from "the axes fail". This
tool is the missing input. It reads ``docs/ac11-axis-sources.json`` (where each axis
envelope comes from, measured from the tree), collects the envelopes an operator or a CI
lane has downloaded, and writes the manifest.

**It refuses rather than omits.** An axis whose envelope is missing is reported by name
with the reason the sources file records, and the manifest is still written so the
aggregator produces its own fail-closed verdict over what exists. The two answers are
different and both are wanted: this tool says *which envelopes it could not assemble*, and
the aggregator says *what the evidence shows*. Silently dropping an axis would turn an
INVALID_RUN into a smaller-looking PASS.

What it refuses outright, each because the manifest would otherwise claim something untrue:

* an envelope whose ``sourceHeadSha`` is not the SHA being aggregated -- evidence about
  another tree, which is the one mistake the whole AC-11 chain is built to prevent;
* an envelope whose ``artifactObservedSha256`` differs from its ``artifactSha256`` -- the
  importer's binding already failed and the value cannot be trusted;
* an expired artifact -- a claim nobody can fetch again has stopped being re-checkable;
* two envelopes for the same axis, or an envelope for an axis the aggregator does not know;
* a duplicate JSON key anywhere in its inputs. ``json.loads`` keeps the last of two
  identical keys, so a file that reads differently depending on who reads it is not
  evidence.

Offline, like every importer in this chain: the caller fetches artifacts with ``gh`` and
passes a directory. The residual trust boundary is the same one
``tools/import_ac11_security_scan.py`` declares.

Exit codes: 0 the manifest was written, 2 the inputs do not support writing one.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.aggregate_ac11_evidence import (  # noqa: E402
    AXIS_PURPOSE,
    REQUIRED_AXES,
    RUN_PURPOSE,
    SCHEMA_VERSION,
)

SOURCES_SCHEMA = "ac11-axis-sources:1"
DEFAULT_SOURCES = REPO_ROOT / "docs/ac11-axis-sources.json"
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CHAINS = ("complete", "incomplete", "absent")
#: Every key an axis entry must carry, exactly. A missing key is a gap that reads as
#: coverage; an unexpected one is a field nobody validates.
SOURCE_KEYS = frozenset({
    "axis", "chain", "workflow", "producer", "importer", "importerArchiveFlag",
    "artifactNamePrefix", "envelopeMember", "importerEmitsAxes", "envelopeShape", "reason",
})
#: The top-level keys of the axis map, exactly. An unknown one is a field nobody validates,
#: and ``repository`` was readable as anything at all before this (#299 r1).
SOURCES_TOP_KEYS = frozenset({"schemaVersion", "purpose", "note", "repository", "axes"})
#: What an importer writes. ``axis-evidence`` is one envelope; ``axes-bundle`` is a wrapper
#: whose ``axes`` array holds them; ``not-an-axis-envelope`` says the output cannot be
#: aggregated at all, which is a reason for ``incomplete`` rather than a shape to read.
ENVELOPE_SHAPES = ("axis-evidence", "axes-bundle", "not-an-axis-envelope")
#: The one repository this chain's artifacts come from. Pinned, because an axis map that can
#: name another repository can point a lane at someone else's runs.
REPOSITORY = "egparadise/SaintVision-Invion"
#: ``runPurpose`` of a bundle that carries axis envelopes inside it.
BUNDLE_PURPOSES = frozenset({
    "ac11-migration-rehearsal-import",
})


class Refused(RuntimeError):
    """The manifest cannot be written, which is not the same as the axes failing."""


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise Refused(f"duplicate JSON key {key!r}")
        seen[key] = value
    return seen


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates)
    except Refused as refusal:
        raise Refused(f"{label}: {refusal}") from None
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Refused(f"{label} is unreadable: {type(error).__name__}") from None
    if not isinstance(value, dict):
        raise Refused(f"{label} must be a JSON object")
    return value


def load_sources(path: Path) -> list[dict[str, Any]]:
    """The axis map, validated strictly.

    Strict because this file decides which envelopes a lane goes looking for: an axis
    missing from it is an axis nobody collects, and that would look like an absent
    envelope rather than a missing instruction.
    """
    document = read_json(path, "the axis sources")
    if document.get("schemaVersion") != SOURCES_SCHEMA:
        raise Refused(f"the axis sources must declare schemaVersion {SOURCES_SCHEMA}")
    if set(document) != SOURCES_TOP_KEYS:
        unexpected = sorted(set(document) - SOURCES_TOP_KEYS)
        missing = sorted(SOURCES_TOP_KEYS - set(document))
        raise Refused(
            "the axis sources' top-level key set is not exact"
            + (f"; unexpected {unexpected}" if unexpected else "")
            + (f"; missing {missing}" if missing else "")
        )
    if document["repository"] != REPOSITORY:
        raise Refused(f"the axis sources name repository {document['repository']!r}")
    for field in ("purpose", "note"):
        if not isinstance(document[field], str) or not document[field].strip():
            raise Refused(f"the axis sources' {field} must be a non-empty string")
    axes = document.get("axes")
    if not isinstance(axes, list) or not axes:
        raise Refused("the axis sources must carry a non-empty axes list")
    seen: set[str] = set()
    for entry in axes:
        if not isinstance(entry, dict):
            raise Refused("an axis entry is not an object")
        if set(entry) != SOURCE_KEYS:
            unexpected = sorted(set(entry) - SOURCE_KEYS)
            missing = sorted(SOURCE_KEYS - set(entry))
            raise Refused(
                f"axis entry {entry.get('axis')!r} key set is not exact"
                + (f"; unexpected {unexpected}" if unexpected else "")
                + (f"; missing {missing}" if missing else "")
            )
        axis = entry["axis"]
        if axis not in REQUIRED_AXES:
            raise Refused(f"{axis!r} is not an AC-11 axis")
        if axis in seen:
            raise Refused(f"the axis sources name {axis!r} twice")
        seen.add(axis)
        if entry["chain"] not in CHAINS:
            raise Refused(f"{axis}: chain is {entry['chain']!r}")
        if entry["envelopeShape"] is not None and entry["envelopeShape"] not in ENVELOPE_SHAPES:
            raise Refused(f"{axis}: envelopeShape is {entry['envelopeShape']!r}")
        emits = entry["importerEmitsAxes"]
        if not isinstance(emits, list) or not all(
            isinstance(value, str) and value in REQUIRED_AXES for value in emits
        ):
            raise Refused(f"{axis}: importerEmitsAxes names something that is not an axis")
        if emits and axis not in emits:
            raise Refused(f"{axis}: importerEmitsAxes does not include this axis")
        for field in ("workflow", "producer", "importer"):
            value = entry[field]
            if value is not None and not (REPO_ROOT / value).is_file():
                raise Refused(f"{axis}: {field} {value} is not in the tree")
        if entry["importer"]:
            # Bound to the importer's own source: the names it writes have to be the names
            # claimed here. The security importer names no axis at all, which is exactly how
            # its chain was mis-classified as complete (#299 r1).
            source = (REPO_ROOT / entry["importer"]).read_text(encoding="utf-8")
            producer_source = (
                (REPO_ROOT / entry["producer"]).read_text(encoding="utf-8")
                if entry["producer"] else ""
            )
            for named in emits:
                if f'"{named}"' not in source and f'"{named}"' not in producer_source:
                    raise Refused(
                        f"{axis}: importerEmitsAxes claims {named!r} but neither "
                        f"{entry['importer']} nor the producer names it"
                    )
        if entry["envelopeMember"]:
            # The member lives inside the artifact zip, so the tree cannot hold it -- but the
            # workflow that uploads it names it, and that is checkable here.
            if not entry["workflow"]:
                raise Refused(f"{axis}: envelopeMember without a workflow that writes it")
            workflow_text = (REPO_ROOT / entry["workflow"]).read_text(encoding="utf-8")
            if entry["envelopeMember"] not in workflow_text:
                raise Refused(
                    f"{axis}: {entry['workflow']} does not name {entry['envelopeMember']!r}"
                )
        if entry["chain"] == "complete":
            for field in ("workflow", "producer", "importer", "importerArchiveFlag",
                          "artifactNamePrefix", "envelopeMember"):
                if not str(entry.get(field) or "").strip():
                    raise Refused(f"{axis}: a complete chain needs {field}")
            if not (REPO_ROOT / entry["importer"]).is_file():
                raise Refused(f"{axis}: importer {entry['importer']} is not in the tree")
            if not (REPO_ROOT / entry["workflow"]).is_file():
                raise Refused(f"{axis}: workflow {entry['workflow']} is not in the tree")
            # The two importers in this chain take the zip under different names
            # (``--artifact-zip`` and ``--archive``). The lane reads the name from here
            # rather than trying both: a fallback that retries on any failure would turn a
            # real refusal into a second attempt with the wrong flag.
            if entry["importerArchiveFlag"] not in ("--artifact-zip", "--archive"):
                raise Refused(
                    f"{axis}: importerArchiveFlag is {entry['importerArchiveFlag']!r}"
                )
            if entry["envelopeShape"] not in ("axis-evidence", "axes-bundle"):
                # A chain is not complete when its importer's output cannot be aggregated.
                raise Refused(
                    f"{axis}: a complete chain needs an admissible envelopeShape, not "
                    f"{entry['envelopeShape']!r}"
                )
        elif not str(entry.get("reason") or "").strip():
            # An axis that cannot be collected has to say why here, or the aggregator's
            # refusal arrives with no explanation attached to it.
            raise Refused(f"{axis}: a {entry['chain']} chain must give a reason")
    missing_axes = sorted(set(REQUIRED_AXES) - seen)
    if missing_axes:
        raise Refused("the axis sources do not cover: " + ", ".join(missing_axes))
    return axes


def read_envelopes(directory: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    """Every ``*.json`` in the directory that claims to be an axis envelope, by axis."""
    if not directory.is_dir():
        raise Refused(f"the envelope directory {directory} does not exist")
    found: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(directory.glob("*.json")):
        document = read_json(path, f"the envelope {path.name}")
        purpose = document.get("runPurpose")
        if purpose in BUNDLE_PURPOSES:
            # A bundle: the importer wrapped its axis envelopes in an ``axes`` array. The
            # first version read only single envelopes and skipped these with ``continue``,
            # so the migration rehearsal's two axes were silently dropped even when the
            # artifact was there (#299 r1) -- the exact failure this module's docstring says
            # it must not have.
            rows = document.get("axes")
            if not isinstance(rows, list) or not rows:
                raise Refused(f"{path.name} is a {purpose} bundle with no axes array")
            for row in rows:
                if not isinstance(row, dict):
                    raise Refused(f"{path.name} has an axes entry that is not an object")
                if row.get("runPurpose") != AXIS_PURPOSE:
                    raise Refused(
                        f"{path.name} carries an axes entry whose runPurpose is "
                        f"{row.get('runPurpose')!r}"
                    )
                _record(found, path, row)
            continue
        if purpose != AXIS_PURPOSE:
            # Not an axis envelope and not a bundle. Reported rather than skipped: a file
            # the operator downloaded and this tool ignored is how an axis goes missing
            # while the artifact is right there.
            raise Refused(
                f"{path.name} has runPurpose {purpose!r}, which is neither an axis envelope "
                f"nor a bundle this tool can read"
            )
        _record(found, path, document)
    return found


def _record(
    found: dict[str, tuple[Path, dict[str, Any]]], path: Path, envelope: dict[str, Any]
) -> None:
    axis = str(envelope.get("axis") or "")
    if axis not in REQUIRED_AXES:
        raise Refused(f"{path.name} claims axis {axis!r}, which AC-11 does not have")
    if axis in found:
        raise Refused(f"two envelopes claim axis {axis!r}: {found[axis][0].name}, {path.name}")
    found[axis] = (path, envelope)


def check_envelope(axis: str, envelope: dict[str, Any], release_sha: str, now: dt.datetime) -> None:
    source = str(envelope.get("sourceHeadSha") or "")
    if not SHA1.fullmatch(source):
        raise Refused(f"{axis}: sourceHeadSha is {envelope.get('sourceHeadSha')!r}")
    if source != release_sha:
        raise Refused(
            f"{axis}: the envelope is about {source[:12]}, not the SHA being aggregated "
            f"({release_sha[:12]})"
        )
    digest = str(envelope.get("artifactSha256") or "")
    observed = str(envelope.get("artifactObservedSha256") or "")
    if not SHA256.fullmatch(digest):
        raise Refused(f"{axis}: artifactSha256 is {envelope.get('artifactSha256')!r}")
    if observed != digest:
        raise Refused(f"{axis}: the downloaded artifact digest does not match the envelope")
    if envelope.get("artifactAvailable") is not True:
        raise Refused(f"{axis}: the envelope says its artifact is unavailable")
    expires = envelope.get("artifactExpiresAt")
    try:
        moment = dt.datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
    except ValueError:
        raise Refused(f"{axis}: artifactExpiresAt is {expires!r}") from None
    if moment.tzinfo is None or moment.astimezone(dt.timezone.utc) <= now:
        raise Refused(f"{axis}: the artifact expired at {expires}")


def assemble(
    *, sources: list[dict[str, Any]], envelopes: dict[str, tuple[Path, dict[str, Any]]],
    release_sha: str, now: dt.datetime,
) -> tuple[dict[str, Any], list[str]]:
    """The manifest, and one line per axis that could not go into it."""
    if not SHA1.fullmatch(release_sha):
        raise Refused("--release-sha must be a full 40-hex commit")
    rows: list[dict[str, Any]] = []
    absent: list[str] = []
    by_axis = {entry["axis"]: entry for entry in sources}
    for axis in REQUIRED_AXES:
        entry = by_axis[axis]
        if axis not in envelopes:
            # A complete chain with no envelope is an instruction, not a blocker: dispatch
            # the workflow at this SHA and import it. Anything else is the sources file's
            # reason, which names the external thing in the way.
            why = entry["reason"] or (
                f"the chain is complete -- dispatch {entry['workflow']} at this SHA and run "
                f"{entry['importer']} over the artifact"
            )
            absent.append(f"{axis} ({entry['chain']}): {why}")
            continue
        path, envelope = envelopes[axis]
        check_envelope(axis, envelope, release_sha, now)
        rows.append(envelope)
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "runPurpose": RUN_PURPOSE,
        "releaseSha": release_sha,
        "axes": rows,
    }
    return manifest, absent


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Assemble the AC-11 aggregator manifest from the axis envelopes present."
    )
    result.add_argument("--release-sha", required=True)
    result.add_argument("--envelopes", type=Path, required=True,
                        help="a directory of importer outputs")
    result.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--report", type=Path, help="where to write the absent-axis lines")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        sources = load_sources(args.sources)
        envelopes = read_envelopes(args.envelopes)
        manifest, absent = assemble(
            sources=sources, envelopes=envelopes,
            release_sha=args.release_sha.strip().lower(),
            now=dt.datetime.now(dt.timezone.utc),
        )
    except Refused as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    summary = {
        "releaseSha": manifest["releaseSha"],
        "assembledAxes": sorted(str(row.get("axis")) for row in manifest["axes"]),
        "absentAxes": absent,
        "aggregationWillBeInvalid": bool(absent),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
