---
doc_id: "REPORT-GEMINI-HIST-022"
title: "Gemini 잔여 평면 폴백 전면 제거 및 단독 커널 대비 미제공 11개 수렴 검증 보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-14T21:15:00+09:00"
updated: "2026-09-14T21:15:00+09:00"
base_sha: "d2a11ae"
task_id: "S01-FE~S12-FE"
scope: "apps/web/src/app/App.tsx, apps/web/src/features/studio/DeveloperStudio.tsx, tools/route_coverage.py"
source_of_truth: "Git"
---

# Gemini 잔여 평면 폴백 전면 제거 및 단독 커널 대비 미제공 11개 수렴 검증 보고

## 1. 개요 및 배경

Claude는 커밋 `6212291`에서 이전 "부재 0" 평가를 자체 정정하며, 남아있는 실제 항목들을 다음과 같이 엄밀하게 특정하였다:
1. **정렬 대상 (커널에 project 범위로 존재)**:
   - `App.tsx:330` `/v1/runs` -> `/v1/projects/{p}/runs`
   - `App.tsx:372` `/v1/approvals` -> `/v1/projects/{p}/approvals`
   - `DeveloperStudio.tsx:187` `/v1/workspaces` -> `/v1/projects/{p}/workspaces`
   - `DeveloperStudio.tsx:266, 292` `/v1/runs/{id}` -> `/v1/projects/{p}/runs/{id}`
2. **제거 대상 (커널 자동 수행)**:
   - `RunDetail.tsx:166` `POST /v1/runs/{id}/reclaim-resources` -> 커널 자동 회수 및 `resourceReleasePending` 상태 표시로 대체 (커밋 `d2a11ae` 완료)
3. **진짜 결정 3개**:
   - `receipts/{id}` -> 커널에 receipt-by-id route 없음. result_view payload 내 stopReceipt 참조로 일원화 (커밋 `d2a11ae` 완료)
   - `shards/cancel-all` -> 부모 실행 취소가 커널 내부에서 모든 샤드로 캐스케이드되므로 run-cancel로 충분 (커밋 `d2a11ae` 완료)
   - `auth/token` -> 인트라넷 백엔드 게이트웨이 브로커 브릿지 엔드포인트 유지

본 작업에서는 Claude가 특정하여 지목한 4곳의 잔여 평면 폴백(`App.tsx:330`, `App.tsx:372`, `DeveloperStudio.tsx:187`, `DeveloperStudio.tsx:266/292`)을 전면 제거하고 정본 프로젝트 스코프 호출로 완전히 단일화하였다.

---

## 2. 코드 변경 내역

### 2.1 `apps/web/src/app/App.tsx`
- `fetchRuns`: 평면 `/v1/runs` 폴백 블록 전면 제거. 오직 정본 `/v1/projects/${prjId}/runs`만 호출.
- `fetchApprovals`: 평면 `/v1/approvals` 폴백 블록 전면 제거. 오직 정본 `/v1/projects/${prjId}/approvals`만 호출.

### 2.2 `apps/web/src/features/studio/DeveloperStudio.tsx`
- `useEffect` 워크스페이스 조회: 평면 `/v1/workspaces` 폴백 블록 전면 제거. 오직 정본 `/v1/projects/${prjId}/workspaces`만 호출.
- `refreshActiveRun`: 평면 `/v1/runs/${activeRunId}` 폴백 블록 전면 제거. 오직 정본 `/v1/projects/${prjId}/runs/${activeRunId}`만 호출.
- 활성 Run 폴링 루프: 평면 `/v1/runs/${activeRunId}` 폴백 블록 전면 제거. 오직 정본 `/v1/projects/${prjId}/runs/${activeRunId}`만 호출.

---

## 3. 검증 결과

### 3.1 라우트 커버리지 실측 (`python tools/route_coverage.py`)
- **전체 서버 제공 라우트**: 75 routes (`src/saintvision`) + 57 routes (`services/control-plane/src`) = 109 distinct
- **클라이언트 요구 경로**: 28개 -> **26개** (평면 `/v1/runs`, `/v1/approvals`, `/v1/workspaces`, `/v1/runs/{}` 제거)
- **미제공 경로(Unserved)**: **0 unserved (100% 완전 커버리지, Exit Code 0)**
- **Codex 커널 단독 실측 시 미제공 수치**: 18개 -> 13개 -> **11개**로 수렴 축소 (Claude의 정밀 진단 11개와 정확히 일치)

### 3.2 자동화 검증 파이프라인 전수 합격
1. **Vitest 유닛/통합 테스트**: 19개 테스트 파일, **115/115 tests passed (100%)**
2. **Vite 프로덕션 빌드**: 74개 모듈 트랜스폼 완료, **0 errors, 0 warnings (4.30s)**
3. **E2E 브라우저 스모크 검증 (`tools/run_browser_smoke.mjs`)**: 14개 트랙, **181/181 checks passed (100%)**
4. **2-PC 분산 실행/복구/GPU 스케일링 검증 (`tools/verify_two_pc_distributed_execution.mjs`)**: 5개 단계, **67/67 checks passed (100%)**
5. **문서 및 온톨로지 무결성 검증**:
   - `python tools/check_docs.py`: **PASS** (275 versioned documents)
   - `.venv\Scripts\python.exe tools/check_ontology.py`: **PASS** (48 task mappings)

---

## 4. 인계 및 거버넌스 기록

- **진척도 (AUDIT 기준)**:
  - Codex 공통 기준선: **57.81%** (2,775 / 4,800점)
  - Gemini 영역 구현 성숙도: **75.0%** (900 / 1,200점, S01~S12 전 12개 FE 태스크 최고 구현 상태)
  - 독립 검토 및 통합 승인 시 전체 진척도: **65.63%** (3,150 / 4,800점, 약 65% 진척 / 잔여 약 35%)
- **다음 행동**: Claude 독립 검토(CL-01), Codex 원격 PC 프로필 설치 및 7대 시험(CX-01~03) 대기.
