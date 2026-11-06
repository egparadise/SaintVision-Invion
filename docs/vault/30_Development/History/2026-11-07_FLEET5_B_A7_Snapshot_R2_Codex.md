---
doc_id: "HIST-FLEET5-B-A7-SNAPSHOT-R2-001"
title: "FLEET5 A7 R2 existing guard coverage before call retention"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Actual independent narrow A7 R2 delta review through Root pending"
updated: "2026-11-07T07:03:52+09:00"
source_of_truth: "Git"
---

# Exact scope and actual independent review

Codex owns FLEET5-B-A7-SNAPSHOT-R2-20261107, task_a8fd2969f0b3 /
ctx_6f0f8253b8a7, under Root msg_e051a19e0010. Preparation receipt KST is
2026-11-07T06:57:31.117516+09:00. Own branch
agent/codex/fleet5-b-a7-snapshot-r2-20261107 starts at exact
1550453d1f072a87fd9a7baa53d4fe4ce8a98d5d; R1 ref is preserved. Product source
remains72028cbac903c4415d9979f980a6e0f9948e914f. Only this new History and
Evidence/fleet5-b-a7-snapshot-r2-20261107-codex are added. No old file, shared
board, registry, ADR, original source, workflow, product/schema or model is edited.

Actual independent review7a8012f47de5aa94a4264366df6722c1f6755a9c is direct
parent1550, ten own added documents, LOW-only REVISION_REQUIRED A7R-L1,
no HIGH/MEDIUM. Root independently verified Docs42299221800/job128172332633,
manual docs.yml/attempt1/title claude-b-a7-1550-review-7a8012f4-ctx_d6e29070eb5d,
all19SUCCESS. Its full original review, driver,49 result rows and commands
were read first. All ten committed originals are preserved with Git object IDs,
paths, byte hashes and review provenance. The49 historical rows are one
baseline,19 BODY,8 CENSUS,20 GUARD_ONLY and one SPAN; the comment-inside-With
control is an INFO expectation mismatch, not all-pass. Reviewer measured
105259008B/65.3s in one process, not an aggregate or quota. The committed log
is the reviewer's normalized Git original; the separate scratch raw hash is
preserved in its original commands, not silently equated to those bytes.

The actual same-input finding has four distinct SPAN/BODY/CENSUS/GUARD_ONLY
rows. Root reported correcting its own initial three-row verifier to four,
without changing author/reviewer bytes. R2 explicitly checks all four origins.
Root's read-only vault at1552766f90269157a6f3eaedf51a16ecf7aedaba had
INDEX-PROGRESS-001 v1.0.483 and WORKBOARD-CODEX-001 v1.0.444.
Input receipts record exact doc IDs/versions/hashes, AGENTS and registry:
INDEX-VIRTUAL-COMPUTER-001/ROADMAP-VIRTUAL-COMPUTER-001 v1.0.0,
GOV-CONTINUOUS-001 v1.1.0, GUIDE-001 v1.1.0, ADR-INDEX-001 v1.37.0,
GOV-AGENT-001 v1.1.3, GOV-GIT-001 v1.1.4, GOV-CONTINUITY-001 v1.0.0,
agent-delivery1.1.0 and core-reliability1.0.0. No helper was dispatched.

# Narrow correction and exact oracle

R1 a7_inventory.census parsed30 lexical candidates but executed existing guards
only after the call-retention filter;12 were audited and18 were omitted.
R2 moves the SAME ra.audit(PROTECTED) and u.module_uses calls before that
filter. Every parsed path/current-SHA pair must equal the audited pair set,
with real per-path guard results. Constructor/call retention remains a
separate downstream classification. Non-retained failures emit the existing
A7_RELEVANT_REFLECTION or A7_FULL_MODULE_USE_SITE_GUARD obligations.
No guard predicate, family, resolver, body rule or caller policy is broadened.

The exact original driver PATCH is extracted as a literal AST constant; it
produces node_certificates.py inputSHA256
19c2e14eb3e586f5ed22e1fb0549fe51961a079557fba2bb07ca1b8410686191.
Original import and assignment spans remain[75,0,75,56] and[76,0,76,54].
The retained guard's precise attribute-store span is[76,0,76,22] with subject
WRITE_USE:inv.node_channels.NodeChannels.snapshot. The fixture compiles, and
NC/CT/DB/ER selected source bodies stay unchanged. bodyAccepted remains true;
the census must add exactly the correctly located guard obligation over the
COMPLETE baseline multiset. It is a census correction, not a body refusal or
proof of closed callers/runtime. Baseline's19 blockers cannot satisfy it.

The oracle compares code/path/current span/semantic subject and multiplicity,
recording all baseline/current additions and removals. Existing use-site node
enumeration is replayed only to locate its actual refusal, never to decide or
bypass the guard. The same patch in retained observation.py still adds its
original census guard; the full pipeline also retains its older downstream
A7_FORWARD_GUARD. Non-retained benign comment and unused import alias controls
must preserve all19 original obligations. The INFOI3 replay of the original
owner input explicitly requires a NEW observation.py[17,16,17,70]
A7_PURPOSE_PROVENANCE key for foreign. Existing NodeDelivery's purpose key
cannot satisfy this corrected oracle; purpose/body predicates stay unchanged.

Frozen30parsed==30audited, with all18 newly audited candidates clean. The
original30/10/10/7/12 source/constructor/snapshot/forward-state/event data,
original19 obligations and selected body proof remain byte/data equal to R1.
All23 copied producer modules except a7_inventory retain their original bytes;
the new test/publication helpers are uniquely scoped R2 harnesses.

# Actual proof, preserved failures and publication

Before the fix, the unchanged R1 inventory SHA256
6910ddfd6ae1f3cd2d037f439ccd194cd4ebd5faf953cb6761d997465693c4e9
was checked. The exact new regression failed exit1 at
MISSING_OR_INEXACT_NEW_CENSUS_DELTA with zero added obligations, body true and
19 baseline obligations. red-original01.json/log preserve argv/cwd/Python/KST,
complete before/after hashes and the actual expected exit1; this intended
negative proof is not task failure or green coverage. Its input/results and
original inventory bytes are separately archived before final green output.

Preparation first failed exit1 for the misspelled codec utf8-sig, before any
proof or module copy. Its initial tool chunk and an unchanged recorded exit1
reproduction are recorded; corrected utf-8-sig preparation then exited0.
The preparation logs are PowerShell transcripts, not claimed byte-for-byte
subprocess stdout. Original R1 dev02/dev03 failures and raw logs remain intact,
as do review INFO/invalid preconditions; no failure is overwritten as a pass.

Final01's five regression cases and build exited0, but its verifier exited1
comparing in-memory tuple facts to R1's JSON arrays. The serialized body had
zero differences. The comparison now canonicalizes the fresh result to JSON
before the exact body/data comparison; no predicate changes. Its raw failure
and original command receipt remain. Final02 then passed those checks but its
verifier exited1 reading a command's exit at the red summary's top level,
instead of its commands[0] record. The original complete nested receipt is
preserved; only the verifier's reader is corrected. Final03 source proof then
passed all three commands. Its docs gate rejected the two UTF-16 preparation
transcripts; their original bytes are losslessly archived with hashes in
raw-preparation-transcripts.json, alongside decoded UTF-8 text logs. The failed
docs receipt is retained. The sealer now accepts separate successful proof/docs
attempt names so publication does not overwrite failed stage receipts. Fresh
final04 proof and publish01 docs use those final harness bytes.

Final bounded serial proof is r2_tests.py (five exact regression/controls),
a7_build.py and r2_verify.py. The deterministic rebuild checks actual review
Git blobs, unchanged helper/body/accounting artifacts and the real parsed and
audited path/SHA sets. proof-final04.json and raw logs record immediate exits,
Python3.14.7 -B, argv/cwd/KST and per-file before/after hashes at final producer
bytes, including inherited Rev8 body predicate and Rev7 manifest. Mutants are
AST-parsed/compiled only. Old33 owner cases,49 reviewer cases, giant ledgers,
523 assembler/3485 plans, old B, model, recovery and full Core are not rerun.
Per-process peaks are observations, not aggregate/hard quota/OS enforcement.

Required eight local docs gates are separately recorded in docs-publish01.json.
Canonical CHECK calls use immediate full-state SHA before/after each call and
own conflicts output; Root may apply concurrently, so real conflicts/state
changes must remain visible. No apply/adopt/resolve/export/state write occurs.
The final proof-producer-hashes.json seals receipts and this History. One own
docs-only commit/push and ONE exact manual Docs run follow; actual pinned SHA,
run/job/head/ref/title/attempt/path/all19 results go to Root. No future CI ID,
post-CI amendment or second CI commit is invented here.

# Preserved limits and next owner

INFOI1 remains failclosed: necessary lexical binding events include their
whole enclosing statement source segment, so a comment inside With may reject
despite unchanged AST semantics. R2 does not call this wholly text-independent.
INFOI2's two other receivers are git snapshot APIs, not closed NodeChannels
receivers. No extra NodeChannels paths are invented. INFOI4's BoundDatabase
is not authenticated inv.db.Database; its different borrowing transaction
stays under existing unresolved owner/root obligations. A missing frozen path
may still raise a failclosed precondition exception; it is not semantic success
or a general source resolver, and is not relabelled as a new passed case.

Status remains SOURCE_STATIC_UNRESOLVED_RUNTIME_PENDING, callerClosureAccepted
false, all original19 blocksGrant, runtimeB0, real bindings NULL/HOLD and
A1-A16PENDING. Shared12 entries/19 edges(16analysis/3runtime), all six accounting
artifacts,598/757/1071/21/573outside/218, model/lifecycle and stage/final bytes
stay unchanged. A7 is not a thirteenth operational entry. No product snapshot,
NodeDelivery delivery/admission, DB/role/SQL/network/crypto/Engine effect, source
inclusion, port/runtime grant, physical-PC acceptance or integration is claimed.

Root's first next action is to verify this frozen R2 package and queue ONE
actual narrow independent delta review after the current D04 CODE review's
actual exit/release and custody. The author sends a structured pending ask,
not whole-B worker_done or selfacceptance, then awaits Root's verdict.
