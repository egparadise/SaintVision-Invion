---
doc_id: "SYNC-STATE-AND-SSR-AUDIT-20260921-CODEX"
title: "Obsidian 동기화 상태·EOL 및 Static Markup 시험 방식 감사"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Pending"
base_commit: "d230b21"
updated: "2026-09-21T11:08:18+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["sync-obsidian", "export-state", "frontend-tests", "renderToStaticMarkup"]
---

# Obsidian 동기화 상태·EOL 및 Static Markup 시험 방식 감사

## 범위

사용자 지시의 두 범위를 처리했다. Codex 소유 `tools/sync_obsidian.py`의 동일 파일 adoption/state 저장 경계는 구현·시험했다. `apps/web/tests`의 `renderToStaticMarkup` 사용은 읽기 전용으로 전수 검색하고, 화면 시험은 수정하지 않았다. 기준 tip은 `4706e89`다.

## Sync state 결함과 수정

### 원인

`export()`는 destination과 source의 해시가 같은 파일을 `state['files']`에 메모리상 기록했지만, 충돌이 하나라도 있으면 state write 전에 `ConflictsDetected`를 던졌다. 그래서 `--adopt-identical` 실행에서도 state 파일이 만들어지지 않았고, destination 변경 없이 안전하게 기록할 수 있는 baseline이 충돌 보고에 막혔다. 기본 state가 `.work/obsidian-sync-state.json`이어서 `.work` 정리 뒤 baseline도 소실될 수 있었다.

### 구현

- 명시적 `--adopt-identical`은 동일 해시 경로만 state에 기록하며, 충돌 판정 전에 state를 원자적으로 저장한다. 충돌 destination은 계속 건드리지 않는다. 진단은 vault 파일 미기록과 state metadata 기록을 별도로 말하고 JSON에도 `adoptedIdentical`을 담는다.
- 기본 state 경로를 `git rev-parse --git-path obsidian-sync-state.json`이 가리키는 현재 worktree의 Git metadata로 옮겼다. `.work` 및 vault/user asset 밖이며, linked worktree의 실제 gitdir도 Git에 조회한다. 환경상 git metadata 경로를 조회할 수 없으면 명시적 `--state` 사용 안내와 비zero로 끝난다.
- state 저장은 같은 디렉터리 임시 파일과 `os.replace`를 써 원자화했다.

### 실행 증거

- `.venv\\Scripts\\python.exe -m pytest -q tools/test_sync.py`: **5 passed**, exit 0.
- `.venv\\Scripts\\python.exe tools/check_docs.py`: exit 0; 24 source hashes, 588 versioned docs, 48 tasks and ownership/dependency checks passed. `.venv\\Scripts\\python.exe tools/check_ontology.py`: exit 0; RDF/SHACL and mirror checks passed. `git diff --check`: exit 0.
- `.venv\\Scripts\\python.exe tools/sync_obsidian.py --check`: exit 3; 675 unmanaged collisions (673 no-baseline, 2 both-diverged), no vault files written. This confirms the real shared-vault sync is still blocked; no `--apply` was attempted. The tool wrote only its `.work/obsidian-sync-conflicts.json` diagnostic.
- 새 CLI 회귀는 임시 Git 저장소와 비어 있는 state로 `main(['--check','--adopt-identical', ...])`을 호출한다. identical 파일 1개의 baseline은 `.git/obsidian-sync-state.json`에 생기고, 다른 편집 충돌은 exit 3으로 유지되며 destination의 사용자 파일 바이트는 보존된다.
- 별도 회귀에서 state path가 `.git` metadata 아래이고 `.work` 밖임을 확인한 뒤 임시 `.work` 디렉터리를 삭제해도 state 파일이 남음을 확인했다.
- 되돌림 대조: 충돌 보고 전 `_write_state` 호출을 제거하자 새 CLI 회귀가 **1 failed**로 깨졌다(기대 state 부재). 원복 뒤 전체 sync 시험은 5 passed다.
- 모든 CLI/state 시험은 임시 Git repo와 임시 vault를 썼다. 실제 공유 Obsidian vault는 수정하지 않았고 이 worktree의 `.git/obsidian-sync-state.json`도 만들지 않았다. `--apply`나 실제 vault sync는 실행하지 않았다.

## EOL 비교 보강 (d230b21 이후)

- 원인: exporter의 `sha()`는 raw byte를 비교해 CRLF/LF만 다른 파일도 수정된 파일처럼 판단했다. 비교에는 CRLF만 LF로 치환한 SHA-256을 쓰고, 복사/내보내기 바이트는 계속 저장소 원본 그대로 둔다. 새 state 값은 정규화 해시다. 기존 raw-byte manifest/state 해시는 raw 또는 정규화 해시 중 하나가 맞으면 baseline으로 인정해 전환 시의 오분류를 피한다.
- `.venv\\Scripts\\python.exe -m pytest -q tools/test_sync.py`: **8 passed**, exit 0. EOL-only 파일은 충돌 없이 비교되고 state에 정규화 해시가 남으며 destination 바이트는 CRLF 그대로인 것을 확인했다. 두 쪽에서 실내용이 달라진 파일은 `both-diverged`로 계속 충돌한다.
- 683개 합성 충돌 fixture는 667개의 EOL-only 파일과 14개의 무기준선 실내용 차이, 2개의 양쪽 변경으로 구성한다. 현재 구현은 **16 conflict (14 no-baseline, 2 both-diverged)**를 낸다. 정규화 코드를 제거하는 되돌림 대조에서는 시험이 **683 conflict** 대 16 기대값 차이로 실패했다. 수정 후 되돌림 대조로 보호되는 것을 확인했다.
- 실제 공유 vault의 read-only `.venv\\Scripts\\python.exe tools/sync_obsidian.py --check`는 exit 3, **16 conflict (14 no-baseline, 2 both-diverged)**를 보고했다. 이 실행 직전 이 worktree에 state가 없음을 확인했다. `--check`는 vault 파일을 쓰지 않았고 진단 JSON만 `.work`에 갱신했다.
- 비교 기준을 되돌린 추가 실측에서는 이 worktree의 실제 vault가 **675** 충돌(673 no-baseline, 2 both-diverged)이었다. 이는 사용자가 보고한 이전 시점의 683과 다르므로 그 수치를 이 worktree의 재현 결과라고 합치지 않는다. 683→16은 고정 합성 fixture에서의 되돌림 증거이고, 현재 live check는 16이다.
- `--apply`는 실행하지 않았다. 남은 16건의 내용 판정 및 사용자 vault 변경은 이 작업 범위에 포함하지 않는다.

### Claude index 흡수 후 최신 read-only check

Claude의 원격 commit `7404a6a`가 Overview와 설계 인덱스의 사용자 편집을 저장소 정본에 흡수한 뒤 같은 `--check`를 다시 실행했다. 결과는 **14 no-baseline, 0 both-diverged**, exit 3이다. 이 2건 감소는 EOL 정규화가 아니라 해당 index 편집의 저장소 흡수다. Claude의 `SYNC-OBSIDIAN-BLOCKED-CLAUDE-001` v1.4.0은 남은 14건을 SAFE(old residue 10, whitespace-only 4)로 판정했다. 그 이력 대조를 Codex가 다시 실행한 것은 아니므로 독립 확인으로 세지 않는다. `--apply`는 여전히 실행하지 않았다.

## `renderToStaticMarkup` 시험 인벤토리

### 전수 방법과 개수

`rg -l 'renderToStaticMarkup' apps/web/tests -g '*.{ts,tsx,js,jsx}'`로 파일을 목록화하고 각 파일의 `renderToStaticMarkup(` 호출을 셌다. 전체 **32개 frontend Vitest 파일 중 7개 파일, 27개 SSR render call site**가 해당한다.

| 파일 | SSR 호출 | 관측한 목적/한계 |
|---|---:|---|
| `tests/approval-review.test.tsx` | 1 | API review helper와 pure action 경계를 별도 테스트하고, `ApprovalDetail`은 전달받은 props로 정적 표시 확인 |
| `tests/desktop-layout.test.tsx` | 3 | layout/preference/tab 정적 렌더; fetch/effect 주장 없음 |
| `tests/fabric-control-plane.test.tsx` | 9 | 앞부분은 API client 함수 직접 호출 시험. UI 부분은 `ResourceExplorer`에 `initial*State` props를 주입해 렌더. “after successful empty query”, “when error”라는 이름과 달리 component fetch/useEffect는 실행하지 않음 |
| `tests/fabric-observation.test.tsx` | 2 | API adapter 함수 검증과 두 view의 빈 초기 화면 표시를 분리함; component effect 검증 아님 |
| `tests/live-observation.test.tsx` | 1 | fetch adapter를 별도 호출한 다음 데이터 props를 전달해 렌더함; effect 검증 아님 |
| `tests/placement-simulator.test.tsx` | 9 | `initialPoolsState`/`initialPreviewState` 등 상태 props를 직접 주입. “query/fetch fails” 명칭과 달리 API effect 실패를 발생시키지 않음 |
| `tests/run-approval-observation.test.tsx` | 2 | API adapter를 직접 호출하고 결과 props를 렌더함; effect 검증 아님 |

### 판정

- 일곱 파일 모두 `renderToStaticMarkup` 호출 자체로 React `useEffect`를 실행하지 않는다. 따라서 SSR 문장 검사만으로 component mount → request pending → fetch success/error → state transition을 주장하면 근거를 넘는다.
- UI-FB audit와 직접 연관된 `fabric-control-plane.test.tsx` 및 `placement-simulator.test.tsx`는 특히 시험 이름이 실제 fetch 결과처럼 읽히지만, 해당 케이스들은 상태 props를 직접 설정한다. 이전 되돌림 대조에서 catch clear/empty-result/error-state guard 변경을 되살려도 `fabric-control-plane` 26건이 통과한 것과 일치한다.
- 나머지 다섯 파일에는 `apiClient`/adapter를 직접 호출해 endpoint 구성·응답 shape·error 전달을 검증하는 유효한 helper-level 시험이 있다. 그것은 component effect 시험과 별개이며 잘못된 시험이라고 판정하지 않는다.
- `tests/developer-studio.test.ts`는 이 7개 SSR 파일에는 포함되지 않는다. 테스트는 `isRouteNotFoundError` helper 경계를 직접 검사하지만 DeveloperStudio의 `/result`→`/artifacts` 요청 분기와 오류 렌더를 실행하지 않는다.
- 별도 브라우저 harness `apps/web/tests/browser/approval.tsx`는 `useEffect`를 사용하고 `tests/integration/test_approval_browser.py`에서 소비된다. 이는 Vitest의 위 SSR 호출들과 다른 test lane이며, 이번 검색에서 실행하지 않았다.

### Gemini 인계용 검토 자료

화면 시험 변경은 하지 않았다. Gemini에게 넘길 test-method finding은 다음이다: UI 상태 fetch/effect를 검증하는 시험은 실제 DOM/browser harness에서 비동기 효과를 기다리거나, component에 연결된 상태 전이 helper를 검증해야 한다. `initial*State` props를 직접 넣은 SSR 케이스는 렌더 순수 표시 시험으로 이름·보고 범위를 제한한다. 특히 UI-FB-01은 정상 빈 응답, pending, 실패 및 이전 후보에서 재조회 실패를 실제 경로로 주입하고 mutation 버튼이 없는지 검사해야 한다. FB-02/03도 component 분기 및 endpoint 호출 횟수를 확인해야 한다. 이 기록은 Gemini 전달용이며 Codex가 Antigravity pane에 직접 전달하거나 UI test를 수정하지 않았다. 다음 owner는 Gemini, fixed SHA 후 Codex 경계 review다.
