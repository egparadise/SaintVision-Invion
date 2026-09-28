---
doc_id: "DESIGN-S11-ST-FAILURE-001"
title: "S11-ST 손상·용량·backup 장애 시험 설계"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-28T15:17:15+09:00"
source_of_truth: "Git"
task_id: "S11-ST"
acceptance_id: "AC-11"
reviewer: "Claude"
---

# S11-ST 손상·용량·backup 장애 시험 설계

## 0. 결정과 경계

이 문서는 S11-ST의 `손상·용량·backup 장애 시험`을 구현하기 전 고정하는 v1 목표다. 공개 HTTP 계약과 migration은 바꾸지 않는다. 구현·hosted 실행·실장비 실행은 이 설계 승인 뒤 별도 카드로 분리하며, 이 문서 자체는 어떤 시나리오도 `MEASURED_PASS`로 주장하지 않는다.

AC-11의 닫힌 8축에는 별도 `storage-failure` 축을 추가하지 않는다. 이 카드의 hosted fault matrix는 축 PASS가 아니라 구현·분류를 검증하는 reference evidence다.

- 객체 손상·부분 쓰기·용량 소진의 hosted 결과는 `long-soak` PASS 분자에 넣지 않는다. `long-soak`은 ADR-100의 CP 겸임 Node를 제외한 물리 4 eligible Node에서 24시간을 충족하는 별도 target이며, 같은 target에 corruption escape·false success·resource drift 기준을 포함한다.
- WAL archive 장애와 보존 만료 중 장애는 `actual-pitr-rpo-rto-retention` 축에 넣는다. hosted MinIO·PostgreSQL 또는 same-host dry-run은 준비·기전 증거일 뿐 이 축의 PASS가 아니다.
- 별도 장애 영역의 운영 archive와 복구, 실제 용량 고갈이 필요한 단계만 `BLOCKED_EXTERNAL`이다. PG-free와 hosted에서 실행 가능한 항목을 `BLOCKED_EXTERNAL`로 낮추지 않는다.

정본 target registry는 #177의 `Evidence/s11-ac11-target-registry-v0.json` 하나뿐이다. 이 PR의 `Evidence/s11-st-failure-target-registry-patch-v0.json`은 적용할 patch의 review artifact이며 `targetRef.path`로 제출할 수 없다. 후속 Codex 카드가 #177 병합 뒤 정본 registry에 물리 long-soak target을 추가하고, 약한 `s11-actual-pitr-v0`를 archive fault target으로 교체하고, 집계기의 `TARGET_REGISTRY_BLOB`과 축별 허용 targetId map을 함께 갱신한다. 이 선행 카드가 merge되기 전에는 측정을 시작하지 않는다. 고정 기준은 [[S11_ST_storage_failure_target_v0]]에 두며, 결과를 본 뒤 임계치를 바꾸지 않는다.

## 1. 현재 코드가 실제로 보장하는 것

아래 줄 번호는 검토 가능한 exact head에 고정한다. PR #159의 제품 S3 adapter는 `c654fada64a3d6804416c928908fdeb7566dfb2e`, 관찰 후속 PR #173은 `288ee0b64c724dbff1c8705453f0d25275492318`, VF-CL-04 retention PR #150은 `f97c48d519496386062ebb55e5aad75c91b61423`이다. 이 PR들이 integration에 merge되지 않은 동안에는 candidate 코드이며 운영 완료 근거가 아니다.

| 경계 | 현재 결속 | 실제 보장 | 아직 없는 보장 |
|---|---|---|---|
| S3 byte·metadata 검증 | `services/control-plane/src/inv/s3_object_store.py:89-115,118-154` at #173 | body hash·size·`x-amz-meta-content-sha256` 불일치는 `VERIFY-0010`/422/non-retryable, provider 비가용은 `STORE-0001`/503/retryable | 실제 vendor quota·network partition·multipart 중단 인수 |
| S3 모호한 PUT | 같은 파일 `:118-146` | timeout·409·412·5xx 뒤 GET으로 실제 byte를 확인한다. 이전 byte와 다르면 `STORE-0005`/409, 성공 응답 뒤 저장 byte가 다르면 `VERIFY-0010`/422 | 장애 주입 hosted 반복과 실제 provider의 read-after-write 특성 |
| S3 삭제 | 같은 파일 `:173-182` | DELETE 뒤 HEAD가 여전히 존재하면 `STORE-0001`/503/retryable | lifecycle·versioned-delete·운영 GC |
| Local byte read | `services/control-plane/src/inv/object_store.py:215-285` at #173 | regular/single-link/owner/read-only/size 경계를 확인하고 hash 불일치는 `VERIFY-0010`, handle·size 불일치는 `STORE-0003`/422 | 읽기 도중 disk I/O 오류의 정본 DomainError 변환 |
| Local publish | 같은 파일 `:287-318` | temp write→file fsync→rename→directory fsync, finally temp unlink | `ENOSPC`·`EDQUOT`·fsync 실패는 아직 raw `OSError`가 될 수 있고, directory fsync 실패 뒤 durable 상태를 분류하는 증거가 없다 |
| 논리 quota | `services/control-plane/src/inv/snapshots.py:144-178` at #173 | project budget row를 잠그고 `used + size`가 budget을 넘으면 byte write 전 `RES-0001`/409/non-retryable | provider 물리 용량과 DB quota가 함께 고갈될 때의 통합 증거 |
| retention plan | `tools/pitr_archive_retention.py:13-40,184-232` at #150 | 최신 backup, unknown-age backup, 유지 경계 이후 WAL, history·partial을 보존한다. 모호한 label은 계획 전체를 거부한다 | 운영 35일·별도 장애 영역·복구 성공 |
| retention apply | 같은 파일 `:235-275` | 계산한 후보만 순차 삭제한다 | 중간 unlink/rmtree 실패 시 journal·원자 rollback이 없고 일부 후보가 이미 삭제될 수 있다 |
| PITR readiness | `tools/pitr_readiness.py:15-45,60-81`, `tools/pitr_opt_in_dry_run.py:24-77,90-130` at #150 | 설정 관측은 항상 `pitrVerified:false`; `--require-pitr`는 exit 1, dry-run은 retention 적용·재시작·설정 변경을 하지 않는다 | 연속 WAL 전달, 목표 시각 복구, RPO/RTO, off-site 내구성 |

따라서 Local disk-full과 retention apply 중단을 현재 통과 항목으로 세지 않는다. 구현 카드는 새 공개 code를 만들지 않고 Local provider의 `OSError`를 기존 `STORE-0001`/503/retryable로 변환하고, retention runner에는 공개 ProblemDetails가 아닌 닫힌 evidence `failureClass`를 추가해야 한다.

## 2. 사전 등록 fault matrix

### 2.1 객체 손상과 부분 쓰기

| ID | 주입 | 기대 표면 | 데이터 보존 단언 | 현재 판정 |
|---|---|---|---|---|
| `OBJ-01` | 저장된 body 1 byte 변조 | S3·Local 모두 `VERIFY-0010`/422/non-retryable | 손상 byte 반환 0, DB digest 변경 0 | S3·Local 코드 경계 존재, 실행 증거 필요 |
| `OBJ-02` | 기대 size와 실제 size 불일치·truncate·append | S3는 `VERIFY-0010`/422/non-retryable, Local truncate·append는 `STORE-0003`/422/non-retryable | 부분 byte 반환 0 | 단위 경계 존재, hosted 반복 필요 |
| `OBJ-03` | S3 metadata digest만 변조 | read는 `VERIFY-0010`/422/non-retryable | body가 맞아도 성공 0 | S3 시험 존재, 제품 path hosted 필요 |
| `OBJ-04` | Local write/fsync/rename 단계 실패 또는 S3 publish 불확실성 | Local write·file fsync·directory fsync 실패는 `STORE-0001`/503/retryable. S3 성공 응답 뒤 partial은 `VERIFY-0010`/422/non-retryable, 모호한 PUT 뒤 다른 byte는 `STORE-0005`/409/non-retryable | 이전 canonical object는 byte-for-byte 불변, 새 canonical partial 0, temp residue 0, metadata commit 0 | Local 오류 변환·durability 분류는 구현 공백 |

`OBJ-04`의 Local directory fsync 실패는 rename 뒤 상태가 보일 수 있다. 실패를 성공으로 낮추지 않고 `STORE-0001`을 반환한다. 동일 digest retry는 기존 exact byte를 재검증해 quiet success할 수 있지만, 최초 호출의 실패를 성공으로 소급하지 않는다.

### 2.2 용량 소진

| ID | 주입 | 기대 표면 | 데이터 보존 단언 | 현재 판정 |
|---|---|---|---|---|
| `CAP-01` | DB project quota를 1 byte 초과 | `RES-0001`/409/non-retryable | storage row·provider byte·usage 초과 0 | 코드 경계 존재, 동시성 hosted 증거 필요 |
| `CAP-02` | 새 key에 Local `ENOSPC`/`EDQUOT` 또는 S3 507 | `STORE-0001`/503/retryable | `begin` 완료 뒤 실패한 part row 0, `ready` 전이 0, 사용량은 예약분만, 이전 object 손실 0, partial/temp residue 0 | S3 non-success 변환은 존재, Local 변환은 구현 공백 |

quota 시험은 “요청 실패”만 보지 않는다. `snapshots.py:166-177`의 `begin`이 `uploading` row와 예약 사용량을 먼저 commit하므로 기준 시점은 `begin` 직후로 고정한다. failure 뒤 DB 사용량, part row, `ready` 전이, immutable object hash, temp key, S3 canonical key를 다시 읽고 초과 예약·부분 publish가 모두 0임을 확인한다.

### 2.3 backup·archive 장애

이 경로는 공개 HTTP route가 없으므로 가짜 ProblemDetails code를 만들지 않는다. runner의 닫힌 `failureClass`와 process exit로 판정한다.

| ID | 주입 | 기대 표면 | 데이터 보존 단언 | 현재 판정 |
|---|---|---|---|---|
| `BAK-01` | `archive_command` write refusal·timeout·archive 목적지 full | `failureClass=WAL_ARCHIVE_FAILED`, nonzero exit, `pitrVerified=false`; 설정 `possible`을 PASS로 세지 않음 | 미전달 WAL을 삭제·재활용했다는 주장 0, 복구 성공 주장 0 | hosted 기전과 운영 별도 장애 영역 증거 모두 필요 |
| `BAK-02` | retention 만료 후보 삭제 중 unlink/rmtree 실패 | `failureClass=RETENTION_APPLY_PARTIAL`, nonzero exit, 삭제 receipt와 미완료 후보를 모두 기록 | 최신·unknown-age backup, oldest-retained boundary 이후 WAL, `.history`·`.partial` 삭제 0 | 현재 apply는 부분 진행 뒤 raw 오류 가능; journal/receipt 구현 공백 |
| `BAK-03` | `archive_command` 또는 backup이 exit 0이지만 byte가 없거나 empty/truncated | source exit 0이어도 verifier는 `WAL_ARCHIVE_EMPTY` 또는 `BACKUP_ARTIFACT_INVALID`로 nonzero exit | restore 검증 전 보관 성공·PITR 성공 주장 0 | `/bin/true` archive와 empty/truncated backup 부정 시험 필요 |

`BAK-02`는 삭제 후보의 일부가 이미 사라질 수 있음을 정직하게 허용하되, 복구 경계를 구성하는 retained set은 한 건도 손대지 않는 것을 절대 불변식으로 둔다. retry는 같은 plan hash·동일 root identity일 때만 허용하고 이미 제거된 candidate는 idempotent하게 처리한다. plan 생성 뒤 root identity·label·boundary가 바뀌면 apply를 거부한다.

허용 raw case는 [[S11_ST_storage_failure_target_v0]]의 22개 identity와 SHA-256 `5d700981ee429ebbfc66b8ed28d8dc9e37e16e327a673d6061bdec5e7e334fd9`로 닫는다. 같은 case 반복으로 개수를 채우거나 provider를 바꿔치기하면 import 오류다. Local 하위 case는 PG-free 전용이며 `CAP-02`는 기존 byte가 없는 새 key에서만 실행한다.

## 3. 실행 계층

| 계층 | 실행 범위 | 허용 판정 | 금지하는 승격 |
|---|---|---|---|
| PG-free | fake S3 응답, Local temp directory fault injection, quota 계산·retention pure plan, evidence importer·mutation tests | 계약·분류·불변식의 단위 증거와 Local 하위 case | provider·운영 archive·PITR·AC-11 축 PASS |
| hosted MinIO+PostgreSQL 16 | opt-in job, scenario를 한 번에 하나씩 순차 실행, disposable bucket/DB/root, S3·quota case와 `/bin/false`·`/bin/true` archive 기전 | reference evidence만. 제품 결함은 case verdict에 보존 | `long-soak`, actual PITR·off-site·실 disk-full·물리 장애 영역 PASS |
| 물리 5노드 | ADR-100의 CP 겸임 Node 1대를 분모에서 제외하고 eligible worker 4대에서 24시간 soak, 실제 네트워크·디스크 경합과 storage fault 관측 | `s11-long-soak-physical-five-node-v0` 후보 | hosted 1시간 결과로 대체 |
| 실장비·운영 후보 | 별도 장애 영역 archive, 실제 disk/quota, WAL 전달 중단, target-time restore, retention interruption 후 복구 | `s11-st-actual-pitr-archive-failure-v0` 후보 | dry-run·same-host·설정 관측으로 대체 |

hosted job은 label 또는 `workflow_dispatch` opt-in이며 job 수준 `cancel-in-progress:false`를 쓴다. PR head를 exact checkout하고 merge ref를 쓰지 않는다. runner·PostgreSQL·MinIO image digest·설정·fault injector version·tree SHA·clean checkout을 evidence에 기록한다. 자격·endpoint 원문은 출력하지 않는다.

## 4. AC-11 target 사전 등록

### 4.1 단일 registry와 적용 책임

집계기가 허용하는 경로는 #177의 `Evidence/s11-ac11-target-registry-v0.json` 하나다. 별도 registry path allowlist 확장은 하지 않는다. 후속 Codex 구현 카드가 다음 변경을 한 commit에 묶는다.

1. `s11-long-soak-physical-five-node-v0` 추가.
2. `s11-actual-pitr-v0` 제거 및 `s11-st-actual-pitr-archive-failure-v0` 추가.
3. `REQUIRED_TARGET_BY_AXIS`에 두 axis와 유일 targetId를 고정해 target shopping 차단.
4. 집계기 `TARGET_REGISTRY_BLOB`과 migration importer의 registry pin 갱신.
5. sourceDocument commit/blob과 HEAD blob이 같은지 보는 repo 수준 시험, old target·별도 registry path·old blob 거부 시험.

이 선행 카드 이전에는 두 축 모두 `NOT_REGISTERED` 또는 기존 미충족 상태이며 측정하지 않는다. `Evidence/s11-st-failure-target-registry-patch-v0.json`은 위 patch를 검토하기 위한 비소비 artifact이고, `consumableAsTargetRef=false`를 강제한다.

### 4.2 `s11-long-soak-physical-five-node-v0`

- axis: `long-soak`.
- requiredEnvironment: `topology=physical-five-node`, `eligibleNodeCount=4`, `excludedNodeCount=1`, `sameHost=false`, `faultInjection=controlled-v1`.
- criteria: window ≥ 86,400초, attempted operations ≥ 1,000, corruption escape·false success·committed object loss·quota overshoot·classification mismatch·unexpected error·cleanup residue 모두 0, memory growth ≤ 256MiB, FD growth ≤ 32, DB connection growth ≤ 4.
- hosted 1시간 storage fault soak은 reference evidence이며 이 axis envelope로 제출하면 `INVALID_RUN`이다.

### 4.3 `s11-st-actual-pitr-archive-failure-v0`

- axis: `actual-pitr-rpo-rto-retention`.
- 목적: RPO 900초, RTO 3,600초, 35일 보존, 매주 restore smoke를 archive·retention 장애 뒤에도 만족하는지 검증한다.
- requiredEnvironment: `topology=physical`, `failureDomain=separate`, `archiveKind=operational`, `sameHost=false`, `faultInjection=controlled-v1`.
- criteria: 연속 주간 restore smoke ≥ 2주, smoke gap ≤ 7일, retention ≥ 35일, RPO ≤ 900초, RTO ≤ 3,600초, WAL archive failure ≥ 1, silent archive loss ≥ 1, retention interruption ≥ 1, fault 뒤 recovery pass ≥ 3, false PITR pass·retained-boundary deletion·cleanup residue 모두 0.
- `pitr_readiness`, `pitr_opt_in_dry_run`, same-host `pitr_rehearsal.sh`, hosted MinIO/PG는 reference observation만 허용한다.

두 target의 `sourceDocument`는 [[S11_ST_storage_failure_target_v0]]의 commit `2ac98cbec2873463f91561a20a706abeb0d776a5`, path `docs/vault/30_Development/S11_ST_storage_failure_target_v0.md`, blob `a9f5f950c14fd4b4d91f6647c5c8473a66e2c5af`를 가리킨다. 이 commit이 integration 조상으로 남도록 이 PR은 merge commit 방식(`--merge`)으로만 병합하고 squash·rebase 병합을 금지한다. envelope의 `targetRef`는 정본 registry commit/path/blob·targetId·criteria exact set을 사용한다. source document와 registry가 `sourceHeadSha`의 조상이 아니거나 source tree의 blob과 다르면 `INVALID_RUN`이다.

## 5. evidence와 fail-closed 판정

### 5.1 raw producer artifact

runner는 case별 raw JSON과 JUnit을 낸다. 각 case에는 `caseIdentity`, `provider`, `injectionObserved`, `attemptedCount`, `expectedFindingCount`, `observedFindingCount`, exact `problemCode/httpStatus/retryable` 또는 닫힌 `failureClass/sourceExit/verifierExit`, redacted before/after digest 일치, `dbRowDelta`, `readyTransitionCount`, `quotaOvershootBytes`, partial/temp/residue, cleanup receipt가 있어야 한다. source/head/tree/clean checkout, runner·injector blob, 22-case identity SHA, artifact digest·만료, 시작/종료도 포함한다.

runner job은 제품 결함을 관측해도 모든 case와 cleanup·artifact upload를 끝냈다면 process success로 종료하고 raw verdict에 실패를 보존한다. job cancelled/failed, artifact 만료·누락, cleanup 미수행은 importer가 `INVALID_RUN`으로 거부한다. 제품 결함을 숨기기 위해 job을 실패시켜 artifact를 버리지 않는다.

### 5.2 storage importer와 AC-11 envelope

storage importer는 raw schema·case identity hash·중복·exact 분류·JUnit 합계를 검증한 뒤에만 #170의 `ac11-axis-evidence` v1 metric 행을 만든다. raw scenario 행을 aggregator에 직접 넣지 않는다. 각 registry criteria와 정확히 1:1인 `metric/value/n/successCount/failureCount/skipCount/errorsByClass`를 내고, producer verdict는 신뢰하지 않는다. 환경 문자열은 workflow run metadata, runner/injector blob, ADR-100 inventory/JUnit으로 대조한다.

- unknown/missing/duplicate case, injection 미관측, 합계 불일치, unknown failure class, digest·만료 누락, wrong target/path/blob, hosted→physical 자기 신고: import 오류 또는 `INVALID_RUN`.
- `skipCount > 0`: 집계기 계약대로 `NOT_OBSERVED`; PASS 분자에 들어가지 않는다.
- planned/executed 기준 미달처럼 관측은 완결됐지만 목표를 못 채운 경우: `MEASURED_FAIL`.
- 손상 byte 반환, false success, committed prior byte 손실, quota overshoot, retained boundary 삭제, 공개 code/status/retryable 불일치, silent backup 손실을 PASS로 처리: `MEASURED_FAIL`.
- failed/cancelled hosted run: `INVALID_RUN`. 측정을 끝낸 success run 안의 제품 finding은 `MEASURED_FAIL`로 보존한다.

release manifest는 모든 축의 `sourceHeadSha == releaseSha`를 요구하므로 PR-head hosted evidence는 reference일 뿐이다. criteria의 `cleanupResidueCount`와 envelope `cleanup.residueCount`는 같은 cleanup receipt에서 도출해 불일치를 거부한다.

## 6. 부정 시험과 되살림 변이

| 변이 | 죽이는 시험 |
|---|---|
| body만 검사하고 metadata drift를 성공 처리 | `OBJ-03` exact `VERIFY-0010`와 성공 body 0 |
| size mismatch에서 요청 size만 신뢰 | truncate·append 각각 read 거부 |
| temp를 fsync 전 canonical로 publish | write/fsync fault 뒤 canonical absent/old hash 불변 |
| directory fsync 실패를 성공 처리 | 성공 응답 0, retryable `STORE-0001`, retry 뒤 exact byte만 quiet success |
| provider quota 실패 뒤 DB row commit | `CAP-02` before/after row·usage·provider key 0 delta |
| DB quota를 provider write 뒤 검사 | `CAP-01` provider call 0 |
| archive 설정 `possible`을 PITR PASS로 변환 | `BAK-01`에서 `pitrVerified=false`와 nonzero exit 강제 |
| archive command가 exit 0이지만 byte를 쓰지 않음 | `BAK-03/postgresql/archive-command-true-empty`의 verifier nonzero·restore 거부 |
| backup이 exit 0이지만 empty/truncated | `BAK-03/local/backup-exit0-*` exact identity·`BACKUP_ARTIFACT_INVALID` |
| invalid/unknown label을 삭제 후보로 간주 | invalid label은 계획 0/exit 3, unknown-age는 retained |
| retention apply 중단 뒤 전체 성공 보고 | receipt 합계 불일치·미완료 후보가 있으면 `RETENTION_APPLY_PARTIAL` |
| retained boundary도 candidate와 함께 삭제 | boundary·이후 WAL·latest/unknown backup hash 불변 |
| hosted storage soak을 `long-soak` target에 사용 | `REQUIRED_TARGET_BY_AXIS`와 physical-five-node 환경 mismatch → `INVALID_RUN` |
| 약한 `s11-actual-pitr-v0`로 archive fault를 우회 | old targetId → `INVALID_RUN` |
| 같은 case를 반복해 전체 case 수를 채움 | 22-case identity SHA·중복 검사 → import 오류 |
| fault case skip을 성공 분모에서 제거 | `skipCount > 0` → `NOT_OBSERVED`, PASS 분자 제외 |

## 7. 기존 증거 재사용과 잔여 범위

| case/범위 | 재사용 | 새로 필요한 것 |
|---|---|---|
| S3 corruption·provider 오류 | #173 `tests/core/test_s3_object_store.py`의 body/metadata/size drift, 403·412 시험 | 제품 route·case identity·raw artifact importer |
| Local corruption·quota | #173 `tests/integration/test_snapshots.py`의 restore rehash, 8-thread quota, publication-before-metadata crash | Local `ENOSPC`/`EDQUOT`·fsync fault exact 분류 |
| WAL archive failure | `tests/integration/test_recovery_drill.py`의 `/bin/false`·`/bin/true` archiver와 `tools/recovery_drill.py`; G-02 #181/#187 실행자 주입 경로 | `BAK-03` empty/truncated byte와 restore 검증, AC-11 importer |
| retention | #150 `pitr_archive_retention.py` plan/apply, readiness·dry-run | receipt/journal, interrupted apply retry, 35일 운영 target |
| 물리 disk full·quota | 없음 | 실장비 target·ADR-100 inventory; `BLOCKED_EXTERNAL` |
| part 중단/재개·GC/upload 경합·Workspace restore | Storage 계획과 기존 snapshot/Workspace 카드 | 이 설계의 22-case 밖이며 별도 owner 카드; AC-11 완료 전에 evidence 공백 지도에서 추적 |
| 실제 backup 매체·네트워크 장애 | 없음 | 별도 장애 영역과 운영 자격; `BLOCKED_EXTERNAL` |

`corruptionEscapeCount`는 손상/불일치 byte가 caller에 성공 반환된 횟수, `falseSuccessCount`는 주입된 failure를 성공으로 분류한 횟수, `classificationMismatchCount`는 exact 표면과 다른 횟수다. 한 사건은 각 정의에 해당할 때만 집계하며 importer가 원 case identity를 보존한다.

## 8. 구현 순서와 롤백

1. 이 설계와 [[S11_ST_storage_failure_target_v0]]를 merge commit 방식으로 병합해 임계치·환경을 먼저 고정한다.
2. #177 병합 뒤 Codex 후속 카드가 정본 `s11-ac11-target-registry-v0.json`에 patch를 적용하고 old PITR target 제거, `REQUIRED_TARGET_BY_AXIS`, registry/blob pin, repo 수준 부정 시험을 한 commit에 넣는다. 이 단계 전 측정 금지.
3. PG-free raw producer·storage importer를 구현하고 22-case hash와 변이 표를 모두 죽인다.
4. Local `OSError`→기존 `STORE-0001` 변환과 retention receipt/journal을 작은 코드 카드로 분리한다. 공개 schema·migration 변화가 생기면 이 설계를 다시 검토한다.
5. hosted opt-in lane에서 MinIO+PG fault matrix와 archive `/bin/false`·`/bin/true`를 실행한다. 전부 reference-only로 보존한다.
6. 운영자가 물리 5노드·별도 장애 영역·archive 자격·허용 중단 창을 제공한 뒤에만 24시간 soak와 `BAK-01~03` target-time restore를 실행한다.

코드 롤백은 fault lane·새 변환·journal을 제거하되 기존 S3/Local ObjectStore와 retention dry-run 의미를 되돌리지 않는다. evidence target은 결과가 나쁜 경우 삭제하지 않고 `MEASURED_FAIL`로 보존한다. AC-11 전체와 S11-ST는 모든 필수 축과 실장비 조건을 충족하기 전 `done`으로 올리지 않는다.

## 9. 이번 카드의 판정

- 설계·사전 목표: v1.1 보강 완료, Claude 재검토 대기. 별도 registry는 소비 금지이며 정본 registry patch 선행 카드가 남아 있다.
- PG-free/hosted/실장비 실행: `NOT_OBSERVED`.
- 공개 계약·migration 변경: 없음.
- S11-ST registry 상태 변경: 없음(`planned` 유지).
