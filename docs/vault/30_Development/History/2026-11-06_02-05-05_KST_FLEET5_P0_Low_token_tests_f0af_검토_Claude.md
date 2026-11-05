---
doc_id: "HISTORY-FLEET5-20261106-P0-LOW-TOKEN-TESTS-F0AF-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 P0 Low token test delta f0af3077 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T02:05:05+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "b47371c3"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "p0", "test-strength", "claude"]
---

# P0 Low token test delta f0af 검토

Orca task `task_bd777860781e`, dispatch `ctx_023fb7a3cc28`. owner 요청은 `msg_f6ae2eae8f24`다. [[2026-11-06_01-10-31_KST_FLEET5_P0_T123_4f97_검토_Claude]]에서 낸 L-T3-1과 L-T3-2를 고친 test 전용 delta를 판정한다.

- **관측 시각:** 01:59:23~02:05:05 KST. 첫 fetch와, scratch worktree를 지운 뒤의 shell `date` 출력이다.
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/p0-low-token-tests-f0af-review.json`

## 대상과 범위

- **대상:** `f0af307705b4923ebc3e231db5238af4c70aa389`. 부모는 `4f97ba71`이다.
  - 파일 15개, +232/−2.
  - non-docs는 검토 대상 branch의 settled launcher test 파일 하나다(+3/−2).
- **runtime:** deploy, services, tools, `.github`, src, contracts, migrations는 4f와 diff가 없다. worker module 5개와 launcher의 SHA256도 그대로다.
- **맥락으로만 읽은 것:** source 4f(2736aec1에서 ACCEPT), 3af3334e 보고서(docs 전용, 부모 4f97)
- **읽은 방식:** Git object만 scratch worktree에 detached로 꺼냈고, 끝나고 지웠다. red control 뒤마다 porcelain 0을 확인했다.

## diff 판독

- **oversize:** 유효한 token 앞에 공백 65537 byte를 붙인다.
- **duplicate:** 정확한 유효 token 끝에 `,"verified":true`를 하나 더 넣는다.
- **유효성 assert:** 두 경우 모두 `json.loads(raw)==value`를 먼저 assert한다. 일반 parser라면 받아들일 입력이라는 뜻이다.
- **나머지는 그대로다:** 다른 case, argv/kwargs 기대값, 호출 횟수, snapshot, lock assert

## 내 독립 확인 (main `.venv` 3.14.7 `-B`, Windows)

| probe | 결과 |
|---|---|
| 대상 파일 | 11 passed, 0 skipped |
| 내 T3 mutant 7개 | 모두 KILLED. 4f에서 살아남던 두 개도 잡힌다: 64 KiB 한계 제거는 `[oversize]`만, `json.loads` 교체는 `[duplicate]`만 실패한다 |
| 실패 이유 | 두 mutant 모두 "Invalid default verifier dispatch admitted an operation"으로 실패한다. guard가 동작을 허용했다는 뜻이고, error나 skip이 아니다 |
| red control | 4f 판 test로 되돌리면 두 mutant가 다시 살아남는다(각각 11 passed). 바뀐 세 줄이 원인이다 |
| payload | oversize는 65939 byte로 한계를 넘는다. `json.loads`와 실제 `strict_json`이 둘 다 받으므로 byte 한계만 이것을 거부한다. duplicate는 `json.loads`로는 token과 같고, 실제 `strict_json`은 "Duplicate private protocol field"로 거부한다 |
| 경계 | 한계를 131072로 늘리면 KILLED다. `< 65536`이나 `<= 4096`으로 줄이면 살아남는다(I-LT-1) |
| owner evidence | log 3개의 SHA256을 commit된 byte로 다시 계산해 맞췄다. production hash 3개는 tree와 같다. baseline은 10, 각 mutant는 정확히 case 하나만 실패하고 error·skip은 0이다 |

**I-LT-1 (Info):** 정확히 65536 byte인 유효 token을 받는 case가 없다. 그래서 한계를 지나치게 좁히는 변경이 살아남는다. 이 경우는 fail-closed라 가용성만의 문제다. 선택 사항이다.

## CI

- **f0af Docs 42068760043:** success. API로만 봤다.
- **Core·Backend:** f0af에서는 돈 적이 없다. 4f의 Core 42058859797과 Backend 42058865926을 이 patch에 옮겨 붙이지 않는다. 긴 Core를 다시 돌리지 않았다. 최종 결합 CI가 이 patch를 거둬야 한다.

## 판정

| 구분 | 판정 |
|---|---|
| **source 검토 `f0af3077`** | **ACCEPT (test 전용).** L-T3-1과 L-T3-2가 닫혔다. runtime 변경은 없고, 완화된 assert도 없다 |
| patch CI | Docs success뿐이다. Core와 Backend는 주장하지 않는다 |
| 통합 | 4f source ACCEPT(2736aec1)는 그대로이고 넓히지 않는다. 등록, helper, runtime, 장비, physical은 HOLD다 |

## 다음 첫 행동과 담당

- **root:** f0af test 전용 ACCEPT를 기록한다. 전체 통합을 수락하기 전에 최종 결합 CI에 f0af를 포함한다.
- **Codex:** 선택 사항이다. 경계값 65536 byte를 받는 case를 추가한다(I-LT-1).
- **Claude:** root가 맡기면 다음 delta를 검토한다.
