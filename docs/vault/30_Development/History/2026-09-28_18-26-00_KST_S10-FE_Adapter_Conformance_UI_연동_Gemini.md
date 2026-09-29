---
doc_id: "HIST-GEMINI-S10-FE-CONFORMANCE-UI-001"
title: "S10-FE 어댑터 conformance 관측 화면 새 API(G-03 1단계) 연동 및 불변식 가드"
version: "1.0.0"
status: "active"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-28T18:26:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-FE", "G-03"]
tags: ["s10-fe", "g-03", "conformance", "adapter", "ui", "not-observed", "a11y", "rfc9457", "contracts-ts", "gemini"]
---

# S10-FE 어댑터 conformance 관측 화면 새 API(G-03 1단계) 연동 및 불변식 가드

## 1. 개요 및 배경

PR #200(Claude, G-03 1단계, Codex 승인)에서 컨트롤 플레인 `GET /v1/projects/{project_id}/adapters/conformance` 엔드포인트와 `contracts/conformance-status-response.schema.json` 계약이 신설되었다.
1단계 백엔드는 어댑터 conformance 실행 기록이 없는 베이스라인이므로 정직하게 `status: "NOT_OBSERVED"`, `recordedAt: null`, 그리고 `adapters.conformance.CHECKLIST` 단일 정본으로부터 파생된 15개 체크리스트 규격(`checks[]`)을 반환한다.

본 작업(카드 80)은 PR #146이 Frontend에서 "미측정"으로 정직화했던 화면(`apps/web/src/features/mlops/ModelLineageView.tsx`)을 이 실제 API에 온전히 연결하고, 가짜 수치/PASS를 전면 배제하며, 접근성 및 계약 무결성을 보장하도록 구현했다.

## 2. 주요 구현 내용

### 2.1 계약 타입 및 런타임 스키마 가드
- `apps/web/scripts/api-response-contracts.mjs`에 `conformance-status-response` 등록 및 `npm run contracts:generate` 실행.
- `apps/web/src/contracts/conformance-status-response.ts` 생성 및 `packages/contracts-ts/src/index.ts`, `apps/web/src/contracts/types.ts`에 `ConformanceCheckDescriptor`, `ConformanceStatusResponse` re-export.
- `apps/web/src/shared/api/adapterObservation.ts` 구현:
  - `isConformanceCheckDescriptor`: `name` 비어있지 않은 문자열, `capabilityGated` boolean, `additionalProperties: false` 검증.
  - `isConformanceStatusResponse`:
    - `contractVersion: "1.0.0"`
    - `scope: "control-plane-host"`
    - `status: "NOT_OBSERVED"` (1단계 단일 리터럴 불변식 강제, `PASS`/`RECORDED` 등 침투 원천 차단)
    - `recordedAt === null`
    - `checks`: 배열 및 각 요소 `isConformanceCheckDescriptor` 검증
    - `reason`: 비어있지 않은 문자열
    - `additionalProperties: false`: 7대 canonical key(`contractVersion`, `scope`, `status`, `recordedAt`, `adapters`, `checks`, `reason`) 외 임의 필드 유입 차단.
  - `fetchConformanceStatus(projectId, signal)`: `/v1/projects/${encodeURIComponent(projectId)}/adapters/conformance` 호출, RFC 9457 ProblemDetails 자동 처리 및 스키마 검증.

### 2.2 화면 연동 (`ModelLineageView.tsx`)
- **Zero-Synthesis 원칙 준수**:
  - `100% CONFORMING`, `0 / 15`, `PASS` 등 가짜 수치와 조기 합격 표기 일체 배제.
  - 서버 응답 `NOT_OBSERVED`를 정직하게 `미측정 (NOT_OBSERVED)`으로 표기.
  - 상단 지표 카드(`conformance-top-status`, `conformance-top-subtext`) 및 어댑터 패널에 실시간 반영.
- **동적 체크리스트 렌더링 (FE 하드코딩 금지)**:
  - 15개 체크 항목 이름과 게이트 여부(`capabilityGated`)를 서버 응답(`checks[]`)에서 직접 순회하여 렌더링.
  - 프런트엔드 소스에 15개 항목명을 하드코딩하지 않음.
- **WAI-ARIA 접근성 (PR #203 F1 교훈 계승)**:
  - `data-testid="conformance-live-status"` 컨테이너를 조건부 렌더가 아닌 마운트 시점부터 DOM에 상시 배치(`role="status" aria-live="polite"`).
  - 로딩(`조회 중...`), 완료(`관측 완료: NOT_OBSERVED`), 오류 상태를 스크린리더에 안정적으로 안내.
- **RFC 9457 ProblemDetails 표준 오류 처리**:
  - 401(인증 실패), 403(권한 거부), 404(엔드포인트 미배포 폴백) 등 오류 응답 시 `role="alert"` 에러 배너(`conformance-error-banner`)에 code, status, title, detail을 온전히 표출하고 상세 컨테이너는 격리(null).
- **다크 테마 WCAG AA 대비율 (>= 4.5:1)**:
  - `#161b22` 다크 배경 기준:
    - 주황 배지 텍스트 `#f0883e`: 대비율 6.83:1
    - 오류 텍스트 `#ff7b72`: 대비율 6.86:1
    - 파랑 로딩/스코프 텍스트 `#58a6ff`: 대비율 6.85:1
    - 음영 보조 텍스트 `#8b949e`: 대비율 5.62:1
    - 반투명 배경(`rgba(240, 136, 62, 0.15)` 등) 합성 시에도 5.3:1 이상 유지.

### 2.3 백엔드 코드 수정 0
- 백엔드 소스코드 변경 0건. 백엔드 동작 및 API 정본 계약을 온전히 존중.

## 3. 검증 결과

| 검증 항목 | 실행 명령 | 결과 | 비고 |
|---|---|---|---|
| Contract Types Check | `npm run contracts:check` | **PASS** | 17 API response types match schemas |
| Frontend Unit Tests | `npm test` | **PASS (78 files, 704 passed)** | `model-lineage.test.ts` 20 passed |
| TypeScript Typecheck & Build | `npx tsc -b && npm run build` | **PASS** | TS 오류 0, 프로덕션 번들(806 kB) 생성 |
| Route Coverage & FE Invariants | `pytest tests/test_route_coverage.py` | **PASS (40 passed)** | 화면-백엔드 라우트 불변식 100% |
| Frontend Integrity Guard | `python tools/check_frontend_integrity.py` | **PASS** | 9개 무결성 규칙 위반 0건 |
| Contract Bindings Check | `python tools/check_contract_bindings.py` | **PASS** | 55 fixture, 20 bound types, 14 replay guards |
| Documentation Integrity | `python tools/check_docs.py` | **PASS** | 909 versioned docs, DAG 무결성 |
| Obsidian Sync Check | `python tools/sync_obsidian.py --check` | **PASS** | 0 conflicts |

## 4. 인계 및 다음 단계

- 본 브랜치(`agent/gemini/s10-fe-conformance-status`)를 origin에 푸시하고 PR 생성.
- Reviewer: Claude (UI 및 회귀 시험 축), Codex (API 계약 및 RFC 9457 스키마 축).
- Hosted CI 4종(Frontend Build, Documentation Build, Desktop HTTP Browser Acceptance, Backend Build) 통과 확인.
