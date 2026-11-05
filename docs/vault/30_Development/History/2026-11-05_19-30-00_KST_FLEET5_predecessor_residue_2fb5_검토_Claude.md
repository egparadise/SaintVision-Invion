---
doc_id: "HISTORY-FLEET5-20261105-PREDECESSOR-RESIDUE-2FB5-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 Codex predecessor residue guard 6fce..2fb5 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T19:30:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "7fe0701f"
task_ids: ["FLEET5-CONSECUTIVE-LEAF-ROTATION-20261105"]
tags: ["fleet5", "independent-review", "leaf-rotation", "claude"]
---

# predecessor residue guard 6fce..2fb5 검토

Orca task `task_ad55d6c5ac02`, dispatch `ctx_e1eac667cf1d`. 앞선 판정 [[2026-11-05_19-05-00_KST_FLEET5_rotation_Low_closure_6fce_검토_Claude]]의 L1b를 root가 option (a)로 고치게 했고, 그 수정을 따로 판정한다. 앞선 `7fe0701f` 판정(안전성 ACCEPT, L1b 잔여)은 그대로 둔다.

- 대상: `agent/codex/fleet5-consecutive-leaf-rotation-20261105`의 `2fb52bbe5e500354b323eb8e46d5aa5066690d2d`(commit 1개, base `6fcedbbd`)
- 검토 시각: 19:10~19:30 KST
- 한 일: diff와 호출 순서 정독, hash 재계산, focused suite, 임시 probe 8개(guard 제거 mutant 포함) 실행. 임시 worktree는 제거했다.
- 하지 않은 일: physical·runtime·CA·private 접근. root integrator 작업공간 수정. 다른 agent 사용.
- 기계 판독 결과: `Evidence/fleet5-20261105-claude/predecessor-residue-2fb5-review.json`

## 무결성

- worker sha256 `497ac592f4a686bfeb63629ccc330800b136784b4dea5fd51638aed445907f06`. 일치하고, launcher pin도 같은 값이다.
- `tools/lan_pilot.py` sha256 `bce8aa36ffced4e73646e52483f5ad77dc3d9e42445ce543402834986c4a6077`, blob `3d205d52a377b52163240b824c1e6a092346e867`. 둘 다 일치한다.
- Card150을 59f와 비교하면 `tools/lan_pilot.py`의 hash 두 줄만 다르다. 59f DB preparation 값과 역사 field는 그대로다.
- non-docs 변경은 다섯이다.
  - worker: 새 `_require_settled_archive`와 `_finalized_successor`에서의 호출(12행)
  - `lan_pilot.py`: `_finalized_predecessor`에서의 호출(1행)
  - launcher repin
  - README 6행
  - test: 새 파일 1개와 기존 fixture에 `prepare` 노출 1행
- import와 runtime lock은 바뀌지 않았다.

## 순서와 의미

- **`_require_settled_archive`:** `.next`가 `exists()`이거나 `is_symlink()`이면 거부한다. 따라서 같은 bytes, 다른 bytes, 디렉터리, 깨진 symlink 모두 막는다. 아무것도 지우지 않는다.
- **Node:** install은 lock을 잡은 뒤 읽기만 하고(journal, bundle 검증) `_finalized_successor`로 간다.
  - `_finalized_successor`는 `_owned_directory`(이미 있는 디렉터리), rotationId 형식 검사, 그리고 **archive를 읽기 전에** `_require_settled_archive`를 한다.
  - 그래서 거부될 때 아무것도 바뀌지 않는다.
  - 만료 supersession 경로는 `restarted` phase만 받으므로 finalized predecessor를 우회하지 못한다.
- **CP:** `_finalized_predecessor`는 `_batch_material`(읽기)을 한 뒤, DB 연결과 archive 검증 **전에** `_require_settled_archive`를 한다.
  - prepare에는 세 경로가 있다.
    - 완성된 output이 있는 successor 경로
    - 같은 batch replay
    - 새로 만드는 경로. 이 경로는 `temporary.mkdir` 전에 확인한다.
  - 세 경로 모두 이 함수를 먼저 지나므로, 거부될 때 output이나 temp가 생기지 않는다.
  - offline recovery는 `staging`/`staged`만 받는다.
- **정리 경로는 그대로다.** Node finalize replay와 CP retire replay만 `_immutable(publish=True)`로, 모든 검증을 마친 뒤 같은 bytes·같은 소유자·regular 파일인 `.next`를 지운다. successor와 preflight는 지우지 않는다.

## 내 실행

**focused suite** (2fb5 detached worktree, main `.venv` Python 3.14.7, `-B`, cache 없음): `test_rotation_predecessor_residue`, `test_leaf_rotation_archive_residue`, `test_lan_leaf_rotation_consecutive`, `test_lan_leaf_rotation_batch_successor`, `test_lan_leaf_rotation`, `test_lan_leaf_rotation_standalone_runtime` 6개 파일이 **164 passed, 20 skipped**였다(57.3초). Codex 보고와 같다. skip은 Windows symlink와 POSIX 소유자·mode case다.

**probe** (임시 test, commit 안 함, sha256 `b69a4d74…`): 7 passed, 1 skipped.

| probe | 결과 |
|---|---|
| Node `.next`가 같은 bytes(hard link) → successor install | 거부. worker tree 전체가 그대로이고 archive inode도 같다 |
| 같은 경우, `_require_settled_archive`를 no-op으로 바꾼 **mutant** | successor가 **받아들여진다**. 이 guard가 유일한 방어선이고, probe가 그것을 잡는다 |
| Node `.next`가 다른 bytes, 또는 디렉터리 → successor | 거부. 예전 finalize replay도 거부(ValueError). 두 번 모두 아무것도 바뀌지 않는다 |
| Node `.next`가 깨진 symlink | Windows에서 symlink를 만들 수 없어 **skip**. code상 `is_symlink()`로 막힌다. Linux CI 몫이다 |
| Node 같은 bytes → 예전 finalize replay → successor | replay가 `.next`를 지우고 archive bytes와 inode는 그대로다. successor install과 finalize가 끝까지 된다 |
| CP 같은 bytes `.next` → successor prepare | 거부. state snapshot이 그대로이고 output과 temp가 없다. 같은 batch prepare replay도 거부된다. 같은 batch commit replay는 되고 `.next`를 남긴다(읽기 전용) |
| 같은 경우 → retire replay → successor | retire가 `.next`를 지우고 archive bytes와 inode는 그대로다. successor batch를 prepare, complete, retire까지 끝낸다 |
| CP `.next`가 다른 bytes, 또는 디렉터리 | successor prepare, 같은 batch prepare, retire replay가 모두 거부된다. 아무것도 바뀌지 않는다 |

## 판정

**`2fb52bbe` ACCEPT (source 안전성과 liveness). 앞선 L1b는 해결됐다.**

- 남은 잔여물이 있으면 successor가 시작되지 않는다. 따라서 정리 경로가 닫히는 순서가 더는 생기지 않는다.
- 같은 bytes의 잔여물은 검증된 predecessor replay로만 정리되고, 그 뒤 정상 cycle이 이어진다.
- 그 밖의 잔여물은 지우지 않고 막는다. README대로 별도 검토된 복구 대상이다.
- 앞선 계약도 그대로다: archive를 덮어쓰지 않고, 모든 member proof가 필요하며, receipt 원문 bytes를 유지하고, 고정 cohort 범위를 지킨다.

판정 범위와 참고:

- 이 판정은 source 판정이다. CI나 physical acceptance가 아니다.
- **같은 batch CP prepare replay도 잔여물이 있으면 막힌다.** 안전한 쪽이고, retire replay로 풀린다. Node `attest-finalized`는 읽기 전용이라 Node 잔여물이 있어도 된다. 둘 다 결함은 아니다.
- 정리하려면 retire에 원래 receipt bytes가 필요하다(L2). receipt를 잃으면 잔여물은 별도 검토된 복구가 필요하다. README에 적혀 있다.

## hosted (19:24:52 KST)

| run | head | 상태 |
|---|---|---|
| Docs 42009966309 | `2fb52bbe` | completed **success** |
| Core | `2fb52bbe` | branch run 목록에 **없음**. 세지 않는다 |
| Core 42006923070 | `6fcedbbd` | **in_progress**. 취소하거나 다시 실행하지 않았다 |

## 다음 첫 행동과 담당

- **root:** 이 ACCEPT를 integrator에 반영한다. 2fb5와 통합 후보의 Core를 실행하고, 6fce Core의 최종 결과를 기록한다. 그다음 통합 후보 검토와 CI 8건을 준비한다.
- **Codex:** 추가할 일은 없다.
- **Claude:** 통합 후보가 오면 검토한다.
