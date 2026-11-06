---
doc_id: "HISTORY-FLEET5-20261107-B-REV9C-5EA-NARROW-DELTA-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 B rev9c 5ea 좁은 delta 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T00:15:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "5ea87937f1b542f8cbe32c08dc224526965a8e2d"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105", "FLEET5-B-REV9C-FIX-ONLY-20261106"]
tags: ["fleet5", "independent-review", "b-contract", "design", "claude"]
---

# B rev9c 5ea 좁은 delta 독립 검토

Orca `task_c5d0e8ae0837` / dispatch `ctx_e399e8dd4f9d`에서 한 실제 독립 검토다. owner는 Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`이다. owner 질문 `msg_bccbed800e8b`는 Root가 답할 때까지 pending이다.

- 대상: `5ea87937`. base는 Rev9b `870486f9`이다. remote ref가 정확히 일치한다. 추가된 경로는 139개(Evidence 138, History 1)이고 수정·삭제는 0이다. 제품 기준은 `72028cba`이다.
- owner Docs `42234721725` / job `127949272081`은 Root가 검증한 결과(`.work/b9c-source-root-verified.json`)를 그대로 받았다. 이 검토자가 다시 조회하지는 않았다.
- 읽은 것: owner History와 바뀐 producer 본문을 Rev9b 사본과 diff로 비교했다(constructor_graph, use_sites, t1_provenance, t1_build, pending_contracts, source_bindings, 그리고 새 파일 forwarding_discovery, owner_transfer). 그 밖에 직전 실제 검토 `aa3387b8`, Root 범위 `b-rev9c-fix-only-root-scope.json`, 72028 원문(workspace_config, app, workspace_api, lan_pilot, business_*)도 읽었다.
- Root vault는 read-only로만 읽었다. 시점은 head `f748a970`, Index 1.0.464, Claude board 1.2.130이다.

**판정: REVISION_REQUIRED (narrow, LOW만 있음, MEDIUM 없음).**

- 72028 실제 bytes에 대한 T1/A8 closure는 유지된다.
- A7(NodeChannels.snapshot)은 아직 부여할 수 없다.
- 상세: `docs/vault/30_Development/Evidence/fleet5-b-rev9c-5ea-review-20261106-claude/review.json`.

## L1~L3, I1 상태

| 항목 | 상태 | 근거 (검토자 probe 47건, exit 0) |
| --- | --- | --- |
| B9b-L1 | 부분 → B9c-L1 | frozen root multiset이 동작한다. aa3387의 state, runtime(state) 치환, 인자를 바꾼 root, helper로 옮긴 root는 모두 `CONSTRUCTOR_ROOT_REMOVED_OR_HIDDEN`으로 거부된다. 6 root를 그대로 둔 채 lan_pilot에 숨긴 root를 더한 변형 7개(importlib, operator alias, sys.modules.get, methodcaller, from-import alias 3개)도 거부된다. 일부는 census short-name 경로(`CONSTRUCTOR_BINDING`)로 거부된다. 대조군 3개는 ACCEPT다. |
| B9b-L2 | 부분 → B9c-L1 | 3-hop 고정점(business_handoff→business_surface→business_auth)은 세 파일을 모두 찾아 거부한다. keyword 호출, module import+getattr, 함수 안 import도 거부된다. 로컬 Database helper와 harness 2-hop은 ACCEPT이고 harness는 분리된다. surface 21은 census 20 + app.py이다. 생성자는 production 6 / harness 20이다. 검토자 git grep에서도 호출자는 app.py:1323과 재귀 :87뿐이다. |
| B9b-L3 | 부분 → B9c-L2 | 보고된 5건은 검토자 철자(`import foreign_module`)로도 거부된다. tuple-unpack, walrus, dict comprehension, append, lambda 변형도 거부된다. 비소유 대조군은 ACCEPT다. |
| B9b-I1 | 종결 | 정렬을 코드에서 확인했다. 두 seed의 closure `7a925bee…`가 Git blob과 같아서 재현은 하지 않았다. |
| I2 / I3 / I4 | 유지 | I2: keyword-only 호출은 graph만 보면 ACCEPT이고 full provenance는 REFUSE다. 두 검사가 함께 있어야 한다. I3: History 문장으로만 기록되어 있다. I4: 72028 대비 "새 사용 없음"만 증명한다. |

## 새 지적 (모두 LOW, 실제 72028 영향 없음)

- **B9c-L1** 열거된 reflection audit이 proof source 12개에만 적용된다.
  - census/discovery가 읽는 바깥 production 파일은 검사하지 않는다.
  - 예 1: `business_auth.py`에 `operator.attrgetter('ObservationWorker')(sys.modules['inv.observer_worker'])(object(), None)` root를 넣으면 ACCEPT된다. 6 root는 그대로다.
  - 예 2: `importlib.import_module('inv.workspace_config').configured_workspace(object(), …)`와 `sys.modules[…]` 변형도 ACCEPT된다.
  - 실제 72028에는 이런 형태가 저장소 전체에 0건이다.
  - 수정: census/discovery가 읽는 production 파일마다 같은 열거 scan을 돌린다. 보호 이름 문자열과 추적 중인 module/이름 문자열을 포함한다. 그 결과 `UNRESOLVED:RELEVANT_REFLECTION_OUTSIDE_PROOF_SOURCES`로 거부한다.
- **B9c-L2** 함수·생성자 parameter로 받은 owner 객체가 소유로 전파되지 않는다.
  - 예 1: `WorkspaceAPI.__init__`의 `runtime`(workspace_config:47 root가 :44의 세 번째 인자로 들어온다)을 `register_runtime(runtime | runtime.db | runtime.db.transaction)`에 넘기면 ACCEPT된다.
  - 예 2: `create_app`의 `workspace`(app.py:1405)를 `register_workspace(workspace | workspace.runtime.db)`에 넘기면 ACCEPT된다.
  - 같은 식을 파생 이름(for runtime / workspace = configured_workspace)으로 쓰면 거부된다. 따라서 원인은 parameter binding이다.
  - aa3387 수정안에 이 형태가 빠져 있었다. 검토자 자신의 이전 누락이다.
  - 수정: proof source 안의 호출 위치(위치 인자·keyword)에서 parameter 소유를 고정점으로 전파한다. current와 frozen을 합친다.
- Info:
  - I1: 열거 밖의 `pkgutil.resolve_name`은 ACCEPT된다. 선언된 한계이고 요구하지 않는다.
  - I2: keyword-only 추적 호출을 graph와 discovery가 매핑하지 않는다. 상위 hop이 inventory에 없다. 지금은 use-site audit과 UNCATALOGUED 때문에 fail-closed다.
  - I3: harness의 함수 범위 module alias와 monkeypatch가 harnessFiles에서 빠진다(test_object_store_provider_binding:500/514).

## 확인한 것과 하지 않은 것

- producer 48/48이 blob과 일치한다(398363 B). raw copy 32/32와 rev9b-review 17/17도 aa3387 blob과 같다. model·lifecycle은 870과 바이트 동일하다. 순서는 pending_contracts→edge_categories이고, stage1 `ab5ecd59…`와 final `68dbd6e6…`이 Git과 같다.
- 회계 artifact 6개가 Rev9b와 바이트 동일하다: 19 edge(16/3), 12 entry, 598/757/1071/21, 573, 218, upgrade 0.
- owner 회귀(29 = 20 + 대조 9)와 development 실패 3건은 읽기만 했다. 대조군 중 old REFUSE→new ACCEPT 2건은 정규화된 key 때문이고, 검토자 대조군도 같은 결과다.
- owner 명령 16개, model182/terminal47/recovery79+8은 다시 실행하지 않았다. model bytes가 같으므로 hash로 유지한다.
- 검토자 fixture 오류 2회(행 이동)는 witness guard가 멈췄다. 로그는 run1/run3로 보존했고 판정에 쓰지 않았다. 최종 peak는 136806400 B로, 관측값이고 quota가 아니다.
- 하지 않은 것: B code/port/freeze/DB/Engine/SSH/issuer/설치/physical 부여, mutant import·실행, full assembler/3485 plan/거대 ledger, Obsidian apply/adopt/resolve/state 쓰기, 공유 보드·registry 수정.
- 실제 binding은 모두 NULL/HOLD이고, runtime B는 0, A1~A16은 PENDING이다. observer lock safety는 named runtime pending으로 남는다. storage gap은 여전히 red가 예상된다.

## 다음 cut (Root에게)

1. Rev9d fix-only: base `5ea87937`. 범위는 B9c-L1(3 negative), B9c-L2(5 negative와 대조 1)이다. 선택으로 keyword 매핑과 I3의 기계 판독 기록을 넣는다. 이어서 Claude 좁은 delta 검토를 1회 받는다.
2. Rev9d가 실제로 수락된 뒤에만 NodeChannels.snapshot 단독 A7으로 간다. NodeDelivery.deliver, full A8, 전체 port는 제외한다.
- 다음 첫 행동: Root가 이 판정을 `msg_bccbed800e8b`에 전달하고 Rev9d를 결정한다. 담당은 Root, 이어서 Codex다.
