---
doc_id: "HIST-20260922-GEMINI-NODE-RESOURCE-USAGE"
title: "NodeResourceUsage Capability 자원 바인딩, Zero-Mock 프로젝터 및 NodeDetail 미관측 가드"
version: "1.0.0"
status: "completed"
author: "Gemini"
reviewer: "Codex"
created: "2026-09-22T16:30:00+09:00"
updated: "2026-09-22T16:30:00+09:00"
source_of_truth: "Git"
---

# NodeResourceUsage Capability 자원 바인딩, Zero-Mock 프로젝터 및 NodeDetail 미관측 가드

## 1. 개요 및 배경

- **배경**: Codex가 `2026-09-22_노드_자원_사용량_HTTP_계약_결정제안_Codex.md` (`CODEX-NODE-USAGE-CONTRACT-PROPOSAL-001`)에서 Option A(Capability 기반 자원 모델)를 확정하고, `NodeResourceUsageResponse` 와이어 스키마와 정본 fixture(`contracts/fixtures/node-resource-usage-response.json`)를 착지시켰다.
- **Frontend 핵심 과제 (GM-02 / S02-FE)**:
  1. **Zero-Mock & Anti-Silent-Fallback**: 동적 텔레메트리가 수집되지 않는 환경(`measured === false`)에서 `reserved`, `spare`, `observedAt`을 `0`이나 가짜 클라이언트 타임스탬프로 합성하지 않고 엄격히 `null`로 유지하는 ViewModel 프로젝터 구축.
  2. **조기 탈출 함정 치유 (NodeDetail.tsx)**: 기존 `NodeDetail.tsx`의 12번 라인 조기 탈출(`if (node.telemetryUnavailable) return ...`)로 인해 노드의 정적 Capability와 사양까지 완전히 은폐되던 문제를 치유하고, 정보 배너와 함께 정적 사양 및 커널 자원 할당 상태를 온전히 표출.
  3. **자원 할당 패널 신설**: `stateAsOf` 시각 부인 고지 `(실시간 캡처나 화면 갱신 시각이 아닙니다)`와 함께 측정/미측정 뱃지, Capacity, Offered, Reserved, Spare를 정직하게 표출하는 `capability-resource-usage-panel` 구축.
  4. **NaN 방어 및 미관측 상태 정합**: sparse 노드 객체(단위 테스트 및 정적 노드)에서 `NaN GiB`, `NaNC`가 출력되지 않도록 수치 가드를 완비하고, `미관측` 어휘 계약 준수.

---

## 2. 상세 작업 내역

### 1) ViewModel 프로젝터 구축 (`apps/web/src/contracts/kernel-observation.ts`)
- `packages/contracts-ts`로부터 `NodeResourceUsageResponse`, `ResourceUsageMeasurement` 정본 생성 타입 re-export.
- `observedNodeResourceUsage(view: NodeResourceUsageResponse): ObservedNodeResourceUsage` 함수 구현.
- `measured === false`일 때 `reserved: null`, `spare: null`, `observedAt: null`을 엄격히 보존하여 허위 0이나 가짜 시각 합성을 원천 차단.

### 2) 제어 평면 어댑터 결속 (`apps/web/src/features/desktop/fabricControlApi.ts`)
- `getNodeResourceUsage(nodeId: string, projectId?: string): Promise<ObservedNodeResourceUsage>` 어댑터 구현.
- 프로젝트 스코프 엔드포인트 `/v1/projects/{p}/nodes/{n}/resource-usage` 및 글로벌 엔드포인트 `/v1/nodes/{n}/resource-usage` 결속.

### 3) NodeDetail 화면 복원 및 Capability 사용량 패널 구현 (`apps/web/src/features/nodes/NodeDetail.tsx`)
- 조기 반환 제거 및 `data-testid="node-telemetry-unavailable-banner"` 안내 배너 전환.
- `data-testid="capability-resource-usage-panel"` 구축:
  - 기준 시각: `{resourceUsage.stateAsOf ?? '미기록'} (실시간 캡처나 화면 갱신 시각이 아닙니다)`
  - 자원별 카드: `resource-usage-card-{kind}`, `resource-measured-badge-{kind}`
  - `측정됨 (Measured)` vs `미측정 (Unmeasured)` 명확한 뱃지 분리.
- `Number.isFinite(...)` 가드로 `NaN` 출력 완전 박멸 및 `미관측` 정합.

### 4) NodeList 미관측 노드 탐색 및 테스트 ID 정합 (`apps/web/src/features/nodes/NodeList.tsx`)
- 미관측 노드 카드에 `onSelectNode` 클릭 핸들러 및 `상세 및 자원 보기 →` 버튼(`data-testid="node-detail-btn-{node.id}"`) 추가.
- active 상태 공지 문단에 `data-testid="node-active-status-notice-{node.id}"` 결속.

### 5) 전용 회귀 테스트 구축 (`apps/web/tests/node-resource-usage-contract.test.tsx`)
- `observedNodeResourceUsage` 정본 fixture 프로젝션 및 null 보존 단언.
- `NodeDetail` 미관측 배너 및 Capability 패널 DOM 단언.
- `NodeList` active 공지 및 상세 탐색 버튼 클릭 단언.
- 총 4/4 tests 100% 통과.

---

## 3. 검증 실측 증거 (8대 게이트 전수 PASS)

1. `npx tsc -b`: exit code 0 (타입 오류 0건).
2. `npm run build`: exit code 0 (Vite 프로덕션 번들 6.45s 99 modules 정상 생성).
3. `npm run test` (Vitest): **76개 파일 659/659 passed 100% in 24.13s (순증 +1 파일, +4 tests)**.
4. `python tools/check_frontend_integrity.py`: **82개 파일 All 9 rules satisfied (0 violations)**.
5. `pytest tests/test_route_coverage.py`: **30 passed in 1.19s**.
6. `python tools/check_contract_bindings.py`: **50 fixtures / 14 serving anchor types PASS**.
7. `python tools/check_doc_single_source.py --ratchet`: **18 pairs PASS**.
8. `python tools/check_docs.py`: **762 versioned documents PASS**.
