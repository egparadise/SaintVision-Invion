---
doc_id: "HISTORY-R5-REOPEN-C50115DCE654-CODEX"
title: "r5 reopen persistence and released runtime, identity, S4U outcomes"
version: "1.0.0"
status: "review_requested"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-04T17:29:00+09:00"
source_of_truth: "Git"
---

# Scope and provenance

Task task_c50115dce654, dispatch ctx_7ffe0c8c472c, new terminal
term_6a916231e43b4f5acc65d986dde2726a, owner Codex/reviewer Claude.
Branch `agent/codex/r5-persistence-c50115dce654`, base evidence
`65b85bc59e402125a264dc6cda475f8c764d255d`, start 16:50:30 KST.
This bounded read-only task follows actual prior worker_done acknowledgment
msg_22ee1c05cc1d and a fresh dispatched terminal. No service was relaunched.

Checked boards INDEX-PROGRESS-001 1.0.376 / WORKBOARD-CODEX-001 1.0.338;
GUIDE-001 1.1.0, ADR-INDEX-001 1.37.0, GOV-AGENT-001 1.1.3,
GOV-GIT-001 1.1.4, GOV-CONTINUOUS-001 1.1.0; previously read continuity,
delivery/reliability skills and original governance remain applicable.
No shared board, registry, Obsidian or coordinator checkout is edited.

# Actual persistence result

**PASS for this bounded worker_done/reopen functional criterion**, measured on
Windows/PowerShell with actual CPython 3.14.7. The evidence directory is
[r5-persistence-c50115dce654](../Evidence/r5-persistence-c50115dce654/manifest.json).
Public proof contains role aliases, creation times and booleans; raw overview,
actual member identities and exact private command vectors remain local.

At 16:50:30 and 16:52:45 KST, Get-CimInstance/GetOwnerSid confirmed all five old
PIDs, exact earlier command lines, parents, session1, and current expected owner:

| Role | Preserved PID | Parent | UTC creation (KST +9h) |
| --- | --- | --- | --- |
| SSH | 15408 | 33976 | 07:20:13.927 |
| serve redirector | 40748 | 33976 | 07:20:17.050 |
| observer redirector | 34380 | 33976 | 07:20:17.563 |
| console real Python | 54216 | 3756 | 07:20:18.178 |
| web Node | 25608 | 33976 | 07:20:18.674 |

Those creation times predate the previous worker_done and this fresh dispatch;
PID reuse is not inferred from PID presence alone. The prior helper33976 and
caller29692 remain absent. Runtime pairs are serve40748→52720,
observer34380→33812 and console3756→54216, with identical parent/child argv for
their Python virtualenv redirector pairs. Original console/web/SSH listeners are
exactly one IPv4 loopback listener each on18082/3000/55448 and their same PIDs.
The pilot serve listener18105 remains bound to its original LAN address on52720;
it is neither a wildcard listener nor falsely described as loopback.

`measure_persistence.py` executed exit0 at 16:52:07 KST, three GET samples eight
seconds apart, bounded three-second HTTP timeouts. Each sample returned
`/pilot/v1/overview` HTTP200 and web HTTP200, source live-postgresql-mtls, exact
two accepted members online/fresh, killSwitch=true, userWorkloadSubmission=false,
runs=0 and offers=0. **Both** Nodes' heartbeat and snapshot timestamps strictly
advanced in each of two intervals. Source03 HEAD/cleanliness, executable pins
and protected state bytes were rechecked and match accepted baselines.
No raw DSN, token, SSH address/key or actual member ID is published.

The strict earlier all-role IsProcessInJob=false gate remains failed exit1 and
retired; it is not rerun or promoted to PASS. This result measures actual
worker_done/reopen persistence using root's functional parent/runtime criterion,
and does not claim indefinite durability or unattended certificate renewal.
Prompt status msg_d9dd2fb41011 delivered the actual result to the coordinator.

# Review, CI and exact next commands

Coordinator msg_c0e710ee9ead reports Claude independently rehashed all17 inputs
and reran27 guards, accepting C2/C3/C4 source. C1 condition remains: attended
transition and RecoverObserverOnly must run through the reviewed WMI breakaway
mechanism or a self-proven job-free attended console. The old scheduled
transition still needs environment/lifetime fixes before certificate-task
registration; it is **not released**. This author does not fabricate acceptance
of a new context guard or unattended execution.

Independent `gh run view` exit0 proves Documentation Build **41795344577**,
`.github/workflows/docs.yml`, workflow_dispatch on exact packet evidence SHA
**65b85bc59e402125a264dc6cda475f8c764d255d**, completed success.
Run41794783892 is Portal Login Journey Harness, also success, and is **not** the
Docs gate or operational acceptance. Landed source FD/pre-eight PASS and pending
post-landing lanes are the coordinator's separate source gate; this report does
not convert them into terminal/Node/IdP acceptance.

Exact future vectors are prepared in the new private file
`.work/r5-persistence-c50115dce654/next-commands.private.json`, SHA-256
`e1c70765a19410f303e72f285cbd711c587cd8709c76b2217e129243fc60c7da`.
It references the unchanged accepted preparation file/hash, exact IdP apply,
exact S4U registration/demand-start, window-only probe, and first 14 certificate
gates. Only the future attended transition/recovery entry is wrapped with a
read-only actual-process IsProcessInJob query that fails closed before observer
stop if the console is job-owned, unknown, noninteractive or wrong owner/session.
The initial generic context guard is privately retained for review, SHA-256
`ed8a4c0ac741f471dd8259426490febcab125f1f5bf5f96559bb2361a752fe39`;
PowerShell AST parsed exit0, **not executed or independently accepted**.
The already-used WMI restoration controller is never replayed for a transition;
a new WMI transition plan would need exact independent review if that path is
chosen. All17 sealed input hashes and68 older packet files remain unchanged.

At 16:59 KST, coordinator **msg_c6fa3bda6ff3** independently corroborated the
same-PID functional persistence and explicitly released only exact runtime-prep
array c981dc09, isolated IdP proposal585413, and demand-only S4U probe c3f655,
after dedicated Docs41795344577 and Claude C2-C4 source acceptance. This extends
this task with those bounded operations; it does not release certificate tasks,
cycle/transition or RecoverObserverOnly. The following original handoff boundary
describes the state before that explicit release; actual execution results follow.

The original next action belonged to the coordinator: accept measured persistence,
review the guarded context, and explicitly release only the selected isolated
runtime-prep/IdP/S4U phase after the exact Docs/source gates. Then measure actual
Python3.12.3 worker preflight and S4U currentStatus/preflight x2. First certificate
transition remains attended and window-gated; scheduled certificate registration
remains blocked by its environment/lifetime condition. At that initial handoff,
prep/IdP/task operations had not occurred; the later explicitly released actual
outcomes follow. Counts remain **2 done / 4 blocked / 42 planned / 0 ready**.

# Actual released stages — success and blocked lane kept separate

Technical release **msg_c6fa3bda6ff3** authorizes the following exact mutations,
not a generic certificate/identity service release. All17 hashes were verified
before execution; accepted sealed files retain their historical plan flags.
Actual results are in separate dated Evidence.

At **17:00:18–17:00:23 KST**, the six exact commands from preparation array
`c981dc09dc8eaf5ff7a1596771cb679cad43024cc913abefa119998ceba4c7e6`
ran once in reviewed order, every native exit **0**. The private runner passed
each pinned stdin file as bytes and sanitized inherited Python paths, retaining
raw logs and hashes per command. New isolated staging/offline runtime directories
were created, public helper/archive inputs transferred, and actual hash-pinned
Bash installation completed. **Actual worker** runtime-preflight succeeded on
Node1 **Python3.14.4** and Node2 **Python3.12.3**: compatible=true,
cryptography50.0.1, utcCertificateAPI=true. This closes the specific actual-3.12
runtime-prep prerequisite; it does not assert five Nodes, rotation, workload or
unattended acceptance. No existing runtime, Node identity, key, certificate or
workload file was a mutation target. Status msg_fdff74e9340b reported the result.

At **17:01:02 KST**, exact new C2 apply script with IdP plan
`585413eeee73cddd483ff6552f3ce778213a31c7870b7294b97be659689717f0`
exited **0**, creating only reviewed new r5 identity files and unique backups.
Scoped ancestry/targets, five original baselines, candidate freshness/tenant,
existing CA and script pins passed before writes. Both target hashes match their
candidates; all **five originals and five backups** match, existing CA unchanged.
Offline construction using the **actual new profile** succeeded at **17:02:34**;
wrong issuer and expired public policy were rejected, verifier exit **0**.
No existing profile, service, global trust, DNS, account, grant or IdP configuration
changed. No token was minted; fresh-token/browser/MFA acceptance is unmeasured.

At **17:02:38 KST**, exact demand-only S4U probe plan
`c3f6553cc48d48cc853196333ffff2b2bfc4a05b6f93ebd2f9be750d8b927415`
was submitted to its reviewed registrar **once**. It failed **exit1** at
Register-ScheduledTask line24: **Access is denied**, PermissionDenied,
CimException, **HRESULT0x80070005**. This actual OS scheduling boundary is not
missing user approval and not PASS. Raw stderr/hash remain private; sanitized
failure is `s4u-failure.json`. At **17:03:33**, exact-name query returned
CmdletizationQuery_NotFound_TaskName: no task, intent or receipt exists.
**No demand-start, retry, elevation, credential or fallback occurred**. No actual
S4U context or its three child gates were measured; interactive preflight is not
substituted for S4U proof. Status msg_9cce44c51202 reported both lane outcomes.
Readback records current token Administrator=false; the precise denial mechanism
beyond the observed API failure is not guessed.

At **17:05:45 KST**, post-state exit **0**: HTTP200/200, actual two fresh online
members, killSwitch=true/workloadSubmission=false, runs/offers0, protected state
unchanged, same five PIDs/owners, no relaunch/service switch. Window-only exit0
confirms three unexpired public leaves and unchanged public leaf-set hash.
Earliest expiry **Nov10 14:15:35 KST**, window **Nov8 14:15:35 KST**, currently
outside the window. No certificate cycle, transition or RecoverObserverOnly ran;
no certificate task was registered.

All **17 sealed inputs and 68 older packet files** still match after operations.
New execution state does not overwrite their historical non-executed-plan
descriptions. Privacy checks passed; protected identities/addresses/connection
material and raw logs remain private.

# Remaining exact action and new context artifact

The current separate private phase/status matrix is
`.work/r5-persistence-c50115dce654/next-commands-after-prep.private.json`, SHA-256
**0978961dfada453f3a6f6d0c745c2e661f1a6dc6f09cd5f7a9c5a951e463769c**.
It preserves pre-release e1c70765 and all sealed inputs; prep/IdP are complete,
S4U denied1. It forbids replaying completed mutations or retrying registration
without technical disposition and retains exact window/first-cycle/recovery
vectors. Proposed attended context guard remains
**ed8a4c0ac741f471dd8259426490febcab125f1f5bf5f96559bb2361a752fe39**,
AST exit0, unexecuted and independent acceptance pending. It checks actual current
process job membership, attended owner/session and binding/script hashes **before
observer stop**; job-owned/unknown consoles fail closed. A new alternative WMI
plan needs exact review; the used restoration controller is not replayed.
Scheduled transition environment/lifetime fixes and actual S4U acceptance still
precede certificate-task registration, which remains unreleased.

Coordinator next reviews the guarded context and chooses a permitted OS scheduling
context/disposition for the observed denial; no missing-approval question is sent
to the user. S4U remains blocked and task outcome exposes its nonzero result.
Runtime/isolated profile success does not change **2 done / 4 blocked / 42 planned
/ 0 ready**.

# New WMI one-shot packet and actual harmless context proof

Coordinator **msg_d72c52706139** extended this task to concrete fresh WMI cycle
context and proposed-only scheduled-transition source. Only harmless ContextOnly
was released; **no Cycle, Transition, ObserverRecovery or ScheduledTransition
operation has run**. Root reports landed FD post-eight canonical CI now PASS;
that source outcome remains separate from this packet and OS/operational gates.

The new WMI packet supersedes direct-console guard ed8a4c0 and phase matrix097896
for future cycle invocation; both earlier private versions remain preserved.
Current exact input table is `wmi-cycle-manifest.json` in this unique Evidence.
Its protected executable vectors are in
`.work/r5-persistence-c50115dce654/wmi-cycle-commands.private.json`, SHA-256
**ead591fb262d69cbbf1c3edcd2992737f0de91b7704ae9b5f9f4184cbf7d6cfc**.

| Current private input | SHA-256 |
| --- | --- |
| WMI controller | `dd82d4c782ee2288c336f46441388f86af6c3ab765acd5f14e56a012d6f63139` |
| WMI entry | `fdc1d7da623b6e1196dd7a142d3efb053a1e51a59e13e2bf1c9bfafa66f33157` |
| Context guards | `f0ac7eeff3a05dc29c9c486db5e77223d21db7c92f100125d00179d9f621b468` |
| Exact-owned transition core | `b0963259bc7791f9b226bc07dcef110bb33c70129eb0584c527c26ab3dbba4fa` |
| Transition/context plan | `ed37d5b8270cf7bf46af6749ef5b691a1afdd596d551a7f220ee06d8726bda82` |
| Cycle context plan | `3380c1e34ed1e0d6bd3765d1769a6ba483f90f30f1009d3c9c5aa7f38b6c535e` |
| Attended cycle config | `2a907e4beaf7d551068e478384711f055af494bc0731368a9cff18373c9d888c` |
| Scheduled config, proposed only | `9b96bb4adb4b813d33f9e7ee12ebc74a6bb21a7ce538ae7f20c814f0c4134e23` |

Controller/entry bind exact plan/file hashes, owner and unique operation/run ID.
Atomic same-directory receipts and exclusive intent refuse replay/overwrite;
all failed intent/source versions are retained. Explicit local
Win32_Process.Create uses CREATE_BREAKAWAY_FROM_JOB, ShowWindow0 and native
**WinstationDesktop='Winsta0\Default'** in a fresh `wmi-runtime` namespace.
Entry measures actual owner/session/UserInteractive/IsProcessInJob plus actual
window-station/desktop names before operation dispatch. ContextOnly returns before
any pilot, network, observer or certificate operation; only local receipts/pins
and context metadata are involved.

At **17:24:15**, the first ContextOnly controller **failed exit1**, HRESULT
**0x80041002**, with an unsupported startup property `Desktop`. Native
Get-CimClass Win32_ProcessStartup proved the correct field is WinstationDesktop.
The wrong controller was corrected in this separate private source; the initial
one-shot intent, logs, manifest, and **all nine original input versions** were
preserved/reconstructed and verified against their exact recorded hashes.
No old restoration controller was replayed and no certificate operation occurred.
Fourteen earlier tests had passed; a new **actual native-class schema** test
reproduces/prevents that property mismatch. It is not hidden by passing tests.

At **17:26:24**, corrected **fresh** ContextOnly run
`20261104T082522Z-c50115dce654` exited **0**, actual helper45540 reported:
same expected owner, Session1, UserInteractive=true, successful job query with
**inJob=false**, actual **WinSta0 / Default**. The helper subsequently exited;
same five existing service PIDs remain and no service was relaunched. This is
actual harmless WMI context proof, **not S4U acceptance**. Exact receipt is in
`wmi-contextonly-result.json`. Status msg_064bd08195fd sent hashes/result to root.

Fifteen targeted WMI/context/receipt/config/native-schema tests passed, zero skips,
JUnit `wmi-guards.xml`, Windows CPython3.14.7. Tests exercise rejected job/owner/
session/desktop contexts and no-overwrite publication on temporary fixtures;
they never run a certificate cycle. Current manual config `--window-only` exited0
on the normal clock: valid leaves, **inWindow=false**. Cycle mode independently
checks that public window and refuses outside-window/expired material before
invoking the canonical mutating executor; no force flag or clock bypass exists.

The manual config preserves **13 non-transition commands byte-for-byte and all
14 gate IDs**, exact Node set, 48-hour window, freshness and canonical source.
Only transition is routed through a separate WMI child, avoiding the canonical
Python virtualenv's internal job inheritance. Status/log outputs are isolated and
notifications disabled for this attended first cycle. Canonical executor retains
its kernel lock, durable mutation latch before prepare, non-retry on uncertain
attempt, per-gate failure records, LAN CAS/idempotency/overlap behavior and final
fresh-changed-every-leaf/same-member-set postconditions. No latch reset/cleanup is
in the packet. Future outside-window refusal is not a successful renewal.

Transition core fixes the known old51b conditions as **source only**: clears and
restores Python environment, binds source/runtime, accepts exact virtualenv
redirector/child group, checks owner and PID creation/argv immediately before stop,
requires job-free entry, verifies real observations, and keeps launcher failure
nonzero even if exact-owned fallback restores observation. ScheduledTransition
uses the same breakaway/source/environment fix without falsely requiring an
interactive S4U caller. Its actual headless transport/session behavior remains
untested, and scheduled-config/latch plan-binding handoff needs review after a
real first cycle; **no certificate task registration is released**.

The staged whitespace gate earlier exited **2** on a trailing blank in the
superseded direct-console review artifact. Its exact ed8a4c0 private source is
retained; that obsolete public artifact is replaced by the new WMI packet.
New WMI source/guard hashes require independent Claude review and root's explicit
technical release before any cycle, transition or observer recovery. Original
17 sealed inputs, 68 prior packet files, state and public leaves remain unchanged.

At 17:09:36 a separate **read-only** current-caller IsProcessInJob query exited0:
query succeeded, inJob=true, Session1, UserInteractive=true, Administrator=false.
The proposed guard would reject this caller. No observer-stop/transition call was
made; full guarded transition remains unexecuted. Review/status
msg_c7b108f1264e delivered the exact new matrix/guard hashes to the coordinator.
Executor and offline-verifier source is clean pinned **b5b8ca68398517f6227a81caac02654a848c8b1d**,
pilot runtime source remains **03e17c31cf535008d39534aaa80d3ae274bd75cc**, and
landed integration FD is a separate code-source fact. This new evidence commit
does not replace any of those code/runtime SHAs.

Before the WMI extension, local checks: `python tools/check_docs.py` exit0 (1174 versioned documents),
`python tools/check_ontology.py` exit0, `git diff --check` exit0. Isolated
`tools/sync_obsidian.py --check --vault .work/r5-persistence-c50115dce654/sync-check-vault
--state .work/r5-persistence-c50115dce654/sync-check-state.json` exit0: 2159
prospective exports, zero conflicts, **no writes**. This is not shared sync.
Source/input/privacy checks exit0; raw protected outputs remain private. Evidence
commit/push SHA and any resulting branch CI are reported in the coordinator's
worker_done handoff, separately from all runtime/code source SHAs. The S4U
registration exit1 is an explicit blocked lane and overall incomplete operational
acceptance, regardless of successful local documentation gates.

After the corrected WMI ContextOnly proof and 15 guard cases, final
`check_docs.py` and staged `git diff --cached --check` exited0. Final isolated
sync check exited0: **2172 prospective exports, zero conflicts, no writes**.
The earlier whitespace exit2 and first ContextOnly exit1 are preserved above;
neither is reported as PASS. Independent review of the new nine-input packet and
root's explicit cycle/transition release remain outstanding at handoff.
