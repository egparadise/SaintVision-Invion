---
doc_id: "HISTORY-FLEET5-20261107-B-A7-OPERATION-7467-CODE-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 B A7 operation guard 746789a 독립 CODE 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T11:30:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "746789a36091c8601afea23fe176069e2fa7d87b"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105", "FLEET5-B-A7-OPERATION-7467-INDEPENDENT-CODE-REVIEW-20261107"]
tags: ["fleet5", "independent-review", "code-review", "b-contract", "a7", "claude"]
---

# B A7 operation guard 746789a 독립 CODE 검토

Orca `task_1e856e06e90a` / dispatch `ctx_fe0931cf5bde`에서 한 실제 독립 CODE 검토다. 검토자는 구현 작성자가 아니다.

시작 조건:

- worktree HEAD `746789a3`, 부모 `b3bbdc8d`를 직접 확인했다. 자동 branch가 달라 `agent/claude/fleet5-b-a7-operation-7467-code-review-20261107`를 같은 SHA에서 새로 만들었다(reset/rebase/force 없음).
- 직전 작업 `ctx_2e3e33bdc879`의 succeeded/settled/exited/released는 Root 기록에 의존했고 다시 조회하지 않았다.
- helper와 두 번째 검토자는 쓰지 않았다.

관련 작업:

- owner: Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`, branch `agent/codex/fleet5-b-a7-operation-guard-r1-20261107`.
- remote readback: 그 branch = `746789a3`.

## 범위

- 대상: `746789a3`, 직접 부모 `b3bbdc8d`. name-status A93/M1이다.
- docs가 아닌 경로는 정확히 둘이다: `services/control-plane/src/inv/dispatch.py`(M), `tests/core/test_delivery_operation_origin.py`(A).
- 제품 blob sha256 `82f02961…`(15823 B), 시험 `3dacdb63…`(9520 B), BASE dispatch `4a334285…`. Root 시험 bytes, WIP02 항목과 같다.

먼저 읽은 것:

- AGENTS.md, `skills/service-integration` 1.0.0, `skills/agent-delivery` 1.1.0.
- Root workspace `fleet-five-orchestration-20261105` HEAD `e459124a`: Index 1.0.498, Codex board 1.0.459, Claude board 1.2.130. 읽기만 했다.
- Root `.work` 기록: `b-operation-7467-ci-root-verified.json`, `b-operation-wip02-root-verified.json`, `b-operation-actual-pytest-root-verified.json`, `b-operation-wip02-root-publication-step.txt`, `b-operation-wip01-root-compatibility-decision.txt`. sha256은 review.json에 있다.
- 직전 mode 검토 `e75b051d`의 review.json(LOW A7M-L1, C1, C2, INFO A7M-I1..I4). 이것은 source 증거 수락이었고 CODE 수락이 아니다.
- candidate Evidence: finite_compatibility, check_finite_compatibility, operation_proof(상수·scope·analyze), finite proof/control 21행, inputs, legacy refusal, raw 표현 기록.

## 판정: ACCEPT_NARROW_CODE_KEEP_HOLD

수락 범위:

- `dispatch.py` 336–343의 DeliveryWorker.once 변경만이다: capture 1회, 정확한 builtin str OR 3-literal guard(기존 try 안에서 ValueError), captured local로 두 비교.
- 새 unit 시험 파일도 포함한다.
- A7 mode 값 경계에 대한 올바르고 최소인 fail-closed 보강이다.

수락하지 않는 것:

- original 19 HOLD, acceptedBaselineDischarges 0, runtimeB 0은 그대로다.
- real bindings NULL, actual authority NULL_HOLD, A1–A16 pending도 그대로다.
- 5대 전체와 program은 미완료다.
- legacy use_sites는 그대로 REFUSED `DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:INSTANCE:operation`이다.
- 새 finite 분류 `EXACT_CAPTURE_GUARD_DELTA_COVERED_WITH_LEGACY_REFUSAL_PRESERVED`와 legacy 상태는 별개다.
- merge·deploy·역할 부여·NodeDelivery mode 허가는 없다.

심각도:

- HIGH/MEDIUM 없음.
- LOW 1개(OPG-L1): proof 도구의 source-set 발견 문제다. 이 candidate의 필수 수정은 아니고, 재사용 조건으로 넘긴다.
- INFO 5개(OPG-I1..I5).

## 제품 코드 확인 (검토자 독자 AST, import/실행 없음)

- **delta**: 최상위 16문 중 DeliveryWorker만 다르다. 그 안에서는 once만, once 안에서는 Try 하나만 다르다.
- handler·orelse·finally와 once signature·decorator는 BASE와 같다.
- capture·guard는 검토자가 손으로 만든 AST와 같다.
- deliver 호출은 두 Compare.left만 `attempt.operation` → `operation`으로 바뀌었다. literal `'observe'`/`'cancel'`은 그대로다.
- DeliveryQueue(acquire/finish SQL) AST는 BASE와 같다.
- **guard 의미**: `type(x) is not str`가 builtin bool로 `or`를 먼저 끝낸다. 그래서 거부 값의 `__eq__/__ne__/__hash__/__bool__`은 호출되지 않는다.
- 검토자 DATA에서 isinstance 변형은 str 하위형의 `__eq__`를 부른다. 그래서 정확 type 검사가 필요하다.
- **예외 경로**: ValueError는 기존 `except Exception`에서 SYS-0001, not_sent=False가 된다. finish는 `not_sent and attempt.operation == "execute"`를 다시 읽지 않고 기존 uncertain backoff로 간다. 속성 읽기가 raise해도 같은 handler로 간다.
- **정상 경로 동일성**: DeliveryAttempt 생성은 dispatch.py:243 하나다. acquire의 operation 저장은 literal뿐이다(170 cancel/observe, 184 cancel, 203 execute).
- 그 class는 `@dataclass(frozen=True)`이고 본문은 AnnAssign만 있다. 그래서 production에서 guard는 발동하지 않고, 세 mapping은 BASE와 같다.
- **builtin 바인딩**: dispatch.py에는 type/str/ValueError 바인딩, star import, globals/exec/setattr류 이름이 없다.
- 저장소 전체 1439개 .py에도 dispatch/builtins 모듈 속성으로 그 이름을 저장하는 곳이 없다.
- **deliver 참조**: selector 루트 안에서 `.deliver`는 dispatch.py:339의 직접 호출 하나뿐이다. 나머지 41개는 tests·docs Evidence 안에 있다.

## 시험 확인

- 정적 확인: 24개 항목이다(3+14+1+4+2).
- 실제 `inv.dispatch`를 import하고, `object.__new__(dispatch.DeliveryWorker)`로 만든 객체의 실제 once를 호출한다.
- monkeypatch는 `containment.ContainmentReconciler` 하나다. 나머지는 collaborator spy다.
- 다음 조건을 모두 assert한다:
  - 읽기 1회, 정확한 bool 식별, rich 호출 0.
  - finish `('SYS-0001', False)`.
  - raise하는 capture.
  - None-attempt 분기, stopped 후속 순서.
- Root PC3 실측은 author나 검토자가 돌린 것이 아니다: GREEN 24/direct 0. 실제 BASE RED 1/direct 1, 205행, deliveries [(True, False)].
- 검토자는 Root packet 안의 hosted Core `core-tests.xml`(7a93f834…)을 읽었다. 새 24건은 모두 통과했고, 전체 9283/skip 46/fail 0/error 0이다.

## finite proof 확인

- author 21개 control은 모두 새 layer 원인이다. 실행된 mutant나 runtime이 아니라 AST/source 변형이다.
- 검토자 replay(exit 0): 고정 `evaluate()`를 실제 현재 25-path 세계에 적용했다(working 파일과 HEAD blob이 같다). 결과는 reason None이다.
- 바뀌지 않은 legacy `analyze()`는 위 refusal 1건을 그대로 낸다. clean은 false다.
- `check_finite_compatibility.main()`과 다른 점:
  - 게시 전 context assert(tracked==[dispatch])를 돌리지 않았다. commit 후에는 맞지 않는 assert이고, 검토자 name-status로 대신 확인했다.
  - emit과 파일 쓰기가 없다. git status는 replay 전후가 같다.
- 검토자 control 9개는 첫 실행에서 모두 예상대로였다:
  - hoist-before-try, isinstance, 순서 바꿈, set literal, DomainError → GRAMMAR.
  - handler 축소, finish short-circuit 제거, decorator → WHOLE_MODULE.
  - AST가 같은 주석·괄호 변경 → None.

## carried 조건

- **A7M-L1 충족.** reference 계약은 25-world 전체 deliver 참조가 정확히 1개이길 요구한다. 그 참조는 Call.func identity를 갖고, 같은 종류 witness(path/fileSHA/function/span/expressionSHA)가 forward 호출과 같아야 한다.
- 원래 A7M-L1 mutant(`abb17b22…`)와 non-call 참조 control은 `DELIVER_REFERENCE_SET_CHANGED`로 거부된다. 남는 새 경로 발견 문제는 OPG-L1로 넘긴다.
- **C1 충족.** closed grammar에 whole-module AST, other-24 bytes, owner 동등성이 함께 걸려 있다.
- **C2 충족(OPG-I2 조건부).** 거부 값은 finish SYS-0001/False, deliver 없음, 추가 읽기 없음이다. raise하는 capture도 같은 handler다. BASE RED가 foreign 값 전달을 재현한다.

## 발견

- **OPG-L1 LOW**:
  - 위치: `finite_compatibility.py` 42–43(current_world)과 186(path set). blob `7b245536…`.
  - 문제: 경로 집합을 BASE에서 가져온다. 그래서 `SOURCE_WORLD_PATH_SET_CHANGED`는 주입한 세계에서만 발동하고, 평가 tree의 새 파일은 찾지 못한다.
  - 746789a에는 영향이 없다: 검토자 P06이 HEAD tree selector를 돌려 같은 25개를 얻었고, 나머지 24 blob도 같다. name-status도 맞다.
  - 재사용 전에는 평가 tree에서 selector를 돌린다. 제품 변경은 필요 없다.
- **OPG-I1**: 거부 시험은 guard의 ValueError와 다른 사전 예외를 구분하지 못한다. AST proof와 인과 RED가 있어 충분하다.
- **OPG-I2**: guard 제거 증거는 실제 BASE RED이다. capture-only mutant를 실행한 증거는 아니다.
- **OPG-I3**: finish:284의 별도 읽기(A7M-I2)는 변경이 없다. production에서는 도달하지 않는다.
- **OPG-I4**: 무효 origin은 기존 SYS-0001 backoff로 간다. 새 liveness 영향은 없다.
- **OPG-I5**: raw 3496 B(`8a74f36b…`)는 Git 단독 경로에 없다.
  - WIP01/WIP02 ZIP에는 있고, wrapper `5c6d7e0b…`의 rawUTF8에 있다. 검토자가 다시 hash했다.
  - 옛 manifest는 frozen ZIP 기술이다. Root post-CI packet `6aed7e34…`는 local uncommitted 증거다.

## 상속 CI (Root 검증, 검토자는 gh metadata와 JUnit을 읽기만 함)

- Docs `42323636412`: job `128253748260` success=19.
- Core `42323639274`:
  - `128253756121` success 42 / 조건부 skip 6, `128253756488` success 16.
  - artifact digest `581f0066…`는 검토자가 다시 hash했다.
  - Go 178 PASS와 binary metadata는 Root 검증에만 의존했다.
- Backend `42323642052`:
  - 3.14 success 18 / skip 2, 3.12 success 20, MLflow success 9.
  - 각 Python 8879 pass / 75 skip / 2 deselect / 0 fail은 Root 공식 log 기준이다. per-case XML은 없다.
- 모두 workflow_dispatch, attempt 1, head `746789a3`다. 다시 돌리거나 dispatch하지 않았다.

## 남은 것과 미실행

- 미실행:
  - pytest, 제품·시험 import·실행, author의 쓰기 스크립트와 `main()`.
  - Go/Node/browser/전체 suite, PG/네트워크/SSH/Docker/PKI/host.
  - 이 검토용 Core/Backend dispatch, Obsidian apply/state write.
  - 검토자 probe peak memory(측정 안 함).
- incident: `fleet5-compute-storage-contract-20261107/never.txt`(2 B)는 Root 기록대로 보존 중이다.
  - 검토자는 그 파일을 건드리지 않았고 차단 사유로 보지 않는다.
  - author workspace의 untracked 영수증 14개, raw 원본, post-CI 파일도 남아 있다. 전체가 clean하다고 주장하지 않는다.

Evidence: `docs/vault/30_Development/Evidence/fleet5-b-a7-operation-7467-code-review-20261107-claude/` (review.json, commands.json, reviewer probe와 replay driver 및 결과, local gate 기록).

다음 첫 행동은 Root가 맡는다:

- 746789a의 once delta와 시험을 ACCEPT_NARROW_CODE_KEEP_HOLD로 기록한다.
- finite_compatibility를 재사용하면 OPG-L1을 조건으로 건다.
- 19/runtime/authority HOLD를 유지하고 통합을 결정한다.
- 검토자는 아무것도 부여하지 않는다.
