---
doc_id: "REPORT-GEMINI-HIST-020"
title: "Claude 잔여 평면 스코프 전면 정합 및 커널 프로젝트 경로 완전 수렴 검증 보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-14T20:15:00+09:00"
updated: "2026-09-14T20:15:00+09:00"
source_of_truth: "Git"
---

# Claude 잔여 평면 스코프 전면 정합 및 커널 프로젝트 경로 완전 수렴 검증 보고

## 1. 개요 및 배경

- **작업 일시**: 2026-09-14T20:15:00+09:00 (KST)
- **작업자**: Gemini (Antigravity)
- **대상 카드**: `GM-01`, `GM-02`, `GM-03`, `GM-05` (부모 Task: `S01-FE`, `S03-FE`, `S04-FE`, `S06-FE`, `S07-FE`)
- **목표**:
  - Claude의 2차 후속 권고(Gemini 작업 현황 비고 110행)에 명시된 잔여 flat scope 호출처 5개 사이트를 커널 프로젝트 스코프 정본으로 100% 수렴:
    1. `App.tsx:320`: 런 목록 조회를 `GET /v1/projects/${prjId}/runs` 우선 호출로 전환.
    2. `DeveloperStudio.tsx:179`: 워크스페이스 목록 조회를 `GET /v1/projects/${prjId}/workspaces` 우선 호출로 전환.
    3. `DeveloperStudio.tsx:247, 263`: 활성 런 조회 및 폴링 루프를 `GET /v1/projects/${prjId}/runs/${activeRunId}` 우선 호출로 전환.
    4. `RunDetail.tsx:65`: `POST /v1/runs/${id}/resume/prepare` 평면 폴백을 제거하고 커널 정본 `POST /v1/projects/${prjId}/runs/${run.id}/resume/prepare` 단일 정본 호출.
    5. `App.tsx:421` & `DeveloperStudio.tsx:566, 605`: `cancel` 및 `resume/prepare`의 잔여 평면 폴백 전면 제거.
    6. `src/saintvision/server.py`: `@app.get("/v1/projects/{project}/workspaces")` 구현 추가.
    7. `tools/route_coverage.py` 실측: **32개 클라이언트 요청 경로 전수 제공 (0 unserved, 100% 완전 커버리지, Exit Code 0)**.

---

## 2. 세부 정합 내역

### 2.1 런 및 워크스페이스 조회 프로젝트 스코프 정합
- `apps/web/src/app/App.tsx`:
  - `fetchRuns`: `apiClient<{ items: RunItem[] }>(`/v1/projects/${prjId}/runs`)` 1순위 호출 및 `setRuns` 연동.
- `apps/web/src/features/studio/DeveloperStudio.tsx`:
  - `workspaces`: `apiClient<{ items: WorkspaceItem[] }>(`/v1/projects/${prjId}/workspaces`)` 1순위 호출.
  - `refreshActiveRun` & `poll`: `apiClient<RunItem>(`/v1/projects/${prjId}/runs/${activeRunId}`)` 1순위 호출.

### 2.2 런 취소 및 재개 준비 뮤테이션 평면 폴백 완전 제거
- `apps/web/src/app/App.tsx`:
  - `handleCancelRun`: `POST /v1/runs/${runId}/cancel` 평면 폴백 제거, 커널 정본 `POST /v1/projects/${prjId}/runs/${runId}/cancel` 직접 호출.
- `apps/web/src/features/runs/RunDetail.tsx`:
  - `handlePrepareResume`: `POST /v1/runs/${run.id}/resume/prepare` 평면 폴백 제거, 커널 정본 `POST /v1/projects/${prjId}/runs/${run.id}/resume/prepare` 직접 호출.
- `apps/web/src/features/studio/DeveloperStudio.tsx`:
  - `handleCancelSubmit` & `handlePrepareResume`: 평면 경로 폴백 전면 제거, 프로젝트 스코프 정본 엔드포인트 직접 호출.

### 2.3 서버 라우트 확장 (`src/saintvision/server.py`)
- `@app.get("/v1/projects/{project}/workspaces")` 신설: 프로젝트 필터링된 워크스페이스 목록 반환.

---

## 3. 검증 결과 및 증거 (Evidence)

| 검증 항목 | 실행 명령 | 결과 / Exit Code | 증거 및 메트릭 |
|---|---|---|---|
| **Route Coverage** | `python tools/route_coverage.py --served src/saintvision --served .worktrees/codex-workspace-bridge/services/control-plane/src --client apps/web/src` | **PASS (0)** | 75 server routes, 57 kernel routes, 109 combined. 32 client paths. **0 unserved (100% 완전 제공)** |
| **Unit Tests** | `npm --prefix apps/web test -- --run` | **PASS (0)** | 19개 테스트 파일, **115/115 테스트 100% 통과** (2.70s) |
| **Production Build** | `npm --prefix apps/web run build` | **PASS (0)** | Vite v6.4.3 프로덕션 번들 생성 완료 (74 모듈 변환, 0 warning, 0 error, 3.93s) |
| **Browser Smoke** | `node tools/run_browser_smoke.mjs` | **PASS (0)** | 14개 트랙, **181/181 checks 100% 통과** |
| **2-PC Distributed** | `node tools/verify_two_pc_distributed_execution.mjs` | **PASS (0)** | 5개 단계, **67/67 checks 100% 통과** |
| **Intranet Deploy** | `powershell -File tools/deploy_intranet.ps1` | **PASS (0)** | 5/5 배포 전단계 무오류 통과 (Gateway Healthy on :8080) |
| **Documentation Check** | `python tools/check_docs.py` | **PASS (0)** | 272 versioned documents PASS |
| **Ontology Check** | `.venv\Scripts\python.exe tools/check_ontology.py` | **PASS (0)** | 48 task mappings PASS |

---

## 4. 거버넌스 및 성숙도 상태 (AUDIT 기준)

- **Codex 공통 기준선 (독립 승인·실장비 미인수 기준)**: **57.81%** (2,775 / 4,800점, 약 58% 또는 약 55%)
- **Gemini Frontend 영역 성숙도**: **75.0%** (900 / 1,200점, `S01-FE` ~ `S12-FE` 전 12개 태스크 최고 구현 점수 달성, `review` 상태)
- **독립 검토 및 통합 승인 시 잠재 진척도**: **65.63%** (3,150 / 4,800점, **약 65% 진척 / 잔여 약 35%**)
- **후속 담당 및 조치**:
  - Claude: `HO-GEMINI-CLAUDE-002` 독립 검토 완료 및 서명.
  - Codex: 원격 PC(192.168.45.225) 프로필 설치 및 7개 시험(`CX-03`) 연계.
  - Gemini: 피드백 대응 및 실장비 인수 준비 대기.
