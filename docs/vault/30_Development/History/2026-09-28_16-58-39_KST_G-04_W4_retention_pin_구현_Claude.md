---
title: "G-04 W4 retention pin 구현 (PR #196)"
version: "1.1"
status: "review"
author: "Claude"
updated: "2026-09-28T16:58:39+09:00"
---

# G-04 W4 retention pin 구현 (PR #196)

branch `agent/claude/g04-w4-retention-pin`, base #191(`agent/claude/g04-w2-model-version-register`) 최신 head merge. 설계 G-04·G-05 business lane route 통합 설계 v1.2.1(PR #183) §5-3(Codex F3, v1.2 고정)의 첫 구현.

## 한 것

- `POST /v1/projects/{project_id}/models/{model_id}/versions/{version}/retention-pin` — `services/lineage.py::pin_retention` 변경 0. 한 READ COMMITTED tx: `SET LOCAL lock_timeout`(`Settings.business_lock_timeout_ms`) → idempotency 직렬화점 → live canApprove → **app clock 1회 읽기**(Codex #191 F3·#196 F2) → 원장 → parent 결속 후 ModelVersion `FOR UPDATE + populate_existing`(#167 `_locked_version` 공유) → canApprove 재확인 → `max(current, until)`(route는 `pinned is row` 단언) → audit + ledger.
- 짧거나 같은 `until` = 200 no-op(`extended: false`). lock timeout(55P03)/deadlock(40P01) = `SYS-0001/503/retryable=true`, 기록 0.
- `RetentionPinRequest`(aware datetime)·`RetentionPinResponse` strict + 생성 contract. migration 없음.

## 검증

- PG-free `tests/core/test_model_retention_pin_route.py`: 공용 `.venv`(Python 3.14, FastAPI 0.141.1) 42 passed. mock Session은 lost-update 사살로 세지 않는다.
- 실 PG `tests/integration/test_model_retention_pin_real_pg.py`(hosted): 독립 연결 row holder + `pg_stat_activity.wait_event_type='Lock'` barrier. 관측: 역순 commit 두 경우 `max(old,a,b)`, **release 먼저 → pin 대기 후 released row 연장**, **pin 먼저 → release(#167 write path: `_locked_version` + `release_model_version`, 독립 세션) 대기 후 새 pin을 보고 released**, 예산 초과 503 + 재시도 200, 같은 키 동시 2건 원장 1행, shorter/equal no-op, 거부들.
- **NOT_OBSERVED**: verify↔pin 경합 — W3 verify는 trusted-worker 측정 Evidence seam 전 보류(설계 v1.2.1)라 이 PR에서 측정하지 않았다. §5-3 표의 "contention 전부"가 아니라 위에 적힌 항목만 관측됐다.
- 무토큰 401/익명 denial은 공유 경계 #195 소관; 이 branch의 실 PG 시험은 "200 아님·기록 0"만 관측한다.

## 다음

Codex 재검토(#196 수정 요청 1~3 반영 head) → hosted 결과 인용 → 승인 뒤 draft 해제. W3 seam 결정 후 verify↔pin 측정 추가.
