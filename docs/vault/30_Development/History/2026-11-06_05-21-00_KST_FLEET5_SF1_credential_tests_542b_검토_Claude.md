---
doc_id: "HISTORY-FLEET5-20261106-SF1-CREDENTIAL-TESTS-542B-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 SF1 credential test 542b48f9 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T05:21:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "542b48f9"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "test-only", "claude"]
---

# SF1 credential test 542b 검토

Orca task `task_9cd71aa339ff`, dispatch `ctx_8fa6addadbda`. [[2026-11-06_04-13-00_KST_FLEET5_test_followup_e50c_검토_Claude]]가 남긴 R-L1에 대한 Codex의 [[2026-11-06_FLEET5_SF1_credential_tests_Codex]] delta를 판정한다.

- **판정 범위:** TEST-ONLY 판정이다. code, runtime, physical, whole-product 수락이 아니다. frozen e50c 선택은 바꾸지 않는다.
- **관측 시각:** 05:19:15~05:20:16 KST. raw 재실행 시작부터 evidence 저장까지의 shell `date` 출력이다.
- **기계 판독 결과:** `Evidence/fleet5-sf1-credential-tests-20261106-claude/542b-review.json`
- **원시 출력:** `Evidence/fleet5-sf1-credential-tests-20261106-claude/542b-review-raw.txt`
  - LF로 저장했다. private scratch 경로 prefix만 `<private-scratch>`로 바꿨다.
  - context probe의 원문은 `542b-context-probe.py.txt`에 있다.
- 진행판, registry, shared board, Obsidian apply는 고치지 않았다.

## 대상

- **대상:** `542b48f996344563424228fb9fc454f5970bbd18`. 부모는 docs-only `8624c3ee`이고, e50c가 조상이다.
- **docs가 아닌 변경:** 부모 대비, e50c 대비 모두 `tests/test_fleet5_sf1_current_credentials.py` 추가 하나뿐이다.
- **production SF1:** SHA256 `bf3754a2…46e5`, blob `b0d01a5f`로 바뀌지 않았다.
- **Docs 42096385358:** head가 정확히 542b이고 docs job이 success다. 이 run은 pytest를 실행하지 않는다. 새 파일의 Linux, Core, Backend 실행은 NOT_RUN이다.

## 코드 확인

- **실제 경로:** test는 production `plain.verify_settled`를 그대로 부른다.
  - monkeypatch는 `rotation.validate_bundle` 하나뿐이다. 이 module은 `plain._legacy()`가 돌려주는 module과 같다.
  - wrapper는 archived public material로 원래 함수를 부른다. 결과는 그대로 돌려주고, 그 뒤에 tmp_path fixture credential에 1 byte만 덧붙인다.
  - 검사 대상인 비교 항은 production 줄 그대로다. mock된 비교가 아니다.
- **그대로 동작하는 검사:**
  - `validate_bundle`의 서명과 CA pin
  - `_verify_record`
  - `_commit`의 control 서명
  - `_finalized_evidence` archive binding
  - `_floor`의 서명과 match
  - `validate_policy`, `credential_archive`
  - journal, archive, target 재확인
- **byte만 바뀐 drift:** `_certificates`가 같다. 그래서 DER 수준 검사나 floor 검사로는 잡히지 않는다.
- **mutation 확인:**
  - `injected`의 길이가 1이고 snapshot이 정확히 일치하는지 assert한다. wrapper가 실제로 불렸다는 증거다.
  - positive 호출은 tree를 바꾸지 않는다.
  - 거부 뒤의 tree는 주입한 상태와 정확히 같다.

## 독립 실행

Windows Python 3.14.7에서 일회용 detached worktree로 돌렸다. Python process는 하나씩 순서대로 실행했다.

- **baseline:** 새 파일만 돌리면 2 pass다. plain_reentry와 함께 돌리면 21 pass, 0 skip, exit 0이다.
- **node-cert 항만 False:** `[node-cert.pem]`가 DID NOT RAISE로 실패한다. `[ca.pem]`는 pass다.
- **ca 항만 False:** `[ca.pem]`가 DID NOT RAISE로 실패한다. `[node-cert.pem]`는 pass다.
- **두 항 모두 False:** 두 case 모두 실패한다.
- 따라서 각 항은 자기 case만 잡는다. 남은 다른 항이 그 drift를 가리지 못한다.
- **context(검증 전에 drift):** 임시 파일로 돌리고 지웠다.
  - guard가 그대로일 때:
    - `node-cert.pem` drift는 마지막 SF1 문구로 거부된다.
    - `ca.pem` drift는 그보다 앞선 `Rotation issuing chain is not the pinned chain`으로 거부된다.
  - node-cert 항만 False이면 `node-cert.pem` drift는 DID NOT RAISE다.
  - 따라서 CA는 앞선 pin 검사가 가린다. ca 항만 따로 검증하려면 검증 뒤에 주입해야 한다. node-cert는 주입하지 않아도 마지막 항만 잡는다.
- **복원:** 모든 mutant는 scratch checkout 안에서만 만들었다. 매번 SHA256 복원을 확인했고 `git status`는 clean이다.

## 판정

**ACCEPT** (TEST-ONLY delta 542b48f9). **R-L1 CLOSED.** 새 finding은 없다.

### 남은 Info

- **R-I1:** 결과는 Windows local에서만 나왔다. 새 파일의 Linux, Core, Backend pytest는 NOT_RUN이고, e50c CI에서 물려받을 수 없다.
- **R-I2, R-I3, C-I2:** 그대로 Info로 둔다. 범위를 넓히지 않았다.
- **R-I4:** ca.pem case는 실제 검증 뒤의 read/check race를 모델링한다. 검증 전 drift는 앞선 CA pin이 이미 거부한다. 두 거부 모두 fail-closed다.

## 다음

다음 owner는 Root다. 542b를 이후 frozen source에 넣을지, 그리고 별도의 Linux CI를 돌릴지 Root가 정한다. Claude는 e50 branch를 옮기지 않았다. respin, all8, archive, runtime 변경도 하지 않았다.
