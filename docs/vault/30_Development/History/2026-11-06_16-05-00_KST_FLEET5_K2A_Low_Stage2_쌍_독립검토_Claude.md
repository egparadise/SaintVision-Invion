---
doc_id: "HISTORY-FLEET5-20261106-K2A-LOW-STAGE2-PAIR-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 K2A Low dba · Stage2 01a 쌍 독립 코드 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T16:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "dba1804b1d180eda2bf0439952e9706782109fd6"
task_ids: ["FLEET5-K2A-TRUST-HISTORY-20261106", "FLEET5-PEER-FLOOR-MOUNT-ORDER-STAGE2-20261106"]
tags: ["fleet5", "independent-review", "k2a", "stage2", "pin-seam", "claude"]
---

# K2A Low dba · Stage2 01a 쌍 독립 코드 검토

Orca `task_de20693ba7c9`, dispatch `ctx_8a1710587147`다. owner는 Codex `task_a95ef3d8ccce / ctx_ed23b4a777d0`다. 질문 `msg_6823df024379`는 이 판정과 Root의 구체 조치가 있을 때까지 pending이다.

검토 대상은 따로 동결된 두 target이다. **통합·결합 source는 없다.** 결합 review·unit·CI를 주장하지 않는다.

- **Low:** `dba1804b`, 정확한 부모는 `ff3169d3`(product == de71)다.
- **Stage2:** helper `01a4bebf`, 정확한 부모는 `52f935ac`다. qualified report `21059451`는 01a의 직접 자식이고 docs-only다.
- 선행 검토는 `49d0f904`(Docs `42168779010`)의 K2A-R1~R5다. Root Evidence `8993b1fc`의 Root 결정 두 건도 읽기만 했다.
- **기계 판독 결과:** `docs/vault/30_Development/Evidence/fleet5-k2a-low-stage2-pair-review-20261106-claude/review.json`
- **명령·exit·hash:** 같은 폴더의 `commands.json`, `hosted-ci-verification.json`, `reviewer-results.txt`, `local-doc-gates.txt`

## 대상별 판정

**Low dba: CODE_AXIS_ACCEPT_FOR_BOUNDED_LOW_REVISION.** 새 Low 1건(PL-R1a)은 bounded slice를 막지 않는다.

- **R2·R3·R4·R5: CLOSED.**
  - R2는 PC2/PC4 사이의 canonical scope·leaf DER·SPKI 중복을 TRUST_UNKNOWN으로 거부한다.
    - 검토자 판별: 같은 구성에서 key만 다르게 하면 통과하고, 같은 key면 거부한다.
  - R3는 모든 operation entry와 고유 HELD lease를 검사한다.
    - 거부 위치는 K1 앞의 pure·evaluate·public 경로이고, 코드는 ORIGINAL_PLAN_OPERATION_MISMATCH다.
    - 합법 2-op fixture는 end-to-end로 통과한다.
  - R4는 HOLD를 문서로만 기록한다. 새 field·ABI·positive factory는 없다.
  - R5 census는 bridge 객체 전체와 method set을 포함한다. 검토자 type-correct mutant 6건도 모두 검출했다.
- **R1:** static selector·alias 계열은 CLOSED다.
- **잔여 PL-R1a(Low):** 아래 compile-valid 변형 3건은 owner gate 세 개를 모두 exit 0으로 통과한다(build exit 0).
  1. 자체 interface 또는 generic constraint의 **exported** method dispatch로 `Certificate.Verify`를 호출한다.
  2. 같은 방식으로 `Time.Local`을 호출한다.
  3. `*(&time.Local)`에 쓴다.
- PL-R1a의 현재 production 도달은 없다. ports는 unexported method만 쓰고, 외부 var 사용은 `time.UTC` 읽기뿐이다.
  - 그러나 README의 "certificate Verify/system roots refused" 문장은 이 계열에는 성립하지 않는다.
  - 수정안(test-only + README 문구): interface/constraint method는 자체 패키지 unexported만 허용한다. 외부 패키지 var에는 `&`를 거부하고, 읽기는 정확한 목록만 허용한다.

**Stage2 01a: CODE_AXIS_ACCEPT_FOR_BOUNDED_STAGE2_FIXED_CASE_CANDIDATE.** Critical·High·Medium·Low는 0건, Info는 5건이다.

- whole-module AST로 확인했다. imports·상수·모든 top-level node가 52f와 같다. 차이는 `observe`의 Mounts 피연산자 2개와 새 `_ordered_plain_mounts`뿐이다.
- `_ordered_plain_mounts`는 원본 dict 전체를 고유 Destination으로 바깥 순서만 정렬한다. projection·field drop·경로나 Unicode 정규화·hash·set 의미는 없다.
- 실제 `_plain`·`repair_target`은 두 read에서 모두 유지된다.
- 검토자 22건이 PASS했다.
  - Mounts 순서가 바뀌어도 Id·Image·Config·StartedAt·RestartCount·consumers·CreatedAt·volume 변경을 가리지 못한다.
  - `/state `·`/STATE`·`/state/.`, type 교차, socket 추가·삭제, Source 교환은 거부된다. 입력은 변형되지 않는다.
- S2-I1: Python `True==1==1.0`은 감지되지 않는다. frozen 52f에서도 같다(기존 동작이며 회귀가 아니다).

## 다섯 축 분리

1. **코드:** 위 두 판정이다.
2. **실제 focused:**
   - Stage2 push `42174324865` job `127749166146`은 15/15 step SUCCESS다.
   - 검토자가 artifact `13483245465`(1767 bytes, `b7e3c237…`)를 GitHub digest와 대조했다. 고유 sample 3개가 모두 PASS다.
   - Low는 hosted race를 새로 돌리지 않았다. local race는 cgo가 꺼져 NOT_RUN(exit 2)이다.
3. **whole Core:** FAILURE를 그대로 보존한다. de71 `42164071724`와 Stage1 52f `42170068364`다. 결합 Core는 없다.
4. **독립 검토:** 이 검토다. Root Codex의 53/45 제안 검토는 Claude 검토로 세지 않는다.
5. **운영 인수:** NONE.

## 정확한 pin seam (변경하지 않음)

- 기존 launcher pin이 바뀐 helper를 거부하는 것은 **의도된 refusal**이다. 거부는 0dfd(17378b80)부터 이어졌다.
- 정상 등록할 값은 `deploy/lan/leaf_rotation_standalone_runtime.py:35`의 `WORKER_MODULES['worker_peer_floor.py']` 한 줄뿐이다.
  - 값: `c73c81ad…2fec` → `7665735e…5799`.
  - 17378b80은 등록하지 않는다.
- **불변:**
  - `LOCK_SHA256 06710d85`와 lock JSON(wheel만 pin)
  - entry `4e296852`와 나머지 module pin 3개
  - BUNDLE/INSTALL schema `:2`
  - K1의 28 pin·v5 graph·K2A raw K1 pin·census baseline·go.mod
  - 역사 Evidence
- **파생 값:**
  - workerModulesSha256: `a08ac3a6…` → `7a2840ba…`
  - launcher 파일 hash `76be4088…`: 실제 편집 후 측정한다.
- seam 증명: `tests/test_lan_leaf_rotation_standalone_runtime.py`의 local 결과다.
  - 01a: 13 failed / 24 passed / 6 skipped
  - dba: 37 passed / 6 skipped
  - 이 test는 테스트 수정 없이 pin commit으로만 green이 된다.
- pin 교체는 installed trust가 아니다. K2 runtime-lock/LinkedClosure 결합도 아니다.

## Root 통합안

0. PL-R1a 처리 시점을 정한다. 권고는 Low branch의 test-only commit과 그 delta만의 Claude 검토다.
1. base는 `21059451`이다.
2. Low head를 2-parent merge로 넣는다. 경로가 겹치지 않으므로(0 overlap) 충돌 해결은 예상되지 않는다. merge 뒤 path별 blob 동일성을 확인한다.
3. 그다음에만 one-line checksum pin commit을 넣는다.
4. merge와 pin을 Claude가 검토한다. 이어서 정확한 최종 SHA에서 fresh full Core + Docs를 한 번 실행한다. Go race·LAN installer acceptance·main pytest·build·`go test ./...`를 포함한다.
5. branch 전용 Stage2 diagnostic workflow를 포함할지 정한다.

## 다음 담당

- **Root:** 두 판정을 기록한다. PL-R1a 시점과 통합·pin 등록 cut을 결정한다.
- **Codex:** Root 지시가 있을 때만 PL-R1a commit, merge, pin commit을 만든다.
- **Claude:** Root가 배정할 때만 그 정확한 commit들을 검토한다.

검토자는 product·test·helper·pin·launcher·workflow·board·registry를 수정하지 않았다. 통합·key·설치·Obsidian apply도 수행하지 않았다.
