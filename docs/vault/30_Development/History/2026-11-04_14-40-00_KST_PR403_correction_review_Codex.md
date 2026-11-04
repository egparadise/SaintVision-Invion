---
doc_id: "HISTORY-PR403-CORRECTION-REVIEW-20261104-CODEX"
title: "Independent exact-head PR403 historical-state correction review"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-04T14:40:00+09:00"
source_of_truth: "Git"
---

# Independent correction review

Task SUPERVISION-20261104-CODEX / task_4a4eaf27c548 / ctx_78f45e976cf3.
Owner/review author Codex; reviewed author Claude. Evidence branch
agent/codex/supervision-20261104-r5-plan, base 4f53b5ab. Required policy/doc versions
and initial review are recorded in the separate audit commit
**a8542f04b5c3bcc8de1c7c0c75d1c9525449d455**. No Claude code or board was edited
by this reviewer. Rescore document now **1.21.1**, Claude History **1.0.1**.

## Exact observed refs and verdict

At KST 14:33-14:34, GitHub PR readback and an actual fetch confirmed:

| Ref | Exact head | Independent conclusion |
|---|---|---|
| integration/all-agents-unified | 03e17c31cf535008d39534aaa80d3ae274bd75cc | train 78 is already landed |
| PR400 | 611a9aab494e6f61825f7a96cfef0615b5b7cb7c | unchanged; earlier acceptance remains limited to Node-leaf-only console projection, not whole trust-path health |
| PR403 | f42c42595ee5c8389d4c66328d3695a30bd91605 | **accept historical-state correction**, with CI/landing acceptance still blocked |
| PR402 | b5b8ca68398517f6227a81caac02654a848c8b1d | Codex correction source; independent Claude review and required CI are separate pending gates |

The first fetch mistakenly used nonexistent `integration`, exit **128**. A second
request combined the correct integration ref with a guessed nonexistent Claude
branch and also exited **128**; neither supports a remote-state conclusion. The
correct command `git fetch origin integration/all-agents-unified refs/pull/403/head`
then exited **0**, and the exact refs above were read directly. This separates
operator command mistakes from actual product/test outcomes.

The four-file diff from 583453a2 to f42c4259 is documentation only. It explicitly
dates the old 6fc0428b unlanded observation at 11:04 KST, records the later 12:08:42
KST push to 03e17c31, and replaces the old operational next action with the supported
fresh isolated namespace path. It attributes the worker's read-only findings to
Codex rather than inventing Claude remeasurement. PR403 continues to stack on
PR400; **400 must precede 403**. This is a review of f42c4259, not inherited approval
of the superseded 583453a2 wording.

The correction carries the earlier accepted score while post-landing verification
is red and retains **3,475/4,800 = 72.40%** as the calculated Z result, rather than
declaring new technical acceptance. That distinction is defensible under the
required acceptance gates. The old title/table are historical and must not be
quoted as today's remote branch topology. No full-program score or strict task
status rises from this documentation correction or from two observation-only Nodes.
Strict original count remains **2 done / 4 blocked / 42 planned / 0 ready**.

The correction's live-decision next action is a 13:26 snapshot. Coordinator later
released the measured r5 bootstrap; its execution is now recorded separately in
[[2026-11-04_14-09-02_KST_r5_preparation_and_execution_Codex]]. Current next action
is independent review of that outcome and reviewed expiry prevention, not another
request for routine user approval and not execution of untouched-r4 partial recovery.

## Reproducible checks and actual CI runtime

A separate owned shared clone was detached at exact f42c4259. Windows **CPython
3.14.7**, at KST 14:34-14:35:

- `python <exact-f42-clone>/tools/check_docs.py`: **exit 0**, 1167 versioned docs.
- `python <exact-f42-clone>/tools/check_ontology.py`: **exit 0**, all stated ontology
  fixtures, mappings and mirror checks passed.
- Git diff confirmed only the four declared document paths changed, **exit 0**.

Hosted readback (source and actual tested checkout are distinct):

| Run | Source head / actual checkout | Runtime | Actual result |
|---|---|---|---|
| PR403 Docs 41773326979 | f42c4259 / 4b6feb669e90968600b8a96f2b8242774c1cb3b9 | Linux CPython 3.12.16 | success |
| PR403 Backend 41773326973 | f42c4259 / same 4b6feb66 PR merge | Linux CPython 3.12.15 and 3.14.9 | each **42 failed / 8341 passed / 75 skipped / 2 deselected / 9 errors**, failure |
| PR403 Desktop 41773326984 | f42c4259 PR check | browser harness | failure; no browser acceptance inferred |
| PR403 Core 41773326931 | f42c4259 PR check | not executed | skipped, not PASS |
| landed integration Backend 41765284237 | 03e17c31 / actual 03e17c31 | Linux CPython 3.12.15 and 3.14.9 | each **42 failed / 8325 passed / 75 skipped / 2 deselected / 9 errors**, failure |

The integration Backend failure is actual post-landing evidence, not an unlanded
claim. Partition horizon/expired AC-11 fixture/VF-CL registry drift are assigned
corrections owned by the coordinator and the appropriate code authors; this review
does not waive those exits or promote a local docs result to product acceptance.
The earlier AC-11 artifact comparison, canonical observation digest, shared target
blob and MEASURED_FAIL limitations remain unchanged by this four-file correction.

CI metadata, exact checkout/runtime extraction, test summaries and protected raw-log
hashes are in `Evidence/r5-bootstrap-plan-20261104/ci-head-readback.json`. Superseded
PR402 b1 Core run **41773055392**, actual PR merge 0b1b523f, CPython **3.12.16**,
had **42 failed / 8711 passed / 46 skipped / 2 deselected / 9 errors**. Its JUnit
independently proves all **28 scheduler cases executed and passed on hosted Linux**
with zero skips, including the executable-symlink witness; the whole run failed,
and it does not approve later N1/N2/all-member revisions. The superseded 5933 Core
run **41777296712** was cancelled, not successful.

Next owner/action: coordinator routes exact b5b8ca68 to Claude and reads new Backend
**41779908473**, Core **41779908364**, Docs **41779908269** and Desktop
**41779908545**. At KST 14:39 Docs is successful, Backend/Core are in progress and
Desktop has failed. No scheduler registration or integration merge is released
by this review. Shared boards/registry/Obsidian remain coordinator-owned.
