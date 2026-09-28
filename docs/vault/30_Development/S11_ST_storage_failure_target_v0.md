---
doc_id: "TARGET-S11-ST-FAILURE-001"
title: "S11-ST storage failure target v0"
version: "1.0.0"
status: "frozen-target"
author: "Codex"
updated: "2026-09-28T15:42:39+09:00"
source_of_truth: "Git"
task_id: "S11-ST"
acceptance_id: "AC-11"
---

# S11-ST storage failure target v0

이 문서는 결과를 보기 전에 고정하는 작은 target 문서다. 정본 target registry는 `docs/vault/30_Development/Evidence/s11-ac11-target-registry-v0.json` 하나뿐이며, 이 문서 자체나 별도 registry 파일을 `targetRef.path`로 제출할 수 없다. 아래 변경이 정본 registry·집계기·importer에 merge되고 새 blob이 다시 pin되기 전에는 측정을 시작하지 않는다.

## 1. 정본 registry patch

1. `actual-pitr-rpo-rto-retention` 축의 약한 `s11-actual-pitr-v0`를 제거하고 `s11-st-actual-pitr-archive-failure-v0`로 교체한다.
2. 집계기는 아래 닫힌 map을 사용한다. 다른 targetId는 `INVALID_RUN`이다.
3. 이 카드의 storage soak는 #157이 정한 물리 장시간 축 전체의 일부일 뿐이다. 열·전원·NTP·스위치·WAN·원격 WS까지 포함한 AC-11 composite target이 별도 승인·등록되기 전에는 `long-soak`을 `NOT_REGISTERED`로 유지하고 `REQUIRED_TARGET_BY_AXIS`에 넣지 않는다.

```json
{
  "actual-pitr-rpo-rto-retention": "s11-st-actual-pitr-archive-failure-v0"
}
```

### `s11-storage-soak-physical-reference-v0` (비소비 reference)

- requiredEnvironment: `topology=physical-five-node`, `eligibleNodeCount=4`, `excludedNodeCount=1`, `sameHost=false`, `faultInjection=controlled-v1`.
- reference criteria:
  - `windowSeconds >= 86400`
  - `attemptedOperationCount >= 1000`
  - `observedCorruptionFaultCaseCount >= 1`
  - `recoveryAfterCorruptionFaultPassCount >= 1`
  - `observedCapacityFaultCaseCount >= 1`
  - `recoveryAfterCapacityFaultPassCount >= 1`
  - `observedDurabilityFaultCaseCount >= 1`
  - `recoveryAfterDurabilityFaultPassCount >= 1`
  - `corruptionEscapeCount == 0`
  - `falseSuccessCount == 0`
  - `committedObjectLossCount == 0`
  - `quotaOvershootBytes == 0`
  - `classificationMismatchCount == 0`
  - `unexpectedErrorCount == 0`
  - `cleanupResidueCount == 0`
  - `memoryGrowthBytes <= 268435456`
  - `fileDescriptorGrowthCount <= 32`
  - `dbConnectionGrowthCount <= 4`

이 reference는 정본 AC-11 registry에 추가하지 않고 axis envelope로 제출할 수 없다. importer는 아래 physical storage identity와 injection/recovery receipt를 대조한다. hosted storage fault soak도 같은 이유로 reference evidence일 뿐이다.

### `s11-st-actual-pitr-archive-failure-v0`

- requiredEnvironment: `topology=physical`, `failureDomain=separate`, `archiveKind=operational`, `sameHost=false`, `faultInjection=controlled-v1`.
- criteria:
  - `consecutiveWeeklyRestoreSmokeWeeks >= 2`
  - `maxRestoreSmokeGapDays <= 7`
  - `retentionDays >= 35`
  - `rpoSeconds <= 900`
  - `rtoSeconds <= 3600`
  - `walArchiveFaultCaseCount >= 1`
  - `recoveryAfterWalArchiveFaultPassCount >= 1`
  - `silentArchiveLossCaseCount >= 1`
  - `recoveryAfterSilentArchiveLossPassCount >= 1`
  - `retentionInterruptionCaseCount >= 1`
  - `recoveryAfterRetentionInterruptionPassCount >= 1`
  - `falsePitrPassCount == 0`
  - `retainedBoundaryDeletionCount == 0`
  - `cleanupResidueCount == 0`

## 2. 닫힌 raw fault case identity

아래 22개는 허용 universe다. 전체 universe SHA-256은 `5d700981ee429ebbfc66b8ed28d8dc9e37e16e327a673d6061bdec5e7e334fd9`다. importer는 한 run에 22개 전부를 요구하지 않고 실행 계층별 필수 subset의 중복·누락·미등록 case를 거부한다.

```json
[
  "BAK-01/postgresql/archive-command-false",
  "BAK-02/local/retention-rmtree",
  "BAK-02/local/retention-unlink",
  "BAK-03/local/backup-exit0-empty",
  "BAK-03/local/backup-exit0-truncated",
  "BAK-03/postgresql/archive-command-true-empty",
  "CAP-01/postgresql/concurrent-8",
  "CAP-01/postgresql/single",
  "CAP-02/local/edquot-new-key",
  "CAP-02/local/enospc-new-key",
  "CAP-02/s3/http-507-new-key",
  "OBJ-01/local/body-byte",
  "OBJ-01/s3/body-byte",
  "OBJ-02/local/append",
  "OBJ-02/local/truncate",
  "OBJ-02/s3/size-metadata",
  "OBJ-03/s3/metadata-digest",
  "OBJ-04/local/directory-fsync-eio",
  "OBJ-04/local/file-fsync-eio",
  "OBJ-04/local/write-enospc",
  "OBJ-04/s3/ambiguous-put-different-byte",
  "OBJ-04/s3/success-partial"
]
```

### 2.1 PG-free 필수 subset (12개)

SHA-256 `f69d161e19a791cdead64f16fae813dd470b0eabe0ed0f7a58ceed9ed4298799`.

```json
["BAK-02/local/retention-rmtree","BAK-02/local/retention-unlink","BAK-03/local/backup-exit0-empty","BAK-03/local/backup-exit0-truncated","CAP-02/local/edquot-new-key","CAP-02/local/enospc-new-key","OBJ-01/local/body-byte","OBJ-02/local/append","OBJ-02/local/truncate","OBJ-04/local/directory-fsync-eio","OBJ-04/local/file-fsync-eio","OBJ-04/local/write-enospc"]
```

### 2.2 hosted MinIO+PostgreSQL 필수 subset (10개)

SHA-256 `0509d94a6648106868ef1ec602af2bed5bbd02b17cec3a4c5ffbf6178ef24a33`.

```json
["BAK-01/postgresql/archive-command-false","BAK-03/postgresql/archive-command-true-empty","CAP-01/postgresql/concurrent-8","CAP-01/postgresql/single","CAP-02/s3/http-507-new-key","OBJ-01/s3/body-byte","OBJ-02/s3/size-metadata","OBJ-03/s3/metadata-digest","OBJ-04/s3/ambiguous-put-different-byte","OBJ-04/s3/success-partial"]
```

### 2.3 physical storage reference (3개)

SHA-256 `f6fef83126954555b004e2ca48a34fb81fdb0bbca57b4f8147f402dcef4f90ec`.

```json
["PHYS-ST-CAPACITY/physical/object","PHYS-ST-CORRUPTION/physical/object","PHYS-ST-DURABILITY/physical/object"]
```

### 2.4 physical PITR gate (3개)

SHA-256 `a5d0f9e6de439af7eee439605adad13d4badc9f37683a9a1afc8c3be8f96cc18`.

```json
["PITR-ARCHIVE-NONZERO/physical/operational","PITR-ARCHIVE-SILENT-EMPTY/physical/operational","PITR-RETENTION-INTERRUPTION/physical/operational"]
```

## 3. exact 결과 분류

| case | exact 결과 |
|---|---|
| `OBJ-01/local/*`, `OBJ-01/s3/*`, `OBJ-02/s3/*`, `OBJ-03/s3/*`, `OBJ-04/s3/success-partial` | `VERIFY-0010` / 422 / retryable=false |
| `OBJ-02/local/*` | `STORE-0003` / 422 / retryable=false |
| `OBJ-04/local/*`, `CAP-02/local/*`, `CAP-02/s3/http-507-new-key` | `STORE-0001` / 503 / retryable=true |
| `OBJ-04/s3/ambiguous-put-different-byte` | `STORE-0005` / 409 / retryable=false |
| `CAP-01/postgresql/*` | `RES-0001` / 409 / retryable=false |
| `BAK-01/postgresql/archive-command-false` | `failureClass=WAL_ARCHIVE_FAILED`, source exit nonzero, verifier exit nonzero |
| `BAK-02/local/*` | `failureClass=RETENTION_APPLY_PARTIAL`, verifier exit nonzero |
| `BAK-03/postgresql/archive-command-true-empty` | source exit 0, `failureClass=WAL_ARCHIVE_EMPTY`, verifier exit nonzero |
| `BAK-03/local/backup-exit0-*` | source exit 0, `failureClass=BACKUP_ARTIFACT_INVALID`, verifier exit nonzero |

Local 하위 case는 PG-free fault injection 전용이다. `CAP-02`는 기존 object가 없는 새 key에서만 실행한다. `OBJ-01/local/body-byte`와 `OBJ-02/local/*`는 byte 변조 뒤 **read 전에** mode를 `0o400`으로 복원하고 read 직전에 mode를 단언한다.

## 4. pin·merge 규칙

- 정본 registry entry의 `sourceDocument`는 이 파일의 고정 commit/path/blob을 가리킨다.
- 이 commit이 integration 조상으로 남도록 PR은 merge commit 방식(`--merge`)으로만 병합한다. squash·rebase 병합은 금지한다.
- 선행 카드 ID는 `CARD-S11-AC11-REGISTRY-REPIN-01`(owner Codex, reviewer Claude)이다. #177 병합 뒤 registry patch, `TARGET_REGISTRY_BLOB`, importer pin, 기존 `test_aggregate_ac11_evidence.py`의 PITR target fixture를 한 commit에서 갱신하고, 기존 sourceDocument blob==HEAD repo 시험을 재사용한다.
- release evidence는 release SHA에서 다시 실행한다. PR-head hosted 결과는 후보·reference일 뿐 release gate evidence가 아니다.
