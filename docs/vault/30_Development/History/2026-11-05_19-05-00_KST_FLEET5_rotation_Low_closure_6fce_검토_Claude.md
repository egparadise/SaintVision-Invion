---
doc_id: "HISTORY-FLEET5-20261105-ROTATION-LOW-CLOSURE-6FCE-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 Codex rotation Low closure 8b53..6fce 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T19:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "b852f9e0"
task_ids: ["FLEET5-CONSECUTIVE-LEAF-ROTATION-20261105"]
tags: ["fleet5", "independent-review", "leaf-rotation", "claude"]
---

# rotation Low closure 8b53..6fce 검토

Orca task `task_da78a1ae6d7b`, dispatch `ctx_607df2b15a4b`. 앞선 판정 [[2026-11-05_18-40-00_KST_FLEET5_연속_leaf_rotation_8b53_검토_Claude]]은 `8b53`만 다뤘다. 이 기록은 그 위의 delta를 따로 판정한다.

- 대상: `agent/codex/fleet5-consecutive-leaf-rotation-20261105`의 `6fcedbbdba24e43e3917adb07f080a683dedfefe`(commit 1개, base `8b53fbfe`)
- 검토 시각: 18:45~19:05 KST
- 한 일: diff 정독, hash 재계산, Card150 구조 비교(59f 대비), focused suite 실행, 임시 probe 6개 실행. 임시 worktree는 제거했다.
- 하지 않은 일: physical·private runtime, CA, 예전 r5, 원래 48 task 변경. 구현 수정. 다른 agent 사용.
- 기계 판독 결과: `Evidence/fleet5-20261105-claude/rotation-low-closure-6fce-review.json`

## 무결성

- worker sha256 `9219cd817778278cb5e92ef4d4ed08b666d6dfe7ab727ee9e660cf1d8a0ca68b`. 일치하고, launcher pin도 같은 값이다.
- `tools/lan_pilot.py` sha256 `e1437600dad2231f40b24cb44d7c3edf1c147e42bc68d39dad2ebb0c9b51f574`, blob `111922523062608efeb02f81de82f0b41a8189fe`. 둘 다 일치한다.
- Card150을 59f와 구조적으로 비교하면, 다른 경로는 `tools/lan_pilot.py`의 hash 두 field뿐이다. preparation 쌍(59f 값), `observedAt`, commit field와 다른 hash는 그대로다.
- non-docs 변경은 넷이다.
  - worker `_immutable` 15행
  - `lan_pilot.py` 3행(terminal retire replay에서 같은 publisher 호출)
  - README 20행
  - 새 test 파일
- import와 runtime lock은 바뀌지 않았다.

## 변경 의미

- **`_immutable`**:
  - archive가 이미 있으면 먼저 archive가 정확히 같은 bytes인지 확인한다(`_history_bytes`: lstat 기준 regular, POSIX 소유자와 mode).
  - `.next`가 있으면 같은 검사를 따로 통과하고 bytes도 같아야 한다.
  - `publish=True`일 때만 그 `.next`를 unlink하고 디렉터리를 fsync한다.
  - 같지 않거나, 비었거나, 일부만 있거나, 소유자가 다르거나, symlink인 `.next`는 거부하고 그대로 둔다.
  - archive의 내용과 inode는 그대로다.
- **호출 시점이 맞다.**
  - Node finalize는 `publish=False` 사전 확인 뒤, 증거 서명 검증·policy·restart를 마치고 나서 `publish=True`를 부른다.
  - CP terminal retire replay는 archive 검증, 모든 proof 검증, 현재 authority·DB channel 확인, receipt bytes 일치를 모두 마친 뒤에야 부른다.
  - 읽기 전용 경로(`_verify_batch_archive`, 같은 batch prepare/commit replay)는 지우지 않는다.
- **L2:** 원래 bytes를 유지하고, README가 재직렬화 복구를 지원하지 않는다고 명시한다. root의 결정과 맞다.
- **L3:** README가 다음을 명시한다.
  - 같은 member 집합, tenant, epoch, CA, 주소, Node/CP key가 필요하다.
  - 추가, 제거, 폐기, re-IP, authority나 key 변경은 이 경로를 막는다.
  - 새 5대는 다섯 대가 모두 준비됐을 때 한 번에 init한다.
  - 분류기는 phase 문자열만 믿지 말고 서명된 archive와 모든 proof를 검증해야 한다.

## 내 실행

**focused suite** (6fce detached worktree, main `.venv` Python 3.14.7, `-B`, cache 없음): `test_leaf_rotation_archive_residue`, `test_lan_leaf_rotation_consecutive`, `test_lan_leaf_rotation_batch_successor`, `test_lan_leaf_rotation`, `test_lan_leaf_rotation_standalone_runtime` 5개 파일이 **162 passed, 20 skipped**였다(54.9초). Codex의 162/18과 pass 수가 같다.

skip은 모두 Windows symlink와 POSIX 소유자·mode case다. 그래서 symlink, 다른 소유자, group-writable `.next` 거부는 **내가 실행하지 못했다.** code만 읽었고, Linux CI에서만 증명된다.

**probe** (임시 test, commit 안 함, sha256 `9d92ad63…`):

| probe | 결과 |
|---|---|
| Q1 Node archive 옆에 같은 inode의 `.next`(실제 link/unlink 사이 crash 모양) → finalize replay | `.next` 제거. archive bytes와 inode는 그대로 |
| Q2 Node `.next` 마지막 1byte가 다름 → finalize replay | `Finalized rotation archive staging collision`. worker 전체 snapshot 불변 |
| Q5 CP terminal archive 옆 `.next` → 같은 batch prepare/commit replay | `.next`가 **남는다**(읽기 전용, 맞음). 그다음 retire replay → 제거 |
| Q8 CP `.next`가 있는 상태에서 proof 1개의 bytes가 다른 retire replay | `Finalized batch replay proof bytes differ`. state snapshot 불변, `.next` 유지(검증 전에는 지우지 않음) |
| Q4 Node predecessor archive에 `.next`가 있는데 successor install | **받아들여진다.** 그 뒤 예전 rotation의 finalize replay는 `Current Node leaf does not match the rotation base`로 거부되고, `.next`는 successor finalize 뒤에도 남는다 |
| Q6 CP predecessor archive에 `.next`가 있는데 successor prepare | **받아들여진다.** 그 뒤 예전 batch retire는 거부되고, `.next`는 남는다 |

## 발견

- **L1b (Low, liveness 문제이고 안전 문제는 아님): crash 뒤 successor를 먼저 시작하면 잔여물이 고아로 남는다.**
  - L1 수정은 "successor 전에 finalize 또는 retire를 replay한다"는 순서일 때만 잔여물을 치운다.
  - Node `_finalized_successor`와 CP `_finalized_predecessor`는 predecessor archive 옆의 같은 bytes `.next`를 받아들이고 진행한다(Q4, Q6).
  - 그 순간부터 정리 경로(예전 rotation finalize, 예전 batch retire)는 영구히 거부된다. 그래서 그 `.next`는 지울 수 있는 검증 경로가 없는 고아가 된다. 손으로 지우는 것은 이 계약 밖이다.
  - 그러면 분류기 규칙(`.next`는 orphan → BLOCK)이 계속 막는다.
  - 고치는 방법은 둘 중 하나다.
    - **(a) 권고:** successor 경로가 predecessor archive의 `.next`를 보면 `"replay finalize/retire first"`로 거부한다. 안전한 쪽으로 실패하고 변경이 가장 작다.
    - **(b)** 두 함수는 이미 모든 검증을 마친 시점이므로, 같은 `_immutable(publish=True)`를 불러 거기서 정리한다.
  - README의 crash 문단에 "successor 전에 replay"를 넣는 것만으로는 사람의 순서 실수를 막지 못한다.
- 그 밖의 요구는 모두 충족한다.
  - 같지 않거나, 비었거나, 일부만 있거나, symlink이거나, 소유자가 다른 잔여물은 거부되고 보존된다(소유자와 symlink는 code와 Linux 전용 test).
  - 읽기 전용 preflight는 지우지 않는다.
  - 검증 전에는 지우지 않는다.
  - archive를 덮어쓰지 않는다.
  - 8b에서 남은 legacy terminal 잔여물도 retire replay로 정리된다(Codex test `test_verified_terminal_cp_replay_cleans_equal_residue_from_prior_source`, 내 Q5).

## hosted (18:59 KST)

| run | head | 상태 |
|---|---|---|
| Docs 42006174091 | `6fcedbbd` | completed **success** |
| Core | `6fcedbbd` | 이 시각 branch run 목록에 **없음**(미실행). 성공으로 세지 않는다 |
| 8b Core 42001883513 | `8b53fbfe` | completed **success**. 앞선 b852 판정의 pending이 풀렸다. 6fce의 증거는 아니다 |

## 판정

**`6fcedbbd` delta ACCEPT (source, 안전성).**

- L1 정리는 모든 검증 뒤에, 같은 bytes·같은 소유자·regular 파일인 `.next`에만 일어난다. 그 밖의 경우는 모두 안전하게 실패한다.
- L2와 L3 문서는 정확하다.
- Card150은 현재 lan_pilot 쌍만 바뀌었다.

단, **L1b**가 남아 있다. 그래서 L1의 "분류기를 막는 잔여물이 생기지 않는다"는 목표는 crash 뒤 replay를 먼저 하는 순서에서만 성립한다. integrator가 source를 pin하기 전에 (a) 또는 (b)를 넣기를 권고한다. 6fce의 Core는 아직 없고, symlink·소유자 case는 Linux CI에서 확인해야 한다.

## 다음 첫 행동과 담당

- **root:** 6fce의 exact Core를 실행하고 결과를 확인한다. L1b를 반영할지 정한다(권고는 (a)). integrator pin은 L1b 처리 뒤에 만든다.
- **Codex:** L1b (a) 또는 (b)를 고치고 test 2개(Node, CP successor-with-residue)를 추가한다.
- **Claude:** L1b delta가 오면 검토한다.
