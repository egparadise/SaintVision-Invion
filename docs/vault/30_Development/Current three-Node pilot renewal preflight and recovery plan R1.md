---
doc_id: "PLAN-FLEET5-CURRENT-THREE-NODE-RENEWAL-R1"
title: "Current three-Node pilot renewal preflight and recovery plan R2"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-11-08T08:13:20+09:00"
source_of_truth: "Git"
---

# R2 decision and lineage

**HOLD: no migration, renewal, restart, recovery, scheduler or operating release is authorized.** This is the single living plan, revised R2 at its retained R1 filename, not a second plan or implementation. Original actual Codex author, task task_3e413989dcaa/ctx_80dec9e2eb1e, branch agent/codex/fleet5-current-three-node-renewal-plan-r2-20261108, direct base a3c6984fa25c6cf179827e15e4259000e7bd294e. Actual independent Claude f29228ed28c651cb2470b45d9f8d14521e1ce75d returned REQUEST_CHANGES with mandatory MAJOR F1/F2 and F3-F6. Original review/verdict and R1 receipts remain immutable. R2 author corrections require a future actual Claude delta review, not self-acceptance.

Read-only management: Root53803f6ea0a2c6cf83074cfa71850892ba4a1873ae5, Index1.0.538/Codex1.0.499/History1.0.147. AGENTS, agent-delivery1.1.0/core-reliability1.0.0, role/continuous governance/final plan/ADR, doc IDs/versions and tracked/untracked status are pinned in NEW unique Evidence/fleet5-current-three-node-renewal-plan-r2-20261108-codex. Its operation-manifest.json, source-contract-map.json and finding-dispositions.json are the R2 proposal/pins. R1 receipts/ZIPs stay intact; Root integrates this delta and never exports this older whole board/vault.

Distinct sources: Node/runtime1efea494f026e932360c35ae811b6423d874a2e7; API96afd799d49717fd40e4ddabd538d82accbe1958/schema0068; UIabb7074e3da0d547ac81d3da33dce347d5c656af. Every product citation below is a full-SHA GitHub permalink, mapped to exact bytes/ranges in R2 source-contract-map. Product/tests/tools/contracts/workflows/policies/fixtures/docs-sources remain byte-identical to the direct base.

## Current custody and historical observations

Tenant97968b42-68aa-40ce-af5e-3a33e2fc2205, epochbcd581be-31b4-4aca-86e6-3ca31b69ed09, projectprj_01M6NDBHVD2DZQ1Q38DCKN1XE3. Exactly these members; no reenrollment, old seven rows, PC1/PC5 addition or obsolete disabled renewers:

| Member / account / IP | Node ID | Pre-migration container ID |
|---|---|---|
| PC2 saintvision-invion / 192.168.45.143 | nod_01M6TGQZ8S3DAFS7TYE8TY1PX2 | fd4bdef2db94c434b740916d50fc0d3e80c5aa49bfe01f45b415f23877e03084 |
| PC3 saintvision-invion3 / 192.168.45.222 | nod_01M6TAWG25JTA3F7J7S1EE4N2W | 702fa3fbc43e8deded94e67c6e5299eb4549958e074ba4aeb40c216db29752f7 |
| PC4 inviz / 192.168.45.210 | nod_01M6TGSXV1J7XWC5D5H7N6EW1D | e74fde5e18c65df59e3f19e4ba988c43ff27a3ff76021412eb71cc79957d489e |

Historical image sha256:de654cd385307ac7147baf6757a480f803361eb5b30d40c7991b272a6889d87f, label ai.saintvision.owner=root-cpu-1efea-r1, profile cpu-pilot-1efea-r1, UID1000:1000, RO root/cap-drop ALL/no-new-privileges. Each account's ~/saintvision-share/nodes/NodeID is RO /config; child/state is RW /state, existing local Docker socket separately bound. Argv uses --state /state, /config/node-cert.pem, node-key.pem, client-ca.pem, launch-signer.pub and peer-policy.json, LAN19443. Preserve identity/keys/journal/floors/mounts through migration; software/CID provenance changes explicitly below. Historical500m/64MiB each/GPUfalse are limited offers, not physical totals.

Root536's one idle process restart per Node, same CID/image/eight hashes/fresh CP recovery06:49:35KST, and earlier UI30.167s/1811frames/0cardloss are historical bounded successes, not current unchanging health, renewal, OS reboot or signed P/C. PC2's successful warning-bearing restart must not be replayed. Current P_i/C_i, floor signatures, migration/renewal timestamps and all new runtime outputs remain null/NOT_RUN.

Protect Main3100 portalabb707 SSH57232 -> PC3loop13103/container54fb6609646d7f57991b1ee04de0454117e8e71fd525e5e1f87afb6d052483c0; API96 PC3loop8080/container8d62139c2408dff910bbfb3a9b322be56520705a3f3e967ce74563cfe9cd3f28; observerb8a2f8f55e524837c4b7db14565ec5f960c4492bc3b9df6972e7f1f153c2aec5; Main API SSH51072, observer DB reverse SSH11396, validation bridge SSH54896. No action occurs here. Future CP switching requires a separately released Root protected-service window and exact instance inventory, not automatic API/observer restart.

## F1: deadline fork and bounded release formulas

| Bound | Genuine input or explicit unknown |
|---|---|
| Peer-policy expiry E_policy | 2026-11-08T07:15:30Z = today2026-11-08 16:15:30KST |
| Node leaf expiry | 2026-11-09T07:15:30Z = 2026-11-09 16:15:30KST |
| CP-client leaf expiry | Same2026-11-09T07:15:30Z, now evidenced by Root538 public read below; active use still unproved |
| CA expiry A | 2026-11-14T07:15:30Z = 2026-11-14 16:15:30KST |
| Default48h leaf eligibility start | Derived2026-11-07T07:15:30Z = 2026-11-07 16:15:30KST; eligibility is not release |
| Reviewed frozen budgets B_N, B_M, B_Rpolicy, B_Rleaf | null; no invented duration, NOT_IMPLEMENTED |
| Normal/migration/recovery cut-offs and actual eligibility | null/HOLD until genuine inputs, bounded budgets, predecessors and release gates are proved |

E is the earliest actual applicable current authority expiry across every member's policy/Node leaf, shared CP-client leaf and CA, reattested by Root before release. Published earliest input is E_policy. L=min(actual Node leaves, actual CP-client leaf), known2026-11-09 16:15:30KST. No current P/C is inferred from historical P1/opaque hashes. The UI's advisory two-day summary covers DB Node leaves only, not peer/CP/CA authority ([summary][summary]); normal issuer safety-window eligibility is separate ([normal-prepare][normal-prepare], [normal-cli][normal-cli]).

**Latest normal release T_cutN = E - B_N - 630 seconds safety - 30 seconds clock skew.** B_N is a reviewed frozen upper bound for the ENTIRE remaining all-three normal protocol, five-site context barrier, durable settlement/readback and bounded retry/reconciliation. It excludes the separately reserved630+30 seconds. It is not an average, CI duration, developer estimate or unlimited retry allowance. Unknown B_N, authority/proof or unsettled predecessor makes T_cutN and eligibility null/HOLD. Future release must be strictly before the computed cut-off with prerequisites still valid. Nearness to expiry, developer approval, an eligible48h window or prepared artifact never authorizes starting or continuing.

Migration is mandatory. B_M separately bounds its entire handoff/settlement/reobservation, excluding normal renewal. **Latest migration release T_cutM = E - (B_M + B_N) - 630 seconds safety - 30 seconds skew**, and migration must settle strictly before T_cutN, leaving sufficient normal budget. Unknown either budget makes migration cut-off/eligibility null/HOLD. Code/CI/review/private preflight must already be ready; uncertain lead time is not hidden in an invented operating budget. Each phase must preserve a proved remaining completion bound. A missed cut-off cancels normal progression and selects the separately reviewed recovery branch even before E; no speculative migration consumes the margin.

Additional per-phase source bounds stay strict: fresh M2 age<=120s/future skew<=30s, before policy write remaining authority strictly>630s, safe integer/overflow and upper expiry bounds. Release adds30s conservatively; it does not weaken the per-write630s check. Overlap>630s and <=21600s, reference default14400s not selected; leaf TTL60..518400s capped at CA notAfter. Selected lifetimes/validity/operation times remain null ([phase-bounds][phase-bounds], [lifetime][lifetime], [issue][issue], [overlap-max][overlap-max]). No clock shift/backdate extends authority or the business approval.

### Deterministic post-policy-expiry state, even if nothing started

After current policy expiry CP mTLS handshakes fail closed: authorization re-reads policy, pins its floor, then checks expiry; requests reauthorize too. Heartbeat, snapshot, delivery and other protected calls become refused/unavailable, not healthy or successful observations. This is expected authority-expiry refusal, not proof of a faulty Node or failed login. A process may still exist; genuine last-good UI becomes stale/unknown/unreachable, never invented zero/healthy telemetry or new observedAt. CP /healthz may remain healthy for CP liveness while Nodes are unreachable: Gateway health is not Node authority/health or admission ([trust-policy][trust-policy], [trust-authorize][trust-authorize], [node-handler][node-handler]).

NewAuthority calls policy() at startup; an expired policy fails run() and exits1. **No current Node restart, Docker restart, reboot, image migration or normal-protocol restart after expiry under unchanged authority.** Do not stop a preserved process to try again. Unexpected crash/automatic restart failure requires Root observation and HOLD, not a retry loop. Preserve keys/CA/signer custody, C/P floors, journals/identity/locks/archives, mounts and original evidence. No reset/delete/chown/reenrollment. Missing serving PID means no ordinary live M2; no helper/quiescent hash substitutes ([startup][startup], [exit][exit], [same-exe][same-exe]).

| Time/state | Next development contract; operation stays HOLD |
|---|---|
| Before cut-offs, valid authority, proved budgets/gates | Required migration then normal adapter, separately reviewed/released; R2 authorizes neither |
| Cut-off missed but peer policy not expired | No speculative normal start/continuation; freeze state and select/prepare expired-current-authority contract, no early bypass |
| E_policy <= now < L, including zero work started | FLEET5-EXPIRED-CURRENT-AUTHORITY-FORWARD-RECOVERY-CONTRACT-R1, policy-expired branch; leaves may be date-valid but peer authority is unavailable |
| L <= now < A | Its explicit expired-leaf re-issuance branch needs stronger reviewed same-CA evidence and separate implementation/release; no old live M2/TLS assumption |
| now >= A | Same-CA issuance/renewal/recovery impossible; distinct authority-replacement workflow outside scope, never legacy init/reset/repin |

Expired-current-authority card: finite security/recovery work, owner Codex, actual Claude reviewer after exact code/hosted proofs. Cover expiry before any migration/normal work, partial migration and partial normal publication without requiring a nonexistent old batch. Define distinct versioned custody/quiescent/no-serving-process recovery evidence, explicit authorization, authenticated preserved floor bounds, monotone P above that floor for newly published policy, independent C+1 CAS/audit and Node-owned signatures. Schema/version, authorization protocol, bounds, implementation and results are **NOT_IMPLEMENTED/null/HOLD**. Do not reuse the normal adapter unchanged or call expired/quiescent evidence live M2. Legacy expired-batch commands require their actual prior batch/authority; they cannot solve this never-started cohort ([normal-current-expiry][normal-current-expiry], [legacy-recovery][legacy-recovery]).

Policy-expired recovery intended to finish while leaves are date-valid has **T_cutRpolicy = L - B_Rpolicy - 630s - 30s**. Unknown/missed bounds or gates prohibit releasing that branch; explicitly redesign/review/release the expired-leaf branch. Its latest same-CA release is **T_cutRleaf = A - B_Rleaf - 630s - 30s**, also null/HOLD until proved. New leaves remain within CA notAfter and stricter phase bounds. At A, or with insufficient CA lifetime, same-CA recovery is impossible. A distinct future authority-replacement workflow requires new trust authorization and retained identity/journal custody; it is not permission to replace authority or reset state here ([issue][issue]).

## F2: required serving-binary/container migration predecessor

A new Go serving binary, reviewed image and new CID are **required**, not conditional. Deployed code rejects this CPU profile/split layout, and M2 requires os.SameFile(actual serving executable, observing executable) plus executable UID equal to journal UID. Both build Dockerfiles COPY /inv-node without --chown, leaving root-owned bytes while the cohort serves UID1000. A replacement helper cannot evade SameFile; live executable chmod/chown is not permitted ([same-exe][same-exe], [fixed-layout][fixed-layout], [remote-copy][remote-copy], [local-copy][local-copy]). Exact de654cd3 build provenance/descriptor metadata still require Root artifact/descriptor attestation; source recipes alone are not that attestation. Incompatible serving code itself already makes migration unavoidable.

Finite predecessor **FLEET5-CURRENT-CPU-SERVING-BINARY-CONTAINER-MIGRATION-R1**, owner Codex, actual Claude reviewer, proof groups P1-P7 below plus separate Root private preflight/operation release. Support exact UID1000 CPU split-bind layout while retaining SameFile, actual PID/start identity, owned descriptor/journal and no initialization fallback. Operate only before T_cutM under valid authority, or under the separately implemented/reviewed/released expired-current-authority contract. R2 does neither.

| Freeze boundary | Frozen identity/provenance and required settlement |
|---|---|
| M0 pre-migration evidence | Freeze historical old CID/image tuples, actual binary/source/provenance, same NodeID/tenant/epoch, public keys, CSR key continuity, actual journal/floor/identity hashes, mounts/UID/endpoints and no active work. This is NOT an unsupported old-binary live M2. Required migration evidence version/authorization remain NOT_IMPLEMENTED/null. |
| M1 authorized artifact preparation | Freeze immutable old->new source/build/CI/artifact/executable/image provenance and migration contract; new binary/image/CID fields remain null until real operations. Root must approve exact process/port handoff and single-writer fencing; retain state/keys/mounts and reject substitutions. No in-place binary/image mutation or reenrollment. |
| M2 handoff under its own released contract | Fence/quiesce exact old container, prevent concurrent journal writers/blind autorestart, preserve custody/state, then create/start reviewed new container on SAME Node identity/keys/journal/floors/mount semantics. A new CID is expected software provenance, not a new Node. Distinct quiescent/custody transition evidence is not implemented; no fake old M2 or silent floor reset. |
| M3 migration settlement | Prove old writer fenced, new actual serving PID/executable/UID/mounts/key continuity, durable identity/floors retained except explicitly reviewed monotone effects, exact immutable migration receipt, genuine authenticated heartbeat/resource readback and protected dependencies. Settle ALL3; no normal batch while any migration is uncertain/expired. |
| N0 normal pre-floor | AFTER all migration settlement/reobservation, obtain fresh independently nonced M2 from each NEW actual serving binary. Freeze new executable/image/CID tuples with the exact normal proposal; starting P_i/C_i independently observed. |
| N1 through retirement | No executable/image/CID/membership/key/epoch/mount drift mid-batch. Install/final acknowledgements compare executable digest to pre-floor; drift fails closed. No migration hidden in renewal retry. Retain old provenance/receipts. |

These executable comparisons make ordering mandatory ([same-exe-install][same-exe-install], [same-exe-final][same-exe-final]). The universal old-CID/image freeze is replaced: old tuple before migration, explicit linked old->new tuple during handoff, settled new tuple before normal pre-floor. Same Node identity does not mean CID never changes. Before migration mutation, abandon leaving old process/state untouched; after writer/authority transition, no automatic old-CID restart or journal snapshot restoration. Migration's forward/crash recovery and necessary expiry branch need their own reviewed proof/release.

## F3: exact five-site CP context inventory and switch barrier

Each NodeTLSClient loads SSLContext/CA/client leaf/key at construction. Atomic file replacement does not update retained objects ([tls-context][tls-context]). Every present instance from ALL five sites must be inventoried/included, or have bounded Root absence proof. Current active-context attestations remain null; this worker performs no live process/config inventory. Historical observer/API presence does not attest which certificate a retained object currently uses.

| Constructor at API96 | Source caller/lifetime | Required Root proof / future launch rule |
|---|---|---|
| [observer_worker:58][ctx-observer] | Observer main constructs ObservationWorker once; repeated5s loop or --once process retains context | Exact process/container/config-handle/public-cert binding, start/provenance and transition acknowledgement, or absence; future launches bind accepted credential publication |
| [worker:122][ctx-delivery] | Worker main constructs NodeDelivery, retained by DeliveryWorker loop/--once | Inventory execution delivery instances, not just API; no real Run to test switch; later starts reject stale publication |
| [workspace_config:54][ctx-workspace] | configured_workspace constructs RestrictedWorkspaceRuntime; [API startup][caller-workspace] calls when workspace configured | Every retained runtime/client in every API worker/process, or absence; later factory invocation must bind current accepted credentials |
| [build_product_runtime:537][ctx-build] | configured_tenant_product_runtime creates quarantine client retained in NodeAgentReceipts/BuildProductRuntime; [worker optional startup][caller-build] calls factory | Every enabled product instance or absence, and future product/CLI invocation. API [admission import][caller-build-api] alone proves neither this TLS instance nor a sixth constructor |
| [storage_check_collect:381][ctx-storage] | configured_storage_sample_collector constructs StorageCheckCollector; [optional API composition][caller-storage] retains it | Collector instances or absence; later configured collection binds accepted credentials before serving, without inventing Node storage capability |

Root must enumerate actual instances/replicas per site, public active certificate/pin provenance, lifetime, pending requests and launch/config control points without secrets. Source feature flags, unused constructors or no observed requests do not prove deployment absence. Every present cached object must acknowledge the same frozen CP public-leaf publication; new starts must not load stale publication. Unprovable complete inventory means switch HOLD.

Future barrier: journal exact publication bytes and active/absent instance evidence, safely quiesce/drain/fence old in-flight contexts, publish new shared leaf with retained CP key, construct/rebind every present context and prove actual new handshakes to all staged Node channel pins. This is a reviewed coordinated transition, not instantaneous atomic mutation across processes. Only after all acknowledgements AND launch-time stale-context guards may P+2 drop old fingerprint. Unknown generation/failed switch stays HOLD/forward reconciliation; never fabricate health or widen allowlists. P5 below covers all five sites, replicas and future/CLI construction.

## F4: new public CP leaf evidence, limited claim

Root538 receipt/program pinned in R2 establish Root's exact PC3 public pki-r1/cp-client-cert.pem read at2026-11-08 07:52:28KST, UID1000 bounded regular file, DER SHA25648911c5ddf7d12f05b9866feea0f0005c193d76a956274e2510492d0c2f76481, expected CP SPIFFE URI, notBefore2026-11-07T07:10:30Z/notAfter2026-11-09T07:15:30Z/dateValidAtRead=true ([actual receipt][cp-validity]). No private key, new context/handshake, file/process mutation; X509 parsing was on PC3, not Main. This supplies missing public expiry evidence for delta review. It does NOT attest active use at any of five sites, future validity or a new TLS connection. R1 F4 remains historical; independent closure is pending actual delta review.

## Preserved normal contract and stop rules

Normal all-three renewal remains unavailable as-is until mandatory migration/adapter gates settle under the correct deadline branch. Retain SAME Node/CP/CA/launch keys, NodeIDs, epoch, membership, project grants/resources, mounts, isolation and journals. Node owns CSR/M2/install/final signatures; Root may not author Node attestations. CP signs its own real commit/archive. Existing single dedicated CA cannot satisfy generic two-chain issuer through a fake intermediate, doubled chain, repin or generic verifier relaxation ([issuer][issuer], [normal-current-expiry][normal-current-expiry]). Private handles, actual nonces, selected next cert/policy bytes and receipts stay null.

| Future operation | Actual contract/guard; all NOT_RUN here |
|---|---|
| Root preflight | Genuine scoped GET nodes/node-certificates/resource-usage/capacity and waiting Run under existing principal/project; Root-only READ ONLY C/epoch/DER/endpoint/enabled/audit queries and owner-visible no-work proof, never RLS-hidden false zero. Summary is not signed P/current CA/client context ([API reads][api-reads], [Run read][run-read]). No credentials/DSNs/tokens in docs. |
| Technical probe | CP mTLS TLS1.3 POST /v1/heartbeats with exact NodeProbeInput nonce64 hex. Snapshots/delivery keep genuine contracts. Probe persists CP observation records and Node authorization may pin a floor, so it is an operating action, not worker SELECT or renewal endpoint ([probe][probe], [node-handler][node-handler]). |
| Fresh pre-floor/prepare | Local exclusive inv-node --observe-peer-policy-floor, not HTTP; Node key signs actual serving PID/executable/cmdline/journal/floor/DER/nonce. Only new settled binary can satisfy current cohort. Exactly all3 same-key CSRs, unrevoked pinned current authority, fresh M2s/locked registry; freeze stable operation ID and exact public proposal bytes, no invented HTTP Idempotency-Key/new operation after uncertainty ([floor-cli][floor-cli], [floor-sign][floor-sign], [normal-prepare][normal-prepare], [batch-prepare][batch-prepare]). |
| Install/stage | Fsync forward-only publication intent BEFORE public writes, same-filesystem per-file replacement in stable bind directory, actual container-view verification/signed post-floor/install receipt; THEN restricted operator CAS C_i->C_i+1/audit, DER-derived pin, exact epoch/endpoint. Browser/runtime cannot provision; fresh admission is not renewal ([install][install], [cas][cas], [fresh-collision][fresh-collision]). |
| Switch/final/retire | Stage all3 Node pins before shared CP context barrier; only exact signed CP commit permits final P_i+2. Each Node signed finalization/no-overwrite archive, then all unique attestations/CP retirement/fresh actual readback ([batch-commit][batch-commit], [final][final], [retire][retire]). |

C_i/P_i independent monotone domains: overlap P_i+1/final P_i+2, channel C_i+1 CAS, safe integer/overflow bounds. Never infer P from C, restore lower/same-version-different-hash policy, decrement DB version, reset floor or replace epoch/identity ([versions][versions], [journal-floor][journal-floor]). Node pins before expiry validation: even failed connection may advance P. Missing receipt, nonzero exit, timeout or old date-valid leaf cannot prove no mutation.

Atomicity remains per-file, not multi-file. Future implementation must validate owned regular nonredirected files/directories, bounded descriptors/dev/inode/UID/modes/hashes, reject links/TOCTOU/unknown .next/history residue, use exclusive operation locks/single journal writer, fsync temp data then same-filesystem rename/parent fsync, preserve stable mount source and verify actual container view. Do not replace mounted directories wholesale or clear foreign staging. Unknown publication/CAS/process outcome requires Root readback and original immutable operation/proposal/receipt bytes before bounded exact replay. Fresh observation nonces cannot rewrite prior evidence; image/executable drift requires separate migration ([atomic][atomic], [same-exe-install][same-exe-install]).

Before any publication/authority/writer mutation, abort with no rotation: leave active bytes/services/keys/journals untouched, preserve staged evidence. Once intent/irreversible floor/CAS may exist, old restoration is forbidden; preserve phase and forward-recover only through reviewed still-valid contract. Expiry/no serving process selects expired-current-authority contract even when nothing started. Legacy init/enroll/reset/old-renewer/force cannot bypass it ([rollback][rollback], [legacy-recovery][legacy-recovery]). GetCertificate reads the current leaf dynamically and policy is reread, but Node CA roots and CP SSLContext load once; preserve reviewed restart/reload/ack semantics rather than assume new hot reload ([trust-tls][trust-tls], [tls-context][tls-context]).

## Proposed dependency DAG and single implementation proof matrix

All future cards are NOT_IMPLEMENTED/null/HOLD, owner Codex, actual independent Claude after exact code/affected hosted CI, Root private preflight and separate explicit operating release. R2 actual delta review precedes them. This finite task corrects the plan; no full-feature or optional-Low loop is requested.

```text
R2 -> actual Claude delta -> Root selects real time/authority/budget branch
  valid authority + proved T_cutM:
    migration + normal-adapter CODE/CI/review + frozen B_M/B_N ready
      -> separately released migration (settle/reobserve all3)
      -> separately released CURRENT-CPU-COHORT-RENEWAL-ADAPTER-R1 operation
      -> fresh new-binary pre-floor -> normal all3 -> retirement
  missed cutoff / expired peer (before or during any work):
    EXPIRED-CURRENT-AUTHORITY-FORWARD-RECOVERY-CONTRACT-R1
      -> distinct reviewed implementation/evidence/release
      -> explicit migration component under that contract
      -> policy-expired completion before L,
         or separately released expired-leaf same-CA branch before A
  CA expired / insufficient same-CA budget:
    AUTHORITY-REPLACEMENT workflow (out of scope; new trust authorization)
```

Full card IDs have prefix FLEET5-CURRENT-CPU- for migration/normal as named above, and FLEET5-EXPIRED-CURRENT-AUTHORITY-FORWARD-RECOVERY-CONTRACT-R1 for recovery. Migration must settle before normal pre-floor. Normal adapter implementation/review and B_N must already be ready before migration operating release; the arrow does not authorize migration while later code/budget is missing. The exact future serving binary is frozen before that release; any later required binary change requires a new settled migration before normal pre-floor. Expired contract defines its OWN migration/authority ordering/evidence; normal migration/adapter cannot be reused unchanged there. DAG arrows are dependencies, not execution or authority.

| Required proof group, once per affected implementation scope | Hosted evidence/review prerequisite to Root release |
|---|---|
| P1 serving/migration | Actual Go current-profile M2/signature on NEW actual serving binary; wrongPID/start/executable/UID/layout/nonce/journal negatives, SameFile preserved; immutable old->new source/build/image/CID provenance, key/identity/journal/floor/mount retention, single writer, bounded crash/uncertain migration. Old unsupported/quiescent metadata is not live M2. |
| P2 Linux isolation/atomicity | Real Linux Docker UID1000 ROconfig/RWstate publication/view visibility/key custody, mount/link/TOCTOU/owner/path/residue refusal, per-file/fsync/journal kill points; no production chown/Main tests. |
| P3 authority continuity | Exact existing singleCA/key/EKU/SPIFFE/IP/expiry/revocation validation; wrong/extra-chain/key/revoked/expired refusal, no generic verifier weakening; real independent current P/C authentication/limits. |
| P4 time/protocol/recovery | Two complete real three-member fixture cycles, independent P/C, cutoff boundary/per-phase expiry, CAS races, duplicate/stale/missing receipts, bounded unknown/crash/retry and irreversible-floor rollback refusal; isolated fixtures are not real people/hardware votes. |
| P5 all CP contexts | Five constructors/replicas/active-or-absent controls, publication/drain/rebind acknowledgements and old-context refusal, future/CLI constructors bind accepted credentials/reject stale ones; no absent-site assumption or old-context success after final policy. |
| P6 distinct recovery evidence | New versioned migration/quiescent/expired/no-serving evidence/authorization for never-started, partial migration/normal cases; no fabricated PID/M2. Policy/leaf cutoffs and CA-terminal refusal. Schemas/bounds/signature protocol NOT_IMPLEMENTED, not presumed solved by this matrix. |
| P7 delivery/release | Exact affected hosted Go/Linux/contract/source gates/artifacts, one actual Claude review, Root custody/live inventory/finite budgets/explicit release; settle migration before pre-floor. Docs CI/review/time pressure alone never releases operations. |

## Finding dispositions and finite handoff

| Actual finding | R2 correction / section and manifest association | Independent status |
|---|---|---|
| F1 MAJOR mandatory | Deadline formulas/reserved migration budget; expiry-before-start/in-flight HOLD and policy/leaf/CA forks. Manifest deadlineFork, tasks.expiredRecovery | Corrected proposal; actual delta pending |
| F2 MAJOR mandatory | Required new Go/image/CID predecessor, phase-specific old->new/new freezes and migration-before-pre-floor. Manifest tasks.migration, phaseIdentityFreezes | Corrected proposal; actual delta pending |
| F3 MODERATE | Five constructors/callers/lifetimes, Root active-or-absent proofs, future constructor and switch guards. Manifest clientContexts[5] | Corrected proposal; actual delta pending |
| F4 MINOR | New Root538 public DER validity/program pins; historical R1 gap retained, active-use claim excluded. Manifest publicCPClientValidity | Evidence supplied for actual delta, not self-certified closure |
| F5 MINOR | COPY remote:11/local:2 corrected, full-SHA permalinks/range coverage including five sites/callers; actual deployed-image provenance still Root future attestation. Source-contract-map and citation coverage | Corrected proposal; actual delta pending |
| F6 MINOR | CA-terminal refusal; separate authority replacement out of scope. Manifest deadlineFork.caTerminal | Corrected proposal; actual delta pending |

R2 finding-dispositions.json records exact section/manifest/source pins. Metadata verifies every Markdown permalink blob/range, not just paths on this branch; no metadata check closes independent findings or proves runtime.

Six immediate-exit metadata gates: docs/ontology/path-ratchet at exact a3c6984fa25c6cf179827e15e4259000e7bd294e/single-ratchet/sync CHECK/diff. Normal scoped commit/push, exact unique-correlation Docs workflow_dispatch attempt1/all19. Entire canonical start/end/postCI must remain587290B/SHA256a59e836f1e826231ddfee3a3be5bb247dd4a9b018c24a9d809104e9ef2c5b5e4. Root alone resumes APPLY after author exits/releases. No apply/export/canonical write or Main/remote/product/crypto/browser/DB/Docker action. Named R2 postCI receipt outside final commit is Root-ready/untracked; raw CI bytes use base64 JSON with size/hash, not whitespace log Git additions.

First next owner/action: Root verifies exact R2 source/Docs/input/state proof, publishes only delta, gets one actual Claude bounded review, then assigns required implementation branch appropriate to real authority/time/budget. All new operation values null/NOT_RUN/HOLD. Genuine Run run_01M6VXSMM9SV8MAB7K4B1YCRX8 last reported awaiting_approval/v4/attempt0; apr_01M6VXSPZ0252M2SJ8ZA5E11QE expired06:24:26KST, real two distinct nonrequester actors absent; no votes/enqueue/newRun/execution. PC1fixedkey255, PC5Main94.58%RAM/unadmittedNode, fullGPU/storage/manual/all5/physicalOSreboot remain. CR90501/CR-CSP02 CLOSED. Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN; wholeProgramCompletefalse.

[summary]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/node_certificates.py#L14-L38
[normal-prepare]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/tools/lan_pilot.py#L3282-L3377
[normal-cli]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/tools/lan_pilot.py#L4136-L4183
[phase-bounds]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/deploy/lan/peer_policy_phase.py#L11-L175
[lifetime]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/tools/lan_pilot.py#L2055-L2136
[issue]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/tools/lan_pki.py#L42-L77
[overlap-max]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/deploy/lan/worker_leaf_rotation.py#L72
[trust-policy]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/transport/trust.go#L50-L93
[trust-authorize]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/transport/trust.go#L102-L131
[node-handler]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/transport/server.go#L55-L139
[startup]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/cmd/inv-node/main.go#L94-L115
[exit]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/cmd/inv-node/main.go#L21-L25
[same-exe]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/runtime/peer_floor_linux.go#L36-L102
[fixed-layout]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/runtime/peer_floor_linux.go#L107-L199
[normal-current-expiry]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/tools/lan_pilot.py#L1564-L1589
[legacy-recovery]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/tools/lan_pilot.py#L2303-L2348
[remote-copy]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/deploy/lan/Dockerfile.node.remote#L11
[local-copy]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/deploy/lan/Dockerfile.node#L2
[same-exe-install]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/deploy/lan/worker_plain_rotation.py#L75-L94
[same-exe-final]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/deploy/lan/worker_plain_rotation.py#L170-L243
[tls-context]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/node_transport.py#L61-L79
[ctx-observer]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/observer_worker.py#L42-L81
[ctx-delivery]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/worker.py#L111-L160
[ctx-workspace]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/workspace_config.py#L12-L68
[caller-workspace]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/app.py#L1340-L1344
[ctx-build]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/build_product_runtime.py#L503-L546
[caller-build]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/worker.py#L127-L140
[caller-build-api]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/app.py#L1381
[ctx-storage]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/storage_check_collect.py#L350-L388
[caller-storage]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/app.py#L1405-L1420
[cp-validity]: https://github.com/egparadise/SaintVision-Invion/blob/03f6ea0a2c6cf83074cfa71850892ba4a1873ae5/docs/vault/30_Development/Evidence/fleet5-20261105-root/current-three-node-renewal-plan-actual-claude-r1/root-public-cp-client-validity-r1/receipt.json#L1-L22
[issuer]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/tools/lan_pilot.py#L397-L433
[api-reads]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/app.py#L719-L741
[run-read]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/app.py#L513-L532
[probe]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/observation.py#L15-L25
[floor-cli]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/cmd/inv-node/main.go#L55-L70
[floor-sign]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/transport/peer_floor.go#L22-L86
[batch-prepare]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/tools/lan_pilot.py#L2997-L3040
[install]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/deploy/lan/worker_plain_rotation.py#L95-L190
[cas]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/node_channels.py#L151-L202
[fresh-collision]: https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/fresh_cpu_admission.py#L208-L221
[batch-commit]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/tools/lan_pilot.py#L3540-L3710
[final]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/deploy/lan/worker_plain_rotation.py#L191-L265
[retire]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/tools/lan_pilot.py#L1962-L2030
[versions]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/deploy/lan/peer_policy_phase.py#L87-L98
[journal-floor]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/runtime/journal.go#L339-L391
[atomic]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/deploy/lan/worker_leaf_rotation.py#L466-L499
[rollback]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/deploy/lan/worker_plain_rotation.py#L264-L265
[trust-tls]: https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/transport/trust.go#L133-L154
