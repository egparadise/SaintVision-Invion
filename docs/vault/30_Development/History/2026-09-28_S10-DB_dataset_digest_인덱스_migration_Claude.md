---
doc_id: "HIST-CLAUDE-S10DB-DIGEST-INDEX-MIGRATION-001"
title: "S10-DB dataset digest 인덱스 migration 0050 — CONCURRENTLY와 재시도 정리, 고정 순서 0047→0048→0049→0050"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T12:45:57+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-DB"]
tags: ["s10-db", "lineage", "migration", "index", "claude"]
---

# S10-DB dataset digest 인덱스 migration

`dataset_versions(tenant_id, content_sha256)` 인덱스 하나와 그 착지 방식. 승인된 설계 `#158` v1.2 §7이 요구한 것이고, **왜 별 PR인지**가 이 문서의 절반이다.

## 1. 왜 lineage 조회 PR과 같이 가지 않는가

설계 §7은 "역조회 라우트는 이 인덱스 없이 착지하지 않는다 — 구현 PR에서 migration과 라우트가 같은 PR에 들어간다"고 적었다. 그런데 코디네이터가 열린 migration의 순서를 하나로 고정했다 — `0047_audit_events_isolation`(#128) → `0048_object_store_locator`(#159) → `0049_mlflow_mirror`(#172) → **`0050`(이것)**. 따라서 이 migration은 #172 위에 있어야 하는데 **#172는 수정 요청 상태**이고, 조회 PR은 공유 `api/problem.py` 때문에 #167 위에 있다. 한 PR에 둘 다 담으면 승인된 #167 작업이 아직 수정 중인 #172에 묶인다.

그래서 코디네이터 권고대로 **migration만 분리**했다. 설계의 요구는 폐기하지 않고 **병합 순서로 지킨다** — `#159 → #172 → 이 PR → 조회 PR`. 조회 PR이 이것보다 먼저 병합되면 역조회 1단계(`content_sha256` 술어)가 `dataset_versions` 전체 스캔이 된다. **순서를 코드로 강제할 방법은 없으므로** 두 PR 본문과 시험 docstring에 적어 두는 것이 내가 할 수 있는 전부다.

같이 옮긴 것: `DatasetVersion`의 인덱스 선언(모델과 DB가 어긋나면 안 된다), CONCURRENTLY 구조를 읽는 PG-free 시험, 설계 §10-35(계획 관측)·§10-36(재시도) 실 PG 두 node.

## 2. 인덱스 자체

```
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_dataset_versions_tenant_id_content_sha256
    ON dataset_versions (tenant_id, content_sha256);
```

- **필요한 이유**: `content_sha256`에 인덱스가 없었다 — 모델 `__table_args__`에도, 기존 migration grep에도 0건. 역조회의 1단계가 바로 그 조회다.
- **`tenant_id` 선행**: 모든 읽기가 RLS tenant 범위 안이라 인덱스와 정책 술어가 같은 방향이다.
- **UNIQUE 아님**: 같은 바이트가 여러 dataset version으로 등록될 수 있고, 유일 제약은 그 사실을 금지한다. API가 배열을 반환하는 이유와 같다.
- `model_lineage`는 `ix_model_lineage_subject_id`가 이미 있어 추가하지 않는다. 측정 없이 인덱스를 늘리지 않는다.

## 3. CONCURRENTLY와 재시도

autocommit block 안에서 **`DROP INDEX CONCURRENTLY IF EXISTS` → `CREATE INDEX CONCURRENTLY IF NOT EXISTS`** 순이고 downgrade도 CONCURRENTLY다.

- 일반 `CREATE INDEX`는 `dataset_versions`에 `ACCESS EXCLUSIVE`를 잡아 dataset 등록을 그 시간만큼 막는다.
- **선행 DROP이 핵심이다**: 실패한 `CREATE INDEX CONCURRENTLY`는 **INVALID index**를 남긴다. 계획에 쓰이지 않으면서 이름을 점유하고 쓰기 비용은 그대로 문다. 그래서 그것을 먼저 치우지 않으면 재실행이 성공할 수 없다.
- autocommit block 안이라 이 migration은 **트랜잭션으로 되돌아가지 않는다**. 부분 실패 상태는 `IF EXISTS`/`IF NOT EXISTS` 조합으로 수렴한다.
- 이 저장소의 **첫 CONCURRENTLY migration**이다(`migrations/`에서 grep 0건).
- `tools/migration_graph.py`가 `0050 reversible`, head `0050_dataset_digest_lookup`, safe downgrade target `0049_mlflow_mirror`로 본다.

## 4. 재현하지 못하는 것

실 PG 재시도 시험이 만드는 것은 **이름이 이미 점유된 상태**이고, 선행 DROP이 없으면 재시도가 실패하는 바로 그 조건이다. **진짜 INVALID index는 재현하지 않았다** — 동시 build를 중간에 죽여야 생기고 시험이 안정적으로 만들 수 없다. 이 구분을 시험 docstring에 적었다.

계획 관측도 성능 단언이 아니다. `enable_seqscan = off`는 금지가 아니라 비용 가중이고, runner 크기에서 나오는 숫자는 근거가 아니다. 기록하는 것은 "인덱스가 있으면 그것을 쓰고, 지우면 seq scan으로 바뀐다"까지다.

## 5. 검증 증거 (실행)

- `pytest tests/core -q` → **1035 passed, 4 skipped**. 신규 `tests/core/test_dataset_digest_index_migration.py` → **3 passed**.
- `pytest tests/integration/test_lineage_digest_index_real_pg.py` → 로컬 **2 skipped**(`INV_TEST_ADMIN_DSN` 부재). 실행 근거는 hosted Backend다.
- `python tools/migration_graph.py` → head `0050_dataset_digest_lookup`, reversible, safe downgrade target `0049_mlflow_mirror`.
- `check_docs`·`check_doc_single_source --ratchet` → exit 0.
- 로컬 실 PG·Docker·전체 suite **미실행**.

## 6. 보고할 사실 — #172가 아직 `0046` 위에 있다

#172의 `0049_mlflow_mirror`는 현재 `down_revision = "0046_model_manifest_readiness"`다. #128(`0047`→`0046`)과 #159(`0048`→`0047`)가 먼저 들어가면 `0046`에서 가지가 갈라져 **head가 둘**(`0048`과 `0050`)이 된다. 코디네이터가 고정한 순서대로 단일 head를 유지하려면 **#172가 `0049`의 `down_revision`을 `0048_object_store_locator`로 바꿔야** 한다. 내 카드로는 닫을 수 없으므로 여기 남긴다.

## 7. 다음 첫 행동

Codex 독립 검토. #159·#172가 정리되면 이 PR을 먼저 병합하고, 그 다음에 lineage 조회 PR을 병합한다.
