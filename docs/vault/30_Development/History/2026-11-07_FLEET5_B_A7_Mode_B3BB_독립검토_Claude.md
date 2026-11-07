---
doc_id: "HISTORY-FLEET5-20261107-B-A7-MODE-ORIGIN-B3BB-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 B A7 mode-origin R1 b3bb 조건부 source 증거 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T09:00:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "b3bbdc8d92a39f2f797a7680deb2770d6f705af0"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105", "FLEET5-B-A7-MODE-ORIGIN-R1-20261107"]
tags: ["fleet5", "independent-review", "b-contract", "a7", "claude"]
---

# B A7 mode-origin R1 b3bb 조건부 source 증거 독립 검토

Orca `task_696b2783bc0b` / dispatch `ctx_6b18bf1ef5b4`에서 한 실제 독립 검토다.

시작 조건:

- 직전 작업 `task_ce76beac4d2d/ctx_8cd16f1141a3`가 succeeded/settled/exited/released인 것을 확인했다.
- managed worktree가 `8141a49b`에서 clean인 것도 확인했다.
- 그 작업과 K2 H12 8141 검토, Root의 R2 design 허가 `msg_e41b206771c3`는 B mode 밖이다. 다시 열지 않는다.

관련 메시지:

- owner: Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`.
- pending 질문: `msg_5fcc462b63c7`.
- Root 허가: `msg_ec880f3ed724`.
- helper와 두 번째 검토자는 쓰지 않았다.

대상과 범위:

- 대상: `b3bbdc8d`, 직접 부모 `969030db`.
- 추가 57개, 수정·삭제 0. 모두 author Evidence 경로와 History 1개 안이다.
- 제품 기준 `72028cba`는 그대로다(product delta 0).

먼저 읽은 것:

- 실제 R2 검토 `14523889`의 History, review.json(INFO I1/I2/I4/I5/I6), commands.json, 12행 결과, attempt 1·2 log를 그 commit에서 직접 읽었다.
- attempt 1의 exit 1은 그 검토자의 missing-frozen-path precheck 버그였다. pre-fix driver는 따로 남기지 않았다.
- 이 12행은 이번 mode coverage로 세지 않는다.
- Root는 read-only로 읽었다: HEAD `28356eb2`, Index 1.0.491, Claude board 1.2.130, `.work/a7-mode-origin-r1-root-cut.txt`, `b-mode-origin-review-spec.txt`, `b-mode-source-root-verified.json`.

사전 확인 (committed bytes 기준, owner 명령은 다시 돌리지 않았다):

- manifest `25229c0c…`의 55개 파일과 History hash가 모두 맞다.
- graph `18eb75fd…`, auxiliary `99ae3d9e…`가 Root 값과 같다.
- review 원본 사본 11개는 1452 blob·objectID와 byte가 같다. immutable predecessor 16개도 모두 같다.
- final 영수증 11개는 exit 0이고, producer hash가 전후로 같다.
- control 입력 5개의 hash는 결과와 같고 모두 compile된다.
- Root의 Docs `42312934123` 검증에 의존했고, 다시 확인하지는 않았다. 추적되지 않는 CI 이후 영수증 4개는 입력으로 쓰지 않았다.

**판정: CONDITIONAL_MODE_SOURCE_EVIDENCE_ACCEPT_KEEP_19_HOLD.**

- node_transport.py:280의 A7_PURPOSE_PROVENANCE **하나**에 대한 유한 source graph를 정직하고 정확히 한정된 **조건부** 후보로 수락한다.
- 고정 기준은 72028, author b3bb다.
- operational discharge는 아니다. acceptedBaselineDischarges 0, original 19는 그대로다.
- accepted18, source inclusion, runtime, admission, 13번째 entry, NORMAL/OBSERVATION 표지에서 나오는 mode permission은 모두 부여하지 않는다.
- HIGH/MEDIUM은 없다. LOW 1건(A7M-L1)은 필수 조건으로 넘긴다. 72028 증거 자체는 바뀌지 않는다. INFO는 4건이다.
- 상세: `docs/vault/30_Development/Evidence/fleet5-b-a7-mode-b3bb-review-20261107-claude/review.json`.

## 확인한 실제 source 사실

operation 값의 출처:

- `DeliveryQueue.acquire` 안의 `operation` Assign은 정확히 세 개다.
  - [170..174]: literal `"cancel"`/`"observe"` IfExp. 조건은 `row["operation"]`와 비교하지만 저장되는 값은 literal이다.
  - [184]: `"cancel"`.
  - [203]: `"execute"`.
- `row['operation']`가 값으로 전달되는 곳은 없다.

DeliveryAttempt와 소비자:

- None이 아닌 return은 `DeliveryAttempt` [243..251] 하나뿐이다. 나머지 다섯은 `return None`이다.
- 여섯 번째 인자 `operation`은 `@dataclass(frozen=True)`의 여섯 번째 field와 맞는다.
- 관련 method에는 decorator, async, generator가 없다.
- `str` annotation은 runtime type 증거로 쓰지 않았다.
- once 안에서 attempt store는 [327] 하나다. None 분기는 return한다.
- deliver 호출은 try 안의 [336..341] 하나다. 오늘 field 값 검증은 없다.

callee 쪽:

- `NodeDelivery.deliver`의 keyword-only 기본값은 False/False다. 두 flag는 다시 대입되지 않는다.
- snapshot 인자는 `observation_only or cancel_only`다.
- `NodeChannels.snapshot`은 `not observation_only`로 truth-test한다(126/136). 그래서 author DATA의 snapshotTruthiness 열은 실제 body와 맞다.

전제 아래의 표:

- 다음이 모두 참이라고 **가정한다**: dataclasses/generated initializer/반환 객체/plain field가 genuine하고, receiver가 genuine하게 bound되어 있고, 모델 밖의 frame·heap 변경이 없다.
- 그 가정 아래: execute→(F,F) NORMAL, observe→(T,F) OBS, cancel→(F,T) OBS.
- builtin type/str/bool binding과 receiver identity는 여전히 전제다.
- `or`는 operand를 반환한다. 'tag'는 str로 남고 bool로 바뀌지 않는다.
- 수락된 NORMAL/OBS body 표는 참조만 하고 손대지 않았다.

## 범위 안 완전성 (선언된 selector 기준)

- **재현성:** git grep을 쓰지 않았다. 같은 pattern의 Python regex를 72028 세 root의 `.py` 398개 blob 전체에 적용했다. 결과는 author의 25개 경로·blob sha256과 같다.
- **공개 superset:** 어간이 들어 있는데 selector에 걸리지 않는 54개 파일은 workflow_dispatch/execution_deliveries 같은 식별자이거나 산문이다. 단어 `deliver`가 있는 6개는 모두 docstring/주석이다. 선언된 selector 안에서 빠진 관련 경로는 없다.
- **AST census:** 직접 호출은 NodeDelivery 3, DeliveryWorker 4, DeliveryQueue 1, DeliveryAttempt 1이다. 이는 inventory 9행과 같다.
  - 네 이름의 non-call 참조(factory 탈출, subclass, base, annotation)는 0이다.
  - `.deliver`는 1개(dispatch.py:336)다.
  - delivery/queue/operation/channels attribute store는 dispatch:315, node_transport:231, tool:107뿐이다.
  - 그 이름들로 하는 getattr/setattr는 0이다. import event는 23개다.
- **forwarding:**
  - worker.py: delivery는 [122]에서 한 번 저장된다. 실제 DeliveryWorker 지점은 [142]다. Root의 starting 133은 틀렸고, author의 142가 맞다.
  - tool: setup [107]의 `a.delivery`를 161과 172로 넘긴다. faithful namespace, no-replacement 전제 아래서다. 145는 NodeDelivery를 inline으로 만든다.
- **명시된 경계:** computed import/alias(예: `importlib.import_module('inv.dispatch')`, 여러 줄 괄호 import), heap/frame 변경, 25개 밖의 reflection은 범위 밖이다. scopeBound가 이를 적는다. 전체 Python heap/language 완전성은 요구하지 않는다.
- path 선택, mode 값, receiver, DB owner, 실제 permission은 서로 다른 것으로 둔다. 나머지 DB owner 10과 reverse root 8은 다루지 않았고 HOLD로 남는다.

## owner 대조군 6개

- 모두 네 anchor 파일에서 `rule()`을 직접 평가한다. 이전 full-use-site guard는 관여하지 않으므로 guard 거부가 mode 원인으로 계산되지 않는다.
- actual / benign 주석: CONDITIONAL. current witness가 이동된 source에서 다시 계산된다.
- forwarding 변경: earlier edge 2개가 성립한 뒤 MODE_FORWARDING_CHANGED.
- dynamic(203→`row["operation"]`): earlier edge 3개가 성립한 뒤 UNRESOLVED_DYNAMIC_OPERATION_ORIGIN.
- foreign rebound: EARLIER_CALLEE_BINDING. EARLIER_BINDING_PRECONDITION으로 따로 표시되고, 나중 원인으로 계산되지 않는다.
- truthiness/or: literal builtin DATA다. foreign type은 UNKNOWN으로 둔다.
- 개발 중 재실행이나 1452 행은 세지 않는다.

## 검토자 대조군 (AST 전용, 직렬 2 process)

실행:

- `reviewer_mode_probes.py`: 08:53:58~08:54:47 KST, exit 0, peak 120668160 B, 46.7 s.
- `reviewer_mode_future_rule.py`: 08:57:27~08:57:29, exit 0, peak 29687808 B.
- 둘 다 한 번씩 실행했다. 제품·mutant는 import하지도 실행하지도 않았다. pinned rule/analyze는 parse만 한다.

| 대조군 | 층 | 결과 | 의미 |
| --- | --- | --- | --- |
| 173 `"observe"`→`"observed"` | RULE | earlier 4개 뒤 OPERATION_LITERAL_DOMAIN_CHANGED | domain 검사가 인과적이다 |
| 여섯 번째 인자→`"execute"` | RULE | ATTEMPT_CONSTRUCTOR_FORWARDING_CHANGED | 생성자 forwarding이 인과적이다 |
| `cancel_only == "observe"` | RULE | MODE_FORWARDING_CHANGED | 두 번째 keyword도 검사한다 |
| acquire decorator | RULE / ANALYZE | rule CONDITIONAL, card는 이전 guard SYMBOL로 UNRESOLVED | A7M-I1 |
| `worker.delivery = object()` | ANALYZE | rule CONDITIONAL, card는 이전 guard WRITE_USE로 UNRESOLVED | A7M-I1 |
| 두 번째 무제약 `.deliver(..., observation_only="foreign-tag")` (lan_pilot.py) | ANALYZE | **card CONDITIONAL 유지**, deliver CALL 2, guard clean | **A7M-L1** |
| 제안 코드를 텍스트로 적용 | RULE | MODE_FORWARDING_CHANGED | A7M-I3 |

## 발견

### A7M-L1 (LOW, 필수 조건으로 넘김)

- **source:** mode.py 119행(card status)과 `rule()` 43~44행.
- **층:** auxiliary status 판정. 72028 증거가 아니다.
- **valid input:** 72028에 tools/lan_pilot.py 끝에 `def _reviewer_second_deliver(delivery, node, permit): return delivery.deliver(node, permit, observation_only="foreign-tag")`를 붙인다.
  - syntax는 유효하다. 25 parsed, 생성자 9, guard clean이다.
- **결과:** status가 CONDITIONAL_SOURCE_CANDIDATE…로 남는다.
  - status는 모든 reference가 CALL인지만 본다.
  - `rule()`은 once 안의 deliver 호출 하나만 요구하고, universe 전체의 하나는 요구하지 않는다.
  - 그래서 두 번째 호출자는 bool이 아닌 truthy operand를 280의 `or`로 바로 넘길 수 있다. 후보는 이 값이 dispatch:336에서만 온다고 말한다.
- **실제 source 영향:** 없다. 72028의 universe에는 `.deliver`가 정확히 하나다. 검토자 AST census로 따로 확인했다.
- **최소 수정** (mode.py를 72028이 아닌 source에 다시 돌리기 전, 그리고 향후 code card에서 할 일):
  - deliverReferences가 MODE_FORWARD_ARGUMENT_BINDING witness(path/span/expressionSHA256)와 같은 한 행일 때만 통과시킨다.
  - 아니면 구별되는 reason(예: DELIVER_REFERENCE_SET_CHANGED)으로 UNRESOLVED를 낸다.
  - 인과 대조군 하나를 더한다: 두 번째 deliver CALL이 earlier guard가 아니라 그 reason으로 UNRESOLVED가 되는지 본다.

### INFO

- **A7M-I1:** method decorator와 receiver field 교체 mutant는 card 수준에서 이전 guard로만 거부된다. rule 자체는 CONDITIONAL이다.
  - fail-closed는 맞다. "genuine bound methods/receivers" 전제와도 일치한다.
  - 72028에는 그런 decorator나 store가 없다. decorator_list 검사는 선택 사항이다.
- **A7M-I2:** `DeliveryQueue.finish:284`의 `attempt.operation == "execute"`는 not_sent가 truthy일 때만 따로 읽힌다. 280 대상 밖이다.
  - 제안의 "한 번 읽기"는 deliver 경계에 한정된다.
  - DomainError/not_sent가 아니라 ValueError를 쓰기 때문에 거부된 값은 finish에서 다시 읽히지 않는다(short-circuit).
- **A7M-I3:** pinned rule은 오늘의 once 텍스트에 맞춰져 있다. 제안을 적용하면 MODE_FORWARDING_CHANGED가 난다.
  - 구현 card는 static mode rule을 다시 정해야 한다: capture 하나가 guard 바로 앞, 정확한 guard AST, 두 keyword가 capture된 local, once 안의 다른 operation store 없음, A7M-L1.
- **A7M-I4:** 1452의 I1/I2/I4/I5/I6은 그대로다.

## 향후 코드 제안 DATA 평가

**판정: PRECISE_MINIMAL_FUTURE_CONTRACT_DATA_ACCEPT_NOT_GRANTED.** 코드 텍스트 수정은 필요 없다.

DATA 근거:

- guard 식을 검토자 값에 대해 builtins type/str만으로 평가했다. 이는 Python 의미 DATA이고, 제품 검증이 아니다.
- 'execute'/'observe'/'cancel'만 통과한다.
- 'Execute', '', b'observe', None, 1, 적대적 str subclass, foreign `__eq__` 객체는 모두 거부된다.
- custom `__eq__`/`__ne__`/`__hash__`/`__bool__` 호출은 0이다. `type(x) is not str`가 builtin bool로 `or`를 short-circuit해서 `in`보다 먼저 끝나기 때문이다.
- 통과한 값의 flag와 `or` 결과는 builtin bool이다.

배치 (72028 텍스트에 적용, parse만):

- capture와 guard가 기존 try의 첫 두 문장이다.
- raise는 try 안이다. `except Exception`이 이를 SYS-0001, not_sent=False로 바꾸고, finish는 'uncertain' backoff로 간다.
- once 안에서 attempt.operation은 한 번만 읽힌다. property에서 예외가 나도 같은 handler가 받는다.

없애는 것과 없애지 않는 것:

- 이 경계 하나에서 foreign/subclass/stateful 값 비교 전제만 없앤다.
- 남는 것: builtin binding, genuine receiver, property read 호출 자체, 앞선 ContainmentReconciler/acquire 효과(없거나 pure하다고 하지 않는다), finish:284, 보편적 callback 격리.
- NodeDelivery API와 mode permission은 바뀌지 않는다.

넘길 조건:

- **C1:** static mode rule을 다시 정하고 A7M-L1을 강제한다.
- **C2:** author의 테스트 목록에 더한다.
  - 거부 값이면 finish(error_code='SYS-0001', not_sent=False)를 부르고, deliver는 부르지 않고, operation을 다시 읽지 않는다.
  - capture 중 예외가 나도 같은 handler가 처리한다.
  - guard를 제거하면 foreign 값 사례가 다시 생긴다.

부여는 없다. 구현하지 않았다. product는 72028, delta 0이다.

## 남는 HOLD와 하지 않은 것

남는 HOLD:

- 후보 상태: CONDITIONAL_SOURCE_CANDIDATE_RUNTIME_AND_OWNER_PREMISES_PENDING, acceptedBaselineDischarges 0.
- 원래 19 blocksGrant가 모두 남는다(NodeDelivery purpose 1, DB owner 10, reverse root 8). accepted18은 없다.
- runtime B 0, real binding 전부 NULL/HOLD, A1~A16 PENDING, 전체 fleet 미완.
- 다음은 그대로다. Root가 검증했고, 검토자는 다시 계산하지 않았다.
  - 12 entry, 19 edge(16/3).
  - 598/757/1071/21/573 outside/218.
  - model, lifecycle, stage/order.

하지 않은 것:

- owner mode/controls/run/docs 명령.
- 33/49 corpus, 수락된 body, R2 guard polish, model/recovery, 523 assembler, 3485 plan, 전체 B.
- 제품·mutant import나 실행, PG/네트워크/crypto/host/clock/permission 작업.
- Obsidian apply/adopt/resolve/state 쓰기, 공유 보드·registry·ADR·workflow 수정.

canonical CHECK와 gate:

- 작성 전 CHECK: exit 0, conflict 0. state는 `7b82bf9f…`이고 전후가 같다.
- author 때의 `5eea4626…`와 다른 것은 그 사이 Root가 적용했기 때문이다. 보존만 하고 adopt하지 않는다.
- 작성 뒤 local gate 8개는 `local-doc-gates.txt`에 실제 exit와 state hash로 남긴다.

## 다음 (Root에게)

- 다음 첫 행동: Root가 이 조건부 mode-source 증거 수락(KEEP 19 HOLD)을 기록하고, 작성자의 `msg_5fcc462b63c7`에 답한다.
- 좁은 향후 code card를 허가할지는 Root가 결정한다. 허가한다면 A7M-L1과 C1/C2를 함께 넘긴다.
- 담당은 Root다. 검토자는 아무것도 부여하지 않고, 다음 범위를 시작하지 않는다.
