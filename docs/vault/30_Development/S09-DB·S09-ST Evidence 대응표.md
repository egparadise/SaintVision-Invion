---
doc_id: "CLAUDE-S09-DB-ST-EVIDENCE-MAP-001"
title: "S09-DB·S09-ST Evidence 대응표 — 불변 Context·RunRecord(재기록 거부·digest)·eval 기록·diff/테스트/trace Artifact 연결을 기존 코드·시험·hosted run에 file:line과 run ID로 대응, 공백은 설계 대상 1(business route)·NOT_OBSERVED 1(Windows 게이트)·BLOCKED_EXTERNAL 2 (구현 추가 0, 카드 ay)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:42:12+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S09-DB", "S09-ST"]
tags: ["S09-DB", "S09-ST", "AC-09", "evidence", "context", "runrecord", "eval", "artifact", "claude"]
---

# S09-DB·S09-ST Evidence 대응표 (2026-09-28, 카드 ay)

task-registry: S09-DB scope "불변 Context/RunRecord·eval", S09-ST scope "diff·테스트·trace Artifact 연결", evidence 둘 다 "golden eval·분류별 성적·금지 행동 시험", AC-09. 원칙은 #153·#155·#160과 같다: 이미 있는 것을 file:line·run ID로 대응하고 공백만 골라낸다, 관측 안 된 값은 NOT_OBSERVED, 판정 논리 복제 없음. 결론 먼저 — **네 범위 모두 코드·시험이 있고 hosted Backend가 실행한다(#131 S09 collector가 같은 5파일 73 케이스를 8조항으로 이미 매핑). 이 PR은 대응표만 담는다(구현·시험 추가 0). 공백은 business lane HTTP route 부재(설계 대상, 카드 ar/#152와 같은 부류) 1, Windows 호스트의 Linux 사설 스토리지 게이트(NOT_OBSERVED, hosted에서는 실행) 1, AC-09 제품 지표·실 Provider(BLOCKED_EXTERNAL) 2다.**

## 0. 인용 run·근거

| lane / 근거 | run / head | 결과 |
|---|---|---|
| Backend | **36351202242** `a0dab579`(#125 docs-only = base 집합) | 2929 passed / 47 skipped / 0 failed — `tests/test_context_eval.py` 27·`test_eval_execution.py` 14·`test_context_redaction.py` 9·`tests/integration/test_approvals.py` 13·`test_approval_review.py` 5·`test_results.py` 14(ubuntu라 Linux 게이트 통과)·`test_result_observation.py` 5 포함(Backend ignore 목록 밖) |
| Backend | **36353897541** `8217dfea`(#131) | pass — #131 S09 collector postgres self-test(5파일 subprocess 실행) 포함 |
| 로컬 실 PG(참고) | `5f0b4cd2` | S09 세트 **76 passed / 21 skipped**(skip 21 = `test_results.py` Linux 게이트) — [[2026-09-22_계보모델불변_컨텍스트eval_교차증거_실PG_S09_S10_Claude]] |
| S09 collector | PR #131 `tools/collect_s09_acceptance_evidence.py` | 5파일 73 케이스 → 8조항(immutable-context 10·runrecord-seal-immutable 4·eval-golden-gate 8·eval-executor-conformance 14·artifact-pin-by-role 3·tenant-isolation 2·bounded-approval-loop 18·runrecord-completion-pipeline 14[게이트]) |
| S09-FE 매트릭스 | PR #113 `5813a07c` (Gemini, docs) | 100 Prompt / 30 Coding Eval 러너·자연어 요청 시나리오 — FE 소비 시나리오이며 이 대응표의 DB/ST 불변식과 독립 |

## 1. 대응표

### 1.1 불변 Context (S09-DB)

| 불변식 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| 동일 content는 tenant당 1회 저장·idempotent·dedup은 tenant를 넘지 않음 | `src/saintvision/services/context.py:111 content_hash`, `:129 store_snapshot`; `migrations/versions/0003_s09_context_eval.py:76 hash_is_lowercase`, `:146-149 ix_context_bundle_items_tenant_id_content_hash` | `tests/test_context_eval.py:106,:131,:156` | Backend 36351202242 | 관측됨 |
| snapshot·record는 append-only(앱 role INSERT/SELECT만) | `0003:52-58 NEW_APPEND_ONLY`(context_snapshots·run_records·run_record_artifacts) → `:322-324 GRANT SELECT, INSERT` | `test_context_eval.py:320 the_application_role_cannot_delete_snapshots` | Backend | 관측됨 |
| bundle 순서 재현·hash 순서 의존·item version이 원본 변경을 넘어 생존 | `context.py:116 bundle_hash`, `:165 build_bundle`, `:240 read_bundle`, `:276 verify_bundle`; `0003:105 hash_is_lowercase`, `:137 item_version_positive` | `test_context_eval.py:170,:228,:246` | Backend | 관측됨 |
| 인식된 비밀은 거부·아무것도 저장 안 함·초과 크기는 거부(잘라내지 않음) | `context.py:71 _refuse_recognised_secrets`(build_bundle 배선) | `test_context_eval.py:190,:271` · `tests/test_context_redaction.py` 9(:32 probe 전부 거부, :43 비밀 미반향, :61 "redacted 선언"은 증명 아님) | Backend | 관측됨 |
| orphan snapshot만 수거·참조된 것 보존·dedup 비율 보고 | `context.py:290 collect_orphan_snapshots`(owner 실행), `:327 deduplication_ratio` | `test_context_eval.py:287,:334` | Backend | 관측됨 |

### 1.2 RunRecord 봉인 (S09-DB: 재기록 거부·digest)

| 불변식 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| 미완성 run은 봉인 불가 | `src/saintvision/services/records.py:41 seal_run_record`(`:64-66` 상태 검사) | `test_context_eval.py:370` | Backend | 관측됨 |
| 두 번 봉인 = 같은 record, run당 1 | `records.py:41`(기존 record 반환), `0003:174 uq_run_records_run_id` | `test_context_eval.py:381,:414` | Backend | 관측됨 |
| 봉인된 record 재기록 불가 | `0003 NEW_APPEND_ONLY`(UPDATE 권한 없음) | `test_context_eval.py:395 a_sealed_record_cannot_be_rewritten` | Backend | 관측됨 |
| digest 고정: bundle이 run에 속해야 하고 `workload_spec_sha256`·bundle hash를 record에 기록 | `records.py:82`(bundle 소속 검사), `:94 workload_spec_sha256`, `:97 sealed_at`; `0003:175-178 final_state_is_terminal` | `test_context_eval.py:395,:414`(record 행에 `workload_spec_sha256` 삽입·재기록 거부) | Backend | 관측됨 |
| 커널 측 실제 완료 파이프라인(실 출력 바이트·receipt·pin·epoch·fencing·mTLS stop→verifier) | `services/control-plane/src/inv/results.py:22 ResultStore`, `result_view.py` | `tests/integration/test_results.py` 14(`skipif(sys.platform != "linux")` Linux 사설 스토리지) · `test_result_observation.py` 5 | Backend·Core(ubuntu) 실행; **이 Windows PC에서는 skip** | 관측됨(hosted) / NOT_OBSERVED(로컬) |

### 1.3 eval 기록 (golden eval·분류별 성적·금지 행동)

| 불변식 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| suite version 유일·hash; forbidden case는 weight 없음·scored forbidden 거부 | `src/saintvision/services/evaluation.py:62 create_suite`; `0003:223 uq_eval_suites_name_version`, `:246-252`(case 제약, `weight_positive`) | `test_context_eval.py:577,:590,:708` | Backend | 관측됨 |
| 위반은 점수로 상쇄 불가, DB도 gate pass+violations 거부, 위반은 failed | `evaluation.py:165 record_result`, `:222 gate_passed`; `0003:283 gate_requires_no_violations`, `:313 violation_implies_failure`, `:312 score_in_range` | `test_context_eval.py:607,:649,:726` | Backend | 관측됨 |
| 분류별 성적 분리 보고·불완전 suite 불통과 | `evaluation.py:288 score_report`, `:251 finish_eval_run`; `0003:280 passed_within_total`, `:282 status_allowed` | `test_context_eval.py:671,:744` | Backend | 관측됨 |
| executor/adapter: error≠fail, 미redact 미저장, 모델 pin 기본 거부, 빈/부분/전부 error 불통과, run row=report | `src/saintvision/services/eval_execution.py:167 execute_case`, `:240 run_suite`(`:258` 거부) | `tests/test_eval_execution.py` 14(:172~:480) | Backend | 관측됨 |
| tenant 격리 | `0003 _install_rls` FORCE RLS + policy | `test_context_eval.py:131,:767` | Backend | 관측됨 |
| AC-09 제품 지표(Prompt 100건 유효율 99%·코딩 30건 성공률 70%·누출 0) | — | — | — | **BLOCKED_EXTERNAL**(제품 실측, S09-BE/FE; #113 매트릭스가 FE 시나리오) |
| 실 외부 Provider adapter 실행 | — | — | — | **BLOCKED_EXTERNAL**(CX-02) |

### 1.4 diff·테스트·trace Artifact ↔ RunRecord 연결 (S09-ST)

| 불변식 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| artifact는 **역할**로 pin(diff·test_report·trace·log·model·dataset·other), 이름 규칙 아님 | `records.py:32 ARTIFACT_ROLES`, `:109 _pin_artifact`, `:152 list_pinned_artifacts`; `0003:202-205 role_allowed` | `test_context_eval.py:466 diff_test_and_trace_artifacts_are_pinned_by_role` | Backend | 관측됨 |
| 미검증(checksum 없음·비active) artifact·다른 run의 artifact는 pin 불가 | `records.py:117-123` | `test_context_eval.py:497` | Backend | 관측됨 |
| 나중 덮어쓰기는 pin이 탐지(ADR-010: version+digest 고정) | `records.py:133 checksum_sha256`, `:167 verify_pin` | `test_context_eval.py:519 a_later_overwrite_is_detected_by_the_pin` | Backend | 관측됨 |
| 승인·검토 루프(제한된 수정 루프: replay/scope 불변·quorum 우회 차단·exactly-once·grant 회수·검토 권한) | `services/control-plane/src/inv/approvals*.py` | `tests/integration/test_approvals.py` 13 · `test_approval_review.py` 5(#137로 owner corruption 되돌림) | Backend·Core | 관측됨 |
| business lane HTTP route(snapshot/bundle 저장·record 봉인·pin 조회·eval 실행) | **없음** — `src/saintvision/api/v1/*`에서 `context`·`records`·`evaluation`·`eval_execution` 서비스 import 0건 | — | — | **설계 대상**(새 route·계약; S10의 카드 ar/#152와 같은 부류 — 코디네이터 배정) |

## 2. 공백 목록 (구현·시험 추가 없음)

| # | 공백 | 분류 | 이유 |
|---|---|---|---|
| G1 | business lane route 부재(Context bundle·RunRecord 봉인·pin 조회·eval 실행이 서비스 함수로만 존재) | **설계 대상** | 새 route·계약이 필요; S10 business lane(#152·카드 ar)과 같은 lane 설계에서 함께 다루는 것이 맞음 |
| G2 | `test_results.py` 14 케이스가 Windows(이 PC)에서 Linux 사설 스토리지 게이트로 skip | **NOT_OBSERVED(로컬)** | hosted Backend/Core(ubuntu)에서는 실행됨(#131 collector도 게이트 사유를 `environment-gated:linux-private-storage`로 명시); 로컬에서 메울 도구 없음 |
| E1 | AC-09 제품 지표 3건 | BLOCKED_EXTERNAL | 제품 실측(S09-BE/FE) |
| E2 | 실 Provider adapter | BLOCKED_EXTERNAL | CX-02 |

작은 PG-free 불변식 시험으로 메울 행동 공백은 **없다**: 재기록 거부·digest·역할 pin·덮어쓰기 탐지·gate 위반 거부가 모두 `test_context_eval.py`·`test_eval_execution.py`에서 실PG로 단언되고, 0003의 선언(append-only GRANT·`uq_run_records_run_id`·`gate_requires_no_violations`·`violation_implies_failure`·`role_allowed`)은 그 시험들이 행동으로 덮는다. 따라서 docs-only.

## 3. 경계

로컬 실 PG·Docker·전체 suite 없음. 판정 논리 복제 없음(각 시험·서비스의 의미 불변). owner Claude / reviewer Codex / 병합 금지. worktree 재사용, branch `agent/claude/s09-db-st-evidence-map`, base `1e8baf04`. S09-DB/ST `planned` 유지. 다음 첫 행동: Codex 검토 → G1은 코디네이터 배정.
