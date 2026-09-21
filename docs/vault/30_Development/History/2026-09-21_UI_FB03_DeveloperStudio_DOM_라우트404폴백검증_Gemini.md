---
doc_id: "UI-FB03-DOM-VERIFICATION-GEMINI-001"
title: "UI-FB-03 DeveloperStudio 라우트 404 폴백 DOM 하네스 및 양방향 돌연변이 실증 완결 보고"
version: "1.0.0"
status: "verified"
author: "Gemini"
reviewer: "Codex"
updated: "2026-09-21T16:35:00+09:00"
code_ref_tip: "b401fc6"
source_of_truth: "Git"
tags: ["ui-fb-03", "developer-studio", "route-404-fallback", "dom-harness", "mutation-testing", "happy-dom"]
---

# UI-FB-03 DeveloperStudio 라우트 404 폴백 DOM 하네스 및 양방향 돌연변이 실증 완결 보고

## 1. 개요 및 목적

Claude의 핸드오프 시험 스펙([[2026-09-21_FB-03_핸드오프_시험스펙_Claude]])에 명시된 통과 기준과 양방향 돌연변이 검증 기준을 100% 충족하는 `DeveloperStudio` DOM 하네스 통합 시험(`apps/web/tests/developer-studio-dom.test.tsx`)을 작성하고, `DeveloperStudio.tsx`의 잔여 결함(아티팩트 다운로드 시 `/artifacts` 직접 호출 잔여, 초기 마운트 시 불필요한 2회 호출 유발)을 완벽하게 교정하였다.

## 2. 작업 내역 및 설계 결정

### 2.1 DeveloperStudio 잔여 결함 교정 (`apps/web/src/features/studio/DeveloperStudio.tsx`)
1. **아티팩트 다운로드 핸들러 정합 (`handleDownloadArtifact`)**:
   - 기존: `/v1/projects/${prjId}/runs/${activeRunId}/artifacts`를 가드 없이 직접 호출하던 잔여 존재.
   - 수정: 컴포넌트 내 이미 로드된 정규 `artifactData`를 최우선 재사용하고, 없을 경우 canonical `/result`를 우선 시도한 후 `isRouteNotFoundError(err)`에 부합할 때만 `/artifacts`로 안전하게 폴백하도록 정합.
2. **초기 마운트 시 아티팩트 중복 호출 버그 수정**:
   - 기존: `const [liveRun, setLiveRun] = useState<RunItem | null>(null);`로 인해 초기 마운트 시 `liveRun?.state`가 `undefined`였다가 직후 `poll()`이 끝나면서 `succeeded`로 바뀌어 `useEffect(..., [activeRunId, liveRun?.state])`가 2회 연속 발화되는 버그가 존재함.
   - 수정: `useState` 초기화 시 `runs` 목록에서 `initialRunId`에 매칭되는 실행 항목을 즉시 찾아 초기화함으로써 불필요한 재발화를 차단하고, `/artifacts` 폴백이 정확히 1회만 호출되도록 안정화.

### 2.2 happy-dom 기반 DOM 통합 시험 스위트 신설 (`apps/web/tests/developer-studio-dom.test.tsx`)
- **실물 `isRouteNotFoundError` 판별 유지**: `vi.spyOn(client, 'apiClient')`만 모의하고 판별 함수 `isRouteNotFoundError`는 실물 그대로 실행시켜 소스 코드의 분기 변형이 시험 결과에 직접 투영되도록 보장.
- **Claude 스펙 7개 시나리오 + 1개 정규 경로 전수 검증 (총 8개 테스트)**:
  1. **시나리오 1 (401 Unauthorized)**: `/artifacts` 호출 0회, 에러 배너(`role="alert"`) 노출, 폴백 뱃지 및 검증 배너 부재.
  2. **시나리오 2 (403 Forbidden)**: `/artifacts` 호출 0회, 에러 배너 노출, 폴백 뱃지 및 검증 배너 부재.
  3. **시나리오 3 (500 Internal Server Error)**: `/artifacts` 호출 0회, 에러 배너 노출, 폴백 뱃지 및 검증 배너 부재.
  4. **시나리오 4 (Malformed JSON / NET-PARSE)**: `/artifacts` 호출 0회, 에러 배너 노출, 폴백 뱃지 및 검증 배너 부재.
  5. **시나리오 5 (Network Rejection / Error)**: `/artifacts` 호출 0회, 에러 배너 노출, 폴백 뱃지 및 검증 배너 부재.
  6. **시나리오 6 (App-level 404 / RES-RUN-404)**: 엔티티 부재 오류로 라우트 미매핑이 아니므로 폴백 엄격 차단(`/artifacts` 호출 0회), 에러 배너 노출, 폴백 뱃지 및 검증 배너 부재. **(핵심 경계 판별자)**
  7. **시나리오 7 (Route-only 404 / detail='Not Found', no code)**: `/artifacts` 호출 정확히 1회, 에러 배너 부재, 폴백 뱃지(`404 호환 폴백: /artifacts`) 표시, 상태 뱃지 `⚠️ 산출물 아티팩트 폴백 (Artifact Fallback / UNVERIFIED)` 표시, `✓ 산출물 검증 완료 (Output Verified)` 엄격 배제.
  8. **시나리오 8 (Canonical /result 200 OK 정규 경로)**: `/artifacts` 호출 0회, 에러 배너 및 폴백 뱃지 부재, `✓ 산출물 검증 완료 (Output Verified)` 정상 표시.

## 3. 양방향 돌연변이 검증 실증 (Mutation Testing Proof)

### 3.1 돌연변이 1: `if (true)` 주입 (항상 라우트 404로 간주하여 무조건 폴백)
- **주입 위치**: `DeveloperStudio.tsx` L294 (`if (isRouteNotFoundError(err))` -> `if (true)`)
- **검증 명령**: `npm --prefix apps/web test -- tests/developer-studio-dom.test.tsx --run`
- **결과**: **8개 중 6개 테스트 실패 (6 failed | 2 passed)** (exit 1)
- **상세 실패 내역**:
  - `Scenario 1 (401)`: FAIL (AssertionError: expected 1 to be +0)
  - `Scenario 2 (403)`: FAIL (AssertionError: expected 1 to be +0)
  - `Scenario 3 (500)`: FAIL (AssertionError: expected 1 to be +0)
  - `Scenario 4 (NET-PARSE)`: FAIL (AssertionError: expected 1 to be +0)
  - `Scenario 5 (Network)`: FAIL (AssertionError: expected 1 to be +0)
  - `Scenario 6 (App-level 404 RES-RUN-404)`: FAIL (AssertionError: expected 1 to be +0)
  - 통과: Scenario 7 (route-404), Scenario 8 (canonical /result 200)
- **판정**: 비-라우트 오류 및 애플리케이션 수준 404가 가짜 폴백으로 마스킹되는 회귀를 100% 감지하여 차단함을 완벽 실증.

### 3.2 돌연변이 2: `if (false)` 주입 (폴백 전면 비활성화)
- **주입 위치**: `DeveloperStudio.tsx` L294 (`if (isRouteNotFoundError(err))` -> `if (false)`)
- **검증 명령**: `npm --prefix apps/web test -- tests/developer-studio-dom.test.tsx --run`
- **결과**: **8개 중 1개 테스트 실패 (1 failed | 7 passed)** (exit 1)
- **상세 실패 내역**:
  - `Scenario 7 (Route-only 404)`: FAIL (AssertionError: expected +0 to be 1)
  - 통과: Scenario 1~6 및 Scenario 8
- **판정**: 라우트 미매핑 환경에서 필요한 404 레거시 호환 폴백 누락을 100% 감지함을 완벽 실증.

### 3.3 복구 후 정상 상태
- 정규 코드 `if (isRouteNotFoundError(err))` 복원 후: **8 passed (8/8, 100%)** (exit 0).

## 4. 전체 검증 실적

1. **Vitest 전체 스위트**:
   - `npm --prefix apps/web test -- --run`
   - **36개 테스트 파일, 344개 테스트 전수 통과 (344/344 passed, 100%, 0 failed)**
2. **프로덕션 빌드**:
   - `npm --prefix apps/web run build` (`tsc -b && vite build`)
   - **Exit 0, 4.59초 클린 빌드 성공** (dist/index.html, dist/assets/index-MJEDkkbE.js 614.17 kB)
3. **문서 및 온톨로지 무결성**:
   - `python tools/check_docs.py` -> **PASS: 24 original hashes, 608 versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG.**
   - `.venv\Scripts\python.exe tools/check_ontology.py` -> **PASS: RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings, positive SHACL, 4 rejected invalid fixtures, 4 competency queries, Obsidian mirrors.**
4. **백엔드 라우트 계약 검사**:
   - `.venv\Scripts\pytest.exe tests/test_route_coverage.py` -> **30 passed in 1.47s (100%)**

## 5. 결론 및 인계

UI-FB-03(DeveloperStudio의 미매핑 라우트 404 폴백 및 비-404 정직한 오류 노출)의 DOM 마운트 효과 전이 검증과 양방향 돌연변이 실증이 완결되었다.
다음 담당(Codex)에게 경계 검토 및 전체 진행판 동기화를 인계한다.
