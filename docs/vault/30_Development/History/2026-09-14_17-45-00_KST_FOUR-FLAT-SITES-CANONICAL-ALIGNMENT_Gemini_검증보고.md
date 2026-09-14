---
doc_id: "REPORT-GEMINI-HIST-018"
title: "2026-09-14 17:45 KST 4대 평면 라우트 잔여 정합 및 커널 정본화 완결 Gemini 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-14T17:45:00+09:00"
updated: "2026-09-14T17:45:00+09:00"
timezone: "Asia/Seoul"
base_sha: "e238b2b"
source_of_truth: "Git"
---

# 4대 평면 라우트 잔여 정합 및 커널 정본화 완결 Gemini 검증보고 (2026-09-14 17:45 KST)

## 1. 개요 및 배경

- **실행 주체**: Gemini (Antigravity)
- **독립 검토자**: Claude (인증·보안·커널 아키텍처는 Codex)
- **기준 Commit**: `e238b2b` (직전 커밋: Kernel ResultView 및 ArtifactList 타입화 완결)
- **추진 배경**:
  - Claude의 잔여 SPA flat call sites 정밀 분석(`Agent 인계 대기 목록.md` / commit `6484ae1`) 수용.
  - 프론트엔드(`apps/web/src`) 전역에 잔존하던 4대 평면(flat) 경로 및 레거시 폴백을 커널 정본 라우트로 전면 정합:
    1. `AdminSecurityConsole.tsx:49`: `/v1/nodes/${nodeId}/undrain` 폴백 제거 -> 커널 정본 `POST /v1/nodes/${id}/resume` 단일 경로 사용.
    2. `App.tsx:381,414`: `/v1/approvals/${id}/approve|reject` 폴백 제거 -> 커널 정본 `POST /v1/projects/${p}/approvals/${id}/decision` (`{ decision: 'approve'|'reject', nonce, reason }`) 단일 경로 사용.
    3. `WebTerminal.tsx:55,138`: `/v1/terminal/tickets` 폴백 제거 -> 커널 정본 `POST /v1/workspaces/${id}/terminal-tickets` 단일 경로 사용.
    4. `deploymentEngine.ts:71`: `/v1/terminal/ws` 레거시 규칙 제거 -> 커널 정본 `/v1/workspaces/{id}/terminals/{sessionId}` 규칙 단일화 및 `intranet-deployment.test.ts` 단언 정합.

---

## 2. 주요 작업 내역

### 1) 노드 복구 라우트 정합 (`AdminSecurityConsole.tsx`)
- 미지원 평면 엔드포인트 `/undrain` 호출을 완전히 제거하고, 양측 백엔드가 공통 지원하는 커널 정본 `POST /v1/nodes/${nodeId}/resume`로 일원화.
- 불필요해진 `isRouteNotFoundError` 미사용 import 제거.

### 2) 프로젝트 승인 판정 라우트 정합 (`App.tsx`)
- `handleApprove` 및 `handleReject`에서 레거시 평면 엔드포인트(`/v1/approvals/...`)로의 fallback을 제거하고, 커널 정본 `POST /v1/projects/${prjId}/approvals/${approvalId}/decision`으로 단일화.

### 3) 워크스페이스 터미널 티켓 라우트 정합 (`WebTerminal.tsx`)
- 초기 연결 및 재접속 시의 레거시 평면 엔드포인트 `/v1/terminal/tickets` fallback을 제거하고, 커널 정본 `POST /v1/workspaces/${workspaceId}/terminal-tickets`로 단일화.
- 불필요해진 `isRouteNotFoundError` 미사용 import 제거.

### 4) Nginx 라우팅 규칙 및 배포 테스트 정합 (`deploymentEngine.ts`, `intranet-deployment.test.ts`)
- `deploymentEngine.ts`의 `nginxRoutingRules`에서 구형 `/v1/terminal/ws` 규칙을 삭제하고, ADR-038 정본인 `/v1/workspaces/{id}/terminals/{sessionId}` 규칙만 유지.
- `intranet-deployment.test.ts`에서 정본 워크스페이스 터미널 WebSocket 프록시 규칙 검증으로 단언 정합.

---

## 3. 실측 검증 결과

| 검증 영역 | 실행 명령 | Exit Code | 검증 결과 |
|---|---|---|---|
| 라우트 커버리지 실측 | `python tools/route_coverage.py --served src/saintvision/api --served .worktrees/codex-workspace-bridge/services/control-plane/src --client apps/web/src` | 1 | 클라이언트 요청 경로 **37 -> 32개로 축소**, 미제공 경로 **21 -> 16개로 대폭 축소** (평면 4대 사이트 전원 해소) |
| 라우트 커버리지 단위 테스트 | `.venv\Scripts\pytest tests/test_route_coverage.py` | 0 | 15개 테스트 전수 통과 (100%) |
| Vitest 단위 테스트 | `npm --prefix apps/web test -- --run` | 0 | 19개 파일 **115/115 passed (100%)** |
| Vite 프로덕션 빌드 | `npm --prefix apps/web run build` | 0 | TypeScript 엄격 컴파일 통과, 74개 모듈 번들링 완료 (0 error, 0 warning) |
| 브라우저 스모크 스위트 | `node tools/run_browser_smoke.mjs` | 0 | 14개 트랙 **181/181 checks passed (100%)** |
| 2-PC 분산 실행 검증 | `node tools/verify_two_pc_distributed_execution.mjs` | 0 | 5단계 **67/67 checks passed (100%)** |
| 인트라넷 배포 사전검증 | `powershell -File tools/deploy_intranet.ps1` | 0 | 5/5 전 배포 파이프라인 무오류 통과 (Gateway Healthy on :8080) |
| 문서 및 링크 정합성 | `python tools/check_docs.py` | 0 | 270개 버전 관리 문서 전수 통과 |
| 역온톨로지 정합성 | `.venv\Scripts\python.exe tools/check_ontology.py` | 0 | 48개 태스크 매핑 및 SHACL 전수 통과 |

---

## 4. 진척도 및 인계 상태

- **공식 진척도 (AUDIT-DEVELOPMENT-20260911 기준)**:
  - **Codex 공통 기준선**: **57.81% (2,775 / 4,800점)** (약 58% 또는 약 55%)
  - **Gemini 프론트엔드 성숙도**: **75.0% (900 / 1,200점)** (S01-FE ~ S12-FE 전 12개 카드 review 상태)
  - **Claude 독립 검토 서명 완료 시 전체 진척도**: **65.63% (3,150 / 4,800점, 약 65% 진척 / 잔여 약 35%)**
- **인계 사항**:
  - Claude의 `HO-GEMINI-CLAUDE-002` (v1.0.23) 독립 검토 대기.
  - 잔여 미제공 4개 경로(승인 목록, 자원 reclaim, 샤드 목록, 샤드 전체 취소)는 Codex의 정본 커널 계약 결정 대기.
