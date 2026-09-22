---
doc_id: "CODEX-S02-S03-INDEPENDENT-REVIEW-20260922"
title: "S02·S03 Claude 증거 독립 검토"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Codex (independent reviewer)"
updated: "2026-09-22T09:00:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S02", "S03", "review", "real-pg", "evidence"]
---

# 판정

S02와 S03 모두 **닫지 않는다**. 작성자가 분리한 사용자 입력 대기와 독립적으로
실행 가능한 증거는 타당하지만, 각 task의 요구 증거와 선행 조건 전체가 충족된 것은
아니다.

## 독립 실행 provenance

- 통합 tip: `f7462e09` (`integration/all-agents-unified`에 계약 커밋을 올린 뒤의 tip)
- 작업 위치: `C:\Project\SaintVision-Invion\.worktrees\codex-integration-merge`
- 인터프리터: `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe`
- PostgreSQL: 소유 라벨 `ai.saintvision.owner=codex`인 일회용
  `pgvector/pgvector:pg16`, 전용 포트, 실행 후 제거
- 두 실행 모두 `INV_TEST_ADMIN_DSN`으로 위 DB를 사용했으며 skip 0이다.
- 보호 컨테이너와 다른 agent의 자원은 건드리지 않았다.

## S02 증거 대조

| 영역 | 요구 범위 | 독립 확인 | 판정 |
|---|---|---|---|
| S02-BE | OIDC·mTLS 등록·heartbeat, 실제 API·인증 실패 | `tests/test_api.py` 및 focused 세트 포함 **91 passed / 0 skipped**. 노드 등록/읽기와 bootstrap token 재사용·미지 토큰·테넌트 결속 거부가 실제 PG에서 재현됨 | 소프트웨어·DB 증거 충족. 실 IdP issuer/audience/JWKS와 물리 mTLS/heartbeat는 미충족 |
| S02-DB | User·Node·Capability·Snapshot | focused 세트의 Node/Capability 계약과 API→DB 경로가 91건 안에 포함됨 | 실PG 증거 충족. S01 선행 과제와 task registry의 전체 증거 게이트가 남아 닫지 않음 |
| S02-ST | 제공 폴더·DataLocation 카탈로그 | storage API/catalog와 계약 시험이 91건 안에 포함됨 | 카탈로그 소프트웨어·DB 증거 충족. 실제 허용 폴더/장비 인수와 브라우저 여정은 미충족 |

명령:

```text
$env:INV_TEST_ADMIN_DSN='[redacted disposable DSN]'
$env:PYTHONPATH='src;services/control-plane/src'
C:\Project\SaintVision-Invion\.venv\Scripts\python.exe -m pytest -q
  tests/test_api.py tests/test_storage_api.py tests/test_storage_catalog.py
  tests/test_node_auth.py tests/core/test_storage_list_response_contract.py
  tests/core/test_storage_observation_contract.py
  tests/core/test_node_page_detail_response_contract.py --tb=short
```

실행 결과: **91 passed, 0 skipped, exit 0, 164.11초**.
Claude 문서의 91 수치는 SHA `a8c979d0` 작성자 실행이었고, 현재 tip에서도 같은 수가 재현됐다.

## S03 증거 대조

| 영역 | 요구 범위 | 독립 확인 | 판정 |
|---|---|---|---|
| S03-DB | Workspace·Workload·Run·Evidence, 허용/거부·exit code·증거 ID | 문서가 열거한 13개 시험 파일을 현재 tip에서 실PG 실행. 성공 증거·증거 없는 성공 거부·상태/attempt/log/approval/workspace 경계를 확인 | 현재 tip 기준 **197 passed / 0 skipped / exit 0**. DB 증거는 충족하지만 S02 선행 게이트와 독립 검토 절차가 남아 닫지 않음 |
| S03-ST | 볼륨·Artifact 기본 전송 | `result_view.py`가 저장 파일이 아니라 DB receipt envelope의 `output_bytes`를 다운로드 본문으로 사용함을 소스 확인. storage metadata의 hash/size와 전송 본문 정본은 분리돼 있음 | 다운로드 정본 선택(#5)이 선행 결정이므로 Claude의 착수 보류 판단이 맞음 |

S03 실행 명령:

```text
$env:INV_TEST_ADMIN_DSN='[redacted disposable DSN]'
$env:PYTHONPATH='src;services/control-plane/src'
C:\Project\SaintVision-Invion\.venv\Scripts\python.exe -m pytest -q
  tests/test_run_state.py tests/core/test_run_result_contract.py
  tests/core/test_run_attempt_contract.py tests/core/test_run_log_contract.py
  tests/core/test_run_approval_observation_contract.py tests/core/test_run_state_alignment.py
  tests/core/test_workspace_api_boundary.py tests/core/test_workspace_response_contract.py
  tests/core/test_workspace_manifest.py tests/test_execution.py
  tests/test_execution_readiness.py tests/test_vf_evidence.py
  tests/test_evidence_case_inventories.py --tb=short
```

현재 결과: **197 passed, 0 skipped, exit 0, 117.58초**.
Claude 문서의 **192 passed**는 SHA `9f43c59d` 당시 수치다. 현재 tip의 차이 5건은
Codex가 추가한 `ControlRunDetail` fixture/음성·서빙 앵커 시험 5건이며, 원래 192건을
현재 수치와 섞어 보고하지 않는다.

## 결론과 다음 조건

- S02-BE: 실 IdP와 물리 Node 인수가 필요하다.
- S02-ST: 실제 제공 폴더/경로와 장비 인수가 필요하다.
- S02-DB: 사용자 입력은 필수로 보이지 않지만, task registry의 S01 선행 및 브라우저/전체 증거 게이트가 남아 있다.
- S03-DB: 실PG 증거는 현재 tip에서 충족했지만 S02 선행과 전체 독립 검토가 남아 있다.
- S03-ST: 다운로드 본문 정본을 DB receipt로 할지 저장 파일로 할지 사용자 결정(#5)이 먼저다. 이 결정을 Codex가 임의로 바꾸지 않는다.

따라서 Claude의 사용자 대기 분류는 과도하지 않다. 다만 S02-DB와 S03-DB의
실PG 증거는 사용자 입력 없이 재현 가능하다는 것을 이번 독립 실행으로 확인했다.
