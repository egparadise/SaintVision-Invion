---
doc_id: "HISTORY-FLEET5-20261107-B-REV9G-0E66-NARROW-DELTA-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 B rev9g 0e66 좁은 delta 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T05:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "0e66b5ab2b5fbc131dd6e98f5d5e8930ac045148"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105", "FLEET5-B-REV9G-FIX-ONLY-20261107"]
tags: ["fleet5", "independent-review", "b-contract", "design", "claude"]
---

# B rev9g 0e66 좁은 delta 독립 검토

Orca `task_6e4ff78a4444` / dispatch `ctx_b48554022c90`에서 한 실제 독립 검토다. owner는 Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`이다. owner 질문 `msg_13ccbb81f97b`는 pending이고, Root 허가는 `msg_6a4d15e35b3e`다.

- 시작 조건: 직전 검토 `task_12e7a699ad90 / ctx_7fb26ffb3970`이 succeeded/settled/exited/released인 것을 `worker-show`로 먼저 확인했다.
- 대상: `0e66b5ab`. base는 Rev9f `9cea33e8`이다. 추가된 경로는 190개(Evidence 189, History 1)이고 수정·삭제는 0이다. 제품 기준은 `72028cba`이다.
- 먼저 읽은 것: 직전 실제 검토 `ce713a85`의 History, review.json, driver, 결과, commands를 ce713 commit에서 직접 읽었다. Rev9g Evidence 안의 사본은 원본과 git blob이 같다(결과 `0d9c2711`, driver `10d748d5`).
- 이어서 읽은 것: owner History, 바뀐 producer 4개(reflection_audit, callee_identity, lexical_bindings, parameter_flow)의 9cea 대비 diff와 전체, rev9g_gap_driver, 결과 json 3개, proof-final01.
- Root receipt `.work/b9g-source-root-verified.json`(Docs `42285078981` / job `128123693430`)은 Root 증거로 받았다. 검토자가 다시 조회하지는 않았다. Root vault는 read-only로 읽었다(head `aaf957a2`, Index 1.0.479, Codex board 1.0.440, Claude board 1.2.130).

**판정: ACCEPT (narrow Rev9g delta). MEDIUM·LOW 없음, INFO만 있음.**

- ce713의 실제 반례 3건은 최종 0e66 producer에서 모두 의미적으로 거부된다. 입력 SHA는 ce713의 ACCEPT 행과 같다.
- 각 반례는 선언된 Rev9g 변경 하나만 검토자 process 안에서 9cea 코드로 되돌리면 다시 ACCEPT된다. 따라서 거부 원인은 그 변경이다.
- 대조군과 72028 positive는 ACCEPT다. positive는 parsed 25 = audited 25, production 11, binding 576, caller binding proof 13이다.
- A7(NodeChannels.snapshot)은 여전히 UNSTARTED / NOT_GRANTED다. 이 ACCEPT는 Root가 별도 A7 cut을 검토할 수 있게 할 뿐 부여가 아니다.
- 상세: `docs/vault/30_Development/Evidence/fleet5-b-rev9g-0e66-review-20261107-claude/review.json`.

## 최종 bytes 확인

- 검토 driver는 실행 전에 Evidence 파일 93개의 hash를 다시 계산했다. 결과는 owner proof-final01 마지막 명령의 after-map과 93/93 같다. 따라서 검토자 probe는 owner 최종 bytes에서 돌았다.
- 이 대조는 실행 전후 bracket일 뿐이고, 실행 중 계속 계측한 것은 아니다. owner의 28 unit, 9 control, 17 명령은 다시 돌리지 않았다.

## L1, L2 상태

주 run은 full provenance 34건(입력 무효 1건 포함), binder fixture 11건, reflection unit 10건이고 exit 0이다. 유효한 full 변형은 모두 compile되고, 새 미결 이름이 없으며, witness 15/15를 확인했고, 6 root가 보존된다. 실행이나 import는 하지 않았다.

| 항목 | 상태 | 근거 |
| --- | --- | --- |
| B9f-L1 | CLOSED | `__import__('workspace_config', *(globals(), None, (), 1))`와 `importlib.__import__('workspace_config', globals(), None, (), 1)`는 `UNCATALOGUED_PRODUCTION_SOURCE:business_auth.py`로 거부된다. `supplied()`의 Starred 줄, 또는 `IMPORTERS`만 되돌리면 각각 ACCEPT다. 가까운 변형(slot 3에서 끝나는 Starred, name slot의 Starred, `importlib.__import__`의 `level=` keyword·from alias·module alias·Starred level, `builtins.__import__`의 Starred level)도 거부된다. 대조군(level 0 literal 위치·keyword, `importlib.__import__('json')`, slot 4 뒤에만 있는 Starred)은 ACCEPT다. |
| B9f-L2 | CLOSED | `inv/workspace_config.py` 끝의 global import installer(`WorkspaceAPI`)는 `UNRESOLVED:CALLEE_REBOUND`로 거부된다. `caller_error`만 되돌리면 ACCEPT다. guard 수준에서도 `:44 WorkspaceAPI`만 거부되고 `:47`, `:64`는 None이다. 같은 installer를 `RestrictedWorkspaceRuntime`(:47)에 쓰는 경우와 class body global import도 Rev9g 때문에 거부된다(되돌리면 ACCEPT). |

L2의 다른 가까운 변형도 모두 `CALLEE_REBOUND`로 거부된다. 다만 이 변형들은 `caller_error`를 되돌려도 기존 use-site guard(`DYNAMIC_BLOCK`)가 이미 거부한다. 해당 변형:

- module 수준 재대입, 같은 줄의 두 번째 import, comprehension 안 walrus, global `del`.
- 함수 scope `SnapshotStore`(:64)의 빈 줄 추가 import, 같은 개수로 import를 바꾼 경우.
- frozen :57에서 owned database를 새 파일로 넘기고, 새 파일 함수가 import 이름을 지역 변수로 덮는 경우.

module star import도 거부되지만 되돌려도 기존 guard가 거부한다. 따라서 새 full star 증명이 아니다. guard 수준에서는 `caller_error`가 :44와 :47을 거부한다.

- 입력 무효: module import 9번 줄을 같은 개수로 바꾸면 6 root가 보존되지 않는다. 그래서 결과로 세지 않았다. guard 수준에서는 :44와 :47이 거부된다.
- binder 회귀: ce713의 실제 입력(source SHA 동일) `near-cross-module-imported-callee-star-shadow`와 `near-cross-module-imported-callee-global-import`는 `CALLEE_REBOUND`이고 owned formal이 묶이지 않는다. 일반 재대입, 같은 import 중복, global for-target도 거부된다. 이것은 binder 증거이고 full semantic 증명이 아니다.
- 대조군:
  - full ACCEPT: 관련 없는 alias import, module 수준 foreign `SnapshotStore` import(:64는 :60의 함수 scope import가 묶는다), 72028 positive.
  - binder ACCEPT: ce713 `control-cross-module-import-plain`, global 선언만 있는 경우, 다른 scope의 지역 변수, 관련 없는 alias.
  - `WorkspaceAPI` 철자를 쓰는 full 대조군 5개(global 선언만, nested 지역, class body, comprehension 반복 변수, lambda 인자)는 기존 `DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:SYMBOL`로 거부된다. 이 거부는 `caller_error` 유무와 관계없다. guard 수준에서 세 call site 모두 None이므로 Rev9g가 만든 오탐이 아니다.
- current positive: caller binding proof 13건이 모두 `EXACT_FROZEN_EVENT_MULTISET`이다. 현재와 frozen의 multiset이 같고, 각각 frozen event 1개, star 0개, reason None이다.

## INFO (판정에 영향 없음)

- **I-1 binder 전용 지역 shadow.** 이 동작은 9cea와 0e66에서 똑같으며, Rev9g가 새로 만든 것이 아니다.
  - frozen 기준이 없는 binder fixture에서 `from M import accept`와 `def use(): accept = receive; return accept(held)`는 여전히 `M.accept.slot`에 held를 묶는다.
  - 원인: 호출의 binding scope `use`에 import event가 없어서 `caller_error`가 None을 낸다.
  - full provenance에서는 이번 검토로 도달하지 못했다.
    - frozen 함수 안의 지역 shadow는 frozen scope 비교로 거부된다(:44 `CALLEE_REBOUND`).
    - owned database를 이런 새 파일로 보내는 경우도 거부된다.
  - 선택적 보강: binder 전용 모드에서 resolver의 import alias scope와 lexical binding scope가 다르면 거부한다. 이번 판정에 필요하지는 않다.
- 현재 binding 576건의 callee는 Name 559건, self attribute 17건이다. module alias attribute callee는 없다. 따라서 caller 쪽 module alias 재바인딩은 72028에서 관련 경로가 아니다.
- nonlocal은 선언대로 INFO이고 이번 cut 밖이다.
- 시험하지 않은 것(선언 범주 밖의 새 family): 이런 형태는 확인하지 않았다.
  - `__package__`/`__spec__` 변경으로 글자가 같은 relative import의 대상을 바꾸는 형태.
  - import된 module의 attribute 대입.
  - `globals()`/`sys.modules` 쓰기.
  - `importlib._bootstrap` 내부 함수.

## 확인한 것과 하지 않은 것

- 자원: 주 probe process의 peak는 168812544 B이고 660 s 걸렸다. 보조 process 3개는 측정하지 않았다. 단일 process 관측값이고 quota가 아니다.
- canonical sync CHECK(작성 전)는 exit 0이다. conflict는 0이고 state는 `73939c3a…`에서 변하지 않았다. 작성 뒤 local gate 8개의 결과는 `local-doc-gates.txt`에 실제 exit와 state hash로 남긴다.
- 다시 실행하지 않은 것:
  - owner proof/docs 명령, model/terminal/recovery, owner 70/19/31/83/29/82 replay.
  - 19 edge(16/3), 12 entry, 회계 6개, stage1/final hash, model/lifecycle 동일성. 이것들은 Root가 검증한 기록이고 검토자가 다시 계산하지 않았다.
- 하지 않은 것:
  - full assembler, 3485 plan, 거대 ledger, whole Core 실행.
  - mutant import·실행, Obsidian apply·adopt·resolve·state 쓰기.
  - 공유 보드·registry·ADR·pin·workflow 수정, helper 사용, 다른 Codex의 D04 작업 열람.
- 실제 binding은 모두 NULL/HOLD이고, runtime B는 0, A1~A16은 PENDING이다. observer lock은 19 밖에 남아 있다. storage R4는 여전히 0/1이 예상된다. model `f7384016…`과 lifecycle `710c6aaf…`는 그대로다.

## 다음 (Root에게)

- Rev9g B9f-L1/L2는 실제 독립 검토로 수락됐다. 이 결과로 Root는 별도의 구체적인 A7 NodeChannels.snapshot 단독 구현 cut을 검토할 수 있다. 부여는 Root만 한다.
- 다음 첫 행동: Root가 이 판정을 `msg_13ccbb81f97b`에 전달하고 A7 부여 여부를 결정한다. 담당은 Root다.
