---
doc_id: "HISTORY-R5-PREPARATION-EXECUTION-20261104"
title: "r5 legitimate runtime preparation and released execution"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-04T14:42:00+09:00"
source_of_truth: "Git"
---

# r5 preparation and execution record

Task SUPERVISION-20261104-CODEX / task_4a4eaf27c548 / ctx_78f45e976cf3.
Owner Codex; technical release coordinator. Claude accepted plan
4f53b5ab85d6fcff765baf7789c3dec59de86561 WITH CONDITIONS C1-C4, relayed by
**msg_b46b1f38a68a**: exact per-step arrays/digests, six-day max leaf and earliest
CP/all-Node renewal time, new admin-copy ownership/retention, pre-write issuer/clock/
source/old-state checks. This releases only isolated r5 under existing user approval;
the scheduler remains not approved for live registration. Independent review of the
actual new outcome remains pending until measured evidence exists.

Evidence branch agent/codex/supervision-20261104-r5-plan, base 4f53b5ab.
Execution source is frozen **03e17c31cf535008d39534aaa80d3ae274bd75cc**, in an
owned clone with its own Git directory under this checkout's ignored `.work`.
The original private plan SHA-256
**2614a1b3b4b3201163d2f6e0ef0295747509d5b4ec0eb388e055f00c6a24c039**
remains byte-identical. A separate prepared-runtime plan derives from that digest;
only the owned source/runtime paths and measured preparation evidence are added.
No other checkout or launcher check was changed.

## Legitimate dependency preparation

- A local `git clone --shared --no-checkout` created a separate owned common directory;
  origin was set to the official project URL and checkout detached at exact 03e17c31.
  Shared worktrees would have resolved a missing runtime in another checkout, so a
  separate clone supplies the reviewed launcher's actual common-directory contract.
  All three Git commands exited 0; tracked source remained clean.
- Runtime uses **Python 3.14.7**, **76** exact version pins from the already exercised
  working environment. The first download inherited an unreachable NVIDIA extra
  index; only its verified task-owned pip process was stopped (exit -1), then a
  process-local clean pip environment and explicit official PyPI index succeeded.
  No machine/user package-index configuration was changed.
- All 76 wheels were SHA-256 recorded, then installed **offline with require-hashes**
  into the owned source's real `.venv`, exit 0. `pip check` exited 0. The hash lock
  digest is **aac4ef21de4e8f3e481962f4c86520f01206e6505e0fe16df9feaa26767fa92e**;
  pin list digest is **42b1750b79f1598e2624f44e5f5000dd095aa19104221ad2fa6a5c523e80e016**.
- **Node 24.10.0 / npm 11.6.1**; `npm ci --no-audit --no-fund` installed 177 packages,
  exit 0. Exact source package-lock SHA-256 is
  **e26cb03e08efa76dbe19f43dfa5afe779b46189181e020ab8503ad4cf428a818**.
  `npm run build` (TypeScript then **Vite 6.4.3**) exited 0. The build's large-chunk
  warning is retained as a warning, not a failed or completed browser acceptance.
- KST 14:03:13-14:04:04, new owned Python runtime on exact source 03e17c31:
  `python -X utf8 -m pytest tests/test_lan_leaf_rotation.py tests/test_lan_leaf_rotation_standalone_runtime.py tests/core/test_lan_pki.py tests/core/test_launcher_failure_boundaries.py -k 'not every_deploy_powershell_script_parses or every_deploy_powershell_script_parses' -q --junitxml=<unique-evidence>`
  exited **0**, **112 passed / 6 skipped / 0 failed / 0 errors / 0 deselected**.
  The selection expression selects the full collected set; six skips are reviewed
  Windows symlink boundaries. Real launcher dependencies now exist at the exact
  paths the unmodified source derives. JUnit, version pins, wheel hashes and
  preparation manifest are in the unique Evidence directory.

## Pre-write and execution checkpoint

Recheck all C1-C4 gates immediately before mutation. Bind every dynamic image/archive,
new Node prepare/enroll/finish and narrow firewall command to actual initialized r5
epoch/identities and record exact redacted argument arrays, KST, exit and public
artifact digests. Never execute a placeholder. Preserve any partial r5 on failure;
do not restore expired r4 authority or alter old volumes/keys/data/controls. Actual
stage receipts and acceptance will be appended below. No scheduler registration,
workload submission, resource offer or global control change is released.

## Measured released execution

The prepared-runtime private plan digest is
**2f2979c61015e1ce62d5c098befc5b8119c1938b76480e65c3022e8bf8e7bf1d**;
the original 2614a1b3 plan remains unchanged. Exact unredacted arrays and diagnostics
are retained only under the task's protected `.work/supervision-codex-audit/`;
the Evidence JSONL contains redacted argument arrays, source SHA, script/input
SHA-256, KST, elapsed time and actual command exits. No command contained an
unresolved operational placeholder. Actual image tag, build/export directory,
archive, Node IDs and prepare/enroll/finish arrays were bound after fresh init.

| Gate/stage | Completion KST 2026-11-04 | Actual outcome |
|---|---|---|
| preflight, immediately rechecked before DB writes | 14:13:21 | exit 0; source 03 clean, issuer/key/chain pin and revocations valid, both known SSH identities/host keys, Docker APIs 1.52/1.56, NTP and bounded clock skew below one second, new namespace/ports absent, four old-state byte baselines unchanged |
| database | 14:13:54 | exit 0; only new `saintvision_lan_r5_f8923863` and its runtime role created in the verified existing pinned PG16.10 container/network; correct credentials accepted, missing/wrong credentials rejected, SCRAM and least privilege verified |
| init/bind | 14:15:38 | both CLI exits 0; new tenant/epoch, two fresh Node identities, new CP/signing material, external valid issuer, passfile-backed DB auth, owned loopback SSH transport |
| exact-source image and bundles | 14:17:37 | exit 0; source archive 03, new-epoch tag, network-disabled/no-pull build, save/inspect and returned hashes matched, reviewed bundle/OCI validator accepted both new matching archives |
| two new Node-local identities | 14:19:49 | every prepare/enroll/finish exit 0; new paths/container/volume absent first, only public CSRs returned, CSR/leaf public keys matched, only public signed leaves returned, private keys remained on their Nodes |
| two real mTLS observations and DB acceptance | 14:22:55 | exit 0; exactly two online/fresh Nodes, advancing heartbeats and persisted snapshots, lan-observe-v1, positive measured CPU/RAM, exact new epoch/channels, enabled version 1 and leaf pins matched, kill switch true, zero runs/resources |
| console and owned shortcut cutover | 14:31:46 | exit 0 after corrected operator verification; overview 18082 and web 3000 HTTP 200, continuous snapshots/heartbeats advanced, one loopback-only listener each 3000/18082/55448, exact source/state/tunnel process-token ownership, shortcut exact new state/source and hidden; prior owned link preserved privately |
| source-bound public bootstrap | 14:36 | exit 0; both authorized Node sources health/public-leaf HTTP 200 with independent own-leaf hash match, non-Node CP source artifact HTTP 403; no firewall rule changed |
| actual Node runtime readback | 14:37 | exit 0; both running, read-only root, privileged false, ALL capabilities dropped, positive CPU/memory/PID limits; each local private key remains regular, owner matched and mode 0600 |

C3 is measured: a new remote private credential directory is **0700**, the new
host-local admin copy is **0600**, its owner equals the authorized SSH user, and
its bytes match the existing trusted source. The source credential is unchanged.
Retention of this new copy is intentional for bounded r5 administration; its
separate private location and the returned new passfiles are not published.
No old credential, key, Node, DB, volume, customer data or global control was
replaced. Four preserved CP-state aggregate file baselines remained identical
through the final cutover. Existing old Node material and names were never targets
of prepare/finish; namespace collisions fail rather than overwrite.

## Operator verification failures retained

The initial owned-tunnel wrapper discarded the helper's boolean return. It was
corrected to explicitly reject false and the **actual strict ownership check
passed before init**; a printed marker alone is not evidence of ownership.

The first console-launch wrapper used captured pipes; descendant Windows handles
kept its capture stalled after services had started. Only its identity-verified
operator Python process was stopped; live source/state-owned services remained.
Its launcher exit is **unknown**, not PASS. Operator capture was changed to private
file-backed streams; the same unmodified reviewed launcher then exited **0** in
5.593 seconds while reusing the verified listeners.

The first shortcut readback mistakenly used a helper that checks `--state` for
Python processes against PowerShell `-StatePath`; it exited **1**, stopping the
operator stage with **exit 2** at 14:29:48. This was an operator verification error,
not a product result. Exact `-File`, `-StatePath`, `-DatabaseTunnelTarget` and
`-SshKeyPath` token checks then passed at 14:31:39, followed by final stage exit 0.
The receipt stream retains both failures and the later passing readback. Original
shortcut backup was retained across the readback retry.

## Actual validity and next executable action

Fresh six-day maximum material is measured, not borrowed from expired r4:

| Public leaf | notAfter KST |
|---|---|
| CP, earliest | **2026-11-10 14:15:35** |
| Node 1 | 2026-11-10 14:19:30 |
| Node 2 | 2026-11-10 14:19:42 |

The earliest 48-hour renewal window starts **2026-11-08 14:15:35 KST**.
No renewal task was registered, no live rotation was attempted and no automatic
workload/resource submission was enabled. Coordinator must dispatch reviewed
prevention before that window and ensure renewal completes before earliest expiry.
If #402 cannot meet review/CI/landing gates in time, dispatch a separately reviewed
manual supported batch while leaves are still valid; preserve exact journals and
measure all-member replacement and final real observations. Never treat expired
old leaves as fresh authority or invent a partial journal for untouched r4.

Next owner/action: **coordinator/Claude** independently review this actual r5
execution evidence and re-observe its live overview. **Codex/Claude/coordinator**
complete #402 exact-head review and CI, then coordinator owns integration and a
separate task-registration dispatch. Scheduler correction source is
**b5b8ca68398517f6227a81caac02654a848c8b1d**, distinct from r5 operational source
**03e17c31** and this evidence commit. Both all-member regressions failed against
5933 (pytest exit 1); dirty and clean exact b5b8 runs each exited 0 with **35 passed /
1 Windows capability skip**. No hosted or review result is inferred from that run.

This restores **two-Node development observation only**. Five-Node readiness still
lacks three admitted identities: CP co-location is blocked by measured Docker API
1.41; the remaining known worker's documented SSH identity is refused; another
worker lacks the required inventory/identity. Five slots have 74 missing fields.
S01 U1-U6 still requires the real inventory/SSH bindings, DNS/IdP issuer and fresh
trust configuration, explicit five-Node admission/reachability, fresh attested
storage roundtrip and restore/PITR acceptance, and required exact-source CI/review.
Pinned IdP discovery and MinIO health reachability do not prove those acceptances.
Original task status remains **2 done / 4 blocked / 42 planned / 0 ready**.

No shared Obsidian export, shared Index/registry/board edit or integration merge was
performed. No physical acceptance, authenticated browser journey, workload
execution, object write or PITR result is claimed from loopback HTTP readiness.
Retain this worker checkout and its frozen `.work/r5-reviewed-source-03e17c31`
clone/runtime while r5 is live: current processes and the owned desktop shortcut
depend on those exact paths. Task completion is not permission to clean them up;
any source-path migration must rebind and remeasure the owned launcher first.

Final read-only preservation check at KST 14:40 used **r4's existing configured
DSN** without printing it, required transaction_read_only=on and statement/connect
timeouts, and exited **0**: old kill switch true, runs/resources 0, exactly two
enabled version-1 channels with still-expired leaves, plus unchanged file baselines
for all four old states. This separately checks the old DB facts after new r5 writes.

Final unique-evidence document gates at KST 14:41: check_docs **exit 0** (1170
versioned documents), check_ontology **exit 0**, git diff --check **exit 0**.
Isolated `sync_obsidian.py --check --vault <task-private-check-vault> --state
<task-private-check-state> --conflicts-out <task-private-conflicts>` exited **0**:
2097 managed / 2097 pending / 0 conflicts / **no writes**. This is not a shared
Obsidian export. Redacted receipts contain **167** rows; binding digests and the
final private operator-source digest are in `r5-evidence-bindings.json`.
The Evidence-local attributes preserve the exact two executed CRLF dependency-lock
inputs and LF receipt bytes. Their staged Git-blob hashes were independently
checked against the recorded digests; automatic newline conversion is not allowed
to silently change these three hashed artifacts. Other repository paths are unaffected.
The first staged-byte hash gate exited **1**, detecting Git's LF conversion of the
actual CRLF runtime lock inputs before commit. The scoped attributes plus explicit
`git add --renormalize` on only these three artifacts corrected the index; the next
hash gate exited **0**, proving exact working/index bytes and all three recorded
SHA-256 values. The failed integrity check is retained here, not reported as PASS.
The subsequent cached diff check exited **2** because the now-preserved CRLF was
classified as trailing whitespace. Only these two frozen input artifacts declare
CR-at-EOL as a line terminator, retaining the normal blank-at-EOL/EOF and
space-before-tab rules; the corrected cached diff check then exited **0**.
