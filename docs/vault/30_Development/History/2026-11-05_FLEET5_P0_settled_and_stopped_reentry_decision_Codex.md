---
doc_id: "DECISION-FLEET5-P0-SETTLED-STOPPED-REENTRY-001"
title: "FLEET5 P0 bounded settled helper and stopped publication re-entry decision"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Root contract decision; independent Claude delta review pending"
updated: "2026-11-05T22:10:00+09:00"
source_of_truth: "Git"
---

# Requested bounded liveness decision

Owner Codex; `FLEET5-COMPUTE-STORAGE-CONTRACT-20261105`,
`task_a8fd2969f0b3 / ctx_6f0f8253b8a7`, branch
`agent/codex/fleet5-compute-storage-contract-20261105`. Published source candidate
is `6c0fc4adf53562909e3d8246ddf293d8aadb0d0e`; published fixture-only nonce fix
is `526d48e4bdcbb0b363d6e45bfc5635fcc1584d2a`. Root's actual code review
`c2102592f9c2204ac96a49c5d0af4a2f888951f5`,
`task_fcd89694c5b7 / ctx_d0aa7908032b`, does **not accept 6c**. This page requests
the precise F2/F3 contract decision directed in `msg_a9b66905c786`; it is not
implementation acceptance or a request to repeat already granted P0 approval.

Guidance/version/base inventory remains in
[[2026-11-05_FLEET5_compute_storage_contract_Codex]]. Initial P0 authorization and
M1–M10 are recorded in [[2026-11-05_FLEET5_P0_plain_peer_phase_implementation_Codex]].
No production F2/F3 exception has been implemented in this proposal. Root's
later `msg_b2c6d37559b1` separately authorizes a bounded signed
`servingExecutableSHA256` from the actual owned executable descriptor, retaining
the existing raw-cmdline meaning of `servingProcessSHA256`; that source/wire/
fixture/native closure is pending. No new bootstrap predecessor/consumer class
is authorized or implemented here; unknown consumers remain refused.

## Source proof and current results

At exact 6c, `deploy/lan/worker_leaf_rotation.py:docker_restart` stops the exact
owned container, copies public credentials while stopped, then starts that same
container. A crash after stop/copy can therefore leave the already owned Node
stopped. `deploy/lan/worker_peer_floor.py:observe` requires a running Node, and
the Go observer binds its signature to the actual serving process and requires
the durable floor hash to equal the active policy bytes. Consequently ordinary
install/finalize replay cannot observe a stopped publication transition.

At exact 6c, `deploy/lan/worker_config.py:no_rotation_mutation` rejects any
leaf journal/archive, including a valid finalized rotation. This safely fences
legacy writers but also prevents useful operations after settlement. A completed
rotation must retain its immutable original journal/archive; deleting or renaming
these to bypass the guard is excluded.

The preserved hosted receipts are under
`Evidence/fleet5-compute-storage-contract-20261105-codex/p0-native-candidate-failures/`:

| Head / Core run | Actual result | Main Core |
|---|---|---|
| 6c / 42028616559 | FAILED, zero complete cycles, actual floor 7; fixture emitted base64 nonce although NodeProbeInput requires lowercase hex64 | Skipped |
| 526d / 42029207673 | FAILED, zero complete cycles, actual floors 7 and 8; real handshake pinned overlap and rollback was refused, then canonical outer receipt signature mismatch | Skipped |

Both artifact ZIP SHA-256 values were verified against GitHub's digest, with raw
job states and failed logs preserved. No schema/handler relaxation was made for
the nonce. Local uncommitted corrections now use the actual request producer in
a shared NodeProbeInput test with a base64 negative, preserve canonical JSON plus
newline for outer receipts/commits, and keep the Go floor's distinct domain and
encoding. The latest full relevant migration probe recorded 140 passed, 3 failed,
14 Windows platform skips; those three failures exposed final-observation nonce
instability on archive retry. A durable first-final-observation fix makes all
four targeted archive crash/residue cases pass. Twenty-four focused protocol and
request tests pass. No later native/full-Core green or corrected-delta review is
claimed. Standalone lifecycle proof migration, legacy historical-reader coverage,
README five-module closure and field-wise bd96479b typed checks remain pending.

## Recommended bounded contract A

### RS1: explicit forward start of an already published frozen phase

Add `resume-publication --bundle <exact-proposal> --worker-root <owned-state>`;
final phase additionally requires its exact signed CP commit receipt. It is a
new bounded command, not an exception to initial preparation's fresh signed Go
floor requirement. The original signed pre-floor and durable publication intent
must already exist and verify before this command considers a start.

1. Take the existing per-Node leaf lock without stealing a stale lock. Require
   strict normal :3, exact proposal digest/phase binding, valid unexpired chain,
   cert/key/policy tuple and the original signed pre-floor/install receipt as
   appropriate. No expired, unknown, legacy in-flight or recomputed transition.
2. Require the exact recorded container ID, image, config, mounts, volume label
   and allowed consumers. The current container must be stopped; every retained
   backup remains stopped with restart=no. Recheck before/after reads and start.
3. Read existing volume entries through Docker's exact container transport,
   with bounded regular-file TAR entries, no symlink/hardlink, expected root
   ownership/0600, strict duplicate-free integer/hash/scope parsing. Identity and
   actual floor bytes must exist. Host and volume public bytes must equal the
   frozen expected phase. Private bytes stay in memory and never enter evidence.
4. Only these actual tuples authorize **start eligibility**:

| Frozen intent | Existing actual floor | Exact active peer bytes |
|---|---|---|
| installed/installing overlap | P/current hash or P+1/overlap hash | P+1/overlap hash |
| finalizing with verified CP C+1 commit | P+1/overlap hash or P+2/final hash | P+2/final hash |
| already finalized exact archive | P+2/final hash | P+2/final hash |

5. Invoke only `docker start <that exact container ID>`. No create, load, copy,
   rename, policy rewrite, floor reset, journal replacement or old restoration.
   Go's existing startup pin independently rejects lower/same-version-different
   hash. New-policy expiry is checked in Python before this start, so the known
   Go pin-before-expiry behavior does not turn an expired proposal into a retry.
6. After start, require the real Go observer's fresh nonce/signature and exact
   expected phase/DER, plus unchanged ownership. Only that fresh Go response can
   become an acknowledgement. Then the original install/finalize path can resume
   against the same frozen proposal. A failed start/ack remains forward-only.

The distinction needing root decision is explicit: a strict unsigned read from
the **actual stopped owned volume** is used only to decide whether to start the
already published frozen phase. It is never represented as a signed floor,
never substitutes for M2 initial preflight, and never becomes CP/Node acceptance.
No helper container, sideloaded binary, host mirror, old-image fallback or new
runtime-image bootstrap is introduced.

### SF1: settled verification for bounded generic operations

Add a read-only `verify-settled` operation to the reviewed five-module leaf
runtime. Under the generic helper's existing leaf lock it verifies the exact
normal :3 finalized journal and immutable archive (including original bytes,
no `.next` residue, all signatures and CP commit), current policy/cert/key/CA
bytes, and a fresh real Go final P+2/hash/DER observation from the exact owned
Node. The existing pinned standalone launcher/module validation supplies the
crypto runtime; absent/unreviewed runtime stays blocked. No environment bypass,
arbitrary import path, unsigned external receipt or manual true flag is accepted.

Allow only idempotent operations or credential copies that preserve the already
verified exact public/private bytes and existing Node/volume identity, with an
actual post-operation Go check where a restart occurs. For a stopped Node, RS1
must first establish the running signed observation. Archive history remains
immutable. Generic workspace/execution actions changing container, image,
profile or mount ownership, and all storage transitions, remain explicit
migration-required under their own next contract. This closes restart/idempotent
liveness without silently approving a new runtime/profile/storage migration.

## Alternative B and rejection conditions

If root requires post-settlement container/profile/image-changing generic
upgrades now, select an explicit broader migration contract: a new immutable
operation receipt binding the settled rotation archive to the new owned
container/config/consumer set and actual pre/post Go floor observations. This
must coordinate with the root's runtime/permit-image inventory decision and
future compound lifecycle; it cannot overwrite the original rotation's frozen
target context. It requires a separate concrete design/review before coding.

Under either selection, wrong/missing floor, unknown hash/version/phase, changed
mount/consumer/container, unsafe TAR metadata, expired tuple, invalid signature,
stale/tampered/channel-mismatch input, missing CP final commit, predecessor
residue or failed preflight must preserve current container and journal. There
is no downgrade, old restart, generic mount copy, RW contribution or workload
host-path grant. Resource policy remains separate from hard quotas.

Required proof includes real Linux Docker crashes after stop/copy/before start,
re-entry to exact P+1/P+2, unknown/future/same-version-different-hash refusal,
expired pre-start refusal with unchanged floor, wrong-owner/volume/consumer
refusal, stale-lock preservation, settled idempotency and post-start actual Go
acknowledgement. Python unit signatures alone do not discharge these cases.

## Standalone proof result compatibility decision

Root's additional `msg_62c3487ffb5b` identifies
`tools/check_leaf_rotation_standalone_lifecycle.py` as another live consumer.
Its existing fake Docker proof still assumes the legacy protocol.
`bd96479b1cd33ea560e3d2ad55030e5c0e7d25e2` adds strict Backend assertions,
including `lifecycle['rolledBack'] is True`. A normal :3 publication must refuse
that rollback under M5; it cannot truthfully return that old success value.

Propose versioning the standalone result to normal :3 semantics: two complete
fixture CLI cycles (four successful phase restarts), `finalized is True`,
`finalizedAttestationVerified is True`, `installRestartReceipt is True`,
`rollbackRejected is True`, **`rolledBack is False`**, and strict integer counts
for restart and bytecode files. Keep the bd96479b strict identity/type checks
field-wise, updating only this explicitly changed rollback expectation and the
new required negative. The five-module count remains five. Retain standalone
mutation negatives and original-byte archive/residue assertions. Its fake Docker
transport remains explicitly a fixture interoperability proof; actual Go/Docker
acceptance is supplied by the separate native and provisioned Core lanes.

This is an output-contract correction request, not permission to weaken a gate
or label mocked observations as native acceptance. Retaining `rolledBack=True`
for normal :3 would contradict the accepted forward-only contract.

Next root action: choose A (RS1 plus SF1), narrow either allowance explicitly, or
choose B with the required migration receipt scope; also settle the truthful
versioned standalone rollback-negative output above. Codex will implement only
that decision and submit a new exact source/CI binding for independent delta
review. Physical/private/scheduler/bootstrap operations remain outside this task.
