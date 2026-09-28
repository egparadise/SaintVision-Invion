---
doc_id: "HIST-GEMINI-G05-W3-W5-REVIEW-ACTION-001"
title: "G-05 W3 Verify 및 W5 Eval Run Codex/Claude 1차·2차·3차 리뷰 조치 (H1·H2·H3·M1~M5·L1~L5·N1·N2 전수 반영)"
version: "1.2.0"
status: "active"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-29T02:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-FE", "G-05", "CARD-101"]
tags: ["s10-fe", "g-05", "card-101", "review-action", "model-verify", "eval-runs", "idempotency", "zero-fake-verification", "gemini"]
---

# G-05 W3 Verify 및 W5 Eval Run Codex/Claude 1차·2차·3차 리뷰 조치 (PR #228)

## 1. 개요

- **대상 PR**: #228 (`agent/gemini/g05-fe-verify-eval`, base: `agent/gemini/g05-fe-model-registry` `f23c0423`)
- **검토 의견 요약**:
  - 1차 리뷰:
    - Codex 계약 축: High 2건, Medium 1건 (componentVersions 상한 불일치, W3/W5 성공 후 멱등키 미회전, W5 멱등성 시험 보강)
    - Claude UI·시험 축: High 3건 (H1~H3), Medium 5건 (M1~M5), Low 5건 (L1~L5)
  - 2차 리뷰 (head `f0c78462`):
    - H3, H1, M1, M2, M5, L1~L4 닫힘 확인, hosted CI 3.12/3.14/desktop/docs/frontend 전수 green 확인.
    - 새 발견 사항: N1 (High/회귀: 입력 변경 핸들러가 in-flight abort 및 로딩 해제를 생략하여 버튼 잠김), N2 (Medium: 늦은 응답 fixture의 Crockford ULID 자릿수/문자 결함 및 W5 폐기 시험 추가 필요), H2 보강(prop 동기화 effect에 결과 초기화 및 결속), M3/M4 보강.
  - 3차 리뷰 (head `fe47aacf`):
    - 조건부 승인 (N1, N2, H2, L3 닫힘; Codex 계약 승인 유지).
    - 남은 조건:
      1) M3 시험: `:466 category: 'SYS'` (정본 SYS-0001), `:565 category: 'GRAPH'` (정본 GRAPH-0002, traceId/causeRef/evidenceId 포함). W5 503 픽스처는 eval run 라우트에 503 경로가 없으므로(`eval_runs.py:100-104`), 서버가 실제 내는 미매핑 내부 장애 응답인 `500 SYS-0002` (`detail: 'The service raised an error this route cannot represent.'`, `retryable: false`, RFC 9457 메타데이터) 픽스처로 전면 교체.
      2) M4 W3 `canApprove === undefined` 시험: 독립된 테스트 블록(새 root/container)에서 렌더링, 프로그래밍 방식 폼 서밋(`dispatchEvent('submit')`)을 통한 핸들러 수준 단언, `/verify` 네트워크 호출 0건 실측 단언(`verifyCalls.length === 0`), alert 표출 검증.
      3) History 문서 정정: M3/M4 설명의 사실 부합화(W5 503 과장 주장 제거, W3 canApprove undefined 핸들러 단언 사실화), 낡은 줄 번호 정합화.
      4) backend CI 실측.
- **조치 원칙**:
  - H3 병합 게이트 선행 해소: base `f23c0423` 머지 및 순수 충돌 해소.
  - 1차·2차·3차 리뷰 전 항목(H1~H3, M1~M5, L1~L5, N1~N2) 1:1 완결 및 되돌리면 실패하는 엄격한 단위/통합 시험 완비 (총 22개 시험).

## 2. 조치 내역 상세

| 항목 | 구분 | 조치 내용 | 반영 위치 및 검증 |
|---|---|---|---|
| **H3** | High (병합 게이트) | base `f23c0423` 머지 후 `ModelLineageView.tsx`와 `Gemini 작업 현황.md` 순수 충돌 해소, push (`21607a24`)하여 hosted CI 트리거. | `MERGEABLE` 전환, hosted CI backend 3.12/3.14, desktop-browser, docs, frontend 모두 green 실측. |
| **H1** | High (어댑터 이름 정합) | 백엔드 `adapters/agents.py:48-80` 정본 어댑터 어휘(`codex-cli`, `claude-code`, `gemini-cli`, `antigravity`)를 선택형(`<select>`)으로 제공, 기본값 `codex-cli` 설정. 픽스처 및 테스트도 실제 어댑터 이름으로 전면 동기화. | `ModelLineageView.tsx:241, 1295-1317`, `tests/model-verify-eval-routes.test.tsx`. |
| **H2** | High (#209 무결성) | 1) `verifyResult` 및 `evalResult`를 현재 모델/버전/스위트 입력에 결속: 입력 변경 시 및 새 제출 실패 시 결과를 즉시 비움.<br>2) `useEffect([effectiveProjectId])` prop 동기화 시에도 결과/타깃 초기화, in-flight abort, 세대 증가, 멱등키 회전 수행.<br>3) 헤더 배지 및 성공 카드를 발행 시점의 `(projectId, modelId, version)` 및 `(projectId, suiteId)`와 일치할 때만 렌더링. | `ModelLineageView.tsx:294-318, 334-450, 770-820, 1440-1550`, prop 변경 및 모델 불일치 상태 초기화 시험 2건 추가. |
| **N1** | High (회귀 조치) | 입력 변경 핸들러(프로젝트/모델/버전/측정ID/스위트/adapter/prompt/ctx/pinning)에서 진행 중인 in-flight AbortController를 즉시 abort하고 로딩 상태(`setVerifyLoading(false)`, `setEvalLoading(false)`)를 즉각 해제하여 입력 변경 시 버튼 영구 잠금 원천 차단. `finally` 블록에서도 현재 generation이거나 본인 controller일 때 안전하게 로딩 해제. | `ModelLineageView.tsx:335-460, 680-750`, W3/W5 각각 요청 중 입력 변경 시 로딩 즉시 해제 및 늦은 응답 무시 시험 2건 추가. |
| **N2** | Medium (시험 보강) | 1) 늦은 응답 fixture의 Crockford ULID를 규격(26자리, L/O 제외)에 맞는 `mvm_01JABCDEF01234567890123451`로 수정하고 `expect(resolveFirst).not.toBeNull()` 단언 추가.<br>2) W5 평가 실행에 대해서도 느린 첫 요청 응답이 빠른 두 번째 요청 응답을 덮어쓰지 않는 세대 가드 시험 추가. | `tests/model-verify-eval-routes.test.tsx`, W3/W5 늦은 응답 폐기 실측 시험 2건 완비. |
| **M1** | Medium (응답 가드 정합) | `isEvalRunResponse()`에서 정본 스키마(`contracts/eval-run-response.schema.json`)에 없는 `componentVersions` 32개 상한 제한 제거. 서버 추가분(`adapter`, `contractVersion`, `modelPinned`)이 포함된 34~35개 키 응답을 합법적으로 수용. | `apps/web/src/shared/api/modelRegistryObservation.ts:596-603`, 35키 수용 시험 추가. |
| **M2** | Medium (멱등키 수명주기) | W3(`handleVerifyVersion`) 및 W5(`handleStartEvalRun`) 성공 수신 시 새 `Idempotency-Key`로 회전. 실패 시 재시도는 동일 키를 보존하고 입력 변경 시 회전하는 3단 수명주기 완결. | `ModelLineageView.tsx:645, 715`, W3/W5 각각 회전·보존 시험으로 고정. |
| **M3** | Medium (서버 오류 일치) | 1) 409 detail을 서버 정본 `SNAPSHOT_DETAIL`로, 503 detail을 `OBSERVATION_DETAIL`로 수정.<br>2) 시험 픽스처 카테고리 정합화: SYS-0001은 `category: 'SYS'`로, GRAPH-0002는 `category: 'GRAPH'`로 수정하고 RFC 9457 메타데이터(`traceId`, `causeRef: null`, `evidenceId: null`) 완비.<br>3) W5 eval run route는 서버 계약(`eval_runs.py:100-104`)에 503 매핑이 존재하지 않으므로, 서버가 실제 반환하는 미매핑 내부 장애 정본인 `500 SYS-0002` (`detail: 'The service raised an error this route cannot represent.'`, `retryable: false`, RFC 9457 메타데이터) 픽스처로 전면 교체하여 멱등키 보존 검증. | `tests/model-verify-eval-routes.test.tsx:466, 565, 1282-1290`. |
| **M4** | Medium (되돌리면 실패하는 시험) | 1) W3/W5 입력 변경 시 키 회전 시험<br>2) W5 실패 재시도 키 보존 및 성공 후 키 회전 시험 (서버 정본 `500 SYS-0002` 픽스처)<br>3) W3/W5 늦은 응답 폐기 실측 시험<br>4) N1 요청 중 입력 변경 시 로딩 해제 시험 (W3/W5)<br>5) `canApprove` false 및 undefined 각각 독립 root에서 버튼 disabled + 폼 서밋 핸들러 차단 + 네트워크 호출 0건 + alert 표출 실측 (W3/W5 전수)<br>6) W3/W5 응답 계약 불일치 alert 시험<br>7) `endedAt: null` NOT_OBSERVED 표출 시험<br>8) H2 prop 동기화 및 입력 변경 결과 초기화 시험 (총 22개 시험). | `tests/model-verify-eval-routes.test.tsx` 22 passed 전수 실측. |
| **M5** | Medium (결과 카드 충실도) | `status`에 따라 제목 동적 렌더링(`aborted` 시 중단, `running` 시 실행 중, `completed` 시 완료). `endedAt`이 null이면 생략하지 않고 `NOT_OBSERVED` 명시. `componentVersions` 정체성을 화면에 표시 (`data-testid="eval-component-versions"`). | `ModelLineageView.tsx:1655-1710`. |
| **L1** | Low (배지 문구 사실 정합) | 연결 완료된 상태에 맞춰 기본 배지 문구를 `W3 검증: 미검증 (커널 계측 검증 대기)`로 수정. | `ModelLineageView.tsx:784`. |
| **L2** | Low (플레이스홀더 정규식) | Crockford Base32 26자리 규격에 맞게 25자 플레이스홀더를 `mvm_01JABCDEF1234567890ABCDEFG` 및 `evs_01JABCDEF1234567890ABCDEFG`로 수정. | `ModelLineageView.tsx:1235, 1281`. |
| **L3** | Low (WCAG AA 대비) | `GATE PASS` 배경색 `#1a7f37` (대비 5.08:1), `GATE FAIL` 배경색 `#cf222e` (대비 5.36:1)로 흰색 텍스트 기준 WCAG AA 4.5:1 이상 실측 달성 (정확한 계산 수치로 문서 정정). | `ModelLineageView.tsx:1671`. |
| **L4** | Low (클라이언트 권한 문구) | W5 권한 부족 에러 문구를 서버 detail 직복사 대신 클라이언트 전용 문구(`승인 권한(canApprove)이 없는 계정은 평가 스위트를 실행할 수 없습니다.`)로 정비. | `ModelLineageView.tsx:667`. |
| **L5** | Low (로딩 상태 가드) | 요청 중단/대체 시 `finally` 블록에서 안전하게 로딩 해제 (N1과 통합 개선). | `ModelLineageView.tsx:655, 725`. |

## 3. 실측 검증 증거

- **단위/통합 테스트 (Vitest)**:
  - `tests/model-verify-eval-routes.test.tsx`: 22 passed (894ms)
  - `tests/model-registry-business-routes.test.tsx`: 20 passed (923ms)
  - 웹 전체: 81 test files / 773 tests passed (26.31s, 0 failures)
- **TypeScript 컴파일 & 빌드**:
  - `cd apps/web && npx tsc -b`: 0 errors (exit 0)
  - `npm run build`: dist/ 번들 생성 성공 (`dist/assets/index-B-CJTiXt.js` 892.68 kB, exit 0)
- **파이썬 라우트 게이트**:
  - `pytest tests/test_route_coverage.py`: 40 passed (3.02s, exit 0)
- **무결성 및 정합성 검사**:
  - `python tools/check_frontend_integrity.py`: 88 files 0 violations (exit 0)
  - `python tools/check_contract_bindings.py`: 55 fixtures / 20 bound kernel types PASS (exit 0)
  - `python tools/check_docs.py`: 24 hashes, 932 docs PASS (exit 0)
  - `python tools/sync_obsidian.py --check`: 1780 files, 0 conflicts PASS (exit 0)
- **Hosted CI 실측 (Commit f0c78462)**:
  - `backend (3.12)`: SUCCESS
  - `backend (3.14)`: SUCCESS (commit `fe47aacf`는 `test_run_seal_real_pg.py`의 PG 반환 순서 flaky 확인, 신규 커밋 재검증 예정)
  - `desktop-browser`: SUCCESS
  - `docs`: SUCCESS
  - `frontend`: SUCCESS
