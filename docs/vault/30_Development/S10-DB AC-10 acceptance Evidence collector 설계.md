---
doc_id: "CLAUDE-S10-DB-AC10-EVIDENCE-COLLECTOR-DESIGN-001"
title: "S10-DB AC-10 acceptance Evidence collector 설계 — 모델 계보 역추적·모델 버전 append-only·보존 pin/release gate·배포 digest/승인·tenant 격리를 고정 SHA에서 한 번에 묶는 collector (기존 S10 실PG 228 세트 재사용, #120과 같은 형태)"
version: "1.0.0"
status: "proposed-review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T06:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-DB", "S10-ST"]
tags: ["S10-DB", "S10-ST", "AC-10", "evidence", "collector", "lineage", "model-registry", "deployment-digest", "claude", "design"]
---

# S10-DB AC-10 acceptance Evidence collector 설계 (1쪽)

> [!warning] 설계 + PG-free 구현 단계
> 근거는 [[2026-09-22_계보모델불변_컨텍스트eval_교차증거_실PG_S09_S10_Claude]]의 S10 세트(실 PG **228 passed / 0 skipped**, `f0f0c790`, 14파일). 이 카드는 그 시험을 새로 쓰지 않고 고정 SHA에서 다시 실행해 AC-10 조항별 redacted 묶음으로 남기는 collector다. 공개 계약·registry·ontology 변경 0. `acceptanceClaim=false`(S10-DB/S10-ST는 `planned`, 인수 판정은 Codex 검토 뒤).

## 1. 형태 — #120 S02 collector와 동일, #120 Codex 지적 3건을 처음부터 적용

| 규칙 | 구현 |
|---|---|
| **fail-closed(모든 실패)** | 파일 하나가 pytest 프로세스 하나(메모리 규칙). 어떤 suite든 failed/error > 0, exit ≠ 0, status ≠ complete → 묶음 **FAIL**(매핑 여부 무관). 조항은 매핑 케이스 전부 `passed`일 때만 `pass`, skipped/missing → `not_run`. 아무것도 실행되지 않았을 때만 `NOT_RUN`. |
| **도달 가능한 clean head provenance** | `tools.provenance.collect`(commit_sha·branch·integration 거리·`working_tree_clean_status`·`content_clean_diff`) + collector 파일 sha256. 커밋된 clean head에서만 evidence를 남기고, 산출물 label에 sha12를 넣어 이전 산출물을 덮어쓰지 않는다. |
| **식별자 redaction + 부정 시험** | 쓰기 전 `assert_no_secrets`(DSN/password 거부) + `assert_redacted`(disposable DB 이름·UUID·커널 ULID `mdl_/mv_/dep_/ds_/img_/cmt_/run_/evd_/nod_/prj_/res_/tnt_`·`IPv4:port`가 남아 있으면 거부), `--note` 동일 치환, pytest 실패 문구 미보존(parameter 제거 케이스 id·count만). 패턴별 부정 시험. 내부 evidence이며 공개 artifact 아님. |

## 2. AC-10 조항 ↔ 기존 시험 (case id = `<module>::<test>`, 전부 실재 — PG-free 시험이 AST로 고정)

| 조항 | 매핑 케이스 |
|---|---|
| `lineage-traceability`(S10-DB, AC-10 "데이터·코드·평가·승인 역추적") | `tests.test_lineage`::a_fully_linked_model_traces_back_to_everything, the_traceback_names_what_is_missing, an_edge_whose_subject_vanished_is_reported_as_dangling, recording_the_same_edge_twice_is_idempotent, an_untraceable_model_cannot_be_released · `tests.test_model_registry`::record_lineage_rejects_unknown_kinds_and_is_idempotent, trace_reports_missing_required_kinds_and_shrinks_as_they_are_recorded, release_succeeds_when_verified_pinned_and_fully_traceable |
| `model-version-append-only`(S10-ST) | `tests.test_lineage`::two_model_versions_cannot_share_content, model_versions_are_append_only_for_the_application, the_database_refuses_a_tag_shaped_digest, an_image_is_its_digest_not_its_tag · `tests.test_model_registry`::identical_weights_under_two_names_is_refused, registering_requires_a_hex_sha256_and_an_existing_model |
| `retention-pin-and-release-gate`(S10-ST) | `tests.test_lineage`::a_retention_pin_only_extends, release_requires_verification_pin_and_traceability, verification_refuses_a_mismatched_checksum, the_database_refuses_a_release_without_verification · `tests.test_model_registry`::a_retention_pin_only_extends, release_is_refused_until_verified_then_pinned_then_traceable, the_database_refuses_released_without_verification_and_pin, verify_sets_the_timestamp_and_rejects_a_mismatch |
| `deployment-digest-and-approval`(OUT-10 배포 digest) | `tests.test_lineage`::a_deployment_pins_the_digest_that_shipped, an_approval_for_other_content_cannot_deploy, an_unreleased_version_cannot_be_deployed, redeploying_supersedes_the_previous_active_one, the_database_refuses_two_active_deployments, a_deployment_without_an_approval_is_refused · `tests.test_model_registry`::deploying_a_released_version_pins_the_shipped_digest_and_supersedes, a_draft_version_cannot_be_deployed · `tests.test_deployment_guard`::approval_time_and_cached_revocation_are_checked, concurrent_first_deployments_leave_one_active_record, cached_released_stage_cannot_override_current_draft, database_rejects_duplicate_active_and_service_supersedes |
| `tenant-isolation` | `tests.test_lineage`::lineage_is_tenant_isolated · `tests.test_model_registry`::a_non_owner_scoped_to_one_tenant_cannot_see_another_tenants_version |
| (보조 suite, 조항 매핑 없음·fail-closed에는 포함) | `integration/test_model_commit`(9)·`test_model_registry_binding`(11)·`test_model_registry_revalidation`(3)·`test_model_locality`(11)·`test_model_view`(7)·`test_model_runtime`(8)·`test_model_retry`(7)·`test_model_license_readthrough`(1) — 각각 postgres 파일 하나씩; `core/test_model_manifest`(11)·`test_model_execution_registry`(3)·`test_model_remote`(8) — PG-free 한 호출 |

## 3. 산출·판정·외부 대기

- 산출: `Evidence/s10-db-acceptance/s10-acceptance-<sha12>-<utc>.{json,md}`: schema `s10-db-acceptance-evidence:1`, provenance, suite별 exit·counts·junit sha256·elapsed, 조항별 케이스 상태, `verdict` ∈ {PASS, FAIL, UNAVAILABLE, NOT_RUN}, `acceptanceClaim=false`, 외부 대기 = 실제 두 외부 Provider 실행/취소/collect/attest(CX-02 credential 경계, S10-BE)·MLflow 실접속 → `UNMEASURED`, 값 없음.
- exit 0 PASS / 1 FAIL / 2 UNAVAILABLE / 3 NOT_RUN. stale 산출물 선삭제.
- 실 PG는 가용 메모리 ≥1.5GB일 때만 단일 invocation(파일 하나씩 순차, 총 14 프로세스, 이전 실측 225s). 전체 suite·브라우저·Docker 기동 없음.

## 4. 시험·롤백·인계

- PG-free: 매핑 실재(AST, BOM 허용), suite ↔ 모듈 커버, JUnit worst-outcome·parameter 제거, 조항 규칙, verdict 표(매핑 밖 실패 → FAIL 되살림 포함), 외부 대기 UNMEASURED·값 없음, sanitizer 패턴별 부정 시험, 비밀 guard, stale 삭제, stub end-to-end. postgres 마커 1(전체 파이프라인 1회; 로컬 DSN 없으면 skip, CI fail; hosted **Backend**가 수집).
- 롤백: collector·시험 파일 삭제. owner Claude / reviewer Codex / 병합 금지. worktree `.worktrees/claude-s10-collector`, branch `agent/claude/s10-db-evidence-collector`, base `1e8baf04`.
