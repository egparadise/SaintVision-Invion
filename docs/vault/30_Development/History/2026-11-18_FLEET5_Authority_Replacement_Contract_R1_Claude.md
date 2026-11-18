---
doc_id: "HISTORY-FLEET5-AUTHORITY-REPLACEMENT-CONTRACT-R1-20261118-CLAUDE"
title: "FLEET5 authority replacement and advance-renewal contract R1 (proposed)"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-18T22:10:00+09:00"
source_of_truth: "Git"
---

Task FLEET5-AUTHORITY-REPLACEMENT-CONTRACT-R1-20261118 (Orca task_bbffe750d781, dispatch ctx_578424c46777) started 2026-11-18 21:35 KST.

| Item | Value |
|---|---|
| Branch | `egparadise/fleet5-authority-replacement-20261118` (Orca-assigned worktree) |
| Base | Root544 `d81d40f824538a4ef553cc8ae4aa75f7c012e325` |
| Boards read | Index 1.0.544, Codex 1.0.505, Claude 1.2.132 |
| Read first | AGENTS.md, the R2 plan [[Current three-Node pilot renewal preflight and recovery plan R1]] |

**Roles:**
- Claude is the author of this proposed contract.
- Independent security review goes to Codex and has **not been performed**.
- Root owns canonical APPLY, SSH, private preflight, DB recovery and every operation.
- The Codex custody/preflight worker owns retained-key custody and read-only preflight. Its files (`tools/recovery_preflight/*`, `services/node-agent/recoverycandidate/*`, `contracts/proposed/expired-policy-custody-*` and tests) were **not touched**.

## What was done

- Added the proposed contract [[Proposed FLEET5 authority replacement and advance-renewal contract R1]]. It covers:
  - C1: independent new trust;
  - C2: separation of ROTATION and NEW_ENROLLMENT, and a unique PC1 identity;
  - C3: preservation of the epoch and the C/P counters;
  - C4: the phase journal;
  - C5: the interrupted-migration recovery decision;
  - C6: the advance-renewal formulas;
  - C7: the CP client and role keys.
- Added a machine-checkable schema, a checker and a recovery function, plus a drift-gated fixture generator. It produces 1 real HOLD instance, 14 positive fixtures, 30 rejection fixtures and 1 operator handoff.
- Coordinator follow-up (msg_c0eb0a51d670) asked for a concrete PC1 first-enrollment fixture and an operator handoff. Added:
  - fixture `p14`, the concrete PC1 first enrollment;
  - `handoff/pc1-first-enrollment-handoff.json`, which carries the new identity, the public CA evidence and a five-node inventory accepted by `tools/five_node_lab_preflight.py` (contract C8);
  - expiry-boundary and interruption-sweep tests. The gate has 155 tests.
- Added the pytest gate `tests/core/test_fleet5_authority_replacement_proposal.py`. Core and Backend whole-suite pytest collect it, so no workflow edit was needed.
- Source evidence came only from Root544 committed files. No live credential, SSH, DB, Docker, certificate or key access was used. Nothing was synced canonically, activated or released.

## Findings that shaped the contract

1. **The 7-day CA default.** `tools/lan_pki.py` `ca_pair()` issues a 7-day CA. The fleet CA's 11-07 → 11-14 lifetime is consistent with it. With leaves capped at six days, there was never a window to stage a successor CA. C6 makes this machine-rejected (fixture `r18`).
2. **Account names are not identity.** PC1 (`inviz@192.168.45.13`) and PC4 (`inviz@192.168.45.210`) share the account name `inviz`. The contract binds identity to NodeID + key + epoch URI only, and rejects a PC1 that copies PC4's NodeID or share directory (`r09`).
3. **The DB has not been recovered.** The preserved epoch and the C/P counters cannot be PROPOSED from historical evidence (`r16`). The real instance therefore stays HOLD until Root reads back the DB.
4. **Node CA roots load once at startup.** Node-side anchor staging (A2) can only happen inside the separately reviewed serving-binary migration handoff. This contract authorizes no restart.

## Verification

Local gates ran on Windows with Python 3.10.11 and `PYTHONUTF8=1`, individually through an argv driver, 2026-11-18 22:01–22:13 KST. **All 12 exited 0**:
- check_docs (1276 documents)
- path-citation ratchet against d81d40f8
- contract bindings, frontend integrity, test_sync
- ontology generation, ontology check, single-source ratchet
- sync_obsidian `--check` (3797 files, 3 pending exports, 0 conflicts; no apply)
- the new checker (45 documents)
- generator `--check`
- pytest (155 passed)

Record: `Evidence/fleet5-authority-replacement-r1-20261118-claude/local-gates.json`. The driver's own git-status decode failed on cp949 and printed `clean`, so that field was corrected by hand to "dirty candidate files".

Hosted runs at exact candidate `12b67c0126c96f09e06a0fa8f78a5d2a73f7461d`, dispatched with correlation IDs `ar-r1-12b67c01-*`. **All three succeeded**, and no step concluded other than success or skipped:

| Workflow | Run | Result |
|---|---|---|
| Docs | 44311583254 | success |
| Core | 44311588702 | success; `core` job 9032 passed, 46 skipped, 2 deselected |
| Backend | 44311594014 | success; 3.12 and 3.14 each 8674 passed, 75 skipped, 2 deselected |

Record: `hosted-ci.json`. The new test file is under `testpaths` and in no ignore list. Its inclusion in those totals is inferred from configuration, because `-q` output lists no individual passing tests.

## Next

1. Codex performs the independent security review of the contract, schema and checker. The questions are at the end of the contract.
2. The Codex custody/preflight card supplies `custodyState`, custody refs and authenticated floors.
3. Root recovers the DB and reads it back read-only, and diagnoses PC1 without secrets.
4. Then the author revises the real instance toward PROPOSED.

Nothing here is an operating release.
