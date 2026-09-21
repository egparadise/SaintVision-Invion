---
doc_id: "SYNC-OBSIDIAN-BLOCKED-CLAUDE-001"
title: "sync_obsidian.py --check 차단 조사 — 683 충돌 사유별 분류·근본원인·도구 진단 수정. --apply 미실행"
version: "1.1.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T10:00:00+09:00"
source_of_truth: "Git"
tags: ["saintvision", "sync", "obsidian", "vault", "diagnosis", "no-apply"]
---

# sync_obsidian.py --check 차단 조사

`tools/sync_obsidian.py --check`가 uncaught ValueError + traceback + exit 1로 죽으며 충돌 675개(실측 683)를 그대로 쏟아낸다. 이 도구는 repo의 `docs/vault`를 사용자 OneDrive Obsidian vault로 내보내는 경로이므로, 막혀 있으면 **오늘 만든 감사·정정·회귀 증거가 사용자 vault에 도달하지 못한다.** 조사·진단까지만 수행했다. **사용자 자산인 vault에 `--apply`는 돌리지 않았고, 어떤 vault 쓰기도 하지 않았다**(모두 읽기 전용).

## 1) 683 충돌 사유별 분류 (읽기 전용 실측)
도구는 `docs/vault` **전체 1362 파일**을 내보내고, 각 파일의 `known` 기준을 `state['files'].get(rel, manifest.get(rel))`로 잡는다. 실측:
- source(docs/vault) 파일 **1362** / vault와 이미 동일 **613** / 깨끗한 pending export **66** / **충돌 683**.
- **충돌 사유**:
  - **681 = no-baseline**: 24파일 manifest에도 없고 state에도 없어 **비교 기준(known)이 아예 없다.** vault에 그 파일이 존재하고 repo와 내용이 다르면(과거 어느 시점 sync의 잔재) 도구가 "그게 사용자 편집인지 미기록 이전 sync인지 판별 불가"라 fail-closed. **대부분 착시성**(사용자 편집이 아니라 추적 공백). 단 도구는 판별 불가라 보수적으로 충돌 처리 — **일괄 덮어쓰기는 위험**(그중 일부가 진짜 편집일 수 있음).
  - **2 = both-diverged**: manifest에 있는 `00_Index/Overview.md`, `00_Index/SaintVision INV 개발 설계 인덱스.md` — repo와 vault가 **둘 다** 2026-09-09 manifest 해시에서 이동. **진짜 재조정 후보**(vault 쪽에 사용자 편집이 있을 수 있음).
  - **0 = destination-edited(vault만 편집)**: manifest 추적 파일 중 vault-only 편집은 없음.

## 2) 근본 원인
- `docs/source-manifest.json`은 **24파일만** curated 추적(`captured_at`, `vault`=OneDrive 경로, `files`). 그런데 도구는 `docs/vault` **전체 1362파일**을 내보낸다.
- 나머지 1338파일의 `known`은 **state 파일**(`--state`, 기본 `ROOT/.work/obsidian-sync-state.json`)이 추적해야 하는데 **그 파일이 없다.**
- state는 `--apply`가 성공해야 기록된다(코드상 write는 apply 경로에만). 그런데 `--apply`는 충돌에서 막힌다 → **state가 애초에 생긴 적이 없을 가능성**이 크다(닭-달걀).
- 게다가 state 기본 위치가 **ephemeral `.work`**라, 있었더라도 `.work` 정리 시 사라진다. (주의: 나는 오늘 회귀 작업 중 `.work`를 지웠다. 다만 state는 apply 성공 시에만 생기고 apply가 막혀 왔으므로, **실재하던 state를 내가 지웠을 가능성은 낮다** — 확증 불가, 정직히 기록.)
- 결과: **all-or-nothing.** 도구는 충돌이 하나라도 있으면 첫 mutation 이전에 전면 무쓰기. 그래서 **깨끗한 66개 pending export(오늘 새 문서 포함)도 683 충돌에 인질**로 잡혀 vault에 도달 못 한다.

## 3) 언제부터 막혔나 (타이밍)
`docs/source-manifest.json`·`tools/sync_obsidian.py` 마지막 변경 = **`d74e82e` 2026-09-09**(일주일 전, "final development guide and reverse ontology"). **오늘 코드 변경이 아니다** — 구조적·pre-existing. 24파일 manifest가 09-09 이후 1300+ 파일 증가를 반영 못 하고, state가 부재하면서 누적된 gap이 지금 683 충돌로 드러난 것.

## 도구 결함 수정 (진단화 — 이 커밋에 포함)
사용자 지시대로 충돌을 **예외가 아니라 진단 결과**로 만들었다(`tools/sync_obsidian.py`):
- 충돌은 이제 `ConflictsDetected`(진단용 예외)로 분리 — usage/config 오류의 ValueError와 구별.
- `main()`이 **사유별로 묶어 요약**(no-baseline/destination-edited/both-diverged 개수)하고, **전체 목록을 파일로 출력**(`.work/obsidian-sync-conflicts.json`, reasonCounts+목록), **종료 코드로 구분**: 0=clean, 2=usage(argparse), **3=충돌(판정 결과)**, 1=내부/설정 오류. 오늘 다른 도구들에 적용한 원칙과 동일.
- **vault 쓰기 안전 불변**: 충돌은 여전히 첫 mutation 이전에 발생 → `--check`·`--apply` 모두 fail-closed(무쓰기). `--check`(읽기 전용)로 검증: traceback 없이 `681 no-baseline / 2 both-diverged` 요약 + 파일 출력 + exit 3.

## 권고 (사용자 판단 후 실행 — 내가 --apply 안 함)
1. **baseline 확립**이 먼저다. 선택지:
   - (a) `docs/source-manifest.json`을 현재 1362파일 전체로 재생성하되, **각 파일의 known을 "vault의 현재 내용"이 아니라 "repo의 내용"으로 잡으면 안 된다**(그러면 vault 편집을 덮어씀). 안전하게는, vault와 repo가 이미 동일한 613파일은 `--adopt-identical`로 state에 흡수 → 그 613은 충돌에서 빠진다.
   - (b) state를 **비-ephemeral 경로**(예: repo 밖 사용자 지정, 또는 committed가 아닌 안정 위치)로 옮겨 apply 성공분이 유지되게 한다. `.work`는 부적절.
2. **683 충돌 개별 판단**: 681 no-baseline은 대부분 착시지만 일부가 진짜 vault 편집일 수 있으니, 사용자가 `.work/obsidian-sync-conflicts.json` 목록을 보고 **vault 편집분을 보존할지** 결정한 뒤 진행. **2 both-diverged(Overview.md·설계인덱스)는 반드시 수동 재조정**(vault 편집 가능성).
3. all-or-nothing 완화(선택): 충돌이 있어도 **깨끗한 신규 파일만 내보내는 모드**가 있으면 오늘 새 문서는 즉시 도달 가능 — 설계 결정(Codex/사용자).
**어느 것도 vault 편집분을 덮어쓸 수 있으므로, 원인이 분명해지고 사용자가 판단한 뒤에만 실제 sync를 한다. 덮어쓰기는 되돌릴 수 없다.**

## v1.1.0 — 사용자 승인 "613 동일분 흡수" 실행 결과 (2026-09-21)

사용자가 **repo·vault 내용이 이미 동일한 파일만 baseline 으로 흡수**(쓰기 없음)하는 방안을 승인해 실행했다. **vault 에는 어떤 쓰기도 하지 않았다.**

### 실행 전 검증 (지시대로 목록 먼저)
- **hash 동일 = 613** (양쪽 존재+해시 동일, 이중 검증, 불일치 0). both-diverged 2 건(`Overview.md`, `SaintVision INV 개발 설계 인덱스.md`)은 **대상에서 제외**(해시 동일 아님).
- **핵심 정정**: `identical ∩ conflicts = 0`(서로소 실측). **613 은 애초에 충돌이 아니라 이미-동일 버킷이다.** 따라서 흡수해도 683 충돌은 줄지 않는다. v1.0.0 및 이전 보고의 "동일분을 흡수하면 충돌에서 빠진다"는 **부정확했고 여기서 정정한다.**
- **조건 5 확인**: 도구 `--check --adopt-identical` 은 exit 3 이며 **state 파일조차 쓰지 않는다**(state write 는 `--apply` 경로에만). `--apply --adopt-identical` 은 충돌에서 먼저 중단. → **도구의 adopt-identical 은 충돌이 있으면 baseline 을 지속시키지 못한다**(adopt 에도 닭-달걀).

### 흡수 실행 + 검증
- 도구가 못 하므로 **`.work/obsidian-sync-state.json` state 파일을 직접 생성**(613 hash-동일 항목만; vault 아님, repo-side tracking JSON). `state['vault']` 가 대상 vault 로 해석돼 도구가 정상 수용(재-check 시 vault-mismatch 오류 없음).
- **vault 무변경 실측**: 흡수 전후 vault 파일 수 1307 동일·샘플 해시 불변 → **vault 쓰기 0**(조건 5 충족: baseline 기록만).
- **흡수 후 재-check: 683 충돌 그대로**(681 no-baseline + 2 both-diverged). 예측·실측 일치 — 흡수는 현재 충돌을 **줄이지 않았다**.

### state 파일 / 닭-달걀 / 위치
- **state 파일이 이제 생겼다**(613 baseline). 닭-달걀의 '달걀'은 마련됐으나 **도구만으로는 여전히 못 만든다**(조건 5) — 내가 우회 생성. **도구 결함(권고·Codex)**: adopt-identical 이 충돌 존재 시에도 hash-동일분 state 를 **충돌 abort 이전에 지속**시키게 고쳐야 도구만으로 baseline 을 세울 수 있다.
- **위치 = `.work/obsidian-sync-state.json`(휘발성)**. 다음 `.work` 정리 때 사라진다. **권고(실행 안 함)**: state 를 **비휘발성 경로**(repo 밖 사용자 지정 또는 안정 위치, `--state` 로 지정 가능)로 두어야 흡수가 지속된다. *위치 변경은 사용자 판단 영역이라 권고까지만.*

### 남은 상태 · apply 전망 (정직)
- **충돌 683 그대로**(681 no-baseline + 2 both-diverged), **67 pending**(오늘 새 문서 포함, vault 미도달 실측 확인).
- **apply 는 충돌 0 이어야 열린다.** 613 흡수는 충돌을 0 으로 못 만들었으므로 **apply 는 여전히 닫혀 있고 67 pending 은 여전히 막혀 있다. 이번 흡수는 unblock 전망을 개선하지 못했다.**
- **unblock 경로**: 681 no-baseline 은 파일별 판단(vault 편집 보존 vs repo 로 덮어쓰기), 2 both-diverged 는 수동 재조정 — 모두 사용자 판단 영역이며 이번에 손대지 않았다. 그 판단으로 충돌이 0 이 되어야 오늘 문서가 vault 에 도달한다.
