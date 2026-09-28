---
doc_id: "HIST-CLAUDE-2026-09-28-S10-ST-EVIDENCE-MAP"
title: "S10-ST Evidence 대응표 — 불변 버전·보존 pin·adapter conformance·배포 digest 대응, 공백 G1(재등록 거부 시험 1 + PG-free 불변식 pin 4)·G2(route → 카드 ar/#152)·외부 2 (카드 aw)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:36:09+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-ST"]
tags: ["S10-ST", "AC-10", "evidence", "claude"]
---

# S10-ST Evidence 대응표 (2026-09-28, 카드 aw)

산출물: [[S10-ST Model immutable version·보존 pin Evidence 대응표]]. 이미 있는 것을 대응시키고 공백만 골라냈다.

## 1. 확인 방법(실제 수행한 것만)

`grep`/`sed`로 `src/saintvision/services/lineage.py`(register/verify/pin/release/deploy guard 행), `migrations/versions/0004_s10_lineage.py`(유일성·CHECK·LIFECYCLE_UPDATE_COLUMNS·partial unique), `0043_replica_retention.py`, `src/saintvision/adapters/model_import.py`·`conformance.py`, `services/control-plane/src/inv/app.py:449` route, 시험 파일별 `def test_` 목록을 읽었다. run ID는 이 세션에서 관찰한 hosted Backend run(36351202242·36363486696·36364528281)과 09-22 로컬 실PG 228 기록만 인용.

## 2. 결과

- 대응: 불변 버전 5·보존 pin 5·adapter 4·배포 digest 3 항목을 file:line + run ID로 대응.
- 공백 G1: "같은 version에 다른 digest 재등록 거부" 시험 부재(DB 제약 `uq_model_versions_model_id_version`은 있음) → `tests/test_lineage.py::test_the_same_version_with_a_different_digest_is_refused`(postgres, hosted Backend) + `tests/test_model_version_invariants_static.py` 4건(PG-free: 유일성 선언·lifecycle UPDATE 컬럼에 identity 없음·`pin_retention` 연장만·release/deploy guard 문구). pinned 버전 삭제 거부는 기존 append-only 시험이 이미 덮음.
- 공백 G2: business lane route·lineage 조회 API 부재 → 카드 ar·#152 이관. E1 실 Provider(CX-02)·E2 MLflow → BLOCKED_EXTERNAL.
- 판정 논리 복제 없음.

## 3. 게이트·인계

PG-free `tests/test_model_version_invariants_static.py` 4 passed; `test_lineage.py` collect-only 31 케이스(문법·import 0 오류; 실행은 hosted Backend). check_docs·single_source·ontology 2·bindings·freshness·export_schemas --check·diff --check exit 0. owner Claude / reviewer Codex / 병합 금지. worktree 재사용. 다음 첫 행동: Codex 검토 → Backend run id·G1 실행 확인.
