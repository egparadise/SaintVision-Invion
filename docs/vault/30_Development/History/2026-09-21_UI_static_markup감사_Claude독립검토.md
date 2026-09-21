---
doc_id: "REVIEW-UI-STATIC-MARKUP-AUDIT-CLAUDE-001"
title: "Codex UI static-markup 시험 감사 독립 검토 — 전수·분류·변형대조·놓친 형태. 시험 미수정(Gemini 인계)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Gemini"
updated: "2026-09-21T18:00:00+09:00"
head_commit: "a0e5bda"
source_of_truth: "Git"
tags: ["saintvision", "independent-review", "frontend-tests", "renderToStaticMarkup", "mutation-testing", "hand-to-gemini"]
---

# Codex UI static-markup 시험 감사 독립 검토

Codex의 `renderToStaticMarkup` 시험 감사(`2026-09-21_sync_obsidian_state_and_static_markup_audit_Codex.md`)를 독립 검토했다. **목적**: UI 코드는 지금 맞게 고쳐져 있으나 회귀가 들어가도 아무도 못 잡는다 — **어떤 시험이 그 회귀를 잡는가**를 밝힌다. **범위: 시험 미수정(apps/web=Gemini 소유). 발견만 기록, Gemini 인계.** 검토 중 변형 대조를 위해 메인 체크아웃 소스를 임시 변형했다가 `git checkout`으로 **원복**했다(커밋 없음). `[소스]`=소스 읽기 판단, `[변형]`=실제 변형 주입 확인.

## ① 전수 여부 — 전수 맞음 `[실측]`
`grep -rl renderToStaticMarkup apps/web/tests` = **7 파일 / 27 call site / 전체 32 Vitest 파일** — Codex 개수와 정확히 일치. 추가로 **다른 SSR 렌더 방식이 있는지** 확인: `renderToString` 0, `@testing-library` import 0, `ReactDOMServer`/stream 0. 즉 SSR 렌더는 `renderToStaticMarkup`이 유일하므로 Codex가 그것만 검색해도 **SSR-렌더 형태는 완전 포착**. 전수 주장 성립.

## ② 분류 기준 — 타당 `[소스]`
Codex 기준(“`renderToStaticMarkup` 자체는 적절, 그 방식으로 fetch/상태전이를 주장하면 근거 초과”)은 옳다. 대표 파일 확인:
- `fabric-control-plane.test.tsx`: 시험 1–16은 `apiClient`(mock) 직접 호출로 endpoint/params 검증(유효 adapter 시험). 366행+ UI 시험은 `<ResourceExplorer initialTab initialCandidatesState="success" initialCandidates={[]} />`처럼 **상태를 props로 주입**하고, 이름은 “**after successful empty query**”(fetch 결과처럼 명명)이나 **fetch/useEffect를 실행하지 않는다**. → Codex 분류(over-claim) 정확.
- adapter 직접 호출 파일(fabric-observation/live-observation/run-approval-observation)이 “유효”라는 판정도 request 구성 검증 측면에서 맞다(단 ④ 참조).

## ③ 되돌림 대조 — 변형으로 공허성 확증 `[변형]`
`ResourceExplorer`의 전이 로직(`loadDiscoveryCandidates`: `getDiscoveryCandidates()` → `setCandidates(res?.items || [])` → `setCandidatesState('success')`)을 **깨서** `setCandidates([])`(성공해도 발견 후보를 버림 = 실제 회귀: UI에 후보가 절대 안 뜸)로 바꾸고 `fabric-control-plane`을 돌렸다. → **26 passed, exit 0. 안 잡힘.** 원복 확인. 즉 SSR+props 주입 시험은 이름과 달리 **전이 회귀를 구성적으로 못 잡는다**(소스 판단이 변형으로도 확증됨). 사용자의 `items.length>0`·유령초기값 재현과 동일 결.

## ④ 감사가 놓친 형태 (Codex 분류 밖 — 추가 발견)
- **(a) 전이는 SSR뿐 아니라 모든 lane에서 미커버 `[실측]`**. `ResourceExplorer`는 **오직 `fabric-control-plane.test.tsx`에서만** 나오고 그 파일의 DOM/effect 실행은 0(SSR 10). 별도 browser harness `apps/web/tests/browser/desktop.tsx`는 **`InvFileExplorer`·`ModelStudioView`만 mount하고 `ResourceExplorer`는 안 한다**(소비: `tests/integration/test_desktop_browser.py`). 따라서 위 전이 회귀는 **Vitest·browser 어느 lane에서도 불가시**다. Codex는 browser lane을 “다른 lane, 미실행”으로만 적고 그것이 ResourceExplorer를 덮지 않는다는 점은 명시하지 않았다.
- **(b) mock–계약 gap `[소스]`**. “유효 adapter 시험”이 `apiClient`를 mock하며 **응답 shape를 테스트가 임의로 정한다**(예: `mockResult = {items:[], nextCursor:null}` 후 `expect(res).toEqual(mockResult)` = pass-through). 이 shape는 **실제 백엔드 응답 계약과 대조되지 않는다.** 백엔드가 shape를 바꾸거나 mock이 애초에 틀리면 시험은 통과해도 컴포넌트(`res?.items`)가 깨진다 — 사용자가 지목한 “mock이 실제 API 계약과 어긋나는” 형태다. Codex는 이 파일들을 “유효”로만 판정하고 계약 대조 부재는 짚지 않았다. (apiClient의 실제 HTTP 계층은 이 파일들에선 mock이고, real은 `api-proxy.test.ts` 등 소수에만 있다.)

## 회귀를 잡을 시험 (목적)
지금 코드는 옳다. 회귀를 잡으려면:
- **전이(effect→state→render)**: `ResourceExplorer`를 **DOM에서 mount**(jsdom+@testing-library 또는 desktop browser harness에 discovery 탭 추가)하고, **adapter `getDiscoveryCandidates`를 mock**해 items를 반환시킨 뒤 **useEffect 완료를 기다려** 렌더에 items가 나타나는지 단언한다. 그러면 `setCandidates([])` 변형이 잡힌다. 현재 apps/web엔 이 effect-실행 lane이 없다(@testing-library 미사용).
- **empty/error 4-state**: 실제 빈 응답·pending·실패·이전 후보 재조회 실패를 **effect 경로로 주입**하고 mutation 버튼 부재를 검사(Codex도 같은 취지 권고).
- **mock–계약**: adapter mock shape를 백엔드 OpenAPI/스키마와 대조하는 계약 시험, 또는 browser/통합 lane이 실제 endpoint를 치게 한다.

## 종합 · 인계
Codex 감사는 **전수·분류·되돌림 대조 정합** — 내가 실측·변형으로 확증했다(결함 0). 다만 **두 가지를 보강**해 Gemini에 넘긴다: (a) 전이가 browser lane 포함 **모든 lane에서 미커버**(desktop harness가 ResourceExplorer를 안 mount), (b) **mock–계약 gap**(응답 shape 미검증). 다음 owner는 Gemini(apps/web 소유), 시험 추가 후 Codex 경계 review. 나는 시험을 수정하지 않았고 변형은 원복했다.
