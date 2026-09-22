---
doc_id: "HIST-CODEX-S05-CARD32-PROVENANCE-001"
title: "S05 Card32 측정 provenance 도달성 보강"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T15:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["history", "s05", "provenance", "evidence", "git-blob"]
---

# S05 Card32 측정 provenance 도달성 보강

## 검토 결과와 보정

Claude Card32 조건 1에 따라 Card24 evidence의 `4c8a7363…`와 Card25 evidence의 `6c389a1d…`를 확인했다. 두 객체는 이 Orca worktree의 local object DB에는 남아 있으나 `origin/integration/all-agents-unified`의 조상이 아니므로 GitHub 재현 anchor로 사용할 수 없다.

두 실행 head의 측정 코드와 origin integration에서 도달 가능한 `c042b3fce80cd246ba5aeb77a6a28d2ca4cdb5ff`를 `git rev-parse <sha>:<path>`로 대조했고 다음 blob이 모두 같았다.

| 파일 | Git blob OID |
|---|---|
| `services/control-plane/src/inv/placement.py` | `8be573eed075812e04d271b3e1237351fde991e2` |
| `services/control-plane/src/inv/db.py` | `2e37b85eb96231e561bc08bf84a1673f9120f80e` |
| `tests/integration/test_placement_benchmark.py` | `46f0ab4878787975e1d60fdefb3927084008ed51` |
| `tests/integration/test_placement_short_commit.py` | `b29689ef4d004f403914959d9d63f14a539f9826` |
| `tools/placement_benchmark.py` | `9a8430ad684f7dfbda0c8aca7f3c289acc7bf4e5` |

따라서 두 evidence의 `codeSHA`를 `c042b3fc…`로 보정하고 당시 local 위치는 `executionHeadAtRun`에 보존했다. `codeSHA`는 실행 commit 자체라는 주장이 아니라 **실행과 측정 파일 blob이 동일하고 origin integration에서 도달 가능한 코드 provenance anchor**다. 사양과 원 History에도 같은 경계를 기록했다.

## 범위와 정직성 경계

- 문서·Evidence provenance만 고쳤다. 제품 코드, 계약, migration, registry, ontology 상태는 바꾸지 않았다.
- Card24/25 원 수치와 판정은 바꾸지 않았다.
- 새 benchmark wave, PostgreSQL 시험, 전체 suite, build, browser는 실행하지 않았다.
- Claude Card32가 요구한 sampler-off 재현 wave 조건은 그대로 남아 있으며 이 보강이 그 wave를 대체하지 않는다.

## 검증

착지 후보에서 다음을 실행했다.

| 검증 | 결과 |
|---|---|
| Evidence JSON 2건 `ConvertFrom-Json` | parse 성공 |
| `python tools/check_docs.py` | 892 versioned documents, exit 0 |
| `python tools/check_contract_bindings.py` | 54 fixtures, 19 response types, 14 replay guards, exit 0 |
| `python tools/check_ontology.py` | 48 task mappings, 4 rejected invalid fixtures, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | 18 pairs, exit 0 |
| `PYTHONUTF8=1 python tools/check_frontend_integrity.py` | 0 violations, exit 0 |
| `git diff --check` | exit 0 |

제품 시험이나 부하를 대신 실행하지 않았고, 이 표는 문서·계약 정합 게이트만 보고한다.
