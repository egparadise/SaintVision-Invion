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
    "artifactNamePrefix", "envelopeMember", "importerEmitsAxes", "reason",
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
        axis = str(document.get("axis") or "")
        if document.get("runPurpose") != AXIS_PURPOSE:
            continue                      # not an axis envelope; the directory may hold more
        if axis not in REQUIRED_AXES:
            raise Refused(f"{path.name} claims axis {axis!r}, which AC-11 does not have")
        if axis in found:
            raise Refused(f"two envelopes claim axis {axis!r}: {found[axis][0].name}, {path.name}")
        found[axis] = (path, document)
    return found


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
