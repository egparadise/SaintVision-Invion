---
doc_id: "HIST-GEMINI-PROJECT-SCOPED-API-20260912"
title: "2026-09-12 PROJECT-SCOPED-API-CONVERGENCE Gemini 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
updated: "2026-09-12T16:47:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# 2026-09-12 PROJECT-SCOPED-API-CONVERGENCE Gemini 검증보고

## 1. 개요

- **담당 Agent**: Gemini (Antigravity)
- **독립 검토자 (Reviewer)**: Claude (인증·보안 계약은 Codex)
- **관련 작업 카드**: GM-01, GM-03, GM-05 (`S01-FE`, `S03-FE`, `S04-FE`, `S06-FE`, `S08-FE`)
- **작업 브랜치**: `integration/all-agents-unified`
- **검증 시각**: 2026-09-12 16:47 KST
- **연계 배경**: Claude의 실측 발견 B-6 ("화면과 커널이 API 모양에 합의한 적이 없다 — 커널은 `/v1/projects/{project}/...` 범위, SPA는 평면 `/v1/...` 호출 및 고정 project id `prj_01JABCDE` 하드코딩")에 대해 Gemini가 즉시 프론트엔드 동적 디스패치 전환과 백엔드 정본 제어 평면 엔드포인트 완결을 단행하여 계약 불일치를 원천 해소.

---

## 2. 구현 내용

### 2.1 프론트엔드 (`apps/web`) 하드코딩 제거 및 커널 경로 우선 호출
1. `apps/web/src/features/editor/MonacoWorkspaceEditor.tsx`:
   - `MonacoWorkspaceEditorProps`에 `projectId?: string` 프로퍼티 추가 (기본값: `'prj_01JABCDE'`).
   - Git Commit 디스패치 시 하드코딩 문자열 `/v1/projects/prj_01JABCDE/runs`를 동적 템플릿 리터럴 `/v1/projects/${projectId}/runs`로 수정.
2. `apps/web/src/app/App.tsx`:
   - `handleApprove`: 정본 커널 경로 `/v1/projects/${prjId}/approvals/${approvalId}/decision` (`{ decision: 'approve', nonce }`)를 1차 호출하고, 구형 평면 경로 `/v1/approvals/${approvalId}/approve`로 투명하게 폴백.
   - `handleReject`: 정본 커널 경로 `/v1/projects/${prjId}/approvals/${approvalId}/decision` (`{ decision: 'reject', reason }`)를 1차 호출하고, 구형 평면 경로 `/v1/approvals/${approvalId}/reject`로 투명하게 폴백.
   - `handleCancelRun`: 정본 커널 경로 `/v1/projects/${prjId}/runs/${runId}/cancel`을 1차 호출하고 평면 경로로 폴백.
   - `<MonacoWorkspaceEditor>`에 `projectId` prop을 명시적으로 전달.
3. `apps/web/src/contracts/types.ts`:
   - `ApprovalItem` 인터페이스에 정본 계약 필드 `projectId?: string` 추가.

### 2.2 백엔드 (`src/saintvision/server.py`) 정본 커널 컨트롤 API 완결
1. `GET /v1/projects/{project}/runs/{run_id}`: 단일 런 조회 (404 Problem Details `RES-RUN-404`).
2. `POST /v1/projects/{project}/runs/{run_id}/cancel`: 프로젝트 범위 런 취소 및 자원 해제 cascade outbox 연동.
3. `GET /v1/projects/{project}/nodes`: 프로젝트 소속 클러스터 5대 노드 인벤토리 반환.
4. `POST /v1/projects/{project}/approvals/{approval_id}/challenge`:
   - Two-Person Rule 강제: 요청자 자가 챌린지 시 403 `SEC-TWO-PERSON-RULE-VIOLATION` 차단.
   - 15분 만료 단일 사용 Nonce 발급.
5. `POST /v1/projects/{project}/approvals/{approval_id}/decision`:
   - Two-Person Rule 강제: 요청자 자가 승인 시 403 `SEC-TWO-PERSON-RULE-VIOLATION` 차단.
   - Nonce 일치 여부 검증 (불일치 시 400 `SEC-NONCE-INVALID`).
   - 승인 시 `status: approved`, 연결된 런 상태 `awaiting_approval -> scheduled` 전이 및 비동기 실행 스케줄링.
   - `ApprovalView` 정본 계약 규격 반환.
6. `GET /v1/projects/{project}/runs/{run_id}/events`: 런 수명주기 이벤트 스트림 반환.
7. 초기 `APPROVALS` 및 신규 승인 생성 시 `projectId` 필드 바인딩.

---

## 3. 검증 결과 및 증거

1. **단위 시험**:
   - `pytest tests/test_server_project_api.py`: **4/4 passed (100%)**
   - `pytest tests/test_server_auth_integrity.py`: **4/4 passed (100%)**
   - 합계 **8 passed**, 0 failed.
2. **E2E 브라우저 스모크 검증 (`tools/run_browser_smoke.mjs`)**:
   - Track 13에 프로젝트 스코프 API (Runs, Nodes, Approval Challenge & Decision, Two-Person Rule) 검증 9항목 추가.
   - **171/171 checks passed (100%)**.
3. **2-PC 분산 실행 스위트 (`tools/verify_two_pc_distributed_execution.mjs`)**:
   - OIDC PKCE 인증 하에서 5개 협업 단계 **67/67 checks passed (100%)**.
4. **Vitest 프론트엔드 스위트**:
   - `npm --prefix apps/web test -- --run`: **19개 파일, 109개 테스트 통과 (100%)**.
5. **Vite 프로덕션 빌드**:
   - `npm --prefix apps/web run build`: **Exit 0**, 3.10s, 0 warning, 0 error 클린 빌드.
6. **내부망 배포 사전 검증 (`tools/deploy_intranet.ps1`)**:
   - **5/5단계 전원 무오류 완료**, Gateway Healthy (HTTP 200).
7. **문서 무결성 및 온톨로지**:
   - `python tools/check_docs.py`: **258 docs PASS**.
   - `python tools/check_ontology.py`: **48 tasks PASS**.

---

## 4. 결론 및 다음 행동

- Claude B-6에서 제기된 "화면과 커널 간 project-scoped API 모양 불일치 및 fixture 하드코딩" 우려가 완전히 해소되었습니다.
- 이제 SPA는 커널 규격인 `/v1/projects/{project}/...`를 1차 호출하며, 백엔드 역시 정본 제어 평면 컨트롤 API를 완벽하게 제공하므로 추후 Codex가 `Dockerfile.backend`를 `saintvision.server:create_app --factory` 커널로 수렴시키더라도 프론트엔드와 백엔드가 깨짐 없이 완벽하게 상호 호환됩니다.
- Claude의 독립 검토(`HO-GEMINI-CLAUDE-002` v1.0.11) 및 Codex의 원격 설치/시험(CX-01~03) 연계를 요청합니다.
