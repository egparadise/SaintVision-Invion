---
doc_id: "HISTORY-FLEET5-20261107-B-REV9E-3CCC-NARROW-DELTA-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 B rev9e 3ccc 좁은 delta 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T03:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "3cccfe4d7511180fa8fbb6f5742328c6a43d04bd"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105", "FLEET5-B-REV9E-FIX-ONLY-20261107"]
tags: ["fleet5", "independent-review", "b-contract", "design", "claude"]
---

# B rev9e 3ccc 좁은 delta 독립 검토

Orca `task_d1f9b00b0306` / dispatch `ctx_52365790d017`에서 한 실제 독립 검토다. owner는 Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`이다. owner 질문 `msg_9578b8329a2e`는 Root가 답할 때까지 pending이다.

- 대상: `3cccfe4d`. base는 Rev9d `54549b90`이다. 추가된 경로는 174개(Evidence 173, History 1)이고 수정·삭제는 0이다. 제품 기준은 `72028cba`이다.
- owner Docs `42264002754` / job `128051002636`은 Root가 검증한 결과(`.work/b9e-source-root-verified.json`)를 그대로 받았다. 이 검토자가 다시 조회하지는 않았다.
- 읽은 것: owner History, 바뀐 producer(reflection_audit, call_binding, parameter_flow, pending_contracts, pending_obligations)의 54549 대비 diff, 새 callee_identity 전체, source_bindings, rev9e_units, rev9e_gap_driver, verify_rev9e, proof-checks와 이전 두 ledger, development-failures, proof-producer-hashes. 직전 실제 검토 `9266f719`와 그 driver도 읽었다.
- Root vault는 read-only로만 읽었다. 시점은 head `138534a6`, Index 1.0.472, Codex board 1.0.433, Claude board 1.2.130이다.

**판정: REVISION_REQUIRED (narrow, LOW만 있음, MEDIUM 없음).**

- 72028 실제 bytes에 대한 T1/A8 closure는 유지된다. 최종 3ccc producer에서도 positive는 ACCEPT다.
- 9266의 실제 반례 6건은 최종 producer에서 모두 거부된다. I1은 선언한 상한 안에서 닫혔다.
- 남은 지적은 L1과 L2가 열거한 범주 안의 가까운 변형 두 가지다. 72028에는 이런 형태가 0건이다.
- A7(NodeChannels.snapshot)은 아직 시작하지 않는다(UNSTARTED).
- 상세: `docs/vault/30_Development/Evidence/fleet5-b-rev9e-3ccc-review-20261107-claude/review.json`.

## L1, L2, I1 상태

검토자 probe는 full provenance 35건과 binder fixture 19건이고 exit 0이다. full provenance 변형은 모두 valid AST이고, 새 미결 이름이 없으며, witness 15/15를 확인했고, 6 root가 보존된다. 실행이나 import는 하지 않았다.

| 항목 | 상태 | 근거 |
| --- | --- | --- |
| B9d-L1 | 부분 → B9e-L1 | 9266 반례 4건(변수 key, f-string, `'.'.join`, getattr 변수로 숨긴 7번째 root)은 모두 `UNCATALOGUED_PRODUCTION_SOURCE:business_auth.py`로 거부된다. hit 종류는 `ENUMERATED_REFLECTION_NONLITERAL_KEY`이다. 4288 literal 거부 3건도 유지된다. 대조군 3건은 ACCEPT다. 관련 없는 key라도 증명할 수 없으면 선언대로 거부된다. parsed 25 = audited 25(production 11)다. frozen NONLITERAL hit은 db.py 1, lan_pilot.py 1, test 2이고, 모두 frozen과 정확히 같아서 허용된다. |
| B9d-L2 | 부분 → B9e-L2 | 9266 `WorkspaceAPI.__new__` runtime 반례는 `CLASS_CONSTRUCTION_BINDING`으로, `_current_finalized_batch` wrapper conn 반례는 `CALLEE_REBOUND`로 거부된다. create_app 재바인딩도 거부된다. 4288 escape 5건도 유지된다. 대조군(unowned working, 관련 없는 module helper, 같은 철자의 local/class attribute)은 ACCEPT다. alias guard는 원래 이름이 다시 바인딩되면 거부한다. 다시 바인딩한 뒤 저장해 둔 alias를 직접 호출해도 거부된다(보수적이고 gap이 아니다). Server 예외는 좁다. `__new__` 추가, metaclass 헤더, 호출 식 변경이 모두 거부된다. |
| B9d-I1 | 닫힘 | 상한은 vararg/kwarg와 factory 수를 포함한다. frozen 실행은 상한 719 중 7회 반복으로 끝나고, binding 576, unresolved 0이다. 명시 keyword→`**kwargs`는 3/3으로 수렴하고, 증거 span/hash가 원래 식과 일치한다. 알 수 없는 `**bag`, `**extra` 전달, `*rest`는 거부된다. |

## 새 지적 (모두 LOW, 실제 72028 영향 없음)

- **B9e-L1** `keys()`는 `importlib.import_module`의 첫 인자만 본다. `package` 인자와 `__import__`의 `level`은 무시하고, 상대 이름을 package와 합치지 않는다.
  - business_auth.py overlay에서 다음 3건이 ACCEPT된다. 6 root는 그대로다.
  - `_CLAUDE_PKG = 'inv'` 다음 `importlib.import_module('.workspace_config', _CLAUDE_PKG).configured_workspace(object(), …)` (열거 API에서 module을 증명할 수 없다)
  - `importlib.import_module('.workspace_config', 'inv')…`
  - `__import__('workspace_config', globals(), None, (), 1).configured_workspace(…)`
  - 수정: `package`와 `level`도 key로 본다. literal이 아니면 unknown이다. 상대 이름이나 0이 아닌 level은 unknown으로 둔다. 결과는 frozen과 정확히 같거나 거부다.
- **B9e-L2** `rebound()`는 `global` 선언을 Name Store/Del에만 적용하고, `import *`도 놓친다.
  - lan_pilot의 guard 앞 빈 두 줄을 `def _claude_install(): global _current_finalized_batch; from foreign_module import _current_finalized_batch`와 `_claude_install()`로 바꾸면 ACCEPT다. 그러면 :1872와 :1990이 conn을 foreign callee에 넘긴다. 9266 wrapper와 같은 escape다.
  - `from foreign_module import *`도 ACCEPT다. foreign `__all__`에 `_current_finalized_batch`를 넣을 수 있다.
  - binder에서도 global 아래 nested def, global 아래 import, star import는 소유 formal을 그대로 묶는다.
  - 수정: 함수 안에서 global로 선언된 이름에 대한 모든 바인딩(import, def/class, match capture, except 이름, Name)을 module 재바인딩으로 본다. callee scope의 `import *`도 frozen과 같지 않으면 재바인딩으로 본다. 선택으로 nonlocal에도 같은 규칙을 적용한다.
- Info:
  - I-a: callee_identity만으로는 class body의 `__new__ = lambda`나 class 정의 뒤의 `C.__init__`/`C.__new__` attribute 대입을 보지 못한다(binder fixture). 다만 full provenance에서는 use-site guard(SYMBOL/WRITE_USE)가 거부한다. `globals()[...] =`도 같다.
  - I-b: nested callee의 nonlocal 재바인딩은 binder fixture에서만 확인했다. 72028에는 nonlocal이 3건 있다. full provenance 사례는 만들지 않았다.
  - I-c: match-capture full provenance probe는 검토자 fixture의 `__import__` 때문에 다른 guard에서 거부됐다. rebound() 판정에는 쓰지 않는다.

## 확인한 것과 하지 않은 것

- seal을 다시 계산했다. producer 71개(528040 B), artifact 20개, receipt ledger 2개가 커밋된 bytes와 같다. owner current-verification의 25/11/576도 검토자 실행값과 같다.
- owner receipt 13건 중 10건은 재사용이다. 특히 새 causal 6건과 대조군 7건은 최종 alias guard 전(02:27)에 실행됐고, 사후 seal은 실행 시점 bytes를 증명하지 않는다. universe guard는 Server 수정 전의 첫 실행(02:20:59)이다. 검토자가 최종 bytes에서 같은 사례를 다시 돌렸고 결과가 일치했다.
- owner의 첫 Server false refusal, cp949 실패, flush되지 않은 tail 복구는 owner 실패와 한계로 남긴다. 제품의 negative 성공이 아니다.
- 검토자 run에서 mismatch는 12건이다.
  - full provenance 5건: 위 지적의 반례다.
  - binder 6건: L2와 I-a, I-b다.
  - 1건: alias 직접 호출에 대한 검토자 예상이 틀렸다. 실제 결과는 보수적 거부였다.
- 자원: peak 162545664 B, 888 s다. 관측값이고 quota가 아니다.
- 로컬 publication gate 8개 중 7개는 exit 0이다. canonical sync CHECK는 두 번 모두 exit 3이다.
  - 첫 CHECK의 conflict 2건은 이 branch의 오래된 vault와 최신 canonical 사이의 차이다(History 2026-11-05 Codex 착수 문서, 오류 및 해결 인덱스). gate 실행 때는 앞의 1건만 남았다. 둘 다 검토자 파일이 아니다.
  - 호출 중 state hash가 c3043aee→e4c2ccd2, e4c2ccd2→084156b4로 바뀌었다. Root가 그 사이에 apply했다. 검토자는 쓰지 않았다.
- 다시 실행하지 않은 것: owner proof 명령, model/terminal/recovery, owner 70/19/31/83/29 replay. 19 edge(16/3), 12 entry, 회계 6개, model 동일성은 owner와 Root 결과를 받은 것이고 검토자가 다시 계산하지 않았다.
- 하지 않은 것: full assembler, 3485 plan, 거대 ledger, mutant import·실행, Obsidian apply·adopt·resolve·state 쓰기, 공유 보드·registry·ADR·pin·workflow 수정, helper 사용.
- 실제 binding은 모두 NULL/HOLD이고, runtime B는 0, A1~A16은 PENDING이다. observer lock은 19 밖에 남아 있다. storage R4는 여전히 0/1이 예상된다.

## 다음 cut (Root에게)

1. Rev9f fix-only: base는 정확히 `3cccfe4d`다. 범위는 B9e-L1(import_module package, `__import__` level, 상대 이름)과 B9e-L2(global 아래 Name이 아닌 바인딩, star import, 선택으로 nonlocal)다. 반례 5건과 binder fixture를 회귀로 쓰고, 기존 대조군을 유지한다. 이어서 Claude 좁은 delta 검토를 1회 받는다.
2. 실제 수락과 Root의 별도 부여가 있은 뒤에만 NodeChannels.snapshot 단독 A7으로 간다.
- 다음 첫 행동: Root가 이 판정을 `msg_9578b8329a2e`에 전달하고 Rev9f를 결정한다. 담당은 Root, 이어서 Codex다.
