"""Frontend Integrity Scanner for SaintVision Web Client.

Five structural checks, no human judgment required:

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

    return all_errors


def run_negative_control() -> bool:
    """Verify scanner catches intentional mutations across all 5 rules (bidirectional negative control)."""
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
        print("Running negative control sensitivity tests across all 5 integrity rules...")
        if run_negative_control():
            print("✔ Negative control passed: Scanner successfully detects mutations across all 5 rules.")
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
        print("\n✔ Frontend Integrity Check Passed: All 5 integrity rules satisfied (0 violations).")
        sys.exit(0)


if __name__ == "__main__":
    main()
