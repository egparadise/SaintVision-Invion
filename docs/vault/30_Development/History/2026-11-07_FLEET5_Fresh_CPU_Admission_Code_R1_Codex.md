---
doc_id: "HISTORY-FLEET5-20261107-FRESH-CPU-ADMISSION-CODE-R1-CODEX"
title: "FLEET5 fresh CPU admission four-file source candidate"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Actual independent Claude through Root pending"
updated: "2026-11-07T13:35:08.492138+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "7033778ad3d2bc284e36f7e29be7597dbb7d9f23"
task_ids: ["FLEET5-FRESH-CPU-ADMISSION-CODE-R1-20261107"]
tags: ["fleet5", "cpu", "metadata", "wip", "not-executed", "hold"]
---

SAME Task `task_a95ef3d8ccce` / Dispatch `ctx_ed23b4a777d0`. Codex owner;
actual independent Claude review through Root pending. Finite Root grants
`msg_e716b2cba047` and bounded-public-stdin clarification `msg_5fa2d17d863e`.
The original WIP was UNCOMMITTED, not a source publication, executed test result, operator
procedure, installed trust, admission grant or FIVE acceptance. The broader K2
Task stays open. No worker_done is justified by this WIP.

Branch `agent/codex/fleet5-fresh-cpu-admission-r1-20261107` starts from exact703,
whose direct parent is accepted6d7. This branch was switched normally in the
existing Orca-managed workspace. Root's dependency703 source verification and
Docs42335285577 success are reported evidence; Core42335287638 and
Backend42335289761 still require Root's actual disposition. No completed prior
proof/CI was rerun. Index1.0.503/Codex1.0.464 working pages were read from the
canonical Root vault, updated13:06:44KST; raw hashes/frontmatter are preserved in
`../Evidence/fleet5-fresh-cpu-admission-code-r1-20261107-codex/required-doc-read-bindings.json`.
AGENTS and agent-delivery1.1.0/core-reliability1.0.0 apply; missing ROOF/Graph/agent
build version values stay UNKNOWN. Root manages shared progress boards.

## Goal, evidence and ownership

The bounded goal is a generic operator-only metadata writer for a fresh CPU Node
in an already selected tenant/project/current recovery epoch. Acceptance requires
real mandatory disposable-PostgreSQL tests, exact source CI and independent
review later. Codex owns the four-file candidate; Root owns the dependency703
disposition, isolated runtime test grant, publication grant and actual review
request. Root separately owns any private request/CA/custody/physical bindings.
None is inferred from public source or previous device observations.

Only four NEW code/test paths are candidates: `services/control-plane/src/inv/fresh_cpu_admission.py`,
`tools/fresh_cpu_admission.py`, `tests/core/test_fresh_cpu_admission.py` and
`tests/core/test_fresh_cpu_admission_cli.py`. Existing product/test files are
unchanged. Old H12 History modification and untracked post-CI evidence were
already present and are excluded, preserved and not staged. No shared board,
registry, schema, workflow, source original, old pilot or protected state changed.

## Public request and authority boundary

Request v1 has EXACT keys: `requestVersion`=1; canonical UUID `tenantId` and
`recoveryEpoch`; Crockford `projectId` prj_26, fresh `nodeId` nod_26 and distinct
`cpuResourceId`/`memoryResourceId` res_26; explicit HTTPS `endpoint`; inline
`certificateDERBase64`; integer `expectedTenantControlVersion`; `cpuMillis`=500
and `memoryBytes`=67108864. Input is UTF-8 JSON from stdin bounded to128KiB;
canonical base64 decodes to at most65536 bytes. Duplicate/unknown keys, wrong
shapes/types, bool-for-int, nonfinite numbers, noncanonical IDs/base64 and
out-of-profile values refuse before any DB work. No force/reuse/operator field.

The unchanged `endpoint_parts`, `certificate_identity`, `NodePrincipal` and
`provision_channel(expected_version=0)` contracts are used. A public leaf proves
its precise tenant/Node/epoch URI, server EKU, non-CA bit and current validity
under that helper. It DOES NOT prove issuer chain, operator authorization or CA
custody. Output explicitly says `certificateIssuerChainVerified=false` and
`executionAuthorized=false`. Synthetic self-signed test leaves do not become
production trust. No product key/CA/signer generation or trust installation.

Actual current-role INSERT rights on nodes/resources/project_nodes/channels/audit
and schema USAGE are checked through PostgreSQL catalog privilege APIs. Runtime
inv_kernel and business inv_app lack the needed rights; a caller boolean or role
label cannot grant them. Every business row query/write carries tenant scope and
its Node/project/resource scope. Freshness uses the actual composite-PK tenant
identity namespace, not an invented global cross-tenant ID reservation.

## Transactions and state

PLAN is default: public input validation plus SELECT-only DB preflight. It is an
observation, not a durable reservation or apply grant. Its deterministic SHA256
binds the canonical derived plan, including selected IDs, exact leaf hash/expiry,
endpoint, version and fixed profile. APPLY requires `--apply` and the exact lower
case `--expected-plan-sha256`; all validations and DB preconditions repeat.

Only an idle caller connection is accepted, so an outer uncommitted savepoint
cannot yield a COMMITTED receipt. APPLY owns one transaction and locks existing
control_epoch, tenant, project and tenant-control rows FOR SHARE. It checks the
expected epoch/version; an existing business_projects link must be enabled and
its same-tenant public project active. No A/B translation or grant changes.
Kill switch true permits metadata insertion but is preserved with control
version/timestamp. Existing target Node, resource, association, channel or audit
causes conflict/HOLD. No repair, reset or idempotent upsert is exposed.

Atomic writes are one offline Node, CPU+memory resources with capacity=offered
500m/67108864, one enabled selected-project membership, then unchanged channel
provisioning at version1 plus immutable audit. The existing schema's AFTER INSERT
node trigger additionally seeds a NEW version0 node_controls row; this is
explicitly verified, not an update of any old control. Exact rows and unchanged
tenant-control preimage are read back before outer commit. COMMITTED is returned
only after commit acknowledges. No snapshot/probe/Run/lease/approval is created;
offline metadata contributes no schedulable capacity before real observation.

Unique collision and DB errors roll back without retry. A lost commit response
is UNKNOWN and requires read-only reconciliation and operator disposition. The
separate library reconciliation API uses one read-only repeatable-read snapshot,
checks operator rights/current epoch/control version and exact metadata. It never
retries APPLY; absence/mismatch/current invalid certificate stays HOLD. A metadata
match does not prove which attempt committed or authorize execution. No CLI
reconcile/repair flag or operational recovery expansion is introduced.

Locks protect present rows and schema uniqueness protects duplicate admissions.
There is no claim of safe arbitrary uncoordinated external mutators or a global
cross-tenant reservation. New business-link publication and broader mutator
coordination are not authorized by a PLAN receipt.

## WIP01 connection question and actual Root resolution

The CLI application opens no public request/config/credential data file,
discovers no configuration, prints no DSN/environment/request/exception body and
executes no subprocess/Node action. A selected environment variable (default
SV_FRESH_NODE_OPERATOR_DSN) supplies the only connection string. Closed error
codes/statuses suppress rejected argv, arbitrary DomainError codes, str/repr,
tracebacks and driver diagnostics. An unknown APPLY outcome never auto-retries.

The original WIP01 SOURCE QUESTION / HOLD concerned forwarding the selected DSN
unchanged to psycopg.connect and the scope of ordinary libpq authentication/TLS
file handling. No actual DSN/credential/driver file was read or used by the author.
That question remains historically recorded in the frozen original artifacts.

Root actually answered `msg_97efddc65fbd`: the selected DBconnection exception
includes ordinary psycopg/libpq authentication/TLS and operator-approved file
references. It does not grant author access to any real secret or driver file.
The DSN and relevant driver environment are TRUSTED OPERATOR deployment inputs;
Root must privately freeze a self-contained host/port/database/user target,
TLS/auth expectations and approved file/environment references before any write.
Ambient service/default target selection is not an approved substitute. The CLI
does not enforce that private deployment profile or sandbox arbitrary DSNs.
No new connection policy framework, TLS downgrade or authentication rewrite.
Only module/CLI wording and one focused synthetic pass-through test changed
after WIP01. This synthetic test makes no driver connection or file read; its
result cannot prove real deployment profile approval.

Root also granted normal publication and ONE uniquely correlated Docs/Core/Backend
candidate verification from exact703 despite its still-running Core dependency.
Docs42335285577 and Backend42335289761 were SUCCESS in Root's fresh metadata;
Core42335287638 remained IN_PROGRESS at this grant. This is controlled early
candidate verification, not whole703 CI or joint review acceptance. No further
source redesign or optional Low expansion is granted. Original WIP01 manifest
c584f14d7bd6cc32fa184891ff3cf6bdbbc7032cdd3fc9a41b9f29ea3f9e8921, original
four-file patch/raw hashes and first failed/corrected static-verifier records
remain frozen. Original manifest-bound History bytes are additionally preserved
as `docs/vault/30_Development/Evidence/fleet5-fresh-cpu-admission-code-r1-20261107-codex/publication-v2/wip01-history-original.txt`.

## Proposed real tests and actual verification

Tests reuse mandatory root `migrated`/`owner_engine` fixtures, actual migrations
and a disposable PostgreSQL DB; missing CI prerequisite fails, with no new opt-in
skip. Synthetic keys are generated only if tests later run in Root/CI. The plan
covers PLAN under PostgreSQL read-only enforcement; normal atomic/offline/channel
and audit/readback; no snapshots/capacity; real inv_kernel/inv_app denial; missing,
foreign and inactive scope; epoch/version mismatch and post-PLAN control change;
kill/version/time preservation; Node/resource/association/channel collisions;
changed digest and caller transaction refusal; real SQL division-by-zero after
all writes and actual inconsistent readback rollback; two concurrent connections
with one winner; real commit followed by injected lost acknowledgement and
read-only reconciliation; bounded shapes/IDs/DER/certificate validity/URI/epoch/
EKU/CA/endpoint failures; CLI stdin/default PLAN/explicit APPLY against real DB;
and synthetic credential markers in parse/argv/connect/DB/forged-code failures.
The two-thread duplicate test is authored source only; the author launched no
parallel test process or helper worker.

Actual MAIN checks are AST parsing of four files and data/hash/source/scope checks
only, with exact results in `wip-static-verification.json`.
The first static-verifier attempt exited1 while its AST parameter-counting logic
tried literal_eval on a synthetic string multiplication. That author verifier
bug and correction (count AST entries without evaluation) are preserved in
`static-verification-attempt01-failure.json`; no product test ran or product file
changed for the correction. A corrected verifier result is separate evidence.
No app import,
cryptography, pytest, PostgreSQL, CLI, Go, remote action or live state occurred.
`git diff --check` exit0 covers tracked residue; static whitespace checking covers
the NEW files too. Product tests, all required delivery gates, CI and independent
review are NOT_RUN/PENDING. Document/static checks are not product acceptance.
At WIP01 no stage/commit/push/CI was authorized. Root's actual later grant above
allows only four new files plus this card's own new History/Evidence to be
published. Every other703 product/test file and old H12 residue stays excluded.
Sync stays CHECK-only with the exact canonical full state captured before/after;
no apply/adopt/resolve/export/global-state write. Frozen evidence is referenced
by hashes, not recopied as a giant archive.

Next finite action: produce a NEW publication-v2 manifest for exactly changed
bytes; pass required source/docs gates with actual exits; explicitly stage only
allowed paths, normal commit/push and exact remote readback; dispatch one same-SHA
Docs/Core/Backend attempt1. Product failures must be preserved and raised in ONE
targeted ASK before codefix/redispatch. After all lanes settle, a LOCAL post-CI
report binds raw receipts/artifacts and actual per-case JUnit outcomes before ONE
actual independent CODE review ASK. No self-referential second commit/CI loop or
original Task worker_done. No operator admission, private request, K2 trust
installation or Run approval is implied.

## Actual prepublication source/docs gate readback

The serial source/docs gate run completed with direct actual exit0 for all nine:
check_docs; check_ontology; check_ontology_generation; check_contract_bindings;
check_frontend_integrity; check_doc_path_citations --ratchet against exact703;
check_doc_single_source --ratchet; official sync_obsidian --check with the exact
canonical state; git diff --check. Byte-exact UTF-8 stdout/stderr and each command,
exit and KST are recorded under this Evidence prefix's publication-v2/gates.
Canonical full state before and after CHECK has SHA256
36d948a780874537f051beb203ba5ecc3e4e9326bae78de69e3c06ceb1d74115 in both
captures. Both independent full byte snapshots are preserved. No apply, adoption,
resolution, export or canonical state write occurred in this run.

A fresh official metadata read of dependency Core42335287638 returned completed /
success / attempt1 at exact703 on its correct branch. Its raw response is preserved
under publication-v2. This updates the earlier at-grant IN_PROGRESS observation;
it is not Root's actual joint review verdict. No dependency CI rerun occurred.
Final candidate product execution, new per-case JUnit and independent CODE review
remain PENDING until the authorized three exact-SHA CI lanes and Root review.
The publication-v2 manifest separately binds current four hashes, original WIP
hashes, exact wording/test-only change proof and allowed scope. Post-CI receipts
will stay LOCAL without a second self-referential commit/CI loop.
