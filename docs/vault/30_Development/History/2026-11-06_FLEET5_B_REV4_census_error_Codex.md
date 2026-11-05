---
doc_id: "HIST-FLEET5-B-REV4-CENSUS-ERROR-001"
title: "FLEET5 revision4 source census decorator scope error and correction"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Actual independent Claude delta review via Root pending"
updated: "2026-11-06T06:48:29+09:00"
source_of_truth: "Git"
---

The initial -B source_census.py --write command exited1 because decorator Call
nodes may precede def.lineno and had no enclosing function in the AST lookup.
No source/product/host operation occurred and no census artifact was published
from that failure. The correction walks module calls once, assigns the innermost
function or explicit module scope, and indexes functions per file; module-level
calls are now included too. Subsequent exact72028 source regeneration exits0;
known-call/ORM/helper/import/alias removal checks return expected exit1.

The original error and correction are recorded in the unique Rev4 Evidence
census-development-error.json. This is a local tooling correction, not a Go/PG/
Docker/physical test or a claim that every dynamic Python edge is resolved.
Next owner Root reviews the actual final Rev4 whole delta before any code grant.

The final staged git diff --check also exited2 for whitespace on one blank line
in the new census script. The whitespace was removed and the staged gate rerun
before commit; this formatting correction changes no source-census semantics.
