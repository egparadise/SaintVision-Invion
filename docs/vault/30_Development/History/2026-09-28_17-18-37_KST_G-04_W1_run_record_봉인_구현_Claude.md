---
title: "G-04 W1 run record 봉인 구현 (PR 7/8)"
version: "1.0"
status: "review"
author: "Claude"
updated: "2026-09-28T17:18:37+09:00"
---

# G-04 W1 run record 봉인 구현 (PR 7/8)

branch `agent/claude/g04-w1-seal-record`, base #184 head `c47811b2`(R1 helper `run_in_project`·공유 403 denial audit #195). 설계 G-04·G-05 business lane route 통합 설계 v1.2.1(PR #183) §5-2(Codex F2, v1.2 고정)의 구현.

## 한 것

- `POST /v1/projects/{project_id}/runs/{run_id}/record` — `services/records.py::seal_run_record` 시그니처 변경 0. **integrity 값은 서버 파생**: 봉인 artifact 집합 = run의 `status='active'`이고 checksum 있는 artifact 전부(`artifact_id` 오름차순 `FOR UPDATE + populate_existing`), checksum·`bundle_id`(run의 최신 bundle)·`bundle_hash`·`workload_spec_sha256`·`component_versions`(run의 evidence envelope 값 우선, bundle 값은 없는 키만) 모두 잠근 정본에서. request는 `roles: {artifact_id: role}`만 — 집합 밖 id는 `GRAPH-0002/409`, 미매핑은 `other`.
- 순서(한 READ COMMITTED tx): preflight canApprove(별 tx) → body → `SET LOCAL lock_timeout` → IDEM-6 직렬화점 → live canApprove → app clock 1회 → 원장(replay / 409) → `runs` 행 `FOR UPDATE + populate_existing` + workload.project 재결속 + terminal·termination_reason 재확인 → live canApprove 재확인 → workload·bundle·evidence·artifact(잠금) → 기존 record 있으면 **canonical seal intent**(정렬된 (artifact_id, role, checksum) 집합 + 파생 값)와 저장 record+pin 비교: 같으면 자연 멱등 200, 다르면 409 → 없으면 service 호출·audit·ledger 같은 tx.
- `uq_run_records_run_id` IntegrityError는 409로(tx rollback, 부분 pin 0); 그 밖 IntegrityError·OperationalError는 위장하지 않음. lock timeout/deadlock `SYS-0001/503/retryable`.
- IDEM-6 helper `serialise_idempotent_write`는 #191(W2)의 텍스트를 그대로 `deps.py`에 이식(같은 hunk라 #191 merge 시 충돌 0 예상). `Settings.business_lock_timeout_ms`는 #196(W4)과 같은 텍스트.
- `RunRecordSealRequest` strict(+contract). migration 없음.

## 검증

- PG-free `tests/core/test_run_seal_route.py`: 공용 `.venv`(Python 3.14, FastAPI 0.141.1) 43 passed. mock Session은 lost-update 사살로 세지 않는다.
- 실 PG `tests/integration/test_run_seal_real_pg.py`(hosted): (a) 같은 intent 동시 2건(직렬화점 barrier, 다른 키) → record 1·pin 집합 1·양쪽 200 동일; (b) 다른 intent 동시 2건 → 승자 200·패자 409·pin은 승자 집합 전체·ledger 1; (c) run 잠금 holder가 terminal 전환 commit → 봉인은 기다린 뒤 최종 상태 봉인(미종료면 409); (d) 잠금 대기 중 membership 회수 → 잠금 뒤 재검사 403·기록 0·denial 1행(action template); 예산 초과 503; 무토큰 401 + anonymous denial; 서버 집합·role·replay·409들.
- NOT_OBSERVED: deadlock(40P01) 실측은 하지 않았다(55P03 경로만 실 PG; 40P01은 PG-free 분류 시험).

## 다음

Codex 검토 → hosted 인용 → 승인 뒤 draft 해제. #191 merge 시 `deps.py` helper hunk 동일성 확인.
