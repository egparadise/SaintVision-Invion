---
doc_id: "HIST-20261028-CARD301-FILESYSTEM-REVIEW-CLAUDE"
title: "Card 301 standalone worker module filesystem review"
version: "1.1.0"
status: "accepted"
author: "Claude"
created: "2026-10-28T12:43:10+09:00"
updated: "2026-10-28T12:50:34+09:00"
source_of_truth: "Git"
---

# Card 301 standalone worker module filesystem review

## Verdict

**Final independent verdict: accepted at exact head
`f2936ae5e91787b3dbba0d069a85ccaef020c984`.** The coordinator restored external Git metadata and
re-observed branch `agent/codex/c301-standalone-worker-modules`, PR #397, CLEAN merge state, the PR
head, and all five reviewed file hashes. They match the filesystem snapshot reviewed below. No live
rollback, rotation, Node, Docker daemon, credential, or database operation is part of this verdict.

Owner/reviewer: Codex/Claude. Implementation base reported by the owner:
`b3ef33c5407a1356343cb457126d2f1217bc7427`; accepted implementation head:
`f2936ae5e91787b3dbba0d069a85ccaef020c984`.

## Findings

- The AST closure is evaluated before wheel download and is fixed to
  `worker_leaf_rotation.py` plus `worker_config.py`; relative imports, a missing local module, a new
  repository-local import, and source digest drift fail closed.
- Bundle validation, installed-file reconstruction, and the install receipt independently bind the
  exact worker-module set and bytes. The receipt digest is a canonical digest map whose entries are
  revalidated against the installed bytes.
- The isolated runner validates the exact runtime tree, removes cached local-module objects, and
  places the installed `worker/` directory ahead of standard-library paths. The external worker
  directory is absent from `sys.path`, so a sibling `worker_config.py` cannot shadow the pinned one.
- The hosted lifecycle helper reaches the real delayed `docker_restart()` import and exact
  `docker cp`, restart, inspect calls through a disposable fake Docker CLI. It checks install,
  finalize, rollback, four restarts, and zero bytecode caches. Backend Build run `39264782855`
  exercised the exact head on CPython 3.12 and 3.14 and both jobs succeeded.
- The four read-only conclusions in the owner report match the code: an ordinary restart retains
  the old container volume after the pre-`install_files()` import failure; the same installed-phase
  journal can retry only while `validate_bundle()` accepts the overlap; Card 293 supersession
  requires a restarted journal and next-version baseline; rollback explicitly accepts `installed`
  and restores only a still-fresh exact backup.

No corrective code finding was identified in this snapshot.

## Direct verification

Environment: Windows, CPython 3.12.14 from the Codex runtime. The repository `.venv` launcher was
unusable because it refers to a missing Python 3.14 executable. Pytest collection from the repository
was also denied while walking the sandbox-blocked parent directory, so the reviewed files were copied
unchanged to a temporary directory and the standalone runtime suite was run there. The temporary copy
is not Git or CI evidence.

| Command / observation | Result |
|---|---|
| `python -m pytest -q .../tests/test_lan_leaf_rotation_standalone_runtime.py` on the unchanged temporary copy | exit 0; 19 passed in 1.28s |
| `python -m py_compile deploy/lan/leaf_rotation_standalone_runtime.py tools/check_leaf_rotation_standalone_lifecycle.py` | exit 0 |
| repository `.venv\\Scripts\\python.exe --version` | exit 103; missing referenced Python 3.14 executable |
| focused pytest directly from repository | exit 2; collection blocked by sandbox parent traversal, not a test assertion |
| coordinator same-checkout focused suite | exit 0; 19 passed on the exact head |
| exact Git/PR identity | branch and PR #397 head `f2936ae5e91787b3dbba0d069a85ccaef020c984`; merge state CLEAN |
| Backend Build `39264782855` | success; CPython 3.12 and 3.14 jobs both success |
| Core `39264782887` | success |
| Documentation `39264783082` | success |
| Desktop browser `39264783012` | success |
| exact-checkout docs / ontology / Obsidian check | exit 0 / exit 0 / exit 0, re-observed by the coordinator |

Reviewed file SHA-256 values: runtime
`b9291fa8069589c2faa4a535630c115505e05bcf5a8a59c1278b10e0fdd9ea3d`, worker
`bca76df80a7bf80a6847e9b115679b1aa3e698d8b3a80ff843aacdd1370cd9b4`, worker config
`bb2b750ac294a2558f0214f8822c02da2f015486767f361b385ccc58e3c18992`, standalone tests
`909509e3ab4bfe9467a96364ea9dd870cd290d5eabd7da7145213bb86882f6a5`, and lifecycle helper
`39f763d2e18f17fc82563e2329ed8ccb12904dbbf6b28d138376a1b977c8cc97`.

The four successful same-SHA workflows above are the only hosted evidence used for this verdict.
Any unrelated job or workflow that was skipped, not triggered, or not listed remains excluded; a
skip is not a pass and is not counted toward Card 301 acceptance.

## Next handoff

Card 301 is ready for Codex integration handling at the accepted head. Live recovery remains
separately authorized work and is not approved by this code-review verdict.
