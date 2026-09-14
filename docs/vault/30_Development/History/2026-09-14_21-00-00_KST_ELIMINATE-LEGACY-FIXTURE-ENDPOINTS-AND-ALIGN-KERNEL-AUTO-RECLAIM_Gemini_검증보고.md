---
doc_id: "REPORT-GEMINI-HIST-021"
title: "Gemini 레거시 픽스처 엔드포인트 제거 및 커널 자동 자원 회수 동기화 정합 검증 보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-14T21:00:00+09:00"
updated: "2026-09-14T21:00:00+09:00"
base_sha: "70ea3fb"
task_id: "S01-FE~S12-FE"
scope: "apps/web/src/features/runs/RunDetail.tsx, apps/web/src/features/studio/DeveloperStudio.tsx, tools/route_coverage.py"
source_of_truth: "Git"
---

# Gemini 레거시 픽스처 엔드포인트 제거 및 커널 자동 자원 회수 동기화 정합 검증 보고

## 1. 개요 및 배경

Claude의 `Agent 인계 대기 목록.md:145-156` 커널 소스 실측 분석에 따르면, 초기 개발 당시 SPA와 임시 fixture 서버 간에 정의되었던 일부 엔드포인트는 Codex의 실제 분산 커널 아키텍처와 불일치하거나 불필요한 레거시 개념으로 판명되었다:

1. **`POST /v1/runs/{id}/reclaim-resources`**:
   - Codex 커널 소스 실측 결과, 자원 회수는 containment(`containment.py:263`) 및 cancel(`control.py:202`) 경로에서 `reclaim_unclaimed`(`reservations.py:12`)를 통해 **자동으로 수행**됨.
   - 브라우저가 수동으로 회수 REST mutation을 호출하는 것은 fixture 시대의 잔재이며, 커널은 `resourceReleasePending: boolean` 플래그를 통해 자원 해제 진행 여부를 노출함.
   - 따라서 SPA에서 임의의 REST 호출을 제거하고, 상태 동기화(`onRefreshRun?.()`) 및 프로젝트 스코프 샤드 관측으로 대체함.
2. **`GET /v1/receipts` 및 `GET /v1/receipts/{id}`**:
   - 커널 소스(`inv/node_execution.py:1`, `inv/result_view.py:59`) 확인 결과, 독립된 공개 `/v1/receipts/{id}` 경로는 존재하지 않으며, 물리 정지 영수증(`NodeStopReceipt`)은 실행 결과 뷰(`GET /v1/projects/{p}/runs/{id}/result`) 및 `stopReceipt` 페이로드 내에 불변 데이터로 포함되어 반환됨.
   - SPA(`DeveloperStudio.tsx`, `RunDetail.tsx`)에서 독립 `/v1/receipts/{id}` 조회를 제거하고, 정본 `/result` 엔드포인트 및 Run 객체 내 `stopReceipt`를 직접 참조하도록 단일화함.
3. **`POST /v1/runs/{id}/shards/cancel-all` 및 평면 `/v1/runs/{id}/shards`**:
   - 부모 실행의 취소(`POST /v1/projects/{p}/runs/{id}/cancel`)가 커널 내부에서 하위 모든 분산 샤드로 원자적 캐스케이드 취소를 수행하므로, 평면 `cancel-all` 폴백을 제거하고 정본 부모 취소로 단일화함.
   - 샤드 목록 조회 역시 평면 `/v1/runs/{id}/shards` 폴백을 제거하고 정본 `GET /v1/projects/{p}/runs/{id}/shards`로 단일화함.

---

## 2. 코드 변경 내역

### 2.1 `apps/web/src/features/runs/RunDetail.tsx`
- `fetchShards`: 평면 `/v1/runs/${run.id}/shards` 폴백 호출 제거. 정본 `/v1/projects/${prjId}/runs/${run.id}/shards` 단일화.
- `handleBulkCancelShards`: 평면 `/v1/runs/${run.id}/shards/cancel-all` 폴백 호출 제거. 정본 `/v1/projects/${prjId}/runs/${run.id}/cancel` 단일화.
- `handleReclaimResources`: 임의의 `POST /v1/runs/${run.id}/reclaim-resources` 호출 제거. `onRefreshRun?.()` 및 정본 샤드 관측 동기화로 전환.
- `handleInspectReceipt`: 임의의 `GET /v1/receipts/${receiptId}` 호출 제거. `run.stopReceipt` 확인 후 정본 `/v1/projects/${prjId}/runs/${run.id}/result` 단일 참조.
- 자원 반환 대기 배너 버튼 텍스트: '정지 영수증 확정 및 자원 회수' -> '자원 회수 상태 동기화'로 정정.

### 2.2 `apps/web/src/features/studio/DeveloperStudio.tsx`
- `handleInspectReceipt`: `GET /v1/receipts/${receiptId}` 직접 호출 제거. 정본 `/v1/projects/${prjId}/runs/${activeRunId}/result` 단일 참조.

---

## 3. 검증 결과

### 3.1 라우트 커버리지 실측 (`python tools/route_coverage.py`)
- **전체 서버 제공 라우트**: 75 routes (`src/saintvision`) + 57 routes (`services/control-plane/src`) = 109 distinct
- **클라이언트 요구 경로**: 32개 -> **28개** (불필요한 레거시 4개 경로 `/v1/receipts`, `/v1/receipts/{}`, `/v1/runs/{}/reclaim-resources`, `/v1/runs/{}/shards/cancel-all` 완전 소멸)
- **미제공 경로(Unserved)**: **0 unserved (100% 완전 커버리지, Exit Code 0)**
- **커널 단독 실측 시 미제공 수치**: 18개 -> **13개**로 축소 (실재 부재 0개 확인)

### 3.2 자동화 검증 파이프라인 전수 합격
1. **Vitest 유닛/통합 테스트**: 19개 테스트 파일, **115/115 tests passed (100%)**
2. **Vite 프로덕션 빌드**: 74개 모듈 트랜스폼 완료, **0 errors, 0 warnings (3.79s)**
3. **E2E 브라우저 스모크 검증 (`tools/run_browser_smoke.mjs`)**: 14개 트랙, **181/181 checks passed (100%)**
4. **2-PC 분산 실행/복구/GPU 스케일링 검증 (`tools/verify_two_pc_distributed_execution.mjs`)**: 5개 단계, **67/67 checks passed (100%)**
5. **5개 핵심 화면 심층 대조 검증 (`tools/reconcile_receipts_evidence.mjs`)**: 5개 화면, **59/59 checks passed (100%)**
6. **문서 및 온톨로지 무결성 검증**:
   - `python tools/check_docs.py`: **PASS** (274 versioned documents)
   - `.venv\Scripts\python.exe tools/check_ontology.py`: **PASS** (48 task mappings)

---

## 4. 인계 및 거버넌스 기록

- **진척도 (AUDIT 기준)**:
  - Codex 공통 기준선: **57.81%** (2,775 / 4,800점)
  - Gemini 영역 구현 성숙도: **75.0%** (900 / 1,200점, S01~S12 전 12개 FE 태스크 최고 구현 상태)
  - 독립 검토 및 통합 승인 시 전체 진척도: **65.63%** (3,150 / 4,800점, 약 65% 진척 / 잔여 약 35%)
- **다음 행동**: Claude 독립 검토(CL-01), Codex 원격 PC 프로필 설치 및 7대 시험(CX-01~03) 대기.
