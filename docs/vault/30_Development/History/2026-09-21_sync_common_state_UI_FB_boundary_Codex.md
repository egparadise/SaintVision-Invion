---
doc_id: "SYNC-COMMON-STATE-UI-FB-BOUNDARY-20260921-CODEX"
title: "Obsidian 공용 worktree state와 UI-FB 경계 최종 재검토"
version: "1.0.4"
status: "review"
author: "Codex"
updated: "2026-09-21T12:52:00+09:00"
source_of_truth: "Git"
tags: ["sync-obsidian", "git-worktree", "UI-FB", "mutation-testing", "verification-boundary"]
---

# Obsidian 공용 worktree state와 UI-FB 경계 최종 재검토

## 범위와 기준

- 시작 tip: `f5bb37c` (`integration/all-agents-unified`).
- 변경 owner: Codex (`tools/sync_obsidian.py`, `tools/test_sync.py`, 감사·진행 문서). UI owner는 Gemini이며 Codex는 재검토만 했다.
- Python 검증 인터프리터: `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe`; 프론트 시험은 `apps/web`의 npm/Vitest.
- Vault 파일에 `--apply` 하지 않았다. state metadata 한 파일만 Git common-dir로 이동했다.

## Obsidian state 경로 결함과 수정

사용자 조사에서 단일 공유 vault의 baseline이 checkout마다 분리됨을 확인했다. 기존 `rev-parse --git-path`는 주 checkout에서 `.git/obsidian-sync-state.json`, `C:\vw`에서 `.git/worktrees/vw/obsidian-sync-state.json`을 반환했다. `C:\vw` 파일에는 1,370개 baseline 항목이 있었고 common-dir의 state는 없었다.

이전 state를 옮기기 전, 다음 read-only 검사를 수행했다.

```powershell
.\.venv\Scripts\python.exe tools\sync_obsidian.py --check --state 'C:\Project\SaintVision-Invion\.git\worktrees\vw\obsidian-sync-state.json'
```

결과: exit 0, `1372 managed files, 10 pending exports, 0 conflicts. No writes.` 따라서 기존 1,370-entry state를 현재 source/vault와 대조한 뒤에만 전환했다.

`default_state_path()`를 `git rev-parse --git-common-dir` 기반으로 바꾸고 `obsidian-sync-state.json`을 common-dir 아래에 둔다. 기존 state bytes를 `ReadAllBytes`로 읽어 공용 파일에 그대로 기록했고 JSON 항목 수 1,370을 확인했다. 그 뒤 새 기본 경로로 주 checkout `--check`를 실행해 exit 0, `1372 managed / 10 pending / 0 conflicts`를 확인한 다음 이전 per-worktree 파일을 제거했다. 이 과정은 vault 파일을 쓰지 않았다. PowerShell에서 시도한 SHA 비교 API는 해당 호스트 런타임에 없어 유효한 digest 비교로 간주하지 않는다. 원본 byte array를 직접 기록한 것과 새 파일의 JSON 항목 수를 확인한 것이 migration evidence다.

변경 후 경로 확인:

```text
default_state_path(C:\Project\SaintVision-Invion) = C:\Project\SaintVision-Invion\.git\obsidian-sync-state.json
default_state_path(C:\vw)                         = C:\Project\SaintVision-Invion\.git\obsidian-sync-state.json
same = True
```

`tools/test_sync.py::test_default_state_is_shared_by_linked_worktrees`는 임시 Git repo와 linked worktree를 실제로 만들고 같은 common state 경로 및 서로 다른 git-path 경로를 비교한다. `--git-path` 구현으로 되돌린 mutation에서는 해당 시험이 assertion에서 실패(exit 1)했다. 수정본 전체 `tools/test_sync.py`: 14 passed; unittest가 추가 보고한 하위 cases 5 passed.

주 checkout migration 직후 check는 `1372 managed / 10 pending / 0 conflicts`였다. 당시 paired 실행의 main 6 및 C:\vw 3 pending, 이후 main 6 및 C:\vw 5 pending은 모두 서로 다른 문서 snapshot의 중간 측정이므로 최종 비교값으로 쓰지 않는다.

### 사용자 최신 paired check 및 export — 2026-09-21

사용자가 두 checkout을 같은 `b5ea2a5` snapshot으로 맞춘 뒤 각각 `tools/sync_obsidian.py --check`를 실행했다. 두 결과 모두 **1373 managed / 6 pending / 0 conflicts**, exit 0이었다. 사용자가 이 시점의 6 pending 문서를 `--apply`해 exit 0, `EXPORTED 6 files; all 1373 destination hashes match`를 확인했다. 적용 뒤 read-only `--check`는 **1373 managed / 0 pending / 0 conflicts**였고 vault 전체는 1,384 files였다. 따라서 기존 6/5, 7 no-baseline, 1373/0/0의 중간 관측을 대체하는 현재 안정 기준은 `b5ea2a5: 1373/0/0`이다.

실행자는 사용자다. 최신 메시지는 명령과 결과를 제공하지만 정확한 Python 실행 경로와 실행 시각은 제공하지 않으므로 이를 추정하지 않는다. 이 구간은 사용자가 보고한 CLI 실측이며 Codex가 실행한 것으로 표시하지 않는다.

## UI-FB-01/02/03 fixed-tip 경계 재검토

### UI-FB-01 — 승인

사용자가 `f5bb37c`의 연속 조회 DOM 시험에 세 mutant를 각각 주입했다. `items.length > 0` 복원, catch의 `setCandidates([])` 제거, error 상태의 목록 render guard 제거가 각각 시험 실패를 일으켰고 원복 후 성공했다. 이는 Codex가 이전에 독립 승인 보류했던 시험 공백을 해소한다. 해당 변형 결과의 실행자는 사용자이며 Codex가 재실행한 것으로 기록하지 않는다.

### UI-FB-02 — component boundary 승인, browser acceptance 별도

소스에서 로컬 점수는 `evaluatePlacement()`의 `localExplainResult`에서 나오며 별도 배지에 `UNVERIFIED: 로컬 시뮬레이션 전용`이라고 명시한다. 서버 shards는 별도 `placement-preview` 응답과 `previewState`로 표시된다. 오류 시 server shards를 비우고 error banner를 렌더한다. Codex가 실행한 `npm exec vitest -- run tests/placement-simulator.test.tsx`: 9 passed. 배지를 `서버 검증 완료`로 바꾸는 mutation은 배지 계약 시험 하나가 실패(exit 1)했다.

이 근거는 local result가 UI에서 server admission이라고 라벨링되지 않는 경계를 고정한다. 실제 브라우저, live backend 및 장비의 UI acceptance를 뜻하지 않는다.

### UI-FB-03 — 독립 승인 보류

소스 경로는 ResultView의 성공 `output`이 없으면 artifact fallback을 하지 않고, route-not-found 404일 때만 fallback하며 401/403/5xx/network/parse 오류는 data를 지우고 error로 기록한다. output verified badge는 `verifiedEvidenceId`와 non-fallback 여부를 요구한다. 그러나 기존 `developer-studio.test.ts` 13건은 `isRouteNotFoundError()` helper 값만 검사한다.

Codex는 다음 mutation을 수행했다. component의 `if (isRouteNotFoundError(err))`를 `if (true)`로 바꿔 모든 ResultView 오류에 artifacts fallback을 허용한 뒤 `npm exec vitest -- run tests/developer-studio.test.ts`를 실행했다. 13건 모두 통과(exit 0)했다. 원복했다. 따라서 helper의 분류시험은 존재하지만 component 요청 전이와 fallback 금지 계약을 고정하지 못한다. Gemini는 실제 component/effect test에서 401, 403, 5xx, malformed JSON/network rejection 각각에 대해 artifacts endpoint 호출 0회, 오류 노출, artifact verified 상태 부재를 고정하고, route-only 404에서는 허용된 fallback 및 UNVERIFIED 표시를 대조해야 한다. 이 finding 해소와 mutation failure 전까지 FB-03 승인을 보류한다.

## Discovery candidates mock/backend response 계약 — 구현 완료, 단일 endpoint 범위

첫 slice는 `GET /v1/discovery/candidates` 한 endpoint다. Backend `DiscoveryCandidatesResponse` / `DiscoveryCandidateResponse`가 strict Pydantic wire contract이고 `tools/export_schemas.py`가 JSON Schema를 생성한다. `apps/web/scripts/discovery-contracts.mjs`는 해당 JSON Schema에서 TypeScript response type을 생성하거나 `--check`로 drift를 거부한다. API adapter는 generated wire type을 사용하며 ResourceExplorer의 post-action `admitted`/`declined` 상태는 더 넓은 UI-only state type으로 분리한다.

`contracts/fixtures/discovery-candidates-response.json`은 backend provider test와 Vitest mock이 함께 쓰는 canonical response다. DB 없이 FastAPI router를 mount하고 auth/session/time dependencies 및 discovery service를 대역 주입해 실제 response-model serialization을 검사한다. Pydantic exact property-set/strict validation과 Ajv JSON Schema validation은 누락, 추가 속성, `verified: true`, 잘못된 `state`를 거부한다. 프런트 build는 generated type을 소비하고 frontend workflow의 `contracts:check`는 schema/type drift를 거부한다. 이 경로는 live backend나 DB를 요구하지 않는다.

`route_coverage.py`는 registered/client path shape만 검사한다. HTTP method와 payload schema를 다시 검사하지 않으며 response 계약은 위 Pydantic/JSON Schema/fixture gate가 담당한다. 기존 source 문자열 기반 discovery response invariant test는 제거하고 실행 가능한 provider/fixture test로 대체했다. 다른 adapter로 확장하는 것은 별도 slice다.

## 다음 담당과 첫 행동

- Gemini: UI-FB-03 component fallback test를 보강한 fixed SHA를 제공한다.
- Codex: 그 SHA에서 401/403/5xx/parse/network 및 genuine 404의 호출 전이를 재검토한다. browser/live backend acceptance는 별도 owner 조건이 준비될 때만 판정한다.
- Obsidian: 사용자 paired check는 두 checkout 모두 동일 `b5ea2a5`에서 1373/6/0이었다. 사용자는 6개를 적용해 모든 1373 destination hash 일치와 사후 1373/0/0을 확인했고 vault는 1,384개 파일이다. 이전 6/5는 중간 snapshot 측정이다. 다음 문서 변경은 새 pending export이며, 이 기존 적용을 반복하지 않는다.
- Codex: discovery candidates contract slice 구현 후 Claude 독립 리뷰로 인계한다. UI-FB-03 component error/fallback test는 Gemini owner 대기이고 브라우저 acceptance와 분리한다.
