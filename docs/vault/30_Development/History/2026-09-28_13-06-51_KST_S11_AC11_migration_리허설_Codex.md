---
doc_id: "HISTORY-S11-AC11-MIGRATION-REHEARSAL-20260928-CODEX"
title: "S11 AC-11 migration restore 리허설 구현"
version: "1.2.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T20:19:23+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tasks: ["S11-BE", "S11-DB"]
acceptance: ["AC-11"]
tags: ["s11", "ac-11", "migration", "restore", "hosted", "fail-closed"]
---

# S11 AC-11 migration restore 리허설 구현

## 기준과 범위

- 승인 설계: PR #157 v1.1.1, head `a793f258dac9b2a4951df084089bf3a3a3ae1bcc`, 설계 blob `99776a491772c4a62e1be26644d35a365d80a030`.
- stack base: PR #170 C1 문서화 head `960fdc6b70fe89ff63ce24e8125b449eb75abf99`를 merge commit `e5e1059a`로 포함했다. #170의 merge-commit-only provenance 조건을 보존한다.
- 공개 API·계약·기존 migration은 바꾸지 않는다. 로컬 PostgreSQL·Docker는 실행하지 않고 실제 리허설은 opt-in hosted lane에서만 수행한다.

## 구현

`tools/run_ac11_migration_rehearsal.py`는 exact PR head와 clean checkout을 확인하고 migration graph·fixture manifest를 정적으로 검증한다. 카드 90에서 승인 migration stack `0047`~`0053`을 포함했고, 최신 불가역 barrier `0052_model_version_digest_scope` 뒤에 가역 `0053_eval_suite_project_scope`가 있어 reversible tail은 1이다. 따라서 `migration-reversible-segment`는 더 이상 구조적 `NOT_APPLICABLE`이 아니며, fresh 0052 기준 DB와 `0052→0053→0052` candidate의 catalog fingerprint·sentinel 동등을 실제 측정해야 한다. 짝 restore 축은 disposable source/restore DB를 각각 새로 만든 뒤 `0051_service_credentials`까지 forward, 사전 sentinel과 custom-format snapshot 생성, source를 head로 forward, 별도 DB에 restore 후 head forward 순서로 실행한다.

최종 source와 restore DB의 catalog fingerprint는 table·column·constraint·index·function body/owner·table/routine grant·RLS policy·role membership을 비교한다. forward 전 sentinel은 restore 뒤 exact match해야 한다. forward 후 sentinel은 사전 snapshot에 없어야 하며 `DECLARED_LOSS_REQUIRES_RESTORE`로 명시한다. 종료 시 owned DB를 강제 정리하고 residue가 하나라도 남으면 실패한다. 오류 보고에는 예외 type만 남기며 DSN·비밀번호·SQL 출력을 evidence에 쓰지 않는다.

fixture manifest는 graph의 가역 revision 20개를 exact cover한다. 새 revision 중 `0047_audit_events_isolation`, `0050_dataset_digest_lookup`, `0053_eval_suite_project_scope`는 실행형 downgrade이고 데이터 손실을 선언하지 않아 `PRESERVED`다. 여기서 0047의 `PRESERVED`는 데이터 보존 등급이다. downgrade가 보안상 `inv_app SELECT`를 복원하지 않으므로 fresh 0046과 catalog는 의도적으로 비대칭이며, 0047이 가역 tail에 들어오는 graph라면 catalog 동등 PASS로 세면 안 된다(현재는 뒤의 불가역 0048 때문에 tail 밖). `0048_object_store_locator`, `0049_mlflow_mirror`, `0051_service_credentials`, `0052_model_version_digest_scope`는 원문이 restore/forward를 요구하는 명시적 refusal이라 manifest에서 제외한다. 기존 restore 필요 10종 집합은 바꾸지 않는다. 이후 migration PR은 같은 PR에서 이 manifest와 tail 기대를 갱신해야 하며, 누락 시 graph gate가 DB 호출 전에 실패한다.

부정 fixture는 기존 3종에 `0053-scoped-row-refusal`을 추가한다. 0053 head DB에 project-bound eval suite를 만든 뒤 0052 downgrade가 정확한 scoped-row 사유로 거부되고, alembic version과 `project_id`가 0053 상태로 원자 보존돼야 `EXPECTED_FINDING`이다.

기존 정본 run `36377513831`은 head 0046·tail 0 evidence이므로 새 head 0053의 release evidence로 재사용하지 않는다. 새 head에서는 restore-forward와 reversible-roundtrip 두 축을 같은 source SHA에서 다시 생성해야 한다.

workflow `AC-11 Migration Rehearsal`은 manual dispatch 또는 PR label `run-ac11-migration`에서만 실행된다. job-level concurrency는 `cancel-in-progress: false`, checkout은 merge ref가 아닌 PR head SHA, PostgreSQL은 `postgres:16` service다. JSON과 7-case JUnit(reversible roundtrip 1, restore 1, 부정 fixture 4, provenance 1)을 artifact로 30일 보존한다. 가역 tail이 0인 source에서만 reversible case 1건을 구조적으로 skip하며, 현재 0053 source에서는 7건 모두 실행해야 한다.

## PG-free 검증

| 명령 | 결과 |
|---|---|
| `PYTHONUTF8=1 python -m pytest tests/test_ac11_migration_rehearsal.py -q` | exit 0, **12 passed** |
| `python -m py_compile tools/run_ac11_migration_rehearsal.py` | exit 0 |
| workflow YAML parse | exit 0 |
| `git diff --check` | exit 0 |

부정 시험은 `downgrade(): pass`, refusal revision을 성공 downgrade로 오분류, `0009` fixture 누락, 기존 catalog 객체 삭제, DSN 부재 시 파일 미작성, opt-in/exact-head/non-cancelling workflow 결속을 포함한다.

## 현재 판정

### hosted 실행 이력

| run | source head | 결과 | 확인된 원인/조치 |
|---|---|---|---|
| `36376475798` | `6ecd29ae` | `MEASURED_FAIL` | type-only 진단만 남아 원인 미분류. safe owned diagnostic을 추가했다. |
| `36376639439` | `1daf4fac` | `MEASURED_FAIL` | catalog fingerprint가 columns·constraints·functions·routine grants에서 달랐다. |
| `36377155444` | `bf84c37a` | `MEASURED_FAIL` | 실제 보안 차이(function owner 유실)와 DB-local OID/physical attnum 비교 잡음을 분리했다. |
| `36377328717` | `2b4fc0d5` | `MEASURED_FAIL` | owner/grant는 일치했다. 남은 차이는 dropped-column 물리 slot과 동등한 CHECK cast deparse 표현이었다. |
| `36377513831` | `de9d8a4e` | **`MEASURED_PASS`** | 논리 column 순서와 동등 CHECK 표현만 정규화하고 owner·grant·function definition·policy 비교는 유지했다. |

정본 hosted 결과는 [run 36377513831](https://github.com/egparadise/SaintVision-Invion/actions/runs/36377513831)이다. exact source head는 `de9d8a4e76e3895325e79c46b536ad42b54dbea1`, checkout tree는 `c29f49bcfdac85e7e37c8a0b3d7ed1c17b8f72f4`, clean checkout은 `true`다. PostgreSQL은 `16.15`, source/restore disposable DB 2개를 만들고 둘 다 제거해 residue `0`, cleanup error `0`이다. JUnit은 **3 tests / 0 failures / 0 errors / 1 skipped**이며 skip은 reversible tail 0의 구조적 `NOT_APPLICABLE`이다.

실행은 `0045_discovery_machine_cred` snapshot을 복원해 `0046_model_manifest_readiness`까지 forward했다. pre-forward sentinel 보존, post-forward sentinel의 snapshot 비포함, catalog 9개 section(table 155, column 1393, constraint 844, index 387, function 42, table grant 1509, routine grant 55, policy 149, role membership 0)이 일치했다. catalog hash는 `df97a8f84c63901870efad6393554e164afe7464340af54d62c57ac6170ba902`, JUnit hash는 `abf6a0b9daa2edc11b8150d0e43633786ab93a5b7eec5f7b791353ef5a4ed7b4`다. artifact `10952070190`의 digest는 `sha256:9813e6aa323e06811ce35f065a5e0f04929ffe4a21346eba4a5e644df4a9c5be`, 만료는 `2026-10-28T04:24:17Z`다.

이 결과는 hosted 단일 PostgreSQL restore 축의 PASS다. lossy-reversible 10개 개별 published-prior restore, 실제 PITR, 5노드·실장비 축은 측정하지 않았으며 AC-11 전체 done이나 S11 상태 승격을 주장하지 않는다.
