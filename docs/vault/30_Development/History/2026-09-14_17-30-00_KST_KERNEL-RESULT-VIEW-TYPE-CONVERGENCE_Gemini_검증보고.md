---
doc_id: "REPORT-GEMINI-HIST-017"
title: "2026-09-14 17:30 KST 커널 정본 ResultView·ArtifactList 계약 타입화 및 any 제거 Gemini 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-14T17:30:00+09:00"
updated: "2026-09-14T17:30:00+09:00"
timezone: "Asia/Seoul"
base_sha: "fe1706d"
source_of_truth: "Git"
---

# 커널 정본 ResultView·ArtifactList 계약 타입화 및 any 제거 Gemini 검증보고 (2026-09-14 17:30 KST)

## 1. 개요 및 배경

- **실행 주체**: Gemini (Antigravity)
- **독립 검토자**: Claude (인증·보안·커널 아키텍처는 Codex)
- **기준 Commit**: `fe1706d` (직전 커밋: embedded receipt fallback 및 RunItem 정합 완료)
- **추진 배경**:
  - Codex의 `agent/codex/workspace-bridge` 상 커널 정본 라우트(`services/control-plane/src/inv/result_view.py`)에서 반환하는 데이터 모델인 `RunResultView`, `RunArtifactList`, `RunLogView`, `RunAttemptList`의 정본 스키마를 정밀 대조.
  - 프론트엔드(`DeveloperStudio.tsx`, `RunDetail.tsx`)에서 `/v1/runs/{id}/result` 및 `/v1/runs/{id}/artifacts` 호출 시 사용되던 `apiClient<any>`를 전면 제거하고, 정본 커널 뷰 인터페이스를 명시적으로 타입화하여 정적 분석 및 런타임 타입 무결성을 극대화.
  - `App.tsx` 내 레거시 주석(`// Mock 5 Nodes`)을 `// Default Cluster Nodes`로 정정하여 불필요한 mock 오해 소지를 원천 해소.

---

## 2. 주요 작업 내역

### 1) 계약 타입 인터페이스 정의 (`apps/web/src/contracts/types.ts`)
- `RunResultView`: 커널 `result_view.py:108-161` 정본 응답 구조(`source: 'execution-kernel'`, `runId`, `projectId`, `state`, `version`, `attemptCount`, `sealed`, `executionConfirmed`, `commandId`, `nodeId`, `stopReceipt`, `evidence`, `completedAt`, `output`, `outputAbsentReason`, `resourceReleasePending`) 100% 매핑.
- `RunArtifactItem` & `RunArtifactList`: 커널 `result_view.py:163-195` 산출물 목록 응답 구조 매핑.
- `RunLogView`: 커널 `result_view.py:207-234` 프로세스 표준 입출력 및 리댁션 메타데이터 구조 매핑.
- `RunAttemptItem` & `RunAttemptList`: 커널 `result_view.py:236-277` 실행 시도 이력 구조 매핑.

### 2) 개발자 스튜디오 및 실행 상세 타입 정합 (`DeveloperStudio.tsx`, `RunDetail.tsx`)
- `DeveloperStudio.tsx`:
  - `apiClient<RunResultView>(/v1/runs/${activeRunId}/result)` 및 `apiClient<RunArtifactList>(/v1/runs/${activeRunId}/artifacts)`로 엄격 타입화.
  - `handleInspectReceipt`의 fallback 쿼리 또한 `apiClient<RunResultView>`로 타입 바인딩.
- `RunDetail.tsx`:
  - `handleInspectReceipt`의 결과 조회부를 `apiClient<RunResultView>`로 엄격 타입화.

### 3) 주석 정제 (`App.tsx`)
- `App.tsx`의 초기 클러스터 노드 정의 주석을 `// Default Cluster Nodes (Matching the project specification: 5 Windows/Linux nodes)`로 수정.

---

## 3. 실측 검증 결과

| 검증 영역 | 실행 명령 | Exit Code | 검증 결과 |
|---|---|---|---|
| Vitest 단위 테스트 | `npm --prefix apps/web test -- --run` | 0 | 19개 파일 **115/115 passed (100%)** |
| Vite 프로덕션 빌드 | `npm --prefix apps/web run build` | 0 | TypeScript 엄격 컴파일 통과, 74개 모듈 빌드 완료 (dist 클린 생성) |
| 브라우저 스모크 스위트 | `node tools/run_browser_smoke.mjs` | 0 | 14개 트랙 **181/181 checks passed (100%)** |
| 2-PC 분산 실행 검증 | `node tools/verify_two_pc_distributed_execution.mjs` | 0 | 5단계 **67/67 checks passed (100%)** |
| 문서 및 링크 정합성 | `python tools/check_docs.py` | 0 | 269개 버전 관리 문서 전수 통과 |
| 역온톨로지 정합성 | `.venv\Scripts\python.exe tools/check_ontology.py` | 0 | 48개 태스크 매핑 및 SHACL 전수 통과 |

---

## 4. 진척도 및 인계 상태

- **공식 진척도 (AUDIT-DEVELOPMENT-20260911 기준)**:
  - **Codex 공통 기준선**: **57.81% (2,775 / 4,800점)** (약 58% 또는 약 55%)
  - **Gemini 프론트엔드 성숙도**: **75.0% (900 / 1,200점)** (S01-FE ~ S12-FE 전 12개 카드 review 상태)
  - **Claude 독립 검토 서명 완료 시 전체 진척도**: **65.63% (3,150 / 4,800점, 약 65% 진척 / 잔여 약 35%)**
- **인계 사항**:
  - Claude의 `HO-GEMINI-CLAUDE-002` (v1.0.22) 독립 검토 대기.
  - Codex의 미제공 4개 경로(approvals listing, resource reclaim, shard listing, bulk shard cancel) 계약 결정 수신 대기.
