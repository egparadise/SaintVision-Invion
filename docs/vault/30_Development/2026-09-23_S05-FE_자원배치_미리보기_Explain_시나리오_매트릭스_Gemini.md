---
doc_id: "GEMINI-S05-FE-SCENARIO-MATRIX-20260923"
title: "S05-FE 자원배치 미리보기·Explain UI 시나리오 매트릭스 (Gemini)"
version: "1.2.0"
status: "review"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-23T07:45:00+09:00"
source_of_truth: "Git"
tags: ["s05-fe", "acceptance-matrix", "placement-preview", "resource-explorer", "explain", "capacity-partitioning", "gemini"]
---

# S05-FE 자원배치 미리보기·Explain UI 시나리오 매트릭스 (Gemini)

> **관련 계약 및 선행 문서**:
> - [[전체 개발 진행 현황]]
> - [[Gemini 작업 현황]]
> - [[S05 자원 배치]] (OUT-05 / AC-05)
> - [[Frontend 최종 개발 계획]]
> - [[설계 충돌 정정 및 ADR]] (ADR-005, ADR-028, ADR-041, ADR-100)
> - `apps/web/src/features/placement/PlacementSimulator.tsx`
> - `apps/web/src/features/placement/ResourceTopologyGraph.tsx`
> - `apps/web/src/features/placement/PlacementExplainView.tsx`
> - `apps/web/src/features/desktop/ResourceExplorer.tsx` (Pools Tab)
> - `apps/web/src/features/desktop/fabricControlApi.ts`
> - `src/saintvision/api/v1/pools.py`
> - `src/saintvision/services/pools.py`
> - `src/saintvision/api/schemas.py`
> - `src/saintvision/errors.py`
> - `tests/test_route_coverage.py`

---

## 1. 개요 및 수용 목표 (OUT-05 / AC-05)

본 문서는 SaintVision 자원 스케줄링 및 제어 평면의 **S05-FE (자원배치 미리보기·설명 가능한 배치 시뮬레이터·자원 풀 관리)** 트랙을 완결하기 위해, 코디네이터 지시 및 Codex 계약 검토(PR #96 수정 요청 4건)와 Claude UI 검토 피드백을 전면 반영하여 수립한 **docs-only 시나리오 매트릭스 정본 개정안(v1.2.0)**이다.

본 문서는 `PlacementSimulator` 및 `ResourceExplorer` 화면의 사용자 여정별 기대를 **실제 프런트엔드 컴포넌트 셀렉터(`data-testid`, `role`, 태그)** 및 **커널 계약 규격(`VAL-SCHEMA`, `RES-NODE-NOT-FOUND`, `AUTH-MISSING-CREDENTIAL`, `AUTH-PROJECT-SCOPE` 등)**과 1:1로 엄격히 대응시키며, 존재하지 않는 셀렉터나 임의 합성 값의 기재를 전면 금지(Zero Fake Selectors / Zero Fake Values)한다.

### 1.1 핵심 합격 기준 (AC-05) 및 경계 분리 원칙
- **정본 용량 3원 분리 (Three Capacity Figures, Never One)**:
  - 자원 풀 목록(`GET /v1/pools`)은 휘발성 용량을 일체 번들링하지 않는다 (인벤토리/신원 필수 필드 `poolId`, `projectId`, `name`, `status`, `memberCount` 및 최상위 `count`만 반환).
  - 풀 용량(`GET /v1/pools/{poolId}/capacity`)은 독립 조회되며 `totalOffered`(풀 총합), `largestSingleNode`(비분할 단일 작업 물리적 천장), `spareNow`(현재 관측된 실 유휴량)의 3원 수치를 반드시 함께 표기한다.
  - `offered <= physical capacity` 불변식은 풀 응답 스키마 자체의 상호 대소 제약이 아니라, 노드 등록 경계(`src/saintvision/services/nodes.py:71-79`)에서 강제되는 도메인 불변식으로 출처를 엄격히 분리한다.
- **배치 미리보기 정직성 및 가짜 샤드 합성 0 (Zero Fake Shards)**:
  - 서버 배치 미리보기(`GET /v1/pools/{poolId}/placement-preview`)는 오직 유휴 우선 후보 노드 순위(`candidates`, `candidateCount`)만을 반환하며 샤드 ID나 실행 배치 결과를 포함하지 않는다.
  - `PlacementSimulator`의 `shd_*` 표시는 실행 전 단일 작업 배치 후보의 로컬 순위 가시화 행(Candidate preview visualization)이며, 실제 분산 샤드(`shardIndex`, `assignedCpuMillicores` 등) 할당은 서버 분산 계획(`POST /v1/pools/{poolId}/plans`)을 통해서만 수립된다. 실제 등록 샤드가 없는 미리보기 단계의 샤드 검증은 **UNMEASURED ('실제 분산 실행 등록 전')**로 정직 표기한다.
  - 미리보기 실패 시 클라이언트는 가짜 샤드를 날조하지 않고 `서버 어드미션 미검증: 가짜 샤드 상태를 생성하지 않습니다` 경보를 표출한다.
- **로컬 시뮬레이션과 서버 어드미션의 엄격한 경계 분리**:
  - `PlacementSimulator`의 클라이언트 결정론적 평가는 `로컬 결정론적 평가 (UNVERIFIED: 로컬 시뮬레이션 전용)` 배지로 한계를 명시하고, 로컬 UNVERIFIED Explain과 서버 candidate preview를 철저히 분리한다.
- **관측 전용 노드(schedulable: false) 편입 차단 (클라이언트 가드 경계)**:
  - `ResourceExplorer.tsx:446-448`의 클라이언트 가드는 `observationOnly === true` 또는 `schedulable === false`인 노드의 풀 편입 시도 시 네트워크 요청 자체를 원천 차단($0$ HTTP requests)한다.
  - 단, 백엔드 `add_member()` (`services/pools.py:136-148`)는 현재 pool/node 존재 여부만 검증하므로, 직접 API 호출에 대한 서버 측 거부 불변식은 백엔드 제어 평면 보강 태스크의 별도 검증 대상임을 명시한다.
- **정본 분산 전략 enum 준수 (`single_node` | `data_parallel` | `sharded`)**:
  - UI 및 API 클라이언트(`fabricControlApi.ts`)는 백엔드 계약 규격(`DistributedPlanRequest`)에 맞춰 `sharded`(분산 샤딩 - 권장), `data_parallel`(데이터 병렬), `single_node`(단일 노드)의 정본 enum을 직접 사용하며, 422 `VAL-SCHEMA` 오류 없이 정상 201 Created에 도달한다.

---

## 2. 4대 핵심 영역 매트릭스 구성 체계

| 영역 코드 | 핵심 테마 | 대상 컴포넌트 / 모듈 | 핵심 방어 기제 및 백엔드 계약 규격 |
|:---:|---|---|---|
| **POL** | **풀 인벤토리 및 3원 용량 분리**<br>(Pool & Capacity Partitioning) | `ResourceExplorer.tsx`<br>`PlacementSimulator.tsx`<br>`fabricControlApi.ts`<br>`services/pools.py` | • `GET /v1/pools`: `{ items: [{ poolId, projectId, name, status, memberCount }], count }` (용량 미번들링)<br>• `GET /v1/pools/{id}/capacity`: 독립 호출로 3원 수치(`totalOffered`, `largestSingleNode`, `spareNow`) 동시 표기<br>• `SNAPSHOT_FRESHNESS_SECONDS = 120` 초과 노드는 `measured: false`, spare=0 처리 및 `unmeasuredNodes` 분리<br>• 정적 스냅샷 수동 갱신 고지(`pool-tab-manual-refresh-notice`, `textContent` 인라인 태그 포함 검사) |
| **PRV** | **배치 미리보기 및 샤드 어댑터**<br>(Placement Preview & Shards) | `PlacementSimulator.tsx`<br>`ResourceExplorer.tsx`<br>`fabricControlApi.ts`<br>`services/pools.py` | • `GET /v1/pools/{id}/placement-preview`: 유휴 우선(`-headroom`, `nodeId`) 후보 순위 반환<br>• 트리거: 풀/요구량 변경에 따른 자동 조회 + `button[data-testid="preview-retry-btn"]` (수동 버튼은 RE의 `적격 노드 순위 조회`)<br>• 실제 헤더: `샤드 ID`, `타겟 노드`, `배치 상태` (PS:678~680)<br>• Zero Fake Shards: 후보 순위 표출, 실제 등록 샤드가 없는 미리보기는 UNMEASURED 표기 |
| **LOC** | **로컬 평가 경계 및 디스커버리**<br>(Local Boundary & Discovery) | `PlacementSimulator.tsx`<br>`ResourceTopologyGraph.tsx`<br>`PlacementExplainView.tsx` | • `local-simulation-badge`에 `로컬 결정론적 평가 (UNVERIFIED: 로컬 시뮬레이션 전용)` 영구 명시<br>• Hard Filter 5단계 및 다기준 가중치(0.4 locality + 0.3 headroom + 0.3 net) 클라이언트 시뮬레이션<br>• `GET /v1/discovery/candidates` 신고 스펙(`claimed*`) 및 `CANDIDATE (미검증)` 표출<br>• 후보 부재 시 운영자 조치 안내(`candidates-empty-state`) |
| **PLN** | **분산 계획 수립 및 멤버 관리**<br>(Planning & Member Management) | `ResourceExplorer.tsx`<br>`fabricControlApi.ts`<br>`services/pools.py` | • 관측 전용(`observationOnly`, `schedulable: false`) 노드 편입 시 클라이언트 가드로 PUT 0건 차단<br>• `plan-run-id-input` 공백 시 `create-plan-btn` 비활성화 및 사용자 조치 안내 표출<br>• 정본 전략 enum(`sharded`, `data_parallel`, `single_node`) 매핑 완료로 정상 201 Created 계획 수립<br>• `splittableDeclared` 미선언 다중 샤드 또는 부분 배치 시 422 `VAL-SCHEMA` 정직 거절 |

---

## 3. 세부 시나리오 매트릭스 (13대 시나리오)

### 3.1 풀 인벤토리 및 3원 용량 분리 (Capacity Partitioning, POL-01 ~ POL-04)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **POL-01** | **자원 풀 목록 인벤토리 조회 및 용량 분리** | `PlacementSimulator.tsx`<br>`ResourceExplorer.tsx`<br>`fabricControlApi.ts` | 테넌트 내 자원 풀 존재 (`pool-default` 등) | 화면 마운트 또는 풀 선택 클릭 | • API 경로: `GET /v1/pools`<br>• 응답 모델: `PoolListResponse = { items: [{ poolId, projectId, name, status, memberCount }], count: number }`<br>• 로딩 셀렉터: `div[data-testid="pools-loading"]`<br>• 풀 버튼: `PlacementSimulator` 내 풀 선택 버튼 | • `GET /v1/pools` 응답 내 휘발성 용량 필드(`totalCores`, `spareRam` 등) 일체 부재 확인.<br>• 엄격 계약 모델에 따라 필수 메타데이터(`projectId`, `name`, `status`, `memberCount`, `count`) 완비 검증.<br>• 풀 목록 로드 완료 후 선택된 `selectedPoolId`에 대해 독립적인 용량 API(`GET /v1/pools/{id}/capacity`)가 트리거됨 ($1$ subsequent request). |
| **POL-02** | **3원 풀 집계 용량 표시 (totalOffered, largestSingleNode, spareNow)** | `ResourceExplorer.tsx`<br>`PlacementSimulator.tsx` | 특정 풀(`pool-default`) 선택 완료 | 용량 응답 수신 후 DOM 렌더링 | • API 경로: `GET /v1/pools/{poolId}/capacity`<br>• 컴포넌트: `ResourceExplorer.tsx` (Pools Tab)<br>• 총 제공량: `div:has-text("총 제공량 (Total Offered)")`<br>• 단일 노드 한도: `div:has-text("단일 노드 최대 한도 (Largest Single)")`<br>• 현재 유휴량: `div:has-text("현재 유휴 여유량 (Spare Now)")` | • 3원 수치 동시 렌더링 검증:<br>  1) `totalOffered`: 풀 전체 노드 제공량 합산.<br>  2) `largestSingleNode`: 비분할 단일 작업 한계치로 반드시 병기 (합산치만으로 거대 작업 수용 착시 방지).<br>  3) `spareNow`: 현재 관측 유휴 여유량.<br>• `offered <= physical capacity` 대소 관계는 풀 응답 스키마 자체 단언이 아닌 노드 등록 경계(`nodes.py:71-79`) 불변식으로 출처 분리. |
| **POL-03** | **정적 스냅샷 수동 갱신 고지 및 120초 신선도 경계** | `ResourceExplorer.tsx` | 자원 풀 탭(`activeTab === 'pools'`) 활성화 | 화면 진입 및 수동 갱신 클릭 | • 알림 배너: `div[role="status"][data-testid="pool-tab-manual-refresh-notice"]`<br>• 갱신 버튼: `button[data-testid="pool-manual-refresh-btn"]`<br>• 백엔드 상수: `SNAPSHOT_FRESHNESS_SECONDS = 120` | • 배너 내 `ℹ️ [스냅샷 모드 · 수동 갱신]: 본 탭의 자원 풀 용량 및 멤버 배치는 실시간 자동 폴링되지 않는 정적 스냅샷입니다.` 문구 표출 확인 (DOM에 `<strong>` 태그가 포함되어 있으므로 `textContent` 포함 검사 수행).<br>• 120초 경과된 낡은 스냅샷 노드는 `measured: false`, spare=0 처리되어 `unmeasuredNodes`로 분리 고지.<br>• 새로고침 버튼 클릭 시 `loadPoolData` 재호출. |
| **POL-04** | **풀 용량 조회 실패 시 RFC 9457 409 경보 및 재시도** | `ResourceExplorer.tsx`<br>`PlacementSimulator.tsx`<br>`src/saintvision/errors.py` | 미존재 풀 ID 입력 또는 백엔드 리소스 오류 | `loadPoolData` 호출 시 에러 인입 | • 에러 배너 1: `ResourceExplorer`의 `div[role="alert"][data-testid="pool-capacity-error"]`<br>• 재시도 버튼 1: `button[data-testid="pool-capacity-retry"]`<br>• 에러 배너 2: `PlacementSimulator`의 `div[data-testid="pool-capacity-error"]` | • 미존재 풀 요청 시 백엔드는 Category `RES` 기본 상태 코드인 **HTTP 409 `RES-NODE-NOT-FOUND`** ProblemDetails 반환 (`services/pools.py:335-337`, `errors.py:43-51`).<br>• `role="alert"` 속성을 가진 에러 배너 마운트 및 에러 상세 문구 표출.<br>• 재시도 버튼 클릭 시 `loadPoolData(selectedPoolId)` 정상 재트리거. |

---

### 3.2 배치 미리보기 및 샤드 어댑터 (Placement Preview & Shards, PRV-01 ~ PRV-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **PRV-01** | **유휴 우선 적격 후보 노드 순위 조회 및 설명 표출** | `PlacementSimulator.tsx`<br>`ResourceExplorer.tsx`<br>`fabricControlApi.ts` | 유효한 풀 선택 및 워크로드 자원 요구량(CPU 4C, RAM 8GB, GPU 0) 설정 | `PlacementSimulator` 요구량 슬라이더 조절(자동 조회) 또는 `button[data-testid="preview-retry-btn"]` 클릭 (참고: RE에서는 `적격 노드 순위 조회` 버튼) | • API 경로: `GET /v1/pools/{poolId}/placement-preview?cpuMillicores=4000&ramBytes=8589934592&gpuDevices=0`<br>• 어댑터: `fabricControlApi.ts`의 `getPoolPlacementPreview`<br>• 로딩 셀렉터: `div[data-testid="preview-loading"]`<br>• 테이블 헤더: `<th>샤드 ID</th>`, `<th>타겟 노드</th>`, `<th>배치 상태</th>` (PS:678~680) | • 백엔드가 유휴 여유도 순(`-headroom`) 및 `nodeId` 사전순 정렬된 후보 반환.<br>• 프런트엔드 `PlacementSimulator` 상단에 `🤖 서버 실시간 배치 설명: 적격 노드 N대 확인 (풀: ...)` 표출.<br>• **Zero Fake Shards 및 UNMEASURED 경계**: 서버 preview 계약(`PlacementPreviewResponse`)에는 후보 순위(`candidates`, `candidateCount`)만 존재하며 실제 샤드 배치가 없음. PS 화면의 `shd_*` 행은 실행 전 가시화 행이며, 실제 커밋된 분산 샤드 배치는 PLN-03 영역이므로 **UNMEASURED ('실제 분산 실행 등록 전')**로 정직 표기. |
| **PRV-02** | **가용 노드 부재 시 빈 상태 고지 및 가짜 샤드 합성 차단** | `PlacementSimulator.tsx` | 풀의 최대 노드 용량을 초과하는 과도한 요구량 설정 (예: CPU 64 Cores) | 슬라이더 조절로 요구량 변경 | • API 응답: `candidateCount: 0`, `candidates: []`<br>• 빈 상태 요소: `p[data-testid="preview-empty-state"][role="status"]`<br>• 안내 문구: `가용 샤드가 없습니다. 👉 [사용자 조치 필요]: 상단 슬라이더에서 모델 크기 또는 샤드 수를 조절하거나 자원 풀 요건을 변경하십시오.` | • 후보 노드가 0건일 때 `preview-empty-state`가 마운트됨.<br>• DOM 상에 어떠한 가짜 샤드 행(Row)도 합성되지 않음 (테이블 언마운트).<br>• 사용자 조치 안내(슬라이더 조절) 정직 표출. |
| **PRV-03** | **서버 배치 미리보기 실패 에러 배너 및 불변식 검증** | `PlacementSimulator.tsx` | 백엔드 통신 두절 또는 422 `VAL-SCHEMA` 오류 발생 | `loadPlacementPreview` 호출 시 거부 | • 에러 배너: `div[role="alert"][data-testid="preview-error-banner"]`<br>• 불변식 텍스트: `서버 어드미션 미검증: 가짜 샤드 상태를 생성하지 않습니다.`<br>• 재시도 버튼: `button[data-testid="preview-retry-btn"]` | • `role="alert"` 경보가 마운트되고 지정된 불변식 안내 문구가 정확히 렌더링됨.<br>• `serverShards` 상태가 `[]`로 초기화되어 미검증 샤드가 화면에 남지 않음.<br>• 재시도 버튼 클릭 시 `loadPlacementPreview()` 재호출. |

---

### 3.3 로컬 평가 경계 및 디스커버리 (Local Boundary & Discovery, LOC-01 ~ LOC-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **LOC-01** | **로컬 시뮬레이션 경계 및 UNVERIFIED 정직 배지** | `PlacementSimulator.tsx`<br>`PlacementExplainView.tsx` | 시뮬레이터 화면 진입 | 슬라이더, GPU 토글, OS 선택, 데이터 지역성 노드 변경 | • 불변식 배지: `span[data-testid="local-simulation-badge"]`<br>• 배지 텍스트: `로컬 결정론적 평가 (UNVERIFIED: 로컬 시뮬레이션 전용)`<br>• 지역성 셀렉트: `select[data-testid="locality-node-select"]`<br>• 뷰 컴포넌트: `PlacementExplainView.tsx` | • 배지 텍스트가 DOM 상에 영구 노출되어 클라이언트 로컬 시뮬레이션과 서버 승인 분리 보장.<br>• 지역성 노드 변경 시 클라이언트 `evaluatePlacement`가 즉각 반응하여 Hard Filter 통과 여부 및 점수(0.4 locality + 0.3 headroom + 0.3 net) 설명 갱신 (서버 Explain이 아닌 로컬 UNVERIFIED Explain임을 명시). |
| **LOC-02** | **자원 풀 부재/대기 시 폴백 배너 및 로컬 평가 분리** | `PlacementSimulator.tsx` | Case A: `poolsState === 'idle'`<br>Case B: `poolsState === 'success' && pools.length === 0` | 풀 목록 상태 전이 시점 | • 대기 배너: `div[data-testid="pools-idle-banner"]`<br>• 폴백 배너: `div[data-testid="pools-fallback-banner"]`<br>• 라벨: `[로컬 결정론적 평가 (UNVERIFIED)]` | • Case A: `pools-idle-banner` 렌더링 및 `자원 풀 연동 대기 중입니다.` 안내.<br>• Case B: `pools-fallback-banner` 렌더링 및 `자원 풀 정보가 없습니다. 현재 관측된 노드 정보로 배치 가능성을 미리 평가합니다.` 고지.<br>• 두 경우 모두 로컬 평가 전용임이 정직하게 표기됨. |
| **LOC-03** | **디스커버리 후보 목록 및 CANDIDATE (미검증) 신고 스펙 표출** | `PlacementSimulator.tsx`<br>`fabricControlApi.ts` | 미승인 후보 머신 1대 이상 등록 상태 (`announcement_id`) | 디스커버리 후보 목록 로드 (`GET /v1/discovery/candidates`) | • API 경로: `GET /v1/discovery/candidates`<br>• 후보 아이템: `div[data-testid="candidate-item-{candKey}"]`<br>• 후보 배지: `span[data-testid="candidate-status-{candKey}"]`<br>• 스펙 문구: `신고 스펙 (Claimed · 실측 가용량 아님)`<br>• 빈 상태: `p[data-testid="candidates-empty-state"][role="status"]` | • 모든 후보 행에 `CANDIDATE (미검증)` 배지 표출.<br>• CPU/RAM 수치가 실측이 아닌 머신 자체 신고치(`claimed*`)임을 명시.<br>• 후보가 0건일 때 `candidates-empty-state` 표출 및 운영자 런북 조치 안내 (`docs/vault/20_Operations/노드 운영 런북.md`). |

---

### 3.4 분산 계획 수립 및 멤버 관리 (Planning & Member Management, PLN-01 ~ PLN-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **PLN-01** | **관측 전용 노드(schedulable: false) 연산 풀 편입 클라이언트 가드 차단** | `ResourceExplorer.tsx` (Pools Tab) | 클러스터 내 관측 전용 노드(`Node-04`, `schedulable: false`, `observationOnly: true`) 존재 | 풀 멤버 선택 드롭다운에서 관측 전용 노드 선택 후 `멤버 추가` 클릭 | • 멤버 셀렉트: `select[data-testid="pool-member-select"]`<br>• 추가 버튼: `button[data-testid="add-pool-member-btn"]`<br>• 에러 배너: `div[role="alert"][data-testid="pool-action-error-banner-inline"]` | • 드롭다운 상에 `Node-04 ... [관측 전용 - 편입 불가]` 표기 및 `disabled=true` 처리.<br>• **클라이언트 가드 경계**: `ResourceExplorer.tsx:446-448` 가드가 호출을 가로채어 HTTP PUT 호출 일체 차단 ($0$ wire requests, `addMemberSpy` 미호출).<br>• 인라인 경보 배너에 `❌ 멤버 추가 거부: 노드 '...'은(는) 관측 전용(schedulable: false)이므로 연산 풀에 편입할 수 없습니다.` 표출.<br>• *주의: 백엔드 `add_member()`는 현재 pool/node 존재 여부만 검증하므로, 직접 API 호출에 대한 서버 측 거부 불변식은 백엔드 제어 평면 보강 태스크의 별도 검증 대상임.* |
| **PLN-02** | **분산 배치 계획 수립 시 승인 Run ID 필수 입력 가드** | `ResourceExplorer.tsx` (Pools Tab) | 자원 풀 선택 완료, 계획 수립 폼 로드 상태 | `planRunId` 입력창을 비워둔 상태에서 화면 관찰 | • 입력창: `input[data-testid="plan-run-id-input"]`<br>• 조치 안내: `div[role="alert"][data-testid="plan-run-id-user-action-notice"]`<br>• 계획 버튼: `button[data-testid="create-plan-btn"]` | • `planRunId`가 빈 문자열일 때 버튼이 비활성화(`disabled=true`, `aria-disabled="true"`, `cursor: not-allowed`)됨.<br>• `plan-run-id-user-action-notice` 경보에 `👉 [사용자 조치 필요]: 승인된 분산 실행 Run ID(예: run_...)를 입력창에 입력하면 배치 계획 생성이 활성화됩니다.` 노출.<br>• 임의의 가짜 Run ID 자동 합성 0건. |
| **PLN-03** | **정본 분산 전략 매핑 및 계획 수립 201 / 422 VAL-SCHEMA** | `ResourceExplorer.tsx`<br>`fabricControlApi.ts`<br>`services/pools.py` | 승인된 `planRunId` 입력 완료 | 전략 선택 후 `분산 계획 생성` 클릭<br>Case A: `shardCount > 1`이나 `splittableDeclared: false`인 경우<br>Case B: 풀 전체 가용 노드 수 초과 샤드 요청 (예: 5노드 풀에 10샤드 단일노드전략)<br>Case C: 정본 `strategy: "sharded"` 및 요건 충족 | • API 경로: `POST /v1/pools/{poolId}/plans`<br>• 요청 본문: `{ runId, strategy: "single_node" \| "data_parallel" \| "sharded", shardCount, shardCpuMillicores, ... }`<br>• 결과 표시: `div[role="status"][data-testid="pool-action-success-banner-inline"]`<br>• 실패 배너: `div[role="alert"][data-testid="pool-action-error-banner-inline"]` | • **정본 enum 매핑**: UI 드롭다운에서 `sharded`(분산 샤딩 - 권장), `data_parallel`(데이터 병렬), `single_node`(단일 노드)를 정본으로 직접 송신.<br>• Case A: 백엔드가 422 `VAL-SCHEMA` ("splitting requires the workload to declare it can be split") 반환.<br>• Case B: 부분 배치 방지 원칙에 따라 422 `VAL-SCHEMA` ("the pool has room for X of Y shards right now; a partial placement would report success for a job that did not run") 반환 및 실패 배너 표출.<br>• Case C: 정상 계획 수립 시 201 Created `DistributedPlanResponse` 반환, `planResult.planId` 및 샤드별 타겟 노드 할당 내역 정상 렌더링. |

---

### 3.5 관련 에러 표면 및 인증 부정 대조군 (Error Surface & Negative Controls)

본 S05-FE 풀 및 배치 계획 경로와 직접 결속된 오류 표면과 인증 대조군은 다음과 같으며, 풀 서비스에서 직접 발생하지 않는 코드는 엄격히 제외한다.

| HTTP 상태 | 오류 코드 | 발생 조건 및 프런트엔드 방어 |
|:---:|---|---|
| **401** | `AUTH-MISSING-CREDENTIAL` | 테넌트 세션 또는 토큰 헤더 누락 시 거부; 로그인/인증 재진입 유도 |
| **401** | `AUTH-INVALID-CREDENTIAL` | 서명 불일치 또는 위조 토큰 인입 시 거부; 에러 배너 및 세션 무효화 |
| **403** | `AUTH-PROJECT-SCOPE` | 해당 프로젝트 권한이 없는 자원 풀 또는 배치 계획 접근 시 거부 |
| **409** | `RES-NODE-NOT-FOUND` | 미존재 자원 풀 또는 미등록 노드 대상 용량/멤버 요청 시 백엔드 ProblemDetails 반환 (POL-04) |
| **422** | `VAL-SCHEMA` | 미지원 전략 문자열, 음수 자원량, 비분할 선언 다중 샤드, 부분 배치 시도 시 거부 (PLN-03) |
| *제외* | `RES-PARTITION-EXHAUSTED` | *풀 preview/plan 서비스가 직접 생성하지 않는 코드로 매트릭스 대상에서 명시적 제외* |

---

## 4. 돌연변이(Mutation) 방어 및 사살 계획 (프로덕션 심볼 타겟)

본 매트릭스의 신뢰성을 검증하기 위해, 시험 코드가 아닌 **실제 프로덕션 프런트엔드 컴포넌트 및 어댑터 코드**에 의도적 결함을 주입하여 단위/통합 테스트에서 즉시 실패(KILLED)하는지 검증하는 돌연변이 사살 계획을 수립한다.

1. **MUT-01 (로컬 평가 배지 UNVERIFIED 문구 변조 돌연변이)**:
   - 대상: `apps/web/src/features/placement/PlacementSimulator.tsx`
   - 주입: `로컬 결정론적 평가 (UNVERIFIED: 로컬 시뮬레이션 전용)` 문구를 `로컬 평가 (VERIFIED)`로 변경.
   - 사살 단언: `pytest tests/test_route_coverage.py:394~`의 백엔드 CI 정적 소스 텍스트/AST 불변식 검사(`assert "UNVERIFIED: 로컬 시뮬레이션 전용" in ps_content`)에서 즉시 실패 (KILLED; 동적 DOM 시험이 아닌 백엔드 CI 게이트의 소스 불변식 검사임).
2. **MUT-02 (가짜 샤드 합성 방어 메시지 누락 돌연변이)**:
   - 대상: `apps/web/src/features/placement/PlacementSimulator.tsx`
   - 주입: 미리보기 에러 배너 내 `서버 어드미션 미검증: 가짜 샤드 상태를 생성하지 않습니다.` 문구 삭제 또는 에러 시 임의 mock 샤드 주입.
   - 사살 단언: `pytest tests/test_route_coverage.py:403~`의 백엔드 CI 정적 소스 텍스트 불변식 검사(`assert "서버 어드미션 미검증: 가짜 샤드 상태를 생성하지 않습니다" in ps_content`)에서 즉시 실패 (KILLED; 백엔드 CI 게이트의 소스 불변식 검사임).
3. **MUT-03 (관측 전용 노드 풀 편입 가드 해제 돌연변이)**:
   - 대상: `apps/web/src/features/desktop/ResourceExplorer.tsx`
   - 주입: `handleAddMember` 내 `if (targetNode?.observationOnly || targetNode?.schedulable === false)` 분기 조건 제거.
   - 사살 단언: `apps/web/tests/resource-explorer-dom.test.tsx`에서 관측 전용 노드 편입 차단 단언(spy 미호출·`role=alert`·거부 문구 검사) 실패 (KILLED).
4. **MUT-04 (미승인 Run ID 분산 계획 생성 허용 돌연변이)**:
   - 대상: `apps/web/src/features/desktop/ResourceExplorer.tsx`
   - 주입: `button[data-testid="create-plan-btn"]`의 `disabled={!planRunId.trim()}` 속성 제거 및 기본값으로 위조 `runId` 주입.
   - 사살 단언: `apps/web/tests/resource-explorer-dom.test.tsx:813` 및 `apps/web/tests/accessibility-status-and-guards.test.tsx:143`에서 `planRunId` 공백 시 버튼 비활성화 및 안내 배너 존재 단언 실패 (KILLED).
5. **MUT-05 (풀 집계 단일 노드 최대 한도 누락 돌연변이)**:
   - 대상: `apps/web/src/features/desktop/ResourceExplorer.tsx`
   - 주입: `largestSingleNode` 카드 렌더링을 삭제하고 `totalOffered` 카드만 단독 표시.
   - 사살 단언: `apps/web/tests/resource-explorer-dom.test.tsx:607`에서 3원 풀 집계 DOM 단언(`단일 노드 최대 한도 (Largest Single)` 및 `16C · 64 GB · 1 GPU`) 실패로 즉시 검출 (KILLED).

---

## 5. 실측 검증 하네스 설계 및 재현성 원칙 (F1~F5 반영, 승인 후 착수용)

> [!NOTE]
> 본 절은 Claude 및 Codex 독립 검토 승인 후 실제 실측 단계에서 사용할 하네스 및 환경 명세이다 (본 docs-only 단계에서는 일체 실행하지 않음; "실측은 승인 후").

### 5.1 F1~F5 하네스 불변식 설계 원칙
1. **F1 (이전 실행 잔여물 carry-over 원천 방지)**:
   - 각 시나리오 실행 전후로 로컬 스토리지, 인메모리 캐시, DOM 트리를 완전히 격리 초기화하여 이전 시나리오의 상태가 다음 시나리오에 잔존하지 않도록 보장한다.
2. **F2 (자기 주입 mock/단언 전면 금지)**:
   - 실측 시 임의의 monkey-patch나 컴포넌트 내부 주입 단언을 금지하며, Uvicorn 8080 제어 평면 서버 및 Vite 3005 프런트엔드의 실제 네트워크 소켓/어댑터 응답만을 관측한다.
3. **F3 (예외 경로 Evidence 명시적 수집)**:
   - 성공(200/201) 시나리오뿐만 아니라 401/409/422 등 부정 대조군(Negative control) 및 거부 경로의 ProblemDetails 응답 및 DOM 알림을 영구 Evidence에 온전히 기록한다.
4. **F4 (프로세스 트리 및 소켓 누수 차단)**:
   - 러너 시작 시 포트 충돌(8080, 3005)을 사전 감지하고, 러너 종료 시 하위 프로세스 트리를 확실히 종료하여 데몬 누수를 방지한다.
5. **F5 (우아한 미측정 UNMEASURED 게이트 규격, Exit Code 3)**:
   - 환경 미구비(백엔드 미기동, 실제 분산 노드 미배치 등) 시 비정상 크래시 대신 `STATUS: UNMEASURED (exit code 3)`으로 안전하게 종료하여 거짓 PASS/거짓 FAIL을 방지한다.

---

## 6. 검토 인계 및 다음 단계

- **문서 상태**: `status: "review"` (Codex 백엔드 계약 수정 요청 4건 및 Claude UI 검토 피드백 전면 반영 v1.2.0 완결)
- **독립 리뷰어**: Claude (Frontend/UI 셀렉터 및 DOM 경로 대조), Codex (커널 오류 코드, 3원 용량 계약, Zero Fake Shards 대조)
- **다음 단계**:
  1. Claude(hh) 및 Codex 리뷰어의 v1.2.0 정합성 독립 검토.
  2. 승인(APPROVED) 확인 후 코디네이터 지시에 따라 실측 스크립트 작성 및 실브라우저 수용 실측 착수.
