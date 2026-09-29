---
doc_id: "HIST-CLAUDE-2026-09-28-S09-DB-ST-EVIDENCE-MAP"
title: "S09-DB·S09-ST Evidence 대응표 — 불변 Context·RunRecord·eval·Artifact 연결 대응, 공백 G1 route 설계 대상·G2 Windows 게이트 NOT_OBSERVED·외부 2, 구현 추가 0 (카드 ay, docs-only)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:42:12+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S09-DB", "S09-ST"]
tags: ["S09-DB", "S09-ST", "AC-09", "evidence", "claude", "docs-only"]
---

# S09-DB·S09-ST Evidence 대응표 (2026-09-28, 카드 ay)

산출물: [[S09-DB·S09-ST Evidence 대응표]]. 이미 있는 것을 대응시키고 공백만 골라냈다. 구현·시험 추가 0.

## 1. 확인 방법(실제 수행한 것만)

`grep`/`sed`로 `src/saintvision/services/context.py`·`records.py`·`evaluation.py`·`eval_execution.py`의 함수·guard 행, `migrations/versions/0003_s09_context_eval.py`의 `NEW_APPEND_ONLY`·유일성·CHECK·GRANT 행, `src/saintvision/api/v1`의 서비스 import 유무, 시험 파일별 `def test_` 목록을 읽었다. #131 collector의 8조항 매핑과 #113(Gemini FE 매트릭스) 파일을 참조했다. run ID는 이 세션에서 관찰한 Backend run(36351202242·36353897541)과 09-22 로컬 실PG 76/21 기록만 인용.

## 2. 결과

- 대응: 불변 Context 5·RunRecord 5·eval 7·Artifact 연결 5 항목을 file:line + run ID로 대응(#131 8조항과 정합).
- 공백: G1 business lane HTTP route 부재 → **설계 대상**(카드 ar/#152 lane과 같은 부류, 코디네이터 배정); G2 `test_results.py` Windows 게이트 → NOT_OBSERVED(로컬), hosted 실행됨; E1 AC-09 제품 지표·E2 실 Provider → BLOCKED_EXTERNAL.
- 작은 PG-free 불변식 시험으로 메울 행동 공백 없음(재기록 거부·digest·역할 pin·덮어쓰기 탐지·gate 위반이 전부 실PG 시험으로 단언됨) → docs-only.

## 3. 게이트·인계

check_docs·single_source·ontology 2·bindings·freshness·export_schemas --check·diff --check exit 0. 코드 변경 0. 로컬 실 PG·Docker·전체 suite 없음. owner Claude / reviewer Codex / 병합 금지. worktree 재사용. 다음 첫 행동: Codex 검토.
