---
doc_id: "HISTORY-FLEET5-20261107-CPU-703-INTEGRATION-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 CPU 통합 소스 7033778 독립 통합 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T14:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "7033778ad3d2bc284e36f7e29be7597dbb7d9f23"
task_ids: ["FLEET5-CPU-703-INDEPENDENT-INTEGRATION-REVIEW-20261107"]
tags: ["fleet5", "independent-review", "integration", "dispatch", "claude"]
---

# CPU 통합 소스 7033778 독립 통합 검토

Orca `task_65b33b98a1b9` / dispatch `ctx_1ba53b566ab1`에서 한 실제 독립 통합 delta 검토다. 검토자는 Claude 하나다. helper·subagent·두 번째 검토자는 쓰지 않았다. 대상은 Codex가 만든 `7033778a`(branch `agent/codex/fleet5-cpu-integration-pin-r1-20261107`)다. 이미 수락된 746 전달 operation-origin guard를 이미 수락된 6d7 H12 소스 위에 올린 결합만 본다. 746·6d7 각각의 좁은 판정은 인용만 하고 다시 판정하지 않는다.

- 시작 13:49:53 KST. 직전 selector `ctx_cfee4b4aa2e7/task_7c3f0ee2e044`의 종료는 Root가 확인했다. 검토자가 다시 관측하지는 않았다.
- 새 branch `agent/claude/fleet5-cpu-703-integration-review-20261107`을 정확히 `7033778a`에서 만들었다. reset·rebase·force는 쓰지 않았다.
- Root 보드: fleet-five-orchestration HEAD `03ec1675`, Index 1.0.504, Codex 1.0.465, Claude 1.2.130, History 1.0.113. 후보 703 안의 옛 보드는 이력으로만 봤다.

## Git 사실 (검토자가 직접 확인)

- `7033778a`의 부모는 `6d7ee3d8` 하나다. 원격 author ref도 정확히 `7033778a`다.
- 변경 경로는 46개다: M `dispatch.py`, A `test_delivery_operation_origin.py`, author Evidence A 43개, author History A 1개. 다른 경로는 없다.
- `dispatch.py` SHA256 `82f02961…`(blob `6ff21a1c`), 시험 SHA256 `3dacdb63…`(blob `8592dbd8`)는 수락된 `746789a3`의 blob과 같다.
- 746 부모 `b3bbdc8d`의 `dispatch.py`는 6d7과 같은 blob `af287f3e`다. 746 부모의 docs 밖 tree는 merge-base `72028cba`와 같다.
- `git merge-tree 6d7 746` 결과 `0e01ff4a`는 충돌이 없다. docs 밖 최상위 32개 항목이 703과 모두 같다. docs가 다른 것은 746 자신의 Evidence를 가져오지 않았기 때문이며 의도된 것이다.
- `services/node-agent` tree `d3de3a19`(202개)는 6d7과 703에서 같다.
- 6d7 쪽에서 바뀐 docs·node-agent 밖 파일 12개(workflow 2, deploy/lan 2, 시험 8)는 `inv.dispatch`, `DeliveryWorker/Queue/Attempt`, `observation_only`, `cancel_only`를 참조하지 않는다. H12 Go 코드와 Python 전달 경로는 import나 symbol을 공유하지 않는다.

## 판정: ACCEPT_JOINT_703_INTEGRATION_CODE_KEEP_ACTUAL_HOLD

현재 범위의 필수 수정은 0건이다. HIGH 0, MEDIUM 0, LOW 0, INFO 3. 상세는 [review.json](../Evidence/fleet5-cpu-703-integration-review-20261107-claude/review.json)에 있다.

**제어 흐름 (`dispatch.py:336-344`, `DeliveryWorker.once`).** AST 비교로 바뀐 member는 `once` 하나뿐이다. 동작 순서는 다음과 같다.

1. 기존 try 안에서 `attempt.operation`을 한 번만 읽어 지역 변수에 둔다(336).
2. rich comparison 전에 `type(operation) is str`과 내장 tuple 포함 여부를 검사한다(337).
3. 거부하면 `ValueError`를 던진다(338). 기존 `except Exception`이 이를 SYS-0001, `not_sent=False`로 바꾼다. 이어서 `queue.finish`가 보통의 backoff/uncertain 경로를 탄다. 거부된 값으로는 `deliver`를 부르지 않는다.
4. 두 kwarg는 지역 변수로 만든 정확한 bool이다.

**operation 식별.** `DeliveryQueue.acquire`는 operation에 내장 literal `'cancel'/'observe'/'execute'`만 넣는다(대입 3곳). 같은 값을 UPDATE와 `delivery_reserved` event에 기록한 뒤 frozen `DeliveryAttempt`를 만든다. 따라서 실제 경로는 항상 guard를 통과하고, 전달 flag 값은 예전 식과 같다. 거부·영속·재시도 쪽에서 `DeliveryQueue.finish`는 6d7과 AST가 같다. 새 SQL·column·event·migration·상태 전이는 없다. `NodeDelivery.deliver` 서명도 그대로다. `dispatch.py`에 새 import는 없다. 시험이 import하는 것은 `types`, `pytest`, `inv.containment`, `inv.dispatch`뿐이고 basename 충돌도 없다. `tests/conftest.py`, `pyproject.toml`, `core.yml`, `backend.yml`은 merge-base 이후 바뀌지 않았다.

- **J703-I1 (INFO).** `finish`(`dispatch.py:284`)는 `not_sent`가 참일 때만 `attempt.operation`을 다시 읽는다. guard 거부 경로는 항상 `not_sent=False`라서 여기에 닿지 않는다. 실제 attempt는 내장 literal을 갖는다. 703 이전부터 있던 코드이고 바뀌지 않았으며, 시험의 spy 주석에도 적혀 있다. 통합 결함이 아니다.
- **J703-I2 (INFO).** 거부된 origin은 전용 terminal code가 아니라 일반 SYS-0001로 남고, 상한이 있는 재시도와 함께 uncertain 상태가 된다. 실제 acquire에서는 도달할 수 없으므로 fail-closed defense-in-depth다. 별도 오류 코드는 FUTURE 관측 카드의 선택 사항이며 지금 필요하지 않다.
- **J703-I3 (INFO).** 24 case는 실제 `once`를 collaborator만 바꿔 돌리며 SQL을 주장하지 않는다. 유효 operation의 실제 PG queue 동작은 703의 hosted Core/Backend에 있는 기존 suite가 맡고, 둘 다 성공했다. 746의 BASE causal RED는 Root가 원래 소스에서 돌린 것이다. 703에서 다시 돌리지 않았고, `once`가 746과 바이트까지 같으므로 이 판정에 필요하지 않다.

## 증거 귀속

- **703 CI (검토자의 읽기 전용 `gh api` 확인).** 세 run 모두 head `7033778a`, author branch, `workflow_dispatch`, attempt 1, conclusion success다. Docs `42335285577` job `128290723992` 19/19. Core `42335287638`: core job `128290730592`은 success 42에 skip 6, S01 job `128290730407`은 success 16. skip 6개는 모두 선언된 dispatch input 조건 step이다(7–10 peer-phase proof, 37–38 S08). Backend `42335289761`: 3.14 job `128290737435`은 18에 skip 2(`matrix.python-version == '3.12'` 조건 step 7, 9), 3.12 job `128290737705`은 20, MLflow job `128290737412`은 9. 실행·artifact 다운로드는 하지 않았다.
- **수치 귀속.** Core XML 9382 = 9336 pass + 46 skip, origin 24 case, Go 146/550, Docker 1/4(hosted CI이며 5대 실장비가 아니다), Backend 각 8977/75/2, MLflow 3은 Root 검증 receipt `.work/joint-703-final-ci-artifacts-root-verified.json`(`c06c7345…`)에서 왔다. 검토자는 이를 DATA로만 읽었다. 검토자가 XML·log ZIP을 직접 내려받거나 파싱하지 않았다. author의 로컬 post-CI receipt(`e6240679…`, `4da8c280…`)는 703 CI tree에 들어 있지 않다. 검토자는 읽지도 바꾸지도 않았다.
- **검토자 DATA 검사.** [integration_data_checks.py.txt](../Evidence/fleet5-cpu-703-integration-review-20261107-claude/integration_data_checks.py.txt)를 Python 3.10 `-I`로 두 번 돌렸다. 1회는 scratch 출력, 2회는 [integration-data-checks.json](../Evidence/fleet5-cpu-703-integration-review-20261107-claude/integration-data-checks.json) 출력이다. 둘 다 exit 0, 18/18이다. git argv 읽기와 blob `ast.parse`일 뿐이며 제품 import·실행은 없다.
- **인용한 구성 검토(다시 하지 않음).** 746 `dc18f668` ACCEPT_NARROW_CODE_KEEP_HOLD. 6d7 `0761de18` ACCEPT_NARROW_PRIVATE_MATH_AND_SCOPED_GUARD_CODE_KEEP_HOLD(선택 H12C-L1은 남은 필수 결함이 아니다). b51 `f489e7e9`는 OPG-L1을 collector.collect()+probe.evaluate_discovered에 대해서만 닫았다. `finite.current_world`는 여전히 base-seeded이고, legacy INSTANCE:operation은 REFUSED다.
- **실행하지 않은 것.** 제품 import/app, pytest, Go/compiler, crypto, Node/browser/runtime, SSH/Docker/PG, install/PKI/trust/OS/process/credential, 새 Core/Backend/Frontend CI, 옛 finite corpus/main(), 746 causal RED 재실행, artifact/log 다운로드. 새 fresh_cpu_admission 후보 소스는 읽지 않았다.

## 남은 것과 다음 담당

이 수락으로 닫히지 않는 것: Original19 HOLD, acceptedBaselineDischarges 0, runtime B0, A1–A16 PENDING, H1–H7/H3EA/RD NULL_HOLD, raw7 UNREGISTERED, A01–A40 NOT_RUN, 5대 전체·전체 프로그램 미완료. CPU Node 하나의 실제 등록, project link, 새 자원 관측, 요청자가 아닌 서로 다른 두 사람의 Run 승인, 실행된 명령과 audit은 아직 증명되지 않았다. 사설 H12 결과는 runtime 권한을 뜻하지 않는다. install·deploy·merge·grant 권한은 주지 않았다.

다음 첫 행동은 Root/Codex 집계자가 이 판정을 받고 다음 범위를 정하는 것이다. 첫 실제 CPU preflight는 Root 담당이다. 로컬 문서 gate와 sync CHECK는 [local-doc-gates.txt](../Evidence/fleet5-cpu-703-integration-review-20261107-claude/local-doc-gates.txt)에 있다. 검토 SHA와 Docs run은 push 뒤 Orca worker_done으로 Root에 보고한다.
