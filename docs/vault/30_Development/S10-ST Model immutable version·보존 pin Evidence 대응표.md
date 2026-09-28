---
doc_id: "CLAUDE-S10-ST-EVIDENCE-MAP-001"
title: "S10-ST Model immutable version·보존 pin Evidence 대응표 — 불변 버전·보존 pin·adapter conformance·배포 digest를 기존 코드·시험·hosted run에 file:line과 run ID로 대응, 공백 2(작은 시험으로 메움 1, 카드 ar/#152 이관 1) + 외부 대기 2 (카드 aw)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:36:09+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-ST"]
tags: ["S10-ST", "AC-10", "evidence", "model-version", "retention-pin", "adapter", "deployment-digest", "claude"]
---

# S10-ST Evidence 대응표 (2026-09-28, 카드 aw)

task-registry S10-ST: scope "Model immutable version·보존 pin", evidence "Adapter conformance·lineage query·배포 digest", AC-10. 원칙은 #153·#155와 같다: 이미 있는 것을 file:line·run ID로 대응하고 공백만 골라낸다, 관측 안 된 값은 NOT_OBSERVED, 판정 논리 복제 없음. 결론 먼저 — **네 범위 모두 코드·시험이 있고 hosted Backend가 실행한다. 공백은 (G1) "같은 version에 다른 digest 재등록 거부"를 단언하는 시험이 없어 최소 시험 1건 + PG-free 불변식 pin 4건을 넣었고, (G2) business model-registry lane의 HTTP route(lineage 조회·등록·배포)가 없어 카드 ar/#152로 넘긴다. 외부 대기 2(실 Provider adapter, MLflow)는 BLOCKED_EXTERNAL.**

## 0. 인용 run

| lane | run | head | 결과 |
|---|---|---|---|
| Backend | **36351202242** | `a0dab579`(#125 docs-only = base 시험 집합) | 2929 passed / 47 skipped / 0 failed (3.12·3.14) — `tests/test_lineage.py`·`test_model_registry.py`·`test_deployment_guard.py`·`test_adapters.py`·`tests/core/test_registry_policy_exact_match.py`·`test_vf_replica_migration.py`·`test_replica_repair.py`·`test_pitr_archive_retention.py` 포함(Backend ignore 목록 밖) |
| Backend | **36363486696** | `f97c48d5`(#150) | 2958/47/0 — VF-CL-04 retention 37 포함 |
| Backend | **36364528281** | `30f5ca83`(#153) | 3041/47/0 — S10 세트와 같은 집합 + S12 collector |
| 로컬 실 PG(참고) | — | `f0f0c790` | S10 14파일 **228 passed / 0 skipped**([[2026-09-22_계보모델불변_컨텍스트eval_교차증거_실PG_S09_S10_Claude]]); #127 S10 collector가 이 세트를 36 케이스·5조항으로 매핑 |

## 1. 대응표

### 1.1 불변 버전 (ModelVersion·manifest digest·재등록 거부)

| 불변식 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| version 이름당 content 하나(재등록은 새 version으로만) | `migrations/versions/0004_s10_lineage.py:194 uq_model_versions_model_id_version` | **G1 신규** `tests/test_lineage.py::test_the_same_version_with_a_different_digest_is_refused` + PG-free pin `tests/test_model_version_invariants_static.py::test_model_version_identity_is_unique_per_model_and_per_content` | Backend(이 PR run) | 관측됨(이 PR부터) |
| 같은 bytes를 두 이름으로 등록 금지 | `0004:195-197 uq_model_versions_tenant_id_content_sha256` | `test_lineage.py:252 two_model_versions_cannot_share_content` · `test_model_registry.py:118 identical_weights_under_two_names_is_refused` | Backend 36351202242 | 관측됨 |
| 애플리케이션 role은 append-only(identity 컬럼 UPDATE·DELETE 불가, lifecycle 컬럼만 UPDATE) | `0004:49-58 LIFECYCLE_UPDATE_COLUMNS` (`stage`·`verified_at`·`retention_pinned_until`만) | `test_lineage.py:272 model_versions_are_append_only_for_the_application`(UPDATE content_sha256·DELETE 거부) + PG-free pin `…static.py::test_application_may_only_advance_lifecycle_columns_never_identity` | Backend | 관측됨 |
| digest 형식·소문자·checksum 검증 | `src/saintvision/services/lineage.py:202 register_model_version`, `:271 verify_model_version`(`:281` 불일치 거부), `0004:199-201 checksum_is_lowercase` | `test_lineage.py:457 verification_refuses_a_mismatched_checksum` · `test_model_registry.py:105,:131` | Backend | 관측됨 |
| 커널 manifest 불변·손상 거부 | `services/control-plane/src/inv/model_manifest.py`, `model_view.py` | `tests/core/test_model_manifest.py` 11 · `tests/integration/test_model_view.py` 7(corrupt manifest → 409 MODEL-0001, #137로 되돌림) · `test_model_commit.py` 9 | Backend·Core | 관측됨 |

### 1.2 보존 pin

| 불변식 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| 모델 버전 pin은 연장만(단축 무시) | `lineage.py:292 pin_retention`(`until > current`일 때만 갱신) | `test_lineage.py:470 a_retention_pin_only_extends` · `test_model_registry.py:148` + PG-free pin `…static.py::test_pin_retention_source_only_extends` | Backend | 관측됨 |
| release는 verify + pin + trace 뒤에만, DB도 거부 | `lineage.py:308 release_model_version`(`:324,:326,:330`), `0004:205-208 release_requires_verification_and_pin` | `test_lineage.py:395,:431,:487` · `test_model_registry.py:165,:198,:343` | Backend | 관측됨 |
| pin된 버전 삭제 거부 | 위 append-only(앱 role DELETE 불가, pin 여부 무관) | `test_lineage.py:272` | Backend | 관측됨(별도 pinned 변형 불필요 — DELETE 자체가 거부) |
| replica 보존 pin(0043: ready/stale만 pin 유지, 노드 이탈 시 pin 보존) | `migrations/versions/0043_replica_retention.py:15 CHECK`, `src/saintvision/services/replica_repair.py:233 mark_node_replicas_unavailable` | `tests/test_vf_replica_migration.py:20,:50` · `tests/test_replica_repair.py:311 node_loss_on_a_pinned_replica_keeps_the_pin` | Backend | 관측됨 |
| WAL archive·base backup 7일 보관(계획만, label 시각 fail-closed) | `tools/pitr_archive_retention.py`(#150) | `tests/test_pitr_archive_retention.py` 37 | Backend 36363486696 | 관측됨 |

### 1.3 adapter conformance

| 항목 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| model import 정확 일치(선언 ≠ 제안이면 거부, 정규화 없음) | `src/saintvision/adapters/model_import.py:51 mismatching_fields`, `:80 require_exact_declaration` | `tests/core/test_registry_policy_exact_match.py` 10(:120 identical, :140 every deviation named) | Backend | 관측됨 |
| provider/CLI adapter conformance(reference adapter 적합·digest 없는 attest 거부·미검증 admit) | `src/saintvision/adapters/conformance.py:121 run_conformance`, `reference.py` | `tests/test_adapters.py:37,:168,:186,:315` · `tests/test_cli_adapters.py` | Backend | 관측됨 |
| 실제 외부 Provider 실행/취소/collect/attest | — | — | — | **BLOCKED_EXTERNAL**(CX-02 credential 경계, S10-BE) |
| MLflow 실접속·등록 | — | — | — | **BLOCKED_EXTERNAL**(S10-BE) |

### 1.4 배포 digest

| 불변식 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| 배포 digest는 모델 버전에서(caller 아님), 승인은 정확 content, released만, 활성 1 | `lineage.py:454 record_deployment`(`:494,:507-514,:534 deployed_digest=version.content_sha256`), `0004:277 uq_deployments_one_active_per_environment` | `test_lineage.py:526,:543,:576,:590,:620,:648` · `test_model_registry.py:450,:509` · `test_deployment_guard.py:43,:62,:106,:118` + PG-free pin `…static.py::test_release_and_deployment_guards_are_still_in_the_service` | Backend | 관측됨 |
| 커널 commitment 조회 route | `services/control-plane/src/inv/app.py:449 GET /v1/projects/{project}/models/{model_id}/versions/{version}/commitment` | `tests/integration/test_model_view.py` 7 | Backend·Core | 관측됨 |
| business lane HTTP route(등록·verify·pin·release·deploy·lineage 조회) | **없음** — `register_model_version`·`verify_model_version` 호출부 0건(#152 §1) | — | — | **카드 ar(lineage 조회 API 설계)·#152(import adapter 요청경로) 이관** |

## 2. 공백 목록

| # | 공백 | 처리 |
|---|---|---|
| G1 | 같은 version에 다른 digest 재등록 거부를 단언하는 시험 없음(DB 제약은 있음) | **이 PR**: `test_lineage.py` postgres 시험 1(hosted Backend) + PG-free 불변식 pin 4(`tests/test_model_version_invariants_static.py`: 유일성 3종 선언, lifecycle UPDATE 컬럼에 identity 없음, `pin_retention` 연장만, release/deploy guard 문구). 판정 논리 복제 없음 — 선언·guard 존재를 고정할 뿐 |
| G2 | business model-registry lane의 HTTP route와 lineage 조회 API 부재 | 새 route·계약이 필요 → **카드 ar(lineage 조회 API 설계)·#152(import adapter 요청경로 결속 설계)** 로 이관, 이 PR에서 만들지 않음 |
| E1 | 실 Provider adapter(CX-02) | BLOCKED_EXTERNAL |
| E2 | MLflow | BLOCKED_EXTERNAL |

## 3. 경계

로컬 실 PG·Docker·전체 suite 없음(G1 postgres 시험은 hosted Backend가 실행; PG-free pin 4건은 로컬 통과). 게이트 exit 0. owner Claude / reviewer Codex / 병합 금지. worktree 재사용, branch `agent/claude/s10-st-evidence-map`, base `1e8baf04`. S10-ST `planned` 유지. 다음 첫 행동: Codex 검토 → hosted Backend run id(G1 실행 확인) → G2는 ar/#152.
