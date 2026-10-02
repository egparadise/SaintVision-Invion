---
doc_id: "HISTORY-CARD237-AC11-DEFINER-ALLOWLIST-20261002"
title: "Card 237 AC-11 SECURITY DEFINER allowlist review"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-02T20:28:31+09:00"
source_of_truth: "Git"
base_sha: "843d283c1ee70cc021385b0f8f25ec323d434829"
reviewer: "Claude"
---

# Selection and scope

The v1.11 AC-11 measurement left `security-critical-high-zero` as the only axis that
could become measurable without physical equipment or an operator acceptance. Its
`SEC-DEF-001` producer observed 15 SECURITY DEFINER functions while the reviewed
allowlist contained only 12. Card 237 therefore reviews the three exact missing
definitions before any score change. It does not weaken the threat definition or infer
a PASS from an empty database.

# Review result

The review document examines the fixed search path, dynamic-SQL absence, owner and
EXECUTE grants, input checks, tenant boundary, and privilege-escalation surface for each
new signature. Migration 0060 adds only a SECURITY INVOKER guard and does not expand the
privileged-function set. The generated allowlist now exactly equals the 15-function
policy; it cannot be emitted when either set differs.

The three `inv_audit_reader` E3/E4/E5 observations are actual intended privileged
visibility, not false positives. They are accepted only through
`2026-10-31T23:59:59+09:00`, at which point the canonical evaluator fails closed unless
the operational membership boundary is reviewed again.

# Generated authority and verification boundary

`tools/write_ac11_security_allowlist.py` projects the reviewer-owned source only when
the definer-policy signature set and RLS-baseline disposition set match exactly. The
generated allowlist blob and canonical SHA-256 are pinned by the aggregator. A follow-up
commit must repin the AC-11 target registry to this commit and rotate every importer
registry pin together; until that commit, no hosted PASS is claimed.

Local verification uses the repository Python 3.14 virtual environment. The generator
test file passed 10/10. The security importer file passed 127 tests and had one unrelated
local Git ancestry timeout; it is rerun after the target-registry repin. Exact-head
hosted security evidence and its canonical verdict remain merge conditions.
