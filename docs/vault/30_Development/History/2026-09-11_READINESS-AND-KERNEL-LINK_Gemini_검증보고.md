---
doc_id: "HIST-READINESS-KERNEL-LINK-20260911"
title: "READINESS-AND-KERNEL-LINK Gemini 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
updated: "2026-09-11T15:42:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["development", "studio", "readiness", "governance", "evidence", "gemini"]
---

# Developer Studio kernelLinked=false 설명 상태 처리 및 Execution Readiness 6대 전제조건 검증보고

- **작업 소유자**: Gemini (Antigravity)
- **검토 대기**: Codex / Claude
- **소유 영역**: Frontend, Developer Studio UX, Execution Readiness 6대 점검 연동, kernelLinked 보안 분리 설명 처리, Zero-Mock 계약, E2E 검증
- **기준 규칙**: `AGENTS.md`, `GEMINI.md`, `skills/frontend-delivery/SKILL.md`

---

## 1. 구현 개요 및 주요 성과

Codex 및 Claude와의 협력 계약에 따라 다음 3대 핵심 요구사항을 화면과 백엔드에 충실히 반영하였다:

### A. `kernelLinked=false` 정상 분리 상태 설명 처리 (`DeveloperStudio.tsx`, `server.py`)
- **보안 설계 원칙**: 프로젝트 생성은 사업체 네임스페이스와 예산을 정의하는 과정이며, 물리 노드에서 실제 코드를 실행할 권한(Kernel Execution Grant)과는 의도적으로 분리되어 있다.
- **화면 설명 처리**:
  - `kernelLinked=false`를 오류(Error)로 취급하여 붉은색 경고나 크래시로 처리하지 않고, 사용자에게 의도된 안전 분리 상태임을 문장으로 명확히 설명하는 전용 배너 도입.
  - "새로 만든 프로젝트는 실행 커널(`inv.business_projects`)에 링크되기 전까지 원격 작업 실행이 보류됩니다. 운영자(Operator)의 승인 및 커널 링크 완료 전까지 실행 제출이 안전하게 보류됩니다." 고지.
  - 프로젝트 카드에 `ℹ️ 커널 미연결 (설명 상태)` 뱃지 표시.
- **백엔드 계약**: `create_project_run`에서 미연결 프로젝트 실행 요청 시 RFC 9457 `400 VAL-PROJECT-KERNEL-UNLINKED` 반환.

### B. Execution Readiness 6대 전제조건 검증 매트릭스 구현 (`DeveloperStudio.tsx`, `types.ts`, `server.py`)
- `GET /v1/workspaces/{workspace_id}/execution-readiness` 엔드포인트 구현 및 연동 (ADR-063 및 `execution_readiness.py` 준수).
- 6대 전제조건을 한 화면에서 종합 평가하여 시각화:
  1. `project_linked_to_kernel`: 프로젝트 커널 연동 여부 (해결 담당: `operator`)
  2. `requester_registered_with_kernel`: 실행 요청자 승인 주체 등록 여부 (해결 담당: `operator`)
  3. `role_permits_requesting`: 프로젝트 역할 요청 권한 여부 (해결 담당: `project owner`)
  4. `workspace_ready`: 워크스페이스 스토리지 프로비저닝 완료 여부 (해결 담당: `project owner`)
  5. `kernel_request_permission`: 계정·프로젝트 실행 허가(Execution Grant) 여부 (해결 담당: `operator`)
  6. `tool_chosen_and_usable`: 개발 도구 선택 및 타겟 노드 검증 여부 (해결 담당: `node owner`)
- **해결 권한자 및 조치 안내 반환**: 각 미충족 항목에 대해 `resolvedBy`(해결 담당자) 및 구체적인 `remedy`(조치 방안)를 명시하여 사용자가 누구에게 요청해야 하는지 즉시 인지하도록 지원.

### C. 실행 제출 차단 및 가이드 (`DeveloperStudio.tsx`)
- `kernelLinked === false`이거나 `readiness.executable === false`인 경우 Step 3의 "⚡ 작업 실행 (Dispatch Run)" 버튼을 사전에 비활성화(`disabled`).
- 버튼 라벨을 `🔒 실행 보류 (커널 미연결)` 또는 `🔒 실행 보류 (전제조건 미충족)`으로 동적 변경하여 불필요한 네트워크 실패를 방지하고 이유를 즉시 파악할 수 있도록 구현.

---

## 2. 검증 결과 및 합격 증거

모든 단위·통합·E2E 브라우저·2-PC 분산 실행·문서 및 온톨로지 검증을 100% 통과하였다 (Exit Code 0).

### A. 단위 및 통합 테스트 (Vitest)
- 명령: `npm --prefix apps/web test -- --run`
- 결과: **19개 테스트 파일, 102개 테스트 전원 통과 (0 failures, 2.39s)**
  - `Step 1: handles kernelLinked=false as an explainable security state rather than an error` 신규 통과.
  - `Step 1 & 3: evaluates Execution Readiness 6 checks and identifies resolvedBy authority for each unmet item` 신규 통과.

### B. 프로덕션 빌드 (Vite + TypeScript)
- 명령: `npm --prefix apps/web run build`
- 결과: **Exit Code 0 (75 modules transformed, 2.49s, 타입 에러 0개)**

### C. E2E 브라우저 여정 및 프로토콜 스모크 (Track 1 ~ 13)
- 명령: `node tools/run_browser_smoke.mjs`
- 결과: **13대 트랙, 118개 검사 항목 100% 통과 (Exit Code 0)**

### D. 2-PC 분산 실행 및 GPU 스케일링 검증 (Step 1 ~ 5)
- 명령: `node tools/verify_two_pc_distributed_execution.mjs`
- 결과: **5대 단계, 63개 검사 항목 100% 통과 (Exit Code 0)**

### E. 문서 및 온톨로지 무결성
- `python tools/check_docs.py`: **PASS (24 original hashes, 223 versioned documents)**
- `.venv\Scripts\python.exe tools/check_ontology.py`: **PASS (RDF, SHACL, 48 task mappings, 4 competency queries)**

---

## 3. 인계 사항 및 협력 상태

- **Codex**: 원격 PC(`192.168.45.225`)에 배포된 `lan-workspace-v1` 설치 확인 후 실제 실행·취소·복구 7개 시험 완료 및 Node-04 스케줄링 활성화(`schedulable: true`) 대기.
- **Claude**: 최신 커널(0031 / PR #22) 독립 검토, `result_view.py` 정본 일원화 및 운영 계정 프로비저닝 대기.
- **Gemini**: 원격 PC 설치 및 Claude 운영 계정 프로비저닝 완료 후, 브라우저에서 최종 2-PC 원격 디스패치 및 결과 다운로드 인수 시험 대기.
