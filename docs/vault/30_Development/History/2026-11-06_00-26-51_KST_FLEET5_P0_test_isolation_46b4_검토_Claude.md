---
doc_id: "HISTORY-FLEET5-20261106-P0-TEST-ISOLATION-46B4-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 P0 standalone test isolation 46b4573f 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T00:26:51+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "8baaa6b5"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "p0", "test-isolation", "claude"]
---

# P0 standalone test isolation 46b4 검토

Orca task `task_7e9c7ba49eab`, dispatch `ctx_a22db97db992`. [[2026-11-06_00-10-02_KST_FLEET5_P0_code_4a92_검토_Claude]]에서 낸 CI-B1을 닫는 test 전용 delta `46b4573f`만 판정한다.

- 4a code 판정과 후보 전체의 판정은 바꾸지 않는다.
- **관측 시각:** 00:20:16~00:26:51 KST. 첫 fetch와, 작성 전 마지막 CI 확인의 shell `date` 출력이다.
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/p0-test-isolation-46b4-review.json`

## 대상과 범위

- **대상:** `46b4573f2b333dfbb3d37f695c19df9ae805a364`. 부모는 `50000697`이다.
  - 파일 34개, +16413/−13. non-docs는 `tests/test_lan_leaf_rotation_standalone_runtime.py` 하나다(49줄).
- **4a 대비 non-docs:** `50000697`의 test 파일 3개와 이 test 하나뿐이다.
- **4a와 tree가 같은 것:** `deploy`, `tools`, `.github`, `contracts`, 검토 대상 branch의 proof 디렉터리, `src`, `migrations`
- **`services` 차이:** `peer_floor_canonical_test.go` 하나다(`50000697`에서 온 것).
- **SHA256이 4a와 같은 파일:**
  - worker module 5개, launcher
  - fixed probe
  - `backend.yml`, `core.yml`
  - `peer_phase_unit_fixtures.py`
- worker module digest 5개는 launcher의 `WORKER_MODULES` pin과 같다. **runtime 변경은 없다.**
- **읽은 방식:** Git object만 scratch worktree에 detached로 꺼냈다. 작성자 checkout은 건드리지 않았다. red control로 바꾼 것은 모두 되돌렸고, porcelain 0개를 확인했다.

## diff 판독

- 대상 test는 `worker_fails` × `helper_entry_state`(original, absent, blocked-import)로 나뉜 6개 case다.
- **저장:** 의존성 3개와 `WORKER_MODULES`의 helper stem 5개를 저장한다. 없는 상태는 `None`과 다른 sentinel로 구분한다.
- **복원:** 성공과 실패 모두 `finally`에서 `sys.path`, `sys.argv`, 저장한 module 전부를 복원한다.
- **복원 뒤 확인:** module identity, path, argv
- **기존 assert는 그대로다:**
  - 성공 case: `first == second == third`, counter 2
  - 실패 case: 설치 결과가 같은지, counter 1
  - bytecode가 없는지, `dont_write_bytecode`
- freshness 한계, skip, runtime은 바꾸지 않았다. production runner는 설계대로 helper를 계속 뺀다.

## 내 독립 probe (main `.venv` 3.14.7 `-B`, Windows)

| probe | 결과 |
|---|---|
| O1: normal → standalone → residue | **78 passed**, 10 skipped. 4a에서는 같은 순서로 5 failed였다 |
| O2: standalone → normal → residue | 78 passed, 10 skipped |
| O3: `test_fleet5_*` + `test_lan_*` + residue | **282 passed**, 23 skipped. 4a에서는 5 failed, 272 passed였다 |
| O4: standalone만 | 37 passed, 6 skipped |
| R1: 이 test만 `50000697`의 판으로 되돌림 | O1 순서에서 **5 failed**. 수정이 실패의 원인을 고친다는 증거다 |
| R2: 저장·확인 집합을 의존성 3개로 줄임 | 이 test 혼자서는 37 passed(못 잡는다). O1 순서에서는 5 failed |
| R2b: `finally`에서 helper 복원만 건너뜀 | 이 test 혼자서 2 failed(blocked-import case). O1 순서에서 8 failed |
| R3: argv 복원 제거 | 6 failed |
| R4: blocked-import의 `None`을 없음으로 취급 | 2 failed |
| 고정 runtime module 누출 | standalone 뒤 pytest 임시 경로에서 온 module은 없다(`[]`) |

**참고 (I-46-1, Info):** 이 test의 identity assert는 복원하는 바로 그 집합을 순회한다. 그래서 그 집합에서 helper를 빼는 변경(R2)은 이 파일만 돌리면 통과하고, 다른 파일과 함께 순서대로 돌릴 때만 잡힌다. 기대하는 stem 5개를 명시해 두면 이 test 혼자서도 잡을 수 있다. CI-B1을 닫는 데 필요한 조건은 아니다.

## CI

| run | 상태 |
|---|---|
| Backend 46b 42053207929 | 진행 중(00:26:51). 주장하지 않는다 |
| Docs 46b 42053214575 | success. API 목록으로만 봤고 log는 보지 않았다 |
| Core 4a 42047390811 | **FAILURE.** core pytest에서 5 failed, 9075 passed. 같은 residue/predecessor 5개다. 원래 실패로 보존한다 |
| Backend 4a 42047403498 | FAILURE(3.12, 3.14). 보존한다 |

내가 Core나 Backend를 새로 돌리지 않았다. 작업하는 동안 T1~T3 수정 SHA는 공개되지 않았고(마지막으로 본 것은 `46b4573f`), 그래서 포함하지 않았다.

## 판정

| 구분 | 판정 |
|---|---|
| **CI-B1 source 수정 `46b4573f`** | **ACCEPT (test 전용).** 8baaa6b5에서 찾은 원인을 고쳤다. 성공과 실패 모두에서 helper 5개의 identity, 의존성, path, argv를 복원한다. R1로 이 수정이 원인을 고친다는 것을 확인했다. runtime, workflow, proof, freshness 변경은 없다 |
| CI-B1 이후 CI | 주장하지 않는다. Backend 42053207929가 진행 중이다 |
| code `4a928310` | 그대로 **NOT ACCEPTED**. T1 mutant, T2, T3이 열려 있고, 4a Core와 Backend RED는 보존한다 |
| 후보 전체 | **NOT ACCEPTED.** T1~T3 delta, `50000697`이나 그 후속의 실제 Go canonical 결과, full CI가 필요하다 |
| runtime·physical | 수락하지 않는다. after-stop/no-copy와 `restarted`는 계속 막혀 있다(guarded BLOCK). SF1의 기본 고정 launcher 경로는 verifier를 바꿔 끼운 test와 구분된다 |

## 다음 첫 행동과 담당

- **root:** 46b Backend 42053207929의 최종 결과를 반영한다. 4a와 후보 전체는 NOT ACCEPTED로 둔다.
- **`ctx_6f0f8253b8a7`:** T1~T3 음성 test와 mutant를 잡는 수정을 정확한 SHA로 낸다.
- **Claude:** root가 맡기면 고친 전체 delta를 검토한다.
