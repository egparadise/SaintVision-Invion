---
doc_id: "HIST-20261029-VF-CL-04-ATTESTED-CI-CODEX"
title: "VF-CL-04 attested CI closure and AC-11 required-CI repair"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-29T14:21:59+09:00"
updated: "2026-10-29T14:21:59+09:00"
source_of_truth: "Git"
---

# VF-CL-04 attested CI closure and AC-11 required-CI repair

## Scope and provenance

- Owner/reviewer: Codex / Claude; Gemini frontend-truth review; Orca aggregation.
- Branch: `agent/codex/c301-standalone-worker-modules`; PR #397.
- Base and attested source head: `ad0132b35d7216552bbe929730562819af15e3bd`.
- Evidence/test commit: `751ea725c8353fe8df4982c0459321d57f53bb89`.
- S12 workflow run: `40633895766`; correlation ID
  `vf-cl-05-ad0132b3-20261028`; producer and attestation jobs both succeeded.

## Work performed

The exact-head S12 acceptance workflow produced the VF-CL-04 receipt in an unprivileged producer
job and signed it in the dispatch-only GitHub OIDC job. The downloaded receipt and attestation
bundle were committed at `docs/vf-cl-ci-receipts/VF-CL-04.json` and
`docs/vf-cl-ci-attestations/VF-CL-04.bundle.json`. The registry and manifest now derive
`ciVerified=true` from those files rather than from prose or a forgeable run identifier.

Required Backend run `40632341602` and Core run `40632341610` failed at the same test and for the
same reason: the positive `test_main_reads_zip_and_github_metadata_files` fixture carried
`expires_at=2026-10-28T04:00:00Z`, earlier than the hosted execution time. The valid fixture now
uses 2099. Explicit `expired=true` and fixed `NOW-1 second` failure cases remain unchanged, so the
importer's fail-closed retention boundary is not weakened.

During the complete local gate run, `tools/check_frontend_integrity.py` scanned all 93 production
files and found zero violations, then raised `UnicodeEncodeError` while printing a Unicode success
symbol to the Windows CP949 console. The four success/failure labels are now ASCII `PASS`/`FAIL`.
No regex, rule, finding, or exit-code branch changed.

## Verification and review

| Check | Result |
|---|---|
| `python tools/verify_vf_cl_ci_attestation.py` with exact head/ref | `VERIFIED`, exit 0; run `40633895766`; receipt SHA-256 `e84a25905faf80d2a82be7596800b5f961fc35faed5b1d8ceff16194f9bcd9aa` |
| `python tools/check_vf_cl_registry.py` | 5 cards re-derived; acceptedCards 0; exit 0 |
| `pytest tests/core/test_check_vf_cl_registry.py -q` | 215 passed; exit 0 |
| `pytest tests/test_import_ac11_migration_rehearsal.py -q` | 19 passed; exit 0 |
| `python tools/check_frontend_integrity.py` on default CP949 console | 93 files, 9 rules, 0 violations; exit 0 after ASCII fix |
| `python tools/check_frontend_integrity.py --test-negative` | all 9 rule mutations detected; exit 0 |
| `python tools/check_docs.py` | 1,174 versioned documents, 48 tasks, dependency DAG; exit 0 |
| `python tools/check_ontology_generation.py` and `check_ontology.py` | fresh graph equivalence and RDF/SHACL/query/mirror checks; both exit 0 |
| `python tools/sync_obsidian.py --check` | 2,082 managed, 6 pending exports, 0 conflicts; exit 0 |
| Claude independent semantic review | approved; blocking findings 0 |
| Gemini frontend-truth review | approved; blocking findings 0; no `apps/web` consumer or user-visible progress change |
| Orca independent aggregation | VF-CL CI 4/5; product score and strict state unchanged |

Claude confirmed the receipt bytes match the Sigstore SLSA subject, the bundle binds repository,
workflow, branch, exact head and run, and the fixed fixture preserves both explicit expiry
rejections. The child environment could not initialize its own `gh attestation verify` Sigstore
verifier, so that limitation is not presented as a second signature verification; the coordinator's
successful repository verifier result is the positive evidence.

Gemini independently confirmed that `apps/web` has no consumer of the VF-CL registry or this field,
so the CI-axis change cannot silently alter a user-facing progress display. Gemini also re-ran the
exact receipt/bundle verifier successfully. The only follow-up finding was the stale field name in
the live post-landing runbook; that runbook is corrected in version 1.4.2 in this documentation
batch. Historical pages retain their then-true old field names as history.

Claude separately reviewed the ASCII-only scanner diff and found no changes to any regex, rule,
finding, or exit branch. Normal and negative-control paths returned 0 under forced CP949; forced
violation and forced negative-control failure paths retained ASCII `FAIL` and exit 1. Verdict:
approved, findings none.

## State and handoff

- VF-CL: implemented 5/5, locally verified 5/5, CI verified 4/5, independently reviewed 5/5,
  operationally accepted 0/5, acceptedCards 0.
- 48-task registry: done 2, blocked 4, planned 42, ready 0; strict 4.17%.
- Weighted evidence: landed 71.35%, candidate 72.40%; no score inferred from this CI receipt.
- Next owner/action: Codex pushes the exact commits and requires new same-SHA Backend/Core/Docs/
  Frontend CI. After CI and Obsidian sync, no internally ready canonical card remains. User/live
  IdP, CA/DNS, physical five-Node inputs, and explicit operational acceptance remain external
  boundaries and must not be auto-accepted.
