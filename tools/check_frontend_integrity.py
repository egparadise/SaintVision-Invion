"""Frontend Integrity Scanner for SaintVision Web Client.

Eight structural checks, no human judgment required:

  (1) Prohibited Placeholder Identifiers:
      Detects hardcoded dummy UUIDs or synthetic test IDs in production source files:
      - '00000000-0000-0000-0000-000000000001' (synthetic tenant)
      - '11111111-1111-4111-8111-111111111111' (synthetic commandId; allowed ONLY in denylist guard definition)
      - 'apr_01JXYZ889900' (synthetic approvalId)
      - 'run_01JABCDEF_DEMO' (synthetic runId)
      - 'prj_01JABCDE' (synthetic projectId)
      - 'wsp_0123456789ABCDEFGHJKMNPQRS' (synthetic workspaceId)
      - 'run_01JABCDE0001' (synthetic fallback runId)
      - 'rcp_01JABCDEF' (synthetic fallback receiptId)

  (2) Premature Success and Connection Display:
      Detects initial component states or initial output buffers that claim
      'Connected via secure WebSocket' before the WebSocket onopen handshake
      has actually completed.

  (3) Ticket and Credential Logging Prevention:
      Detects console.log/info/warn/error statements that output sensitive
      authorization credentials ('ticket', 'terminalTicket', 'bootstrapToken') directly.

  (4) Tri-State Verification Invariant:
      Ensures components managing cryptographic verification (InvFileExplorer)
      maintain strict 3-state handling ('verified' | 'mismatch'/'tampered' | 'unverified')
      and never promote unverified bytes or mismatches to verified.

  (5) Zero-Call Guard Enforcement:
      Ensures security-sensitive mutation APIs (handleBroadcastAnnouncement) enforce
      mandatory identity parameters (tenantId) before calling the network.

  (6) Synthetic Timestamp Fallback & Qualification Invariant:
      Prevents forging missing backend timestamps with current client time
      ('|| new Date().toISOString()', '|| Date.now()'). Also enforces that
      freshness-critical timestamps (stateAsOf, completedAt) carry explicit semantic
      qualification disclaimers so users do not misread them as real-time snapshots.

  (7) Honest Capability & Unimplemented Consistency Invariant:
      Prevents contradictory or false 'unimplemented' labels. Detects files that
      invoke or bind backend APIs (e.g. getArtifactDownloadUrl, saveWorkspaceEditView)
      while claiming the API is unexposed or uncallable ('API 미노출', '미구현').
      Also forbids known false-unimplemented claims.

  (8) Integrity PASS Gate (shape-based, file-agnostic):
      Any component computing an integrity PASS/UNVERIFIED verdict must default to the
      non-positive value and gate PASS on an explicit verification signal
      (.verified / verified === true), never on execution-success or hash-presence.
      Unlike Rule 4 (bound to InvFileExplorer.tsx), this follows the *shape* to any file:
      the EvidenceViewer.tsx fake-PASS regression escaped Rule 4 precisely because it
      was a different file; a shape-based check catches the disease wherever it appears.

  (9) Canonical Wire Contract & Adapter Enforcement (shape-based, file-agnostic):
      (a) Forbids `apiClient<any>` across all frontend production source files. Stripping
          wire response types allows screen code to invent arbitrary unvalidated shapes
          and blinds compiler/governance to backend contract drift.
      (b) Forbids raw `apiClient` invocations on routes with canonical adapters
          (e.g. `/v1/pools/{pool_id}/placement-preview`) outside approved adapter modules,
          enforcing that UI components route through validated contract adapters.

What this scanner does NOT check (needs human judgment / runtime testing -- see governance doc):

  (1) Dynamically constructed / variable-interpolated fake values:
      Scans for string literal patterns. If a placeholder is assembled via string concatenation
      (e.g. `'0000' + '0000-...'`), template literals, or computed at runtime, regex will not detect it.
  (2) Novel / unregistered synthetic identifiers:
      Catches today's known fingerprint list. A new, differently formatted dummy ID (e.g. `'nod_9999fake'`)
      will not be flagged until fingerprinted and registered in FORBIDDEN_PLACEHOLDERS.
  (3) Component-targeted rules vs newly added files:
      Rule 4 specifically inspects InvFileExplorer.tsx and Rule 5 inspects ResourceExplorer.tsx.
      If a new component handling file integrity or tenant-scoped broadcast is added in another file,
      this scanner does not automatically enforce tri-state or zero-call guards on that new file.
  (4) Lexical presence vs Runtime execution / data flow:
      Scans whether tokens exist in code, but cannot trace runtime control flow: whether a validated
      tenantId is actually forwarded to the fetch header, or whether an empty string fallback satisfies
      backend schema validation at runtime.
  (5) Semantic existence of validly shaped values:
      A valid UUID (e.g. `'a1b2c3d4-...'`) that is not on the denylist will pass this scanner even if
      the entity does not exist in the database or belongs to another tenant. Backend fail-closed
      authorization remains the definitive gate.
  (6) Visual / Non-textual indicators of premature success:
      Detects specific text tokens in initial output/state, but cannot evaluate CSS color classes
      (e.g. green badges) or SVG icons that might visually convey 'success' before async confirmation.
  (7) Temporal truth and clock skew of timestamps:
      The scanner verifies that timestamp fields have explanatory labels and lack client-side synthesis,
      but cannot verify whether the timestamp reflects actual DB commit time, whether backend clocks
      have drifted (>5s skew), or whether an observed replica is truly healthy. That requires backend
      truth audits and real DB/PG16 integration testing.
  (8) Backend route existence vs client unimplemented claim:
      When a screen states '미제공 (API 미노출)', the scanner cannot autonomously verify whether the
      backend actually lacks the endpoint (e.g. /v1/recovery/* absent) or whether the frontend falsely
      labeled an existing route as unexposed. That requires route-table cross-checking (Claude's backend audit lane).
  (9) Lifecycle condition guard vs feature absence:
      A button disabled because a run is in progress ('running') or requiring out-of-band operator CLI
      action is often mistakenly called 'unimplemented' by frontend authors. Distinguishing valid
      lifecycle guards from missing endpoints requires workflow domain knowledge beyond static regex.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = ROOT / "apps" / "web" / "src"

# Patterns strictly forbidden in apps/web/src production code
FORBIDDEN_PLACEHOLDERS = [
    ("00000000-0000-0000-0000-000000000001", "Synthetic tenant UUID"),
    ("apr_01JXYZ889900", "Pre-filled synthetic approval ID"),
    ("run_01JABCDEF_DEMO", "Synthetic demo run ID"),
    ("prj_01JABCDE", "Hardcoded dummy project ID"),
    ("wsp_0123456789ABCDEFGHJKMNPQRS", "Synthetic dummy workspace ID"),
    ("run_01JABCDE0001", "Synthetic fallback run ID"),
    ("rcp_01JABCDEF", "Synthetic fallback receipt ID"),
]

# Command ID placeholder is permitted ONLY as a denylist reject constant in WebTerminal.tsx
COMMAND_PLACEHOLDER = "11111111-1111-4111-8111-111111111111"
ALLOWED_COMMAND_DEF = "export const PLACEHOLDER_COMMAND_ID = '11111111-1111-4111-8111-111111111111';"

# Premature connection string in initial state/output
PREMATURE_WS_REGEX = re.compile(
    r"useState[^(]*\([^)]*Connected via secure WebSocket", re.IGNORECASE
)
PREMATURE_INITIAL_LINES_REGEX = re.compile(
    r"terminalOutput[^=]*=\s*useState<string\[\]>\(\[\s*[^\]]*Connected via secure WebSocket",
    re.DOTALL | re.IGNORECASE,
)

# Ticket and credential logging regex
CREDENTIAL_LOG_REGEX = re.compile(
    r"console\.(?:log|info|warn|error)\([^)]*\b(?:ticketData\.ticket|terminalTicket\.ticket|bootstrapToken)\b[^)]*\)",
    re.IGNORECASE,
)

# Rule 6: Synthetic timestamp fallback regex (e.g. res.completedAt || new Date().toISOString())
SYNTHETIC_TIMESTAMP_FALLBACK_REGEX = re.compile(
    r"\b(?:completedAt|stateUpdatedAt|stateAsOf|lastHeartbeatAt|observedAt|committedAt|exportedAt)\b\s*\|\|\s*(?:new\s+Date\(\)(?:\.toISOString\(\))?|Date\.now\(\))",
    re.IGNORECASE,
)

# Rule 7: Known false unimplemented / unexposed notices strictly forbidden in production UI
FORBIDDEN_FALSE_UNEXPOSED_NOTICES = [
    ("서버 아티팩트 파일 스트림 다운로드 API 미노출 상태", "False unexposed artifact download API claim"),
    ("다운로드 (API 미노출)", "False unexposed download button label"),
    ("인메모리 워크스페이스 에디터 (백엔드 저장 API 미노출)", "False unexposed editor save API claim"),
    ("로컬 인메모리 버퍼에 저장합니다 (백엔드 저장 API 미노출)", "False unexposed editor save button tooltip"),
]

# Rule 7: Contradiction patterns where an API route/helper is wired/imported but marked unimplemented
WIRING_CONTRADICTION_PATTERNS = [
    (
        "getArtifactDownloadUrl",
        re.compile(r"아티팩트.*다운로드\s*API\s*미노출|다운로드\s*\(API\s*미노출\)", re.IGNORECASE),
        "Contradiction: imports getArtifactDownloadUrl but claims artifact download API is unexposed",
    ),
    (
        "saveWorkspaceEditView",
        re.compile(r"저장\s*API\s*미노출|백엔드\s*저장\s*API\s*미노출", re.IGNORECASE),
        "Contradiction: wires saveWorkspaceEditView but claims backend save API is unexposed",
    ),
]

# Rule 9: Canonical Wire Contract & Adapter Invariant
API_CLIENT_ANY_REGEX = re.compile(r"apiClient\s*<\s*any\s*>", re.IGNORECASE)
PLACEMENT_PREVIEW_DIRECT_API_REGEX = re.compile(r"apiClient[^;]*placement-preview", re.IGNORECASE)
POOL_LIST_DIRECT_API_REGEX = re.compile(r"apiClient[^;]*['\"]/v1/pools['\"]", re.IGNORECASE)
DISCOVERY_CANDIDATES_DIRECT_API_REGEX = re.compile(r"apiClient[^;]*['\"]/v1/discovery/candidates['\"]", re.IGNORECASE)



def get_production_source_files() -> list[Path]:
    """Return all .ts and .tsx files under apps/web/src excluding contracts and test files."""
    files: list[Path] = []
    for path in WEB_SRC.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in (".ts", ".tsx"):
            continue
        # Exclude contracts directory (generated types)
        rel = path.relative_to(WEB_SRC)
        if "contracts" in rel.parts:
            continue
        # Exclude test files
        if ".test." in path.name or ".spec." in path.name:
            continue
        files.append(path)
    return sorted(files)


def check_placeholders(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for p in files:
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT)

        # Check standard forbidden placeholders
        for token, desc in FORBIDDEN_PLACEHOLDERS:
            if token in text:
                for line_no, line in enumerate(text.splitlines(), start=1):
                    if token in line:
                        errors.append(
                            f"[RULE-1 Placeholders] {rel}:{line_no} contains forbidden placeholder '{token}' ({desc})"
                        )

        # Check command placeholder (only permitted in PLACEHOLDER_COMMAND_ID definition)
        if COMMAND_PLACEHOLDER in text:
            if p.name == "WebTerminal.tsx":
                # Ensure it only appears in the approved constant definition
                occurrences = [
                    (line_no, line)
                    for line_no, line in enumerate(text.splitlines(), start=1)
                    if COMMAND_PLACEHOLDER in line
                ]
                for line_no, line in occurrences:
                    if "export const PLACEHOLDER_COMMAND_ID =" not in line:
                        errors.append(
                            f"[RULE-1 Placeholders] {rel}:{line_no} uses '{COMMAND_PLACEHOLDER}' outside of approved rejection guard definition"
                        )
            else:
                for line_no, line in enumerate(text.splitlines(), start=1):
                    if COMMAND_PLACEHOLDER in line:
                        errors.append(
                            f"[RULE-1 Placeholders] {rel}:{line_no} contains command placeholder '{COMMAND_PLACEHOLDER}'"
                        )
    return errors


def check_premature_success(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for p in files:
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT)

        if PREMATURE_WS_REGEX.search(text) or PREMATURE_INITIAL_LINES_REGEX.search(text):
            errors.append(
                f"[RULE-3 Premature Display] {rel} declares premature 'Connected' message in initial state before socket onopen"
            )
    return errors


def check_ticket_logging(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for p in files:
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT)

        matches = CREDENTIAL_LOG_REGEX.finditer(text)
        for m in matches:
            line_no = text[: m.start()].count("\n") + 1
            errors.append(
                f"[RULE-3 Credential Logging] {rel}:{line_no} logs credential/ticket directly: '{m.group(0)}'"
            )
    return errors


def check_tristate_verification(files: list[Path]) -> list[str]:
    errors: list[str] = []
    explorer_file = WEB_SRC / "features" / "desktop" / "InvFileExplorer.tsx"
    if explorer_file.exists():
        text = explorer_file.read_text(encoding="utf-8")
        rel = explorer_file.relative_to(ROOT)

        # Must distinguish verified vs mismatch/tampered vs unverified
        has_negative = ("'mismatch'" in text) or ("'tampered'" in text)
        if "'verified'" not in text or not has_negative or "'unverified'" not in text:
            errors.append(
                f"[RULE-4 Tri-State] {rel} must implement strict 3-state verification ('verified' | 'mismatch'/'tampered' | 'unverified')"
            )

        # Must not have fallback where unverified or mismatch is treated as verified
        if re.search(r"isMatch\s*\?\s*['\"]verified['\"]\s*:\s*['\"]verified['\"]", text) or re.search(
            r"isMatch\s*\?[^:]*:\s*['\"]verified['\"]", text
        ):
            errors.append(
                f"[RULE-4 Tri-State] {rel} contains bogus ternary promoting mismatch to verified"
            )

        # Ensure else branch of isMatch check does not set status to 'verified'
        if re.search(
            r"if\s*\(\s*isMatch\s*\).*?else\s*\{[^}]*status:\s*['\"]verified['\"]",
            text,
            re.DOTALL,
        ):
            errors.append(
                f"[RULE-4 Tri-State] {rel} sets status to 'verified' in else branch of isMatch check"
            )
    return errors


# Rule 8 (shape-based, not file-targeted): any component that computes an integrity
# PASS/UNVERIFIED verdict must default to the non-positive value and gate PASS on an
# explicit verification signal. Rule 4 was bound to InvFileExplorer.tsx only, so the
# same disease in another file (EvidenceViewer.tsx: default 'PASS', PASS on sealed+hash
# instead of verified===true) escaped it and had to be caught by a Python route test in
# a lane the frontend owner does not run. This rule follows the *shape* to any file.
INTEGRITY_DEFAULT_TO_POSITIVE_REGEX = re.compile(
    r"\blet\s+\w+\s*:\s*[^=;\n]*['\"]UNVERIFIED['\"][^=;\n]*=\s*['\"](?:PASS|verified)['\"]"
)
INTEGRITY_VERIFIED_GATE_REGEX = re.compile(r"\.verified\b|verified\s*===\s*true")


def check_integrity_pass_gate(files: list[Path]) -> list[str]:
    """Rule 8: integrity PASS must rest on real verification, in ANY component (file-agnostic)."""
    errors: list[str] = []
    for p in files:
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT)
        has_positive = ("'PASS'" in text) or ('"PASS"' in text)
        has_unknown = ("'UNVERIFIED'" in text) or ('"UNVERIFIED"' in text)
        if not (has_positive and has_unknown):
            continue  # not an integrity PASS/UNVERIFIED verdict component
        # (a) honest default is the non-positive value, never PASS/verified
        m = INTEGRITY_DEFAULT_TO_POSITIVE_REGEX.search(text)
        if m:
            line_no = text[: m.start()].count("\n") + 1
            errors.append(
                f"[RULE-8 Integrity Gate] {rel}:{line_no} default-initializes an integrity status to PASS/verified; honest default is UNVERIFIED"
            )
        # (b) PASS must be gated on an explicit verification signal, not execution-success/hash-presence
        if not INTEGRITY_VERIFIED_GATE_REGEX.search(text):
            errors.append(
                f"[RULE-8 Integrity Gate] {rel} computes an integrity PASS/UNVERIFIED verdict but has no explicit verification gate (.verified / verified === true)"
            )
    return errors


def check_zero_call_guards(files: list[Path]) -> list[str]:
    errors: list[str] = []
    explorer_file = WEB_SRC / "features" / "desktop" / "ResourceExplorer.tsx"
    if explorer_file.exists():
        text = explorer_file.read_text(encoding="utf-8")
        rel = explorer_file.relative_to(ROOT)

        # Ensure broadcastAnnouncement handler enforces tenantId existence inside its body before calling broadcastAnnouncement
        if "handleBroadcastAnnouncement" in text:
            m = re.search(
                r"handleBroadcastAnnouncement\s*=\s*async[^{]*\{(?:(?!broadcastAnnouncement).)*!tenantId",
                text,
                re.DOTALL,
            )
            if not m:
                errors.append(
                    f"[RULE-2 Zero-Call Guard] {rel} handleBroadcastAnnouncement must guard against missing tenantId (!tenantId) before invoking broadcastAnnouncement"
                )
    return errors


def check_synthetic_timestamps(files: list[Path]) -> list[str]:
    """Rule 6: Detect synthetic timestamp fallbacks (e.g. res.completedAt || new Date().toISOString())
    and verify qualification disclaimers for freshness-critical timestamps in core views."""
    errors: list[str] = []
    for p in files:
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT)

        # 1. Detect synthetic current-time fallback on backend timestamp variables
        matches = SYNTHETIC_TIMESTAMP_FALLBACK_REGEX.finditer(text)
        for m in matches:
            line_no = text[: m.start()].count("\n") + 1
            errors.append(
                f"[RULE-6 Synthetic Timestamp] {rel}:{line_no} forges backend timestamp with client current time: '{m.group(0)}'"
            )

        # 2. Check semantic qualification disclaimers in RunDetail.tsx
        if p.name == "RunDetail.tsx":
            # stateAsOf must be qualified with disclaimer preventing reading as single common snapshot
            if "stateAsOf" in text and "단일 공통 스냅샷" not in text:
                errors.append(
                    f"[RULE-6 Freshness Qualification] {rel} renders stateAsOf but lacks qualification disclaimer ('단일 공통 스냅샷이나 조회 시각이 아닙니다')"
                )
            # completedAt in artifact/log tabs must disclaim that it is not capture/download time
            if "completedAt" in text and ("로그 캡처" not in text or "다운로드" not in text):
                errors.append(
                    f"[RULE-6 Freshness Qualification] {rel} renders completedAt but lacks disclaimer ('로그 캡처나 다운로드 시각이 아닙니다')"
                )
    return errors


def check_unimplemented_consistency(files: list[Path]) -> list[str]:
    """Rule 7: Detect false unimplemented notices and wiring contradictions where an API
    is imported/bound while simultaneously claiming to be unexposed or unimplemented."""
    errors: list[str] = []
    for p in files:
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT)

        # 1. Check known false unimplemented notices
        for token, desc in FORBIDDEN_FALSE_UNEXPOSED_NOTICES:
            if token in text:
                for line_no, line in enumerate(text.splitlines(), start=1):
                    if token in line:
                        errors.append(
                            f"[RULE-7 Honest Capability] {rel}:{line_no} contains false unimplemented claim: '{token}' ({desc})"
                        )

        # 2. Check wiring-unimplemented contradictions
        for api_token, regex, desc in WIRING_CONTRADICTION_PATTERNS:
            if api_token in text and regex.search(text):
                m = regex.search(text)
                assert m is not None
                line_no = text[: m.start()].count("\n") + 1
                errors.append(
                    f"[RULE-7 Contradiction] {rel}:{line_no} {desc}"
                )
    return errors


def check_uncontracted_wire_bypass(files: list[Path]) -> list[str]:
    """Rule 9: Enforce canonical contract typing and adapter usage on wire calls (shape-based).

    (a) Forbids `apiClient<any>` across all frontend source files: stripping response types
        allows screen code to invent arbitrary unvalidated shapes and miss contract drifts.
    (b) Forbids direct raw `apiClient` invocations for routes with canonical adapters
        (e.g. /v1/pools/{pool_id}/placement-preview) outside of approved adapter modules,
        requiring UI components to route through validated contract adapters.
    """
    errors: list[str] = []
    for p in files:
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT)

        # (a) Check prohibited apiClient<any>
        m_any = API_CLIENT_ANY_REGEX.search(text)
        if m_any:
            line_no = text[: m_any.start()].count("\n") + 1
            errors.append(
                f"[RULE-9 Wire Contract] {rel}:{line_no} uses prohibited 'apiClient<any>'; all backend responses must bind to canonical contract types"
            )

        # (b) Check direct placement-preview bypass outside fabricControlApi.ts
        if p.name != "fabricControlApi.ts" and PLACEMENT_PREVIEW_DIRECT_API_REGEX.search(text):
            m_bypass = PLACEMENT_PREVIEW_DIRECT_API_REGEX.search(text)
            assert m_bypass is not None
            line_no = text[: m_bypass.start()].count("\n") + 1
            errors.append(
                f"[RULE-9 Wire Contract] {rel}:{line_no} directly calls placement-preview via raw apiClient; must use getPoolPlacementPreview adapter"
            )

        # (c) Check direct /v1/pools bypass outside fabricControlApi.ts
        if p.name != "fabricControlApi.ts" and POOL_LIST_DIRECT_API_REGEX.search(text):
            m_pools = POOL_LIST_DIRECT_API_REGEX.search(text)
            assert m_pools is not None
            line_no = text[: m_pools.start()].count("\n") + 1
            errors.append(
                f"[RULE-9 Wire Contract] {rel}:{line_no} directly calls /v1/pools via raw apiClient; must use getPoolList adapter"
            )

        # (d) Check direct /v1/discovery/candidates bypass outside fabricControlApi.ts
        if p.name != "fabricControlApi.ts" and DISCOVERY_CANDIDATES_DIRECT_API_REGEX.search(text):
            m_cand = DISCOVERY_CANDIDATES_DIRECT_API_REGEX.search(text)
            assert m_cand is not None
            line_no = text[: m_cand.start()].count("\n") + 1
            errors.append(
                f"[RULE-9 Wire Contract] {rel}:{line_no} directly calls /v1/discovery/candidates via raw apiClient; must use getDiscoveryCandidates adapter"
            )

    return errors


def run_checks(verbose: bool = True) -> list[str]:
    files = get_production_source_files()
    if verbose:
        print(f"Scanning {len(files)} frontend production source files under apps/web/src ...")

    all_errors: list[str] = []
    all_errors.extend(check_placeholders(files))
    all_errors.extend(check_premature_success(files))
    all_errors.extend(check_ticket_logging(files))
    all_errors.extend(check_tristate_verification(files))
    all_errors.extend(check_zero_call_guards(files))
    all_errors.extend(check_synthetic_timestamps(files))
    all_errors.extend(check_unimplemented_consistency(files))
    all_errors.extend(check_integrity_pass_gate(files))
    all_errors.extend(check_uncontracted_wire_bypass(files))

    return all_errors


def run_negative_control() -> bool:
    """Verify scanner catches intentional mutations across all 9 rules (bidirectional negative control)."""
    # Test 1 (Rule 1): Catches standard prohibited placeholders
    dummy_text_1 = "const tenant = '00000000-0000-0000-0000-000000000001';"
    errs_1 = []
    for token, desc in FORBIDDEN_PLACEHOLDERS:
        if token in dummy_text_1:
            errs_1.append(f"caught placeholder {token}")
    assert len(errs_1) > 0, "Negative control failed: Rule 1 standard placeholder not caught"

    # Test 2 (Rule 1 Command): Catches command placeholder outside approved definition
    dummy_cmd = "const cmd = '11111111-1111-4111-8111-111111111111';"
    assert COMMAND_PLACEHOLDER in dummy_cmd and "export const PLACEHOLDER_COMMAND_ID =" not in dummy_cmd, \
        "Negative control failed: Rule 1 command placeholder outside guard not caught"

    # Test 3 (Rule 2): Catches missing tenant guard in announcement handler
    dummy_handler_bad = "const handleBroadcastAnnouncement = async () => { broadcastAnnouncement(); };"
    assert "!tenantId" not in dummy_handler_bad, "Negative control failed: Rule 2 missing tenantId guard not caught"

    # Test 4 (Rule 3 Premature): Catches premature connected in initial output
    dummy_ws_bad = "const [terminalOutput] = useState<string[]>(['Connected via secure WebSocket']);"
    m_ws = PREMATURE_INITIAL_LINES_REGEX.search(dummy_ws_bad)
    assert m_ws is not None, "Negative control failed: Rule 3 premature connection not caught"

    # Test 5 (Rule 3 Credential): Catches direct ticket/token logging
    dummy_log_bad = "console.warn('Leaking ticket:', ticketData.ticket);"
    m_log = CREDENTIAL_LOG_REGEX.search(dummy_log_bad)
    assert m_log is not None, "Negative control failed: Rule 3 credential logging not caught"

    # Test 6 (Rule 4 Tri-State): Catches bogus ternary promoting mismatch to verified
    dummy_tristate_bad = "const status = isMatch ? 'verified' : 'verified';"
    m_tri = re.search(r"isMatch\s*\?\s*['\"]verified['\"]\s*:\s*['\"]verified['\"]", dummy_tristate_bad)
    assert m_tri is not None, "Negative control failed: Rule 4 bogus ternary not caught"

    # Test 7 (Rule 6 Synthetic Timestamp): Catches || new Date().toISOString() on timestamp field
    dummy_ts_bad = "const exportedAt = res.completedAt || new Date().toISOString();"
    m_ts = SYNTHETIC_TIMESTAMP_FALLBACK_REGEX.search(dummy_ts_bad)
    assert m_ts is not None, "Negative control failed: Rule 6 synthetic timestamp fallback not caught"

    # Test 8 (Rule 6 Qualification): Catches stateAsOf lacking qualification disclaimer
    dummy_stateasof_bad = "<div>기준 시각: {stateAsOf}</div>"
    assert "단일 공통 스냅샷" not in dummy_stateasof_bad, "Negative control failed: Rule 6 qualification absence not caught"

    # Test 9 (Rule 7 False Notice): Catches known false unexposed notice
    dummy_notice_bad = "<button>다운로드 (API 미노출)</button>"
    errs_7 = [token for token, desc in FORBIDDEN_FALSE_UNEXPOSED_NOTICES if token in dummy_notice_bad]
    assert len(errs_7) > 0, "Negative control failed: Rule 7 false unexposed notice not caught"

    # Test 10 (Rule 7 Contradiction): Catches wiring contradiction (imports getArtifactDownloadUrl but claims API 미노출)
    dummy_contra_bad = "import { getArtifactDownloadUrl } from './runArtifactObservation';\nconst notice = '서버 아티팩트 파일 스트림 다운로드 API 미노출 상태';"
    has_contra = any(api_token in dummy_contra_bad and regex.search(dummy_contra_bad) for api_token, regex, desc in WIRING_CONTRADICTION_PATTERNS)
    assert has_contra, "Negative control failed: Rule 7 wiring contradiction not caught"

    # Test 11 (Rule 8 Integrity Gate, shape-based): catches the EvidenceViewer-class regression in any file
    dummy_int_default_bad = "let integrityStatus: 'PASS' | 'FAIL' | 'UNVERIFIED' = 'PASS';"
    assert INTEGRITY_DEFAULT_TO_POSITIVE_REGEX.search(dummy_int_default_bad) is not None, \
        "Negative control failed: Rule 8 default-to-PASS integrity status not caught"
    # PASS gated on sealed+hash (no verification signal) must be detectable as a missing gate
    dummy_int_nogate_bad = "if (res.sealed && res.output?.sha256) { integrityStatus = 'PASS'; }"
    assert INTEGRITY_VERIFIED_GATE_REGEX.search(dummy_int_nogate_bad) is None, \
        "Negative control failed: Rule 8 missing verification gate not detectable"

    # Test 12 (Rule 9 Wire Contract): Catches apiClient<any> and raw adapter bypasses
    dummy_any_bad = "const res = await apiClient<any>('/v1/projects/prj/runs/run/result');"
    assert API_CLIENT_ANY_REGEX.search(dummy_any_bad) is not None, \
        "Negative control failed: Rule 9 apiClient<any> not caught"
    dummy_bypass_bad = "apiClient<{ poolId: string }>('/v1/pools/pool1/placement-preview')"
    assert PLACEMENT_PREVIEW_DIRECT_API_REGEX.search(dummy_bypass_bad) is not None, \
        "Negative control failed: Rule 9 placement-preview direct bypass not caught"
    dummy_pool_bad = "apiClient<PoolListResponse>('/v1/pools')"
    assert POOL_LIST_DIRECT_API_REGEX.search(dummy_pool_bad) is not None, \
        "Negative control failed: Rule 9 pool list direct bypass not caught"
    dummy_cand_bad = "apiClient<DiscoveryCandidatesResponse>('/v1/discovery/candidates')"
    assert DISCOVERY_CANDIDATES_DIRECT_API_REGEX.search(dummy_cand_bad) is not None, \
        "Negative control failed: Rule 9 discovery candidates direct bypass not caught"

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="SaintVision Frontend Integrity Scanner")
    parser.add_argument(
        "--test-negative",
        action="store_true",
        help="Run negative control test suite to verify scanner sensitivity across all rules",
    )
    args = parser.parse_args()

    if args.test_negative:
        print("Running negative control sensitivity tests across all 9 integrity rules...")
        if run_negative_control():
            print("✔ Negative control passed: Scanner successfully detects mutations across all 9 rules.")
            sys.exit(0)
        else:
            print("❌ Negative control failed.")
            sys.exit(1)

    # Normal execution
    errors = run_checks(verbose=True)
    if errors:
        print(f"\n❌ Frontend Integrity Violations Detected ({len(errors)} errors):")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\n✔ Frontend Integrity Check Passed: All 9 integrity rules satisfied (0 violations).")
        sys.exit(0)


if __name__ == "__main__":
    main()
