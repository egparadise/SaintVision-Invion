---
doc_id: "REPORT-GEMINI-HIST-025"
title: "Gemini 실행 결과 및 아티팩트 프로젝트 스코프 정합 및 평면 폴백 제거 검증 보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-14T22:30:00+09:00"
updated: "2026-09-14T22:30:00+09:00"
base_sha: "43640ee"
task_id: "S01-FE~S12-FE"
scope: "apps/web/src/features/runs/RunDetail.tsx, apps/web/src/features/studio/DeveloperStudio.tsx, src/saintvision/server.py"
source_of_truth: "Git"
---

# Gemini 실행 결과 및 아티팩트 프로젝트 스코프 정합 및 평면 폴백 제거 검증 보고

## 1. 개요 및 배경

Claude는 `4956787`에서 미제공 라우트 잔여 4건 중 `/v1/runs`를 "정렬 — 커널 `/v1/projects/{p}/runs` 존재. Gemini 잔여"로 분석하였다.
정밀 분석 결과, `tools/route_coverage.py`의 `_CLIENT_HEAD` 정규식이 `${...}` 앞의 리터럴 헤드를 추출함에 따라, `DeveloperStudio.tsx` 및 `RunDetail.tsx`의 템플릿 리터럴(`` `/v1/runs/${runId}/result` `` 등)에서 `/v1/runs/`가 추출되어 bare `/v1/runs`가 오인식되었음을 확인하였다.

또한 커널(`services/control-plane/src/inv/app.py:379-380`)은 이미 `/v1/projects/{project_id}/runs/{run_id}/result` 및 `/artifacts`를 정본으로 완전 제공하고 있었다. 이에 따라 Gemini(Antigravity)는 `DeveloperStudio.tsx`와 `RunDetail.tsx`의 아티팩트·결과 경로를 프로젝트 범위(`/v1/projects/${prjId}/runs/${runId}/...`)로 전면 정합하고 잔여 평면 폴백을 제거하였다.

---

## 2. 코드 정합 내역

### 2.1 DeveloperStudio.tsx 프로젝트 스코프 정합 및 평면 폴백 제거
- `DeveloperStudio.tsx:300`: 아티팩트 결과 조회 경로를 `GET /v1/projects/${prjId}/runs/${activeRunId}/result`로 전환.
- `DeveloperStudio.tsx:314, 324, 451`: 아티팩트 목록 조회 경로를 `GET /v1/projects/${prjId}/runs/${activeRunId}/artifacts`로 전환.
- `DeveloperStudio.tsx:518`: 원본 바이트 다운로드 경로를 `GET /v1/projects/${prjId}/runs/${activeRunId}/artifacts/content`로 전환.
- `DeveloperStudio.tsx:615`: 영수증 조회 시 `/v1/runs/${activeRunId}/result`로 떨어지던 평면 폴백 제거 및 미사용 `isRouteNotFoundError` import 정리.

### 2.2 RunDetail.tsx 잔여 평면 폴백 제거
- `RunDetail.tsx:181`: 영수증 모달 오픈 시 정본 `/v1/projects/${prjId}/runs/${run.id}/result` 조회 후 존재하던 `/v1/runs/${run.id}/result` 평면 폴백 코드 전면 제거 및 미사용 import 정리.

### 2.3 제어 평면 서버 별칭 데코레이터 추가 (`src/saintvision/server.py`)
- `server.py`의 `download_run_artifacts`, `read_run_result`, `list_run_artifacts`, `get_run_artifact_content` 함수에 `@app.get("/v1/projects/{project_id}/runs/{run_id}/...")` 별칭 데코레이터를 추가하여 커널과의 100% 동일 경로 상호 운용성 확보.

---

## 3. 검증 결과

### 3.1 라우트 커버리지 실측 (`python tools/route_coverage.py`)
- **클라이언트 요구 경로**: 24개 → **22개**로 압축.
- **통합 제공 라우트 대비 미제공**: **0 unserved (100% 완전 커버리지, Exit Code 0)**.
- **Codex 커널 단독 실측 시 미제공**: 11개 → **10개**로 축소 (`/v1/runs` 완전 소멸).

### 3.2 자동화 파이프라인 전수 합격
1. **Vitest 유닛/통합 테스트**: 21개 테스트 파일, **131/131 tests passed (100%)**.
2. **Vite 프로덕션 빌드 (`tsc -b && vite build`)**: 75개 모듈 트랜스폼 완료, **0 errors, 0 warnings (5.86s)**.
3. **E2E 브라우저 스모크 검증 (`tools/run_browser_smoke.mjs`)**: 14개 트랙, **181/181 checks passed (100%)**.
4. **2-PC 분산 실행/복구/GPU 스케일링 검증 (`tools/verify_two_pc_distributed_execution.mjs`)**: 5개 단계, **67/67 checks passed (100%)**.
5. **문서 및 온톨로지 무결성 검증**:
   - `python tools/check_docs.py`: **PASS** (277 versioned documents).
   - `.venv\Scripts\python.exe tools/check_ontology.py`: **PASS** (48 task mappings).

---

## 4. 인계 및 거버넌스 기록

- **진척도 (AUDIT 기준)**:
  - Codex 공통 기준선: **57.81%** (2,775 / 4,800점)
  - Gemini 영역 구현 성숙도: **75.0%** (900 / 1,200점, S01~S12 전 12개 FE 태스크 최고 구현 상태)
  - 독립 검토 및 통합 승인 시 전체 진척도: **65.63%** (3,150 / 4,800점, 약 65% 진척 / 잔여 약 35%)
- **Git 반영**: commit `9a57889` (`origin/integration/all-agents-unified`)
- **다음 행동**: Claude 독립 검토(CL-01), Codex 원격 PC 프로필 설치 및 7대 시험(CX-01~03) 연계 대기.
