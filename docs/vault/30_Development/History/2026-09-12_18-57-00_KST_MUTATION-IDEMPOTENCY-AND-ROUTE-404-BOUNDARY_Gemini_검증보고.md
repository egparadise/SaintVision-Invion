---
doc_id: "HISTORY-20260912-185700-GEMINI"
title: "Gemini Mutation 멱등성 보장 및 Route 404 경계 판별 안전성 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-12T18:57:00+09:00"
updated: "2026-09-12T18:57:00+09:00"
source_of_truth: "Git"
---

# Gemini Mutation 멱등성 보장 및 Route 404 경계 판별 안전성 검증보고

- **작업 일시**: 2026-09-12 18:57:00 KST
- **작업자**: Gemini (Antigravity)
- **독립 검토자**: Claude (인증·보안 경계는 Codex)
- **작업 브랜치**: `integration/all-agents-unified`
- **대상 작업 카드**: `GM-01`, `GM-03`, `GM-05` (부모 Task: `S01-FE`, `S03-FE`, `S04-FE`, `S06-FE`, `S08-FE`, `S11-FE`)

---

## 1. 작업 배경 및 목적

1. **Codex 비판("404는 객체 미존재·권한 은닉일 수 있으므로 404만으로 재제출 안전 미보장") 완전 해소**:
   - Codex가 제시한 핵심 비판:
     > *"404는 라우트 부재뿐 아니라 객체 미존재·권한 은닉 응답일 수도 있으므로 404만으로 안전한 재제출을 보장한다고 인정하지 않는다. 명시적 API capability/version 선택 또는 동일 idempotency/scope 보장 검토가 필요하며 kernel 연결/물리 인수와 별개다."*
   - 단순 `status === 404` 검사는 위험합니다. 만약 백엔드 컨트롤러가 엔티티 미존재나 테넌트 격리/권한 마스킹으로 인해 404 ProblemDetails(`RES-RUN-404`, `RES-APPROVAL-404` 등)를 반환한 경우, 이를 라우트 부재로 착각하고 레거시 평면 경로로 재제출하면 중복 제출, 권한 우회 프로빙 또는 데이터 오염이 발생할 수 있습니다.
   - 따라서 **FastAPI/Starlette 프레임워크 수준의 라우터 미매핑 404(`{"detail": "Not Found"}` 또는 `NET-404`)**와 **비즈니스 도메인의 리소스 부재 404(`RES-*`)**를 엄격히 분리하는 `isRouteNotFoundError(err)` 경계 판별자를 설계·도입하였습니다.
2. **상태 변경 Mutation의 고유 멱등성(Idempotency-Key) 보장**:
   - 재시도나 대체 경로 요청 시 동일한 작업이 2번 실행되지 않도록, 모든 Mutation 요청에 `Idempotency-Key` 헤더를 주입하는 메커니즘을 `apiClient`와 주요 컴포넌트에 구축하였습니다.

---

## 2. 세부 구현 내역

### 2.1 API 클라이언트 멱등성 헤더 및 라우트 부재 경계 함수 (`client.ts`)

- **`apps/web/src/shared/api/client.ts`**:
  - `RequestOptions` 인터페이스에 `idempotencyKey?: string` 추가 및 fetch 시 `Idempotency-Key` HTTP 헤더 자동 주입.
  - `isRouteNotFoundError(err: any): boolean` 함수 추가:
    - HTTP 404 상태가 아니면 즉시 `false`.
    - RFC 9457 ProblemDetails에 `RES-`, `APP-`, `SEC-`, `VAL-` 등 구조화된 애플리케이션 코드가 포함되어 있다면, 이는 백엔드 라우터가 정상 매핑되어 컨트롤러가 의도적으로 반환한 리소스 부재 또는 권한 은닉 응답이므로 즉시 `false` 반환 (하위 호환 fallback 절대 차단!).
    - FastAPI 라우터 미매핑 기본 응답(`detail === 'Not Found'`), 클라이언트 네트워크 합성 404(`code === 'NET-404'`), 또는 애플리케이션 코드가 없는 경우에만 라우트 부재로 판정하여 `true` 반환.

### 2.2 프론트엔드 전 Mutation 경로 적용

- **`apps/web/src/app/App.tsx`**:
  - `handleApprove`: 결정 API 호출 시 고유 `idmp_apprv_${approvalId}_${nonce}` 주입. 에러 발생 시 `isRouteNotFoundError(err)`를 만족할 때에만 평면 경로로 재시도. `SEC-TWO-PERSON-RULE-VIOLATION`(403) 등 비즈니스 실패 시 재제출 없이 즉시 re-throw.
  - `handleReject`: 고유 `idmp_reject_${approvalId}_${Date.now()}` 주입 및 `isRouteNotFoundError` 적용.
  - `handleCancelRun`: 고유 `idmp_cancel_${runId}` 주입 및 `isRouteNotFoundError` 적용.
- **`apps/web/src/features/studio/DeveloperStudio.tsx`**:
  - `handleCancelSubmit`: `idmp_cancel_${activeRunId}` 주입 및 `isRouteNotFoundError` 안전 fallback 적용.
  - `handlePrepareResume`: `idmp_resume_prep_${activeRunId}` 주입 및 `isRouteNotFoundError` 안전 fallback 적용.
- **`apps/web/src/features/runs/RunDetail.tsx`**:
  - `handlePrepareResume`: `idmp_resume_prep_${run.id}` 주입 및 `isRouteNotFoundError` 안전 fallback 적용.
- **`apps/web/src/features/terminal/WebTerminal.tsx`**:
  - 일회용 PTY 티켓 발급 시 raw fetch 대신 `apiClient` 사용으로 Bearer 토큰 연계.
  - `/v1/workspaces/${workspaceId}/terminal-tickets` 우선 호출 및 `isRouteNotFoundError(err)` 검증 하에만 `/v1/terminal/tickets` fallback 수행.

### 2.3 단위 테스트 스위트 확장 (`api-proxy.test.ts`)

- **`apps/web/tests/api-proxy.test.ts`**:
  - `Idempotency-Key` 헤더 주입 검증 테스트 케이스 추가.
  - `isRouteNotFoundError` 경계 판별 단위 테스트 추가:
    - FastAPI 기본 404 (`{ detail: "Not Found" }`) -> `true` 확인.
    - 클라이언트 합성 404 (`code === "NET-404"`) -> `true` 확인.
    - 도메인 404 (`RES-RUN-404`, "Run does not exist or is masked") -> `false` 확인 (fallback 차단).
    - 2인 규칙 거부 (`SEC-TWO-PERSON-403`) -> `false` 확인.
    - 상태 충돌 (`SEC-STATE-409`) -> `false` 확인.
    - 서버 에러 (`SYS-500`) -> `false` 확인.
  - Vitest 테스트 스위트: **19개 파일 114개 테스트 100% 통과**.

---

## 3. 검증 결과 실측 기록 (Zero-Mock Conformance)

| 검증 항목 | 실행 명령 | 결과 / 증거 | 상태 |
|---|---|---|---|
| Vitest 단위 테스트 | `npm --prefix apps/web test -- --run` | 19개 파일 114개 테스트 통과 (1.88s) | **PASS (100%)** |
| Vite 프로덕션 빌드 | `npm --prefix apps/web run build` | dist 번들 클린 생성 (0 error, 0 warning, 5.20s) | **PASS (100%)** |
| E2E 브라우저 스모크 | `node tools/run_browser_smoke.mjs` | 14개 트랙 174/174 검사 통과 (100%) | **PASS (100%)** |
| 2-PC 분산 실행 검증 | `node tools/verify_two_pc_distributed_execution.mjs` | 5개 협동 단계 67/67 검사 통과 (100%) | **PASS (100%)** |
| Pytest Project API | `.venv\Scripts\pytest tests/test_server_project_api.py` | 6/6 테스트 통과 (0.75s) | **PASS (100%)** |
| API 라우트 커버리지 | `python tools/route_coverage.py --served src/saintvision --client apps/web/src` | 70 routes 제공, 33 paths 요청, **0 unserved** | **PASS (100%)** |
| 내부망 배포 사전점검 | `powershell -File tools/deploy_intranet.ps1` | 5/5 전 배포 파이프라인 무오류 통과, Gateway Healthy | **PASS (100%)** |
| 거버넌스 문서 검사 | `python tools/check_docs.py` | 261개 버전 문서, 48개 태스크, 12개 outcome 무오류 | **PASS (100%)** |
| 온톨로지 지식그래프 | `.venv\Scripts\python.exe tools/check_ontology.py` | 48개 태스크 매핑, SHACL 검사, 4개 질의 통과 | **PASS (100%)** |

---

## 4. 진척도 및 인계 상태

1. **진척도 (AUDIT-DEVELOPMENT-20260911 기준 투명 산정)**:
   - **총점**: 48개 태스크 × 100점 = 4,800점.
   - **Codex 공통 기준선 (독립 승인 및 실장비 미인수 기준)**: **57.81%** (2,775 / 4,800점) (약 58% 또는 약 55%).
   - **Gemini 프론트엔드 영역 구현 성숙도**: **75.0%** (900 / 1,200점, `S01-FE` ~ `S12-FE` 전 12개 태스크 최고 구현 상태 도달, review 대기).
   - **Claude 독립 검토 통과 및 통합 승인 시 잠재 진척도**: 2,775점 + 375점 = **3,150 / 4,800점 = 65.63% (약 65% 진척 / 잔여 약 35%)**.
2. **독립 검토 및 협업 인계**:
   - 인계서: `HO-GEMINI-CLAUDE-002` (v1.0.14).
   - Claude(`CL-01`): 독립 검토 진행 가능.
   - Codex(`CX-01` ~ `CX-03`): `deploy/Dockerfile.backend` 팩토리 엔트리포인트 복원 및 `.225` 원격 PC 프로필 설치 대기.
