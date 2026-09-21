---
doc_id: "AUDIT-RUN-RETRY-PATH-CODEX-20260922"
title: "Run 재시도 경로 감사와 저위험 쓰기 응답 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-22T04:02:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["run", "retry", "response-contract", "static-audit"]
---

# Run 재시도 경로 감사와 저위험 쓰기 응답 계약

## 제품 실패 Run 재시도 판정

기준 SHA `044c343a518f7ec9f8ae83fd436a8a1da67486bd`에서 제품 소스의 Run·worker·queue 경로를 시험 파일과 구별해 정적으로 조사했다. 제품 코드나 retry wiring은 바꾸지 않았다.

**일반 failed Run을 다시 실행하는 제품 경로는 찾지 못했다.** `ModelRetryStore.prepare`는 failed model Run의 조건을 확인하고 child Run, 새 placement reservation, lineage와 outbox를 만든다. 그러나 `ModelRetryStore`는 앱 라우트나 worker assembly에서 import·생성·호출되지 않는다. 해당 클래스의 호출은 tests에만 있다. 따라서 이것은 유효한 구현/DB 시험을 가진 server-internal capability이지 현재 제품 retry 기능이 아니다.

비슷해 보이는 경로의 실제 역할은 다음과 같다.

| 관찰된 경로 | 실제 동작 | 일반 failed Run retry인가? |
|---|---|---|
| `DeliveryQueue` / `DeliveryWorker` | lease 만료나 전송 불확실 시 기존 command의 delivery를 다시 관찰한다. `execution_deliveries.attempts`는 전달 시도이며 `runs.attempt`는 최초 `queued` command가 실제 시작 권한을 얻을 때만 증가한다. terminal Run이나 불확실 command를 새 Run으로 재실행하지 않는다. | 아니오. 같은 command의 전달/receipt 확인이다. |
| `OutputIngestion` | 같은 command의 이미 생성된 output receipt를 재수집한다. `retry`는 ingestion 상태이고 Node 작업을 재실행하지 않는다. | 아니오. 결과 수집 재시도다. |
| Run 목록의 “다시 시도” 버튼 | `onRefresh()`로 목록을 다시 조회한다. | 아니오. 읽기 요청 재시도다. |
| `WorkspaceResume` API/UI | 특정 workspace Run이 `recovering`이고, 현재 attempt에 맞는 checkout/snapshot이 있고, lease가 해제됐으며, 다음 step과 별도 approval이 성립할 때 같은 Run의 다음 workspace step을 준비한다. | 제한된 workspace continuation이다. 일반 실패 재실행은 아니다. |
| `ShardRecovery` | 실패/취소 parent plan을 검증하고 같은 ordered workload로 새 child Run들과 새 approval을 만들어 세대 제한 내에서 대체 plan을 준비한다. | retry에 가까운 명시적 shard replacement capability지만 제품 route/assembly에서 생성·호출되지 않는다. 현재 사용자 경로가 아니다. |
| Run 생성 API | `EmptyRequest`를 받아 독립적인 draft Run을 만든다. 실패 Run의 workload/parent/attempt를 재사용하거나 retry lineage를 만들지 않는다. | 아니오. 새 Run 생성이다. |

결론적으로 **일반 실패 Run은 새 실행/명시적 workspace 또는 shard recovery가 별도로 성립하지 않는 한 failed 상태로 남는다.** 자동 worker retry는 전송·수집 계층에 한정된다. WorkspaceResume는 사용자에게 노출된 별도 다음-step 경로지만 엄격한 체크아웃·승인 조건이 있다. ShardRecovery와 ModelRetry는 구현되어 있어도 현재 제품 진입점이 없다. 기존 architecture 문서가 ModelRetry endpoint/auth binding을 후속으로 남겼으므로 이것은 우발 누락으로 단정하지 않으며 제품/업무 owner가 노출 여부를 결정해야 한다. 제품 연결은 하지 않았다.

### 검색 및 경계

`services/control-plane/src/inv`의 app route, `DeliveryWorker`, `DeliveryQueue`, `OutputIngestion`, `RunStore`, `WorkspaceAPI`, `WorkspaceResume`, `WorkspaceRecovery`, `ShardRecovery`, `ModelRetryStore`와 그 호출자를 저장소 전체에서 tests 제외 검색으로 대조했다. 별도로 `apps/web/src/features/runs`, `RunDetail`, `DeveloperStudio`의 retry/resume/run-create 동작을 읽었다. app route에서 `ShardRecovery` 구성/호출은 없고, `ModelRetryStore`도 제품 참조 0이다. 이는 tracked repository 기준의 정적 판정이며 실행 중인 외부 wrapper/배포 설정은 확인하지 않았다. Worker/DB 런타임 시험은 이번 감사 범위가 아니다.

## 저위험 raw-dict 쓰기 응답 결속

사용자가 이미 저위험으로 분류한 일곱 단순 수령증/상태 route만 계약 앵커로 묶었다. 위험 분류를 재판정하지 않았다.

1. `POST /nodes/{node_id}/heartbeats` — `HeartbeatAcceptedResponse`
2. `POST /nodes/liveness-sweeps` — `NodeLivenessSweepResponse`
3. `POST /discovery/announcements` — `DiscoveryAnnouncementResponse`
4. `DELETE /discovery/candidates/{announcement_id}` — `DiscoveryDeclineResponse`
5. `DELETE /projects/{project_id}/members/{user_id}` — `ProjectMemberRemovalResponse`
6. `PUT /users/{user_id}/status` — `UserStatusResponse`
7. `PUT /projects/{project_id}/status` — `ProjectStatusResponse`

각 모델은 strict/extra-forbid이고 상태와 고정 수령 필드는 제한 타입으로 표현했다. Discovery announce는 새 row만 `candidate`지만 기존 admitted/declined/expired row를 다시 announce하면 서비스가 결정을 되살리지 않고 기존 상태를 그대로 응답할 수 있으므로 네 상태를 허용한다. 네 상태가 모두 roundtrip하는 시험도 추가했다. Route에 FastAPI `response_model`을 붙이고 공유 fixture와 회귀시험을 추가했다. 응답의 handle이 없으므로 후속-handle 고위험 범위를 넓히지 않는다.

## 검증 provenance

- 수행: Codex 작성자 실행. 독립 검토, hosted CI, PostgreSQL 통합, HTTP, UI 인수는 미실시.
- 정적 감사 기준: HEAD `044c343a518f7ec9f8ae83fd436a8a1da67486bd`. 구현 착수 당시 origin은 `d45435be560180156bad16b5716272f9e814b89a`였고, 통합에 추가된 계약 정정 `167a7f1f`를 포함하도록 재기반했다. 최종 코드 SHA `22ecafcf583b3c251b552d3df73dacbca65d828f`, branch `agent/codex/contribution-lifecycle-contracts`, 격리 worktree `C:/Users/egpar/AppData/Local/Temp/sv-codex-contract-land-20260922`.
- Interpreter: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`, Python 3.14.6. Node v24.17.0. 최종 재검증 KST 2026-09-22 04:05–04:06.
- 계약 회귀: final code SHA `22ecafcf`, `tools/provenance.py -- C:/Project/SaintVision-Invion/.venv/Scripts/python.exe -m pytest tests/core/test_low_risk_write_response_contracts.py tests/core/test_node_page_detail_response_contract.py tests/core/test_pool_placement_response_contract.py tests/core/test_workspace_response_contract.py -q` → exit 0, **77 passed**, 2 dependency deprecation warnings. Executor egpar/Codex 작성자.
- Route-detach 되돌림 대조: 일곱 route의 `response_model`을 각각 메모리에서 제거했을 때 anchor invariant가 일곱 번 모두 실패를 감지했다. 각 값을 즉시 복원했고 실행 종료 code 0이다. 이 대조는 선언 앵커 검사의 감지력을 검증하며 별도 운영 서버/DB 동작 증거가 아니다.
- Schema: `tools/export_schemas.py`가 새 7 schema를 생성해 총 56개. final code SHA에서 `tools/export_schemas.py --check` exit 0, 56/56 일치.
- 계약 사슬: final code SHA에서 `tools/check_contract_bindings.py` exit 0, 46 fixtures 각각 시험 참조 및 12 kernel serving-anchor tests.
- 문서 게이트: 최종 작업 문서를 포함한 tree에서 `tools/check_docs.py` exit 0 (24 original hashes, 717 versioned docs); `tools/check_ontology.py` exit 0. `tools/sync_obsidian.py --check`는 1518 managed, 3 pending, 0 conflicts로 exit 0; read-only, apply하지 않았다.
- Provenance wrapper는 실행 당시 `working_tree_clean: NO`라고 기록했다. 변경은 보고서와 진행판 세 문서이며 제품/시험 소스는 final code SHA에 커밋돼 있었다. `git diff --check`도 통과했다. 브랜치는 fetch 시각의 integration `167a7f1f` 위에 2 commits 앞섰으며, 이후 remote 이동 여부는 아직 재확인하지 않았다.

## 다음 담당

- 사용자/업무 owner: 일반 ModelRetry를 제품에 노출할지와 owner/API authority 결정. WorkspaceResume와 ShardRecovery는 각각 별도 좁은 정책이다.
- Codex: 문서 갱신 커밋 후 최신 integration fetch, 개인 index로 자기 파일만 착지, rev-range 확인, 그 뒤 Claude 독립 검토를 요청한다.
