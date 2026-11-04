---
doc_id: "HISTORY-R5-REVIEWED-BOOTSTRAP-PLAN-20261104"
title: "r5 exact-source bootstrap plan before live mutation"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-04T13:35:02+09:00"
source_of_truth: "Git"
---

# r5 bootstrap plan and measured preconditions

Task SUPERVISION-20261104-CODEX, task_4a4eaf27c548 / ctx_78f45e976cf3.
Coordinator message **msg_5d55fb6c0ed7** selects the supported fresh isolated
namespace. This is a concrete pre-mutation plan for internal review and binding to
existing user approval; no new user permission is requested. No bootstrap, new DB,
certificate, Node, SSH key, volume, workload or scheduled task has been changed.
Owner Codex; reviewer Claude pending; coordinator owns execution dispatch.
Plan branch agent/codex/supervision-20261104-r5-plan, base/reviewed scheduler target
**b1e59f85e690ae61efe8748090815d2b53fd549d**, local checkout
`D:/Project/SaintVisionI-Invion/supervision-codex-20261104`.
Context versions and prior audit are recorded in the two preceding unique History
records; shared boards/registry/Obsidian are outside this task's edits.

## Exact scope and private bindings

- **Execution source:** landed, previously reviewed train 78
  **03e17c31cf535008d39534aaa80d3ae274bd75cc**. Bootstrap-related source files
  `tools/lan_pilot.py`, database prepare/verifier, worker prepare/finish,
  Dockerfile and desktop launcher have no diff from recorded accepted train 77
  **e86064239e219394e24831acc78ee01ef4a29bfd**. Do not run the unlanded scheduler
  correction as bootstrap source or fabricate a genesis-expired protocol.
- **New state:** `r5-03e17c31-f8923863`, below the existing protected pilot root.
  **New database:** `saintvision_lan_r5_f8923863`.
  **New least-privilege runtime role:** `inv_lan_runtime_r5_f8923863`.
  These exact names are fixed for this plan; an unexpected collision stops execution.
- **Ports:** Node TCP **18505** on both already authorized Linux hosts; CP download
  TCP **18105**; reuse only the verified remote loopback PostgreSQL transport
  **55448**, with an owned local loopback SSH forward. UI/overview remain local
  **3000/18082** after acceptance. No extra Node identity is invented.
- **Private exact bindings:** `.work/supervision-codex-audit/r5-private-plan.json`
  in this owned checkout holds known SSH user/host/key references, issuer/key/password
  file references, existing container/network, new credential directories and exact
  command argument arrays. It contains **no credential value, token or raw DSN** and
  is not committed or exported. Its final digest is supplied directly to coordinator.
  Redacted measured evidence is committed separately under
  `Evidence/r5-bootstrap-plan-20261104/`.

## Actual read-only measurements (KST 13:31-13:35)

- Existing key/strict known-host SSH succeeds on **both** preserved r4 hosts, exit 0.
  Docker APIs are **1.52 / 1.56**, meeting worker minimum 1.45. `ss -H -ltn`
  shows 18505 and 18105 unused on both. Local listener inventory shows none on
  18105/18082/3000/55448. Availability is a snapshot; repeat immediately before use.
- Exact encrypted issuing intermediate/key/password/chain pass repository validation
  again and match r4's pinned CA bytes. Existing revocation registry parses. Old r4
  leaves remain expired history and are not new authority. Both Node-local key
  matches were already directly proven without exporting either private key.
- PostgreSQL **16.10** selected by r4's actual published port is running, labeled
  with the expected pilot owner, uses one owned user-defined network (not internal)
  and publishes **only 127.0.0.1**. Pinned image is
  `postgres@sha256:ab8380566c3ea09690a9ecaa85a59d82bfc6eb86744151a2a54335866c83a3e9`.
  Read-only catalog query exits 0; new DB and role collision counts are **0/0**.
- Existing r4 runtime is LOGIN with **no superuser/bypass-RLS/create-DB/create-role/
  replication** privileges, SCRAM password, and **one expected inv_kernel membership**;
  unexpected membership count is **0**. Its DB is admin-owned; runtime is not DB owner.
  Password encryption and every host HBA method are SCRAM-SHA-256. A new role must
  pass the same verifier after creation and again after kernel grants.
- New remote credential directory is absent. The plan creates it separately and
  copies the existing admin password **only locally on its existing host**, with
  owner-only permissions, to satisfy the reviewed helper without rewriting the old
  password file or exporting a private key. New runtime credentials/passfiles belong
  only to r5. CP DSNs are passfile-backed and generated with forward-slash absolute
  passfile paths; they are validated before init and never printed.
- Both hosts report NTP synchronized. SSH midpoint estimates are **+0.487 s / +0.438 s**
  with RTT **0.366 s / 0.337 s**; these are bounded estimates, not independent high
  precision clock proofs. Repeat and require ADR clock bounds before issuing material.
- Four prior state trees (`r2`, `r2-7057dcd0`, `r3-4607ca85`, `r4-e8606423`) have
  private aggregate byte baselines recorded. Prior namespaces, containers, volumes,
  state, journals, identities and keys must remain preserved.

## Local preparation gate discovered during planning

The existing train-77 and train-78 worktrees are clean but their launcher-derived
common-repository Python executable is **missing**, and their own Vite dependency
entry points are **missing**. This reproduces the original launcher's dependency gate;
do not claim desktop readiness or insert a placeholder executable. The known working
Python 3.14.7 environment is elsewhere. Before any new DB/Node mutation, prepare the
reviewed Python dependencies at the exact common path the source launcher derives,
and `npm ci` against the exact reviewed package-lock in this owned source checkout.
Alternatively coordinator may supply a measured already-prepared exact-source
checkout under the correct common directory. Keep coordinator/other Agent checkouts
unchanged. Validate native paths and shortcut ownership with the reviewed input
helpers (`Register-DesktopShortcut.ps1` has no plan-only mode); do not
change the reviewed launcher or its checks merely to hide missing dependencies.

## Executable sequence after coordinator binds this plan

1. **Freeze inputs and preserve old state.** In this owned checkout switch to exact
   source 03e17c31 and require clean tracked inputs. Verify dependency gate above,
   private plan digest, CA/key/chain/revocations, known SSH host-key/key binding,
   both host clocks, free ports, exact DB owner/image/network, empty new namespace
   and all prior aggregate baselines. Never run from an archive inheriting a different
   checkout's HEAD. Every nonzero exit stops before the next command.
2. **Create only r5 DB credentials/namespace.** On the verified DB host, create a new
   private directory and copy the existing admin credential locally without overwriting
   any existing file. Invoke exact-source
   `deploy/lan/prepare-pilot-database.sh <pinned-image> <verified-container> 55448 <new-private-dir> <verified-network> saintvision_lan_r5_f8923863`.
   Invoke `verify-pilot-database.sh <verified-container> <verified-network> saintvision_lan_r5_f8923863 <new-private-dir>`.
   Validate missing/wrong credentials rejected, real admin/runtime accepted, no elevated
   flags, only the expected membership and SCRAM. The helper's collision refusal is
   mandatory; preserve a partially created r5 on failure rather than deleting it.
3. **Owned tunnel and CP init.** Return only new DB passfiles over existing protected
   SSH to the new CP credential directory; generate/validate new passfile DSNs locally.
   Open or reuse only the known host/key-bound loopback 55448 tunnel. Execute
   `tools/lan_pilot.py --state <new-state> init` with the two existing host addresses,
   Node 18505, download 18105, new DSN-file arguments and exact external CA references
   from private command arrays; then `bind-db-auth` with both new passfiles. New
   tenant, epoch, Node IDs, CP/signing keys and leaves are generated only inside r5.
4. **Build exact new-epoch image and bundle.** Archive only the reviewed source inputs,
   transfer to a fresh build directory on the existing authorized Docker host and
   build via digest-pinned `deploy/lan/Dockerfile.node.remote`. Tag it with **r5's new
   epoch**, export one image and its inspect record, verify independent hashes, and
   use `bundle --prebuilt-image ... --prebuilt-inspect ...`. Existing r4 archive tags
   bind the old epoch and cannot simply be relabeled as an r5 bundle. Preserve the
   old images/archives; local CP Docker API 1.41 is not used for the build.
5. **Enroll only two new Node-local identities.** Serve only new public material on
   18105. If the existing firewall does not permit it, add only a new r5-owned TCP
   18105 rule scoped to the two authorized host addresses, preserving other rules.
   Require the source-IP-bound bootstrap endpoint to reject another source. Transfer
   each matching public archive and its independent digest; require
   each new Node root/container/volume name absent before prepare. Run the reviewed
   `prepare-worker.sh`, capture only each public CSR, validate CSR/SAN/issuer/tenant/
   epoch/key match in `enroll`, return only the matching public leaf and verify its
   digest, then `finish-worker.sh`. Each private key stays at its own new Node root.
   No old Node is restarted, replaced, enrolled again or assigned a new key.
6. **Measure before desktop cutover.** Run exact-source `observe --once` and `status`,
   then repeat after a fresh heartbeat interval. Require exactly **two** online/fresh
   mTLS observations with advancing persisted snapshots, exact new identities/epoch,
   enabled monotonic channel version **1**, fresh leaves/chain, earliest CP/all-Node
   expiry and a computed two-day renewal window. Require new kill switch default
   **true**, **0 Runs / 0 resource offers**, workload submission **false**. No global
   control toggle, workload execution, storage folder registration or customer data.
7. **Cut over owned local surfaces only after acceptance.** Source
   `Start-LiveConsole.ps1` receives exact new state and validated known tunnel/key
   arguments. Require one loopback-only listener per 3000/18082/55448, fresh overview
   and actual new-state process ownership before replacing the owned shortcut.
   Preserve the DB tunnel across console transitions. The failed broader-CI harness
   does not substitute for this measured two-Node read-only acceptance.
8. **Record, then separately prevent expiry.** Record exact source, KST, command exits,
   counts, public validity times, private receipt baselines and old-state preservation.
   Install no renewal task until corrected #402 has exact-head review, required CI,
   integration and explicit coordinator execution dispatch. Do not merge unreviewed
   scheduler code into this source to accelerate the bootstrap. The original 48-task
   count stays 2 done / 4 blocked / 42 planned / 0 ready.

## Failure, rollback and non-claims

Before cutover, any failed gate leaves old r2/r3/r4 objects and the old shortcut alone;
preserve every new r5 artifact for exact diagnosis/replay and stop new bootstrap
processes only after verifying their state-bound ownership. After cutover, stop only
confirmed r5-owned observation/console/worker processes if required; preserve their
volumes, keys, DB, receipts and the shared owned DB tunnel. Never restore expired r4
material as live authority or automatically delete/roll back a namespace. Uncertain
effects require readback and reviewed recovery rather than duplicate execution.

This plan restores **two-Node development observation**. It does not create missing
three physical Nodes, fix CP co-location Docker API 1.41, repair the third worker's
SSH access, enable workloads, certify IdP/browser operation, perform object writes/
PITR, or close S01/operational acceptance. The coordinator-selected supported path
uses existing authority rather than requesting known inputs again.


Private plan final SHA-256: **2614a1b3b4b3201163d2f6e0ef0295747509d5b4ec0eb388e055f00c6a24c039**. This binds private argument arrays
and exact known references without publishing their values. Bootstrap source
equivalence check exited **0** against train 77 for all listed bootstrap paths.
No operational command from the plan has been executed.
