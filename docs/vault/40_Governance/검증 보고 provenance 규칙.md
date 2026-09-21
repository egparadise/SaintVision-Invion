---
doc_id: "VERIFICATION-PROVENANCE-RULE-001"
title: "검증 보고 provenance 규칙 — 강제 형식과 생성 도구"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T14:30:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["governance", "verification", "provenance", "reproducibility", "reporting-rule"]
---

# 검증 보고 provenance 규칙

**적용: 다음 세션부터, 모든 "검사 통과/실패" 보고에 강제.** 권고로만 두면 다음 사람이 안 읽어 없는 것과 같다 — 2026-09-21 하루 종일 아무도 pass-report에 tip을 안 박아 브랜치-통합 괴리(check_docs가 각자 브랜치엔 green·통합엔 broken)를 못 봤다. 이 규칙은 그 형식을 확정하고 **기계적으로 생성하는 도구**(`tools/provenance.py`)를 제공해, 사람이 손으로 적어 빠뜨리는 것을 막는다.

이 규칙은 Codex의 보고 규칙 제안([[2026-09-21_integration-tip-verification_Codex]] 9항)을 **운영 표준으로 승격**하고, 빠진 세 가지(A clean 상태·측정법, B 환경 지문/생략목록, C 신뢰 계측)를 더하며, 도구로 강제한다. 중복이 아니라 그 제안의 실행 형태다.

## 강제 형식

### 필수 항목 (없으면 그 보고는 통합 상태를 보증하지 못함)
| 항목 | 획득 명령 |
|---|---|
| 1. commit_sha (full) | `git rev-parse HEAD` |
| 2. branch | `git rev-parse --abbrev-ref HEAD` (detached면 `(detached@<sha>)`) |
| 3. worktree_path | `git rev-parse --show-toplevel` |
| 3-1. **integration_sync** | 이 트리가 통합 tip과 같은가. 다르면 몇 커밋 뒤/앞인가. **로컬 기준**(마지막 fetch한 `origin/integration/all-agents-unified`)으로 `git rev-list --count HEAD..origin/integration/all-agents-unified`(뒤처짐)·`...{ref}..HEAD`(앞섬). 네트워크 갱신은 선택(`--fetch`). 브랜치에서 통과한 것을 통합 상태로 읽지 않기 위함 — 거리가 보고에 있어야 한다. |
| 4. **working_tree_clean** | `git status --porcelain` 빈값 = clean. **단 EOL 드리프트 게이트는 `git diff --exit-code`로 판정** — Windows에서 `git status`는 CRLF를 "수정됨"으로 오탐한다(2026-09-21 `models.py` 실증). "clean을 어느 명령으로 쟀는가"가 결과를 바꾸므로 명시한다. |
| 5. interpreter (절대경로) | 실제 실행 인터프리터. python이면 `sys.executable`(bare `python`과 `.venv`를 혼동 불가), shell 도구면 `which <tool>`의 절대경로 |
| 6. runtime version | `python --version` / `node --version` / `go version` 중 해당 |
| 7. timestamp KST | 시작·종료 시각 |
| 8. 검사별 결과 | **정확한 명령 + 작업 디렉터리 + 직접 종료코드(파이프로 가리지 말 것) + pass/fail/skip/deselected 수 + skip 사유** |
| 9. executor + 검토자 동일인 여부 | 실행자와 검토자가 다른 사람이라야 독립 검증(Codex 9항) |

### 선택/조건부 항목
- **환경 지문 + "안 돌린/skip한 검사와 그 이유"** (필수에 준함): 이 호스트가 PG/Docker/Go/browser 게이트를 돌릴 수 있는지(`INV_TEST_ADMIN_DSN` 유무, `docker`/`go`/`node` 존재). Windows "전부 통과"가 그 게이트를 통째로 생략했다면 CI 통과와 다르다 — 무엇을 생략했는지 표면에 있어야 한다.
- **artifact 경로** (junit xml 등) 해당 시.
- **단일 실행 vs 배치 산술 합** 라벨: 여러 배치 합이면 한 실행처럼 인용하지 말 것(JUnit 432/2628 함정).

## 생성 도구 — 손으로 적지 말 것
```
python tools/provenance.py                 # 필수 1~7·9 + integration_sync + 환경 지문 생성 → 보고에 붙여넣기
python tools/provenance.py --json          # JSON
python tools/provenance.py --executor NAME # 실행자 각인
python tools/provenance.py --fetch         # integration_sync를 네트워크 갱신 후 측정(기본은 로컬 last-fetch)
python tools/provenance.py --integration-ref REF   # 비교 대상 ref 변경
python tools/provenance.py -- <검사 명령>   # 헤더 + 그 검사를 파이프 없이 실행해 종료코드·출력꼬리까지 자기 정체성으로 출력(항목 8), 검사의 종료코드로 종료
```
도구는 (3-1) integration_sync를 로컬 `origin/integration/all-agents-unified` 대비 `git rev-list --count`로 재서 **IN SYNC / BEHIND N / AHEAD M**을 찍고(뒤처졌으면 "results from this tree may NOT reflect integration" 경고), (4)를 `git status --porcelain`과 `git diff --quiet HEAD` 양쪽으로 재서 **status-dirty·content-clean이면 EOL/untracked 산물**임을 명시하고, (5)를 `sys.executable`로, (8)의 종료코드를 subprocess 반환값으로 직접 잡아 `| tail`류 파이프 마스킹을 원천 차단한다. integration_sync는 **네트워크 없이 로컬 last-fetch 기준**이 기본이며 그 사실을 출력에 라벨한다(`local (last fetch)` vs `fetched`) — 로컬 ref가 stale일 수 있으므로 정확한 거리는 `--fetch`.

## 검사 자기-출력에 대한 판단 (사용자 part 3)
검사 도구마다 자기 정체성을 뱉게 고치는 것은 python·go·npm 다언어라 침습적이다. **현실적 강제점은 wrap 모드**(`provenance.py -- <검사>`)다 — 언어 무관, 검사 도구 무수정, 종료코드를 파이프 없이 캡처. 따라서 보고되는 검사는 wrap으로 돌리는 것을 표준으로 한다. (최다 사용 게이트가 한 줄 정체성을 추가로 찍는 것은 선택적 보강일 뿐 필수 아님.)

## 검증 (되돌림 대조 포함, 2026-09-21 실측)
`tools/provenance.py`를 오늘 우리가 쓴 방식으로 검증했다:
- **두 워크트리에서 다른 값**: `.worktrees/claude-cx01`(SHA b2c2080) vs 주 checkout(SHA 5c7ce9d) — commit_sha·worktree_path·branch 모두 다르게 출력.
- **dirty 트리**: 추적 파일 내용 변경 시 `working_tree_clean=NO`·`content_clean=NO`, 원복 시 복귀.
- **EOL 케이스**: 추적 파일을 CRLF로 바꾸면 `status=NO`이나 `content=YES` + "EOL/untracked 산물" note — 실 드리프트와 구분. 원복.
- **wrap 종료코드**: 검사 exit 1이면 wrapper도 1, exit 0이면 0 (파이프 없이 확인). 종료코드 라인은 이후 `| grep`에도 안 가림.

## 실증 — provenance를 안 찍으면 무엇이 안 보이나 (2026-09-21)
도구를 검증하던 중 오늘 문제의 **원형**을 실물로 만났다. 주 체크아웃(`C:/Project/SaintVision-Invion`)의 HEAD가 `5c7ce9d`인데 통합 tip은 `89c6bc3`이었다 — 로컬 측정으로 **BEHIND 7**. 거기엔 `provenance.py`도 아직 없었다. agent들은 각자 워크트리에서 작업해 통합에 push하지만 **주 체크아웃은 자동으로 따라가지 않는다.** 아무도 보고에 `commit_sha`+`worktree_path`를 안 찍었기에 이 괴리가 하루 종일 안 보였다 — 이것이 `check_docs`가 각 브랜치엔 green·통합엔 broken이었는데 아무도 몰랐던 이유이고, 측정을 두 번 엉뚱한 트리에서 한 이유다. 도구의 출력은 그 상황을 숨길 수 없게 만든다:
```
integration_sync:    BEHIND 7   (vs origin/integration/all-agents-unified @89c6bc3; local (last fetch)) -- results from this tree may NOT reflect integration
```
**아침부터 이 한 줄이 있었다면 첫 보고에서 괴리를 봤을 것이다.** "도구가 유용하다"는 추상적 주장보다 이 사례가 규칙을 정당화한다 — provenance를 안 찍으면 어느 트리의 어느 시점인지가 보이지 않고, 뒤처진 트리의 통과를 통합 통과로 오독한다.

## 주 체크아웃·워크트리 동기 규약 (재발 방지)
위 실증의 물리적 원인 — 주 체크아웃이 통합보다 뒤처짐 — 을 재발하지 않게 하는 규약이다.

**오늘 이 문제가 실제로 만든 결과**(추상적 권고보다 이 근거가 설득력 있다): `check_docs.py`가 통합에서 broken이었는데 각 agent 브랜치에선 green이라 **하루 종일 아무도 몰랐다**. 그리고 나는 **두 번 엉뚱한(뒤처진) 트리에서 측정**했다. 원인은 하나 — 주 체크아웃(`C:/Project/SaintVision-Invion`)이 통합보다 8커밋 뒤처졌는데(BEHIND 8) 아무도 그 거리를 안 찍었다. 사람이 저장소를 열거나 도구를 돌릴 때 기본으로 가는 곳이 바로 거기다.

**규약(3방향 조합, 판단 결과):**
1. **주 체크아웃은 참조 전용, 항상 통합 tip과 동기.** agent는 `C:/Project/SaintVision-Invion`을 작업 공간으로 쓰지 않는다 — 각자 `.worktrees/<name>`에서 작업한다. 주 체크아웃은 통합 tip에 **detached로 맞춰 두어**(브랜치 ref는 건드리지 않음) 사람이 열거나 도구를 돌릴 때 통합 상태를 보게 한다. (2026-09-21 조치: 주 체크아웃을 `agent/codex/discovery-candidates-contract`@5c7ce9d에서 통합 tip `5c1e9ef`로 detached 갱신, 브랜치 ref 보존, 미커밋 없어 손실 0, 갱신 후 `integration_sync: IN SYNC` 확인.)
2. **tripwire = provenance 도구의 integration_sync.** 뒤처진 트리에서 검사를 돌리면 `BEHIND N` + "results from this tree may NOT reflect integration"이 **첫 보고에 뜬다.** 그래서 보고 검사는 `provenance.py`를 거쳐 돌린다(위 규칙). 이것이 규약 위반을 잡는 탐지기다.
3. **조건부 자동화는 가드 필수(선택).** 주 체크아웃 자동 갱신을 두려면 **clean이고 detached/참조 상태이며 최근 활동이 없을 때만** 통합 tip으로 ff한다. **미커밋 변경이나 활성 브랜치가 있는 트리는 절대 자동 갱신하지 않는다** — 오늘 `codex-public-dsn-integration` 워크트리가 integration 브랜치에 미커밋 6건을 들고 활성 작업 중이었다. 가드 없이 자동화했으면 그 작업을 파괴했을 것이다. 자동화 실장은 이 가드를 갖춘 뒤에만.

**요지**: 사람이 매번 기억해서 갱신하면 또 뒤처진다. 그래서 (1) 주 체크아웃을 참조로 고정하고, (2) 거리를 모든 보고에 자동으로 박아 위반을 즉시 보이게 하고, (3) 자동화하려면 활성 트리를 파괴하지 않는 가드를 건다.

## 왜 규칙으로 올리는가
2026-09-21 우리가 틀린 경우가 전부 이 항목 중 하나가 빠져서였다(인터프리터=5, 시점/트리=1·4, clean=4, 실행위치=3). 상호 정정 루프는 오류를 잡는 데는 탁월했으나 **인스턴스만 고치고 convention을 안 고쳐 같은 유형이 재발**했다. 이 문서와 도구는 사후 정정을 **예방**으로 바꾸기 위한 것이다. 관련: `memory:pass-report-provenance-rule`, `memory:wrong-interpreter-fakes-unrunnable`.

## 인계
Codex: 9항 제안자로서 이 표준·도구가 그 제안을 온전히 담는지, 더한 A/B/C가 충분한지 경계 재검토. 표준 채택 후 각 agent의 보고 템플릿([[Agent 연속 실행과 최종 보고 정책]] 계열)에 `provenance.py` 출력 첨부를 반영.
