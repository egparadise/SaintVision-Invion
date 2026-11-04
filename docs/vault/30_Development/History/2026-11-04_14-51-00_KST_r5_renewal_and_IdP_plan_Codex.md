---
doc_id: "HISTORY-R5-RENEWAL-IDP-PLAN-20261104-CODEX"
title: "Actual r5 renewal registration preparation and read-only IdP repair plan"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-04T15:39:00+09:00"
source_of_truth: "Git"
---

# Task preparation

Orca task **task_9c44acb935e9**, dispatch **ctx_b9e243ab6b54**;
owner **Codex**, independent reviewer **Claude**, technical release **coordinator**.
Branch **agent/codex/r5-renewal-idp-plan-20261104**, clean tracked base
**2b49312cc15f364c66b2599541a5b8214f55b286**, KST 2026-11-04 14:47 start.
Coordinator messages **msg_5c0f1fc21594** and **msg_bf546920cf38** authorize plan
preparation and read-only IdP inspection; no task registration, certificate/Node
mutation, global trust/DNS/hosts change, credential/account change or service write.

Required policy and plans were read in the preceding supervision and rechecked:
GUIDE-001 1.1.0; ADR-INDEX-001 1.37.0; GOV-AGENT-001 1.1.3;
GOV-GIT-001 1.1.4; GOV-CONTINUOUS-001 1.1.0; GOV-CONTINUITY-001 1.0.0;
agent-delivery 1.1.0 and core-reliability 1.0.0. This branch's progress board
1.0.376 and Codex board 1.0.338 still describe historical Card304/r4; current r5
execution is in prior evidence commit 2b49312c. Shared Obsidian/task-registry
snapshots are consulted but remain unchanged by this explicitly scoped task.

The r5 operational source is **03e17c31cf535008d39534aaa80d3ae274bd75cc**;
the scheduler review candidate is separately **b5b8ca68398517f6227a81caac02654a848c8b1d**.
No candidate source is represented as final landed/CI accepted. Root's independent
live corroboration digest is **ef947ab65469960466fcb10a1148579275e4402079ce48647d9e21eb2297b8dd**;
remote CSR/enrollment remains attributed to the prior worker execution evidence.

Next: bind the actual r5 members, known issuer/SSH authority, executable/runtime
hashes, explicit gate arrays and current-user Desktop/task context into a private
candidate configuration, validate only read-only/plan-only paths, then inspect
the actual IdP bundle/config and give exact scoped repair/backup commands before
any live write. Preserve original **2 done / 4 blocked / 42 planned / 0 ready**.

## Concrete renewal candidate, not registered

Private workspace: `D:/Project/SaintVisionI-Invion/supervision-codex-20261104/.work/r5-renewal-idp-plan-20261104`.
The exact real configuration is `renewal-config.private.json`, SHA-256
**4fb067d06a0796dab2d533d35134d9181abb14a16bd07e613d5da59686d6964e**.
Bindings are `bindings.private.json`, SHA-256
**a67edb5148d20d704b11f5d7d9dd6a2c25d96d3fe0c2fab7b9c40640468ea956**.
These files remain outside Git: real Node IDs, SSH identities, known host keys and
private file references are reviewable locally without publishing them. There is
no credential value, raw DSN or private key in the configuration.

The candidate binds the two **actual r5** members/tenant/epoch, valid preserved
issuer/key/password-file/chain/revocation references and previously trusted SSH
authority. A frozen copy of existing known_hosts is pinned; host-key updates are
disabled and neither global known_hosts nor SSH keys are changed. Six executables
(Python, system SSH/SCP, Windows PowerShell, Node and Git), critical Python runtime
files and **99 regular input files per gate** are hash checked. CP runtime is the
real previously prepared **Windows Python 3.14.7** virtualenv; no fake interpreter
or another checkout's missing dependency path substitutes for it.

The **14** gates are currentStatus, two runtimePreflights, prepare, two installs,
two stages, shared commit, exact-owned CP observer transition, observe, two
finalizations and finalObserve. Source03 CLI, source-b5 scheduler and candidate
wrapper code are distinct inputs. New private wrapper/transition scripts are
**review candidates**, not already independently reviewed code. Their exact bytes
are archived in this unique Evidence directory with digests. Public redacted
command matrix is marked **not executable**; the private arrays are exact. Only
the executor's validated timestamp/UUID `runId` expands at runtime. No operator
TODO value exists in any executed command.

Prepare uses the two existing public CSR/key bindings, **48-hour** safety window,
**14400-second** bounded overlap and **518400-second** maximum new leaves. Node
keys never leave their existing roots. Public bundle/receipt transfers use only
the two existing SSH identities with independently checked file hashes. Install
receipts are flushed/fsynced locally; stage/commit continue to use reviewed
signatures and channel CAS. The transition stops only the exact source03/r5-owned
continuous observer and runs the existing reviewed hidden launcher without
OpenBrowser or foreign-listener replacement. Old states/volumes/keys are not targets.

Before registration, six exact commands in `preparation-commands.private.json`
create only two **new r5 runtime/transfer directories**, transfer the digest-pinned
offline runtime and reviewed helper closure, and install/preflight it without pip,
sudo, network fetching on Nodes or a system package change. This preparation was
**not executed**. Node Python executables/ABIs were measured read-only: **3.14.4 /
cpython-314-x86_64-linux-gnu** and **3.12.3 / cpython-312-x86_64-linux-gnu**. Both
new runtime/transfer targets were absent. CP bundle build exited **0**, four pinned
wheels and two reviewed worker modules, **5317028 bytes**, SHA-256
**5e47591d9ac6d2d1e17c62bec33c7d33a7ab2f01c07cc0522424fe2b51e6f579**.

Read-only/plan-only validation at KST 15:03-15:24:

- Exact b5 `scheduled_leaf_renewal.py --config <actual-private-config>
  --expected-config-sha256 <actual-digest> --window-only`: **exit 0**, two Nodes,
  unexpired/outside window. No executor attempt, guard, latch or operational
  receipt was created in r5 by this observation.
- Exact b5 registrar `-ConfigPath <actual-config> -PythonPath <real-runtime>
  -PlanOnly`: **exit 0**. Task name **SaintVision-Leaf-Renewal-b08b0726c9aaff4a**;
  exact current-user SID owner, limited S4U, noninteractive, **00:15 and 12:15**,
  IgnoreNew, four-hour limit; source settings include StartWhenAvailable.
- Desktop status target is **C:/Users/inviz/Desktop/SaintVision-r5-leaf-renewal-status.json**;
  append-only log is under this private plan workspace, never shared Obsidian.
  No status file or scheduled task was installed.
- Actual currentStatus gate **exit 0**, two real r5 rows. Both new runtime gates
  **exit 2**, **BLOCKED_NOT_PREPARED**. These are explicit blocked lanes, not PASS;
  they performed only read-only checks and no remote directory/runtime/Node write.
- Both candidate PowerShell scripts parsed with **0 syntax errors**, not executed.
  Private plan guard suite on Windows Python 3.14.7: **15 passed / 0 failed /
  0 errors / 0 skipped**, pytest **exit 0**. Descriptions execute no child, Linux
  paths remain POSIX and invalid IDs, traversal and actual-member drift are rejected.

CP earliest expiry is still **2026-11-10 14:15:35 KST**; the 48-hour window starts
**2026-11-08 14:15:35 KST**. With the current daily trigger times, the first eligible
trigger for this generation would be **November 9 00:15 KST**. This is a schedule
calculation, not a successful future run. Review/CI/source/run-context preparation
must complete before the window; retain a separately reviewed valid-leaf manual
batch as the fallback before actual expiry if unattended acceptance is not achieved.

## Run-context limit is technical, not missing user approval

The current observer/tunnel/console/web were launched in **interactive Session 1**;
3000/18082/55448 listeners are still single loopback binds in Session 1. The
existing SSH key loads without an agent/password, ssh-agent is stopped, and the
SSH key, encrypted issuer-key file, password file and Python executable have no
NTFS EFS or reparse-point attribute. None of this proves batch-logon access.

Microsoft documents S4U's noninteractive desktop and says there is **"no access
to either the network or to encrypted files"**. This is a documented constraint,
not proof that this deployment's Linux SSH transport works under S4U. [Microsoft TASK_LOGON_TYPE](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type).
No network exemption is inferred from a plaintext SSH key or a live interactive
tunnel. No S4U task, logged-off session, batch right, transport restart or notification
delivery has been measured here. `msg.exe` is best effort; the Desktop receipt is
authoritative and a logged-off user is not promised a visible alert.

The current-status gate deliberately requires the existing owned DB transport;
it does not silently adopt another listener or start a new service. If logoff loses
that transport, read-only preflight fails and N1 permits another trigger but does
not create a renewal result. The outside-window executor path skips these network
gates, so an outside-window task no-op would **not** prove unattended readiness.
Exact read-only context-probe arrays are in
`run-context-readonly-probe-commands.private.json` (digest in packet-bindings).
After technical release, run them under the intended actual Task Scheduler context
and verify SSH, local files, DB transport, runtime preflights and durable Desktop
receipt while disconnected/logged off. If that context cannot satisfy the checks,
coordinator must choose and independently validate a supported network-capable
context/transport arrangement; do not claim the hardcoded S4U candidate is accepted.
No new credential, account, global policy or task is created by this plan.

## IdP audit: two different expired public key bundles

KST 15:05-15:08 read-only audit found:

- The legacy **D:/Project/SaintVisionI-Invion/.work/intranet/api.json** points to
  **.work/dev/jwks.json** and still carries development issuer/audience/client
  settings. That configured development bundle expired **2026-10-05 08:08:30 KST**,
  contains public keys only, and its signing keys differ from the live IdP. Actual
  `AccessTokens` construction against this profile rejects with **ValueError**.
- The separate **.work/intranet/oidc-trust-bundle.json** is an **offline OAuth
  RS256 signing-key policy**, not a TLS CA bundle or Node certificate. Its issuer
  is canonical and its public signing keys still match current live JWKS, but its
  policy expiry was **2026-10-07 00:02:27 KST**. Its expiration must not be bypassed.
- Existing **.work/intranet/smoke/api.json** already has canonical issuer,
  `sv-api` audience and `[sv-portal]` client. Its tenant differs from both the
  legacy profile and actual r5. Copying that tenant into r5 is not a valid repair.
- Current GET discovery and JWKS through existing trusted Web-PKI chain, correct
  SNI/hostname and known inventory address returned **HTTP 200 / 200** with no
  global DNS/hosts edit or disabled verification. Issuer is
  **https://idp.sv.lan/realms/saintvision** and JWKS is same-origin. Live TLS leaf
  matches existing operator-held service material. Existing CA SHA-256 is
  **92455f1b778130334da43b0eee977357b5ae498eb1005bc29ecc6c3afb7192ba**;
  fresh JWKS SHA-256 **878bd3256d65619d63bc8b43c0a89236dae3a74e92818919bdeb317dd52b4c18**.
  One RS256 signing key is selected; one non-signing key is excluded by the source
  builder. No private component was present or published.
- A bounded SSH/Docker query of the exact owner-labelled, pinned PostgreSQL16.10
  IdP database used **BEGIN READ ONLY**, confirmed read-only mode and rolled back.
  Both clients exist/enabled. sv-api has login/service/password grants off;
  sv-portal is public, standard flow on, PKCE **S256**, password/service grants off.
  No token/admin session was requested and no realm/account/configuration changed.
  Fresh token claims, MFA/step-up, browser and DNS acceptance remain unmeasured.

## Concrete isolated IdP local repair proposal, not applied

Private exact plan: **idp-local-repair-plan.private.json**, SHA-256
**228403ffd4ec9c145ffe4492b1309ab7269fc66c92ce2b6307d619ec462dca94**.
`Apply-IdPLocalProposal.private.ps1` is digest-pinned by that plan and archived for
review. It is **not executed**. The proposed scope creates only these new files:

- **D:/Project/SaintVisionI-Invion/.work/intranet/r5-f8923863/identity/api.json**
- **D:/Project/SaintVisionI-Invion/.work/intranet/r5-f8923863/identity/oidc-trust-bundle.json**

Derive the new profile from the existing canonical smoke profile, bind its tenant
to **the already registered actual r5 tenant**, retain canonical issuer/audience/
client and point JWKS to its own new r5 public bundle. Existing legacy/dev/smoke
profiles and their tenants remain unchanged. This is an **identity profile** only;
it supplies no missing Node/storage/live API admission evidence and switches no
running consumer. The profile's operational DB/consumer binding is a separate
explicit deployment gate, not implied by successful offline verifier loading.

Use the already fetched, TLS-authenticated current JWKS with the exact reviewed
`make_oidc_trust_bundle.py --jwks-file ... --issuer <canonical> --ttl-seconds 604800`;
do not merely extend the old bundle's timestamp. Builder exited **0** in the private
workspace. Offline candidate verifier construction succeeds; wrong issuer and
expired policy are both refused. No fresh token verification is claimed. Current
candidate expiry is **2026-11-11 15:11:35 KST**, bundle SHA-256
**f50a221d410aca0804e235d9c2256b9c3d541121d346b4b530fb2f6b8b55f530**,
profile SHA-256 **3a3ab0717feaf1a781d26fc635d574c015dd615ee9adf9973bb4e0f56d4225ba**.
Re-fetch/rebuild and rebind candidate hashes if execution is delayed or key material
changes. Weekly bundle freshness and December service TLS expiry are separate from
the r5 six-day Node/CP leaf renewal.

Before the proposed writes, verify pinned plan/script/candidate/CA hashes, all five
old file baselines, regular/no-reparse files and scoped parents, future policy
expiry and actual r5 tenant. Refuse any existing new target or backup directory.
Backup destination is exactly
**D:/Project/SaintVisionI-Invion/.work/intranet/backups/2026-11-04-r5-identity-plan-9c44acb935e9**;
the private plan names each source and distinct backup file and requires matching
hash readback. Create only the new identity directory/files, refuse overwrite and
read back both hashes. On failure preserve partial outputs for review; no deletion
or restoration of expired authority. No IdP restart, API start/switch, OS trust,
hosts/DNS, secret, account, DB row or existing identity file change is included.

## Validation failures and source-specific CI

- A proposed isolated `python -I -B tools/lan_pilot.py ... status` probe exited **1**
  (lan_pki ModuleNotFoundError): that reviewed CLI expects its normal tools script
  path. The plan uses its already reviewed **-B** invocation instead; supervisor/
  private gates and Node standalone runtime retain **-I -B** where supported.
- The first read-only IdP client collector exited **1** parsing a multiline
  json_agg result after a successful read-only query. jsonb_agg fixed only the
  collector shape; the corrected read-only probe exited **0**. No DB repair ran.
- Initial private guard suite exited **1**, **13 passed / 1 failed**: generic remote
  token grammar permitted a `..` component. The candidate explicitly rejects it;
  final suite exited **0**, **15 passed**, with before/after JUnit retained.
- PR402 b5 exact source CI was read at KST 15:17. Actual PR merge checkout
  **45d6ab737f2baede2664b096dcc0e0846ff82c13**. Backend **41779908473**, Python
  **3.12.15 / 3.14.9**, each **42 failed / 8361 passed / 75 skipped / 2 deselected /
  9 errors**, failure. Core **41779908364**, Python **3.12.15**, **42 failed /
  8719 passed / 46 skipped / 2 deselected / 9 errors**, failure. Its actual JUnit
  proves **all 36 scheduler cases passed / 0 skipped**, including Linux symlink,
  crash/latch and both all-member cases. That subset does not make Core PASS.
  Source and full/filtered evidence are recorded in b5-ci-readback.json.

Fetched integration still resolves to already-landed train78 **03e17c31**. Final
combined CI and landing remain coordinator-owned. Before real registration, freeze
the final accepted source, regenerate/review exact configuration/source/input
digests if changed, execute the scoped runtime preparations, measure the actual
run context and obtain the coordinator's requested **technical** release. Existing
user approval is not missing or being requested again. The candidate plan and
unattended readiness are not accepted merely because PlanOnly/local tests pass.

Next owner/action: **coordinator/Claude** review the pinned private configuration,
new wrapper/transition candidates and isolated IdP proposal; dispatch a bounded
post-gate preparation/context check and separately scoped local IdP write only
after that review. Retain both live source03 runtime and this private plan workspace
across task completion. Five-Node assignments/user hardware input remain pending;
no Nodes were invented and all original task counts stay unchanged. Only this
unique History/Evidence set is edited; shared boards/registry/Obsidian are untouched.

Final packet check at KST **15:37-15:38** revalidated the exact configuration and
all 99 local input hashes, window-only/PlanOnly exits **0**, owned-tunnel/current
status exit **0**, and both still-unprepared remote runtime checks **exit 2**.
The status preflight now explicitly checks **every** 55448 listener with the
reviewed system-SSH/forward/target ownership helper before DB authentication; an
added negative witness proves refusal never reaches the DB command. The private
binding also pins the actual r5 private-state bytes without publishing them or
making the generic scheduler read private state. The final 15-case suite includes
that witness; batch rotation changes leaf/journal files, not this bound state file.

Final document gates: check_docs **exit 0**, **1171** versioned documents;
check_ontology **exit 0**; diff check **exit 0**. Isolated Obsidian check **exit 0**,
**2114 managed / 2114 pending / 0 conflicts / no writes**. Final public packet scan
found **0** private non-loopback addresses and **0** credential-pattern matches;
all five original IdP file hashes still match, and both new target/backup directories
remain absent. Evidence-local attributes preserve byte identity of the four pinned
review-candidate source files; staged Git-blob hashes are checked before push.
