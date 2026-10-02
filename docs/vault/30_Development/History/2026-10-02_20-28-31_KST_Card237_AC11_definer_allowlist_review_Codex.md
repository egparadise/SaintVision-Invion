---
doc_id: "HISTORY-CARD237-AC11-DEFINER-ALLOWLIST-20261002"
title: "Card 237 AC-11 SECURITY DEFINER allowlist review"
version: "1.5.0"
status: "review"
author: "Codex"
updated: "2026-10-02T22:57:28+09:00"
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

Local verification uses the repository Python 3.14 virtual environment with
`PYTHONUTF8=1`; without that Windows console setting, a Git-show subprocess cannot decode
the Korean registry content under CP949. The generator passed 10/10, security importer
128/128, aggregator 138/138, accessibility importer 32/32, migration importer 19/19,
and composite-long-soak importer 23/23. Exact-head hosted security evidence and its
canonical verdict remain merge conditions.

# Registry repin

The generated allowlist first landed in commit
`0c7fbecd8fb96c91f887a509c78d64efc3c51b7e`, whose allowlist blob is
`47349f312f24629b83ac68e6ecdd006b39e46d48`. The canonical AC-11 target registry now
binds `s11-security-critical-high-zero-v0` to that reachable commit and exact blob. The
resulting registry blob is `5f92d6f70c614501cb4b20a78615379b1aea7078`; the aggregator and all four registry-aware
importers rotate to that same value in one follow-up commit. This is a definition-source
repin, not a relaxation of the empty `criteria` or hosted environment boundary.

# Hosted observation

Opt-in AC-11 security run `37002231140` executed on source head
`634d2a96ed49057f65826d6a7034121fcc151492`. Artifact `11224420911` has GitHub digest
`sha256:78a1c6bccc1e48262b57a88fe19b5c6dd4fabad3860dc004c2789948cbf299b1` and is not
expired at observation time. Its SEC-DEF-001 report records 15 functions,
`matches_reviewed_policy`, and exit 0. The dependency/SAST report is `MEASURED_PASS`;
the RLS row-isolation report remains `UNMEASURED` with exit 3. The latter is retained as
an honest independent threat boundary and is not converted into a PASS by this card.

# Backend regression and authority correction

The first generated review source incorrectly copied the dependency/SAST producer lane
(`.github/workflows/ac11-security-scan.yml`) into `secVf001.workflow`. SEC-VF-001 is the
separate browser proof, so `tools/find_ac11_vf_evidence.py` correctly stopped finding the
desktop-browser runs and four established finder tests failed with exit 3. Their expected
0/2 outcomes were not weakened.

Commit `976586282a0b0ebff0265e99a46589d1ddd096f2` restores the authority to
`.github/workflows/desktop-browser.yml` and its tree blob
`bb5708a803e6e8ceed2252a34fd895ace61fd0fe`. The generated allowlist blob is now
`54f8edf27a845a35e1428b69bcdff6754de91bbc` with canonical SHA-256
`c75fc38a5a988852e6068329b901d6f01e6fa0aa7aab5dbab2846137fc16836e`.
Commit `58c7e9e2bc11ea535c72238bfc504ad5e44d8e68` repins the canonical target
registry; its blob is `60800cc0a86aa723f04308f2f38786423a94f968`. The aggregator and all
registry-aware importers use that same blob. A regression test now keeps the SEC-VF
browser workflow distinct from the security-scan producer workflow.

Rotating the registry constants changes the security importer blob to
`0c46ccd9f3006ab723825815568268d7d1f45abb`; therefore the dependency/SAST
allowlist was mechanically repinned as well. Its resulting blob is
`8f1a36c6584413c4ea308f35853c1f675f280fe9`. This second pin remains about the
`ac11-security-scan.yml` producer and does not replace the distinct SEC-VF browser
authority.

# Migration 0060 composition rebind

Merge commit `4c90791c4ae4de9c22eae0cd827c2699cf6622eb` composes the approved Card 237
tree with train 26 candidate `a2d64b6193913a56448a0ef495d1b7b374de2a54` without changing either product
implementation. Train 26 advances `tools/definer-policy.json` from revision
`0059_build_execution_intents` to `0060_build_execution_admissions`; migration 0060
adds no SECURITY DEFINER function, so the reviewed inventory remains the same exact
15 signatures. The reviewer-owned source is rebound to that 0060 revision and the
generator confirms the existing allowlist blob `54f8edf27a845a35e1428b69bcdff6754de91bbc`
and canonical SHA-256 `c75fc38a5a988852e6068329b901d6f01e6fa0aa7aab5dbab2846137fc16836e`.

Focused regression after composition passed `test_write_ac11_security_allowlist.py`
11/11, `test_find_ac11_vf_evidence.py` 60/60, and
`test_import_ac11_security_scan.py` 128/128. Combined-tree hosted security run
`37012727613` independently observed SEC-RLS-001 PASS with zero violations and
SEC-DEF-001 `matches_reviewed_policy`; this run is corroborating train evidence rather
than a substitute for exact-head Backend and Core checks on this PR.
