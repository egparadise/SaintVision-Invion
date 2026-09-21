---
doc_id: "HISTORY-2026-09-22-WRITE-RESPONSE-FOLLOWUPS-CODEX"
title: "후속 요청 핸들을 만드는 쓰기 응답 추가 결속"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-22T02:31:00+09:00"
source_of_truth: "Git"
---

# 후속 요청 핸들을 만드는 쓰기 응답 추가 결속

## 범위와 판정 기준

- 작업 카드 `THREAD-2026-09-22-WRITE-RESPONSE-FOLLOWUPS`; owner Codex, independent reviewer pending.
- Claude 위험 재판정 문서 `CLAUDE-WRITE-RESPONSE-RISK-REJUDGE-001`과 commit `945496234f1aa00077f1ea86281a05118c145fed`를 기준으로 현재 route와 consumer를 다시 확인했다. 판정 렌즈는 응답의 값이 다음 요청의 대상·입력·경로를 정하는가이다. 이미 상위로 묶인 create project, discovery admission, member role, resource offer, workspace status의 다섯 응답에 더해 이전의 여섯 번째 `set_workspace_status`도 현재 response_model로 묶여 있다.
- 구현 branch `agent/codex/write-response-followup-contracts`, base integration `aa67de8c6f6a79798cebe58f685456939d70cdf7`, code SHA `f0a96dc81dae0bcb7741ea76c8a2c254f2a566fe`. Worktree `C:/Project/SaintVision-Invion/.worktrees/codex-write-response-followups`; 코드 검사 시 clean. Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6, Node v24.17.0, Windows 11, 실행자 Codex, KST 약 02:18–02:20. PostgreSQL DSN 없음.

## 추가로 확인된 상위 위험 두 건

| 응답 | 후속 입력이 되는 값 | 변경 |
|---|---|---|
| `POST /v1/nodes` | 등록 응답의 새 `nodeId`가 이후 heartbeat 등 노드 작업의 대상이 된다. 내부 `_node_body`는 `NodeResponse`로 검증했지만 route wrapper 자체에는 FastAPI 응답 계약이 없었다. | 이미 존재하던 `NodeEnrollResponse`를 route `response_model`로 연결했다. fixture로 성공 본문을 고정하고, nested response에 추가 필드를 주입하면 거부되는 시험을 추가했다. |
| `POST /v1/storage/contributions` | 새 `contributionId`가 activation/revoke의 대상이고 `normalizedPath`가 등록된 저장 경로를 식별한다. 일반 경로는 `ContributionResponse` 생성자를 사용하지만 idempotency replay는 저장된 raw dict를 그대로 반환해 그 검증을 우회했다. | `ContributionRegistrationResponse` wrapper와 생성 JSON Schema를 추가하고 route `response_model`을 연결했다. 성공 응답 fixture와 invalid idempotency replay 거부를 시험한다. |

두 계약은 `src/saintvision/api/schemas.py`의 Pydantic 모델에서 `tools/export_schemas.py`가 생성한 JSON Schema로 이어진다. `export_schemas.py --check`가 47개 스키마를 검사한다. 프런트 화면 코드는 변경하지 않았다.

## 더 높은 위험의 잔여 여부

현재 확인한 쓰기 응답 중 위 두 건 외에 새 식별자·handle·전이집합·경로로 다음 요청의 대상을 정하는 미결 응답은 찾지 못했다. 따라서 이 기준의 상위 미결은 없다. Claude 표에 남은 항목은 다음 이유로 하위에 유지한다.

- `PUT /workspaces/{id}/tool`은 tool/usability 판단을 돌려주지만 새 대상 ID나 경로를 만들지 않는다. 실행 가능성 표시의 정확도 문제로 남긴다.
- project/user status 응답은 상태 표시이고 후속 허용 전이 집합을 내지 않는다.
- member removal, candidate decline, contribution activation/revoke는 요청이 이미 지정한 ID의 상태 수령증이다. 응답이 새로운 다음 대상 핸들을 발급하지 않는다.
- heartbeat와 liveness sweep 및 discovery announcement 응답은 요청의 기존 노드 식별자·상태·개수만 확인하며 새로운 후속 대상 핸들을 제공하지 않는다.

이 판정은 잔여 항목을 위험이 없다고 선언하는 것이 아니다. 응답 모양 결속의 우선순위가 위 두 후속 핸들 응답보다 낮다는 뜻이다.

## 검증 증거

검사는 `tools/provenance.py --executor Codex`로 실행했다. 실제 명령과 absolute interpreter는 아래와 같다.

| 명령 | 결과 |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/core/test_write_response_contracts.py -q` | exit 0, 33 passed, 2 framework deprecation warnings. 기존 다섯 write cases와 신규 두 cases의 fixture, route success, invalid response 거부를 실행했다. |
| `.venv/Scripts/python.exe tools/export_schemas.py --check` | exit 0, 47 schemas match. |
| `.venv/Scripts/python.exe tools/check_contract_bindings.py` | exit 0, 38 fixtures each referenced by a test, 12 kernel response serving anchors. 이 검사기는 saintvision route anchors를 세지 않으므로 새 route 결속 근거로 오인하지 않는다. |
| `.venv/Scripts/python.exe -m pytest tests/test_api.py::test_enrolled_node_is_registered_and_readable tests/test_api.py::test_contribution_is_registered_with_a_normalised_path tests/test_api.py::test_contribution_registration_is_idempotent -q` | exit 0, 3 skipped, 각각 `INV_TEST_ADMIN_DSN is absent; PostgreSQL tests not run`. 실 DB service와 idempotency 저장소 경로는 미검증이다. |

검사는 pinned code SHA `f0a96dc81dae0bcb7741ea76c8a2c254f2a566fe`의 clean tree에서 직접 실행했다. 당시 원격 integration은 연속 변경 중이어서 검사가 실행된 순간의 `origin/integration` ref SHA를 provenance 출력 그대로 구분해야 한다. 작성자 실행이며 독립 검토 또는 CI 통과라고 표시하지 않는다.

### 되돌림 대조

- `nodes.py`의 `NodeEnrollResponse` response_model을 제거하자 `test_high_risk_write_route_refuses_invalid_service_response[node-enroll-…]`가 실패했다. 시험은 route가 잘못된 nested node field를 `201`로 내보낸 것을 관측했다.
- `storage.py`의 `ContributionRegistrationResponse` response_model을 제거하자 같은 파라미터 시험이 실패했다. 시험은 schema를 우회한 idempotency replay 응답이 `201`을 받는 것을 관측했다.
- 두 변형을 각각 복구한 뒤 전체 관련 core 시험은 33 passed였다. 이는 통과 결과와 별개로 각 route response_model이 시험에 실질적 영향을 준다는 증거다.

## 브랜치 ref 정리

이전 `agent/codex/response-freshness`는 이력 불일치 원격 ref를 force-update하지 않았다. 그 branch의 코드 커밋은 integration 이력에 있고 후속 문서 변경도 integration에 포함된 것을 확인한 뒤 해당 원격 ref를 삭제하고 내 local branch 및 worktree를 정리했다. 현 확인에서 그 이름의 local/remote ref와 worktree는 없다. 이번 branch는 최신 integration `aa67de8c`에서 새로 분기했고 integration에 fast-forward 가능한 한 commit이다. 다른 Agent의 branch나 worktree는 건드리지 않았다.

## 다음 담당과 첫 행동

1. Claude가 integration의 최종 landed SHA에서 node enrollment 및 contribution registration response binding을 독립 검토한다.
2. disposable PostgreSQL 16+ DSN을 사용할 수 있을 때 위 세 DB-backed API cases를 실행한다. DSN 부재 skip은 성공으로 집계하지 않는다.
3. 이 기준에서 상위 응답은 닫았다. 하위 receipt/status 응답은 현 증거로 우선순위를 유지하고, 화면에서 새 후속 handle 소비가 발견되면 다시 올린다.

## PostgreSQL API 실측 및 응답 계약 되돌림 대조

- 작업 카드 `THREAD-2026-09-22-WRITE-RESPONSE-FOLLOWUPS`; owner Codex, reviewer pending. 이 후속은 integration 기준 `b3a14db6286cbcb037ff8aa423c961ce1f2420c7`에서 `agent/codex/write-response-followup-postgres` 브랜치로 진행했다. 실행 위치 `C:/Project/SaintVision-Invion`; Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6; Windows 11; executor Codex.
- 세 API 시험은 이전 DSN 부재 skip에서 실제 PostgreSQL 실행으로 바뀌었다. 기존 node enrollment/readback, contribution normalized-path, contribution idempotency 시험에 성공 응답의 canonical Pydantic 검증을 넣었다. 같은 contribution POST를 반복해 DB에 저장된 두 번째 replay도 같은 contract 객체임을 확인한다.
- DB 경로의 응답모델 anchor도 각각 검증했다. 노드 시험은 실제 enrollment을 수행하고 DB commit 후 route 응답에 합성 미지원 필드를 주입해 `ResponseValidationError`를 기대하며, owner connection으로 실제 node row가 남았음을 확인한다. contribution 시험은 실제 첫 등록과 durable idempotency row를 만든 뒤 그 행의 응답 객체만 추가 필드로 변형하고 동일 요청의 DB replay를 실행해 `ResponseValidationError`를 기대한다. 이 두 대조는 응답 모델 제거 시 실제 DB 시험 자체가 실패하는지를 확인한다.
- KST 2026-09-22 02:28:44 및 02:29:59에 다음 명령을 `tools/provenance.py --executor Codex --`로 감싸 실행했다: `.venv/Scripts/python.exe -m pytest -q -rs tests/test_api.py::test_enrolled_node_is_registered_and_readable tests/test_api.py::test_node_enrollment_db_route_rejects_invalid_response_shape tests/test_api.py::test_contribution_is_registered_with_a_normalised_path tests/test_api.py::test_contribution_registration_is_idempotent tests/test_api.py::test_db_idempotency_replay_is_checked_by_response_contract`. 최종 exit 0: **5 passed, 0 skipped, 0 failed/errors** (13 framework warnings). PostgreSQL 16 `pgvector/pgvector:pg16` disposable 컨테이너와 fixture가 생성한 전용 `inv_backend_test_<random>` 데이터베이스를 사용했다. DSN 원문이나 인증 정보는 기록하지 않았다.
- 실 DB 되돌림 대조: 02:29:28에 `/nodes` `NodeEnrollResponse` anchor만 제거하자 `test_node_enrollment_db_route_rejects_invalid_response_shape`가 **1 failed**(pytest exit 1)했다. 복원 후 02:29:45에 contribution `ContributionRegistrationResponse` anchor만 제거하자 `test_db_idempotency_replay_is_checked_by_response_contract`가 **1 failed**(pytest exit 1)했다. 두 anchor를 복구한 최종 명령은 5/5 통과했다. 따라서 기존 idempotency DB 경로뿐 아니라 replay 응답 계약도 실제 경로에서 보호된다.
- 자원 격리/정리: 이름 `sv-codex-write-pg-c07b13e5bc4f4de3871df2b4ea72b06a`, image `pgvector/pgvector:pg16`, data 디렉터리 tmpfs, `127.0.0.1` 임시 포트. `ai.saintvision.owner=codex`와 고유 `ai.saintvision.write-response-db` 라벨 및 컨테이너 ID/생성 시각을 inspect해 소유를 확인한 뒤 해당 컨테이너만 제거했다. 제거 후 같은 ID inspect 결과 부재, daemon 수 48→49→48이었다. 보호 자원 `saintvision-lan-db-bff1a31d`, `saintview-orthanc`, `saintview-orthanc-h1`, `saintview-orthanc-h2`는 확인 당시 기존 상태 그대로였다.
- 동시 편집 경계: provenance에서 다른 agent의 미커밋 UI 파일들이 관측됐다. 이 실행은 이를 수정하거나 stage하지 않았고, 이 작업의 소유 파일만 변경 대상으로 삼았다. 기록 시점의 worktree는 공유 UI 변경 때문에 clean이 아니었다. 이 PG 증거는 작성자 실행이며 독립 검토, hosted CI, 운영 HTTP 인수로 표시하지 않는다.
- 결론: `NodeEnrollResponse`와 `ContributionRegistrationResponse`는 기존 세 DB 사례에서 실 PostgreSQL 서비스/HTTP 경로를 통과했고, 성공 객체와 저장된 재생 객체를 확인했다. 계약 anchor를 제거하면 두 신규 DB 부정 대조가 각각 실패하므로 세 개의 과거 skip은 이제 실행 근거로 대체됐다.
- 고정 SHA 재실행: commit `ce3ea282fbc57486fa0045c235be241843824577`에서 KST 2026-09-22 02:32:36에 위의 같은 pytest command를 다시 실행했다. Provenance에 SHA와 절대 인터프리터/환경이 기록됐고 결과는 exit 0, **5 passed / 0 skipped / 0 failed/errors** (13 warnings)였다. 그 시점 integration checkout은 dirty였으며 감지된 변경은 다른 agent의 UI 파일뿐이었다. 실행 코드는 해당 SHA였고, UI 변경은 stage/commit하지 않았다.
- 고정 SHA 재실행 자원 `sv-codex-write-pg-final-db08f341309e4e469010db0344cd579d` (ID `adc3206df99c30041988bce9c63cf63b82bbfb28e39251f82600249600d9cf6e`)도 고유 owner/task label 확인 후 제거했다. 제거 후 ID inspect에서 부재, daemon 수는 48로 복귀했다. 임시 DB 디렉터리는 tmpfs였고 DSN 원문은 기록하지 않았다.
