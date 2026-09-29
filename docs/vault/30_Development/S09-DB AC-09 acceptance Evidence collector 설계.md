---
doc_id: "CLAUDE-S09-DB-AC09-EVIDENCE-COLLECTOR-DESIGN-001"
title: "S09-DB AC-09 acceptance Evidence collector 설계 — 불변 Context·RunRecord 봉인·eval golden gate·diff/test/trace Artifact pin·제한된 승인 루프를 고정 SHA에서 한 번에 묶는 collector (기존 S09 실PG 76+21 세트 재사용, #127과 같은 형태, Linux 사설 스토리지 게이트는 not_run으로 명시)"
version: "1.0.0"
status: "proposed-review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T09:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S09-DB", "S09-ST"]
tags: ["S09-DB", "S09-ST", "AC-09", "evidence", "collector", "context", "runrecord", "eval", "claude", "design"]
---

# S09-DB AC-09 acceptance Evidence collector 설계 (1쪽)

> [!warning] 설계 + PG-free 구현 단계
> 근거는 [[2026-09-22_계보모델불변_컨텍스트eval_교차증거_실PG_S09_S10_Claude]]의 S09 세트(실 PG **76 passed / 21 skipped / 0 failed**, `5f0b4cd2`; skip 21 = `tests/integration/test_results.py` 전부, 파일 자체의 `skipif(sys.platform != "linux", reason="Linux private storage")`). 이 카드는 그 시험을 새로 쓰지 않고 고정 SHA에서 다시 실행해 AC-09 조항별 redacted 묶음으로 남기는 collector다. 공개 계약·registry·ontology 변경 0. `acceptanceClaim=false`(S09-DB/S09-ST는 `planned` 유지, 인수 판정은 owner/reviewer).
> AC-09 본문("Prompt 100건 유효율 99%, 코딩 과제 30건 성공률 70%, 누출 0")은 **제품 실측**이며 이 collector가 재는 것이 아니다 — 세 항목과 실제 외부 Provider(CX-02)는 `externalWaits`에 `UNMEASURED`·값 없음으로만 적는다.

## 1. 형태 — #120·#121·#127에서 Codex가 잡은 결함 부류 (a)~(g)를 처음부터 적용

| 규칙 | 구현 |
|---|---|
| **(a) 모든 실패 fail-closed** | 파일 하나가 pytest 프로세스 하나(메모리 규칙, 5 프로세스). 어떤 suite든 JUnit failed/error > 0, exit ≠ 0, status ≠ complete → 묶음 **FAIL**(매핑 여부 무관). **검사 순서가 fail-closed 먼저**라 failed와 unavailable이 섞이면 FAIL(UNAVAILABLE은 실패가 하나도 없을 때만). 조항은 매핑 케이스 전부 `passed`일 때만 `pass`. |
| **(b) 관측하지 않은 값은 0이 아니다** | unavailable suite는 `counts=null`·`unavailableSuites`에 이름, `totals`는 counts가 있는 suite만 합산(하나도 없으면 null). 조항 `not_run`은 항상 `reason`을 가진다(`case-skipped-or-missing` / `environment-gated:linux-private-storage`). 게이트 사유는 **그 suite가 pytest를 완주했고(JUnit 존재) 실행 0·skipped > 0이며 조항의 모든 케이스가 skipped일 때만** 붙는다 — 케이스 하나라도 missing이면 게이트 사유 없이 `not_run`, 하나라도 실행됐으면 게이트로 치지 않는다. |
| **(c) clean reachable head, repo 루트 provenance** | dirty tree **기본 거부(exit 2)**, `--allow-dirty-tree`는 `provenance.dirtyTreeAllowed=true`로 기록되는 명시 opt-out. `tools.provenance.collect`는 repo 루트를 cwd로 계산(`collect_provenance_at_repo_root`) + collector 파일 sha256. |
| **(d) label 시각·덮어쓰기 거부** | 기본 label `s09-acceptance-<sha12>-<UTC %Y%m%dT%H%M%SZ>`. 같은 label의 json/md가 하나라도 있으면 **삭제 없이 exit 2**. |
| **(e) prefix 무관 redaction + 부류별 부정 시험** | 쓰기 전 `assert_no_secrets`(DSN/password 거부) + `assert_redacted`: disposable DB 이름·UUID·`<3~4 소문자>_<Crockford ULID 26>` 전부(S09 실제 id는 `evs/evc/evr/art/apv/run/evd/wsp/usr`, 시험은 `saintvision.ids.PREFIXES` 전수 + 커널 21 prefix)·`IPv4:port` → placeholder. `--note` 동일 치환. pytest 실패 문구 미보존(parameter 제거한 case id·counts만). |
| **(f) repo 밖 경로 placeholder** | 산출 경로는 `evidence_ref()`로 repo 상대 POSIX, repo 밖(hosted CI `/tmp`)은 `<outside-repo>/<name>`. |
| **(g) PR 코멘트** | `@codex` 멘션 없음. |

## 2. AC-09 조항 ↔ 기존 시험 (5파일 73 케이스 **전수** 매핑 — PG-free 시험이 AST로 "매핑 = 파일의 test 전체"를 고정)

| 조항 | 매핑 케이스 |
|---|---|
| `immutable-context`(S09-DB, 10) | `tests.test_context_eval`::the_same_content_is_stored_once_per_tenant, storing_the_same_content_twice_is_idempotent, a_bundle_reproduces_its_items_in_order, build_bundle_refuses_a_secret_and_stores_nothing, bundle_hash_depends_on_order, the_item_version_survives_the_source_changing, an_oversized_item_is_refused_not_truncated, orphan_snapshots_are_collected_and_referenced_ones_are_not, the_application_role_cannot_delete_snapshots, deduplication_ratio_is_reported |
| `runrecord-seal-immutable`(S09-DB, 4) | `tests.test_context_eval`::a_record_cannot_be_sealed_for_an_unfinished_run, sealing_twice_returns_the_same_record, a_sealed_record_cannot_be_rewritten, only_one_record_per_run |
| `eval-golden-gate`(S09-DB, AC-09 필수 증거 "golden eval·분류별 성적·금지 행동", 8) | `tests.test_context_eval`::a_suite_version_is_unique_and_hashed, a_forbidden_case_cannot_carry_a_weight, a_violation_fails_the_gate_however_good_the_score, the_database_refuses_a_gate_pass_with_violations, per_category_scores_are_reported_separately, a_scored_forbidden_case_is_refused, a_violation_on_a_scored_case_is_refused, an_incomplete_suite_does_not_pass_the_gate |
| `eval-executor-conformance`(S09-DB/BE 경계, 14) | `tests.test_eval_execution` 14 전부(a_correct_adapter_passes_the_gate … a_partial_run_is_not_a_pass; error≠fail, 미redact 미저장, 모델 pin 기본 거부, 빈/부분/전부 error 불통과, run row=report) |
| `artifact-pin-by-role`(S09-ST, 3) | `tests.test_context_eval`::diff_test_and_trace_artifacts_are_pinned_by_role, an_unverified_artifact_cannot_be_pinned, a_later_overwrite_is_detected_by_the_pin |
| `tenant-isolation`(2) | `tests.test_context_eval`::deduplication_does_not_cross_tenants, evaluation_is_tenant_isolated |
| `bounded-approval-loop`(OUT-09 "제한된 수정 루프", 18) | `tests.integration.test_approvals` 13 전부 + `tests.integration.test_approval_review` 5 전부 |
| `runrecord-completion-pipeline`(S09-DB, **gate = linux-private-storage**, 14) | `tests.integration.test_results` 14 전부(실 출력 바이트·receipt·pin·epoch·GC 직렬화·mTLS stop→verifier). 이 PC(Windows)에서는 pytest가 14 id를 skip → 조항 `not_run`·reason `environment-gated:linux-private-storage`, `passScope.notRunEnvironmentGated`에 이름. hosted Backend(ubuntu)에서는 실제 실행되어 measured. |

## 3. 산출·판정·외부 대기

- 산출: `Evidence/s09-db-acceptance/s09-acceptance-<sha12>-<utc>.{json,md}`: schema `s09-db-acceptance-evidence:1`, provenance(+`dirtyTreeAllowed`), suite별 gate·exit·counts(null 가능)·junit sha256·elapsed, `environment.gatesSkippedHere`, 조항별 status·reason·케이스, `passScope`{passed, notRunEnvironmentGated, notRunOther, failed}, `verdict` ∈ {PASS, PASS_MEASURED_PARTIAL, FAIL, UNAVAILABLE, NOT_RUN}, `acceptanceClaim=false`, `externalWaits` 4(AC-09 세 지표 + CX-02) = UNMEASURED·값 없음.
- verdict 순서: (1) 어느 suite든 실패 → FAIL, 조항 fail → FAIL; (2) unavailable/invalid-junit suite → UNAVAILABLE; (3) pass 조항 0이거나 게이트 아닌 not_run 조항이 있거나 게이트 없는 suite가 실행 0 → NOT_RUN; (4) 게이트 사유 not_run만 남으면 **PASS_MEASURED_PARTIAL**(`passScopeNote`에 범위 명시); (5) 전부 pass → PASS. exit 0 PASS/PASS_MEASURED_PARTIAL · 1 FAIL · 2 UNAVAILABLE(DSN 없음·suite 미실행·dirty·기존 파일) · 3 NOT_RUN.
- 실 PG는 가용 메모리 ≥1.5GB일 때만 단일 invocation(5 프로세스 순차, 이전 실측 110.88s). 전체 suite·브라우저·Docker 기동 없음. 조건 미충족이면 실 PG evidence는 **없음(UNMEASURED)**으로 두고, hosted Backend의 postgres 마커 1건(collector 전체 파이프라인 1회, ubuntu에서 test_results.py까지 실행)을 근거로 적는다.

## 4. 시험·롤백·인계

- PG-free **98 passed**: 매핑 73 = 5파일 test 전체(AST, BOM 허용)·유일·파일당 1프로세스, 게이트 파일이 소스에 skipif를 선언하고 collector가 같은 이름을 씀, JUnit worst-outcome·parameter 제거·실패 문구 미보존, 조항 규칙 5(reason 포함), 게이트 사유 부여 조건 3(전부 skipped일 때만·귀속 없으면 일반 not_run·1건 실행/1건 missing이면 게이트 아님), verdict 표 9, PASS_MEASURED_PARTIAL 범위·게이트 suite counts 보존(skipped 14, pass 아님·0 아님), 되살림(매핑 밖 실패 → FAIL), incomplete 2, failed>unavailable 양방향 + not_run 안의 error, unavailable = null·unknown, 외부 대기 값 없음, sanitizer 부정 시험 6 + prefix 전수(core ∪ kernel), S09 prefix ⊂ core 세트, git sha/count/case명 보존, 비밀 guard, `evidence_ref` placeholder, 기존 산출물 거부·미삭제, dirty 기본 거부·opt-out 기록, DSN 없음 → 아무것도 안 씀, label 시각 형식, repo 루트 provenance, stub end-to-end(게이트 호스트 시나리오·note 치환·stdout 경로 placeholder). postgres 마커 1(로컬 DSN 없으면 skip, CI fail; hosted **Backend** 수집).
- 롤백: collector·시험 파일 삭제. owner Claude / reviewer Codex / 병합 금지. worktree `.worktrees/claude-s09-collector`, branch `agent/claude/s09-db-evidence-collector`, base `1e8baf04`.
