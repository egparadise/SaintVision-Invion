---
doc_id: "CLAUDE-S03-ST-EVIDENCE-MAP-001"
title: "S03-ST 볼륨·Artifact 기본 전송 Evidence 대응표 — Workspace 볼륨·Artifact 업로드/다운로드·checksum 검증·허용/거부 기록·exit code·증거 ID를 기존 코드·시험·hosted run에 file:line과 run ID로 대응, S3 ObjectStore는 #149/#159 인용, 공백 NOT_OBSERVED 1·설계/타 PR 2·BLOCKED_EXTERNAL 1 (구현 추가 0, 카드 az)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:51:32+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S03-ST"]
tags: ["S03-ST", "AC-03", "evidence", "workspace", "artifact", "checksum", "audit", "claude"]
---

# S03-ST Evidence 대응표 (2026-09-28, 카드 az)

task-registry S03-ST: scope "볼륨·Artifact 기본 전송", evidence "허용·거부 로그·exit code·증거 ID", AC-03 "허용 실행 성공, 금지 경로/명령 차단, 종료 후 자원 회수". 원칙은 #155·#160·#161과 같다: 이미 있는 것을 file:line·run ID로 대응하고 공백만 골라낸다, 관측 안 된 값은 NOT_OBSERVED, 판정 논리 복제 없음. S3 ObjectStore와 겹치는 부분은 **#149(v1 승인)·#159(v2 검토 중)를 인용**하고 새로 만들지 않는다. 결론 먼저 — **다섯 범위 모두 코드·시험·hosted lane이 있다(#121 S03 collector가 AC-03 4조항으로 매핑). 이 PR은 대응표만 담는다(구현·시험 추가 0). 공백은 Windows 로컬의 Linux 게이트(NOT_OBSERVED) 1, S3 제품 경로(#159 검토 중)·`public.audit_events` RLS(F-S02-01 별도 카드) 2, 실 5노드 전송(BLOCKED_EXTERNAL) 1.**

## 0. 인용 run·근거

| lane / 근거 | run / head | 결과 |
|---|---|---|
| Core (`run-core`) | **36353272311** `bc27588d`(#126) | success — `workspace-tests.xml` 22/22(`core.yml:133` test_workspace_resume+test_workspace_api), `containment-tests.xml` 28/28(`:135`), `core-tests.xml` 3253/3236/17 skipped(exact map; test_execution·test_output_ingestion·test_node_delivery·test_node_storage_transport·test_workspace_start/checkout 포함), `lan-installer-tests.xml` 15/15 |
| Backend | **36351202242** `a0dab579`(#125 = base 집합) | 2929 passed / 47 skipped / 0 failed — `tests/test_execution.py` 25·`test_verification.py` 12·`test_verification_readroot.py` 18·`test_backup_verification_integrity.py` 11·`test_workspace_package.py` 16·`tests/core/test_sandbox_contracts.py` 5·`test_artifact_content_contract.py` 7·`test_decided_resource_and_download_contracts.py` 5·`test_server_config_volume.py` 3·`test_docker_volume_provenance.py` 2·`tests/integration/test_tool_admission.py` 11·`test_storage_commit.py` 14·`test_output_ingestion.py` 5·`test_node_delivery.py` 14·`test_definer_audit.py` 8·`test_api.py`(denial 기록) 포함 |
| S03 collector | PR #121 `tools/collect_s03_acceptance_evidence.py` | AC-03 4조항(allowed-execution-succeeds·forbidden-path-or-command-blocked·resources-reclaimed-after-exit·evidence-id-and-output-hash-enforced) + DB lane C1~C4·container lane P1~P4(`collect_container_evidence`), Docker lane opt-in |
| S3 ObjectStore | PR #149 `5a794ae9`(v1 승인) · #159 `ba345680`(v2 검토 중) | locator 기반 `ObjectStore` SPI, `LocalObjects` 호환, `S3Objects` 실바이트 SHA-256 검증·fail-closed 거부·verified delete(#149); provider/locator identity 영속·`configurationReadiness.objectStore`·Artifact read ticket·hosted MinIO 제품 경로(#159) |

## 1. 대응표

### 1.1 Workspace 볼륨

| 항목 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| 개인 트리·복원 세대·작업 세대(발행 시 검증) | `services/control-plane/src/inv/workspace_files.py:134 PrivateTree`, `:253 RestoreGenerations`(`:272 publish`, `:355 _verify`), `:412 WorkingGenerations`(`:424 inspect_committed`) | `tests/integration/test_workspace_resume.py`·`test_workspace_api.py`(Core 22) · `test_workspace_recovery.py`·`test_workspace_recovery_http.py` | Core 36353272311 `workspace-tests.xml` 22/22 | 관측됨 |
| Workspace 시작·checkout(볼륨 마운트·입력 준비) | `inv/workspace_start.py:72 WorkspaceStart`, `workspace_git.py`, `workspace_config.py` | `tests/integration/test_workspace_start.py` 16 · `test_workspace_checkout.py` 5 · `tests/core/test_workspace_start_contract.py`·`test_workspace_manifest.py`·`test_workspace_package.py` 16 | Core core-tests · Backend | 관측됨 |
| 볼륨 provenance·서버 config 볼륨 | `deploy/`·compose 볼륨 선언 | `tests/test_docker_volume_provenance.py` 2 · `tests/core/test_server_config_volume.py` 3 | Backend | 관측됨 |
| 업그레이드 시 Workspace 볼륨 보존 | `inv/workspace_recovery.py` | `tests/integration/test_workspace_upgrade.py`(Core lan-installer step) | Core `lan-installer-tests.xml` 15/15 | 관측됨(hosted Linux Docker) |

### 1.2 Artifact 업로드·다운로드

| 항목 | 코드 | 시험 | hosted 파일 | 상태 |
|---|---|---|---|---|
| Node→CP 출력 전달(stdout/stderr 해시·재전송·재시도 예산 3·overflow 실패) | `inv/output_ingestion.py:20 output_bytes`, `:60 OutputIngestion`(`:104 exitCode≠0`) · `inv/node_execution.py` | `tests/integration/test_output_ingestion.py` 5(:37 실 해시 → evidence, :100 재시도 3, :125 overflow) · `test_node_delivery.py` 14 | Core core-tests(카드 12 hosted 대조: output_ingestion 5·node_delivery 18 케이스 passed) | 관측됨 |
| Node 스토리지 전송 경계(chunk·크기 한도) | `inv/node_execution.py`, `src/saintvision/storage/readroot.py:109 ReadRoot` | `tests/integration/test_node_storage_transport.py` 11 · `tests/core/test_node_chunk.py` | Core core-tests(27 케이스) | 관측됨 |
| Artifact 결과·목록·내용 다운로드 route(권한·내용 계약) | `inv/app.py:470-481` (`/v1/…/runs/{run_id}/result`, `/artifacts`, `/artifacts/content`), `inv/result_view.py` | `tests/core/test_artifact_content_contract.py` 7 · `test_decided_resource_and_download_contracts.py` 5 · `tests/integration/test_result_observation.py` 5 | Backend·Core | 관측됨 |
| 객체 저장(put/digest) — Local | `inv/object_store.py:23 LocalObjects`, `:64 ObjectHandle`(`:93 put(name, data, digest)`) | `tests/integration/test_output_ingestion.py:82 publication_crash_reuses_ready_object` | Core | 관측됨 |
| 객체 저장 — S3(실바이트 SHA-256·fail-closed·verified delete·제품 경로) | **#149 `ObjectStore` SPI·`S3Objects`**, **#159 provider identity·read ticket·MinIO 제품 경로** | #149·#159의 시험(그 PR 인용) | #159 hosted MinIO lane | 관측됨(#149 승인) / **#159 검토 중**(이 문서에서 새로 만들지 않음) |

### 1.3 checksum 검증

| 항목 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| `inv://` URI 범위 해석·내용 hash/size 검증 | `inv/storage.py:20 parse_uri`, `:67 resolve_scoped`, `:82 verify_content(path, expected_hash, expected_size)` · `src/saintvision/storage/pathsafe.py:163/182/212/235` | `tests/test_verification_readroot.py` 18 · `tests/core/test_sandbox_contracts.py` 5 | Backend | 관측됨 |
| 파일·백업·replica 바이트 검증(잘린 파일도 유효 SHA → 내용 비교) | `src/saintvision/services/verification.py:74 hash_file`, `:150 verify_backup_bytes`, `:225 verify_replica_bytes`, `:255 verify_pending_backups` | `tests/test_verification.py` 12(:158 truncated) · `test_backup_verification_integrity.py` 11 | Backend | 관측됨 |
| Artifact는 검증 없이는 active 불가 | `src/saintvision/services/…`(artifact status·checksum) | `tests/test_execution.py:674 an_artifact_cannot_be_active_without_verification` | Backend | 관측됨 |
| 제공 폴더 sample commit·손상 row 거부 | `inv/storage_commit.py:42 StorageSampleStore`(`:98 issue`, `:27 refused`) · `storage_sampling.py` · `src/saintvision/storage/sampling.py:10 check_sample` | `tests/integration/test_storage_commit.py` 14 · `test_storage_view.py` 11 · `tests/test_storage_check_integrity.py` 13 | Backend·Core | 관측됨 |

### 1.4 허용·거부 기록 (로그·audit)

| 항목 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| 정책 결정 강제(action digest 결속) | `inv/policy.py:10 action_digest`, `:18 enforce_decision` | `tests/core/test_sandbox_contracts.py` · `tests/integration/test_tool_admission.py` 11(위조 outbox·stale node·미검증 runtime·revoke 뒤 claim 중지) | Backend·Core | 관측됨 |
| 샌드박스 필수 capability(`network_deny`·`read_only_root`·`cap_drop_all`…) 없으면 실행 거부 | `inv/sandbox.py:14-28 REQUIRED_CAPABILITIES`, `:33 SandboxProfile`, `:81 RuntimeCapabilities`, `:106 compile_launch` | `tests/core/test_sandbox_contracts.py` 5 · `tests/test_execution.py` 25 | Backend | 관측됨 |
| 격리·물리 정리(containment) | `inv/containment.py:15 require_execution`, `:55 Containment`, `:204 ContainmentReconciler` | `tests/integration/test_containment.py` 23 함수(Core 28 케이스) | Core `containment-tests.xml` 28/28 | 관측됨 |
| 거부·인증 실패의 audit 기록(redaction, 트랜잭션 밖 기록) | `src/saintvision/services/audit.py:47 redact`, `:66 record_event`, `:106 record_denial_out_of_band` | `tests/test_api.py`(denials_are_recorded 등, #120 S02 collector 조항) · `tests/test_database.py` · `tests/integration/test_definer_audit.py` 8 | Backend | 관측됨 |
| `public.audit_events`의 RLS ENABLE+FORCE | — | `tools/collect_rls_evidence.py` E2 위반 1(#120 evidence) | Backend | **F-S02-01 별도 카드**(Codex 판정: baseline 수용 기각, RLS+audit writer/reader 역할) |

### 1.5 exit code·증거 ID

| 항목 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| 증거 ID 결정성(`evd_` + command 기반 Crockford 26) | `inv/output_ingestion.py:51 evidence_id` | `tests/integration/test_output_ingestion.py:37` · `test_results.py`(evidence pin) | Core | 관측됨 |
| exit code≠0·미확인 stop은 성공 아님 | `output_ingestion.py:104`, `inv/results.py:93,:192` | `tests/integration/test_result_observation.py:166 failed_process_reports_actual_exit_without_success_evidence` · `test_output_ingestion.py:125` | Core | 관측됨 |
| RunRecord 완료 파이프라인(receipt·pin·epoch·mTLS stop→verifier) | `inv/results.py:22 ResultStore` | `tests/integration/test_results.py` 14(`skipif(sys.platform != "linux")`) | Core·Backend(ubuntu) 실행 / **이 PC skip** | 관측됨(hosted) / NOT_OBSERVED(로컬) |
| AC-03 조항 집계(exit·JUnit·lane) | #121 `collect_s03_acceptance_evidence.py`(PASS_MEASURED_PARTIAL·passScope) | `tests/test_collect_s03_acceptance_evidence.py` 96 | Backend 36351646801(#121) | 관측됨(승인) |

## 2. 공백 목록 (구현·시험 추가 없음)

| # | 공백 | 분류 | 이유 / 처리 |
|---|---|---|---|
| G1 | `test_results.py` 14 케이스(RunRecord 완료·실 출력 바이트)가 Windows(이 PC)에서 Linux 사설 스토리지 게이트로 skip | **NOT_OBSERVED(로컬)** | hosted Core/Backend(ubuntu)에서 실행됨; 로컬에서 메울 도구 없음(#131·#161과 동일 판단) |
| G2 | S3 ObjectStore 제품 경로(provider identity·read ticket·MinIO hosted) | **#159 검토 중** | #149 v1 승인·#159 v2 Codex 검토 — 이 문서는 인용만, 새로 만들지 않음 |
| G3 | `public.audit_events` RLS ENABLE+FORCE 부재(허용·거부 로그 테이블의 tenant 경계) | **별도 카드(F-S02-01)** | #120 evidence E2 위반 1; Codex가 baseline 수용을 기각하고 RLS + 별도 writer/reader 역할 + 시험 4종을 요구 — 코디네이터 배정 대기 |
| E1 | 실 5노드 Node→CP Artifact 전송·볼륨 마운트 | **BLOCKED_EXTERNAL** | 물리 PC(ADR-100: Ubuntu worker 3 등록·CP 겸임 BLOCKED); hosted는 synthetic Node·컨테이너 |

작은 PG-free 불변식 시험으로 메울 행동 공백은 **없다**: 허용/거부·exit code·증거 ID·checksum·볼륨 보존이 전부 기존 시험(Backend·Core)으로 단언된다. 따라서 docs-only.

## 3. 경계

로컬 실 PG·Docker·전체 suite·무거운 명령 없음(메모리 0.6GB). 판정 논리 복제 없음. owner Claude / reviewer Codex / 병합 금지. worktree 재사용, branch `agent/claude/s03-st-evidence-map`, base `1e8baf04`. S03-ST `planned` 유지. 다음 첫 행동: Codex 검토 → G2는 #159, G3는 F-S02-01 카드.
