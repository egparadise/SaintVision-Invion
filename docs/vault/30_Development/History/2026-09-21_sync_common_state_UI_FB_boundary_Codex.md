---
doc_id: "SYNC-COMMON-STATE-UI-FB-BOUNDARY-20260921-CODEX"
title: "Obsidian 공용 worktree state와 UI-FB 경계 최종 재검토"
version: "1.0.2"
status: "review"
author: "Codex"
updated: "2026-09-21T12:40:00+09:00"
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

주 checkout의 migration 직후 `--check`는 `1372 managed / 10 pending / 0 conflicts`였다. 동일 코드 tip `507a486`에서 main은 exit 0, `1373 managed / 6 pending / 0 conflicts`, `C:\vw`는 exit 0, `1373 managed / 5 pending / 0 conflicts`였다. 차이는 main에서 이 history 문서를 추가로 수정한 한 파일이며 state 공유 자체의 차이는 아니다. 두 곳은 같은 common-dir state를 읽고 `--check`는 vault에 쓰지 않는다. `C:\vw`의 이전 `1373 / 0 / 0`은 먼저 확인한 중간 시점 결과이며 최종 결과가 아니다. 실행은 main의 `.venv\Scripts\python.exe`로 `C:\vw\tools\sync_obsidian.py --check`를 호출했다. `C:\vw` 자체 Python 환경은 실행되지 않았다. 문서 snapshot을 동일하게 맞춘 뒤 양쪽 check를 다시 대조한다.

## UI-FB-01/02/03 fixed-tip 경계 재검토

### UI-FB-01 — 승인

사용자가 `f5bb37c`의 연속 조회 DOM 시험에 세 mutant를 각각 주입했다. `items.length > 0` 복원, catch의 `setCandidates([])` 제거, error 상태의 목록 render guard 제거가 각각 시험 실패를 일으켰고 원복 후 성공했다. 이는 Codex가 이전에 독립 승인 보류했던 시험 공백을 해소한다. 해당 변형 결과의 실행자는 사용자이며 Codex가 재실행한 것으로 기록하지 않는다.

### UI-FB-02 — component boundary 승인, browser acceptance 별도

소스에서 로컬 점수는 `evaluatePlacement()`의 `localExplainResult`에서 나오며 별도 배지에 `UNVERIFIED: 로컬 시뮬레이션 전용`이라고 명시한다. 서버 shards는 별도 `placement-preview` 응답과 `previewState`로 표시된다. 오류 시 server shards를 비우고 error banner를 렌더한다. Codex가 실행한 `npm exec vitest -- run tests/placement-simulator.test.tsx`: 9 passed. 배지를 `서버 검증 완료`로 바꾸는 mutation은 배지 계약 시험 하나가 실패(exit 1)했다.

이 근거는 local result가 UI에서 server admission이라고 라벨링되지 않는 경계를 고정한다. 실제 브라우저, live backend 및 장비의 UI acceptance를 뜻하지 않는다.

### UI-FB-03 — 독립 승인 보류

소스 경로는 ResultView의 성공 `output`이 없으면 artifact fallback을 하지 않고, route-not-found 404일 때만 fallback하며 401/403/5xx/network/parse 오류는 data를 지우고 error로 기록한다. output verified badge는 `verifiedEvidenceId`와 non-fallback 여부를 요구한다. 그러나 기존 `developer-studio.test.ts` 13건은 `isRouteNotFoundError()` helper 값만 검사한다.

Codex는 다음 mutation을 수행했다. component의 `if (isRouteNotFoundError(err))`를 `if (true)`로 바꿔 모든 ResultView 오류에 artifacts fallback을 허용한 뒤 `npm exec vitest -- run tests/developer-studio.test.ts`를 실행했다. 13건 모두 통과(exit 0)했다. 원복했다. 따라서 helper의 분류시험은 존재하지만 component 요청 전이와 fallback 금지 계약을 고정하지 못한다. Gemini는 실제 component/effect test에서 401, 403, 5xx, malformed JSON/network rejection 각각에 대해 artifacts endpoint 호출 0회, 오류 노출, artifact verified 상태 부재를 고정하고, route-only 404에서는 허용된 fallback 및 UNVERIFIED 표시를 대조해야 한다. 이 finding 해소와 mutation failure 전까지 FB-03 승인을 보류한다.

## 공통 mock/backend response 계약 제안

모든 UI mock을 live backend에 묶지 않는다. 기존 backend Pydantic strict response model → JSON Schema/OpenAPI export drift gate를 response envelope까지 확장하고, frontend types/fixtures는 같은 schema에서 생성하거나 검사한다. DB 없는 provider serialization test가 실제 FastAPI response shape를 검증하고, adapter/component tests는 canonical fixture로 변환·오류 처리를 검증한다. `route_coverage.py`는 path-shape 범위로 유지하며 method/response schema 검사로 오해하지 않는다. 이 안은 제안이며 이 작업에서 구현하지 않았다.

## 다음 담당과 첫 행동

- Gemini: UI-FB-03 component fallback test를 보강한 fixed SHA를 제공한다.
- Codex: 그 SHA에서 401/403/5xx/parse/network 및 genuine 404의 호출 전이를 재검토한다. browser/live backend acceptance는 별도 owner 조건이 준비될 때만 판정한다.
- Obsidian: 공용 Git common-dir state로 전환 완료. 동일 코드 tip에서 main은 6, `C:\vw`는 5 pending exports / 모두 0 conflicts였으며 차이는 main에서 수정 중인 history 문서 1건이다. 둘 다 `--apply` 없이 유지한다. 다음 동기화는 일반 `--check` 후 승인된 정책에 따른 절차로 진행한다.
