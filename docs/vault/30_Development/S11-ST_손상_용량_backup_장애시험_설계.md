---
doc_id: "DESIGN-S11-ST-FAILURE-001"
title: "S11-ST 손상·용량·backup 장애 시험 설계"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-28T14:08:30+09:00"
source_of_truth: "Git"
task_id: "S11-ST"
acceptance_id: "AC-11"
reviewer: "Claude"
---

# S11-ST 손상·용량·backup 장애 시험 설계

## 0. 결정과 경계

이 문서는 S11-ST의 `손상·용량·backup 장애 시험`을 구현하기 전 고정하는 v1 목표다. 공개 HTTP 계약과 migration은 바꾸지 않는다. 구현·hosted 실행·실장비 실행은 이 설계 승인 뒤 별도 카드로 분리하며, 이 문서 자체는 어떤 시나리오도 `MEASURED_PASS`로 주장하지 않는다.

AC-11의 닫힌 8축에는 별도 `storage-failure` 축을 추가하지 않는다.

- 객체 손상·부분 쓰기·용량 소진은 `long-soak` 축의 **필수 하위 fault matrix**로 넣는다. 짧은 fault matrix만 통과해서는 `long-soak` PASS가 아니며, 사전 등록한 1시간 window와 표본 수도 함께 충족해야 한다.
- WAL archive 장애와 보존 만료 중 장애는 `actual-pitr-rpo-rto-retention` 축에 넣는다. hosted MinIO·PostgreSQL 또는 same-host dry-run은 준비·기전 증거일 뿐 이 축의 PASS가 아니다.
- 별도 장애 영역의 운영 archive와 복구, 실제 용량 고갈이 필요한 단계만 `BLOCKED_EXTERNAL`이다. PG-free와 hosted에서 실행 가능한 항목을 `BLOCKED_EXTERNAL`로 낮추지 않는다.

두 target의 기계 판독용 사전 등록은 `Evidence/s11-st-failure-target-registry-v0.json`에 둔다. target 문서와 registry가 Git에 merge되기 전에는 측정을 시작하지 않으며, 결과를 본 뒤 임계치를 바꾸지 않는다.

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
| `OBJ-01` | 저장된 body 1 byte 변조 | read는 `VERIFY-0010`/422/non-retryable | 손상 byte 반환 0, DB digest 변경 0 | S3·Local 코드 경계 존재, 실행 증거 필요 |
| `OBJ-02` | 기대 size와 실제 size 불일치·truncate·append | read는 `VERIFY-0010` 또는 invalid handle `STORE-0003`/422 | 부분 byte 반환 0 | 단위 경계 존재, hosted 반복 필요 |
| `OBJ-03` | S3 metadata digest만 변조 | read는 `VERIFY-0010`/422/non-retryable | body가 맞아도 성공 0 | S3 시험 존재, 제품 path hosted 필요 |
| `OBJ-04` | Local write/fsync/rename 단계 실패 또는 S3 성공 응답 뒤 부분 object | Local은 `STORE-0001`/503/retryable로 변환, S3는 read-back 결과에 따라 `VERIFY-0010` 또는 `STORE-0005` | 이전 canonical object는 byte-for-byte 불변, 새 canonical partial 0, temp residue 0, metadata commit 0 | Local 오류 변환·durability 분류는 구현 공백 |

`OBJ-04`의 Local directory fsync 실패는 rename 뒤 상태가 보일 수 있다. 실패를 성공으로 낮추지 않고 `STORE-0001`을 반환한다. 동일 digest retry는 기존 exact byte를 재검증해 quiet success할 수 있지만, 최초 호출의 실패를 성공으로 소급하지 않는다.

### 2.2 용량 소진

| ID | 주입 | 기대 표면 | 데이터 보존 단언 | 현재 판정 |
|---|---|---|---|---|
| `CAP-01` | DB project quota를 1 byte 초과 | `RES-0001`/409/non-retryable | storage row·provider byte·usage 초과 0 | 코드 경계 존재, 동시성 hosted 증거 필요 |
| `CAP-02` | Local `ENOSPC`/`EDQUOT`, MinIO/provider quota·507·write refusal | `STORE-0001`/503/retryable | DB row commit 0, 이전 object 손실 0, partial/temp residue 0 | S3 non-success 변환은 존재, Local 변환은 구현 공백 |

quota 시험은 “요청 실패”만 보지 않는다. failure 뒤 DB 사용량, immutable object hash, temp key, S3 canonical key를 다시 읽고 초과 예약·부분 publish가 모두 0임을 확인한다.

### 2.3 backup·archive 장애

이 경로는 공개 HTTP route가 없으므로 가짜 ProblemDetails code를 만들지 않는다. runner의 닫힌 `failureClass`와 process exit로 판정한다.

| ID | 주입 | 기대 표면 | 데이터 보존 단언 | 현재 판정 |
|---|---|---|---|---|
| `BAK-01` | `archive_command` write refusal·timeout·archive 목적지 full | `failureClass=WAL_ARCHIVE_FAILED`, nonzero exit, `pitrVerified=false`; 설정 `possible`을 PASS로 세지 않음 | 미전달 WAL을 삭제·재활용했다는 주장 0, 복구 성공 주장 0 | hosted 기전과 운영 별도 장애 영역 증거 모두 필요 |
| `BAK-02` | retention 만료 후보 삭제 중 unlink/rmtree 실패 | `failureClass=RETENTION_APPLY_PARTIAL`, nonzero exit, 삭제 receipt와 미완료 후보를 모두 기록 | 최신·unknown-age backup, oldest-retained boundary 이후 WAL, `.history`·`.partial` 삭제 0 | 현재 apply는 부분 진행 뒤 raw 오류 가능; journal/receipt 구현 공백 |

`BAK-02`는 삭제 후보의 일부가 이미 사라질 수 있음을 정직하게 허용하되, 복구 경계를 구성하는 retained set은 한 건도 손대지 않는 것을 절대 불변식으로 둔다. retry는 같은 plan hash·동일 root identity일 때만 허용하고 이미 제거된 candidate는 idempotent하게 처리한다. plan 생성 뒤 root identity·label·boundary가 바뀌면 apply를 거부한다.

## 3. 실행 계층

| 계층 | 실행 범위 | 허용 판정 | 금지하는 승격 |
|---|---|---|---|
| PG-free | fake S3 응답, Local temp directory fault injection, quota 계산·retention pure plan, evidence importer·mutation tests | 계약·분류·불변식의 단위 증거 | provider·운영 archive·PITR PASS |
| hosted MinIO+PostgreSQL 16 | opt-in job, scenario를 한 번에 하나씩 순차 실행, disposable bucket/DB/root, `OBJ-01~04`·`CAP-01~02`, archive refusal·retention interruption 기전 | `long-soak` target의 hosted 조건을 모두 만족한 run만 해당 축 후보; archive 항목은 reference-only | actual PITR·off-site·실 disk-full·물리 장애 영역 PASS |
| 실장비·운영 후보 | 별도 장애 영역 archive, 실제 disk/quota, WAL 전달 중단, target-time restore, retention interruption 후 복구 | `actual-pitr-rpo-rto-retention` target의 후보 | dry-run·same-host·설정 관측으로 대체 |

hosted job은 label 또는 `workflow_dispatch` opt-in이며 job 수준 `cancel-in-progress:false`를 쓴다. PR head를 exact checkout하고 merge ref를 쓰지 않는다. runner·PostgreSQL·MinIO image digest·설정·fault injector version·tree SHA·clean checkout을 evidence에 기록한다. 자격·endpoint 원문은 출력하지 않는다.

## 4. AC-11 target 사전 등록

### 4.1 `s11-st-hosted-storage-fault-soak-v0`

- axis: `long-soak`
- 목적: 객체 손상·부분 쓰기·용량 장애를 포함한 hosted storage soak. fault matrix 단발 실행만으로 PASS 금지.
- requiredEnvironment: `topology=hosted`, `storageProvider=s3-compatible-minio`, `database=postgresql-16`, `sameHost=true`, `faultInjection=controlled-v1`, `scope=s11-st-storage-soak-v0`.
- criteria: window ≥ 3600초, attempted operations ≥ 1000, 계획 fault 6/실행 fault 6, corruption escape 0, false success 0, committed object loss 0, quota overshoot 0 byte, classification mismatch 0, unexpected error 0, cleanup residue 0.
- 집계 경계: 모든 관측은 같은 source tree·runner·provider 설정의 한 comparable group이어야 한다. fault 실행 때문에 정상 요청 표본이 줄어 1000 미만이면 `MEASURED_FAIL`, 0건·누락·skip은 `INVALID_RUN`이다.

### 4.2 `s11-st-actual-pitr-archive-failure-v0`

- axis: `actual-pitr-rpo-rto-retention`
- 목적: 기존 AC-11 목표(RPO 900초, RTO 3600초, 35일 보존, 매주 restore smoke)를 archive·retention 장애 뒤에도 만족하는지 검증한다.
- requiredEnvironment: `topology=physical`, `failureDomain=separate`, `archiveKind=operational`, `sameHost=false`, `faultInjection=controlled-v1`.
- criteria: 연속 주간 restore smoke ≥ 2주, smoke gap ≤ 7일, retention ≥ 35일, RPO ≤ 900초, RTO ≤ 3600초, WAL archive fault ≥ 1, retention interruption ≥ 1, fault 뒤 recovery pass ≥ 2, false PITR pass 0, retained-boundary deletion 0, cleanup residue 0.
- 집계 경계: `pitr_readiness`, `pitr_opt_in_dry_run`, same-host `pitr_rehearsal.sh`, hosted MinIO/PG는 source observation으로 보존할 수 있으나 이 target의 requiredEnvironment를 충족하지 않으므로 release manifest 축 봉투로 가져오면 `INVALID_RUN`이다.

target registry의 `sourceDocument.commit/path/blob`은 이 설계의 최초 고정 commit과 blob을 가리킨다. envelope의 `targetRef`는 registry commit·path·blob·targetId·criteria exact set을 사용한다. source document와 registry가 `sourceHeadSha`의 조상이 아니거나 source tree의 blob과 다르면 `NOT_REGISTERED`가 아니라 provenance 위조 가능성이므로 `INVALID_RUN`이다.

## 5. evidence와 fail-closed 판정

공통 envelope는 #170의 `ac11-axis-evidence` v1을 따른다. 최소 필드는 source/head/tree/clean checkout, targetRef, required environment 관측, artifact digest·만료, start/end, cleanup, observations다. producer verdict는 신뢰하지 않고 importer·aggregator가 다시 계산한다.

storage observations는 최소 아래를 포함한다.

- `scenarioId`, `injectionPoint`, `attemptedCount`, `expectedFindingCount`, `observedFindingCount`.
- `problemCode`, `httpStatus`, `retryable` 또는 비 HTTP 경로의 닫힌 `failureClass`, `processExit`.
- before/after canonical digest·size는 값 자체가 아니라 일치 여부와 redacted identity만 기록한다.
- `dbRowDelta`, `quotaOvershootBytes`, `partialObjectCount`, `temporaryResidueCount`, `retainedBoundaryDeletionCount`.
- 정상·실패·skip 분모, provider·DB cleanup 시도/성공/잔존, JUnit 수치.

다음은 무조건 `INVALID_RUN`이다: scenario 누락, 모르는 scenario/failure class, fault가 실제로 주입됐다는 관측 없음, expected finding 0인데 PASS, failure 합계 불일치, digest·artifact 만료 누락, cleanup 미시도, hosted를 physical로 자기 신고, 결과를 본 뒤 targetRef 변경. 다음은 `MEASURED_FAIL`이다: 손상 byte 1회라도 반환, false success 1건 이상, committed prior byte 손실, quota overshoot, retained boundary 삭제, 공개 code/status/retryable 불일치, 예상한 fault가 fail-closed하지 않음.

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
| invalid/unknown label을 삭제 후보로 간주 | invalid label은 계획 0/exit 3, unknown-age는 retained |
| retention apply 중단 뒤 전체 성공 보고 | receipt 합계 불일치·미완료 후보가 있으면 `RETENTION_APPLY_PARTIAL` |
| retained boundary도 candidate와 함께 삭제 | boundary·이후 WAL·latest/unknown backup hash 불변 |
| hosted/same-host evidence를 운영 target에 사용 | requiredEnvironment mismatch → `INVALID_RUN` |
| fault case skip을 성공 분모에서 제거 | planned 6 != executed 6 → `INVALID_RUN` |

## 7. 구현 순서와 롤백

1. 이 설계와 target registry를 merge해 임계치·환경을 먼저 고정한다.
2. PG-free fault injector와 evidence validator를 구현하고 변이 표를 모두 죽인다.
3. Local `OSError`→기존 `STORE-0001` 변환과 retention receipt/journal을 작은 코드 카드로 분리한다. 공개 schema·migration 변화가 생기면 이 설계를 다시 검토한다.
4. hosted opt-in lane에서 MinIO+PG matrix와 1시간 soak를 실행한다. archive 장애 결과는 reference-only로 보존한다.
5. 운영자가 별도 장애 영역·archive 자격·허용 중단 창을 제공한 뒤에만 `BAK-01~02`와 target-time restore를 실행한다.

코드 롤백은 fault lane·새 변환·journal을 제거하되 기존 S3/Local ObjectStore와 retention dry-run 의미를 되돌리지 않는다. evidence target은 결과가 나쁜 경우 삭제하지 않고 `MEASURED_FAIL`로 보존한다. AC-11 전체와 S11-ST는 모든 필수 축과 실장비 조건을 충족하기 전 `done`으로 올리지 않는다.

## 8. 이번 카드의 판정

- 설계·사전 목표: 작성 완료, Claude 검토 대기.
- PG-free/hosted/실장비 실행: `NOT_OBSERVED`.
- 공개 계약·migration 변경: 없음.
- S11-ST registry 상태 변경: 없음(`planned` 유지).
