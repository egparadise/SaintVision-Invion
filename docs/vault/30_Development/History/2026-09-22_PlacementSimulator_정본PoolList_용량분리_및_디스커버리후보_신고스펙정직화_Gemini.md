---
doc_id: "HIST-20260922-GEMINI-POOL-DISCOVERY-INTEGRITY"
title: "PlacementSimulator 정본 PoolList 연동, 용량 분리 및 디스커버리 후보 신고스펙 정직화와 정직성 스캐너 Rule 9 확장"
version: "1.0.0"
status: "completed"
author: "Gemini"
created: "2026-09-22T09:23:00+09:00"
updated: "2026-09-22T09:23:00+09:00"
source_of_truth: "Git"
---

# PlacementSimulator 정본 PoolList 연동, 용량 분리 및 디스커버리 후보 신고스펙 정직화와 정직성 스캐너 Rule 9 확장

## 1. 개요 및 배경

- **배경**: Codex가 `/v1/pools` 엔드포인트를 구현하여 정본 `PoolListResponse`, 스키마, TypeScript 타입(`pool-list-response.ts`), 어댑터(`getPoolList`)를 integration 브랜치에 착지시켰다.
- **핵심 설계 원칙 (풀 목록과 용량의 계약적 분리)**:
  - Codex는 의도적으로 풀 목록(`PoolListResponse`)에 휘발성 용량(`totalOffered`, `spareNow` 등)을 포함하지 않았다. 목록에 용량을 번들링하면 낡은 용량이 목록 캐시와 함께 굳어버리는 신선도 부패(Staleness Corruption)가 발생하기 때문이다.
  - 따라서 화면은 식별과 멤버 수만 풀 목록에서 읽고, 용량 정보는 `GET /v1/pools/{id}/capacity`(`getPoolCapacity`)를 통해 온디맨드로 분리 조회해야 한다.
- **지적 사항 및 부류 교정 (Discovery 후보 과잉 기대 및 허위 합성 박멸)**:
  - `PlacementSimulator.tsx`가 등록 전인 디스커버리 후보에 대해 `availableCores`, `availableMemoryBytes`, `healthStatus: 'online'`, `gpuName` 등 백엔드가 결코 줄 수 없는 허위 필드를 상상하고 있었다.
  - 디스커버리 후보는 아직 클러스터에 편입되지 않은 등록 대기 머신(`state: 'candidate'`, `verified: false`)이다. 후보가 자체 신고한 스펙(`claimedCpuCores`, `claimedRamBytes`, `claimedGpuCount`)을 실제 측정된 "가용량(`available`)"으로 둔갑시키거나, 건강 상태를 `online`으로 합성하여 표출하는 것은 운영자에게 치명적인 안전 환각을 유발한다.

---

## 2. 작업 내역

### 1) PlacementSimulator 정본 PoolList 연동 및 용량 분리 조회 (`PlacementSimulator.tsx`)
- **수기 `PoolItem` 제거 및 정본 바인딩**:
  - `export type PoolItem = PoolListItemResponse;`로 정합하고 `getPoolList()` 어댑터에 결속.
  - raw `apiClient<{ items: PoolItem[] }>('/v1/pools')` 호출을 영구 제거.
  - `selectedPoolId` 식별자를 `p.poolId`로 통일.
- **풀 용량 온디맨드 분리 조회 (`getPoolCapacity`)**:
  - `poolCapacity` 및 `poolCapacityState`('idle' | 'loading' | 'success' | 'error') 상태 신설.
  - `selectedPoolId` 변경 시 `getPoolCapacity(selectedPoolId)`를 별도 호출하여 정본 `spareNow` 및 `totalOffered`로부터 실시간 가용량 표출.
  - `Math.round(poolCapacity.spareNow.cpuMillicores / 1000)} / {Math.round(poolCapacity.totalOffered.cpuMillicores / 1000)} Cores`
  - `Math.round(poolCapacity.spareNow.ramBytes / 1024 ** 3)} / {Math.round(poolCapacity.totalOffered.ramBytes / 1024 ** 3)} GB`
  - `poolCapacity.totalOffered.gpuDevices > 0 ? ... : 'GPU 없음 (CPU 풀)'`
  - 활성 멤버 수(`activeMemberCount / memberCount`) 정직 표출.

### 2) Discovery 후보 허위 합성 소거 및 신고 스펙 정직화 (`PlacementSimulator.tsx`)
- **수기 `CandidateItem` 소거 및 정본 바인딩**:
  - `export type CandidateItem = DiscoveryCandidateResponse;`로 정합하고 `getDiscoveryCandidates()` 어댑터에 결속.
  - raw `apiClient<{ items: CandidateItem[] }>('/v1/discovery/candidates')` 호출을 영구 제거.
- **3대 필드 부류 교정**:
  1. **신고값 명시**: `availableCores`와 `availableMemoryBytes`를 소거하고, 장비가 자체 보고한 `claimedCpuCores`, `claimedRamBytes`, `claimedGpuCount`를 `"신고 스펙 (Claimed · 실측 가용량 아님): 8C / 32 GB"`로 정직하게 고지.
  2. **미제공 고지**: 후보 스키마에 부재한 `gpuName`을 아는 척하지 않고 `"모델: 미제공 (등록 후 감지)"`로 처리.
  3. **허위 `online` 합성 박멸**: `c.healthStatus === 'online'` 뱃지를 완전 영구 소거하고, 후보 정본 상태인 `CANDIDATE (미검증)` 경고/대기 뱃지(`rgba(234, 179, 8, 0.15)`, `#fbbf24`)로 교정.
  4. **식별자 교정**: 미실재 `nodeId` 대신 정본 `c.announcementId`를 고유 키로 사용.

### 3) 정직성 스캐너 Rule 9 확장 (`tools/check_frontend_integrity.py`)
- **Rule 9: Canonical Wire Contract & Adapter Invariant 확장**:
  - `POOL_LIST_DIRECT_API_REGEX`: `fabricControlApi.ts` 외의 컴포넌트에서 `/v1/pools`를 raw `apiClient`로 직접 호출하는 우회 패턴 차단.
  - `DISCOVERY_CANDIDATES_DIRECT_API_REGEX`: `fabricControlApi.ts` 외의 컴포넌트에서 `/v1/discovery/candidates`를 raw `apiClient`로 직접 호출하는 우회 패턴 차단.
- **음성 대조군(Negative Control) Test 12 확장**:
  - 직접 우회 코드 주입 시 100% 감지 및 즉각 실패 사살 실측.
  - `--test-negative` 100% PASS 실측.
  - 프로덕션 82개 파일 검사 0 violations PASS 실측.

### 4) 신규 단위 테스트 2종 구축 (`apps/web/tests/placement-simulator.test.tsx`)
- Test 1: `renders canonical pool capacity when pool list and capacity are provided` — 풀 목록과 capacity가 온디맨드로 결합되어 `12 / 16 Cores`, `48 / 64 GB`, `1/2 GPUs`, `활성 멤버: 2/3 노드`로 정확히 렌더링됨을 단언.
- Test 2: `renders honest claimed specs and unverified status for discovery candidates without fake online synthesis` — `cand-worker-01` 후보의 `신고 스펙 (Claimed · 실측 가용량 아님)` 문구 및 `CANDIDATE (미검증)` 뱃지 렌더링 단언, `online` 및 `가용 코어` 위조 부재 단언.
- 전체 Vitest 스위트 결과: **75개 파일 655/655 passed 100% (순증 +2 passed)**.

---

## 3. 검증 실측 증거 (Evidence)

| 검증 단계 | 명령 | 결과 | 소요 시간 | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **TypeScript 컴파일** | `cd apps/web && npx tsc -b` | **0 errors** (exit 0) | 7.82s | 컴파일 오류 0건 |
| **Production 빌드** | `cd apps/web && npm run build` | **built in 3.24s** (exit 0) | 3.24s | 761.38 kB 프로덕션 번들 정상 생성 |
| **Vitest 단위 테스트** | `cd apps/web && npm run test` | **75 files / 655 passed** (100%) | 12.90s | 신규 테스트 2종 순증 (+2 passed) |
| **정직성 스캐너 (대조군)** | `python tools/check_frontend_integrity.py --test-negative` | **All 9 rules sensitive** (exit 0) | 0.45s | Rule 9 풀/후보 직접호출 차단 검증 |
| **정직성 스캐너 (프로덕션)**| `python tools/check_frontend_integrity.py` | **82 files, 0 violations** (exit 0) | 0.48s | All 9 rules satisfied |
| **파이썬 라우트 게이트** | `.venv/Scripts/pytest tests/test_route_coverage.py` | **30 passed** (exit 0) | 0.90s | 화면-백엔드 라우트 무결성 불변식 통과 |
| **계약 바인딩 검사** | `python tools/check_contract_bindings.py` | **48 fixtures / 14 anchors PASS** | 3.20s | 와이어 계약 바인딩 완벽 유지 |
| **문서 단일 소스 래칫** | `python tools/check_doc_single_source.py --ratchet` | **18 pairs, all in baseline** | 0.52s | 회귀 0건 |
