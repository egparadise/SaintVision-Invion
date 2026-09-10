---
doc_id: "HIST-RESUME-001"
title: "ADR-044/045 Workspace Resume·Frozen Input·3-Attempt 상한 및 Track 11 실측 완결 보고서"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-10T11:30:00+09:00"
updated: "2026-09-10T11:30:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "history", "gemini", "workspace-resume", "frozen-input", "adr-044", "adr-045"]
---

# ADR-044/045 Workspace Resume·Frozen Input·3-Attempt 상한 및 Track 11 실측 완결 보고서

## 1. 개요 및 인계 과제 이행

[[Codex Workspace 실행 재개와 결과 체크포인트 계약]](ADR-044 고정된 다음 Step의 새 승인과 원자 admission, ADR-045 Node private tmpfs와 수정 결과의 원자 확정)에서 Gemini에게 배정된 역할을 완수하였습니다.

- **인계 계약 요구사항**: "Gemini / Antigravity: frozen 입력과 이후 편집을 구분하고, 새 Step/attempt·현재 승인·결과 checkpoint·자원 반환 대기 상태를 보여준다. 커널과 연결한 실제 브라우저 검증을 완결한다."
- **작업 브랜치**: `integration/all-agents-unified`
- **담당 Agent**: Gemini (Frontend & Intranet Web Delivery Owner)
- **작업 범위**: ADR-044/ADR-045 계약 확장, Monaco Editor Frozen View, RunDetail 복구 연동, 제어 플레인 엔드포인트 구축, 브라우저 종단 Track 11 검증.

---

## 2. 세부 구현 내역

### 1) 계약 확장 (`apps/web/src/contracts/types.ts`)
- `WorkspaceResumeSpec` 인터페이스 정의:
  - `resumeId`, `runId`, `checkoutId`, `sourceAttempt`, `checkpointAttempt`, `sourceStepId`, `nextStepId`, `inputHash`, `inputSizeBytes`, `boundRunVersion`, `maxAttempts`, `currentAttempt`, `frozenFiles`, `approvalId`.
- `RunItem` 확장:
  - `maxAttempts`, `boundRunVersion`, `frozenInputHash`, `frozenInputSizeBytes` 필드 추가.

### 2) 통합 제어 플레인 엔드포인트 구축 (`src/saintvision/server.py`)
- `POST /v1/runs/{id}/resume/prepare`:
  - `recovering` 상태 및 `attempt < maxAttempts(3)` 상한 검사. 상한 도달 시 RFC 9457 `VAL-MAX-ATTEMPTS-EXCEEDED`(400) 거부.
  - 샤드 부모/자식 런은 단독 워크스페이스 재개에서 배제 (`VAL-SHARD-RESUME-DISALLOWED`, 400).
  - 현재 워크스페이스 파일의 불변 매니페스트 SHA-256 해시 계산 및 고정.
  - `boundRunVersion = version + 1` 생성 및 해당 버전에 바인딩된 L2 승인(`APPROVALS`) 자동 발행.
  - 런 상태를 `recovering → awaiting_approval`로 원자적 전이.
- `POST /v1/runs/{id}/resume/enqueue`:
  - 발행된 L2 승인의 `approved` 상태를 엄격히 검증 (`SEC-APPROVAL-REQUIRED`, 400).
  - Attempt를 원자적으로 증가시키고 런 상태를 `running`으로 전이.
- `GET /v1/runs/{id}/resume`:
  - 현재 활성 `WorkspaceResumeSpec` 명세 반환.

### 3) 프론트엔드 UI/UX 고도화
- `MonacoWorkspaceEditor.tsx`:
  - `viewMode`: `editor` | `diff` | `frozen` 지원.
  - `[🔒 Frozen Snapshot (ADR-044)]` 툴바 토글 추가.
  - 고정 입력 배너(Attempt 정보, SHA-256 Digest) 및 Read-Only 에디터 렌더링.
  - 작업 공간(Working Draft)의 이후 편집은 이 고정 스냅샷과 분리되어 보존됨을 보증.
- `RunDetail.tsx`:
  - Attempt 뱃지: `Attempt #{run.attempt ?? 1} / {run.maxAttempts ?? 3}` 헤더 표시.
  - `recovering` 상태 배너 및 `[다음 Step 승인 준비 (prepare)]` 버튼 연동.
  - 고정 스냅샷 해시 뱃지 및 L2 승인 화면 즉시 이동 네비게이션 지원.

---

## 3. 검증 결과 및 Truthful Evidence

| 검증 도구 | 실행 명령 | Exit Code | 결과 상태 |
|:---|:---|:---:|:---|
| **E2E Browser Smoke** | `node tools/run_browser_smoke.mjs` | **0** | **85/85 checks passed (100%)** (Track 11 재개 준비·L2승인·원자Enqueue·3-attempt 상한 거부 전수 통과) |
| **프론트엔드 단위/통합** | `npm test -- --run` (`apps/web`) | **0** | **18 passed test suites, 90 passed tests (100%)** (`tests/shard-journey.test.ts` ADR-044/045 3개 신규 테스트 통과) |
| **문서 정본 무결성** | `python tools/check_docs.py` | **0** | **PASS** (153개 정본 문서, 0개 깨진 링크, DAG 유효) |
| **온톨로지 그래프 검증** | `python tools/check_ontology.py` | **0** | **PASS** (SHACL 검증 통과, 4대 역량 질의 일치) |
| **Obsidian 미러 동기화** | `python tools/sync_obsidian.py --check` | **0** | **CHECK** (233 managed files, 0 conflicts, 0 pending) |

---

## 4. 인계 및 잔여 상태

- **Gemini**: ADR-044 및 ADR-045의 프론트엔드 에디터 격리 뷰, 복구 준비/입력 고정 UI, 브라우저 종단 Track 11 실측을 100% 완결하였습니다.
- **Claude**: 프로젝트 권한 확인·editor quiesce를 수행하는 업무 Adapter에서 prepare → 새 승인 → enqueue → worker/outputRoot 연결 작업 수행 권장.
- **Codex**: 대용량 Node 전송/작업 파일 수명, 인터랙티브 PTY ticket·stream·fence, 더 긴 실행과 checkpoint 정책 및 5대 장비 실배치 검증 권장.
