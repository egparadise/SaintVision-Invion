---
doc_id: "UI-FB-CONTRACT-REVIEW-20260921-CODEX"
title: "UI-FB 계약 구현 준비도 재검토"
version: "1.3.0"
status: "review"
author: "Codex"
reviewer: "Pending"
base_commit: "d0d1322"
updated: "2026-09-21T12:08:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["UI-FB", "contract", "frontend", "verification-boundary"]
---

# UI-FB 계약 구현 준비도 재검토

## 범위 / 역할

기존 계약 [[2026-09-19_UI_우선순위6_검증경계감사_Codex]]의 UI-FB-01/02/03만 다시 점검했다. Gemini가 화면 owner이며 Codex는 검증 경계 계약 reviewer다. 이번 작업은 문서 계약 보강뿐이고 화면 코드나 시험은 수정하지 않았다.

## 결론

기존 계약은 방향은 맞았으나 구현자가 일부 pass/fail을 추측해야 했으므로 아직 충분하지 않았다. 원 계약을 v1.1.0으로 확장했다. 공통 상태·오류 표시 규칙, 빈 성공 응답과 idle/pending 구분, 화면별 구체적인 실패 대조, 기본 후보 fallback 되돌림 대조, 정확한 ResultView route-404 의미, 그리고 Gemini 완료 뒤 Codex가 확인할 review checklist를 추가했다.

## 현재 소스 snapshot

`d0d1322`를 tracked base로 사용했다. 확인 당시 공유 working tree에는 아래 두 파일이 수정 상태였지만 아직 커밋 SHA가 없었다. 그 diff는 고정 구현이나 합격 증거로 보지 않았다.

- `apps/web/src/features/desktop/ResourceExplorer.tsx`
- `apps/web/tests/fabric-control-plane.test.tsx`

현재 스냅샷의 계약 불일치/미결 기준:

- ResourceExplorer의 discovery 기본 `idle` 상태가 렌더 조건상 success-empty처럼 나타날 수 있다. empty copy는 성공한 `{items: []}` 뒤에만 허용해야 한다.
- storage fetch catch가 `storageError`를 state에 넣지만 화면에 표시하는 사용처는 검색 결과 없었다. 빈 목록 문구와 실제 실패를 분리해야 한다.
- 새 ResourceExplorer 검사는 `renderToStaticMarkup` 사용이다. 이 방식은 `useEffect`를 실행하지 않으므로 실제 API async 상태 전이를 증명하지 않는다.
- PlacementSimulator의 pool/candidate 빈 안내도 `idle && length===0`을 성공 empty처럼 렌더하지 않아야 한다.
- DeveloperStudio의 `/result` catch-any artifacts fallback과 2xx envelope의 output 부재 fallback은 아직 broad fallback 구조다. 허용 fallback을 API client의 `isRouteNotFoundError`로 한정해야 한다.

이 관측은 당시 source/diff에서 읽은 것이며 runtime/browsing 증거가 아니다. 진행 중인 변경의 작성자를 git만으로 확정하지 않았다.

문서화 직전 working-tree 확인에서는 UI 관련 수정 파일이 세 컴포넌트와 테스트 파일들로 늘어 있었고, placement simulator 테스트 하나는 untracked 상태였다. 모두 고정 커밋이 아니므로 이 후기 diff는 구현 합격 여부를 평가하지 않았다. 전체 `git diff --check`는 `apps/web/tests/developer-studio.test.ts:448`의 EOF 빈 줄을 보고했지만, 이 진행 중 파일도 Codex가 수정하지 않았다.

## 계약을 구체화한 pass/fail 핵심

- 공통 원격 상태는 loading / success-empty / success-with-data / error다. idle이나 pending은 empty 성공이 아니다. 401/403/5xx, bad JSON/shape, network rejection은 오류다. 오류는 접근 가능한 alert로 나타나고 false-success나 server mutation을 만들지 않는다.
- UI-FB-01은 discovery, capacity, node detail뿐 아니라 audit에서 발견한 storage contributions/locations empty-on-error 경로도 포함한다. 정상 빈 API 결과와 실패 UI를 각각 실행하고, API pending 중 sentinel Node-06 후보와 운영 버튼이 나타나지 않음을 검사한다. 성공-empty 완료 뒤 sentinel 복원도 시험이 실패해야 한다.
- UI-FB-02의 pool/candidate/preview idle과 성공 empty를 구분한다. 로컬 설명은 항상 local-unverified로 표시하고 server admission/ready/shard 판정과 별도로 유지한다. backend failure는 alert이며 server shard/explanation success 상태가 없어야 한다.
- UI-FB-03은 `isRouteNotFoundError(err) === true`인 unmapped route 404에서만 artifacts fallback을 허용한다. business/resource 404, 401/403/5xx, network/parse error 및 2xx output 누락은 fallback 금지다. fallback은 artifact-only/unverified로 표시하고 canonical ResultView PASS로 집계하지 않는다.
- 기존 테스트 패키지에는 Testing Library 의존성이 확인되지 않았다. 그래서 계약은 특정 프레임워크를 강제하지 않되, effect 구동 DOM harness나 실제 컴포넌트와 연결된 상태전이 helper 중 하나로 async fetch→render 전이를 입증하도록 명시했다. SSR만으로 이를 대체하지 않는다.

세부 조건·예제 및 후속 fixed-SHA review checklist는 원 계약 v1.1.0의 `2026-09-21 계약 완결성 검토` 부록에 기록했다.

## 확인 범위 / 다음 행동

- 확인한 것: 원 계약 전체, 세 컴포넌트의 관련 fetch/state/render 경로, shared API client의 `ApiError`와 `isRouteNotFoundError`, 현재 `fabric-control-plane.test.tsx` test technique.
- 실행하지 않은 것: Vitest, browser, backend HTTP failure injection, implementation tests. 문서 보강 전에/후 화면 코드를 고치거나 staged하지 않았다.
- 다음: Gemini가 구현·관련 시험을 완료하고 fixed SHA를 제공한다. Codex는 UI-FB-01의 phantom-target mutation 불가, idle→success-empty/error 전이, UI-FB-02 local/server 구분, UI-FB-03 route-only 404 fallback 및 모든 음성 대조가 실제로 실패하는지 검토한다. 사용자에게 Gemini 수신·완료를 대신 주장하지 않는다.

## 문서 검증 기록

- KST 2026-09-21 10:41, `.venv\\Scripts\\python.exe tools/check_docs.py`: exit 0, 587 versioned documents 및 48 task 검사 통과.
- 같은 인터프리터로 `tools/check_ontology.py`: exit 0, RDF/SHACL/task mapping 검사 통과.
- Codex가 변경한 여섯 문서에 한정한 `git diff --check`: exit 0. 저장소 전체 점검은 `apps/web/tests/developer-studio.test.ts:448` EOF 공백으로 exit 1이었으나, 그 공유 진행 중 파일은 수정하지 않았다.
- `.venv\\Scripts\\python.exe tools/sync_obsidian.py --check`: exit 1, 675 unmanaged destination collisions(655 no-baseline, 12 destination-edited, 8 both-diverged), no writes. `--apply`는 실행하지 않았다.

## 고정 SHA 독립 경계 재검토 — `c6dc915`

Gemini 구현 commit을 확인해 이 SHA의 소스와 회귀 증거를 검토했다. **판정: 수정 방향은 맞지만 UI-FB-01/02/03 계약의 독립 검토는 아직 승인하지 않는다.** 아래는 구현 owner가 처리할 시험·상태 표시 잔여다. 화면 소유권은 Gemini에 유지한다.

### 확인된 구현 및 근거 강도

- 소스 확인: `ResourceExplorer`의 합성 `ann_node06_unverified` 후보가 초기값에서 제거됐고, 후보 fetch catch가 목록을 비우며 `error`로 바꾼다. 렌더도 `error`에서 후보 목록을 숨긴다. pool capacity/node detail/storage 오류 배너가 추가됐다.
- 소스 확인: `PlacementSimulator`는 로컬 평가를 `UNVERIFIED`로 표시하고 pools/candidates/preview 상태를 분리한다. preview catch는 shard와 server explanation을 비운다.
- 소스 확인: `DeveloperStudio`의 `/result` catch는 `isRouteNotFoundError(err)`일 때만 `/artifacts`를 요청하고, 다른 오류에서는 데이터를 비우고 오류를 기록한다.
- 실행 확인: `npm --prefix apps/web test -- --run` (KST 10:43:12, exit 0) → 32 files / 322 tests passed. `.venv\\Scripts\\python.exe -m pytest -q tests/test_route_coverage.py` (exit 0) → 28 passed.
- 이들은 현 시험 스위트가 통과한다는 증거이며 브라우저나 실제 backend 인수 증거가 아니다. 세 UI 시험 파일은 상태 props를 넣어 `renderToStaticMarkup`로 출력 문자열을 확인한다. `useEffect`/fetch→render 전이를 돌리지 않는다. DeveloperStudio 테스트는 현재 컴포넌트의 route fallback 분기가 아니라 `isRouteNotFoundError` helper 자체만 검사한다.

### 되돌림 대조

각 mutant를 일시 적용해 `apps/web`에서 `npm exec vitest run tests/fabric-control-plane.test.tsx`로 확인한 뒤 원복했고 작업 트리는 clean임을 확인했다.

- 유령 pending 후보를 초기값에 되살림: **1 test failed**. idle 렌더 시험이 승인 버튼 출현을 잡았다. 이 변형은 공허하지 않다.
- 후보 fetch catch의 `setCandidates([])` 제거: **26 passed**. 기존 시험은 성공 뒤 새로 고침 실패 시 과거 후보와 운영 버튼이 사라지는 것을 검사하지 못한다.
- 빈 API 응답에서 목록을 덮지 않도록 `items.length > 0` 조건 복원: **26 passed**. 시험이 실제 API 응답 전이를 실행하지 않아 원래 회귀를 놓친다.
- 오류 렌더 조건에서 `candidatesState !== 'error'` 제거: **26 passed**. 오류 시험의 초기 후보가 비어 있으므로 버튼 금지 단언이 데이터 공백에만 의존한다. error 상태인데 pending 후보가 남은 대조가 없다.

### Gemini 처리 필요 — 독립 검토 미승인 사유

1. **FB-01 실제 전이 회귀시험**: UI 시험이 요청 pending → 성공 `{items: []}` 및 401/403/5xx/깨진 JSON/network rejection → error 상태를 실제 컴포넌트 경로에서 실행해야 한다. 최소 추가 대조는 (a) pending 동안 후보/승인/거부 버튼 없음, (b) 정상 빈 응답 후 success-empty, (c) 기존 pending 후보를 가진 상태에서 재조회 실패 시 목록 clear/error/버튼 없음이다. 각 API 실패 분류와 재시도 호출도 단언한다. 현재 idle/success/error props를 직접 지정한 SSR 렌더로는 이를 대신할 수 없다.
2. **FB-01 버튼 가드 반증**: error 상태에 pending 후보 데이터를 넣고 운영 버튼이 없음을 검사한다. error guard를 제거한 mutant가 실패해야 한다. “목록이 비어서 버튼이 없다”만으로 상태에 따른 억제를 증명하지 않는다.
3. **FB-01 다른 데이터 영역**: storage와 pool-capacity/node-detail 오류 catch의 화면을 실제 오류 주입으로 검사한다. 특히 storage error가 빈 성공 문구가 아니며 읽기 오류로 보이는지 고정한다.
4. **FB-02 로컬/서버 분리**: 로컬 `PlacementExplainView`는 `최적 배치 노드 선정` 및 후보 점수/통과 표시를 계속 출력한다. 상단 UNVERIFIED 배지는 있지만 이 결과가 로컬 휴리스틱이며 서버 eligible/admission이 아님을 해당 결과와 함께 식별할 수 있는지 실행 시험이 없다. pool/preview 실패와 실제 서버 shard의 최신성도 각각 주입해 단언한다.
5. **FB-03 component 분기 및 정본 상태**: helper 테스트만으로 `/result` 실패 뒤 artifacts 호출 횟수·표시를 증명하지 못한다. 컴포넌트 시험에서 unmapped route 404는 fallback 1회, resource 404/401/403/5xx/parse/network 실패와 2xx output 누락은 fallback 0회 및 올바른 오류/미생성 상태를 단언한다. 소스의 카드 상태는 `currentRun.state === 'succeeded'`만으로 “산출물 검증 완료 (Output Verified)”를 표시한다. 이는 artifact/result 검증 상태와 분리되어 있지 않으므로 표시 계약을 수정하고, 실행 성공이나 artifacts fallback만으로 canonical output 검증 완료가 되지 않는 대조를 추가한다.
6. **오류 접근성/일관성**: 세 컴포넌트에서 조사한 오류 배너는 `role="alert"` 또는 `aria-live`를 갖지 않는다. pass/fail 계약의 접근 가능한 오류 알림 요건을 충족하도록 고치고, 다른 UI 문구를 동일하게 만들 필요는 없지만 loading/empty/error의 의미와 접근성은 일관되게 검사한다.

재검토 경계: vitest 및 Python 시험은 실행했으나 browser, live HTTP, backend 장애 주입, 실제 운영 화면은 실행하지 않았다. Gemini가 위 잔여를 fixed SHA로 반영한 뒤 Codex가 다시 검토한다. Gemini 실행 보고서의 `reviewer: Codex` / `status: approved` / “100% 완료” 표현은 이 검토를 반영한 승인이 아니다. Codex 독립 판정은 위 finding이 닫히기 전까지 **pending**이다.

## `84f26ca` DOM harness 및 연속 조회 잔여 — 사용자 변형 증거

사용자가 제공한 실측을 기록한다(이 단락의 테스트 재실행자는 사용자이며 Codex는 해당 변형을 다시 돌리지 않았다). `84f26ca`는 `happy-dom`을 추가했고 `ResourceExplorer`를 `tests/browser/desktop.tsx` 및 `resource-explorer-dom.test.tsx`에 마운트해 이전에 없던 effect 구동 lane을 만들었다. 사용자는 DOM 시험 5건과 `fabric-control-plane.test.tsx` 26건 통과를 보고했다. 이어 `items.length > 0` 조건을 복원했을 때에도 5+26건이 모두 통과했고 소스를 원복했으며 트리는 clean이라고 보고했다. 새 lane의 방향은 개선됐지만 정상 성공-empty가 **기존 후보에서 재조회하는 전이**로 고정되지는 않았다.

### Gemini 전달용 구체 계약

각 케이스는 같은 컴포넌트를 실제 사용자 경로로 두 번 조회해야 한다(버튼·탭·props 기반 재조회 중 구현에 맞는 경로는 Gemini가 선택). 단일 최초 조회는 기존 목록 잔류 mutant를 구분하지 못한다.

| DOM 시나리오 | 응답 순서 및 최종 합격 | 함께 주입할 mutant | mutant가 시험에서 실패해야 하는 이유 |
|---|---|---|---|
| 후보 있음 → 정상 빈 응답 | 1차 GET이 pending 후보 1개를 반환한다. 그 row와 승인/거부 버튼이 보이는 것을 먼저 확인한다. 2차 GET은 `{items: []}`다. 이후 기존 row/버튼이 사라지고 success-empty 상태가 보인다. | `setCandidates` 갱신을 `items.length > 0` 조건 안으로 되돌린다. | 2차 응답 후 첫 후보가 남으므로 row/button 부재 및 empty 상태 단언이 실패한다. |
| 후보 있음 → 재조회 오류 | 1차 GET에서 후보 row/운영 버튼을 확인한다. 2차 GET은 401/5xx 또는 network rejection이다. 최종 화면에 error alert가 있고 row/버튼은 없어야 한다. | catch에서 `setCandidates([])` 제거. | stale 후보와 운영 버튼이 남아 clear/button 부재 단언이 실패한다. |
| error + 후보 데이터 | 실패 직후 목록이 이미 빈 상황만 검사하지 않는다. error 상태 전이와 함께 후보 1개를 남기는 harness/state fixture를 만들어 error가 버튼을 억제하는지 본다. | error-state의 후보 목록 렌더 가드 제거. | 데이터가 있어도 error 상태 자체가 운영 버튼을 숨겨야 하므로 mutant에서 버튼이 나타나 시험이 실패한다. |

각 mutant를 개별 적용해 대응하는 DOM 시험이 실패함을 Gemini가 확인하고, 원복 후 같은 시험이 통과해야 한다. 시험이 통과했다는 수치만으로는 완료가 아니다. 현 판정은 제품 코드 방향이 맞더라도 이 세 회귀 조건을 고정하지 못한 **UI-FB-01 독립 검토 pending**이다.

### Mock 응답 shape와 실제 backend 계약

adapter 시험이 `apiClient`를 mock하면서 expected response shape를 시험 안에서 직접 만들고 같은 mock 값을 반환하는 방식은 consumer와 provider를 독립적으로 대조하지 않는다. 권고 계약은 한 쪽만 source of truth가 되는 것이다: backend의 OpenAPI/Pydantic response schema에서 TypeScript 타입 또는 JSON Schema fixture를 생성하고, (1) client adapter test는 응답을 그 schema로 검증하며, (2) backend provider test는 실제 route response가 같은 schema를 만족하는지 검증한다. 생성 산출물의 drift 자체도 CI에서 검사한다. live backend 시험이 환경상 skip되더라도 provider schema 생성/검증은 backend 소스 또는 OpenAPI snapshot에서 실행할 수 있어야 한다. hand-written mock fixture가 contract 정의 역할까지 겸하게 두지 않는다.

역할 경계: 이 표는 Gemini 전달용 finding이다. Codex는 Antigravity에 직접 보내지 않았고 UI 구현·시험을 수정하지 않았다. Gemini가 위 세 변형을 통과시키고 fixed SHA를 제공한 뒤 Codex가 독립 재검토한다.
