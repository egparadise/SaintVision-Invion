---
doc_id: "CLAUDE-S12-ST-EVIDENCE-MAP-001"
title: "S12-ST 운영 점검·제공 폴더·복구 훈련 Evidence 대응표 — 세 범위별 기존 도구·시험·hosted lane을 file:line과 run ID로 대응, 공백은 NOT_OBSERVED/BLOCKED_EXTERNAL로 분리 (구현 추가 0, 카드 as)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T12:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S12-ST"]
tags: ["S12-ST", "AC-12", "evidence", "storage", "recovery-drill", "operational-check", "claude"]
---

# S12-ST Evidence 대응표 (2026-09-28, 카드 as)

task-registry S12-ST: scope "운영 점검·제공 폴더·복구 훈련", evidence "Release manifest·사용자 인수·웹 smoke·복구 Evidence", AC-12. 이 문서는 **이미 있는 것**을 file:line·run ID로 대응시키고 **공백만** 골라낸다. 원칙은 #153 S12-DB collector와 같다: 관측 안 된 값은 NOT_OBSERVED, 판정 논리는 복제하지 않는다. 결론 먼저 — **세 범위 모두 도구·시험·hosted lane이 이미 있고, 남은 공백은 실장비·사용자 입력·CX-09 결정(BLOCKED_EXTERNAL) 4건과 hosted 관측 한계(NOT_OBSERVED) 1건이다. 새 구현은 넣지 않았다.**

## 0. 인용 run (전부 hosted CI, 통합 base `1e8baf04` 위)

| lane | run | head | 결과 |
|---|---|---|---|
| Core (`run-core`) | **36353272311** | `bc27588d`(#126) | success 37 step; `cx01-recovery-tests.xml` 20/18 passed/2 skipped(archiver 2, 사유 고정)/0 failed; `lan-installer-tests.xml` 15/15; `containment-tests.xml` 28/28; `core-tests.xml` 3253/3236/17 skipped(exact map) |
| Backend | **36351202242** | `a0dab579`(#125, docs-only = base 시험 집합) | 2929 passed / 47 skipped / 0 failed (3.12·3.14) |
| Backend | **36363486696** | `f97c48d5`(#150) | 2958/47/0 — retention 37·하네스 6 포함 |
| desktop-browser | **36364528322** | `30f5ca83`(#153) | pass — 브라우저 여정 5개 전부 실행(`vf-desktop-browser-ci.json` proof, 여정 집합 고정 `desktop-browser.yml:57-77`) |

## 1. 대응표

### 1.1 운영 점검 (operational check)

| 항목 | 도구 | 시험 | hosted lane / run | 상태 |
|---|---|---|---|---|
| 운영 입력 존재(폴더 제공·capability·offer) | `tools/operational_readiness.py:97 inputs()` (`public.storage_contributions status='active'`·`node_capabilities`·`resource_offers` count) | `tests/test_operational_readiness.py` 10건(:194 ready, :206 missing input 공급자 명시) | Backend 36351202242 | 관측됨(PG-free+실PG) |
| 기록된 offer ↔ 커널 offer | `operational_readiness.py:227 offers()` | `test_operational_readiness.py:320` | Backend | 관측됨 |
| admission gate(진단, 실행 승인 아님) | `operational_readiness.py:437 admission()` (`scope=diagnostic-not-execution-admission`) | `test_operational_readiness.py:286,:308` | Backend | 관측됨 |
| 알람(스큐·파티션·count) | `tools/alarm_check.py:178 evaluate()` (GOV-ALERT-001) | `tests/test_alarm_check.py` 22건 | Backend; 실측 `Evidence/alarm-check-live-7168d573-20260922.json` | 관측됨 |
| AC-12 기록 catalog 집계(`catalogComplete`·`acceptanceAssessed`) | `operational_readiness.py:688 report() → :546 _acceptance_evidence()` → `src/saintvision/services/pilot.py:475 pilot_readiness()` | `tests/test_pilot.py:511,:536,:629,:655` | Backend | 관측됨 |
| 항목별 PASS/FAIL/NOT_OBSERVED/BLOCKED_EXTERNAL 분류 | `tools/collect_s12_acceptance_evidence.py`(#153) | `tests/test_collect_s12_acceptance_evidence.py` 111 + postgres 1 | Backend(#153 run은 PR 코멘트) | 관측됨(PR 검토 중) |

### 1.2 제공 폴더 (contributed folders)

| 항목 | 도구 | 시험 | hosted lane / run | 상태 |
|---|---|---|---|---|
| 제공 폴더 로컬 샘플 점검(읽기 전용, `--node`는 주장이지 증명 아님) | `tools/storage_check.py:40 run()` → `pilot.py:230 record_storage_check()` | `tests/test_storage_check_integrity.py` 13건(:71 read-only·attestation 아님, :94 미검증 bytes 불통과, :129 junction 거부, :236 DSN 미출력, :248 실제 CLI) | Backend | 관측됨 |
| 주의 필요 폴더 판정(미점검·stale·mismatch·unreachable) | `pilot.py:284 contributions_needing_attention()` | `tests/test_pilot.py:298,:311,:323,:339,:349,:367` | Backend | 관측됨 |
| Storage sample commit·관측 view(손상 row 거부) | `tests/integration/test_storage_commit.py` 14 · `test_storage_view.py` 11(#137로 owner corruption 되돌림) | 동일 | Backend·Core | 관측됨 |
| Node 스토리지 전송 경계 | `tests/integration/test_node_storage_transport.py` 11 | 동일 | Core(핸드오프 기록 "노드 스토리지 전송 27" 케이스) | 관측됨 |
| LAN 설치본의 storage source root·installer 수용 | `tools/check_storage_bundle.py`(synthetic PKI·owned Docker) · `tools/check_lan_storage_readiness.py`(읽기 전용 인벤토리) | `tests/integration/test_lan_storage_install.py` 5 + `test_workspace_upgrade.py` | Core 36353272311 `lan-installer-tests.xml` 15/15 (`core.yml:103-112` source root 제공, `:141-146` 전부 실행·통과 강제) | 관측됨(hosted Linux Docker) |
| 파일럿 실제 제공 폴더(허용 폴더 목록·contribution_id·root_version) | — | — | — | **BLOCKED_EXTERNAL** (U5 사용자 결정 C2; S01 Node 인벤토리 실측 초안(PR #134) C2 전부 사용자 결정, `inv.resources` 0행) |

### 1.3 복구 훈련 (recovery drill)

| 항목 | 도구 | 시험 | hosted lane / run | 상태 |
|---|---|---|---|---|
| DB 백업→disposable 복원→무결성·fencing·목표 판정·기록 | `tools/recovery_drill.py:1163 main()`, `:838 _restore_and_verify()`, `:470 _recovery_capability()`, 기록 `:1070 record_backup`/`:1080 verify_backup`/`:1087 record_recovery_drill` | `tests/integration/test_recovery_drill.py` 13 함수 = 20 케이스 (`args` fixture → `resolve_owned_postgres_container`) | Core 36353272311 focused `cx01-recovery-tests.xml` **18 passed / 2 skipped / 0 failed** (#126: owned CX01 컨테이너, `core.yml:174-207` gate) | 관측됨(hosted) |
| drill 기록 규칙(측정치·checksum·fencing·목표 미달 표기) | `pilot.py:142 record_recovery_drill()`, `:83 record_backup()`, `:119 verify_backup()` | `tests/test_pilot.py:93,:106,:119,:137,:152,:165,:226,:245,:260,:718` | Backend | 관측됨 |
| PITR 설정 가능 여부(configuration-only) | `tools/pitr_readiness.py:15 assess()` | `tests/test_pitr_readiness.py` 7 · `tests/test_pitr_boundary.py` 11 | Backend | 관측됨(`pitrVerified=false` 고정) |
| WAL archive·base backup 7일 보관 계획(dry-run, label 시각 fail-closed) | `tools/pitr_archive_retention.py`(#150) | `tests/test_pitr_archive_retention.py` 37 | Backend 36363486696 | 관측됨 |
| PITR opt-in 리허설(읽기 전용, mutation 0) | `tools/pitr_opt_in_dry_run.py:23 rehearse()` | `tests/test_pitr_opt_in_dry_run.py` 6 | Backend 36363486696 | 관측됨 |
| live archiver로 운영 RPO 인증 불가 확인(2 케이스) | `test_recovery_drill.py:488-579 test_live_archiver_configuration_cannot_certify_operational_rpo[/bin/true, /bin/false]` | 동일 | Core 36353272311에서 **skipped 2**(사유 `:191-198`: 내부 네트워크 컨테이너를 host pytest가 Docker 이름으로 못 닿음; inspect로 running·ready·hostPortPublished=False 확인 뒤에만 skip) | **NOT_OBSERVED(hosted)** — 아래 공백 G1 |
| 실 PITR target-time 복구·운영 RPO/RTO·전체 서비스 복원 | — | — | — | **BLOCKED_EXTERNAL** (Tier-A 결정 B 유예; [[2026-09-22_CX-09_PITR_Tier-A_활성여부_결정준비_Claude]]) |

### 1.4 registry evidence 4종 ↔ 위치

| evidence | 만들어지는 곳 | 읽는 곳 | 상태 |
|---|---|---|---|
| Release manifest | `pilot.py:358 create_release_manifest()`(`tests/test_pilot.py:400`) | #153 `release-manifest-recorded` | BLOCKED_EXTERNAL(release cut = 사용자 입력) |
| 사용자 인수 | `pilot.py:396 record_acceptance()`(`test_pilot.py:418,:437,:463,:488`) | #153 `user-acceptance-record-ac12` | BLOCKED_EXTERNAL(사용자 승인) |
| 웹 smoke | `desktop-browser.yml:52-77` 여정 5개 → `vf-desktop-browser-ci.json` | #153 `web-smoke-journeys`(`--web-smoke-proof`) | 관측됨(hosted runner); 물리 Node·인증 브라우저 인수는 BLOCKED_EXTERNAL |
| 복구 Evidence | §1.3 전부 | #153 recovery 그룹 6항목 | 관측됨(hosted)·실 PITR BLOCKED_EXTERNAL |

## 2. 공백 목록 (구현 추가 없음 — 판단 근거 포함)

| # | 공백 | 분류 | 이유 / 다음 |
|---|---|---|---|
| G1 | live archiver 2 케이스가 hosted Core에서 항상 skip(`Docker-only name`) → 운영 RPO "인증 불가" 단언이 hosted에서 실행되지 않음 | **NOT_OBSERVED(hosted)** | 도구/시험으로 메울 수 있으나 `test_recovery_drill.py:533`의 접속 경로(컨테이너 이름 → host 도달 경로) 변경이 필요하고 #126 검토에서 "시험 변경, 별도 검토"로 남긴 항목. 이 카드에서 만들지 않음; Codex 판단(skip 사유는 이미 정직하게 gate에 고정) |
| G2 | 파일럿 실제 제공 폴더 점검(허용 폴더·contribution·root_version) | **BLOCKED_EXTERNAL** | U5 사용자 결정(C2); 도구(`storage_check.py`)·기록(`record_storage_check`)·판정(`contributions_needing_attention`)은 있음 |
| G3 | verified off-site backup 선언·실 failure-domain bytes | **BLOCKED_EXTERNAL** | 운영자 선언(ADR-018); 기록 경로 `record_backup(off_site=…)`·`verify_backup` 있음 |
| G4 | 실 PITR 복구·운영 RPO/RTO·전체 서비스 복원 | **BLOCKED_EXTERNAL** | CX-09 Tier-A 결정 B 유예; dry-run·readiness·retention까지만 관측 |
| G5 | Release manifest·사용자 인수·물리 Node 브라우저 인수 | **BLOCKED_EXTERNAL** | 사용자 입력; 기록·비교 경로와 collector 항목은 있음 |

도구·시험으로 메울 수 있는 공백 중 **이 카드에서 최소 구현이 필요한 것은 없다**(G1은 별도 검토 대상). 따라서 docs-only.

## 3. 경계

- 판정 논리 복제 없음: 이 문서의 "관측됨"은 인용한 run의 JUnit/proof 결과이며, 각 도구의 verdict 의미(`scope=diagnostic…`, `pitrVerified=false`, `catalogComplete≠운영 인수`)를 바꾸지 않는다.
- 로컬 실 PG·Docker·전체 suite 실행 없음. run ID는 `gh run view`/artifact 파싱(#126 검토·#150·#153 코멘트)에서 인용.
- owner Claude / reviewer Codex / 병합 금지. worktree 재사용, branch `agent/claude/s12-st-evidence-map`, base `1e8baf04`. S12-ST `planned` 유지. 다음 첫 행동: Codex 검토 → G1은 Codex 판단 → G2~G5는 사용자 입력 뒤.
