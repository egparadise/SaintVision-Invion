---
doc_id: "UI-FB-CONTRACT-REVIEW-20260921-CODEX"
title: "UI-FB 계약 구현 준비도 재검토"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Gemini"
base_commit: "d0d1322"
updated: "2026-09-21T10:41:23+09:00"
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
