---
doc_id: "CLAUDE-S03-DB-AC03-EVIDENCE-RUNNER-DESIGN-001"
title: "S03-DB AC-03 acceptance Evidence runner 설계 — 제한 컨테이너 출력 bytes/hash·금지 경로/명령 거부·lease 회수·Evidence ID를 고정 SHA에서 한 번에 묶는 runner (기존 collect_container_evidence.py + S03 시험 재사용)"
version: "1.0.0"
status: "proposed-review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T06:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S03-DB"]
tags: ["S03-DB", "AC-03", "evidence", "runner", "container", "lease", "sandbox", "claude", "design"]
---

# S03-DB AC-03 acceptance Evidence runner 설계 (1쪽)

> [!warning] 설계 단계
> 차단 지도 [[2026-09-22_21-55-00_KST_review_done_차단지도_Codex]] S03-DB 행("컨테이너 출력 bytes/hash·금지 명령·lease 회수·Evidence ID 수집 runner", U1~U6 간접)의 Claude 몫. 이 페이지는 구현 전 설계이며 코드·계약·registry·ontology를 바꾸지 않는다. 구현은 카드 13(S02-DB, PR #120)과 같은 형태로 진행한다.

## 1. 이미 있는 것 (재사용, 새로 만들지 않음)

| 조각 | 위치 | 덮는 AC-03 요소 |
|---|---|---|
| `tools/collect_container_evidence.py` | DB lane(C1~C4): terminal run의 active lease 0, succeeded run의 evidence↔result completion/commitment 동일 `evidence_id`·`outputSha256`==`storage_objects.content_hash`, failed run의 성공 evidence 0, released lease의 `stop_receipt`/`reservation_abort` 출처. Container lane(P1~P4): 커널 `sandbox.compile_launch` 계획과 동일 제약(network none·ro rootfs·cap-drop ALL·uid 65532·pids 64)으로 probe 컨테이너 실행 → stdout/stderr **bytes·SHA-256**, rootfs 쓰기 거부, 네트워크 격리(loopback refused는 증거 아님·control probe 비식별이면 위반), uid/caps. 미측정 lane은 `measured:false`·UNMEASURED(exit 3), 비밀 guard, `--disposable` | 출력 bytes/hash · lease 회수 · Evidence ID · 컨테이너 거부(rootfs/network) |
| `tests/test_execution.py`(25, postgres) | `test_the_database_refuses_a_success_without_evidence`(증거 없는 성공 DB 거부), `test_complete_run_writes_state_evidence_and_event_together`, `test_a_failure_after_evidence_rolls_the_evidence_back_too`, `test_success_is_refused_from_any_state_but_verifying`, `test_evidence_is_append_only_for_the_application_role`, `test_output_ref_must_be_an_inv_uri`, `test_a_terminal_state_without_a_reason_is_rejected`, `test_cancel_is_idempotent`, `test_cancelling_a_finished_run_is_refused`, `test_a_dataset_mount_cannot_be_writable`, `test_another_tenant_cannot_see_runs_or_evidence` | 허용 실행 성공(상태 전이·exit) · Evidence ID 강제 · 금지 경로(쓰기 가능 dataset mount·비-`inv://` output) |
| `tests/test_run_state.py`(17, PG-free) | 11 상태·3 종료·전이 그래프·terminal reason | 허용 실행 상태 전이 |
| `tests/core/test_sandbox_contracts.py` + `tests/core/test_workload_spec_input_anchors.py`(PG-free) | `compile_launch`의 `SANDBOX-0002`(image digest·실행파일 allowlist·argv 길이/NUL·cpu/mem/gpu/timeout 초과 → 403), `SANDBOX-0001`(검증된 sandbox capability 부재), host access/isolation 하향 거부, 셸 메타문자 리터럴, 상태 접근 전 WorkloadSpec 거부 | **금지 명령·경로 차단**(제품 경로) |
| `tests/integration/test_tool_admission.py`(postgres) | 위조 outbox 무효, stale node 거부, 미검증 runtime 거부, revoke 뒤 claim 중지, 실행 컨텍스트 변경 거부 | 금지 실행 차단(admission) |
| `tests/integration/test_reservation_aborts.py`(3) + `test_postgres.py`(`test_expiration_and_cancellation_do_not_release_capacity`, `test_recovery_blocks_until_stop_and_old_checkpoint_cannot_win`) + `test_containment.py::test_running_kill_preempts_network_call_and_releases_only_after_real_stop` | 종료 후 자원 회수(stop receipt 뒤에만 lease 해제, 위조 receipt 없이 반환) |
| `tests/test_vf_evidence.py`(6) | exit code와 evidence 독립, 이전 report 재사용 금지, 실패 요약 redaction, docker 전 수집 거부 | 하네스 정직성 규칙(runner가 따를 규칙) |

## 2. 만들 것: `tools/collect_s03_acceptance_evidence.py` (카드 13과 같은 형태)

한 번의 호출로 (a) AC-03 clause 시험 세트를 JUnit으로 실행, (b) `collect_container_evidence.py --disposable`(DB lane) + `--container-image`(있을 때만)를 실행, (c) 고정 SHA provenance와 함께 redacted JSON+MD로 묶는다.

| AC-03 조항 | 매핑 케이스(파일::케이스, 전부 기존) | 조항 상태 규칙 |
|---|---|---|
| `allowed-execution-succeeds` | `test_execution.py`::complete_run_writes…, success_is_refused_from_any_state_but_verifying, cancel_is_idempotent, cancelling_a_finished_run_is_refused, a_terminal_state_without_a_reason_is_rejected · `test_run_state.py`::the_happy_path_is_walkable, the_approval_path_is_walkable, illegal_transitions_are_refused | 전부 passed → `pass`; 하나라도 failed/error → `fail`; skipped/missing → `not_run` |
| `forbidden-path-or-command-blocked` | `test_sandbox_contracts.py`::sandbox_contract_rejects_host_access_or_isolation_downgrade, profile_limits_block_unapproved_execution, profile_executable_allowlist_is_canonical, shell_metacharacters_are_literal_container_arguments · `test_workload_spec_input_anchors.py`::sandbox_compile_rejects_workload_before_profile_access, tool_claim_rejects_workload_after_command_before_runtime_access · `test_execution.py`::a_dataset_mount_cannot_be_writable, output_ref_must_be_an_inv_uri · `test_tool_admission.py`::forged_outbox_content_has_no_execution_effect, unverified_or_incomplete_runtime_is_denied, changed_execution_context_is_rejected_before_first_claim | 동상 |
| `resources-reclaimed-after-exit` | `test_reservation_aborts.py` 3건 · `test_postgres.py`::expiration_and_cancellation_do_not_release_capacity, recovery_blocks_until_stop_and_old_checkpoint_cannot_win · `test_containment.py`::running_kill_preempts_network_call_and_releases_only_after_real_stop · DB lane C1·C4 | 시험 동상 + C1/C4 위반 0 |
| `evidence-id-and-output-hash-enforced` | `test_execution.py`::the_database_refuses_a_success_without_evidence, a_failure_after_evidence_rolls_the_evidence_back_too, evidence_is_append_only_for_the_application_role · DB lane C2·C3 | 시험 동상 + C2/C3 위반 0 |
| `container-output-bytes-and-denials`(lane) | Container lane P1~P4 | 이 PC(Windows, Linux docker socket 없음): **UNMEASURED**, 값 없음. hosted Core(ubuntu, `inv-node-test` 이미지)·격리 Linux host에서만 measured |

- 시험 실행: postgres 마커 파일은 **한 파일씩 순차**(메모리 규칙), PG-free 파일은 한 호출. 파일별 JUnit sha256·exit·소요 기록, 케이스 id는 parameter 제거(카드 13 `safe_case_id`), 실패 문구 미보존.
- 매핑 케이스 실재 검증: PG-free 시험이 AST로 파일별 `def test_` 존재를 고정(이름 표류 시 즉시 red).
- DB lane: `collect_container_evidence.py --disposable --out-dir <bundle>/… --label …`를 서브프로세스가 아니라 import로 호출해 exit(0/1/2/3)와 JSON 요약(runs·leases·violations·measured 플래그)만 묶음에 넣는다. disposable DB는 비어 있으므로 "runs 0 → UNMEASURED"가 정직한 기본값이다 → runner는 **시드 옵션 `--seed-ledger`**로 `tests/test_collect_container_evidence.py`의 `s03_db` 시드(제어 epoch·tenant·project·node·resource·runs draft/succeeded/failed·lease·stop receipt·reservation abort·storage object·evidence)를 같은 disposable DB에 넣고 측정한다(시드 함수를 시험에서 도구 모듈로 승격, 동작 보존). 시드는 제품 경로가 아니므로 `ledgerSource: seeded-fixture`로 표기하고 실 Node 경유 ledger(`ledgerSource: product`)와 구분한다.
- Container lane: `--container-image`가 주어지고 로컬 docker에 이미지가 있을 때만; 없으면 collector가 그대로 `measured:false`. runner는 그 값을 옮기고 이유를 남긴다. 이미지 pull 금지.
- 묶음 verdict: 측정된 4조항 전부 pass ∧ DB lane 위반 0 → `PASS_MEASURED`(lane UNMEASURED 있으면 `PASS_MEASURED_PARTIAL`); 실패/위반 → `FAIL`; 실행 불가 → `UNAVAILABLE`; 측정 0 → `NOT_RUN`. `acceptanceClaim=false` 고정(실 Linux 제한 컨테이너·ToolGateway·제품 Storage 출력은 물리 자원 대기).
- 외부·물리 대기(값 없음): 실제 Linux 제한 컨테이너 실행 24파일(`integration/test_node_runtime`·`test_dispatch_node`·`test_node_delivery`·`test_shard_recovery`·`test_workspace_*`·`test_results` 등, "Real Linux Docker runtime explicitly enabled only in isolated CI") → `not_run_here` + hosted Core run id를 인용 칸으로만, ToolGateway 실 Node, S03-ST 전송 정본(#5 결정 대기).
- 산출: `Evidence/s03-db-acceptance/s03-acceptance-<sha12>-<utc>.{json,md}` + `-container.{json,md}`(collector 원본). stale 선삭제, DSN/비밀번호 쓰기 거부, provenance = SHA·branch·integration 거리·clean 플래그·runner sha256·collector sha256. exit 0 PASS_MEASURED(_PARTIAL) / 1 FAIL / 2 UNAVAILABLE / 3 NOT_RUN.

## 3. 시험 계획

- PG-free: 매핑 실재(AST), JUnit 파싱·clause 규칙, lane 전달(measured/unmeasured 그대로, 절대 pass로 승격 금지), verdict 표, 비밀 guard, stale 삭제, stub end-to-end, 시드 함수 동작 보존(승격 전후 동일 row 수).
- 실 PG: 단일 파일 1회 = runner의 postgres 케이스(disposable DB에 시드 → DB lane PASS → 조항 시험 세트는 파일별 순차). 로컬 총 실행 시간 예상 2~3분(test_execution 25·tool_admission 12·containment 1·postgres 2·reservation 3).
- 되살림 1건 이상: C2의 `outputSha256` 대조 제거 → 시드된 불일치 object에서 runner가 잡는지; 금지 명령 조항의 케이스 하나를 매핑에서 빼면 AST 시험이 아니라 clause 규칙이 잡는지.

## 4. 경계·롤백·인계

- 제품 코드·계약·migration 변경 0. `collect_container_evidence.py`는 수정하지 않고 import만(시드 승격만 시험→도구 이동, 동작 보존). 롤백은 runner 파일 삭제.
- 메모리 규칙(약 2GB): 전체 suite·브라우저 미실행, postgres 파일 한 개씩.
- owner Claude / reviewer Codex / 병합 금지. 구현 카드는 이 설계 승인 뒤 같은 worktree `.worktrees/claude-s03-runner`(branch `agent/claude/s03-db-evidence-runner`, base `1e8baf04`)에서 진행.
