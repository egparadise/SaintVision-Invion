---
doc_id: "HISTORY-FLEET5-20261107-B-REV9F-9CEA-NARROW-DELTA-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 B rev9f 9cea 좁은 delta 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T04:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "9cea33e8a087981fdedcddb71c4381bdc25c1507"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105", "FLEET5-B-REV9F-FIX-ONLY-20261107"]
tags: ["fleet5", "independent-review", "b-contract", "design", "claude"]
---

# B rev9f 9cea 좁은 delta 독립 검토

Orca `task_12e7a699ad90` / dispatch `ctx_7fb26ffb3970`에서 한 실제 독립 검토다. owner는 Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`이다. owner 질문 `askmsg_453ac2a3ea95`는 pending이고, Root 허가는 `msg_ca131b500e12`다.

- 시작 조건: P02 Rev3 검토 `task_01cdc5e54543 / ctx_a6589fe0c3df`가 succeeded/settled/exited/released인 것을 `worker-show`로 먼저 확인했다.
- 대상: `9cea33e8`. base는 Rev9e `3cccfe4d`이다. 추가된 경로는 175개(Evidence 174, History 1)이고 수정·삭제는 0이다. 제품 기준은 `72028cba`이다.
- 먼저 읽은 것: 직전 실제 검토 `764c3bf3`의 History, review.json, driver, 결과, commands. Rev9f Evidence 안의 764 결과 사본은 원본과 git blob이 같다(`3e840fab`).
- 이어서 읽은 것: owner History, 바뀐 producer(reflection_audit, callee_identity, pending_contracts, pending_obligations)의 3ccc 대비 diff, 새 lexical_bindings 전체, source_bindings, call_binding, parameter_flow, rev9f_gap_driver, rev9f_units, proof-final01.
- Root receipt `.work/b9f-source-root-verified.json`(Docs `42276852254` / job `128095264239`)은 Root 증거로 받았다. 검토자가 다시 조회하지는 않았다. Root vault는 read-only로 읽었다(head `fc02b4ae`, Index 1.0.477, Codex board 1.0.438, Claude board 1.2.130).

**판정: REVISION_REQUIRED (narrow, LOW만 있음, MEDIUM 없음).**

- 764의 실제 반례 5건은 최종 9cea producer에서 모두 의미적으로 거부된다. 입력 SHA는 764의 ACCEPT 행과 같다.
- 대조군과 72028 positive는 ACCEPT다. positive의 parsed 25 = audited 25, production 11, binding 576이다.
- 다만 같은 선언 범주 안의 가까운 변형 3건이 full provenance에서 아직 ACCEPT된다. 72028에는 이런 형태가 0건이다.
- A7(NodeChannels.snapshot)은 아직 시작하지 않는다(UNSTARTED).
- 상세: `docs/vault/30_Development/Evidence/fleet5-b-rev9f-9cea-review-20261107-claude/review.json`.

## 최종 bytes 확인

- 검토 driver는 실행 전에 Evidence 파일 82개의 hash를 다시 계산했다. 결과는 owner proof-final01 마지막 명령의 after-map과 82/82 같다. 따라서 검토자 probe는 owner 최종 bytes에서 돌았다.
- 이 대조는 실행 전후 bracket일 뿐이고, 실행 중 계속 계측한 것은 아니다. 보존된 이전 기록은 새 coverage가 아니다.

## L1, L2 상태

검토자 run은 full provenance 22건, binder fixture 13건, reflection unit 5건이고 exit 0이다. full provenance 변형은 모두 compile되고, 새 미결 이름이 없으며, witness 15/15를 확인했고, 6 root가 보존된다. 실행이나 import는 하지 않았다.

| 항목 | 상태 | 근거 |
| --- | --- | --- |
| B9e-L1 | 부분 → B9f-L1 | 764 business_auth overlay 3건(`import_module('.workspace_config', _CLAUDE_PKG)`, `import_module('.workspace_config', 'inv')`, `__import__('workspace_config', globals(), None, (), 1)`)은 `UNCATALOGUED_PRODUCTION_SOURCE:business_auth.py`로 거부된다. keyword 형태(`level=1`, `package='inv'`)도 거부된다. literal 0인 level(위치와 keyword)은 ACCEPT다. 5번째 slot 뒤의 starred는 UNKNOWN이다. 절대 이름에 starred package를 주면 UNKNOWN이다(보수적이고 gap이 아니다). |
| B9e-L2 | 부분 → B9f-L2 | 764 lan_pilot overlay 2건(global import installer, module star import)은 `UNRESOLVED:CALLEE_REBOUND`로 거부된다. comprehension을 통한 바깥 scope walrus도 거부되고, 같은 철자의 comprehension 반복 변수는 ACCEPT다. binder: class body global, module walrus, global 아래 for/with, type alias, nested 함수 안의 global은 거부된다. 대조군(다른 이름의 global, lambda 인자, 같은 철자의 method, 일반 cross-module import)은 owned formal을 유지한다. |

## 새 지적 (모두 LOW, 실제 72028 영향 없음)

- **B9f-L1** `supplied()`는 `args[index]`, keyword, `**` spread만 본다. 4번 slot 앞에서 끝나는 위치 `*` spread는 level을 숨긴다. 또 `importlib.__import__`는 기존 `importlib.*` 열거 안에 있고 signature가 같지만, `builtins.__import__`만 처리된다.
  - `__import__('workspace_config', *(globals(), None, (), 1)).configured_workspace(object(), tenant, settings)` → ACCEPT. 실제 level 1 사례와 같은 import다.
  - `importlib.__import__('workspace_config', globals(), None, (), 1).configured_workspace(…)` → ACCEPT.
  - 수정: index 이하 위치에 `ast.Starred`가 있으면 `[None]`으로 둔다. `importlib.__import__`를 `builtins.__import__`와 똑같이 다룬다. 일반 import resolver는 필요 없다.
- **B9f-L2** 새 lexical index는 callee가 정의된 파일(receiver)에만 적용된다. Name 호출이면 caller에서 def로 선언된 이름에만 적용된다. call-site 이름이 caller의 import alias이면, caller의 binding scope에 있는 global import나 star import는 기록만 되고 판정에 쓰이지 않는다.
  - `inv/workspace_config.py` 끝에 `def _claude_install(): global WorkspaceAPI; from foreign_module import WorkspaceAPI`와 `_claude_install()`을 붙이면 ACCEPT다. 그러면 configured_workspace :44가 owned database를 foreign callable에 넘긴다. 764 installer와 같은 모양이고 대상만 import된 이름이다.
  - 덧붙인 것이라 줄이 밀리지 않는다. installer는 module import 때 실행되므로 configured_workspace 호출보다 먼저 돈다.
  - binder: cross-module import 이름의 star shadow와 global import는 owned formal을 그대로 묶는다.
  - star 쪽은 full provenance 탈출을 보이지 못했다. 72028에서 relevant callee를 import하는 production 파일은 모두 자기 relevant callee도 정의한다. 그래서 module star import는 그 파일 쪽에서 이미 거부된다(workspace_api star 사례가 그렇다). star는 binder 증거로만 남긴다.
  - 수정: Name 호출이면 caller 파일도 본다. call-site 이름을 묶는 scope에, global 재지정을 반영한 binding event나 star import가 그 파일의 frozen multiset보다 많으면 `CALLEE_REBOUND`다. frozen import 자체는 허용해야 하므로 지금의 writes set 대신 개수를 비교해야 한다.
  - 돌리지 않은 것: caller 쪽에서 import 이름을 그냥 다시 대입하는 경우(`WorkspaceAPI = wrap(WorkspaceAPI)`). 위 수정이 이 경우도 덮는다.
- Info:
  - nonlocal은 선언대로 INFO이고 이번 cut 밖이다. 72028에는 nonlocal이 3건 있다.
  - I-a(class body `__new__`, class 정의 뒤의 dunder attribute 대입)는 여전히 full use-site guard에만 기댄다. binder만으로는 부족하다는 owner 한계가 그대로다. 이번에 다시 돌리지 않았다.
  - 이전에 결론이 나지 않은 match probe는 증거로 쓰지 않는다.

## 확인한 것과 하지 않은 것

- 검토자 run에서 mismatch는 8건이다.
  - full provenance 3건: 위 지적의 반례다.
  - binder와 unit 4건: 같은 지적의 AST 수준 확인이다.
  - 1건: 절대 이름에 starred package를 준 경우다. 검토자 예상이 틀렸고, 실제 결과는 보수적 UNKNOWN이었다.
- frozen 72028의 production 11개 경로를 scan했다. starred import 호출, `__import__` attribute, global, star import는 모두 0이다. nonlocal은 3이다.
- 자원: peak 153198592 B, 227 s다. 단일 검토자 process의 관측값이고 quota가 아니다.
- canonical sync CHECK(작성 전)는 exit 0이다. conflict는 0이고 state는 `3dda9efc…`에서 변하지 않았다. 작성 뒤 local gate 8개의 결과는 `local-doc-gates.txt`에 실제 exit와 state hash로 남긴다.
- 다시 실행하지 않은 것:
  - owner proof/docs 명령, model/terminal/recovery, owner 70/19/31/83/29 replay.
  - 19 edge(16/3), 12 entry, 회계 6개(598/757/1071/21/573/218), model/lifecycle 동일성. 이것들은 Root가 검증한 기록이고 검토자가 다시 계산하지 않았다.
- 하지 않은 것: full assembler, 3485 plan, 거대 ledger, whole Core, mutant import·실행, Obsidian apply·adopt·resolve·state 쓰기, 공유 보드·registry·ADR·pin·workflow 수정, helper 사용, 다른 Codex의 D04 작업 열람.
- 실제 binding은 모두 NULL/HOLD이고, runtime B는 0, A1~A16은 PENDING이다. observer lock은 19 밖에 남아 있다. storage R4는 여전히 0/1이 예상된다. model `f7384016…`과 lifecycle `710c6aaf…`는 그대로다.

## 다음 cut (Root에게)

1. Rev9g fix-only: base는 정확히 `9cea33e8`이다. 범위는 B9f-L1(level 앞의 starred spread, `importlib.__import__`)과 B9f-L2(import된 call-site 이름의 caller 쪽 binding scope에 lexical index 적용, frozen 개수 비교)다. full provenance 3건과 binder 2건을 회귀로 쓰고, 기존 대조군을 유지한다. 이어서 Claude 좁은 delta 검토를 1회 받는다.
2. 실제 수락과 Root의 별도 부여가 있은 뒤에만 NodeChannels.snapshot 단독 A7으로 간다.
- 다음 첫 행동: Root가 이 판정을 `askmsg_453ac2a3ea95`에 전달하고 Rev9g를 결정한다. 담당은 Root, 이어서 Codex다.
