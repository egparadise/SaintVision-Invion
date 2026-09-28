---
doc_id: "HIST-GEMINI-G05-W3-W5-REVIEW-ACTION-001"
title: "G-05 W3 Verify 및 W5 Eval Run Codex/Claude 1차 리뷰 조치 (H1·H2·H3·M1~M5·L1~L5 전수 반영)"
version: "1.0.0"
status: "active"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-29T01:08:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-FE", "G-05", "CARD-101"]
tags: ["s10-fe", "g-05", "card-101", "review-action", "model-verify", "eval-runs", "idempotency", "zero-fake-verification", "gemini"]
---

# G-05 W3 Verify 및 W5 Eval Run Codex/Claude 1차 리뷰 조치 (PR #228)

## 1. 개요

- **대상 PR**: #228 (`agent/gemini/g05-fe-verify-eval`, base: `agent/gemini/g05-fe-model-registry` `f23c0423`)
- **검토 의견**:
  - Codex 계약 축: High 2건, Medium 1건 (componentVersions 상한 불일치, W3/W5 성공 후 멱등키 미회전, W5 멱등성 시험 보강)
  - Claude UI·시험 축: High 3건 (H1~H3), Medium 5건 (M1~M5), Low 5건 (L1~L5)
- **조치 원칙**:
  - H3 병합 게이트 선행 해소: base `f23c0423` 머지 및 순수 충돌 해소 후 즉시 push하여 hosted CI 트리거 (MERGEABLE 전환 및 hosted CI desktop-browser/docs/frontend SUCCESS 달성).
  - High/Medium/Low 전 항목 1:1 완결 및 되돌리면 실패하는 엄격한 단위/통합 시험 추가.

## 2. 조치 내역 상세

| 항목 | 구분 | 조치 내용 | 반영 위치 및 검증 |
|---|---|---|---|
| **H3** | High (병합 게이트) | base `f23c0423` 머지 후 `ModelLineageView.tsx`와 `Gemini 작업 현황.md` 순수 충돌 해소, 즉시 push (`21607a24`)하여 hosted CI 트리거. | `MERGEABLE` 전환, hosted CI desktop-browser, docs, frontend 모두 green 실측. |
| **H1** | High (어댑터 이름 정합) | 백엔드 `adapters/agents.py:48-80` 정본 어댑터 어휘(`codex-cli`, `claude-code`, `gemini-cli`, `antigravity`)를 선택형(`<select>`)으로 제공, 기본값 `codex-cli` 설정. 픽스처 및 테스트도 실제 어댑터 이름으로 전면 동기화. | `ModelLineageView.tsx:241, 1295-1317`, `tests/model-verify-eval-routes.test.tsx`. |
| **H2** | High (#209 무결성) | `verifyResult` 및 `evalResult`를 현재 모델/버전/스위트 입력에 결속: 프로젝트/모델/버전/스위트/어댑터/측정ID 입력 변경 시 즉시 결과 상태를 `null`로 초기화하고, 새 제출 시작 및 실패 시에도 초기화하여 서버가 검증하지 않은 버전 옆에 허위 "검증 완료"가 잔존하지 않도록 원천 차단. | `ModelLineageView.tsx:334-441, 600, 640, 650, 695`, 시험으로 상태 초기화 고정. |
| **M1** | Medium (응답 가드 정합) | `isEvalRunResponse()`에서 정본 스키마(`contracts/eval-run-response.schema.json`)에 없는 `componentVersions` 32개 상한 제한 제거. 서버 추가분(`adapter`, `contractVersion`, `modelPinned`)이 포함된 34~35개 키 응답을 합법적으로 수용. | `apps/web/src/shared/api/modelRegistryObservation.ts:596-603`, 35키 수용 시험 추가. |
| **M2** | Medium (멱등키 수명주기) | W3(`handleVerifyVersion`) 및 W5(`handleStartEvalRun`) 성공 수신 시 새 `Idempotency-Key`로 회전. 실패 시 재시도는 동일 키를 보존하고 입력 변경 시 회전하는 3단 수명주기 완결. | `ModelLineageView.tsx:635, 692`, W3/W5 각각 회전·보존 시험으로 고정. |
| **M3** | Medium (서버 오류 문자열 일치) | 409 detail을 서버 정본 `SNAPSHOT_DETAIL`("The measurement does not match the current storage snapshot of the model version.")로, 503 detail을 `OBSERVATION_DETAIL`("The model measurement observation could not be read.")로 수정하고 `componentVersions.contractVersion`을 픽스처에 포함. | `tests/model-verify-eval-routes.test.tsx`. |
| **M4** | Medium (되돌리면 실패하는 시험) | 1) W3/W5 입력 변경 시 키 회전 시험, 2) W5 실패 재시도 키 동일·성공 후 키 회전 시험, 3) W3/W5 generation/abort 늦은 응답 폐기 시험, 4) `canApprove` 누락/false fail-closed 버튼 및 폼 제출 핸들러 가드 시험, 5) 응답 계약 불일치 시 alert 시험, 6) `endedAt: null` NOT_OBSERVED 시험, 7) H2 결과 초기화 시험 추가 (총 15개 시험으로 확장). | `tests/model-verify-eval-routes.test.tsx` 15 passed 전수 실측. |
| **M5** | Medium (결과 카드 표출 충실도) | `status`에 따라 제목 동적 렌더링(`aborted` 시 중단, `running` 시 실행 중, `completed` 시 완료). `endedAt`이 null이면 생략하지 않고 `NOT_OBSERVED` 명시. `componentVersions` 정체성을 화면에 표시 (`data-testid="eval-component-versions"`). | `ModelLineageView.tsx:1509-1545`. |
| **L1** | Low (배지 문구 사실 정합) | 연결 완료된 상태에 맞춰 기본 배지 문구를 `W3 검증: 미검증 (커널 계측 검증 대기)`로 수정. | `ModelLineageView.tsx:774`. |
| **L2** | Low (플레이스홀더 정규식) | Crockford Base32 26자리 규격에 맞게 25자 플레이스홀더를 `mvm_01JABCDEF1234567890ABCDEFG` 및 `evs_01JABCDEF1234567890ABCDEFG`로 수정. | `ModelLineageView.tsx:1232, 1278`. |
| **L3** | Low (WCAG AA 대비) | `GATE PASS` 배경색을 `#1a7f37`(대비 5.02:1), `GATE FAIL` 배경색을 `#cf222e`(대비 5.15:1)로 조정하여 흰색 텍스트 기준 4.5:1 이상 실측 달성. | `ModelLineageView.tsx:1523`. |
| **L4** | Low (클라이언트 권한 문구) | W5 권한 부족 에러 문구를 서버 detail 직복사 대신 클라이언트 전용 문구(`승인 권한(canApprove)이 없는 계정은 평가 스위트를 실행할 수 없습니다.`)로 정비. | `ModelLineageView.tsx:649`. |
| **L5** | Low (로딩 상태 가드) | 요청 중단/대체 시 `finally` 블록에서 이전 요청이 로딩 상태를 오해제하지 않도록 `generation === currentGen && !ctrl.signal.aborted` 가드 적용. in-flight 중복 클릭 방지. | `ModelLineageView.tsx:641, 696`. |

## 3. 실측 검증 증거

- **단위/통합 테스트 (Vitest)**:
  - `tests/model-verify-eval-routes.test.tsx`: 15 passed (742ms)
  - `tests/model-registry-business-routes.test.tsx`: 20 passed (917ms)
  - 웹 전체: 81 test files / 766 tests passed (25.82s, 0 failures)
- **TypeScript 컴파일 & 빌드**:
  - `cd apps/web && npx tsc -b`: 0 errors (exit 0)
  - `npm run build`: dist/ 번들 생성 성공 (`dist/assets/index-DKd5natM.js` 890.55 kB, 9.22s, exit 0)
- **파이썬 라우트 게이트**:
  - `pytest tests/test_route_coverage.py`: 40 passed (3.13s, exit 0)
- **무결성 및 정합성 검사**:
  - `python tools/check_frontend_integrity.py`: 88 files 0 violations (exit 0)
  - `python tools/check_contract_bindings.py`: 55 fixtures / 20 bound kernel types PASS (exit 0)
  - `python tools/check_docs.py`: 24 hashes, 932 docs PASS (exit 0)
  - `python tools/sync_obsidian.py --check`: 1780 files, 0 conflicts PASS (exit 0)
