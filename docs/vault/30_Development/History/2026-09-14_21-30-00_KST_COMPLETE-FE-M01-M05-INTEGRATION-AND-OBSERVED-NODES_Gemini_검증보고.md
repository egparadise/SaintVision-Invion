---
doc_id: "REPORT-GEMINI-HIST-023"
title: "Gemini Codex FE-M01~M05 변이 계약 전면 통합 및 관측 노드 동적 집계 완결 검증 보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-14T21:30:00+09:00"
updated: "2026-09-14T21:30:00+09:00"
base_sha: "4956787"
task_id: "S01-FE~S12-FE"
scope: "apps/web/src/app/App.tsx, apps/web/src/features/runs/RunDetail.tsx, apps/web/src/features/studio/DeveloperStudio.tsx, apps/web/tests/kernel-mutations.test.ts"
source_of_truth: "Git"
---

# Gemini Codex FE-M01~M05 변이 계약 전면 통합 및 관측 노드 동적 집계 완결 검증 보고

## 1. 개요 및 배경

Codex는 `agent/codex/frontend-mutations` 및 `test_frontend_mutation_contract.py`를 통해 프론트엔드의 mutation 계약 불일치를 정밀 분석하고 FE-M01~M05 요건을 정립하였다. Claude 역시 `c5c014e` 및 `4956787`에서 이를 검토하고 인정하였으며, "신규 커널 route가 필요한 실 결정은 0에 수렴하며, 화면이 픽스처 흐름을 정본으로 교체하는 것으로 B-6/7이 종결된다"고 판정하였다.

Gemini(Antigravity)는 Codex의 변경 사항(`agent/codex/frontend-mutations` @ `8037166`)을 통합하고 잔여 프론트엔드 연동을 전면 완결하였다.

---

## 2. 코드 통합 내역

### 2.1 FE-M01 (승인/반려 challenge-nonce-actionDigest 계약 정합)
- `apps/web/src/shared/api/kernelMutations.ts`: `decideApproval` 함수를 통해 `POST challenge`로 nonce를 사전 수신하고, 화면에 렌더링된 불변 `actionDigest` 및 Idempotency-Key를 포함하여 `POST decision` 호출.
- `apps/web/src/contracts/types.ts`: `ApprovalItem`에 `actionDigest?: string` 필드 추가 및 매핑 보존.
- `apps/web/src/features/approvals/ApprovalDetail.tsx`: `actionDigest` 유효성 검증 적용 및 정본 반려 호출 (`onReject(id, '')`).

### 2.2 FE-M02 & FE-M03 (버전 지정 취소 및 Idempotency-Key 무결성)
- `apps/web/src/shared/api/kernelMutations.ts`: `cancelKernelRun` 함수를 통해 직전 Run 버전을 조회하고 `{ expectedVersion: current.version }` 및 W3C/UUID 기반 `idempotencyKey`를 탑재하여 취소 발행.
- `apps/web/src/app/App.tsx`: `handleCancelRun`에 `cancelKernelRun` 연동. 서버 실패 시 임의로 state를 'cancelled'로 변경하지 않고 오류 알림 및 상태 보존.
- `apps/web/src/features/runs/RunDetail.tsx`: `handleBulkCancelShards`에서 `cancelKernelRun` 호출 연동.
- `apps/web/src/features/studio/DeveloperStudio.tsx`: `handleCancelSubmit`에서 `cancelKernelRun` 호출 연동.

### 2.3 FE-M04 (실제 관측 노드 집계 연동)
- `apps/web/src/app/App.tsx`: 헤더의 고정값 `onlineNodesCount={5}`를 제거하고, 실제 클러스터 노드 관측 상태 집계인 `nodes.filter(n => n.status === 'online').length` 및 `nodes.length`로 동적 바인딩.

### 2.4 FE-M05 (샤드 조회 로딩 상태 해제 안전성)
- `apps/web/src/features/runs/RunDetail.tsx`: 성공 분기 조기 리턴을 제거하고 공통 `finally` 블록에서 `setIsLoadingShards(false)`가 단일하게 안전 보장되도록 정합.

### 2.5 테스트 파일 배치 정합
- Codex가 추가한 `kernelMutations.test.ts`를 `apps/web/src`에서 `apps/web/tests/kernel-mutations.test.ts`로 배치 이동하여, 정적 라우트 검사기(`tools/route_coverage.py --client apps/web/src`)가 테스트 목 데이터의 리터럴 경로를 미서빙 라우트로 오인하지 않도록 조치.

---

## 3. 검증 결과

### 3.1 라우트 커버리지 실측 (`python tools/route_coverage.py`)
- **전체 서버 제공 라우트**: 75 routes (`src/saintvision`) + 57 routes (`services/control-plane/src`) = 109 distinct
- **클라이언트 요구 경로**: **24개**
- **미제공 경로(Unserved)**: **0 unserved (100% 완전 커버리지, Exit Code 0)**
- **Codex 커널 단독 실측 시 미제공 수치**: **11개** (Claude의 실측 수치와 100% 일치)

### 3.2 자동화 검증 파이프라인 전수 합격
1. **Vitest 유닛/통합 테스트**: 20개 테스트 파일, **127/127 tests passed (100%)** (`kernel-mutations.test.ts` 12개 포함)
2. **Vite 프로덕션 빌드**: 75개 모듈 트랜스폼 완료, **0 errors, 0 warnings (3.86s)**
3. **E2E 브라우저 스모크 검증 (`tools/run_browser_smoke.mjs`)**: 14개 트랙, **181/181 checks passed (100%)**
4. **2-PC 분산 실행/복구/GPU 스케일링 검증 (`tools/verify_two_pc_distributed_execution.mjs`)**: 5개 단계, **67/67 checks passed (100%)**
5. **문서 및 온톨로지 무결성 검증**:
   - `python tools/check_docs.py`: **PASS** (276 versioned documents)
   - `.venv\Scripts\python.exe tools/check_ontology.py`: **PASS** (48 task mappings)

---

## 4. 인계 및 거버넌스 기록

- **진척도 (AUDIT 기준)**:
  - Codex 공통 기준선: **57.81%** (2,775 / 4,800점)
  - Gemini 영역 구현 성숙도: **75.0%** (900 / 1,200점, S01~S12 전 12개 FE 태스크 최고 구현 상태)
  - 독립 검토 및 통합 승인 시 전체 진척도: **65.63%** (3,150 / 4,800점, 약 65% 진척 / 잔여 약 35%)
- **다음 행동**: Claude 독립 검토(CL-01), Codex 원격 PC 프로필 설치 및 7대 시험(CX-01~03) 대기.
