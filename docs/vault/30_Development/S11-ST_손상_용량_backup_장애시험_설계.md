---
doc_id: "DESIGN-S11-ST-FAILURE-001"
title: "S11-ST 손상·용량·backup 장애 시험 설계"
version: "1.4.1"
status: "review"
author: "Codex"
updated: "2026-09-28T18:15:00+09:00"
source_of_truth: "Git"
task_id: "S11-ST"
acceptance_id: "AC-11"
reviewer: "Claude"
---

# S11-ST 손상·용량·backup 장애 시험 설계

## 0. 결정과 경계

이 문서는 S11-ST의 `손상·용량·backup 장애 시험`을 구현하기 전 고정하는 v1 목표다. 공개 HTTP 계약과 migration은 바꾸지 않는다. 구현·hosted 실행·실장비 실행은 이 설계 승인 뒤 별도 카드로 분리하며, 이 문서 자체는 어떤 시나리오도 `MEASURED_PASS`로 주장하지 않는다.

AC-11의 닫힌 8축에는 별도 `storage-failure` 축을 추가하지 않는다. 이 카드의 hosted fault matrix는 축 PASS가 아니라 구현·분류를 검증하는 reference evidence다.

- 객체 손상·부분 쓰기·용량 소진의 PG-free·hosted·물리 결과는 모두 storage reference evidence다. #157의 `long-soak`은 열·전원·NTP·스위치·WAN·원격 WS까지 포함하므로 S11-ST 기준만으로 축 target을 만들지 않는다. AC-11 owner가 전체 범위 composite target을 별도 승인·등록하기 전까지 `long-soak=NOT_REGISTERED`다.
- WAL archive 장애와 보존 만료 중 장애는 `actual-pitr-rpo-rto-retention` 축에 넣는다. hosted MinIO·PostgreSQL 또는 same-host dry-run은 준비·기전 증거일 뿐 이 축의 PASS가 아니다.
- 별도 장애 영역의 운영 archive와 복구, 실제 용량 고갈이 필요한 단계만 `BLOCKED_EXTERNAL`이다. PG-free와 hosted에서 실행 가능한 항목을 `BLOCKED_EXTERNAL`로 낮추지 않는다.

정본 target registry는 #177의 `Evidence/s11-ac11-target-registry-v0.json` 하나뿐이다. 이 PR의 `Evidence/s11-st-failure-target-registry-patch-v0.json`은 적용할 patch의 review artifact이며 `targetRef.path`로 제출할 수 없다. 선행 카드 `CARD-S11-AC11-REGISTRY-REPIN-01`(owner Codex, reviewer Claude)이 #177 병합 뒤 약한 `s11-actual-pitr-v0`를 archive fault target으로 교체하고, `TARGET_REGISTRY_BLOB`·PITR 허용 targetId·importer pin을 함께 갱신한다. long-soak map은 만들지 않는다. 이 선행 카드가 merge되기 전에는 측정을 시작하지 않는다. 고정 기준은 [[S11_ST_storage_failure_target_v0]]에 두며, 결과를 본 뒤 임계치를 바꾸지 않는다.

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

PG-free `CAP-02/local/*`는 exact 오류 변환·provider key·partial/temp residue만 검증한다. `begin` 뒤 DB row·usage·`ready` 불변식은 PostgreSQL이 있는 hosted `CAP-02/s3/http-507-new-key`에서 검증하며 PG-free run의 합격 조건으로 요구하지 않는다.

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
| 물리 5노드 | ADR-100의 CP 겸임 Node 1대를 분모에서 제외하고 eligible worker 4대에서 24시간 storage soak, 실제 디스크 경합과 storage fault 관측 | `s11-storage-soak-physical-reference-v0` reference. AC-11 composite target 전 `long-soak=NOT_REGISTERED` | hosted 결과로 대체하거나 storage만으로 축 PASS |
| 실장비·운영 후보 | 별도 장애 영역 archive, 실제 disk/quota, WAL 전달 중단, target-time restore, retention interruption 후 복구 | `s11-st-actual-pitr-archive-failure-v0` 후보 | dry-run·same-host·설정 관측으로 대체 |

hosted job은 label 또는 `workflow_dispatch` opt-in이며 job 수준 `cancel-in-progress:false`를 쓴다. PR head를 exact checkout하고 merge ref를 쓰지 않는다. runner·PostgreSQL·MinIO image digest·설정·fault injector version·tree SHA·clean checkout을 evidence에 기록한다. 자격·endpoint 원문은 출력하지 않는다.

## 4. AC-11 target 사전 등록

### 4.1 단일 registry와 적용 책임

집계기가 허용하는 경로는 #177의 `Evidence/s11-ac11-target-registry-v0.json` 하나다. 별도 registry path allowlist 확장은 하지 않는다. 선행 카드 `CARD-S11-AC11-REGISTRY-REPIN-01`(owner Codex, reviewer Claude)이 다음 변경을 한 commit에 묶는다.

1. `s11-actual-pitr-v0` 제거 및 `s11-st-actual-pitr-archive-failure-v0` 추가.
2. `REQUIRED_TARGET_BY_AXIS`에는 PITR axis와 유일 targetId만 고정한다.
3. 집계기 `TARGET_REGISTRY_BLOB`, migration importer registry pin, 기존 `test_aggregate_ac11_evidence.py`의 PITR fixture를 갱신한다.
4. 기존 sourceDocument blob==HEAD repo 시험을 재사용하고 old target·별도 registry path·old blob 거부 시험을 추가한다.

storage soak target은 정본 registry에 추가하지 않는다. #157의 물리 장시간 범위 전체 composite target이 AC-11 owner의 별도 설계로 승인·등록되기 전에는 `long-soak=NOT_REGISTERED`이고 map에도 없다. `Evidence/s11-st-failure-target-registry-patch-v0.json`은 위 PITR patch를 검토하기 위한 비소비 artifact이며, `consumableAsTargetRef=false`를 강제한다.

### 4.2 `s11-storage-soak-physical-reference-v0`

- axis 없음. AC-11 envelope로 소비 금지.
- requiredEnvironment: `topology=physical-five-node`, `eligibleNodeCount=4`, `excludedNodeCount=1`, `sameHost=false`, `faultInjection=controlled-v1`.
- reference criteria: 24시간, operation ≥ 1,000, corruption·capacity·durability 관측과 복구 각각 ≥ 1, corruption escape·false success·committed object loss·quota overshoot·classification mismatch·unexpected error·cleanup residue 모두 0, memory growth ≤ 256MiB, FD growth ≤ 32, DB connection growth ≤ 4.
- identity는 [[S11_ST_storage_failure_target_v0]]의 physical storage 3개와 SHA `f6fef83126954555b004e2ca48a34fb81fdb0bbca57b4f8147f402dcef4f90ec`로 닫는다.

### 4.3 `s11-st-actual-pitr-archive-failure-v0`

- axis: `actual-pitr-rpo-rto-retention`.
- 목적: RPO 900초, RTO 3,600초, 35일 보존, 매주 restore smoke를 archive·retention 장애 뒤에도 만족하는지 검증한다.
- requiredEnvironment: `topology=physical`, `failureDomain=separate`, `archiveKind=operational`, `sameHost=false`, `faultInjection=controlled-v1`.
- criteria: 연속 주간 restore smoke ≥ 2주, smoke gap ≤ 7일, retention ≥ 35일, RPO ≤ 900초, RTO ≤ 3,600초, WAL archive failure·silent archive loss·retention interruption 각각 ≥ 1, 각 fault 종류 뒤 recovery pass 각각 ≥ 1, false PITR pass·retained-boundary deletion·cleanup residue 모두 0.
- physical PITR identity는 3개와 SHA `a5d0f9e6de439af7eee439605adad13d4badc9f37683a9a1afc8c3be8f96cc18`로 닫는다.
- `pitr_readiness`, `pitr_opt_in_dry_run`, same-host `pitr_rehearsal.sh`, hosted MinIO/PG는 reference observation만 허용한다.

PITR target의 `sourceDocument`는 [[S11_ST_storage_failure_target_v0]]의 commit `3363ab77e7fc4ccf3be140466a053a973b0b65a4`, path `docs/vault/30_Development/S11_ST_storage_failure_target_v0.md`, blob `421d4d3a6e39720e74bc6fd832f30e8b45f8680a`를 가리킨다. 이 commit이 integration 조상으로 남도록 이 PR은 merge commit 방식(`--merge`)으로만 병합하고 squash·rebase 병합을 금지한다. envelope의 `targetRef`는 정본 registry commit/path/blob·targetId·criteria exact set을 사용한다. source document와 registry가 `sourceHeadSha`의 조상이 아니거나 source tree의 blob과 다르면 `INVALID_RUN`이다.

## 5. evidence와 fail-closed 판정

### 5.1 raw producer artifact

runner는 case별 raw JSON과 JUnit을 낸다. 각 case에는 `caseIdentity`, `executionLayer`, `provider`, `injectionObserved`, `attemptedCount`, `expectedFindingCount`, `observedFindingCount`, exact `problemCode/httpStatus/retryable` 또는 닫힌 `failureClass/sourceExit/verifierExit`, redacted before/after digest 일치, `dbRowDelta`, `readyTransitionCount`, `quotaOvershootBytes`, partial/temp/residue, cleanup receipt가 있어야 한다. source/head/tree/clean checkout, runner·injector blob, 전체 허용 universe SHA와 해당 계층 필수 subset SHA, artifact digest·만료, 시작/종료도 포함한다. PG-free run은 12개, hosted run은 10개만 각각 완결해야 하며 다른 계층 case의 부재는 누락이 아니다.

runner job은 제품 결함을 관측해도 모든 case와 cleanup·artifact upload를 끝냈다면 process success로 종료하고 raw verdict에 실패를 보존한다. job cancelled/failed, artifact 만료·누락, cleanup 미수행은 importer가 `INVALID_RUN`으로 거부한다. 제품 결함을 숨기기 위해 job을 실패시켜 artifact를 버리지 않는다.

### 5.2 storage importer와 AC-11 envelope

storage importer는 raw schema·case identity hash·중복·exact 분류·JUnit 합계를 검증한 뒤에만 #170의 `ac11-axis-evidence` v1 metric 행을 만든다. raw scenario 행을 aggregator에 직접 넣지 않는다. 각 registry criteria와 정확히 1:1인 `metric/value/n/successCount/failureCount/skipCount/errorsByClass`를 내고, producer verdict는 신뢰하지 않는다. 환경 문자열은 workflow run metadata, runner/injector blob, ADR-100 inventory/JUnit으로 대조한다.

metric 행의 계수 의미도 닫는다. `n = successCount + failureCount + skipCount`이며 raw receipt를 중복 없이 센 값이다. zero-expected count metric의 `value`는 `failureCount`, minimum-positive metric의 `value`는 receipt로 증명된 `successCount`, max/percentile metric의 `n`은 유효 표본 수다. parsing·identity·분모 오류는 `failureCount`로 낮추지 않고 import 오류다. `failureCount > 0`인데 `value`가 이를 반영하지 않거나, `n=0`, 합계 불일치는 `INVALID_RUN`이다. physical evidence의 환경은 workflow metadata가 아니라 ADR-100 inventory, signed injector/recovery receipt, runner blob으로 대조한다.

`retentionDays`는 실행 종료 시점에 보존 경계의 oldest retained WAL/backup timestamp에서 계산한 gauge다. `n=1`, `successCount=1`, `failureCount=0`, `skipCount=0`이고 경계 receipt와 동일한 값을 써야 한다. signed injector/recovery receipt는 사전 등록한 Node identity key로 서명한 canonical JSON이며 `caseIdentity`, `sourceRunId`, `sourceHeadSha`, `nodeId`, `injectedAt`, `recoveredAt`, before/after digest, key id를 exact set으로 담는다. key가 ADR-100 inventory에 없거나 서명·run 결속이 틀리면 import 오류다.

현재 stage-1 aggregator는 count 합계와 target value만 독립 검증하고 metric별 `value` 도출 의미까지 재계산하지 않는다. 따라서 `failureCount > 0`인데 forged `value`가 target을 통과하는 R12는 이 카드에서 임의 휴리스틱으로 막지 않는다. §8-3 storage importer 구현 카드에서 metric kind/receipt 결속을 importer 전용으로 둘지 registry가 해석 가능한 machine-readable semantics를 추가해 aggregator에서도 거부할지 결정하고 부정 시험으로 고정한다.

- unknown/missing/duplicate case, injection 미관측, 합계 불일치, unknown failure class, digest·만료 누락, wrong target/path/blob, hosted→physical 자기 신고: import 오류 또는 `INVALID_RUN`.
- `skipCount > 0`: 집계기 계약대로 `NOT_OBSERVED`; PASS 분자에 들어가지 않는다.
- planned/executed 기준 미달처럼 관측은 완결됐지만 목표를 못 채운 경우: `MEASURED_FAIL`.
- 손상 byte 반환, false success, committed prior byte 손실, quota overshoot, retained boundary 삭제, 공개 code/status/retryable 불일치, silent backup 손실을 PASS로 처리: `MEASURED_FAIL`.
- failed/cancelled hosted run: `INVALID_RUN`. 측정을 끝낸 success run 안의 제품 finding은 `MEASURED_FAIL`로 보존한다.

release manifest는 모든 축의 `sourceHeadSha == releaseSha`를 요구하므로 PR-head hosted evidence는 reference일 뿐이다. criteria의 `cleanupResidueCount`와 envelope `cleanup.residueCount`는 같은 cleanup receipt에서 도출해 불일치를 거부한다.

## 6. 부정 시험과 되살림 변이

| 변이 | 죽이는 시험 | PG-free 상태 | 후속 범위 |
|---|---|---|---|
| body만 검사하고 metadata drift를 성공 처리 | `OBJ-03` exact `VERIFY-0010`와 성공 body 0 | 계층 밖 | hosted 10-case |
| size mismatch에서 요청 size만 신뢰 | truncate·append 각각 read 거부 | 구현 | — |
| Local byte 변조 뒤 writable mode로 read해 size/hash 검사를 우회 | read 전 `0o400` 복원·mode 단언 뒤 `OBJ-01`은 VERIFY-0010, `OBJ-02`는 STORE-0003 | 구현 | — |
| temp를 fsync 전 canonical로 publish | write/file-fsync fault 뒤 canonical absent/old hash 불변 | 구현: 불완전 canonical·temp·cleanup residue가 양수면 finding | retry 뒤 quiet success는 Local 오류 변환 카드 |
| directory fsync 실패를 성공 처리 | 성공 응답 0, retryable `STORE-0001`, retry 뒤 exact byte만 quiet success | 부분: rename 뒤 exact canonical byte는 허용하되 raw `OSError` 분류 불일치는 finding; 불완전 canonical만 residue | retry 경로는 Local 오류 변환 카드 |
| provider quota 실패 뒤 DB row commit | `CAP-02` before/after row·usage·provider key 0 delta | Local key·quota overshoot만 관측; DB는 미관측 | hosted PG 10-case |
| DB quota를 provider write 뒤 검사 | `CAP-01` provider call 0 | 계층 밖 | hosted PG 10-case |
| archive 설정 `possible`을 PITR PASS로 변환 | `BAK-01`에서 `pitrVerified=false`와 nonzero exit 강제 | 계층 밖 | hosted PG 10-case |
| archive command가 exit 0이지만 byte를 쓰지 않음 | `BAK-03/postgresql/archive-command-true-empty`의 verifier nonzero·restore 거부 | 계층 밖 | hosted PG 10-case |
| backup이 exit 0이지만 empty/truncated | 별도 `verify_backup_artifact.py`가 tar 구조·필수 PostgreSQL member를 검사해 `BACKUP_ARTIFACT_INVALID`; truncated fixture는 유효 tar의 `pg_control` data 구간을 실제 절단 | 구현: member 누락·잘못된 version·label 줄 누락·8191-byte control·`../`·중복 member 부정 시험 | 실제 restore는 hosted/physical |
| invalid/unknown label을 삭제 후보로 간주 | invalid label은 계획 0/exit 3, unknown-age는 retained | 미해결: 현재 integration retention 도구는 #150 이전 | #150 병합 뒤 retention 카드 |
| retention apply 중단 뒤 전체 성공 보고 | 적용 중단은 `RETENTION_APPLY_PARTIAL`·nonzero exit이며 receipt의 removed/incomplete 합계가 plan과 정확히 일치해야 한다 | 부분: raw `OSError` 분류 불일치와 retained-set digest 손실을 finding으로 보존; 삭제 대상 미완료 후보는 허용 상태라 residue로 세지 않음 | receipt/journal 구현 카드 |
| retained boundary도 candidate와 함께 삭제 | boundary·이후 WAL·latest/unknown backup hash 불변 | 구현: retained set before/after digest | — |
| hosted/physical storage reference를 `long-soak` PASS로 사용 | composite target 미등록·map 부재 → `NOT_REGISTERED`, axis envelope 생성 금지 | 구현 | — |
| 약한 `s11-actual-pitr-v0`로 archive fault를 우회 | old targetId → `INVALID_RUN` | 구현 | — |
| 같은 case를 반복해 전체 case 수를 채움 | 계층별 subset 또는 physical identity SHA·중복 검사 → import 오류 | 구현 | — |
| fault case skip을 성공 분모에서 제거 | `skipCount > 0` → `NOT_OBSERVED`, PASS 분자 제외 | PG-free는 skip 금지 | hosted/physical importer |

## 7. 기존 증거 재사용과 잔여 범위

| case/범위 | 재사용 | 새로 필요한 것 |
|---|---|---|
| S3 corruption·provider 오류 | #173 `tests/core/test_s3_object_store.py:126,135,146-156`의 403·412와 body/metadata/size drift | 제품 route·case identity·raw artifact importer |
| Local corruption·quota | #173 `tests/integration/test_snapshots.py:83,151-161,183`의 publication-before-metadata crash, restore rehash, 8-thread quota | Local `ENOSPC`/`EDQUOT`·fsync fault exact 분류 |
| WAL archive failure | `tests/integration/test_recovery_drill.py:488-489,560-569`의 `/bin/false`·`/bin/true`, `tools/recovery_drill.py:444-506`; G-02 #181/#187 실행자 주입 경로 | `BAK-03` empty/truncated byte와 restore 검증, AC-11 importer |
| retention | #150 `pitr_archive_retention.py` plan/apply, readiness·dry-run | receipt/journal, interrupted apply retry, 35일 운영 target |
| 물리 disk full·quota | 없음 | `s11-storage-soak-physical-reference-v0`의 capacity case(Codex S11-ST 후속); 자원 제공 전 `BLOCKED_EXTERNAL` |
| part 중단/재개·GC/upload 경합·cache 손상·링크 탈출·complete 재호출·Workspace restore | Storage 계획과 기존 snapshot/Workspace 카드 | 이 설계의 22-case 밖이며 Codex S11-ST 후속 카드가 evidence 공백 지도에서 추적 |
| MLflow artifact 보존 | #172/#176 mirror·credential stack | Claude S10-BE 후속 카드; S11-ST storage PASS로 중복 계산하지 않음 |
| 실제 backup 매체·네트워크 장애 | 없음 | 별도 장애 영역과 운영 자격; `BLOCKED_EXTERNAL` |

`corruptionEscapeCount`는 손상/불일치 byte가 caller에 성공 반환된 횟수, `falseSuccessCount`는 주입된 failure를 성공으로 분류한 횟수, `committedObjectLossCount`는 fault 전 canonical byte가 사라진 횟수, `classificationMismatchCount`는 exact 표면과 다른 횟수, `unexpectedErrorCount`는 닫힌 code/class 밖 결과 횟수다. physical `observed*FaultCaseCount`는 서로 다른 고정 identity의 injection receipt 수이며 recovery count는 같은 identity·source run에 결속된 recovery receipt 수다. 한 사건은 각 정의에 해당할 때만 집계하며 importer가 원 case identity를 보존한다.

## 8. 구현 순서와 롤백

1. 이 설계와 [[S11_ST_storage_failure_target_v0]]를 merge commit 방식으로 병합해 임계치·환경을 먼저 고정한다.
2. #177 병합 뒤 `CARD-S11-AC11-REGISTRY-REPIN-01`이 정본 `s11-ac11-target-registry-v0.json`에 PITR patch를 적용하고 old target 제거, PITR `REQUIRED_TARGET_BY_AXIS`, registry/blob·importer pin, 기존 repo 시험과 old-target 부정 시험을 한 commit에 넣는다. long-soak은 composite target 전 `NOT_REGISTERED`다. 이 단계 전 측정 금지.
3. PG-free raw producer·storage importer는 commit `06718b59`에서 시작했고 #193 Claude r1·r2 조건에 따라 보강한다. universe 22개와 PG-free 12개 subset hash, exact surface·provenance·redaction·JUnit을 fail-closed로 검증하며, 실제 tar verifier 변이와 retention/rename의 허용 residue 경계를 고정한다. 위 표의 PG-free 구현/부분/미해결 상태를 숨기지 않으며 hosted 10개 producer/importer는 별도 lane 카드에 남는다.
4. Local `OSError`→기존 `STORE-0001` 변환과 retention receipt/journal을 작은 코드 카드로 분리한다. 공개 schema·migration 변화가 생기면 이 설계를 다시 검토한다.
5. hosted opt-in lane에서 MinIO+PG fault matrix와 archive `/bin/false`·`/bin/true`를 실행한다. 전부 reference-only로 보존한다.
6. 운영자가 물리 5노드·별도 장애 영역·archive 자격·허용 중단 창을 제공한 뒤에만 24시간 storage reference와 physical PITR identity 3개를 실행한다. storage reference는 long-soak composite target 승인 전 축 판정에 쓰지 않는다.

코드 롤백은 fault lane·새 변환·journal을 제거하되 기존 S3/Local ObjectStore와 retention dry-run 의미를 되돌리지 않는다. evidence target은 결과가 나쁜 경우 삭제하지 않고 `MEASURED_FAIL`로 보존한다. AC-11 전체와 S11-ST는 모든 필수 축과 실장비 조건을 충족하기 전 `done`으로 올리지 않는다.

## 9. 이번 카드의 판정

- 설계·사전 목표: v1.2는 Claude r3 승인됐다. `CARD-S11-AC11-REGISTRY-REPIN-01`은 merge commit `067e6a48` 위 구현 commit `ffd99bfd`에서 old PITR target 제거·새 target 적용·축별 targetId·registry/importer pin을 반영했다. 별도 patch proposal은 계속 소비 금지다.
- PG-free producer/importer: Claude #193 r1 D1~D6과 r2 C1~C2를 반영했다. backup 2건은 별도 tar verifier를 호출하며 truncated case는 유효 physical tar의 data 구간을 자른다. retention 2건은 receipt/journal 전 raw `OSError` finding이고, 삭제 대상 미완료 후보와 directory-fsync 뒤 완전한 canonical object를 residue로 오인하지 않는다. retained boundary 삭제는 digest finding으로 보존하고 committed-loss 미관측값은 `null`이다. 최종 hosted Linux head 실행 전까지 `NOT_OBSERVED`이며 hosted 10-case와 실장비도 `NOT_OBSERVED`다.
- Hosted 10-case reference lane: PR #204의 opt-in label `run-s11-storage`가 exact PR head를 checkout하고 MinIO+PostgreSQL fault matrix와 archive `/bin/false`·`/bin/true`를 실행한다. 첫 run `36399940041`은 composite quota key upsert 결함으로 실패했고 숨기지 않았다. 수정 head `3fe6a7a1`의 run `36400113385`와 docs head `b972a70e`의 run `36400962763`은 10/10 exact surface, finding 0, residue 0, secret 0으로 `MEASURED_PASS`를 냈다. 최종 artifact `10960581532`의 digest는 `sha256:dfaf7cf4…6c37`, 만료일은 2026-10-28이다. 전용 환경변수가 없는 기본 Backend/Core에서는 정확한 opt-in 사유로 skip하고 exact skip map이 1건을 고정한다. 이 결과는 `referenceOnly=true`, `axis=null`, `targetRef=null`이며 AC-11 축 판정·S11-ST 승격에 쓰지 않는다. opt-in 경계 hotfix를 포함한 최종 head 실행 식별자는 PR #204 코멘트에 보존한다.
- 공개 계약·migration 변경: 없음.
- S11-ST registry 상태 변경: 없음(`planned` 유지). 정본 task registry는 sprint task만 허용하고 S10 선행 task가 미완료이므로 synthetic subtask를 추가하거나 parent를 `in_progress`로 올리지 않았다. 카드 ID는 History·Codex 작업판에서 추적한다.
