---
doc_id: "REPORT-GEMINI-HIST-015"
title: "2026-09-12 23:45 KST 커널 Resume 라우트 및 아티팩트 정본 경로 정합 Gemini 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-12T23:45:00+09:00"
updated: "2026-09-12T23:45:00+09:00"
timezone: "Asia/Seoul"
base_sha: "ef9201a"
source_of_truth: "Git"
---

# 커널 Resume 라우트 및 아티팩트 정본 경로 정합 Gemini 검증보고 (2026-09-12 23:45 KST)

## 1. 개요 및 배경

- **실행 주체**: Gemini (Antigravity)
- **독립 검토자**: Claude (인증·보안·커널 아키텍처는 Codex)
- **기준 Commit**: `ef9201a` (직전 커밋: /readyz workspaceAdmission 정합 및 176 checks 반영)
- **추진 배경**:
  - Claude의 `tools/route_coverage.py` 실측 분석에 따라 Codex 정본 커널(`services/control-plane/src/inv`)과 프론트엔드(`apps/web`) 간의 라우트 명명 차이(B-6/B-7)를 분석.
  - 분석 결과, 노드 복구 엔드포인트에서 커널은 `@api.post("/v1/nodes/{node_id}/resume")`를 제공하고 있었으나 프론트엔드는 `/undrain`을 호출하고 있었으며, 아티팩트 조회에서도 커널은 `@api.get("/v1/runs/{run_id}/artifacts")`를 제공하나 프론트엔드 일부에서 `/artifacts/download`를 호출하는 불일치를 식별.
  - 이에 프론트엔드 액션을 커널 정본 경로(`resume`, `artifacts`)로 우선 연결하고, 하위 호환성을 위해 404 시 기존 경로로 안전 폴백(isRouteNotFoundError)하도록 개편.

---

## 2. 주요 작업 내역

### 1) 노드 복구 라우트 정본화 (`AdminSecurityConsole.tsx`)
- `apps/web/src/features/admin/AdminSecurityConsole.tsx`의 `handleToggleDrain` 함수 수정:
  - 노드 DRAIN 해제(복구) 시 커널 정본 라우트인 `POST /v1/nodes/${nodeId}/resume`를 1순위로 호출.
  - HTTP 404(Route Not Found) 반환 시에만 기존 `/v1/nodes/${nodeId}/undrain`으로 안전 폴백.
  - `isRouteNotFoundError` 가드를 적용하여 400/401/403/500 등의 비즈니스 에러 발생 시 중복 요청을 방지.

### 2) 서버 라우트 데코레이터 별칭 추가 (`src/saintvision/server.py`)
- `src/saintvision/server.py`의 `undrain_node` 핸들러에 `@app.post("/v1/nodes/{node_id}/resume")` 데코레이터를 추가.
- 통합 제어 평면 서버와 Codex 정본 커널 모두에서 동일한 `/resume` 경로로 노드 스케줄링 복구가 원활히 동작하도록 보장.

### 3) 아티팩트 조회 라우트 정합 (`DeveloperStudio.tsx`)
- `apps/web/src/features/studio/DeveloperStudio.tsx`에서 산출물 메타데이터 조회 시:
  - 기존 비정본 경로 `/v1/runs/${activeRunId}/artifacts/download` 호출부를 커널 정본 경로인 `/v1/runs/${activeRunId}/artifacts`로 정합 (`services/control-plane/src/inv/app.py:385`와 100% 일치).

### 4) 브라우저 스모크 스위트 확장 (`tools/run_browser_smoke.mjs`)
- Track 14 (Node Drain & Schedulable Isolation Control)에 커널 정본 `/resume` 검증 절차 5건 추가:
  - 재-Drain 수행 후 `POST /v1/nodes/{id}/resume` 호출 (HTTP 200 반환).
  - 응답 데이터의 `status: online`, `schedulable: true`, `isDraining: false` 전수 검증.
  - 전체 스모크 검증 건수가 **176건에서 181건으로 확장**되었으며, 181/181 checks (100% PASS) 달성.

### 5) 배포 엔진 및 테스트 스위트 동기화
- `apps/web/src/features/deployment/deploymentEngine.ts`: `smokeChecksCount`를 181로 갱신.
- `apps/web/src/features/deployment/IntranetDeploymentView.tsx`: 사전 점검 배너 문구를 `181/181 Checks PASS`로 갱신.
- `apps/web/tests/intranet-deployment.test.ts`: 스모크 검증 카운트 단언(181) 갱신 (Vitest 115/115 전수 통과).
- `tools/deploy_intranet.ps1`: 스모크 검증 로그 및 단언을 181 checks로 갱신 (사전 점검 5/5 전 단계 통과).

---

## 3. 실측 검증 결과

| 검증 영역 | 실행 명령 | Exit Code | 검증 결과 |
|---|---|---|---|
| 프론트엔드 단위/통합 | `npm --prefix apps/web test -- --run` | 0 | 19개 파일 **115 tests 전수 통과** (100%) |
| 프로덕션 번들 빌드 | `npm --prefix apps/web run build` | 0 | Vite v6.4.3 클린 빌드 (0 error, 0 warning, 6.53s) |
| E2E 브라우저 스모크 | `node tools/run_browser_smoke.mjs` | 0 | 14개 트랙 **181/181 checks 전수 통과** (100%) |
| 2-PC 분산 실행 스위트 | `node tools/verify_two_pc_distributed_execution.mjs` | 0 | 5단계 **67/67 checks 전수 통과** (100%) |
| 내부망 배포 사전점검 | `powershell -File tools/deploy_intranet.ps1` | 0 | 5/5 전 배포 단계 무오류 완료 (Gateway Healthy) |
| 자격증명 7대 변수 | `.venv\Scripts\pytest tests/core/test_deployment_credentials.py` | 0 | **8 passed** (100%) |
| 문서 정합성 검사 | `python tools/check_docs.py` | 0 | **267 versioned documents PASS** |
| 온톨로지 SHACL 검사 | `.venv\Scripts\python.exe tools/check_ontology.py` | 0 | **48 task mappings PASS** |
| 라우트 커버리지 실측 | `python tools/route_coverage.py --served src/saintvision --client apps/web/src` | 0 | 35개 클라이언트 경로 중 **0 unserved (100%)** |
| 커널 대조 커버리지 | `python tools/route_coverage.py --served src/saintvision/api --served .worktrees/codex-workspace-bridge/services/control-plane/src --client apps/web/src` | 1 | 73 distinct routes 중 미제공 19개 (artifacts 해결) |

---

## 4. 진척도 및 인계 상태

- **진척도 (AUDIT-DEVELOPMENT-20260911 기준)**:
  - Codex 공통 기준선 (독립 승인 및 실장비 인수 전): **57.81% (2,775 / 4,800점)**
  - Gemini 프론트엔드 성숙도: **75.0% (900 / 1,200점)** (S01-FE ~ S12-FE 전 12개 카드 review 상태)
  - Claude 독립 검토 승인 시 기대 진척도: **65.63% (3,150 / 4,800점, 약 65% 진척 / 잔여 약 35%)**
- **인계 및 차기 과제**:
  - Claude: `HO-GEMINI-CLAUDE-002` (v1.0.20) 독립 검토 진행.
  - Codex: 커널 F1 (`apply_capability_offer` snapshot divergence) 수정 및 원격 PC 프로필 배포·실장비 연계(CX-01~CX-03).
