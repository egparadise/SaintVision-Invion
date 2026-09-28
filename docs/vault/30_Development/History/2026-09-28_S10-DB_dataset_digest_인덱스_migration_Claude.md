---
doc_id: "HIST-CLAUDE-S10DB-DIGEST-INDEX-MIGRATION-001"
title: "S10-DB dataset digest 인덱스 migration 0050 — CONCURRENTLY와 재시도 정리, 고정 순서 0047→0048→0049→0050"
version: "1.2.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T13:14:20+09:00"
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

- `pytest tests/core -q` → **1138 passed, 5 skipped**(#172 head merge 이후). 신규 `tests/core/test_dataset_digest_index_migration.py` → **4 passed**(경로 guard 1건 추가).
- `pytest tests/integration/test_lineage_digest_index_real_pg.py` → 로컬 **2 skipped**(`INV_TEST_ADMIN_DSN` 부재). **로컬 skip은 실행이 아니므로** 실행 근거는 이 head의 hosted Backend run이고, run ID와 두 matrix 수치를 PR에 적는다.
- `python tools/migration_graph.py` → head `0050_dataset_digest_lookup`, reversible, safe downgrade target `0049_mlflow_mirror`.
- `check_docs`·`check_doc_single_source --ratchet` → exit 0.
- 로컬 실 PG·Docker·전체 suite **미실행**.

## 6. v1.1 — Codex 검토 3건 반영, 그리고 v1.0의 내 보고는 이미 낡았다

### 6-1. 실 PG 재시도 node가 없는 파일을 읽고 있었다

`tests/integration/test_lineage_digest_index_real_pg.py`의 경로가 renumber 이전의 `0047_dataset_digest_lookup.py`였다. 그 node는 migration source를 읽어 **그 안의 statement로** 재시도를 돌리므로, 수집은 되고 본문이 `FileNotFoundError`로 죽는다 — 즉 재시도·downgrade 검증이 **한 번도 실행되지 않았다.** 카드 be에서 시험 본문을 그대로 옮겨오면서 renumber를 따라가지 않은 내 실수다.

경로를 `0050`으로 고치고 그 node 안에 `path.exists()` 단언을 넣었다. 그리고 **경로는 DB 없이 확인할 수 있으므로 DB 없이 확인한다** — `tests/core/test_dataset_digest_index_migration.py`가 그 실 PG 파일의 소스에서 `migrations/versions/*.py` 문자열을 뽑아 **전부 존재하는지**, 첫 항목이 이 migration인지 단언한다. #167에서 두 번, 여기서 한 번, 같은 부류(실 PG 파일의 결함을 hosted에서야 발견)라 guard를 남긴다.

### 6-2. stack base가 #172의 현재 head가 아니었다

내 head의 parent는 `44654021`이었고 #172는 그동안 `faa2e470`으로 수정됐다(GitHub이 이 PR을 CONFLICTING으로 표시하고 hosted check가 0건이었다). force 없이 `faa2e470`을 **merge**했다. 그 head는 이미 #159를 병합해 `0047`·`0048`을 갖고 있으므로, 이제 이 브랜치에 **`0047 → 0048 → 0049 → 0050` 전체 사슬**이 있고 `migration_graph`가 head 하나(`0050`, reversible, safe downgrade `0049`)로 본다.

### 6-3. 내가 보고한 "#172의 `0049`가 `0046` 위" 는 이미 정정됐다

v1.0에서 "#128·#159가 먼저 들어가면 head가 둘이 된다"고 적었는데, **`faa2e470`에서 `0049`의 `down_revision`이 이미 `0048_object_store_locator`로 고쳐졌다.** 그 보고는 `44654021` 시점에는 참이었고 지금은 아니므로 철회한다 — 고정 순서는 #172 쪽에서 이미 닫혔다.

### 6-4. head를 옮기니 따라와야 하는 것이 둘 있었다

#172 head를 merge하고 `0050`을 그 위에 두자 #159 lane의 시험 둘이 깨졌다 — 둘 다 **migration head를 상수로 pin**하고 있었다.

- `tests/core/test_object_store_locator_migration.py`가 `head.revision == "0049_mlflow_mirror"`를 단언한다. 그 파일의 docstring이 이미 "0048이 head였다가 0049가 위에 왔다"는 이력을 적고 있으므로, 같은 방식으로 `0050`까지 적고 `0049`는 **중간 고리로** 계속 단언하게 바꿨다(`0049.down_revision == 0048`).
- 같은 파일이 `tools/definer-policy.json`의 `revision`이 chain head와 같아야 한다고 단언하고, `tools/check_definer_functions.py:64-70`이 **살아 있는 DB의 `alembic_version`과 그 필드를 비교**해 다르면 `migration_revision_mismatch`를 낸다. 그래서 policy의 `revision`을 `0050_dataset_digest_lookup`으로 옮겼다.

**`functions` 목록은 건드리지 않았다** — 이 migration은 SECURITY DEFINER 함수를 만들지 않으므로 옮겨야 하는 것은 head 표시뿐이고, 13개 항목이 그대로임을 시험이 확인한다. 다른 lane의 시험을 고치는 것이라 여기 명시한다: 바꾼 것은 **기대 head 상수**이고 그 시험의 뜻("사슬에 head가 하나이고 policy가 그것을 따라간다")은 그대로다.

### 6-5. 실행 증거

이 head의 hosted Backend 결과로 갱신한다. v1.0이 적은 "core 1035 passed / 실 PG 2 skipped"는 **새 head의 hosted 실행을 대신하지 않는다**는 지적이 맞다 — 로컬 skip은 실행이 아니다.

## 7. 다음 첫 행동

이 head의 hosted Backend에서 두 postgres case가 failure·skip 0으로 돌고 graph가 단일 head임을 run ID로 제시한 뒤 Codex 재검토를 받는다. #172 head가 다시 바뀌면 force 없이 다시 merge한다. 병합은 이 PR이 lineage 조회 PR(#175)보다 먼저다.

## 8. v1.2 — 계획 관측이 아무것도 증명하지 못하고 있었다 (hosted run 36376198678)

merge 뒤 첫 hosted 실행에서 **migration graph 단계는 통과**했다(`head: 0050_dataset_digest_lookup`, `safe downgrade target: 0049_mlflow_mirror`). 그런데 `test_35`가 실패했고, 실패 메시지가 문제를 그대로 보여 준다 — `Index Scan using uq_dataset_versions_tenant_id_version_id`.

**빈 테이블에서는 계획이 아무것도 말해 주지 않는다.** 행이 없으면 모든 비용이 비슷하고 `enable_seqscan = off`로 벌점을 받은 seq scan은 **어떤** 인덱스에도 진다. 그래서 planner가 내 인덱스와 무관한 unique index를 골랐고, 내 인덱스가 있든 없든 같은 결과가 나왔다. 즉 v1.0·v1.1의 그 node는 **통과하든 실패하든 근거가 아니었다.**

고친 방식: 2000행을 심고 `ANALYZE`한 뒤 EXPLAIN한다(`enable_seqscan` 조작 없이). 그러면 `(tenant_id, content_sha256)` 동등 조건에 두 컬럼 인덱스가 선택되는 것이 **결정적**이고, 인덱스를 지우면 그것을 쓸 수 없다는 것이 falsifiable한 단언이 된다. 대체로 무엇을 고르는지는 planner의 몫이라 단언하지 않고 실패 메시지에 계획을 싣는다. 심은 행·project·dataset은 `finally`에서 지우고 다시 `ANALYZE`한다 — 이 node가 다른 시험의 통계를 바꾸지 않는다.

**성능 단언이 아니라는 성질은 그대로다.** 주장하는 것은 "이 술어를 이 인덱스가 담당한다"까지이고 비용 숫자는 아니다.

### 같은 run의 다른 실패 2건은 이 PR의 diff가 아니다

`tests/test_tracking_mirror.py`의 `test_finished_eval_run_enqueues_suite_identity_and_category_scores`와 `test_attempt_check_constraints_refuse_malformed_rows`가 함께 실패했는데, 둘 다 **merge해 온 #172 head(`41256e4f`)의 시험**이고 이 브랜치의 diff는 `0050` migration·모델 인덱스 선언·그 시험들뿐이다. #172는 그 뒤 `0be57050`으로 다시 움직였고 자체 Backend가 돌고 있다. 그 head가 정리되면 force 없이 다시 merge해 재실행한다.
