"""S12-DB AC-12 acceptance evidence collector (restore, permissions, operational acceptance).

At one fixed, committed code SHA and in one invocation this collector reads the outputs of
the EXISTING acceptance tools -- it re-implements none of their judgement -- and sorts the
AC-12 evidence items into PASS / FAIL / NOT_OBSERVED / BLOCKED_EXTERNAL:

* ``tools/operational_readiness.py --acceptance-evidence [--release R] --json`` (ADR-082/083:
  operational inputs, offer agreement, admission gates, and ``pilot_readiness``'s AC-12 record
  catalog -- ``acceptanceAssessed``, ``catalogComplete``, ``blockers``);
* ``tools/pitr_readiness.py --json`` (configuration-only PITR verdict);
* ``tools/pitr_opt_in_dry_run.py`` (read-only readiness + retention rehearsal report);
* the desktop-browser CI proof (``vf-desktop-browser-ci.json`` from
  ``tools/run_vf_security_tests.py``) for the web smoke, when a path is given.

Item semantics (fail-closed, nothing unobserved is ever zero or PASS):

* PASS      -- the tool ran, produced the field, and it satisfies the item;
* FAIL      -- the tool ran and the field says the item is not satisfied (or a fail-closed
               refusal: exit 3 / ``mode=refused``);
* NOT_OBSERVED -- the tool did not run, was unavailable, or did not produce the field
               (reason recorded); never counted toward PASS;
* BLOCKED_EXTERNAL -- the item needs a user decision or an external environment (a cut
               release with an AC-12 acceptance record, five physical nodes, a real
               Tier-A PITR, an authenticated browser on a physical Node); reason recorded,
               no value invented.

The overall verdict: FAIL if any item FAILed; otherwise ``PASS_MEASURED_PARTIAL`` when
every observed item passed but NOT_OBSERVED / BLOCKED_EXTERNAL items remain (always the
case until the external waits clear); ``NOT_OBSERVED`` when nothing at all was observed.
``acceptanceClaim`` is always ``false``: this bundle feeds the S12-DB review, it does not
close AC-12.

Provenance comes from ``tools.provenance.collect`` computed with the repository root as
cwd, plus this collector's own hash; a dirty working tree is refused by default
(``--allow-dirty-tree`` is a recorded opt-out) and so is a head that no remote ref
contains (``--reachable-ref`` for explicit ancestry, ``--allow-unpushed-head`` as the
recorded opt-out); the output label carries the SHA and a UTC timestamp and existing
outputs are never overwritten.  Redaction happens at the structured level BEFORE
serialization and is re-checked on the produced text in raw and JSON-escaped forms, so
quotes, backslashes or control characters in a value cannot hide it: DSN values and
passwords (from the DSN environment variables this run used and the usual test/admin
ones), the exact tenant / release values passed on the command line, UUIDs, any
``<prefix>_<26 Crockford ULID>`` entity id regardless of prefix, and ``IPv4:port``.
Paths outside the repository are recorded as ``<outside-repo>/<name>``.

Fail-closed guards on the record catalog: a blocker text this collector cannot attribute
to an item (a blocker ``pilot_readiness`` did not emit when this collector was written)
turns every blocker-derived PASS into NOT_OBSERVED; ``acceptanceAssessed=true`` with
``catalogComplete`` not true and no blocker is a FAIL (the tool contradicts itself).  The
web smoke proof must carry ``browserOptIn=true`` and be bound to this bundle's code SHA
(``codeSha``/``gitSha`` in the proof or ``--web-smoke-sha``), otherwise NOT_OBSERVED.

Exit codes: 0 PASS / PASS_MEASURED_PARTIAL; 1 FAIL; 2 UNAVAILABLE (dirty tree without
opt-out, existing output, no DSN at all); 3 NOT_OBSERVED (nothing observed).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.provenance import collect as collect_provenance  # noqa: E402

SCHEMA_VERSION = "s12-db-acceptance-evidence:1"
DEFAULT_OUT_DIR = REPO_ROOT / "docs/vault/30_Development/Evidence/s12-db-acceptance"
TOOLS = REPO_ROOT / "tools"

PASS, FAIL, NOT_OBSERVED, BLOCKED_EXTERNAL = "PASS", "FAIL", "NOT_OBSERVED", "BLOCKED_EXTERNAL"

# AC-12 evidence items.  ``source`` names the tool output each item is read from; the
# evaluation functions below read only fields those tools already publish.
AC12_ITEMS: list[dict[str, str]] = [
    {"id": "release-manifest-recorded", "group": "release", "title": "Release manifest 기록(releaseId·manifestSha256)", "source": "operational_readiness.acceptanceEvidence"},
    {"id": "user-acceptance-record-ac12", "group": "release", "title": "사용자 인수 기록: AC-12 acceptance 존재·거절 없음·manifest 일치", "source": "operational_readiness.acceptanceEvidence"},
    {"id": "known-limitations-recorded", "group": "release", "title": "알려진 제한 기록", "source": "operational_readiness.acceptanceEvidence"},
    {"id": "database-recovery-drill-passed-with-targets", "group": "recovery", "title": "DB 복구 drill 통과 + 목표/무결성/fencing", "source": "operational_readiness.acceptanceEvidence.blockers"},
    {"id": "verified-backup-in-retention", "group": "recovery", "title": "보존 기간 내 verified backup", "source": "operational_readiness.acceptanceEvidence.blockers"},
    {"id": "verified-off-site-backup", "group": "recovery", "title": "verified off-site backup 선언(ADR-018)", "source": "operational_readiness.acceptanceEvidence.blockers"},
    {"id": "contributed-folders-checked", "group": "recovery", "title": "제공 폴더 점검(주의 필요 0)", "source": "operational_readiness.acceptanceEvidence.blockers"},
    {"id": "operational-inputs-present", "group": "permissions", "title": "운영 입력 전부 존재(absent 0)", "source": "operational_readiness.inputs"},
    {"id": "offer-agreement", "group": "permissions", "title": "기록된 offer = 커널 offer", "source": "operational_readiness.offerAgreement"},
    {"id": "admission-gates-observed-open", "group": "permissions", "title": "admission gate 관측 전부 open(진단, 실행 승인 아님)", "source": "operational_readiness.admission"},
    {"id": "pitr-configuration-possible", "group": "recovery", "title": "PITR 설정 가능(configuration-only)", "source": "pitr_readiness"},
    {"id": "pitr-rehearsal-dry-run-observed", "group": "recovery", "title": "PITR opt-in 리허설(읽기 전용) observed", "source": "pitr_opt_in_dry_run"},
    {"id": "web-smoke-journeys", "group": "web", "title": "웹 smoke: 브라우저 여정 전부 실행·통과", "source": "vf-desktop-browser-ci.json"},
]

# Items that are user decisions or external environments.  Recorded with a reason and no
# value; they can never be PASS from this collector.
EXTERNAL_ITEMS: list[dict[str, str]] = [
    {"id": "five-node-full-journey", "title": "5노드 전체 여정(개발→배포→장애 복구)", "reason": "five physical PCs; only three Ubuntu workers are registered and the CP co-located Node is BLOCKED (ADR-100)"},
    {"id": "operational-rpo-rto-measured", "title": "정량 목표(운영 RPO/RTO, 전체 서비스 복원)", "reason": "Tier-A PITR is deferred (decision B); dry-run cannot measure operational RPO/RTO"},
    {"id": "real-pitr-target-time-recovery", "title": "실 PITR target-time 복구·off-site bytes", "reason": "requires a real WAL archive on the failure domain and an operator-run recovery"},
    {"id": "authenticated-browser-acceptance-on-physical-node", "title": "물리 Node·인증 브라우저 인수", "reason": "user acceptance on the physical fleet; CI browser journeys run on a hosted runner"},
]

_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\binv_(?:backend_test|rls|s03|test)_[0-9a-f]{20,32}\b"), "inv_disposable_<redacted>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<uuid:redacted>"),
    (re.compile(r"\b[a-z]{2,16}_[0-9A-HJKMNP-TV-Z]{26}\b"), "<id:redacted>"),  # any prefixed ULID, prefix length agnostic
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b"), "<host:port:redacted>"),
]
_DSN_ENV_NAMES = ("INV_TEST_ADMIN_DSN", "INV_AUDIT_DSN", "INV_DATABASE_URL", "INV_TEST_DATABASE_URL",
                  "INV_READINESS_DSN", "INV_PITR_DSN")


# --------------------------------------------------------------------------------------
# tool runners (subprocess, read their JSON; never re-implement their judgement)
# --------------------------------------------------------------------------------------


def _tool_env(base: dict[str, str]) -> dict[str, str]:
    """The tools import ``saintvision``/``inv``; make them importable from any caller cwd."""
    env = dict(base)
    env["PYTHONUTF8"] = "1"
    paths = [str(REPO_ROOT / "src"), str(REPO_ROOT / "services" / "control-plane" / "src")]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def _run_json(command: list[str], *, env: dict[str, str], cwd: Path = REPO_ROOT) -> dict[str, Any]:
    env = _tool_env(env)
    started = dt.datetime.now(dt.timezone.utc)
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    elapsed = round((dt.datetime.now(dt.timezone.utc) - started).total_seconds(), 3)
    payload: Any = None
    parse_error = None
    text = completed.stdout.strip()
    if text:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            # Tools that print two JSON documents (plan + result) or trailing text.
            try:
                payload = json.loads(text.split("\n}\n", 1)[0] + "\n}")
            except json.JSONDecodeError as error:
                parse_error = type(error).__name__
    return {"exitCode": completed.returncode, "elapsedSeconds": elapsed, "payload": payload,
            "parseError": parse_error, "stderrLines": len(completed.stderr.splitlines())}


def run_operational_readiness(dsn_env: str, tenant: str, release: str | None, *, python: str = sys.executable) -> dict[str, Any]:
    if not os.environ.get(dsn_env):
        return {"status": "unavailable", "reason": f"{dsn_env} is not set", "payload": None, "exitCode": None}
    command = [python, str(TOOLS / "operational_readiness.py"), "--dsn-env", dsn_env, "--tenant", tenant,
               "--acceptance-evidence", "--json"]
    if release:
        command += ["--release", release]
    result = _run_json(command, env=os.environ.copy())
    payload = result["payload"]
    if not isinstance(payload, dict) or "error" in payload or "acceptanceEvidence" not in payload:
        return {**result, "status": "unavailable",
                "reason": (payload or {}).get("error", "no acceptance evidence in output") if isinstance(payload, dict) else "no JSON output"}
    return {**result, "status": "complete", "reason": None}


def run_pitr_readiness(dsn_env: str, *, python: str = sys.executable) -> dict[str, Any]:
    if not os.environ.get(dsn_env):
        return {"status": "unavailable", "reason": f"{dsn_env} is not set", "payload": None, "exitCode": None}
    result = _run_json([python, str(TOOLS / "pitr_readiness.py"), "--dsn-env", dsn_env, "--json"], env=os.environ.copy())
    payload = result["payload"]
    if not isinstance(payload, dict) or "verdict" not in payload:
        return {**result, "status": "unavailable", "reason": "no verdict in output"}
    return {**result, "status": "complete", "reason": None}


def run_pitr_dry_run(dsn_env: str, archive: Path | None, backups: Path | None, now: dt.datetime, *,
                     python: str = sys.executable) -> dict[str, Any]:
    if archive is None or backups is None:
        return {"status": "not_run", "reason": "--pitr-archive/--pitr-backups not given", "payload": None, "exitCode": None}
    command = [python, str(TOOLS / "pitr_opt_in_dry_run.py"), "--dsn-env", dsn_env, "--archive", str(archive),
               "--backups", str(backups), "--now", now.isoformat()]
    result = _run_json(command, env=os.environ.copy())
    payload = result["payload"]
    if result["exitCode"] == 2 and not isinstance(payload, dict):
        # argparse error path: fail-closed refusal (e.g. unreadable backup label time)
        return {**result, "status": "refused", "reason": "harness refused (argparse error, stderr not recorded)"}
    if not isinstance(payload, dict) or "harnessVerdict" not in payload:
        return {**result, "status": "unavailable", "reason": "no harness report in output"}
    return {**result, "status": "complete", "reason": None}


def read_web_smoke_proof(path: Path | None, bound_sha: str | None = None) -> dict[str, Any]:
    """``bound_sha`` is the run head the proof was produced for (``gh run view --json headSha``);
    it is recorded next to the proof so the item can be bound to the current codeSha."""
    if path is None:
        return {"status": "not_run", "reason": "no --web-smoke-proof given (desktop-browser lane, Gemini)", "payload": None}
    if not path.is_file():
        return {"status": "unavailable", "reason": "proof file absent", "payload": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "unavailable", "reason": "proof file unreadable", "payload": None}
    if not isinstance(payload, dict) or not isinstance(payload.get("tests"), dict):
        return {"status": "unavailable", "reason": "proof has no tests counts", "payload": None}
    return {"status": "complete", "reason": None, "payload": payload, "proofSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "boundSha": bound_sha}


# --------------------------------------------------------------------------------------
# item evaluation (reads fields the tools publish; PASS only on an observed satisfying value)
# --------------------------------------------------------------------------------------


def _item(status: str, reason: str | None = None, **facts: Any) -> dict[str, Any]:
    return {"status": status, "reason": reason, **facts}


_HEX_SHA = re.compile(r"^[0-9a-f]{12,40}$")


def sha_binding(proof_sha: Any, code_sha: Any) -> tuple[bool, str | None]:
    """Bind a proof to this bundle's code SHA: both must be lowercase hex of 12..40 chars (a full
    40 is recommended) and the shorter must be a prefix of the longer.  Anything else -- a
    1-character or 11-character token, non-hex text, or a different SHA -- is NOT a binding."""
    if not isinstance(proof_sha, str) or not isinstance(code_sha, str):
        return False, "sha is not a string"
    proof_sha, code_sha = proof_sha.strip().lower(), code_sha.strip().lower()
    if not _HEX_SHA.fullmatch(proof_sha):
        return False, f"proof sha is not 12..40 lowercase hex characters ({len(proof_sha)} chars)"
    if not _HEX_SHA.fullmatch(code_sha):
        return False, "bundle code sha is not 12..40 lowercase hex characters"
    shorter, longer = sorted((proof_sha, code_sha), key=len)
    if not longer.startswith(shorter):
        return False, "different code SHA"
    return True, None


# Every blocker text ``pilot_readiness`` can emit today, attributed to the item it blocks.  A
# blocker that matches none of these is UNCLASSIFIED: the catalog is then not known to be
# clean and no blocker-derived item may become PASS (fail-closed against future blockers).
KNOWN_BLOCKER_PREFIXES: dict[str, tuple[str, ...]] = {
    "user-acceptance-record-ac12": ("no acceptance record for AC-12", "a rejected acceptance", "an acceptance refers to a different manifest"),
    "database-recovery-drill-passed-with-targets": ("no passing database recovery drill", "no database recovery drill meeting"),
    "verified-backup-in-retention": ("no verified backup",),
    "verified-off-site-backup": ("no verified off-site backup",),
    "contributed-folders-checked": ("contributed folder",),
}
BLOCKER_DERIVED_ITEMS = tuple(KNOWN_BLOCKER_PREFIXES)


def _matches(blocker: str, prefixes: tuple[str, ...]) -> bool:
    return any(blocker.startswith(prefix) or (prefix == "contributed folder" and "contributed folder" in blocker) for prefix in prefixes)


def unclassified_blockers(evidence: dict[str, Any]) -> list[str]:
    blockers = evidence.get("blockers")
    if not isinstance(blockers, list):
        return []
    known = tuple(prefix for prefixes in KNOWN_BLOCKER_PREFIXES.values() for prefix in prefixes)
    return [b for b in blockers if not isinstance(b, str) or not _matches(b, known)]


def catalog_guard(evidence: dict[str, Any] | None) -> tuple[str, str] | None:
    """Reason a blocker-derived PASS must be withheld, or None when the catalog is trustworthy.

    * unclassified blockers -> NOT_OBSERVED (cannot attribute; not known clean);
    * ``acceptanceAssessed`` true but ``catalogComplete`` not true while every blocker is
      classified and none hit -> FAIL (the tool says incomplete; a PASS would contradict it).
    """
    if evidence is None:
        return None
    unknown = unclassified_blockers(evidence)
    if unknown:
        return NOT_OBSERVED, "unclassified blocker(s) in the catalog: " + "; ".join(str(b) for b in unknown)
    if evidence.get("acceptanceAssessed") is True and evidence.get("catalogComplete") is not True and not evidence.get("blockers"):
        return FAIL, "catalogComplete is not true although no blocker is reported (catalog inconsistent)"
    return None


def _blocker_item(evidence: dict[str, Any] | None, prefixes: tuple[str, ...]) -> dict[str, Any]:
    if evidence is None:
        return _item(NOT_OBSERVED, "acceptance evidence not produced")
    blockers = evidence.get("blockers")
    if not isinstance(blockers, list):
        return _item(NOT_OBSERVED, "blockers field missing")
    hits = [b for b in blockers if isinstance(b, str) and _matches(b, prefixes)]
    if hits:
        return _item(FAIL, "; ".join(hits), blockers=hits)
    guard = catalog_guard(evidence)
    if guard is not None:
        return _item(guard[0], guard[1], blockers=[])
    return _item(PASS, None, blockers=[])


def evaluate_items(readiness: dict[str, Any], pitr: dict[str, Any], dry_run: dict[str, Any],
                   web: dict[str, Any], release_given: bool, code_sha: str | None = None) -> dict[str, dict[str, Any]]:
    payload = readiness.get("payload") if readiness.get("status") == "complete" else None
    evidence = payload.get("acceptanceEvidence") if isinstance(payload, dict) else None
    items: dict[str, dict[str, Any]] = {}

    # release group
    if evidence is None:
        for key in ("release-manifest-recorded", "user-acceptance-record-ac12", "known-limitations-recorded"):
            items[key] = _item(NOT_OBSERVED, readiness.get("reason") or "acceptance evidence not produced")
    elif not release_given or evidence.get("acceptanceAssessed") is not True:
        reason = "no --release given: a cut release with its AC-12 acceptance record is a user input (acceptanceAssessed=false)"
        for key in ("release-manifest-recorded", "user-acceptance-record-ac12", "known-limitations-recorded"):
            items[key] = _item(BLOCKED_EXTERNAL, reason, acceptanceAssessed=bool(evidence.get("acceptanceAssessed")))
    else:
        items["release-manifest-recorded"] = (
            _item(PASS, None, versionRecorded=bool(evidence.get("version")), manifestSha256Recorded=bool(evidence.get("manifestSha256")))
            if evidence.get("manifestSha256") and evidence.get("version") else
            _item(FAIL, "release assessed but version/manifestSha256 missing"))
        items["user-acceptance-record-ac12"] = _blocker_item(evidence, KNOWN_BLOCKER_PREFIXES["user-acceptance-record-ac12"])
        limitations = evidence.get("knownLimitations")
        if isinstance(limitations, list) and limitations:
            items["known-limitations-recorded"] = _item(PASS, None, count=len(limitations))
        else:
            items["known-limitations-recorded"] = _item(NOT_OBSERVED, "no known-limitation entries: cannot distinguish 'none' from 'not recorded'", count=0)

    # recovery group (record catalog)
    items["database-recovery-drill-passed-with-targets"] = _blocker_item(evidence, KNOWN_BLOCKER_PREFIXES["database-recovery-drill-passed-with-targets"])
    if evidence is not None and isinstance(evidence.get("drillsMissingTargets"), list):
        items["database-recovery-drill-passed-with-targets"]["drillsMissingTargets"] = len(evidence["drillsMissingTargets"])
    items["verified-backup-in-retention"] = _blocker_item(evidence, KNOWN_BLOCKER_PREFIXES["verified-backup-in-retention"])
    items["verified-off-site-backup"] = _blocker_item(evidence, KNOWN_BLOCKER_PREFIXES["verified-off-site-backup"])
    items["contributed-folders-checked"] = _blocker_item(evidence, KNOWN_BLOCKER_PREFIXES["contributed-folders-checked"])
    if evidence is not None and items["contributed-folders-checked"]["status"] == PASS:
        items["contributed-folders-checked"]["needingAttention"] = len(evidence.get("contributionsNeedingAttention") or [])

    # permissions group (operational readiness proper)
    if not isinstance(payload, dict):
        for key in ("operational-inputs-present", "offer-agreement", "admission-gates-observed-open"):
            items[key] = _item(NOT_OBSERVED, readiness.get("reason") or "operational readiness not produced")
    else:
        absent = payload.get("absent")
        if isinstance(absent, list):
            names = [a.get("input") for a in absent if isinstance(a, dict)]
            items["operational-inputs-present"] = _item(PASS, None, absent=[]) if not absent else _item(FAIL, "absent operational inputs", absent=names)
        else:
            items["operational-inputs-present"] = _item(NOT_OBSERVED, "absent field missing")
        agreement = payload.get("offerAgreement") or {}
        disagreeing = agreement.get("disagreeing") if isinstance(agreement, dict) else None
        if isinstance(disagreeing, list):
            items["offer-agreement"] = _item(PASS, None, disagreeing=0) if not disagreeing else _item(FAIL, "recorded offer differs from kernel offer", disagreeing=len(disagreeing))
        else:
            items["offer-agreement"] = _item(NOT_OBSERVED, "offerAgreement.disagreeing missing")
        admission = payload.get("admission") or {}
        closed = admission.get("closed") if isinstance(admission, dict) else None
        if isinstance(closed, list) and "observedGatesOpen" in admission:
            items["admission-gates-observed-open"] = (_item(PASS, None, closed=[], scope=admission.get("scope"))
                                                     if admission.get("observedGatesOpen") is True else
                                                     _item(FAIL, "closed admission gates", closed=closed, scope=admission.get("scope")))
        else:
            items["admission-gates-observed-open"] = _item(NOT_OBSERVED, "admission gates missing")

    # PITR configuration
    if pitr.get("status") != "complete":
        items["pitr-configuration-possible"] = _item(NOT_OBSERVED, pitr.get("reason") or "pitr_readiness not produced")
    else:
        verdict = pitr["payload"].get("verdict")
        items["pitr-configuration-possible"] = {
            "possible": _item(PASS, None, verdict=verdict, pitrVerified=False),
            "absent": _item(FAIL, "; ".join(pitr["payload"].get("reasons") or []), verdict=verdict),
        }.get(verdict, _item(NOT_OBSERVED, "; ".join(pitr["payload"].get("reasons") or ["inconclusive"]), verdict=verdict))

    # PITR rehearsal
    status = dry_run.get("status")
    if status == "complete":
        report = dry_run["payload"]
        hv = report.get("harnessVerdict")
        mutations = report.get("mutations") or {}
        if hv == "observed" and mutations and not any(mutations.values()):
            items["pitr-rehearsal-dry-run-observed"] = _item(PASS, None, harnessVerdict=hv, retentionDeleteCandidates=len((report.get("retention") or {}).get("deleteArchive") or []), pitrVerified=False)
        elif hv == "observed":
            items["pitr-rehearsal-dry-run-observed"] = _item(FAIL, "rehearsal reported a mutation", harnessVerdict=hv)
        else:
            items["pitr-rehearsal-dry-run-observed"] = _item(NOT_OBSERVED, "harness inconclusive", harnessVerdict=hv)
    elif status == "refused":
        items["pitr-rehearsal-dry-run-observed"] = _item(FAIL, dry_run.get("reason"))
    else:
        items["pitr-rehearsal-dry-run-observed"] = _item(NOT_OBSERVED, dry_run.get("reason") or "not run")

    # web smoke: the proof must come from a real browser run (browserOptIn) AND be bound to the
    # code SHA this bundle describes; an unbound or differently-bound proof is evidence of
    # something else and stays NOT_OBSERVED.
    if web.get("status") != "complete":
        items["web-smoke-journeys"] = _item(NOT_OBSERVED, web.get("reason"))
    else:
        proof = web["payload"]
        counts = proof.get("tests") or {}
        passed = counts.get("passed")
        bad = [k for k in ("failure", "error", "skipped") if counts.get(k) not in (0,)]
        proof_sha = proof.get("codeSha") or proof.get("gitSha") or web.get("boundSha")
        if proof.get("browserOptIn") is not True:
            items["web-smoke-journeys"] = _item(NOT_OBSERVED, "proof was not produced with browserOptIn=true (no real browser ran)", browserOptIn=proof.get("browserOptIn"))
        elif not proof_sha:
            items["web-smoke-journeys"] = _item(NOT_OBSERVED, "proof is not bound to a code SHA (no codeSha/gitSha in proof and no --web-smoke-sha)")
        elif not (binding := sha_binding(proof_sha, code_sha))[0]:
            items["web-smoke-journeys"] = _item(NOT_OBSERVED, f"proof is not bound to this bundle's code SHA: {binding[1]}",
                                                proofSha=str(proof_sha)[:12] if isinstance(proof_sha, str) else None)
        elif not isinstance(passed, int):
            items["web-smoke-journeys"] = _item(NOT_OBSERVED, "proof has no passed count")
        elif passed > 0 and not bad and proof.get("exitCode") == 0 and proof.get("evidenceStatus") == "complete":
            items["web-smoke-journeys"] = _item(PASS, None, passed=passed, proofSha256=web.get("proofSha256"), boundSha=str(proof_sha)[:12])
        else:
            items["web-smoke-journeys"] = _item(FAIL, f"journeys not all passed (nonzero: {bad}, exit {proof.get('exitCode')}, status {proof.get('evidenceStatus')})", passed=passed)

    # externals
    for spec in EXTERNAL_ITEMS:
        items[spec["id"]] = _item(BLOCKED_EXTERNAL, spec["reason"], value=None)

    ordered = {spec["id"]: {"title": spec["title"], "group": spec["group"], "source": spec["source"], **items[spec["id"]]} for spec in AC12_ITEMS}
    ordered.update({spec["id"]: {"title": spec["title"], "group": "external", "source": None, **items[spec["id"]]} for spec in EXTERNAL_ITEMS})
    return ordered


def scope(items: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {PASS: [], FAIL: [], NOT_OBSERVED: [], BLOCKED_EXTERNAL: []}
    for key, item in items.items():
        out[item["status"]].append(key)
    return out


def overall_verdict(items: dict[str, dict[str, Any]]) -> str:
    s = scope(items)
    if s[FAIL]:
        return "FAIL"
    if not s[PASS]:
        return "NOT_OBSERVED"
    return "PASS_MEASURED_PARTIAL" if (s[NOT_OBSERVED] or s[BLOCKED_EXTERNAL]) else "PASS"


EXIT_BY_VERDICT = {"PASS": 0, "PASS_MEASURED_PARTIAL": 0, "FAIL": 1, "NOT_OBSERVED": 3}


# --------------------------------------------------------------------------------------
# bundle, redaction, output
# --------------------------------------------------------------------------------------


def evidence_ref(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return f"<outside-repo>/{path.name}"


def _tool_summary(result: dict[str, Any], keep: tuple[str, ...]) -> dict[str, Any]:
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    return {"status": result.get("status"), "reason": result.get("reason"), "exitCode": result.get("exitCode"),
            "elapsedSeconds": result.get("elapsedSeconds"), **{k: payload.get(k) for k in keep if k in payload}}


def build_evidence(*, provenance: dict[str, Any], readiness: dict[str, Any], pitr: dict[str, Any],
                   dry_run: dict[str, Any], web: dict[str, Any], release_given: bool,
                   note: str | None = None) -> dict[str, Any]:
    items = evaluate_items(readiness, pitr, dry_run, web, release_given, provenance.get("commit_sha"))
    verdict = overall_verdict(items)
    evidence = (readiness.get("payload") or {}).get("acceptanceEvidence") if readiness.get("status") == "complete" else None
    return {
        "schemaVersion": SCHEMA_VERSION,
        "task": ["S12-DB"],
        "acceptance": "AC-12",
        "acceptanceClaim": False,
        "acceptanceScope": ("measured: outputs of operational_readiness (--acceptance-evidence), pitr_readiness, "
                            "pitr_opt_in_dry_run and the desktop-browser proof at one code SHA, sorted per AC-12 item; "
                            "BLOCKED_EXTERNAL: cut release + AC-12 acceptance record, five physical nodes, real Tier-A PITR, "
                            "authenticated browser acceptance on a physical Node; NOT_OBSERVED items carry no value"),
        "codeSha": provenance.get("commit_sha"),
        "provenance": {
            **{key: provenance.get(key) for key in (
                "commit_sha", "branch", "integration_ref", "integration_sha", "integration_check_mode",
                "working_tree_clean_status", "content_clean_diff", "modified_paths", "interpreter",
                "runtime_python", "timestamp_kst", "executor", "os_platform")},
            "collectorSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "dirtyTreeAllowed": bool(provenance.get("dirtyTreeAllowed", False)),
            "remoteReachable": provenance.get("remoteReachable"),
            "remoteRefCount": provenance.get("remoteRefCount"),
            "remoteRefFreshness": provenance.get("remoteRefFreshness"),
            "unpushedHeadAllowed": bool(provenance.get("unpushedHeadAllowed", False)),
        },
        "inputs": {
            "operationalReadiness": _tool_summary(readiness, ("observedAt",)),
            "acceptanceCatalog": ({k: evidence.get(k) for k in ("acceptanceAssessed", "catalogComplete", "scope",
                                                                  "operationalAcceptanceAssessed", "evidenceComplete", "unverified", "blockers")}
                                  if isinstance(evidence, dict) else None),
            "pitrReadiness": _tool_summary(pitr, ("verdict", "scope", "pitrVerified", "reasons")),
            "pitrDryRun": _tool_summary(dry_run, ("harnessVerdict", "mode", "decision", "mutations", "acceptance")),
            "webSmokeProof": {k: v for k, v in web.items() if k != "payload"},
            "releaseGiven": release_given,
        },
        "items": items,
        "scope": scope(items),
        "verdict": verdict,
        "note": note,
    }


def render_markdown(evidence: dict[str, Any]) -> str:
    p = evidence["provenance"]
    lines = [
        f"# S12-DB AC-12 acceptance evidence — `{(evidence.get('codeSha') or 'nogit')[:12]}`",
        "",
        f"- verdict (measured part): **{evidence['verdict']}** · acceptanceClaim: `false`",
        f"- captured: {p.get('timestamp_kst')} · executor: {p.get('executor')} · clean tree: {p.get('working_tree_clean_status')}"
        f" · dirty allowed: {p.get('dirtyTreeAllowed')} · collector sha256 `{(p.get('collectorSha256') or '')[:16]}`",
        f"- inputs: readiness {evidence['inputs']['operationalReadiness']['status']} · pitr {evidence['inputs']['pitrReadiness']['status']}"
        f" · dry-run {evidence['inputs']['pitrDryRun']['status']} · web proof {evidence['inputs']['webSmokeProof'].get('status')}"
        f" · release given {evidence['inputs']['releaseGiven']}",
        "",
        "| AC-12 item | group | status | reason / facts |",
        "|---|---|---|---|",
    ]
    for key, item in evidence["items"].items():
        facts = {k: v for k, v in item.items() if k not in ("title", "group", "source", "status", "reason")}
        lines.append(f"| {item['title']} (`{key}`) | {item['group']} | **{item['status']}** | {item.get('reason') or '—'} {json.dumps(facts, ensure_ascii=False) if facts else ''} |")
    s = evidence["scope"]
    lines += ["", f"- scope: PASS {s[PASS]} · FAIL {s[FAIL]} · NOT_OBSERVED {s[NOT_OBSERVED]} · BLOCKED_EXTERNAL {s[BLOCKED_EXTERNAL]}"]
    if evidence.get("note"):
        lines += ["", f"- note: {evidence['note']}"]
    return "\n".join(lines) + "\n"


def _explicit_forms(value: str) -> tuple[str, ...]:
    """Every representation an explicit value can take in the produced files: raw, JSON-escaped
    (quotes/backslashes/control characters), and ASCII-escaped (``\\uXXXX``)."""
    return tuple({value, json.dumps(value, ensure_ascii=False)[1:-1], json.dumps(value)[1:-1]})


def redact_text(text: str, explicit: tuple[str, ...] = ()) -> str:
    forms = sorted({form for v in explicit if v and len(v) >= 6 for form in _explicit_forms(v)}, key=len, reverse=True)
    for form in forms:
        text = text.replace(form, "<value:redacted>")
    for pattern, placeholder in _REDACTIONS:
        text = pattern.sub(placeholder, text)
    return text


def redact_value(obj: Any, explicit: tuple[str, ...] = ()) -> Any:
    """Redact at the structured level, before serialization, so escaping can never hide a value."""
    if isinstance(obj, str):
        return redact_text(obj, explicit)
    if isinstance(obj, dict):
        return {redact_text(str(k), explicit) if isinstance(k, str) else k: redact_value(v, explicit) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_value(v, explicit) for v in obj]
    return obj


def assert_redacted(text: str, explicit: tuple[str, ...] = ()) -> None:
    """Fail closed on the raw AND the escaped representations of every explicit value."""
    for value in explicit:
        if not value or len(value) < 6:
            continue
        for form in _explicit_forms(value):
            if form in text:
                raise ValueError("evidence would embed an unredacted identifier (<value:redacted>)")
    for pattern, placeholder in _REDACTIONS:
        if pattern.search(text):
            raise ValueError(f"evidence would embed an unredacted identifier ({placeholder})")


def assert_no_secrets(text: str, extra_env: tuple[str, ...] = ()) -> None:
    from psycopg.conninfo import conninfo_to_dict

    for key in (*_DSN_ENV_NAMES, *extra_env):
        dsn = os.environ.get(key)
        if not dsn:
            continue
        if dsn in text:
            raise ValueError(f"evidence would embed {key}")
        try:
            password = conninfo_to_dict(dsn).get("password")
        except Exception:
            password = None
        if not password:
            match = re.search(r"://[^:/]+:([^@]+)@", dsn)
            password = match.group(1) if match else None
        if password and password in text:
            raise ValueError(f"evidence would embed the password of {key}")


def write_evidence(evidence: dict[str, Any], out_dir: Path, label: str, *, explicit: tuple[str, ...] = (),
                   extra_env: tuple[str, ...] = ()) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    # 1) structured redaction before serialization (F1: escaping cannot hide a value),
    # 2) serialization, 3) text-level redaction again, 4) fail-closed check of raw and
    #    escaped forms plus every DSN/password.
    clean = redact_value(evidence, explicit)
    json_text = redact_text(json.dumps(clean, indent=2, ensure_ascii=False, sort_keys=True) + "\n", explicit)
    md_text = redact_text(render_markdown(json.loads(json_text)), explicit)
    for text in (json_text, md_text):
        assert_no_secrets(text, extra_env)
        assert_redacted(text, explicit)
    json_path, md_path = out_dir / f"{label}.json", out_dir / f"{label}.md"
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    return json_path, md_path


def existing_outputs(out_dir: Path, label: str) -> list[Path]:
    return [out_dir / f"{label}{suffix}" for suffix in (".json", ".md") if (out_dir / f"{label}{suffix}").exists()]


def collect_provenance_at_repo_root(executor: str | None) -> dict[str, Any]:
    previous = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        return collect_provenance(executor=executor)
    finally:
        os.chdir(previous)


def _git_lines(*args: str) -> list[str]:
    completed = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _git_ok(*args: str) -> bool:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True).returncode == 0


def resolve_remote_tracking_ref(ref: str) -> dict[str, Any]:
    """Accept only a remote-tracking ref (``refs/remotes/<remote>/<branch>`` or ``<remote>/<branch>``
    for a configured remote) that git can resolve.  ``HEAD``, local branches, tags and unknown
    remotes are refused -- an ancestry check against those proves nothing about the remote."""
    remotes = set(_git_lines("remote"))
    name = ref.strip()
    if name.startswith("refs/remotes/"):
        short = name[len("refs/remotes/"):]
    elif "/" in name and not name.startswith("refs/"):
        short = name
    else:
        return {"ok": False, "reason": "not a remote-tracking ref (HEAD, local branch, tag or refs/heads are refused)"}
    remote, _, branch = short.partition("/")
    if remote not in remotes or not branch:
        return {"ok": False, "reason": f"remote {remote!r} is not configured or branch is empty"}
    full = f"refs/remotes/{remote}/{branch}"
    resolved = _git_lines("rev-parse", "--verify", "--quiet", full + "^{commit}")
    if not resolved:
        return {"ok": False, "reason": f"{full} does not resolve to a commit"}
    # Stale detection: compare the remote-tracking tip with what the remote reports now.
    live = _git_lines("ls-remote", "--heads", remote, branch)
    if not live:
        freshness = "unknown"
    else:
        live_sha = live[0].split()[0]
        freshness = "fresh" if live_sha == resolved[0] else "stale"
    return {"ok": True, "ref": full, "sha": resolved[0], "remote": remote, "freshness": freshness}


def remote_reachability(sha: str | None, ref: str | None = None) -> dict[str, Any]:
    """Whether the commit this evidence describes can be reached from a remote ref.

    A clean but unpushed commit would otherwise produce evidence nobody can check out.  With
    ``ref`` the check is explicit ancestry (``merge-base --is-ancestor``) against a VERIFIED
    remote-tracking ref only; without it, any ``refs/remotes/*`` that contains the commit
    counts.  A stale remote-tracking ref (its tip differs from the live remote) does not count.
    Fail closed when git says nothing.
    """
    if not sha:
        return {"reachable": False, "refs": [], "mode": "no-sha", "freshness": None}
    if ref:
        resolved = resolve_remote_tracking_ref(ref)
        if not resolved["ok"]:
            return {"reachable": False, "refs": [], "mode": "invalid-ref", "reason": resolved["reason"], "freshness": None}
        ancestor = _git_ok("merge-base", "--is-ancestor", sha, resolved["sha"])
        reachable = ancestor and resolved["freshness"] != "stale"
        return {"reachable": reachable, "refs": [resolved["ref"]] if reachable else [], "mode": "explicit-ref",
                "freshness": resolved["freshness"], "reason": None if reachable else ("remote-tracking ref is stale" if ancestor else "not an ancestor")}
    refs = [line for line in _git_lines("branch", "-r", "--contains", sha) if "->" not in line]
    return {"reachable": bool(refs), "refs": refs, "mode": "remote-containment", "freshness": None}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    result.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    result.add_argument("--label", default=None, help="file stem (default: s12-acceptance-<sha12>-<UTC %%Y%%m%%dT%%H%%M%%SZ>)")
    result.add_argument("--executor", default=os.environ.get("INV_S12_EXECUTOR") or "Claude")
    result.add_argument("--note", default=None)
    result.add_argument("--tenant", required=True, help="tenant id to observe (value is redacted in the evidence)")
    result.add_argument("--release", default=None, help="release id whose AC-12 acceptance record is compared (redacted)")
    result.add_argument("--readiness-dsn-env", default="INV_READINESS_DSN")
    result.add_argument("--pitr-dsn-env", default="INV_PITR_DSN")
    result.add_argument("--pitr-archive", type=Path, default=None)
    result.add_argument("--pitr-backups", type=Path, default=None)
    result.add_argument("--web-smoke-proof", type=Path, default=None, help="vf-desktop-browser-ci.json from the desktop-browser workflow")
    result.add_argument("--web-smoke-sha", default=None,
                        help="head SHA of the desktop-browser run that produced the proof (gh run view --json headSha); "
                             "required for the web item to be bound to this bundle's codeSha unless the proof carries codeSha")
    result.add_argument("--reachable-ref", default=None,
                        help="remote ref the head must be an ancestor of (default: any refs/remotes/* containing HEAD)")
    result.add_argument("--allow-unpushed-head", action="store_true",
                        help="explicit opt-out: run on a head no remote ref contains (recorded in provenance)")
    result.add_argument("--now", default=None, help="ISO 8601 UTC clock override for reproducible dry-run plans")
    result.add_argument("--allow-dirty-tree", action="store_true",
                        help="explicit opt-out: run on a dirty working tree (recorded in provenance)")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    provenance = collect_provenance_at_repo_root(args.executor)
    provenance["dirtyTreeAllowed"] = bool(args.allow_dirty_tree)
    sha12 = (provenance.get("commit_sha") or "nogit")[:12]
    label = args.label or f"s12-acceptance-{sha12}-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}"
    if existing := existing_outputs(args.out_dir, label):
        print(f"refusing to overwrite existing evidence: {[p.name for p in existing]}", file=sys.stderr)
        return 2
    if not provenance.get("working_tree_clean_status") and not args.allow_dirty_tree:
        print("working tree is not clean; evidence must come from a committed, reachable head "
              "(pass --allow-dirty-tree to record an explicit opt-out)", file=sys.stderr)
        return 2
    reach = remote_reachability(provenance.get("commit_sha"), args.reachable_ref)
    provenance["remoteReachable"] = reach["reachable"]
    provenance["remoteRefCount"] = len(reach["refs"])
    provenance["remoteRefFreshness"] = reach.get("freshness")
    provenance["unpushedHeadAllowed"] = bool(args.allow_unpushed_head)
    if reach["mode"] == "invalid-ref":
        print(f"--reachable-ref rejected: {reach.get('reason')}", file=sys.stderr)
        return 2
    if not reach["reachable"] and not args.allow_unpushed_head:
        print(f"head is not reachable from any remote ref ({reach['mode']}: {reach.get('reason') or 'no containing ref'}); "
              "evidence must come from a pushed head (pass --allow-unpushed-head to record an explicit opt-out)", file=sys.stderr)
        return 2
    if not os.environ.get(args.readiness_dsn_env) and not os.environ.get(args.pitr_dsn_env):
        print(f"neither {args.readiness_dsn_env} nor {args.pitr_dsn_env} is set; nothing can be observed", file=sys.stderr)
        return 2
    now = dt.datetime.fromisoformat(args.now).astimezone(dt.timezone.utc) if args.now else dt.datetime.now(dt.timezone.utc)
    explicit = tuple(v for v in (args.tenant, args.release) if v)
    readiness = run_operational_readiness(args.readiness_dsn_env, args.tenant, args.release)
    pitr = run_pitr_readiness(args.pitr_dsn_env)
    dry_run = run_pitr_dry_run(args.pitr_dsn_env, args.pitr_archive, args.pitr_backups, now)
    web = read_web_smoke_proof(args.web_smoke_proof, args.web_smoke_sha)
    note = redact_text(args.note, explicit) if args.note else None
    evidence = build_evidence(provenance=provenance, readiness=readiness, pitr=pitr, dry_run=dry_run, web=web,
                              release_given=bool(args.release), note=note)
    try:
        json_path, md_path = write_evidence(evidence, args.out_dir, label, explicit=explicit,
                                            extra_env=(args.readiness_dsn_env, args.pitr_dsn_env))
    except ValueError as error:
        print(f"refused to write evidence: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"verdict": evidence["verdict"], "scope": evidence["scope"],
                      "json": evidence_ref(json_path), "markdown": evidence_ref(md_path)}, ensure_ascii=False))
    return EXIT_BY_VERDICT[evidence["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
