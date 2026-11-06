---
doc_id: "HISTORY-FLEET5-20261106-K2A-TRUST-HISTORY-CODEX"
title: "FLEET5 K2A trust history bounded implementation"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude through Root; actual code review pending"
updated: "2026-11-06T13:59:21+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "4ce63e8ee78d957aa91e813f6ee226cc21abb52a"
task_ids: ["FLEET5-K2A-TRUST-HISTORY-20261106"]
tags: ["fleet5", "codex", "readonly", "trust", "implementation"]
---

Same actual Orca task_a95ef3d8ccce / ctx_ed23b4a777d0, amended bounded scope in
Root msg_18271633c26c after actual fe7e1ea03c2862fce305fb617a4d5782fe9c0d48
review/Docs42158896721. Verdict is bounded design acceptance for K2A trust/history
readiness only; D-OBSERVATION Medium remains separately OPEN and is not a code
predecessor. Completed K1 task remains closed.

Orca worktree fleet5-k2a-trust-history-20261106 identity
af2147c9-d871-427d-872f-9ca009ce609b, branch
agent/codex/fleet5-k2a-trust-history-20261106 starts at exact4ce63e8e.
Allowed product path is services/node-agent/internal/migrationcontext only, plus
its tests/README and this unique History/Evidence. Existing K1, source28 pins,
wire/descriptors, go.mod/go.sum, workflows, shared boards/registry/ADR/source
originals and old refs/cache remain frozen. No helper agents or operational work.

Actual canonical Root read at implementation start: Index1.0.437/Codex1.0.398,
governance1.0.6, after task-start reference aed226c2/436/397. Its new implementation
scope section was read. agent-delivery1.1.0/core-reliability1.0.0 apply; existing
main Python3.14.7 and local Go1.27.0 are used without dependency/toolchain installs.

Scope: closed readonly registry/history/status/clock/running-code ports with
production ports NULL/default-refusal, checked private DTO construction and
LoadInstalledPolicy/ReadHistory/ValidateHistory. No current API or placeholders,
K2B interfaces, nonce/signing/Engine/SSH/DB/journal/lock/tempfile/entrypoint/
self-measurement/installation implementation. Repo-wide Go boundary and whole
package AST/types underlying-type gates, meaningful synthetic checks, new exact
Core/Docs and one actual Claude code review are required before delivery.

Actual authentication-source bindings, installed roots/custody/CA, clock/stdlib
match and all A01-A40 remain null/HOLD/NOT_RUN. An unchecked port record, hash,
role label or boolean must not become trust. Missing external attestation formats
are not silently invented as accepted wire. The old g2-planning-policy proof
does not itself install/authenticate a full registry.

Root actually answered the concrete proof-format question in msg_f4259ea0de6b:
CHOOSE A, narrowing the earlier grant. No positive production authentication or
new signature format/domain/ABI is granted. All unregistered provider records
refuse, including internally consistent/self-signed records. This is a read-only
boundary and refusal slice, not a usable positive K2A authenticator. Its private
already-bound synthetic test fixtures deliberately bypass missing external auth
solely to test downstream copy/bind/selector/status/clock/K1 logic.

Actual implementation: closed null ports, no-argument service, private opaque
policy/history bindings and public LoadInstalledPolicy/ReadHistory/ValidateHistory
default refusals. Pure functions freeze all mutable fields, reject arbitrary JSON
marshalers/callbacks, check original plan operation/HELD/fence/containing facts,
necessary provenance/executable/review/DER/C2 joins and structured clock/status
bounds. The sole new K1 importer/constructor is k1_bridge.go. Current/effect APIs,
positive production opaque issuers and all I/O/provider implementations are absent.
The interval evaluator does not observe a clock or perform real final TOCTOU
readbacks; actual clock/stdlib mechanism remains HOLD.

At 13:30:47-13:32:06 KST, serial local Go1.27.0 focused new-package plus existing
K1 suites and vet exited0. The local race command exited2 before execution:
CGO is disabled, so race is NOT_RUN locally; no CGO/compiler/environment mutation
or retry was performed. A fresh exact hosted Core race job is mandatory before
bounded delivery. Actual commands/logs/exits are preserved in the unique Evidence,
including the initial missing-brace gofmt2 and module-pathspec source-gate1
authoring failures and their fixes. New tests later added for status boundaries
require the final focused rerun below before commit.

Whole-package actual Go parser/types census covers12 non-test K1 files with actual
dependency export data, no source/type stubs:13 reachable local input types,
73 fields,0 embedded. It compares full underlying named/alias/map/slice/function/
interface/generic shapes and deterministic cycles to immutable eb32 under the same
actual toolchain. G01-G08, type-correct named map/slice/function R01-R03 after
simulated raw repins, and a cross-file generic mutation are detected. Repo-wide AST
boundary covers both first-party modules/all platform files; immutable K1
definitions are separated from the sole new bridge. The synthetic crypto history
passes identical L/U/t0 full reports with195 records/112 proofs/227 signatures per
evaluation, using an expired original operation absent from live context. The
fixture contains no private keys and is not a real K2 producer/authentication proof.

Next: final scoped tests and required documentation/sync gates; commit/push and
fresh exact Core+Docs, then one actual Claude code/boundary/census review through
Root. Actual CI/review remains pending, all real bindings/clock/installation/
prepublication/current/effect work remains HOLD/ABSENT and A01-A40 remain NOT_RUN.
No five-PC/whole-program completion is claimed. D-OBSERVATION Rev3 is a separate
later contract correction, not a predecessor or implemented interface here.

Final scoped Go checks at13:35:37-13:35:52 KST exited0: new package 11 top-level tests and 24 subtests, then vet0. The unchanged existing K1 suite previously passed in the same serial local run. Local race remains NOT_RUN/CGO-disabled command exit2; fresh hosted Core remains required.

At13:36:50-13:38:20 KST all10 required documentation gates exited0, including
canonical read-only sync --check --state. Before/after state SHA256 is
d0b82b21910faf1f4c6e08896173138f790a5ae8aad37d5898468715b26cf66a, unchanged; no apply/adopt/resolve.
The subsequent pre-archive scope/original-selector guard and negative test were
verified by scoped new-package tests and vet at13:39:49-13:40:04 KST, both exit0.
Final local source evidence is local-go-final2-results.json; no frozen K1 source
or earlier accepted worktree/ref was changed. Fresh candidate CI and independent
code review remain PENDING until actual immutable results are received.


## Actual de71 CI failure and external scope boundary

Published source candidate de71c07c2b827eea50e2ca660f80d042334472c7 on own branch.
Core42164071724/attempt1 failed in core job127716312318, step Run provisioned LAN
installer acceptance: tests/integration/test_workspace_upgrade.py::test_real_upgrade_preserves_credentials_journal_and_replays
raised Owned container/state changed during actual floor observation at
worker_peer_floor.py:217, with1 failed/16 passed. Later main pytest/build steps
were SKIPPED, not success. S01 job127716312164 succeeded. Docs42164075078/job127716312780
succeeded with all required steps. Root msg_1e5eb53d0056 confirms
ACTUAL_CI_FAILURE_NO_REVIEW; no independent code review/acceptance has started.

The earlier actual hosted Go race step succeeded. Its exact artifact records
new-package11 top-level/24 subtests passing,0 package failure events and0 whole-Go
failure events. This replaces the local race NOT_RUN gap only for the actual
hosted source test, not for overall Core or installed/runtime authentication.
Core evidence artifact13478861491 ZIP SHA256
9e4152c8c6b0bb981b7fa8e8befcf348d067f685c5a042bff7b38a8ba8d65bd9 matches
GitHub digest. Raw ZIP/logs remain ignored .work/de71-ci-failure, not exported.
Only aggregate safe metadata/source pins are published in de71-ci-failure-analysis.json.

Failing helper and test bytes are unchanged between eb32,4ce and de71; exact
SHA256 pins are in that analysis. The failed barrier compares container identity,
image/config/raw Mounts/start/restart fields plus full volume metadata and exact
consumers across two real CI Docker reads. The logs do not record the two snapshots,
so the specific differing field is UNKNOWN. Adjacent context normalization sorts
Mounts and excludes CreatedAt, a concrete separate diagnostic candidate only;
no harmless-metadata assumption, guard relaxation or actual live-fleet failure
is inferred. Both failing source paths are outside the package-only grant.
No outside source edits, environment mutation, blind Core rerun or helper worker
was performed. First next action: Root assigns a separately scoped diagnosis/fix
or an exact combined integration plan; bounded delivery and all-code review stay
pending until actual required CI/review evidence exists.

Failure-report documentation gates at13:57:43-13:58:28 KST all10 exited0; fresh records are in de71-failure-report-gates, preserving the original source gate files byte-exact from de71. Canonical sync before/after SHA2562442c54fbc3bf9582a55073aed82082019c6543bf9f46dd62300a72a7330cc53 is unchanged for this check; no apply/adopt/resolve. Product/test/workflow source remains exactly de71; this report does not claim Core acceptance or code review.
