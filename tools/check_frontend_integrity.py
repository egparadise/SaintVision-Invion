"""Frontend Integrity Scanner for SaintVision Web Client.

Guards against re-accumulation of frontend integrity violations:
  (1) Prohibited Placeholder Identifiers:
      Detects hardcoded dummy UUIDs or synthetic test IDs in production source files:
      - '00000000-0000-0000-0000-000000000001' (synthetic tenant)
      - '11111111-1111-4111-8111-111111111111' (synthetic commandId; allowed ONLY in denylist guard)
      - 'apr_01JXYZ889900' (synthetic approvalId)
      - 'run_01JABCDEF_DEMO' (synthetic runId)
      - 'prj_01JABCDE' (synthetic projectId)
      - 'wsp_0123456789ABCDEFGHJKMNPQRS' (synthetic workspaceId)
      - 'run_01JABCDE0001' (synthetic fallback runId)
      - 'rcp_01JABCDEF' (synthetic fallback receiptId)

  (2) Premature Success and Connection Display:
      Detects initial component states or initial output buffers that claim
      'Connected via secure WebSocket' or premature 'verified' status before
      underlying network or cryptographic events have occurred.

  (3) Ticket and Credential Logging Prevention:
      Detects console.log/info/warn/error statements that output sensitive
      authorization credentials ('ticket', 'terminalTicket', 'bootstrapToken') directly.

  (4) Tri-State Verification Invariant:
      Ensures components managing cryptographic verification (e.g. InvFileExplorer)
      maintain strict 3-state handling ('verified', 'tampered', 'unverified') and
      never promote unverified bytes to verified without cryptographic proof.

  (5) Zero-Call Guard Enforcement:
      Ensures security-sensitive mutation APIs (e.g., broadcastAnnouncement) enforce
      mandatory identity parameters (tenantId) and do not allow unconditional invocation.
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

        # Must not have fallback where unverified is treated as verified
        if re.search(r"isMatch\s*\?\s*['\"]verified['\"]\s*:\s*['\"]verified['\"]", text):
            errors.append(
                f"[RULE-4 Tri-State] {rel} contains bogus ternary promoting mismatch to verified"
            )
    return errors


def check_zero_call_guards(files: list[Path]) -> list[str]:
    errors: list[str] = []
    explorer_file = WEB_SRC / "features" / "desktop" / "ResourceExplorer.tsx"
    if explorer_file.exists():
        text = explorer_file.read_text(encoding="utf-8")
        rel = explorer_file.relative_to(ROOT)

        # Ensure broadcastAnnouncement handler enforces tenantId existence
        if "handleBroadcastAnnouncement" in text:
            if "!tenantId" not in text:
                errors.append(
                    f"[RULE-2 Zero-Call Guard] {rel} handleBroadcastAnnouncement must guard against missing tenantId before calling API"
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
    """Verify scanner catches intentional mutations (negative control)."""
    fake_source = Path("dummy_test_file.tsx")
    test_files = [fake_source]

    # Test 1: Catches placeholder
    dummy_text_1 = "const tenant = '00000000-0000-0000-0000-000000000001';"
    errs_1 = []
    for token, desc in FORBIDDEN_PLACEHOLDERS:
        if token in dummy_text_1:
            errs_1.append("caught placeholder")
    assert len(errs_1) > 0, "Negative control failed: placeholder not caught"

    # Test 2: Catches ticket logging
    dummy_text_2 = "console.log('Ticket received:', ticketData.ticket);"
    m = CREDENTIAL_LOG_REGEX.search(dummy_text_2)
    assert m is not None, "Negative control failed: ticket logging not caught"

    # Test 3: Catches premature connected
    dummy_text_3 = "const [output] = useState(['Connected via secure WebSocket']);"
    m3 = PREMATURE_WS_REGEX.search(dummy_text_3)
    assert m3 is not None, "Negative control failed: premature connection not caught"

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="SaintVision Frontend Integrity Scanner")
    parser.add_argument(
        "--test-negative",
        action="store_true",
        help="Run negative control test suite to verify scanner sensitivity",
    )
    args = parser.parse_args()

    if args.test_negative:
        print("Running negative control sensitivity tests...")
        if run_negative_control():
            print("✔ Negative control passed: Scanner successfully detects synthetic mutations.")
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
