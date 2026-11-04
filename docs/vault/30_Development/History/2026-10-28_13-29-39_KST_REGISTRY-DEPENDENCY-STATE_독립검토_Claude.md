---
doc_id: "HIST-20261028-REGISTRY-DEPENDENCY-STATE-REVIEW-CLAUDE"
title: "REGISTRY-DEPENDENCY-STATE independent review"
version: "1.0.0"
status: "accepted"
author: "Claude"
created: "2026-10-28T13:29:39+09:00"
updated: "2026-10-28T13:29:39+09:00"
source_of_truth: "Git"
---

# REGISTRY-DEPENDENCY-STATE independent review

## Scope and exact head

- Owner/reviewer: Codex / Claude
- Base: `6e1c4a365b1d4df3b3e3ba793b6e1f9eb162b401`
- Reviewed head: `ad0132b35d7216552bbe929730562819af15e3bd`
- Scope: `tools/check_docs.py`, the seven dependency-state cases,
  `docs/task-registry.json`, generated ontology equivalence, and preservation of existing task
  evidence fields.

## Findings and verdict

**Finding 0. Independent verdict: accepted for the reviewed local/source scope.** Hosted CI was
still running when this verdict was recorded, so this is not a same-SHA CI acceptance claim.

The new rule is fail-closed at the correct boundary. `ready`, `in_progress`, `review`, and `done`
are active claims and every declared direct prerequisite must be `done`. `planned` and `blocked`
remain legal waiting states. Unknown dependencies, duplicate IDs, and cycles continue to be checked
by the existing validation path, so the new helper does not replace or weaken those guards.

The seven cases cover all six legal waiting/active classifications relevant to the rule plus the
positive completed-prerequisite path:

1. unmet dependency rejected for `ready`;
2. rejected for `in_progress`;
3. rejected for `review`;
4. rejected for `done`;
5. allowed for `planned`;
6. allowed for `blocked`;
7. active task allowed when its dependency is `done`.

## Registry and evidence preservation

The current registry is version `1.0.1` with exactly 48 tasks:

- `done`: 2 (`S01-FE`, `S01-DB`);
- `blocked`: 4 (`S01-BE`, `S01-ST`, `S02-FE`, `S02-DB`);
- `planned`: 42;
- active `ready/in_progress/review`: 0.

The coordinator's escalated exact diff from base to reviewed head confirms that the registry changed
only version `1.0.0` to `1.0.1` and 20 status values. `S01-BE/ST` changed from `in_progress` to
`blocked`; `S02-FE/DB` from `review` to `blocked`; and 16 downstream FE/DB rows from `review` to
`planned`. There were no other registry hunks. `depends_on`, `next_handoff`, evidence requirements,
acceptance/contract/skill references, scope, owner, and reviewer remain byte-for-byte represented by
the existing fields. Therefore the correction withdraws premature active-state claims without
deleting implementation, test, CI, History, or 75%-class evidence.

## Reproduction

| Command/check | Result |
|---|---|
| Isolated unchanged `tests/test_check_docs_dependency_status.py` | 7 passed, exit 0 |
| Dependency test plus unchanged secret-guard regression suite | 12 passed, exit 0 |
| `python tools/check_docs.py` | PASS: 24 source hashes, 1,172 versioned documents, 48 tasks, 12 outcomes; exit 0 |
| `python tools/check_ontology_generation.py` | four tracked artifacts graph-equivalent to fresh generation; exit 0 |
| `python tools/check_ontology.py` | RDF/SHACL/query/mirror/task mapping checks PASS; exit 0 |
| Direct RDF status audit of `ontology/example.ttl` | 48 tasks = 2 done, 4 blocked, 42 planned; exit 0 |

The first ad-hoc RDF count invocation exited 1 because PowerShell removed quotes from an inline raw
path literal. Passing the repository path as `argv` corrected the harness; the corrected invocation
exited 0. This was a review-command quoting error, not an ontology failure.

The child sandbox could not read the external Git metadata (`git status/diff` reported not a Git
repository). Exact base/head and registry-diff facts above are therefore explicitly attributed to
the coordinator's escalated read-only observation rather than presented as a child-local Git result.

## Handoff

Codex/coordinator should retain this local reviewer acceptance with the exact-head CI result. A
failed or incomplete required CI lane must remain separate and must not be converted into acceptance
by this review. No product code, registry, or common progress board was changed by Claude.
