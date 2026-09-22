---
doc_id: "HIST-20260922-GEMINI-NODE-RESOURCE-USAGE"
title: "NodeResourceUsage Capability 자원 바인딩, Zero-Mock 프로젝터 및 NodeDetail 미관측/트라이스테이트 가드"
version: "1.1.0"
status: "completed"
author: "Gemini"
reviewer: "Codex"
created: "2026-09-22T16:30:00+09:00"
updated: "2026-09-22T18:50:00+09:00"
source_of_truth: "Git"
---

# NodeResourceUsage Capability 자원 바인딩, Zero-Mock 프로젝터 및 NodeDetail 미관측/트라이스테이트 가드

## 1. 개요 및 배경

- **배경**: Codex가 `2026-09-22_노드_자원_사용량_HTTP_계약_결정제안_Codex.md` (`CODEX-NODE-USAGE-CONTRACT-PROPOSAL-001`)에서 Option A(Capability 기반 자원 모델)를 확정하고, `NodeResourceUsageResponse` 와이어 스키마와 정본 fixture(`contracts/fixtures/node-resource-usage-response.json`)를 착지시켰다.
- **상태**: Claude 카드 3 착지(`3d1892c0`, `GET /v1/projects/{project}/nodes/{node_id}/resource-usage`)에 따른 App 레벨 연결, 미서빙 글로벌 분기 제거, 정직한 tri-state 안내 가드 및 계약 검증 완결.
- **Frontend 핵심 과제 (GM-02 / S02-FE)**:
  1. **Zero-Mock & Anti-Silent-Fallback (F4 치유)**: 동적 텔레메트리가 수집되지 않는 환경(`measured === false`)에서 `reserved`, `spare`, `observedAt`을 `0`이나 가짜 클라이언트 타임스탬프로 합성하지 않고 엄격히 `null`로 유지. non-finite `capacity`/`offered` 역시 `0`으로 강등하지 않고 `null` 유지하며 UI에서 `미측정` 렌더링.
  2. **미서빙 글로벌 경로 제거 및 정본 라우트 단일화 (Claude 재검토 지적 1 치유)**: 백엔드에서 서빙되지 않는 `/v1/nodes/{n}/resource-usage` 분기를 제거하고, `getNodeResourceUsage(nodeId: string, projectId: string)`로 `projectId`를 필수화하여 `/v1/projects/{project}/nodes/{node_id}/resource-usage`만 호출. `route_coverage` 정합성 100% 확보.
  3. **프로젝트 미선택 안내 및 Tri-State 가드 (Claude 재검토 지적 2 치유, Anti-F2)**: 프로젝트 미선택 상태에서 무의미한 404 호출을 방지하고 `resourceUsageState: 'unselected'` 노출. `NodeDetail`에서 프로젝트 미선택 안내(`data-testid="node-resource-usage-unselected-notice"`, `role="status"`), 조회 중(`data-testid="node-resource-usage-loading"`), 조회 실패(`data-testid="node-resource-usage-error"`, `role="alert"`), 성공 패널의 4단계 정직 표출 구현(조용한 null 강등 완전 제거).
  4. **조기 탈출 함정 치유 (NodeDetail.tsx)**: 기존 `NodeDetail.tsx`의 12번 라인 조기 탈출(`if (node.telemetryUnavailable) return ...`)로 인해 노드의 정적 Capability와 사양까지 완전히 은폐되던 문제를 치유하고, 정보 배너와 함께 정적 사양 및 커널 자원 할당 상태를 온전히 표출.
  5. **자원 할당 패널 신설 및 로케일 정합 (F6 치유)**: `stateAsOf` 시각 부인 고지 `(실시간 캡처나 화면 갱신 시각이 아닙니다)`와 함께 측정/미측정 뱃지, Capacity, Offered, Reserved, Spare를 정직하게 표출하는 `capability-resource-usage-panel` 구축. 모든 수치와 시각에 `.toLocaleString('ko-KR')` 적용.
  6. **라이브 관측 및 검증 한계 정직 고지 (Claude 재검토 지적 3 치유)**: dev DB에 등록 노드가 0대이므로 실제 노드의 라이브 "미측정 null" 응답은 dev 환경 라이브 브라우저 경로로는 미실측(등록 노드 0대 한계). 대신 백엔드 PostgreSQL 실 DB 통합 시험(`tests/integration/test_node_resource_usage.py` 6 passed) 및 프론트엔드 프로젝터/DOM 계약 시험(`tests/node-resource-usage-contract.test.tsx` 9 passed)으로 무결성을 교차 검증함.

---

## 2. 상세 작업 내역

### 1) ViewModel 프로젝터 구축 (`apps/web/src/contracts/kernel-observation.ts`)
- `packages/contracts-ts`로부터 `NodeResourceUsageResponse`, `ResourceUsageMeasurement` 정본 생성 타입 re-export.
- `observedNodeResourceUsage(view: NodeResourceUsageResponse): ObservedNodeResourceUsage` 함수 구현.
- `measured === false`일 때 `reserved: null`, `spare: null`, `observedAt: null`을 엄격히 보존하여 허위 0이나 가짜 시각 합성을 원천 차단.
- non-finite `capacity`, `offered`에 대해 `0` 대신 `null`을 보존하여 F4 조용한 강등 방지.

### 2) 제어 평면 어댑터 및 App 최상위 배선 (`apps/web/src/features/desktop/fabricControlApi.ts`, `apps/web/src/app/App.tsx`)
- `getNodeResourceUsage(nodeId: string, projectId: string): Promise<ObservedNodeResourceUsage>` 어댑터 개편. 미서빙 글로벌 경로를 제거하고 project-scoped 엔드포인트 `/v1/projects/{encProject}/nodes/{encNode}/resource-usage` 단일 호출.
- `App.tsx`에 `nodeResourceUsage`, `nodeResourceUsageState`, `nodeResourceUsageError` 상태를 추가하고, `!projectId`인 경우 네트워크를 호출하지 않고 `unselected` 상태 설정. `projectId`가 존재할 때만 `loading` → API 호출 → `success` 또는 `error` 설정.
- 탭 전환 및 프로젝트 변경 시 자원 사용량 상태를 초기화.

### 3) NodeDetail 화면 복원, 안내 가드 및 Capability 사용량 패널 구현 (`apps/web/src/features/nodes/NodeDetail.tsx`)
- 조기 반환 제거 및 `data-testid="node-telemetry-unavailable-banner"` 안내 배너 전환.
- Tri-state 및 프로젝트 미선택 가드:
  - `data-testid="node-resource-usage-unselected-notice"` (`role="status"`): 프로젝트 미선택 시 안내 메시지 노출.
  - `data-testid="node-resource-usage-loading"` (`role="status"`): 조회 중 안내.
  - `data-testid="node-resource-usage-error"` (`role="alert"`): 조회 실패 시 명시적 오류 메시지 노출.
- `data-testid="capability-resource-usage-panel"` 구축:
  - 기준 시각: `{resourceUsage.stateAsOf ?? '미기록'} (실시간 캡처나 화면 갱신 시각이 아닙니다)`
  - 자원별 카드: `resource-usage-card-{kind}`, `resource-measured-badge-{kind}`
  - `측정됨 (Measured)` vs `미측정 (Unmeasured)` 명확한 뱃지 분리.
  - `capacity !== null ? capacity.toLocaleString('ko-KR') : '미측정'` 및 `offered !== null ? offered.toLocaleString('ko-KR') : '미측정'` 렌더링.
  - `node.heartbeatAt` 포맷에 `'ko-KR'` 로케일 적용.
- `Number.isFinite(...)` 가드로 `NaN` 출력 완전 박멸 및 `미관측` 정합.

### 4) NodeList 미관측 노드 탐색 및 테스트 ID 정합 (`apps/web/src/features/nodes/NodeList.tsx`)
- 미관측 노드 카드에 `onSelectNode` 클릭 핸들러 및 `상세 및 자원 보기 →` 버튼(`data-testid="node-detail-btn-{node.id}"`) 추가.
- active 상태 공지 문단에 `data-testid="node-active-status-notice-{node.id}"` 결속.

### 5) 전용 회귀 테스트 구축 (`apps/web/tests/node-resource-usage-contract.test.tsx`)
- `observedNodeResourceUsage` 정본 fixture 프로젝션 및 null 보존 단언.
- non-finite capacity/offered null 보존 및 anti-F4 회귀 단언.
- `NodeDetail` 미관측 배너, Capability 패널, 미선택 안내, 로딩, 에러 alert DOM 단언.
- `getNodeResourceUsage` 인코딩 및 project-scoped 엔드포인트 호출 단언.
- `NodeList` active 공지 및 상세 탐색 버튼 클릭 단언.
- 총 9/9 tests 100% 통과.

---

## 3. 검증 실측 증거

1. `npx tsc -b`: exit code 0 (타입 오류 0건).
2. `npm run build`: exit code 0 (Vite 프로덕션 번들 7.56s 99 modules 정상 생성).
3. `npm run test` (Vitest): **`tests/node-resource-usage-contract.test.tsx` 9/9 passed 100% in 13.93s**.
4. `python tools/check_frontend_integrity.py`: **82개 파일 All 9 rules satisfied (0 violations)**.
5. `pytest tests/test_route_coverage.py`: **37 passed in 0.85s**.
6. 백엔드 PostgreSQL 실 DB 시험 (`tests/integration/test_node_resource_usage.py`): **6 passed** (서버 미측정 null 실물 생성 및 동작 검증).
7. 라이브 한계 명시: dev DB 등록 노드 0대로 브라우저 경로 실 노드 미측정 null 실측은 환경상 미실측이며, 백엔드 DB 시험 및 단위 계약 시험으로 무결성 보장.
8. `python tools/check_docs.py`: **PASS (24 original hashes, 785 versioned documents)**.
