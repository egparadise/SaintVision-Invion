---
doc_id: "HIST-FLEET5-P0-V2-EXACTHEAD-CI-001"
title: "FLEET5 P0 v2 exact-head CI and Unicode vector correction"
version: "1.1.0"
status: "in-progress"
author: "Codex"
reviewer: "Independent Claude corrected-delta review via root pending"
updated: "2026-11-06T00:12:33+09:00"
source_of_truth: "Git"
---

# Exact-head proof checkpoint

Owner Codex; task `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`, program task
`FLEET5-COMPUTE-STORAGE-CONTRACT-20261105`, branch
`agent/codex/fleet5-compute-storage-contract-20261105`. This checkpoint uses
source `4a928310e88ac336efb040c1621525fee7133f32`, following the exact guidance
IDs/versions/base/Index401/Codex362 recorded in the original source inventory
and [[2026-11-05_FLEET5_P0_plain_peer_phase_implementation_Codex]]. Root
RS1/SF1, N1 and C2 decisions remain the scope; full compound B, migration,
bootstrap predecessors and physical acceptance are excluded.

Core `42047390811`, job `127313967305`, passed the early native Go two-cycle
gate. Actual peer floors were 7,8,9,10,11 with control channels 8,9; both final
states rejected the old CP certificate. Frozen retries, expiry-before-write,
rollback refusal after handshake pin, CP/floor mismatch, strict old reader,
predecessor residue/original replay, actual Go same-version hash rejection and
expired direct-startup pin guards passed. The native fixture excludes actual
Docker ownership, PostgreSQL CAS and operational acceptance. Artifact
`13426365088` was downloaded and its ZIP SHA-256 matched GitHub's digest:
`89905efce01632d27238a433e189c46150c7c0ff4a45838ca1b87da617683d0c`.
Docs `42047397366` passed exact 4a. At this checkpoint full Core and Backend
`42047403498` are in progress; their final results are not inferred.

Artifact inspection then found an incomplete test claim: three static named
Unicode vectors contained question-mark substitutions. Equality and signatures
were valid for those supplied bytes, but the named cases did not cover their
intended Unicode scalars. The existing direct Python non-ASCII body assertion
was valid. Root was notified in `msg_7113bdba916c`; 4a's native result is retained
unchanged and does not establish the full intended C2 Unicode requirement.

The correction changes only the fixture and Python/Go test assertions. It pins
actual Hangul, accented Latin, emoji, a supplementary musical symbol and
U+10FFFF using escaped source code points; nested Unicode and U+2028 are covered.
Distinct precomposed U+00E9 and decomposed U+0065/U+0301 keys must both survive
without NFC normalization; both languages check known UTF-8 hex before signing.
Explicit Python coverage assertions against the original fixture failed with
exit 1 (one failed, nine passed), as intended. After the escaped fixture change,
the same command passed ten with exit 0. Go assertions independently require
those exact code points before comparing static canonical bytes and producing
signatures. Runtime source and outer receipt/newline semantics are unchanged.

Raw artifacts, first job snapshots, native receipt, expected-red/green logs and
fixture hashes are under
`Evidence/fleet5-compute-storage-contract-20261105-codex/p0-v2-exacthead-ci/`.
The corrected Go proof, full exact-head Core/Backend/Docs and actual independent
implementation review remain required. Codex next publishes this narrow delta
and runs the affected hosted proof; root owns independent review and candidate
integration. No host Docker, physical/private Node, CA/enrollment/install,
remote/trust/system, scheduler, cleanup or Obsidian apply action was made.


## Follow-up fixture isolation regression

Unicode-only delta `5000069744931afb2fb85d24752a9916f7ba0ccc` is pushed;
Docs `42050046566` passed that exact head. Production source remains exact 4a.
Root's `msg_80d97ffc4e8b` requires preserving original 4a terminal runs and using
only fixture/coverage changes; no active same-ref Core/Backend run was replaced.

Backend `42047403498`, Python 3.14 job `127314057819`, failed five residue and
predecessor cases: 8717 passed, 75 skipped, two deselected, five failed. The raw
job log and precise failure summary are preserved. Investigation found fixture
module isolation, rather than a production freshness defect: the in-process
standalone repeated-cycle test evicts helper modules via the real runner but
restores only dependency modules. Subsequent fixture adapters retain old module
objects while dynamic imports receive new objects and an unpatched clock.

The isolated residue suite passed twelve with four Windows skips; running the
runner plus residue sequence without a prior adapter import passed six. Adding
one prior normal fixture reproduces exactly five failed/two passed, exit 1,
without sleeps, system clock changes or weakened signatures. Both diagnostic
orders and the actual failing run are retained. Root was notified in
`msg_a76228cf2439`. The narrow test correction restores all worker module
identities and argv alongside its existing dependency/path restoration and
asserts that restoration; production freshness and runner behavior are unchanged.
Ordered seven-case green and sorted relevant-suite receipts follow separately.


Root `msg_d8d3b719e68b` confirms this bounded test-isolation closure. The final
fixture matrix checks successful and failing worker execution with each helper
entry initially its original object, absent, or blocked-import None. Its
exception-safe finally restores all five entries, dependency entries, argv and
sys.path, preserving the existing no-bytecode and repeated-cycle assertions.
The exact ordered repro now passes twelve; the fifteen relevant suites in
sorted order pass 314 with twenty existing Windows platform skips, exit 0.
Seven document/contract checks also pass, with sync --check making no writes.
All eighteen recorded runtime/proof/workflow surface hashes remain equal to 4a.

Backend 4a is now terminal failure in BOTH matrices: Python 3.12 job
`127314058613` has the same five failures, 8717 passed, 75 skipped and two
deselected. Neither matrix reached installed standalone verification because
its prior Tests step failed. Raw logs, API terminal run/jobs and summaries are
preserved. Core 4a remains active at this checkpoint and will not be cancelled;
the next same-ref Core dispatch must wait for its terminal result. Codex next
publishes this test-only successor and dispatches Backend/Docs after the prior
same-workflow runs are terminal, then Core with the corrected native proof.
Actual independent runtime and narrow-delta review remains pending via root.
