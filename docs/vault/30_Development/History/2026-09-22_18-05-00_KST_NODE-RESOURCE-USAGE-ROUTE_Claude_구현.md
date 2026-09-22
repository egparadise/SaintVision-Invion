---
doc_id: "CLAUDE-NODE-RESOURCE-USAGE-ROUTE-001"
title: "노드 자원 사용량 서빙 라우트 구현 — GET /v1/projects/{project}/nodes/{node_id}/resource-usage (결정 #2 A 후속, 계약 eceac8cf 무변경)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T18:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "cf65a126"
impl_sha: "(착지 커밋 — 아래 §5)"
tags: ["node", "resource-usage", "serving-anchor", "real-pg", "claude", "decision-2A"]
---

# 노드 자원 사용량 서빙 라우트 (2026-09-22, 카드 3)

PR #36 독립 검토 F1: 결정 #2 A 계약(`eceac8cf` — `NodeResourceUsageResponse`, capability별, 미측정 null, kind/unit enum)은 스키마·생성 타입·fixture만 있고 **서빙 라우트 0(404)** 이었다. 이 카드는 그 라우트를 Claude 소유 중간 난도 읽기 API로 구현한다. **계약은 바꾸지 않았다**(스키마·fixture·생성 타입 diff 0).

## 1. 설계 (코디네이터 승인 A)

- 계약 경로 `GET /v1/projects/{projectId}/nodes/{nodeId}/resource-usage`는 커널 HTTP 표면(`inv/app.py`의 `/v1/projects/{project}/…` 계열)이다. 코디네이터 `ask` 회신: **옵션 A** — 핸들러 본문은 Claude 소유 새 모듈에 두고, `app.py`에는 위임 호출 **코드 3줄**(데코레이터·def·본문)만 추가(빈 줄 1 별도). Codex 소유 파일 접촉이므로 커밋 메시지에 R5 통지 문구, rev-range로 다른 줄 무변경 증명(§5).
- **읽기 모델** `services/control-plane/src/inv/node_resource_usage.py`(Claude):
  - 인가: `control.grant(conn, principal, project)` 재사용(project_grants + business 권한, 403). `NodeId` 계약 검증. 프로젝트에 **연결·enabled된 노드만**(`inv.project_nodes`) — 미연결/미지 노드는 404(빈 목록 아님). discovery 후보 claim은 절대 투영하지 않음.
  - 값: `inv.resources`(capacity·offered) · `reserved` = 미해제 `inv.resource_leases.amount` 합 · `observedAt` = **`capacity.py`와 동일한 인가·신선 술어**(같은 recovery epoch, channel version 일치, 채널 enabled, 인증서 미만료, snapshot·heartbeat 15초 이내)를 통과한 `node_resource_snapshots.received_at`. 두 읽기 모델이 "관측됨" 여부에서 어긋나지 않게 술어를 같게 뒀다.
  - **정직 규칙**: 신선·인가 관측이 없으면 `measured=false`, `reserved/spare/observedAt=null` — 0 합성 없음(F4 capacity→0 강등 방지). `spare = offered - reserved`. 저장 상태가 `0 ≤ reserved ≤ offered ≤ capacity`를 깨면 **clamp 대신 500 DomainError로 거부**(그럴듯한 숫자는 거짓말). kind→unit은 고정 매핑(cpu millicores·memory bytes·gpu devices·storage bytes·network bitsPerSecond; `inv.resources.kind` CHECK와 계약 enum 일치). `stateAsOf` = 측정된 항목의 최신 observedAt, 없으면 null.
  - **서빙 앵커**: 응답 직전 `validate_contract("NodeResourceUsageResponse", response)`.
- **미변경**: Codex 커널 로직(control.py·capacity.py·placement 등), 계약, apps/web(Gemini 몫 — 배선 안 함).

## 2. 검증 (실 PG, 내 손)

| 검사 | 명령 | 결과 |
|---|---|---|
| 서빙 앵커 시험(HTTP 경로, 실 PG) | `pytest tests/integration/test_node_resource_usage.py` (TestClient + `create_app`, JWT, disposable DB) | **6 passed / 0 failed**: fixture와 서빙 응답이 같은 계약 shape · 미관측 노드 measured=false·null(0 아님) · 신선 관측+lease 3 → reserved 3/spare 7/observedAt=received_at, stateAsOf 일치 · 60초 지난 관측 → 다시 unmeasured · 앵커 거부(unit을 enum 밖으로 변이→200 아님·본문에 계약명) · outsider 403·무토큰 401·미지 노드 404·연결 해제 404 |
| **되살림(변이)** | 모듈의 `validate_contract("NodeResourceUsageResponse", response)`를 `pass`로 → 같은 파일 재실행 | **1 failed / 5 passed** → 복원 후 6 passed. 앵커를 지우면 시험이 깨진다(무게 있음) |
| check_contract_bindings | `tools/check_contract_bindings.py` (SERVING_MODULES에 `node_resource_usage.py` 등록) | **PASS exit 0 — 14→15 bound kernel response TYPES, 17→18 anchor sites**, 50 fixtures, 12 replay guards. 등록 전엔 내 앵커가 스캔 밖이라 "서빙됨(dead 아님)"까지만 잡혔다 — 도구가 자기 범위를 선언하는 이유 |
| check_frontend_integrity | `tools/check_frontend_integrity.py` | PASS 0 위반 exit 0 |
| route_coverage 반영 | `route_coverage.scan_served(services/control-plane/src)` | `/v1/projects/{}/nodes/{}/resource-usage` 정적 스캔에 포함(데코레이터 유도, 목록 편집 없음). `tools/route_coverage.py main`은 설정된 Control Plane 환경 필요라 여기선 미실행(`test_vf_canonical`이 CI에서 실측) |
| 착지 SHA 정확 트리 재실행 | 측정 워크트리 `D:\Project\sv-measure-claude` checkout, porcelain 0 | §5 |

## 3. 하지 않은 것 (정직)
- 실 노드 heartbeat가 만든 snapshot으로의 end-to-end(관측 ingest → 이 라우트)는 미실측 — 시험은 `capacity.py`와 같은 술어를 SQL로 재현해 `node_channels`·`node_resource_snapshots`·`resource_leases`를 직접 심었다. 물리 노드 5대가 붙으면 그 자리에서 첫 관측.
- lease `expires_at`은 `capacity.py`와 같이 무시(`released_at IS NULL`만). 만료-미해제 lease를 reserved로 세는 것이 옳은지는 Codex 판단(현 정본과 일관성 우선).
- 화면 배선(Gemini): 노드 상세에서 이 라우트를 읽어 "용량 표시 + 사용률 미제공"을 "capability별 예약량/미측정 정직 표시"로 바꾸는 것.

## 4. Codex에 넘기는 것
- `app.py` 위임 3줄 등록 통지(R5) — 원하면 자기 방식으로 재배치 가능(모듈 API `serve(control, principal, project, node_id)` 유지).
- 판단 요청: 만료 lease 처리(§3), `RES-0010/0011` 코드 번호가 커널 코드 체계와 충돌하지 않는지.

## 5. 착지
- 파일: `services/control-plane/src/inv/node_resource_usage.py`(신규) · `services/control-plane/src/inv/app.py`(+4줄: 빈 줄 1 + 코드 3줄, 다른 줄 무변경) · `tests/integration/test_node_resource_usage.py`(신규) · `tools/check_contract_bindings.py`(SERVING_MODULES 1줄) · 이 문서 · Claude 작업 현황.
- 착지 SHA·정확 트리 재실행 결과·게이트 exit는 커밋 후 Claude 작업 현황 항목과 이 문서 §5에 기록(아래 갱신).
