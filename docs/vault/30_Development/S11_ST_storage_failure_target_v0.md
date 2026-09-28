---
doc_id: "TARGET-S11-ST-FAILURE-001"
title: "S11-ST storage failure target v0"
version: "1.0.0"
status: "frozen-target"
author: "Codex"
updated: "2026-09-28T15:29:13+09:00"
source_of_truth: "Git"
task_id: "S11-ST"
acceptance_id: "AC-11"
---

# S11-ST storage failure target v0

이 문서는 결과를 보기 전에 고정하는 작은 target 문서다. 정본 target registry는 `docs/vault/30_Development/Evidence/s11-ac11-target-registry-v0.json` 하나뿐이며, 이 문서 자체나 별도 registry 파일을 `targetRef.path`로 제출할 수 없다. 아래 변경이 정본 registry·집계기·importer에 merge되고 새 blob이 다시 pin되기 전에는 측정을 시작하지 않는다.

## 1. 정본 registry patch

1. `long-soak` 축에 `s11-long-soak-physical-five-node-v0`를 추가한다.
2. `actual-pitr-rpo-rto-retention` 축의 약한 `s11-actual-pitr-v0`를 제거하고 `s11-st-actual-pitr-archive-failure-v0`로 교체한다.
3. 집계기는 아래 닫힌 map을 사용한다. 다른 targetId는 `INVALID_RUN`이다.

```json
{
  "long-soak": "s11-long-soak-physical-five-node-v0",
  "actual-pitr-rpo-rto-retention": "s11-st-actual-pitr-archive-failure-v0"
}
```

### `s11-long-soak-physical-five-node-v0`

- requiredEnvironment: `topology=physical-five-node`, `eligibleNodeCount=4`, `excludedNodeCount=1`, `sameHost=false`, `faultInjection=controlled-v1`.
- criteria:
  - `windowSeconds >= 86400`
  - `attemptedOperationCount >= 1000`
  - `observedStorageFaultCaseCount >= 3`
  - `recoveryAfterStorageFaultPassCount >= 3`
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

관측 fault 3건은 corruption, capacity, partial-write/durability 부류를 각각 1건 이상 포함해야 하고 importer가 injection receipt와 recovery receipt를 대조한다. hosted storage fault soak은 이 target을 만족하지 않으며 reference evidence일 뿐이다.

### `s11-st-actual-pitr-archive-failure-v0`

- requiredEnvironment: `topology=physical`, `failureDomain=separate`, `archiveKind=operational`, `sameHost=false`, `faultInjection=controlled-v1`.
- criteria:
  - `consecutiveWeeklyRestoreSmokeWeeks >= 2`
  - `maxRestoreSmokeGapDays <= 7`
  - `retentionDays >= 35`
  - `rpoSeconds <= 900`
  - `rtoSeconds <= 3600`
  - `walArchiveFaultCaseCount >= 1`
  - `silentArchiveLossCaseCount >= 1`
  - `retentionInterruptionCaseCount >= 1`
  - `recoveryAfterFaultPassCount >= 3`
  - `falsePitrPassCount == 0`
  - `retainedBoundaryDeletionCount == 0`
  - `cleanupResidueCount == 0`

## 2. 닫힌 raw fault case identity

아래 22개만 허용한다. importer는 정렬된 UTF-8 compact JSON 배열의 SHA-256 `5d700981ee429ebbfc66b8ed28d8dc9e37e16e327a673d6061bdec5e7e334fd9`를 고정하고, 중복·누락·미등록 case를 import 오류로 거부한다.

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

Local 하위 case는 PG-free fault injection 전용이다. `CAP-02`는 기존 object가 없는 새 key에서만 실행한다. Local mode 변조 case는 검증 뒤 원래 mode를 복원한다.

## 4. pin·merge 규칙

- 정본 registry entry의 `sourceDocument`는 이 파일의 고정 commit/path/blob을 가리킨다.
- 이 commit이 integration 조상으로 남도록 PR은 merge commit 방식(`--merge`)으로만 병합한다. squash·rebase 병합은 금지한다.
- registry patch 뒤 `TARGET_REGISTRY_BLOB`과 importer pin을 새 정본 registry blob으로 갱신하고, repo 수준 시험으로 registry의 sourceDocument blob이 HEAD blob과 같은지 확인한다.
- release evidence는 release SHA에서 다시 실행한다. PR-head hosted 결과는 후보·reference일 뿐 release gate evidence가 아니다.
