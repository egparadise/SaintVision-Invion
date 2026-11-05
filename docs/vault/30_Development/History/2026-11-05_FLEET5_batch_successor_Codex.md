---
doc_id: "HIST-FLEET5-BATCH-SUCCESSOR-20261105-CODEX"
title: "FLEET5 verified public normal batch retirement and successor"
version: "1.3.0"
status: "review"
author: "Codex"
updated: "2026-11-05T18:36:00+09:00"
source_of_truth: "Git"
---

# FLEET5 verified public normal batch retirement and successor

Same card `FLEET5-CONSECUTIVE-LEAF-ROTATION-20261105`, task `task_a9b68a07d157`/dispatch `ctx_4194506d5037`; owner Codex, independent Claude reviewer through root. Branch `agent/codex/fleet5-consecutive-leaf-rotation-20261105`, original source base59f, Node milestone `a93ec9f1906cf5374fa8e2de172e11be0fd7cbdf`. Required document/skill versions and original scope are in [[2026-11-05_FLEET5_consecutive_leaf_rotation_Codex]]. Root message `msg_0ee0b2f49d8b` authorized the necessary public CP tooling/worker contract/tests/README extension; no worker or helper agent was spawned.

## Design and source proof

The original complete two-Node batch prepared, installed, staged, switched/committed and finalized successfully, but after four fixture days a distinct normal batch failed **1 failed / exit1**: `Another leaf rotation batch owns the pilot state`. This red was produced on a93 before CP edits. Red-test SHA256 `3dfefa84dddc207457527893e81e15cc708d0c6c5337367e6c8665d419eb3742`; original CP SHA256 `1a8ccbc5c884c562ec6038a2fd20bcb88b6ecf544797f4fe4484ddd30349c49b`. No system clock, old live receipt, claim or latch was reset.

The concrete design was sent to root as `msg_de70f202b211` before implementation. A Node now exposes public `attest-finalized`: it validates the exact active finalized journal, immutable a93 archive, current leaf/key/CA and final policy, and signs a distinct attestation binding tenant/Node/epoch/rotation/proposal/version/Node+CP certificate hashes/final-policy hash/full-evidence hash. The full public evidence accompanies the signature; a signed install receipt or unsigned boolean cannot substitute for this finalization signature. The immutable a93 proof format remains valid and is not rewritten.

The CP now exposes explicit `retire-leaf-rotation-batch --bundle ... --finalized-receipt ...` repeated once per active member. It requires switched phase, every unique Node signature and embedded signed install/CP receipts, exact batch and all current public files, pinned CA, tenant/epoch/address/member set and locked DB channel version/hash/expiry/enabled/endpoint. It publishes an immutable CP-signed archive containing the exact switched journal, terminal journal, batch and all public Node proofs, then atomically records phase `finalized`. It never treats `switched` alone as Node finalization and never unlinks or resets the active journal/lock.

New normal preparation accepts a verified terminal predecessor only while all current authority and membership bindings still match. It preserves archived evidence and replaces the active slot only after a complete new public batch is published. The complete-output/old-terminal crash window is explicitly revalidated and resumed. Exact same-batch prepare/commit replay preserves terminal phase; old batches cannot replay across a later active generation. Unknown, partial, prepared/staging/staged, uncommitted, stale, tampered, colliding or redirected history cannot retire/start a successor. Legacy switched journals require this explicit command with every Node proof; legacy Node finalizations first replay their exact finalize inputs to create the public proof.

## Verification and delivery state

New evidence is isolated under `docs/vault/30_Development/Evidence/fleet5-consecutive-leaf-rotation-20261105/batch-successor`; the a93 evidence remains unchanged. Two complete NORMAL batches are exercised for both **2 and 5 fixture Nodes**, with real Ed25519 issuer/CSR/signature validation, the public CP prepare/stage/commit/retire APIs and worker install/finalize/attestation APIs. DB persistence is a CAS fixture and restart callbacks are substituted; these are source tests, not hardware acceptance. Prior/current certificate hashes, distinct batch IDs, generation relationships, immutable prior CP/Node history, old backups and unchanged keys are asserted. The standalone hosted lifecycle helper also exercises the actual launcher `attest-finalized` command.

Initial expanded focused run: **194 passed /19 capability skips /exit0** across batch successor, consecutive Node, existing leaf rotation, standalone runtime, multi-Node pilot and PKI tests. After exact archive/terminal-byte checks, CLI wiring and staged-archive durability hardening, final focused result is **197 passed /19 capability skips /exit0** (`batch-successor/focused-final.txt`); counts overlap and must not be added. Final local docs/ontology/contracts/frontend-integrity/single-source and path ratchets/ontology generation/sync-check/freshness reporter are all **exit0**, and serving/route tests are **50 passed /exit0** (`batch-successor/local-gates.json`). Sync:2250 managed/46 pending/0 conflicts/no writes. Windows cannot create test symlinks (OS1314); POSIX ownership and shell cases remain hosted Linux requirements. Final changed-source CI and actual independent review remain pending.

New negatives include every nonterminal/unknown phase, missing/duplicate/unsigned/foreign/tampered Node proofs, uncommitted CP, wrong CP key, Node leaf/final policy, CA/epoch/member drift, DB version/enabled/endpoint/expiry drift, archive/staging collisions, stale terminal/archive signatures/bytes, locks and symlinks. Crash tests preserve publication evidence and resume through the explicit verified paths. No prior journal/backup/certificate/key/receipt is discarded or overwritten by retirement.

The only affected current-tooling metadata pair is `source.toolSHA256[tools/lan_pilot.py]` and `source.toolGitBlobSHA1[tools/lan_pilot.py]` in Card150's Evidence JSON. After final tests, root received exact proposal `msg_4c0d159d6c2a`: SHA256 `b282767fbb3d71bb07ae94ea2c80ea26262f32485d4c6575f9553484563fe4e9` / Git blob `502edf7b85582ad40fee1c48703787d7b87ce421`. At the published `c540e4846a084401268c7e3271b55f46d8b896b5` milestone this proposal was deliberately not applied. The197-pass precommit run correctly checked the then-current a93 HEAD pair and is not claimed as c540 committed-head metadata validation.

Root independently recomputed both requested source values and authorized exactly these two fields in `msg_b61483e8e0f3`. Codex applied them at18:21KST, rederived the actual source bytes/blob first, and programmatically compared every other JSON field for exact equality (`batch-successor/tooling-pair-applied.json`). Every historical observedAt/source commit/controlPlaneToolingCommit/observation/verdict and every other hash is preserved. In particular this base59f's preparation pair remains unchanged; root's integrator owns combination with DB864's separate preparation pair. The original proposal remains as historical evidence, and the application receipt records the later authorized action.

At18:21KST the exact a93 Core41995694509 and Docs41995699334 were both **success**. This is Node-only milestone CI, not the extended source's CI. Exact c540 Docs41999753647 was dispatched separately. Final metadata-bound committed-head PKI check, Core/Docs and actual Claude review remain pending. No bootstrap source was changed or failed hosted run silently retried.

Final source worker SHA256 `3411ba485aad6ee0cc356191759584aecfca76ce1421aef68d138fabb7ef603f`, CP SHA256 `b282767fbb3d71bb07ae94ea2c80ea26262f32485d4c6575f9553484563fe4e9`; the standalone launcher pins the worker bytes. The frozen a93 source/evidence and original source59f archive remain unchanged.

Next first action: Codex completes final focused/local gates, publishes the separate future code revision and exact Core/Docs evidence; root obtains actual independent Claude review of that SHA. The Node-only a93 hosted runs remain milestone evidence. Base59f bootstrap is unchanged; unrelated hosted failures are reported for combined integration without silent retries. No live CA/Node/Docker or remote connection, private r5/executorB5, source03, frozen first-wave archive, hardware map, permissions, board/registry, schedule/pin or Obsidian apply was changed. Existing48-task/VF-CL and physical FIVE acceptance remain unchanged.

## Published final source and actual review in progress

Final metadata-bound source is `8b53fbfef107837602b1b2f700e1f8e7bae28638`; committed-head `tests/test_intranet_pki.py` is **6 passed /exit0**. Exact Docs42001888497 is **success**. Exact Core42001883513 is in progress, and by18:35KST its LAN installer, recovery, build fairness and real PostgreSQL script gates had passed; the full pytest step was running. Both run heads were checked against8b. This is not terminal Core success.

Actual independent Claude review is task `task_2aba347fdf39` / dispatch `ctx_7b3724557215`, reviewer terminal `term_c10f1342b1c3014f6084923a120ee960`. Claude's early `msg_abd41fa0c0d6` confirms matching hashes/exact metadata scope and reports **79 passed /10 Windows/POSIX skips** in the two new test files. Its additional probes completed three consecutive two-Node batches and refused mixed stale/duplicate proofs and attestation after a successor install. **Verdict remains pending**; these are actual reviewer measurements, not owner self-review or final acceptance.

Three actual early Low findings are preserved for root's disposition under the requested source freeze:

- L1: a crash between immutable `os.link` publication and temporary unlink can leave an equal `.next`; exact replay accepts it without removing it, while the external Low-closure classifier currently calls any `.next` an orphan and blocks. The private classifier/registry must understand any future terminal archive contract; no private file was edited here.
- L2: retirement crash replay currently requires byte-identical transferred attestation JSON files. Reformatting a semantically identical file causes an archive collision and leaves `switched`, safely refusing retirement; canonicalizing inputs is a possible later improvement.
- L3: README should state the same member set, Node/CP keys, tenant/epoch/CA/IP requirements and that add/remove/revoke/re-IP blocks retirement/succession more explicitly.

Root's `msg_2da317f8afed` says to retain the same Dispatch/source, collect the actual terminal Core result/artifacts and obtain the final actual review before `worker_done`; no new source change or broad test is authorized absent further steering. The existing `gh run watch42001883513 --exit-status` is still observing that run. No Low disposition, final review acceptance, terminal CI result or FIVE acceptance is inferred.

Later steering `msg_efc20b4eded2` supplies actual Claude **ACCEPT (source)** at `b852f9e089bac41fc19bd6060230aef90823f885` for8b and authorizes the narrow L1 source repair, strict L2 byte-binding documentation and L3 fixed-cohort documentation. Codex read the actual committed review JSON. The separate delta/red/green/gates/CI/review record is [[2026-11-05_FLEET5_rotation_low_closure_Codex]];8b remains a preserved milestone, and its Core result is collected separately.
