---
doc_id: "EVIDENCE-R5-FOLLOWUP-0814EC2A5432"
title: "r5 C1-C4 executable follow-up and measured source03 restoration"
version: "1.0.0"
status: "review_requested"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-04T16:45:00+09:00"
source_of_truth: "Git"
---

# Packet and acceptance boundary

Task task_0814ec2a5432 / dispatch ctx_81cc0efa0eea; owner Codex, reviewer Claude.
This is a separate follow-up to evidence commit
`52e236491213dc4d57ea98fc24d560187ab8d651`. The private executable packet is
`D:/Project/SaintVisionI-Invion/supervision-codex-20261104/.work/r5-followup-0814ec2a5432`.
`packet-manifest.json` binds the actual private bytes; `review-candidates` contains
byte-identical generic source for review, with Git text conversion disabled.
Run commands from the private packet, which retains the protected local inputs.
Private configurations, actual Node identities, SSH addresses/keys, raw process
arguments, and database connection strings are deliberately absent from Git.

The C1-C4 packet is prepared and locally validated. **Runtime preparation, IdP
writes, S4U task registration/start, certificate renewal and attended transition
were not executed.** Their next dispatch still needs the coordinator's technical
release after exact-head review, CI, and persistence evidence. User authorization
is already granted; this is a technical acceptance boundary.

| Private input | SHA-256 |
| --- | --- |
| renewal-config.private.json | `9513bd3875ae3845a00f7f9ca674685bb393656db89963d9fc57ad7e25128d8f` |
| bindings.private.json | `74aaadc8760a8582697fd9a310189bee1f413909c5e0cd15dbba54636e56ea06` |
| idp-local-repair-plan.private.json | `585413eeee73cddd483ff6552f3ce778213a31c7870b7294b97be659689717f0` |
| s4u-probe-plan.private.json | `c3f6553cc48d48cc853196333ffff2b2bfc4a05b6f93ebd2f9be750d8b927415` |
| preparation-commands.private.json | `c981dc09dc8eaf5ff7a1596771cb679cad43024cc913abefa119998ceba4c7e6` |
| registration-and-first-attended-sequence.private.json | `18fe469f1ce459262c9071ad53ff67c47cdf163926a2a81ab97a6bfc6004144d` |

`rebind-delta.json` verifies all 14 gates retain 99 common input pins each; only
the changed gate and binding pins move to the new packet. Six direct lan_pilot
arrays also gain `-E`. Only two preparation install commands change. Prior
authority, CSR, source, executable, runtime bundle, state, tenant/epoch and actual
two-member identities remain pinned. All 68 top-level prior-packet files and five
original identity inputs still match their baselines; identity/backup targets
remain absent. No canonical product source changed.

# C1-C4 implementation and executable order

C2: `IdPPathGuards.private.ps1` walks every scoped ancestor from the trusted
workspace root, rejecting reparse points and non-directories. The apply script
verifies old inputs, candidates, tenant and freshness, creates/checks the exact
immediate `intranet/backups` parent, rechecks both new targets, then creates the
unique backup and identity directories without overwriting existing targets.
Existing targets fail closed. Only the helper ran on temporary fixtures, including
an actual Windows junction; the real apply entrypoint did not run.

C3: every wrapper child receives an environment with PYTHONPATH/PYTHONHOME removed
case-insensitively. All six direct lan_pilot prepare/stage/commit/observe arrays
use `-E -B`, as does currentStatus. This preserves the script-directory imports
that `-I` would break. Actual source03 `--help`, direct `status`, and wrapped
currentStatus all exited 0 under deliberately invalid inherited Python paths;
both status calls returned the actual two online members. Parent environment
preservation is covered by the guard test.

C4: read-only SSH probes at 16:02:35 KST resolved actual `/usr/bin/bash` on each
Node, root-owned mode 0755. The two exact Bash hashes, versions and Python
resolutions are in `bash-readonly-bindings.json`. Each future install checks the
actual Python executable/hash and `python3` resolution, the actual Bash resolution
and hash, and each transferred helper/archive hash; it invokes absolute pinned
Bash. After prep it invokes the actual standalone worker's `runtime-preflight`
and requires compatible=true, cryptography 50.0.1, UTC certificate API=true, and
exact Python **3.14.4 / 3.12.3** respectively. The second Node's actual 3.12 worker
execution remains required; mocked version-drift tests do not count as that proof.
No runtime directory or transfer directory was created by this task.

The coordinator can dispatch the following exact ordered operations using the
named JSON arrays; every native exit must be recorded immediately and stop on
nonzero. Existing failure artifacts are preserved and diagnosed, never bypassed.

1. First complete the functional **same-PID** persistence check after worker_done
   and a fresh terminal reopen. Compare the recorded process pairs, exact owner,
   source/state, listeners and advancing fresh mTLS observations. No service
   replacement is needed merely because a runtime owns an internal job object.
2. Revalidate the manifest, original 68 files, source03 head/cleanliness, protected
   state bytes, public leaf validity and actual two members. Read the exact FD
   post-landing CI results and Claude's review of this packet before release.
3. After explicit runtime-prep release, execute the existing directory/transfer
   steps and the two updated `*-install-and-preflight-new-r5-runtime` entries in
   `preparation-commands.private.json`, in their listed order. Feed each pinned
   stdinFile as bytes, checking stdinSHA256 first. These steps affect only the
   previously absent isolated runtime/transfer locations; worker identity/key and
   workload state are not changed. Preserve the actual worker preflight output,
   especially Python 3.12.3. Stop on any failure.
4. After separate S4U probe release, use `registration.probeRegisterAfterTechnicalRelease`
   from `registration-and-first-attended-sequence.private.json`, read back its
   exact owner/principal/action, then use `probeDemandStartAfterOwnerReadback`
   **once**. The task is limited-current-user S4U, demand-only, zero triggers,
   IgnoreNew, ten-minute limit. Its exact argv allowlist contains currentStatus,
   runtimePreflight-1 and runtimePreflight-2 only; duplicates/extra actions are
   refused. It verifies actual S4U/noninteractive owner context, all pins and
   one-shot exclusive intent/receipt. Record child exits, actual 3.12/3.14 results,
   fresh member status and LastTaskResult. A failure is a blocked lane; preserve
   the task/intent/receipt and diagnose instead of silently re-running it.
5. Even a successful context probe does not establish unattended renewal. The
   production renewal task remains unregistered. For the first certificate cycle,
   recheck the public window and obtain the coordinator's technical release for
   the pinned `attendedFirstCycle` 14-gate array. The observed window begins
   **2026-11-08 14:15:35 KST**, before earliest expiry **Nov 10 14:15:35 KST**.
   At 16:39 Nov 4 the window is false; no early rotation was attempted.
6. The 14 gates are currentStatus; actual runtimePreflight x2; certificate prepare;
   public bundle install x2; stage x2; commit; **attended transition**; observe;
   finalize x2; finalObserve. The first transition command substitutes the new
   `Invoke-AttendedTransition.private.ps1 -Attended`, bound to exact script hash,
   owner SID and interactive session. It checks source/state/tunnel before
   stopping only the exact observer process group and verifies actual process
   owners, including virtualenv redirector/child pairs.
7. If the launcher fails, the attended script preserves its primary error,
   restores only an absent exact-owned source03/state observer, and requires real
   mTLS observation/fresh snapshots. It records observerRecovered=true and
   **returns failure** for the primary launcher gate. The exact
   `attendedRecoveryCommand` with `-RecoverObserverOnly` is prepared for attended
   diagnosis; it performs no certificate rollback. Do not claim unattended proof
   from this fallback. Observe/finalize proceed only after explicit technical
   disposition of the failed gate and measured accepted state.
8. IdP file creation is a separate released operation using the new proposal and
   apply-script hashes above. Recheck the existing pinned service CA, live JWKS,
   candidate public policy freshness and original input hashes. It creates only
   the isolated r5 profile/public policy plus backups; there is no API/IdP service
   switch or token issuance in this packet. Canonical sv-api/password/service
   grants remain disabled; a profile file is not browser/token acceptance.
9. Production twice-daily registration, unattended certificate transition, MFA/
   browser acceptance and five-Node S01-BE/ST acceptance require their real gates.
   Only two identities/Nodes are present; three missing identities are not
   fabricated. Counts remain **2 done / 4 blocked / 42 planned / 0 ready**.

# Measured restoration and persistence limitation

At 16:10 KST all prior r5 listeners/processes were gone; observer stdout stopped
at 15:52:15.467 near the terminal replacement. Empty observer/serve/console stderr
and unavailable termination audit do not prove the cause. Nine log/PID artifacts
were preserved privately with public metadata in `lifecycle-before.json`.

Coordinator releases msg_b86842a732c6 and msg_3c3d7290f481 authorized only source03
service restoration. Claude/root accepted the exact one-shot WMI plan before use:

| Preserved executed artifact | SHA-256 |
| --- | --- |
| Restore-R5Source03.private.ps1 | `af53251b24ea455f2ec0f5ea2cb7d59d0a0e07d1fa79229326b8ed768ef2bf2c` |
| Launch-R5RecoveryContext.private.ps1 | `bb46402865847247cf9dca17c700273b8f7b2d93e0a55d4d19727875810b026a` |
| recovery-context-plan.private.json | `d1c0b05eb950338d48adf3cd7317cecfd132d2339544ae4ddc1453336d01567b` |

At 16:20:10 KST the controller ran **once**, exit 0 / WMI ReturnValue 0, with
CREATE_BREAKAWAY_FROM_JOB and hidden startup. This flag addresses the job
constraint described by Microsoft's [Win32_Process.Create](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/create-method-in-class-win32-process)
and [Win32_ProcessStartup](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-processstartup)
documentation; the flag alone is not a persistence measurement. No task,
credential, certificate, Node/workload change or policy change was involved.

The helper 33976 and its caller 29692 exited. At 16:25:14 HTTP 18082/3000 returned
200/200; three samples over two advancing intervals showed two online fresh
members, source live-postgresql-mtls, three valid public leaves, killSwitch=true,
userWorkloadSubmission=false, runs=0 and offers=0. State bytes were preserved.
`restoration-process-proof.json` records exact owner/parent/session and PIDs.

The attempted strict all-five-roles IsProcessInJob=false gate **exited 1**:
observer/serve redirectors and SSH were outside jobs; the console real Python and
Node web process were in jobs. This negative result is preserved and not PASS.
Coordinator msg_b5e649d90528 reports Claude's independent analysis that virtualenv
children and libuv internal jobs explain the mixed values; root retired that
literal criterion and adopted functional same-PID persistence after actual
worker_done/reopen. This author has measured parent exit, **not worker/terminal
exit**. Root owns that next bounded measurement; the services are left unchanged.

# Validation and provenance

`validation-results.json` records KST, exact exits and private output hashes.
`review-candidates/validate_followup.py` supplies reproducible command arrays.
At 16:39 KST on Windows, actual CPython 3.14.7: 27 guard tests passed, zero skips;
Python and PowerShell AST checks, poisoned-environment real CLI/wrapper status,
public `--window-only`, probe `--describe`, registration `-PlanOnly`, source/state
and preserved-input checks all exited 0. No S4U/renewal/identity/prep operation is
in those successful probes. `followup-guards.xml` contains the targeted cases.

The correct remote `origin/integration/all-agents-unified` was independently read
at **fd1530d9b46e6b90a708daa59b4394599684309a** after fetch. Initial 15:59 source
comparison had correctly measured the earlier landed train78 03e17c31; that
observation is historical. Eleven b5 executor/runtime/worker/launcher Git blobs
equal FD exactly (`source-equivalence.json`). The live source03 clone is retained
clean and unchanged, rather than being silently upgraded with this evidence.

`fd-ci-readback.json` binds every CI ID to exact FD source. At 16:39 the post-push
Backend 41792325651 and Core 41792325643 were still running; other completed
post-push lanes are listed with their actual conclusions. Signed S12
41792498330 was successful. Root reports all eight pre-landing lanes accepted;
this packet does not turn skipped entries or running post-landing lanes into
PASS. The separate backend pre-CI metadata 41787943473 records its actual jobs.

Diagnostic errors are separate from validation success: querying nonexistent
`origin/integration` returned Git 128 before the correct ref was found; a local
JSON read initially rejected a UTF-8 BOM and another rejected PowerShell's UTF-16
redirection (each exit 1), then explicit BOM-aware decoding succeeded. No live
mutation followed those failed diagnostics. The strict process-job gate exit 1
remains the operational negative finding described above.
