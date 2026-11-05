---
doc_id: "HISTORY-FLEET5-20261106-COMBINED-72028-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 결합 후보 72028cba 독립 결합 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T02:35:58+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "70f7502b"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "combined", "packet", "claude"]
---

# 결합 후보 72028 독립 검토

Orca task `task_ba0ee0a71106`, dispatch `ctx_53da843108e6`. 고정된 결합 후보 `72028cbac903c4415d9979f980a6e0f9948e914f`(tree `46df710b`, ci2 branch)와 비실행 packet을 판정한다. [[2026-11-06_01-10-31_KST_FLEET5_P0_T123_4f97_검토_Claude]]의 4f CODE ACCEPT와 3af 보고서는 맥락으로만 읽었다.

- **관측 시각:** 02:13:20~02:35:58 KST. 첫 fetch와 작성 직전의 shell `date` 출력이다. 마지막 CI 조회는 02:35:41이다.
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/combined-72028-review.json`

## 대상과 범위

- **사슬:** 72028(02:02:59) ← 0662b83f(3af 보고서 merge) ← 773e8523(4f를 local c913에 merge). 842, bd96, 0136, c913은 모두 조상이다. ci2 ref는 02:35에도 72028이다.
- **4f 대비 delta:** 파일 355개.
  - non-docs는 정확히 4개이며 모두 추가다: builder tool 하나와 새 test 3개(backend leaf runtime contract, build setup packet, setup packet).
  - docs는 350개 추가, 1개 수정이다. 수정된 것은 통합 Codex History이고, 끝에만 덧붙였다.
- **runtime:** deploy, services, src, contracts, migrations, `.github`, `tools/lan_pilot.py`는 4f와 diff가 없다.
- **f0af:** 조상이 아니다. settled launcher test는 4f blob과 같다. 그래서 L-T3-1·L-T3-2(test 전용 Low)는 72028에서 열려 있다. 4f CI는 옮겨 쓰지 않았다.
- **읽은 방식:** Git object만 detached scratch worktree로 꺼냈고, 끝나고 지웠다. mutant 뒤마다 porcelain 0을 확인했다. 작성자 packet은 읽기만 했고, 신뢰하지 않는 data로 다뤄 `-I`로 열었다.

## 계약 판독

| 항목 | 결과 |
|---|---|
| 11-field lifecycle | backend workflow(4f와 동일)가 dict 전체 일치, flag 7개의 `is True/False`, count 3개의 `type is int`를 요구한다. 새 test는 AST로 이 assert만 실행한다 |
| plan `4899f8c9…` | `executed`·`queryExecuted`는 false다. count는 모두 null이고 settlement는 UNKNOWN이다 |
| cohort·topology | 다섯 대를 함께 초기화한다. 독립 Linux 4대(PC1~4)와 CP 동거 PC5다. 공유 storage mount는 없다. 운영 binding 7개는 모두 null이다 |
| SF1 | 최신 nonce 서명 M2 v2 final floor, 바뀌지 않은 executable, 원래 byte에 묶인 CP receipt를 요구한다 |
| pin | archive byte로 다시 계산했다. module 5개와 launcher가 일치한다. LAN `2c626540`/`d8de953f`, prepare `60bebe11`/`a5695cab`도 일치한다 |
| Card150 | 0136·bd 대비 LAN 쌍만 실제 값으로 바뀌었다. 나머지 field는 그대로이고, 4f와 같다 |
| 리뷰 파일 8개 | c210, 8baa, 3154, 2736의 History·Evidence가 원래 review commit과 byte까지 같다 |

## carry-forward

- **B1:** builder는 120000과 160000을 출력 전에 거부한다. 내 disposable repo에서 `.work`가 생기지 않았고, link도 만들어지지 않았다. owner test는 120000만 다룬다(C-I3).
- **B2:** 엄격한 tri-state 형식이 유지된다. flag에 1, 1.0, "true", None을 넣거나 count에 4.0, True, False, "4"를 넣으면 모두 거부된다.
- **B3:** 범위가 정해진 attribute 16개는 glob이 아닌 literal이다. 모두 존재하고 `-text -whitespace`다.
- **보존:** 842, bd, c913, 0136 대비 삭제된 Evidence·History는 없다.
  - `.gitattributes`, `errors.md`, 통합 History는 byte prefix를 유지하며 끝에만 덧붙었다.
  - P0_v2 History는 선택된 4f blob과 같다.

## packet 독립 확인

- 파일 6개는 모두 일반 파일이고 symlink가 없다.
- 주장한 값이 모두 맞다:
  - archive 46895143 byte, `28a78428…`
  - inventory 4757개, `aa9667ce…`
  - packet 48259331 byte, `dedd5571…`
  - manifest `0d03e5c1…`
  - plan `4899f8c9…`. Git blob과 같다
- manifest, inventory, receipt는 builder의 canonical byte와 정확히 같다. sourceTree는 Git과 같다.
- inventory를 내 `ls-tree`와 비교했다. mode와 blob id가 모두 같고, 100644/100755 blob만 있다.
- archive member 4757개를 모두 다시 hash했다(git blob sha1, sha256, 길이). 불일치는 0이고, 이름 집합이 tree와 같다.
- packet은 STORED member 5개다. 경로 탈출이 없고 testzip이 깨끗하다. 각 member는 입력과 같다. NOTICE는 비실행이라고 밝힌다.

## 내 독립 확인 (main `.venv` 3.14.7 `-B`, Windows)

| probe | 결과 |
|---|---|
| 새 test 3개 | 104 passed, 0 skipped |
| builder 음성 | 출력 전에 거부: 160000, 120000, 축약·대문자·ref 이름·tree id. 기존 dir은 FileExistsError로 거부하고 이전 byte를 건드리지 않는다. plan 주장 6종, export-subst·export-ignore, archive 변조, host autocrlf=true도 거부한다. 이 경우들은 receipt가 없다 |
| workflow mutant | equality 제거, attest `is True` 제거, rolledBack `is False` 제거, bytecode·restart type 제거가 모두 KILLED다. cycles를 isinstance로 바꾼 mutant는 살아남지만 equality가 이미 bool을 막으므로 동치다 |
| SF1 mutant | executable 비교 제거와 match_floor 제거는 KILLED다. **현재 peer-policy 비교를 제거하면 살아남는다**: packet test와 기존 SF1 suite 42개 case 모두 통과한다(C-L2) |
| builder mutant | mode 검사 제거와 120000 허용 모두 KILLED다 |
| harness | 처음 두 번의 시도는 내 실수였다(basetemp 부모 없음, disposable repo의 전역 autocrlf). 고친 뒤 다시 돌렸고, 그 두 결과는 세지 않았다 |

## 발견

- **C-L1 (Low, 문서 provenance):** 결합 tree는 내 review 두 개의 *원래* byte를 들여왔다.
  - 45bc23cb의 History `75c852c1`과 Evidence `a5e3e70d`
  - c2102592의 History `6adbe00a`와 Evidence `473d7b25`
  - 이 두 review의 관측 시각은 나중에 내가 무효(지어낸 값)라고 정정했다. 정정 commit은 dcff213a(`fbd52a7e`, `3db3a5ef`)와 c2e63982(`9cd5446b`, `5e8f3bc4`)이고, 72028보다 먼저 공개됐다. 그런데 결합 tree에는 빠져 있다.
  - landing 전에 정정본을 함께 싣거나, superseded receipt를 남겨야 한다.
- **C-L2 (Low, test 강도):** SF1이 현재 `peer-policy.json`을 정착된 final과 비교하는데, 이 비교를 고정하는 test가 없다. packet test의 자체 harness가 같은 비교를 다시 하므로 production 검사가 빠져도 드러나지 않는다. runtime 변경은 없다.
- **C-I1 (Info):** backend contract test를 단독으로 돌리면 case 하나가 import 오류로 실패한다. `tools/`를 sys.path에 넣는 다른 module이 함께 수집되면 통과한다. 4f의 standalone result test에도 같은 기존 패턴이 있다.
- **C-I2 (Info):** plan 주장 거부와 archive 비교 거부는 archive를 쓴 뒤에 일어난다. 그래서 receipt 없는 partial dir이 남고, 같은 SHA로 재시도하면 막힌다. fail-closed다. B1 mode 거부는 요구대로 출력 전이다.
- **C-I3 (Info):** 160000 test가 없다. 선택 사항이다.

차단 발견은 없다.

## CI (API만, dispatch·cancel 없음)

| run | 결과 |
|---|---|
| Backend 42071344810 | success (job 3개) |
| Core 42071358669 | **진행 중**(02:35:41). s01은 success다. core job 안의 fixed native Go two-cycle proof step은 success이고, 전체 pytest와 go test는 아직 끝나지 않았다 |
| Frontend 42071370665 | success (job 2개) |
| Desktop 42071383997 | success |
| Docs 42071396345 | success |
| Portal 42071150605 | success (push) |
| Security 42071418886 | success |
| A11y 42071431273 | success |

job 12개 중 11개 success, 1개 진행 중이다. 모든 run의 head는 72028이다.

## 판정

| 구분 | 판정 |
|---|---|
| **결합 source·builder·plan `72028cba`** | **ACCEPT.** C-L1과 C-L2(Low)가 조건이다. 차단 발견은 없다 |
| **비실행 packet** | **ACCEPT.** 주장한 hash, 크기, 개수와 모든 Git blob을 독립적으로 재현했다 |
| 후보 CI | **아직 완료가 아니다.** Core가 진행 중이다. all-eight는 실제 terminal 결과를 확인한 뒤에만 주장할 수 있다 |
| f0af | 72028에 들어 있지 않다(동결됨). L-T3-1과 L-T3-2가 열려 있다 |
| HOLD | runtime, config, NodeOps, 발급, 배포, 통합 landing, physical, Obsidian. binding은 모두 null이다 |

## 다음 첫 행동과 담당

- **root:** Core 42071358669의 실제 terminal 결과를 확인한 뒤 all-eight를 판단한다. 결합 ACCEPT를 C-L1·C-L2 조건과 함께 기록한다.
- **Codex:** landing 전에 C-L1 정정본을 반영한다. C-L2 음성 test와 160000 test(C-I3)는 선택 사항이다.
- **Claude:** root가 맡기면 다음 delta를 검토한다.
