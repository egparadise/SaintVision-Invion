---
doc_id: "HISTORY-FLEET5-20261106-TEST-FOLLOWUP-E50C-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 isolated test followup e50c1482 독립 검토"
version: "1.0.1"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T04:13:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "e50c1482"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "test-only", "claude"]
---

# Isolated test followup e50c 검토

Orca task `task_6baccbb465af`, dispatch `ctx_0e847a7f4af8`. Codex의 [[2026-11-06_FLEET5_test_followup_Codex]]가 만든 TEST-ONLY delta를 독립적으로 판정한다.

- **판정 범위:** test 변경만 판정한다. code, runtime, physical, whole-product 수락이 아니다. f0af에 대한 이전 70f7502b ACCEPT를 이 판정에 빌려 쓰지 않았다.
- **관측 시각:** 04:02:26~04:12:10 KST. 검토 첫 명령부터 작성 직전 확인까지의 shell `date` 출력이다.
- **기계 판독 결과:** `Evidence/fleet5-test-followup-20261106-claude/e50c-review.json`
- **원시 출력:** `Evidence/fleet5-test-followup-20261106-claude/e50c-review-raw.txt`
  - LF로 저장했다. private scratch 경로 prefix만 `<private-scratch>`로 바꿨다.
- 진행판, registry, shared board, Obsidian apply, landing은 고치지 않았다.

## 대상과 범위

- **대상:** `e50c148287779add421265868ef16909ed984650`. 부모는 `a52782e8`이고, 조상 관계를 확인했다.
- **docs가 아닌 변경:** 정확히 test 파일 4개이고 모두 M이다.
  - [tests/test_backend_leaf_runtime_contract.py](https://github.com/egparadise/SaintVision-Invion/blob/e50c148287779add421265868ef16909ed984650/tests/test_backend_leaf_runtime_contract.py)
  - [tests/test_build_fleet5_setup_packet.py](https://github.com/egparadise/SaintVision-Invion/blob/e50c148287779add421265868ef16909ed984650/tests/test_build_fleet5_setup_packet.py)
  - [tests/test_fleet5_plain_reentry.py](https://github.com/egparadise/SaintVision-Invion/blob/e50c148287779add421265868ef16909ed984650/tests/test_fleet5_plain_reentry.py)
  - [tests/test_fleet5_settled_launcher.py](https://github.com/egparadise/SaintVision-Invion/blob/e50c148287779add421265868ef16909ed984650/tests/test_fleet5_settled_launcher.py)
- **72028과 비교:** docs·tests 밖에서 달라진 경로는 0이다. production SF1 source blob은 e50c와 72028에서 같은 `b0d01a5f`다. SHA256은 `bf3754a2…46e5`다.
- **owner static closure 대조:** 네 파일의 git blob과 LF SHA256이 owner의 `followup-static-closure.json`과 모두 같다.
- **launcher 파일:** blob `2b99768f5dac8396dd034ab44140fc11643c2456`이 f0af의 blob과 같다.
- **hosted run:** GitHub API로 읽기만 했다.
  - Docs 42084668698과 Portal 42084627956은 head e50c에서 모든 job이 success다.
  - C-L1 Docs 42084583685(`97edf991`)는 별도 범위다.
  - 위 hosted run은 네 test 파일을 실행하지 않는다. e50c에서 Backend, Core, all8은 실행되지 않았고, 실행됐다고 주장하지도 않는다.
- **실행 환경:** e50c를 private scratch의 일회용 detached worktree로 꺼내 실행했다.
  - Python 3.14.7, win32이다. Python process는 하나씩 순서대로 돌렸다.
  - 다른 process는 죽이지 않았다.

## 독립 확인

- **C-I1:**
  - 새 process에서 이 module만 돌리면 72 pass, 0 skip, exit 0이다.
  - path probe plugin으로 확인했다. 수집 후와 종료 시 모두 `tools/` 디렉터리는 sys.path에 없다. bare module도 load되지 않았다.
  - module은 repo root 기준 `tools.` namespace로 풀린다. hosted `python -m pytest` 호출 방식과 같다.
  - 부모의 import만 되돌려 같은 방식으로 돌리면 1 fail, ModuleNotFoundError다. 되돌린 파일은 바로 복원했다.
- **B1(Gitlink 160000):**
  - fixture는 실제 commit object와 160000 index entry다. submodule은 clone하지 않는다.
  - test가 ls-tree kind `commit`과 cat-file type을 확인한다. 출력 전에 거부되고 `.work`가 생기지 않는다.
  - 160000을 허용하는 mutant에서는 이 test가 실패한다. 뒤쪽 archive 검사가 다른 문구로 raise하므로 정확한 `160000` match에 걸린다.
- **owning suite:**
  - 각각 따로 돌리면 packet 4, SF1 19, launcher 11, 합계 34가 pass다.
  - 네 파일을 역순으로 한 process에서 돌리면 106 pass, 0 skip이다.
- **SF1 peer-policy guard:**
  - 정확히 `peer-policy.json` 비교 항 하나만 지운 mutant를 만들었다. 새 owning test는 `DID NOT RAISE ValueError`로 실패한다.
  - plain_reentry suite 전체에서 이 mutant를 잡는 test는 새 test 하나뿐이다.
  - 같은 drift를 observation을 고정하지 않고 넣으면 fixture의 floor 재검사가 다른 문구로 먼저 거부한다. 이 대조는 임시 파일로 돌리고 지웠다.
  - 따라서 유효한 서명 final observation을 고정해야 owning guard만 따로 검증된다. `_floor`의 서명과 match 검사, archive 검사는 그대로 동작한다.
- **격리:**
  - 새 상태는 모두 function-scope monkeypatch와 tmp_path로 만든다.
  - delta 안에 sys.modules나 전역 sys.path 수정은 없다.
- **assertion 약화:** 찾지 못했다.
  - 120000 확인은 substring 비교에서 정확한 mode, kind, type 비교로 강해졌다.
  - launcher의 oversize와 duplicate 입력은 이제 유효한 JSON이다. byte bound와 duplicate 규칙만 그 입력을 거부할 수 있다.
- **복원:** 모든 mutant는 scratch checkout 안에서만 만들었다. 끝난 뒤 SHA256 복원과 `git status` clean을 확인했다.

## 판정

**ACCEPT** (TEST-ONLY delta e50c1482). 이 delta를 막는 finding은 없다.

### 별도 범위의 새 관측

- **R-L1 (Low, 비차단):** 같은 SF1 guard에 `node-cert.pem` 비교 항과 `ca.pem` 비교 항이 있다.
  - 각 항을 False로 바꾼 mutant를 따로 돌렸다. 대상은 `verify_settled`, `verify-settled`, `current credentials differ`를 참조하는 모든 test 파일이다.
  - 두 mutant 모두 72 pass, 5 skip으로 살아남았다. skip은 opt-in Linux Docker test다.
  - production guard는 있고 바뀌지 않았다. e50c의 C-L2 peer-policy 범위 밖의 test 공백이다. 다음 test followup에 넣을지는 Root가 정한다.

### 남은 Info

- **R-I1:** 106 pass는 owner와 reviewer 모두 Windows Python 3.14.7 local 결과다. Linux hosted pytest coverage는 Root가 고르는 final source CI에서 확보해야 한다.
- **R-I2:** launcher의 fault case는 넓은 exception tuple을 받는다. 진단 문구를 고정하지 않는다. 파일 byte는 f0af에서 승인된 그대로이고, 이번에 launcher mutant는 다시 돌리지 않았다.
- **R-I3:** owner가 미룬 C-I2(partial-output fail-closed)와 선택 항목 exact65536은 Info로 남는다. 이번 검토 대상이 아니다.

## 다음

다음 owner는 Root다. Root가 최종 frozen test source를 고른 뒤에만 새 source CI나 archive를 만든다. Claude는 새 all8, archive, runtime 변경을 만들지 않았다.


Root aggregate citation adaptation only: this coordinator branch still contains old59f product code. Four e50-only test citations now link to verified immutable e50 Git blobs; original reviewer source/report and semantic verdict remain unchanged. No code import or ratchet baseline raise.
