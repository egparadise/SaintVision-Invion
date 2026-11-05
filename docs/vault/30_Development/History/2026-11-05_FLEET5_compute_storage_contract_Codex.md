---
doc_id: "HISTORY-FLEET5-COMPUTE-STORAGE-CONTRACT-20261105-CODEX"
title: "FLEET5 same-Node compute and storage contract proposal"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude via root; pending"
updated: "2026-11-05T22:28:36+09:00"
source_of_truth: "Git"
---

# FLEET5 compute/storage source proof and decision request

This is the historical first source-grounded proposal, not an accepted ADR, implementation, integrated
candidate, active storage installation, or five-PC acceptance. Production source
remains the preliminary combined base
`0bcf9670d098fac87667fc9e2448b332db46e691`.

## Assignment and reading record

- Card: `FLEET5-COMPUTE-STORAGE-CONTRACT-20261105`; Orca task
  `task_a8fd2969f0b3`, dispatch `ctx_6f0f8253b8a7`.
- Owner Codex; independent reviewer Claude through root, genuinely pending.
- Branch `agent/codex/fleet5-compute-storage-contract-20261105`;
  branch creation recorded by Git reflog at **2026-11-05 19:12:03 KST**.
- Scope before root's decision: source inspection, uniquely scoped fixture proof,
  source inventory, this History and Evidence only. No production guard change.
- Read root's latest vault, not old base boards: `INDEX-PROGRESS-001` v1.0.401
  and `WORKBOARD-CODEX-001` v1.0.362, both updated 19:03:32 KST, under
  `D:/Project/SaintVisionI-Invion/fleet-five-orchestration-20261105`.
- Read AGENTS, delivery skill v1.1.0, core-reliability skill v1.0.0;
  `GUIDE-001` v1.1.0, `ADR-INDEX-001` v1.37.0, `ADR-100` v1.0.0,
  `GOV-AGENT-001` v1.1.3, `GOV-GIT-001` v1.1.4,
  `GOV-CONTINUOUS-001` v1.1.0, `GOV-CONTINUITY-001` v1.0.0,
  `INDEX-VIRTUAL-COMPUTER-001` and `ROADMAP-VIRTUAL-COMPUTER-001` v1.0.0,
  `PLAN-STORAGE-001` v1.0.0, `CONTRACT-STORAGE-SAMPLE-001` v1.9.0,
  `RUNBOOK-STORAGE-POLICY-001` v1.4.0, and registry v1.0.1.
- Exact document paths, hashes and source anchors are in
  `docs/vault/30_Development/Evidence/fleet5-compute-storage-contract-20261105-codex/source-inventory.json`.
  Shared boards, registry, ADRs, source originals and Obsidian are unchanged.

## What the source establishes

| Contract | Existing supported behavior | Missing semantics / consequence |
|---|---|---|
| Workspace upgrade | `deploy/lan/worker_workspace.py:70` explicitly rejects storage-policy flags and every mount except owned `/state` and the exact default Docker socket | A legitimate storage Node cannot become a workspace Node through this installer; do not delete the R4 guard |
| Storage install | `deploy/lan/worker_storage.py:178` requires exactly two mounts, `/state` and read-only `/contribution`; requires `BindOptions.NonRecursive=true`, rprivate and exact source/image | Adding a third default socket fails its validator, install and receipt paths; copying a bind in workspace alone cannot close the gap |
| Storage replacement | `deploy/lan/worker_replacement.py:103` accepts only a clean stopped observation profile and two bounded mount sets; `deploy/lan/worker_replace.py:90` constructs an observation-only command | Existing replacement cannot attach storage to a completed workspace Node; silently generalizing it would alter the recovery contract |
| Node runtime | `services/node-agent/cmd/inv-node/main.go:98` creates a storage sampler in serve mode without prohibiting the workspace profile; execution runner is constructed separately | The Go architecture permits coexistence in principle, but shipped deployment contracts do not authorize or prove it |
| Manifest/package | `tools/lan_workspace.py:63` emits workspace schema 1, software/certificate hashes and exactly three installer hashes; `tools/check_workspace_package.py:88` checks that shape | No explicit contribution/source identity/mount/floor preservation intent; current archive cannot express the required migration |
| Storage channel | `contracts/v1alpha1/core.schema.json:6176` binds tenant, node, epoch, version, endpoint and **DER leaf** hash; root config at line 6359 has no execution profile | No new HTTP storage protocol is inherently required for coexistence; profile is not the problem. A deployment/local mount-binding contract is required |
| Identity and state | `deploy/lan/worker_config.py:83` validates named owned RW volume and exact durable identity arguments; `same_identity` at line 122 preserves identity/endpoints | It is a necessary common validator, not full mount, socket, policy, volume-consumer, journal or concurrency proof |
| Workspace workload boundary | `services/node-agent/runtime/docker.go:215` creates private `/workspace` and `/tmp` tmpfs, UID 65532, network none; line 256 rejects bind mounts | Node contribution does not grant workload host-path access, writeback, or a persistent host checkout |
| Existing storage observation | `services/node-agent/storage/sample.go:112` checks exact channel/contribution/root version and challenge expiry, then signs bounded file observations; transport checks policy/cert before and after | A local startup JSON, mounted folder, or unsigned ready file is not authenticated current storage acceptance |
| Five-node admission | `tools/five_node_lab_preflight.py:15` and line 306 require `lan-workspace-v1`; ADR-100 excludes the CP-colocated Node from independent S05/S07 | Dedicating an independent PC to observation-only storage leaves three independent workspace workers; four plain workers leave contributed storage unaccepted |

The roadmap explicitly includes contributed storage, `inv://` and actual five-PC
storage/execution acceptance. Folder/ACL preparation and four-plain-Node integration
are useful prerequisites; neither closes this contract gap. Root's continuing
integrator `task_78064fb4b7ff` / `ctx_ed7ec73163d6` owns that baseline; this branch
does not modify its checkout or claim derivative integration.

## Reproduction on unchanged guarded source

Interpreter: existing main repository `.venv/Scripts/python.exe`, CPython 3.14.7,
Windows, `-B`; no package installation and no protected pilot interpreter.

Commands (from this checkout):

```powershell
& 'D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe' -B tests/proofs/fleet5_compute_storage_contract_probe.py --require-coexistence
$proofExit = $LASTEXITCODE
if ($proofExit -ne 1) { throw "Expected guarded-source rejection exit 1" }
```

Actual **exit 1, expected red**: unmodified `validate_install_target` raises
`Workspace upgrade does not support storage contribution; preserve this Node and use a separate plain Node for workspace acceptance`.
The fixture first passes `worker_storage.prepare` and `worker_storage.target` for
the synthetic storage-only inspection; its actual workspace call fails. The
nonzero result is the deliverable, not an unreported task failure.

Default fixture command (without `--require-coexistence`) exits 0: owned state-only
and default-socket plain targets pass; the valid two-mount storage fixture passes;
workspace refuses that storage fixture; storage refuses the combined third socket;
single-dash/equals aliases are refused; inspected objects and exact policy bytes
remain unchanged. All identities and addresses in fixtures are synthetic.

Focused pytest: new fixture proof plus existing workspace guard suite **34 passed,
exit 0**; after refining the red call to raise from source directly, the new test
alone **1 passed, exit 0**. These runs overlap and are not added together.
The new pytest replaces Docker functions with a fatal assertion: no daemon call is
possible. This establishes structural rejection, not Linux mount enforcement,
live TLS, authenticated storage, physical equipment or performance.

Evidence siblings: `coexistence-expected-red.txt`, `current-contract-fixture.json`,
`fixture-tests.txt`, `fixture-tests.xml`, `fixture-final.txt`, `fixture-final.xml`.
Source hashes in the default fixture match the unchanged base files.

## Proposed bounded contract A (recommended first implementation)

**Preserve exactly one existing approved read-only contribution while upgrading a
native Linux observation Node to workspace; reject every other storage migration.**
An existing storage install must precede this migration. A plain/completed
workspace cannot acquire/change/remove storage through it. This fits a newly
initialized all-five rollout before first workspace upgrade; root must select its
order explicitly if its plain-node baseline has already advanced further.

Proposed interface, names subject to root's concrete decision:

1. Keep workspace schema 1/default behavior and R4 rejection unchanged. Introduce
   workspace package schema 2 with explicit `storagePreservation` mode
   `existing-readonly-contribution-v1`; require the exact policy SHA, contribution,
   root/channel versions and hashes, original Node/cert/epoch/endpoint, source
   dev/inode and bounded mount properties. No implicit flag from discovered mounts.
   Require CLI `--preserve-readonly-contribution` plus independently supplied
   policy/request hash. No bool coercion, aliases, single-dash flags, duplicate or
   equals-spelled variants; parse complete argv against a closed allowlist.
2. Bind immutable request to current container ID/config hash, owned state volume
   identity/labels/consumer set, bounded journal digest, exact protected policy
   bytes/mode/owner, current `.storage-<contribution>` pin and source identity.
   Native Linux / local default Docker daemon only in this bounded version;
   remote daemons and unproved Desktop/WSL path translations refuse.
3. Allow exactly owned RW `/state`, one `/contribution` bind with readonly,
   nonrecursive, rprivate, and the existing `/var/run/docker.sock` bind at that
   same source/destination, RW/rprivate. A storage-only old Node may acquire
   **only this existing workspace daemon socket** in the accepted mode.
   Reject custom `--socket` values even if the mount looks familiar. No additional
   mount, nested mount, device, alternate daemon, RW contribution or propagation.
4. Reuse storage's strict file/hash/path validation, with descriptor-based
   no-follow ancestor/source checks and repeated identity checks around stop,
   create and start. A source path string alone is insufficient: the current
   Python precheck can race Docker's later path lookup. Add a small **local Go
   mount-binding contract**, e.g. private `/state/storage-mount-binding.json`
   selected by an exact `--storage-mount-binding` path, carrying expected
   contribution/policy hash/root dev+inode and required mount constraints.
   Validate the actual opened root identity and read-only filesystem state
   **before pin/listen/sample**, and retain descriptor/current-root checks.
   Use Docker inspect for exact NonRecursive/rprivate intent and real Linux
   tests for behavior. Host/daemon namespace identity must be demonstrated;
   otherwise refuse rather than claiming a TOCTOU fix from two path stats.
5. Existing NodeStorageRootConfig and signed sample wire shapes stay unchanged.
   Any shared definition for the new local binding must originate in canonical
   schema and generated readers, not duplicate ad hoc Python/Go semantics.
   Schema bounded integers (currently max 2147483647) govern versions; the more
   permissive Python integer check is not authority to broaden the wire contract.
6. Preserve tenant/node/epoch, private key, current certificate bytes, channel,
   peer policy, original storage policy bytes, root identity and journal/pins
   exactly. The migration changes only verified software/profile/workload image
   and the explicitly allowed socket. It must not advance storage floors.
   Write the new mount binding without overwriting existing unknown state;
   journal exact newly owned files and preserve them on interruptions.
7. One deterministic per-Node operation lock/fence must serialize workspace,
   storage replacement and leaf rotation, with a documented lock order. Current
   workspace, bridge/stage and rotation locks are distinct; reusing just one
   existing helper does not serialize all writers. Recheck the recorded container
   and consumer set after fencing. A host administrator is outside this trust
   model; source substitution by ordinary path changes remains tested.

The default installer may continue upgrading plain Nodes. Other helper entry
points must refuse this new combined configuration before mutation until they
implement the same explicit contract. Do not make observation replacement or
execution-probe setup silently rebuild a combined Node.

### Rollout and rollback for A

Root first pins/reviews/CI-tests source and rebuilds all software, helper hashes,
manifests, archives and archive checksums. Before operational execution, root's
integrator selects the storage-enabled observation step and later workspace
upgrade in the all-five plan. This worker does not enroll, issue certificates,
change offers/policies or execute that plan in the proof phase.

Prepare is non-mutating to the container/journal; validation/unknown/stale failures
leave it running or stopped exactly as found. Apply binds the immutable request,
requires no owned workload (including stopped/uncollected), records durable
intent, stops the exact old Node, verifies state/identity again, preserves old
container as backup with restart=no, creates a fenced replacement with the three
explicit mounts, checks it, then starts and validates receipt/state/identity.
No container or volume is deleted. Successful local state remains
`awaiting-server-mtls-verification`, operationalAcceptanceAssessed=false.

Before new work or any floor/authority change, rollback stops/quarantines only
the exact migration-owned replacement, validates the backup and unchanged shared
state, and restores the original ID/mounts/restart behavior. Current backup and
replacement share a state volume; the old container is not an independent backup.
The new binding file may remain as inert migration-owned evidence; do not delete
unrecognized state. Automatic downgrade after ready/new work is refused. Unknown
phase, changed container, extra consumer, journal mismatch, pin advance or failed
rollback preserves both containers, request and journal for exact-plan recovery;
it must not reset state or mark ready. Simulated recovery is not crash proof.

### Certificate renewal is an explicit lifecycle boundary

`services/node-agent/storage/sample.go:84` checks the current leaf's **DER** SHA
against the policy; `transport/storage.go:44` hashes serialized channel and raw
policy, checks cert/root, then pins. `runtime/storage_policy.go:44` refuses a
different channel hash at the same channel version and rejects regressions.
The workspace manifest's `certificateSHA256` is a **PEM file hash**
(`worker_workspace.py:105`); never substitute it for the storage DER fingerprint.

[Historical leaf publisher at source0bcf line920](https://github.com/egparadise/SaintVision-Invion/blob/0bcf9670d098fac87667fc9e2448b332db46e691/deploy/lan/worker_leaf_rotation.py#L920) backs up only cert/peer-policy, then writes
the new public leaf/overlap peer-policy and calls restart. Its
`docker_restart` at line 1105 only calls `worker_config.install_files`, Docker
restart and running check. It does not regenerate/install storage policy.
`tools/lan_pilot.py:3428` and line 3505 stage/commit channel changes separately.
Thus the next leaf makes the old storage certificate binding invalid; storage
startup/sample must fail closed. Keeping the Node key or identity does not make
the leaf fingerprint unchanged. This gap exists even before coexistence.

**Bounded A must refuse leaf install/finalize/rollback on storage-configured Nodes
before any credential, peer-policy, journal or container mutation**, unless a
future explicit compound renewal contract is present. Root-side staging must
also reject the unsupported cohort before channel CAS. No silent sampler disable,
hash-ignore, policy-byte rewrite at old version, journal reset or old-leaf restart
after a forward storage pin. A is safe migration capability, not complete storage
lifecycle acceptance; root must record/assign that remaining work.

Alternative **B** expands this assignment to coordinated storage+leaf renewal:
reviewed future policy bound to new DER pin and channel version, unchanged
contribution/root/root_version/source; package exact old/new policies and hashes;
preflight all selected Nodes; drain/fence, stage public leaf+policy as one durable
generation, restart/pin, then current-channel CAS and signed challenge verification.
Before any new floor, exact old generation restoration can be allowed; after pin
or channel commit use exact-plan forward recovery, never rollback to old storage
channel version. Batch partial failure and compensating forward versions must be
specified and tested with existing root rotation owner. This is a broader local
and batch lifecycle contract, not a one-line mount fix.

## Source/helper surfaces needing coordinated updates

| Surface | Required change or deliberate refusal |
|---|---|
| `deploy/lan/worker_workspace.py`, `worker_config.py` | New opt-in dispatch/closed argv; shared identity/mount/lock/consumer validation; intent, recheck, rollback |
| `deploy/lan/worker_storage.py` | Preserve default two-mount contract; distinct explicit combined validator/receipt; exact policy/channel/root pin checks |
| `deploy/lan/worker_storage_bridge.py`, `worker_replacement.py`, `worker_replace.py`, `Replace-Storage.ps1` | Refuse new combined profile/contract before staging or mutating; do not inherit unknown mounts or observation command |
| `deploy/lan/worker_execution.py`, `Enable-ExecutionTests.ps1`, `tools/lan_execution.py` | Probe installer currently recreates state/socket only; reject storage/combined mode before image load or stop; bind changed helper in packages |
| `deploy/lan/start-node.sh`, `finish-worker.sh`, `Start-Worker.ps1`, repair wrappers | Preserve observation install semantics; only accepted explicit new route can create combined configuration; repair must not overwrite binding/policy |
| `deploy/lan/Enable-Workspace.ps1` | Explicit bounded mode/hash propagation and exact result validation; native Linux CLI also required; no ambiguous WSL source conversion |
| `tools/lan_workspace.py`, `check_workspace_package.py` | Versioned manifest field and complete helper/schema/source hashes; unique members; exact policy/binding hashes; regenerated archives/checksums |
| `tools/lan_pilot.py:1235` bundle and leaf prepare/stage/commit paths | Updated packaged helpers; cohort preflight/refusal for A, coordinated public storage policy generation/CAS for B |
| `deploy/lan/worker_leaf_rotation.py` including install/finalize/rollback/restart | Shared fence and pre-mutation storage refusal for A; compound old/new generation and forward pin semantics for B; preserve mount/config/state |
| Go command/transport/storage root plus canonical schema/generated readers | New private mount-binding parse/open identity/read-only check; preserve signed sample protocol and workload isolation |
| `tools/check_workspace_upgrade.py`, `check_storage_bundle.py`; existing core/integration tests | Extend source bindings and real Linux combined install/mount/rollback/crash/renewal cases, not merely mocked success |
| `tools/check_lan_storage_readiness.py`, `five_node_lab_preflight.py`, remote-workspace wrappers/collectors | Separate package presence, execution profile, authenticated storage evidence and physical acceptance; manifest/source bindings include changed dependencies |

All 45 inspected source surfaces with hashes/anchors are inventoried in Evidence.
The inventory does not claim that every source file must change: unchanged
readers may be validated by rejection/conformance tests. Root's private generated
campaign wrappers/manifest assembler must be reviewed by root against the same
matrix, regenerated from the accepted source and exact hashes, and supplied as
redacted bindings; this worker has not read private configurations or issuer.

## Required red/green and acceptance evidence after decision

1. **Source/contract:** existing R4 default rejection remains green for unknown
   mounts/flags; explicit valid mode turns the meaningful coexistence red case
   green; no opt-in still refuses. Policy bytes/mode/owner, root identity,
   cert/key/channel/epoch, pin and protected journal digests stay exact.
2. **Adversarial:** duplicate/single-dash/equals/unknown argv; custom sockets;
   RW, recursive or shared binds; wrong image/owner/volume/consumer; symlink in
   any ancestor, inode replacement, renamed source, root/private overlap;
   tampered/stale/duplicate-key/wrong-channel/DER-pin policy; interrupted/unknown
   intent; source substitution specifically between last precheck and Docker
   create. Each refuses without success output or destructive cleanup.
3. **Real Linux Docker in CI only:** synthetic local identities and disposable
   uniquely owned containers/volumes; build exact Go binary and packages; real
   read succeeds and write fails on `/contribution`; nested bind remains hidden,
   propagation remains private; actual mount root identity matches before sample;
   substitute source mount at the fault seam and prove rejection before serving.
   Workload UID/tmpfs/read-only/network restrictions persist, contribution and
   Docker socket are absent inside workload, no host writeback. Existing
   `.github/workflows/core.yml:230` runs separate installer tests; extend that
   provisioned lane rather than claiming Windows fixture proof as Docker proof.
4. **Crash/concurrency:** terminate after intent/stop/rename/create/install/start
   and before each phase persistence; retry exact request; source/state mutation,
   extra volume consumer and parallel workspace/storage/rotation contention;
   demonstrate rollback restores exact old ID/mounts and retains journal, and
   unknown/failed rollback preserves both. Unsupported renewal must refuse before
   mutation in A. In B, add old/new channel challenge, new leaf+old policy failure,
   changed policy at old floor failure, channel CAS race, partial batch restart,
   forward recovery after pin, and finalization/replay behavior.
5. **Signed storage:** existing current-authority mTLS request generates an actual
   DB/catalog challenge, bounded Node-signed sample and atomic Evidence/StorageCheck
   consumption; verify actual TLS DER cert, exact request/nonce/root/channel and
   freshness, authenticated readback and rejection of stale/tampered/channel
   mismatch. `storage_commit.py:189`, line 255 and line 328 are existing authority
   and commit boundaries. Local startup JSON is unsigned and stays pending.
6. **Review and physical:** exact source SHA hosted CI and actual Claude verdict
   before candidate inclusion, then root's separately authorized physical all-five
   smoke/storage/execution and four-independent-worker S05/S07. Preserve original
   48-task and VF-CL statuses; no source test changes those statuses.

Resource numbers such as 2 CPU/2 GiB/20 GiB remain proposals until enforced and
measured by an accepted quota mechanism. Existing Node container limits and
individual workload limits do not impose a host workspace-disk hard quota.

## Decision requested from root

Choose **A**: authorize only native-Linux preservation migration with a versioned
package/private mount-binding contract, exact unchanged storage authority, default
R4 guard, and mandatory early storage-renewal refusal; assign compound renewal as
an explicit remaining blocker. Or choose **B**: authorize the same migration plus
coordinated compound storage-policy/leaf/channel lifecycle now with the existing
rotation owner before deployment. A third safe outcome is to defer this derivative
and retain the four-plain-Node baseline explicitly without claiming contributed
storage acceptance. Please also confirm root's selected rollout order (storage
observation before workspace for A); no production change occurs before reply.

## Current delivery state and next action

Worked: source proof, bounded proposal, 45-surface inventory and fixture tests.
Checked: expected red exit 1 and focused exits 0 above; validation/commit/push/Docs
results are recorded in the sibling `delivery-state.json` when available.
Required `check_docs.py` actually **failed exit 1** on two pre-existing base
History links to the absent Low-closure review page; `base-docs-blocker.json`
proves both source pages exist at base (git cat-file exit 0) and the target is
absent in this checkout and root vault. The chained gates stopped. Commit, push
and hosted Docs are **not attempted**, with no gate bypass or shared-page edit.
The initial metadata-edit quoting failure and correction are retained in
`validation-errors.txt`. Root must reconcile the missing combined documentation.
Implementation **not started**; independent Claude review **pending**; real Linux
Docker, physical PCs, signed storage and operational acceptance **not performed**.
Obsidian apply **prohibited by this dispatch**, not pending implicit approval.
Next owner root: answer the structured Orca ask with A/B/defer and concrete scope;
next owner Codex: implement only the accepted contract in this branch, then
red/green, actual CI and independent review before candidate inclusion.

Subsequent root replies selected staged B contract publication and an early
native-Linux plain-mode Go proof before production implementation. See
[[2026-11-05_FLEET5_compound_lifecycle_B_contract_Codex]]. The original base proof
above remains historical. Accepted lifecycle 2fb was normally merged into this
proof branch, retaining combined DB preparation and current lan-pilot tooling
bindings; no new production lifecycle implementation was authored.

## Aggregated citation clarification

Codex Root changed only the historical line920 citation into an immutable source0bcf link when collecting this page into the report branch. That exact Git blob has1171 lines and the cited publication phase was read back. The Root report branch keeps an older804-line product file; this historical statement does not describe that file or imply product integration. The original source323 page bytes/hash are retained in the import receipt and Git history. No proof result or design decision changes.
