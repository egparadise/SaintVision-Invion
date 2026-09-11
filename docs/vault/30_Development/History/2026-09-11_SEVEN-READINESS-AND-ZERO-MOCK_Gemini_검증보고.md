---
doc_id: "HIST-SEVEN-READINESS-ZERO-MOCK-20260911"
title: "SEVEN-READINESS-AND-ZERO-MOCK Gemini 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
updated: "2026-09-11T16:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["development", "studio", "readiness", "zero-mock", "result-view", "lineage", "gemini"]
---

# Developer Studio 7대 전제조건 검증, Zero-Mock 결과 바인딩 및 MLOps 계보 정비 검증보고

- **작업 소유자**: Gemini (Antigravity)
- **검토 대기**: Codex / Claude
- **소유 영역**: Frontend, Developer Studio UX, 7대 전제조건 Execution Readiness, Canonical ResultView, Zero-Mock 다운로드 계약, MLOps 계보 동적 지표, 브라우저 검증
- **기준 규칙**: `AGENTS.md`, `GEMINI.md`, `skills/frontend-delivery/SKILL.md`

---

## 1. 구현 개요 및 주요 성과

Codex 및 Claude와의 협력 계약 및 지침에 따라 다음 4대 핵심 요구사항을 화면과 백엔드에 충실히 반영하였다:

### A. Execution Readiness 7대 전제조건 완성 및 입력 매니페스트 바인딩 (`DeveloperStudio.tsx`, `types.ts`, `server.py`)
- **7대 전제조건 표준화 (ADR-063 및 `execution_readiness.py` 준수)**:
  1. `project_linked_to_kernel`: 프로젝트 커널 연동 여부 (해결 담당: `operator`)
  2. `requester_registered_with_kernel`: 실행 요청자 승인 주체 등록 여부 (해결 담당: `operator`)
  3. `role_permits_requesting`: 프로젝트 역할 요청 권한 여부 (해결 담당: `project owner`)
  4. `workspace_ready`: 워크스페이스 스토리지 프로비저닝 완료 여부 (해결 담당: `project owner`)
  5. `kernel_request_permission`: 계정·프로젝트 실행 허가(Execution Grant) 여부 (해결 담당: `operator`)
  6. `tool_chosen_and_usable`: 개발 도구 선택 및 타겟 노드 검증 여부 (해결 담당: `node owner`)
  7. `input_prepared`: 입력 매니페스트 및 동결 파일 준비 여부 (해결 담당: `requester`)
- **스냅샷 바운드 시각화**: `input_prepared` 검증 시 `snapshotBytes` (예: 1,024 Bytes) 및 `maxSnapshotBytes` (65,536 Bytes / 64 KiB), `maxContentBytes` (32,768 Bytes)를 화면에 정밀하게 표시.
- **담당자 배지 및 Remedy 안내**: 7개 전제조건 각각의 미충족 시 해결 권한자(`operator`, `project owner`, `node owner`, `requester`)와 조치 권한 안내를 명시.

### B. 임의 준비·성공 표시 제거 (Zero-Mock Enforced)
- **Readiness Fetch Fallback 제거**:
  - 기존 `DeveloperStudio.tsx`의 `.catch` 블록에서 API 응답 실패 시 임의로 `satisfied: true` 객체를 합성하던 잔여 모의 코드를 전면 제거.
  - API 조회 실패 시 `readiness = null`로 설정하고 `readinessError`에 실제 실패 원인을 기록.
  - 화면에 명시적인 실패 배너(`⚠️ 준비 상태 검증 실패`)를 렌더링하고, 실행 버튼(`Dispatch Run`)을 안전하게 잠금(`🔒 실행 불가 (검증 실패)`).
- **합성 증거 ID 및 임의 ExitCode 제거**:
  - 산출물 다운로드 및 결과 조회 시 `evi_${runId}` 형태의 임의 ID 합성을 전면 폐지하고, 서버가 반환한 `verifiedEvidenceId` (또는 `null`)를 정본으로 사용.
  - 정지 영수증(`NodeStopReceipt`) 미수신 시 `{ exitCode: 0, physicallyStopped: true }`를 임의로 제조하지 않고 `executionReceipt: null` 및 `exitCode: 미확인`으로 정직하게 표현.

### C. 검증된 파일 다운로드 및 정본 ResultView 연동 (`server.py`, `DeveloperStudio.tsx`)
- `GET /v1/runs/{id}/result`: 실행 커널의 정본 `ResultView` (`sealed`, `stopReceipt`, `output SHA-256`, `verifiedEvidenceId`) 연동.
- `GET /v1/runs/{id}/artifacts`: 산출물 목록 (`checksumSha256`, `byteSize`, `evidenceId`) 정본 연동.
- `GET /v1/runs/{id}/artifacts/download`: 불변 매니페스트와 실제 출력 해시를 포함한 JSON 아티팩트 다운로드 보장.

### D. MLOps 계보 및 AI 평가 동적 지표 정비 (`ModelLineageView.tsx`)
- 고정 텍스트("2개 Deployed, 1개 Staging", "100% 적합 (Codex = Claude)")를 모델 목록과 어댑터 적합성 배열에 기반한 동적 계산식으로 교체.
- `datasetDigest`, `sourceCommitSha`, `evalAccuracy`, `evalF1Score`의 null-safe 포맷팅 도입.

---

## 2. 검증 결과 및 합격 증거

모든 단위·빌드·E2E 브라우저 스모크·2-PC 분산 실행·문서 및 온톨로지 검증을 100% 통과하였다 (Exit Code 0).

### A. 단위 및 통합 테스트 (Vitest)
- 명령: `npm --prefix apps/web test -- --run`
- 결과: **19개 테스트 파일, 102개 테스트 전원 통과 (0 failures, 2.98s)**

### B. 프로덕션 번들 빌드 (TypeScript & Vite)
- 명령: `npm --prefix apps/web run build`
- 결과: **TypeScript (`tsc -b`) 타입 검사 100% 통과, Vite 프로덕션 번들 빌드 성공 (3.91s, Exit Code 0)**

### C. E2E 브라우저 여정 스모크 테스트
- 명령: `node tools/run_browser_smoke.mjs`
- 결과: **13개 트랙, 126개 점검 항목 전원 통과 (126/126 checks passed, 100%)**
  - Track 13 신규 추가: `GET /v1/workspaces/{id}/execution-readiness` (7대 전제조건 및 `input_prepared` 검증)
  - Track 13 신규 추가: `GET /v1/runs/{id}/result` (execution-kernel 정본 ResultView 연동 확인)
  - Track 13 신규 추가: `GET /v1/runs/{id}/artifacts` (execution-kernel 정본 artifacts 연동 확인)

### D. 2-PC 분산 실행 및 GPU 확장 검증
- 명령: `node tools/verify_two_pc_distributed_execution.mjs`
- 결과: **5단계 협력 파이프라인, 63개 검증 항목 전원 통과 (63/63 checks passed, 100%)**

### E. 문서 정본 및 온톨로지 무결성 검증
- `python tools/check_docs.py`: **24 original hashes, 224 versioned documents, wiki links, 48 tasks PASS**
- `python tools/check_ontology.py`: **RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings PASS**

---

## 3. 변경 파일 내역

- `apps/web/src/contracts/types.ts`: `ExecutionReadinessCheck` 인터페이스에 스냅샷 및 runId 필드 확장
- `src/saintvision/server.py`:
  - `read_workspace_readiness`: 7번째 전제조건 `input_prepared` 추가 및 요약 갱신
  - `download_run_artifacts`, `read_run_result`, `list_run_artifacts`: 임의 합성 `evi_{run_id}` 제거
- `apps/web/src/features/studio/DeveloperStudio.tsx`:
  - 임의 준비 모의 코드(`.catch` 합성 fallback) 제거 및 `readinessError` 배너/실행 차단 도입
  - 7대 전제조건 매트릭스 UI, 스냅샷 크기 표시기 및 해결 권한자 뱃지 렌더링
  - Step 4 및 아티팩트 다운로드에서 임의 receipt 및 exitCode 합성 제거
- `apps/web/src/features/mlops/ModelLineageView.tsx`:
  - 배너 지표의 정적 문자열을 모델 상태 및 적합성 데이터에 연동된 동적 표현으로 정비
  - 계보 노드 전반의 null-safe 포맷팅 적용
- `tools/run_browser_smoke.mjs`:
  - Track 13에 7대 전제조건, `input_prepared`, `ResultView`, `artifacts` 검증 4건 추가 (총 126건)

---

## 4. 인계 사항 및 후속 계획

- **Codex 인계**:
  - 원격 PC `192.168.45.225`에 실행 프로필(`execution profile`) 설치 완료 시 관측 전용 모드 해제 및 실제 7개 원격 시험(원격 실행·취소·복구·시간초과·영수증 대조 등) 수행 대기.
  - Frontend는 커널의 실제 `ResultView`와 7대 전제조건을 정본 그대로 렌더링할 준비를 100% 완료하였음.
- **Claude 인계**:
  - 운영 계정 로그인 및 Workspace 권한 프로비저닝 완료 상태 확인.
