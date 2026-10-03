---
doc_id: "HISTORY-CARD258-AC11-EXACT-SHA-AXIS-COVERAGE-CODEX-001"
title: "Card 258 AC-11 exact-SHA axis coverage measurement"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-03T11:21:53+09:00"
source_of_truth: "Git"
---

# Card 258 AC-11 exact-SHA axis coverage measurement

## Scope and immutable inputs

This card measured the already-approved AC-11 contracts without changing an evaluator, schema,
target registry or product file. The measured release SHA was
`694217b0df7cca2765e1bce5ecd7d9148f5615b5` on
`coord/train36a-ci-1007`; its checkout tree was
`6dbd6cac94740db35a2a5d116c390d7bae6a8370`. The documentation branch starts from the later
candidate `coord/train37a-ci-1106` at `e5549f4bae23f2206dd0bf8f02b00207e07f2750`, which contains
that measured SHA as an ancestor. The measurement does not apply the result to the later SHA.

The two existing same-SHA inputs were:

| Axis | Run | Artifact | Artifact digest | Result |
|---|---:|---:|---|---|
| `security-critical-high-zero` | `37084904992` | `11260082765` | `sha256:ae2e7975e1d14733b87ebc59f693b0dd6f41fb736a264757692234fc4af764ef` | `MEASURED_PASS` |
| `accessibility-e2e` | `37084910005` | `11260142942` | `sha256:0bae73a9cc627928236a339d8703adca1ba37b8fe83bb0f447e5abf95b2b5a27` | `MEASURED_FAIL` |

The accessibility failure is the observed `manualAcceptanceMissingCount=1`. Its automated
observations remained 5/5 canonical journeys, 9/9 desktop invariants, 3/3 contrast checks and
2/2 keyboard checks. This card does not reinterpret that result as a pass.

## Same-SHA migration rehearsal

The following opt-in workflow was dispatched against the exact target ref:

```text
gh workflow run ac11-migration-rehearsal.yml --ref coord/train36a-ci-1007
```

Run `37088890116` completed `success` with head SHA
`694217b0df7cca2765e1bce5ecd7d9148f5615b5`. Artifact `11262010132`, named
`s11-ac11-migration-694217b0df7cca2765e1bce5ecd7d9148f5615b5`, has GitHub digest
`sha256:e832fe5b1fe56c41b656a7f8f4aef8bfff91109a7ea519e5dc7f91e83493d6c5` and expires at
`2026-11-02T02:11:52Z`.

The producer report SHA-256 is
`ff781a5cdcbfa6b3525ebba148d9a0771d5500286571b63f6b02b09525eae4a4`; its JUnit SHA-256 is
`e4aa19f0baafc5db5f4bf100183da428db0f5584a31b2daa809c827798fa0542`. JUnit reported 7 tests,
0 failures, 0 errors and 0 skips. Cleanup reported 10 attempted disposable PostgreSQL databases
and 0 residues. Both emitted axes were `MEASURED_PASS`:

- `migration-reversible-segment`
- `irreversible-restore-forward`

## Same-SHA assembly and independent recomputation

The aggregate workflow was dispatched with:

```text
gh workflow run ac11-aggregate.yml --ref coord/train36a-ci-1007 \
  -f source_sha=694217b0df7cca2765e1bce5ecd7d9148f5615b5 \
  -f correlation_id=card258-ac11-four-axis-694217b0
```

Run `37089008514` completed `success` at the same head SHA. Artifact `11261094847`, named
`s11-ac11-aggregate-694217b0df7cca2765e1bce5ecd7d9148f5615b5`, has GitHub digest
`sha256:a1606f90293fd0e4b999691018cf52163693ab4eb660a1200b26461fda0dfc2e` and expires at
`2027-01-01T02:12:58Z`.

The downloaded manifest was passed again to the canonical evaluator while the local clean checkout
was detached at the exact target SHA:

```text
.\.venv\Scripts\python.exe tools\aggregate_ac11_evidence.py \
  --manifest "$env:TEMP\sv-card258-aggregate-37089008514\ac11-aggregate-manifest.json" \
  --repo . \
  --output "$env:TEMP\sv-card258-aggregate-37089008514\ac11-aggregate-result-recomputed.json"
```

The process returned exit 2, the specified exit for an invalid/incomplete release-gate run. The
recomputed JSON was semantically identical to the uploaded `ac11-aggregate-result.json`; only JSON
formatting changed. The uploaded result file SHA-256 is
`0a689b56c848253616e2bd52b30432f89783f82ddc0abfb732f40cc3013d62ac`.

## Measured verdict

The assembler emitted 4 of the required 8 axes:

| Axis | Recomputed verdict |
|---|---|
| `migration-reversible-segment` | `MEASURED_PASS` |
| `irreversible-restore-forward` | `MEASURED_PASS` |
| `security-critical-high-zero` | `MEASURED_PASS` |
| `accessibility-e2e` | `MEASURED_FAIL` |

The following four axes were absent, not synthesized:

- `actual-pitr-rpo-rto-retention`
- `long-soak`
- `physical-five-node-ac05-placement-load`
- `physical-five-node-failure-recovery`

The canonical overall verdict therefore remains `INVALID_RUN`, `done=false`, with the missing-axis
reason listing those four axes. This is a coverage measurement, not an AC-11 completion or score
promotion. Repeated missing-lane discovery and dispatch automation is intentionally left to a
separate card.

## Documentation verification

- `python tools/check_docs.py`: exit 0.
- `python tools/check_doc_single_source.py --ratchet`: exit 0.
- `python tools/check_ontology.py`: exit 0.
- `python tools/sync_obsidian.py --check`: exit 0, 2,030 managed files, 128 pending exports and
  0 conflicts; no write was performed.
- `git diff --check`: exit 0.
- `python tools/check_doc_path_citations.py --report`: exit 0 and this History file contributed
  0 broken citations. The local ratchet mode separately reported five stale baseline entries
  because ignored generated frontend build and dependency directories existed in this reused
  checkout; the clean candidate checkout's Documentation run `37088667601` was successful.
  The PR Documentation run remains the final clean-checkout gate.

## Handoff

- Owner: Codex.
- Reviewer: Claude.
- Change class: documentation only; evaluator, workflow, schema, target and product deltas are zero.
- Next action: independently verify the run/artifact identifiers and the unchanged fail-closed
  interpretation, then decide a separate automation card without changing these measurements.
