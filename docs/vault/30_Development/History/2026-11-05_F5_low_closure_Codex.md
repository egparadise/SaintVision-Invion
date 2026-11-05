---
doc_id: "HISTORY-F5-20261105-LOW-CLOSURE-CODEX"
title: "2026-11-05 F5 final Low closure and later preparation stage contract"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-05T16:13:52+09:00"
source_of_truth: "Git"
---

# F5 Low closure: local preparation and a nonexecuting contract

Task `task_26607075f612`, dispatch `ctx_69be9896a8e3`, owner Codex/reviewer Claude. Branch `agent/codex/fleet5-low-closure-20261105`, actual worktree `D:/Project/SaintVisionI-Invion/fleet5-worker-readiness-20261105`, base `6cbb2b9801dc5040b5a5ad70bf7b5434130d8ccc`; product/source archive remains exact59f. Root supplied actual Claude review `087aaf3521608a19fff28c8d70bacdda92697367` and verified Docs41983434951 success: P1–P8 are resolved **as a plan**, 2-to-5 append-only extension is supported, P2 installation remains blocked. This task closes only the remaining Lows; it does not infer runtime/five-Node acceptance.

Read current coordinator Index1.0.397/Codex1.0.358 (local inherited copies393/354), unchanged required governance and agent-delivery1.1.0/core-reliability1.0.0, the actual087aaf review and source59f rotation implementation. No common board, registry, Obsidian apply, bootstrap source or separately owned R4 source is edited. This task performs **no remote authentication, rule, CA, DB, Node or listener change**.

## Actual local change and preserved bytes

An F5-owned private `known_hosts.f5.pinned` was copied from the existing protected pinned source into ignored `.work/f5-low-closure-26607075f612`. The new file/directory received owner-only ACLs using the source59f private-file helper, exit0. No SSH/SCP command was run. The original file was read and hashed before and after the copy and ACL action; the destination was read back and compared byte-for-byte.

- Original SHA256 before and after, and F5 copy SHA256: `0dcbf0f4cfc363e4affc30810ad8a9e57bd2c4a31991e2c8285bdae7052ec2d2`.
- `known-hosts-copy-receipt.json` records actual KST, byte count, equality, pre/post digests, ACL exit and no transport invocation. Hostnames/addresses/keys are not published.
- Effective private parameters and all SSH/SCP/denied-peer vectors now select the F5-owned copy. StrictHostKeyChecking=yes, UpdateHostKeys=no, existing key identity and bounded BatchMode behavior are retained. Later transports must verify both original and copy against these pins before/after their group; mismatch stops progress, never auto-updates trust.
- The original reviewed public core hash `5121cb83…` and old frozen packet remain unchanged. The local source59f archive was actually rehashed to `a9f0a3b88c6b9f31b5133bf1bce388fa574f201832d32b324b1a08ed3d9911a9`; it was not rebuilt or patched.

The public effective overlay and exact updated hashes are under `docs/vault/30_Development/Evidence/f5-low-closure-20261105-codex/low-closure-packet.json`. Private resolved vectors/parameters/SQL remain in ignored `.work/f5-low-closure-26607075f612`; only hash-bound references are public. This overlay supersedes old transport-path and generic quiescence wording, while preserving the earlier reviewed plan's unrelated inputs.

## H1 and CA custody wording

The earlier History step4 now explicitly selects **non-r5 main .venv Python3.14.7**, `-B`, inherited `PYTHONDONTWRITEBYTECODE=1`, no pip and exact59f tool paths. Step5's bundle command now includes `-B`; the reviewed execution vectors already had it. These are documentation corrections only.

The intended development CA custody is **rootOnline=true /rootOffline=false**: encryption and a separately located password file do not prove offline custody. The planned external issuer's root key remains in its online CA tree unless separate evidence proves otherwise. This task generated no hierarchy; the planned F5 state and issuer directory are absent on actual local stat. No offline-root or new-certificate claim is made.

## Firewall proof expires on host or routing changes

The selected route is **re-proof**, with no OS persistence changes here. A prior ingress receipt becomes invalid after worker reboot/boot identity change, firewall reload/restart, Docker/backend/network restart affecting routing, rule/order/hash change or unknown event history. Before publishing/resuming a new F5 Node, the authorized operator must re-read the correct backend chain/order and exact original-destination18515/Node-IP/CP-only scope. Stale proof cannot authorize publication.

After startup, require the same-time combination of a successful fresh-CA authenticated CP observation, failed known-worker3 TCP connection while the Node listener is active, scoped deny counters, direct exits/KST, and current boot/backend/rule hashes. An absent listener alone is not a firewall pass. A separately reviewed persistence mechanism could be proposed later, but none is installed or assumed. On invalidation block new publish/resume and append acceptance, isolate only exact owned new F5 resources and re-prove; never alter r5.

Until persistence is reviewed, this remains an attended connection phase: do not leave new F5 Nodes active unattended or claim reboot-safe ingress. Stop only new owned F5 Nodes at session end and before controlled reboot/reload. An unplanned event invalidates acceptance and requires authorized isolation/re-proof; the shipped container restart policy alone is not proof of a safe resumed firewall state. No restart policy or OS setting is changed here.

## Precise zero-uncommitted-batch gate before append

Source59f stores rotation authority in filesystem manifests and `leaf-rotation-batch.json`, **not a fictitious SQL batch table**. Before a later append, obtain one complete hash-bound snapshot of the exact F5 tenant/epoch/active Node set, current public leaves/policies, CP/Node rotation locks, every registered F5 prepare/recovery batch output (including `.next` and orphan output), signed CP commit receipts, Node finalization evidence and actual channel/epoch rows. All output roots must be registered in a bounded F5-only catalog; incomplete, unreadable, unsafe, malformed or unregistered material is UNKNOWN/BLOCKED.

| Actual journal/artifact state | Gate classification |
|---|---|
|`prepared` |Uncommitted, even with zero staged Nodes or expired overlap; never auto-abandon |
|`staging` |Uncommitted regardless staged count |
|`staged` |Uncommitted even when all Nodes staged; CP commit is still absent |
|`switched` |Only a committed candidate; require bound batch digest/tenant/epoch/set, actual next CP leaf, target enabled channel versions/certificates, valid per-Node CP-signed committed receipts and same-batch Node finalization/final policy evidence |
|Historical terminal output |Close only through verified signed commit/finalization chain or valid repository abandonment evidence with matching digest and unchanged unstaged authority; a filename or phase alone does not close it |
|Absent journal |Only a candidate no-active-batch condition; still inspect complete registered/orphan artifacts and actual current channel/policy consistency |
|Any ambiguity/lock/writer/partial output |Block and preserve; do not delete, recover, clear a latch or force a zero |

PASS requires **preparedOrStagedUncommittedBatchCount=0**, unfinalizedCommittedBatchCount=0, unknownCount=0, no live rotation writer/CP or Node lock, valid final policies, stable pre/post hashes and exact-context read-only DB evidence. A valid historical abandoned archive can retain `phase=prepared`; validate its abandonment schema/digest/timestamp/unchanged authority rather than treating the filename as proof. A `switched` journal alone is insufficient because CP receipt creation or Node finalization may still be incomplete.

The planned SQL uses `BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY`, asserts `SHOW transaction_read_only=on`, sets only transaction-local tenant context, reads `inv.control_epoch` and tenant-filtered `inv.node_channels`, then ROLLBACK. The file classifier, not a fabricated SQL COUNT, derives batch counts. Record actual KST, direct exits, registry/file hashes, all counts/unknowns and signed/channel/policy proof digests when this query is eventually run. A reviewed single-owner execution exclusion must cover check and append; do not claim source59f init itself provides an atomic rotation fence.

**Current result:** F5 state is absent; DB/SSH query was **not executed**, pending/unfinalized counts are **null**, and append is **not accepted**. Local path absence was measured; it is not a measured zero-batch query. `append-quiescence-gate.json` keeps this distinction explicit.

## Later actual preparation: current stage contract

| Stage | Current disposition |
|---|---|
|This Low task |Local docs/packet, exact known_hosts copy/ACL/hash checks only; no remote auth or operational change |
|01–02 and07 preparation |Earlier classified safe only for later admitted owner-attended execution, outside r5 exclusions and with actual headroom/ownership/cap proofs; not executed here |
|03 PG/bootstrap |**HOLD**: root must resolve Core41982378091's existing runtime-hardening failure and the source owner's exactly-one same-head failed-job retry/separate59f investigation; this worker does neither |
|04b external issuer |Later reviewed long-lived development issuer preparation; rootOnline caveat remains, no generation here |
|05 init /09 enroll |**HOLD** until a real P2 operator appointment/date is fixed within about4days; these commands start six-day leaves with legitimate48h renewal window |
|09 finish/start and10 acceptance |**BLOCKED** on actual P2 authorized operator rules/proof and post-event re-proof; no privileged Docker/helper/account workaround |
|Later2→5 append |**HOLD** until extension prerequisites and the actual precise zero-uncommitted/finalized query are measured; no current zero assumption |

The possible temporary-initdb Unix-readiness issue is **not a proved cause** of the Core failure. Root owns the release decision and accepted source/CI evidence. If a future source repair changes bootstrap bytes, it needs a separately reviewed new archive/pin revision; this task neither edits nor silently overlays source59f, bootstrap or R4 guard. Existing r5 sources, keys, profiles, epochs, containers, pins and three renewal followups remain outside this task's write scope. No generic approval question is introduced.

## Checks and handoff

Focused existing rotation-batch tests, local docs/ontology/ratchets/sync-check and exact hosted Docs evidence are recorded in this task's check/delivery receipts. No new tests mirror the Low implementation. Current operational queries remain unperformed and no source-level runtime repair is claimed. Obsidian apply and common-board updates belong to the coordinator.

What was done: H1 corrections, an actual exact-byte F5 known_hosts copy and a precise nonexecuting Low-closure/stage overlay. What was verified: copy/source/archive bytes, selected local checks and same-SHA Docs CI in Evidence. Next owner **Codex root /Claude**: review the effective Low packet; root resolves stage03's actual source/CI blocker and actual P2 operator date before any later preparation/init/enroll, then measures the append and firewall gates. Physical FIVE acceptance remains false.
