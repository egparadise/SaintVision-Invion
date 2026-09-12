---
doc_id: "HISTORY-20260912-181800-GEMINI"
title: "Gemini Mutation 중복 제출 방지 안전성 통제 및 Terminal 정본 API 연동 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-12T18:18:00+09:00"
updated: "2026-09-12T18:18:00+09:00"
source_of_truth: "Git"
---

# Gemini Mutation 중복 제출 방지 안전성 통제 및 Terminal 정본 API 연동 검증보고

- **작업 일시**: 2026-09-12 18:18:00 KST
- **작업자**: Gemini (Antigravity)
- **독립 검토자**: Claude (인증·보안 경계는 Codex)
- **작업 브랜치**: `integration/all-agents-unified`
- **대상 작업 카드**: `GM-01`, `GM-03`, `GM-05` (부모 Task: `S01-FE`, `S03-FE`, `S04-FE`, `S06-FE`, `S08-FE`, `S11-FE`)

---

## 1. 작업 배경 및 목적

1. **Codex 지적사항("mutation의 평면 fallback/중복 제출 안전성") 해소**:
   - Codex가 `agent/codex/workspace-bridge`의 진행판에서 지적한 바와 같이, POST/PUT 등 서버 상태를 변경하는 Mutation 호출에서 에러 발생 시 무조건 하위 평면 경로로 재시도하면 네트워크 지연, 인가 실패, 유효성 위반 상황에서 중복 제출(duplicate POST) 및 상태 왜곡이 발생할 위험이 있음.
   - 따라서 에러 응답의 HTTP 상태 코드가 정확히 **404 (Route Not Found / 엔드포인트 미구현)**일 때에만 하위 호환 평면 경로로 fallback하도록 제한하고, 400(잘못된 요청), 401(미인증), 403(2인 승인 위반), 409(충돌), 500(서버 오류) 등 비즈니스 검증 실패나 권한 거부 시에는 **중복 제출 없이 에러를 즉시 상위로 전파(re-throw)**하도록 안전장치를 구축.
2. **Workspace Terminal Tickets & WebSocket 정본 API 연동 (ADR-038)**:
   - 프론트엔드 터미널 컴포넌트(`WebTerminal.tsx`)에서 정본 커널 경로(`/v1/workspaces/${workspaceId}/terminal-tickets`)를 1차 호출하고 404 시에만 평면 `/v1/terminal/tickets`로 fallback하도록 정합.
   - 백엔드(`src/saintvision/server.py`)에 `@app.post("/v1/workspaces/{workspace_id}/terminal-tickets")` 및 `@app.websocket("/v1/workspaces/{workspace_id}/terminals/{session_id}")` 라우트를 등록하여 정본 커널 형태와 완전 일치시킴.

---

## 2. 세부 구현 내역

### 2.1 Mutation Fallback 안전성 강화

- **`apps/web/src/app/App.tsx`**:
  - `handleApprove`: `/v1/projects/${prjId}/approvals/${approvalId}/decision` 호출 실패 시, `err?.problem?.status === 404`일 때만 `/v1/approvals/${approvalId}/approve` fallback. 403 Two-Person Rule 등 거부 시 재제출 차단 및 즉시 throw.
  - `handleReject`: 404일 때만 `/v1/approvals/${approvalId}/reject` fallback.
  - `handleCancelRun`: 404일 때만 `/v1/runs/${runId}/cancel` fallback.
- **`apps/web/src/features/studio/DeveloperStudio.tsx`**:
  - `handleCancelSubmit`: `/v1/projects/${selectedProjectId}/runs/${activeRunId}/cancel` 1차 호출, 404 시에만 fallback.
  - `handlePrepareResume`: 404 시에만 fallback.
- **`apps/web/src/features/runs/RunDetail.tsx`**:
  - `handlePrepareResume`: `/v1/projects/${prjId}/runs/${run.id}/resume/prepare` 1차 호출, 404 시에만 fallback.

### 2.2 Terminal Tickets & WebSocket 정본 경로 연동

- **`apps/web/src/features/terminal/WebTerminal.tsx`**:
  - `/v1/workspaces/${workspaceId}/terminal-tickets` 우선 호출 및 404 fallback 적용.
- **`src/saintvision/server.py`**:
  - `@app.post("/v1/workspaces/{workspace_id}/terminal-tickets", status_code=201)` 데코레이터 추가 및 `ws_id` 바인딩.
  - `@app.websocket("/v1/workspaces/{workspace_id}/terminals/{session_id}")` 데코레이터 추가.
- **`tests/test_server_project_api.py`**:
  - `test_workspace_terminal_tickets_canonical` 단위 시험 추가 (정본 경로 201 Created 및 평면 호환 201 검증 통과).

---

## 3. 검증 결과 요약 (Zero-Mock 준수 실측)

| 검증 영역 | 실행 명령 | 결과 | 상세 내역 |
|---|---|---|---|
| **Route Coverage Tool** | `python tools/route_coverage.py --served src/saintvision --client apps/web/src` | **Exit 0 (0 unserved)** | 클라이언트 33개 경로 중 미제공 0개 (70 routes 제공, 100% 커버리지) |
| **Frontend Unit Tests** | `npm --prefix apps/web test -- --run` | **109/109 PASS** | 19개 테스트 파일 109개 테스트 전수 통과 (3.06s) |
| **Frontend Build** | `npm --prefix apps/web run build` | **Exit 0** | Vite v6.4.3 프로덕션 번들 클린 생성 (6.33s, 0 error, 0 warning) |
| **Pytest Server API** | `pytest tests/test_server_project_api.py` | **6/6 PASS** | 프로젝트 런/취소/노드/승인/재개/터미널 티켓 전수 통과 (1.43s) |
| **E2E Browser Smoke** | `node tools/run_browser_smoke.mjs` | **174/174 PASS** | 14개 트랙 전수 100% 통과 (Track 9 정본 워크스페이스 터미널 검증 포함) |
| **2-PC Distributed Execution** | `node tools/verify_two_pc_distributed_execution.mjs` | **67/67 PASS** | 5단계 분산 실행, OIDC PKCE 인증, GPU 스케일링 전수 100% 통과 |
| **Intranet Deploy Preflight** | `powershell -File tools/deploy_intranet.ps1` | **5/5 PASS** | Nginx TLS 1.3, FastAPI Gateway, Compose 오케스트레이션 무오류 통과 |
| **Docs & Ontology Check** | `python tools/check_docs.py`, `check_ontology.py` | **PASS / PASS** | 260개 문서, 48개 태스크 온톨로지 전수 정합 |

---

## 4. 진척도 및 인계 상태

- **진척도 (AUDIT-DEVELOPMENT-20260911 기준)**:
  - Codex 공통 기준선 (독립 승인 및 실장비 미인수 기준): **57.81% (2,775 / 4,800점)**
  - Gemini 영역 구현 성숙도: **75.0% (900 / 1,200점, 전 12개 FE 태스크 75점 최고 구현 상태 달성)**
  - Claude 독립 검토 통과 시 전체 진척도: **65.63% (3,150 / 4,800점, 약 65% 진척 / 잔여 약 35%)**
- **인계서 갱신**: [[Gemini_GM01-06_프론트엔드_독립검토_인계서]] (`HO-GEMINI-CLAUDE-002` v1.0.13)
- **다음 행동**: Claude 독립 피어 리뷰(CL-01), Codex factory entrypoint 복원 및 원격 7개 시험(CX-01~03) 연계 대기.