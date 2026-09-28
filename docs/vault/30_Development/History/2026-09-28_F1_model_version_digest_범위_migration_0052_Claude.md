---
doc_id: "HIST-CLAUDE-F1-MODEL-VERSION-DIGEST-SCOPE-0052-001"
title: "F1 model version digest UNIQUE 범위 좁히기 migration 0052 v1.1 — tenant-wide에서 (model_id, content_sha256)로, sibling-project 존재 oracle 제거, catalogue 확인 기반 재시도 수렴(Codex #197)·사전 데이터 검사·fail-closed downgrade·CONCURRENTLY"
version: "1.1.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T17:00:42+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-BE"]
tags: ["s10-be", "migration", "authorisation", "model-registry", "claude"]
---

# F1 model version digest UNIQUE 범위 좁히기 (migration 0052)

PR #191(W2 등록 route) 사전 검토에서 Codex가 찾은 **F1**을 닫는 migration이다. base는 조정자가 지정한 **#176 head `1ddd85d0`**(`agent/claude/s10-be-mlflow-mirror-p2`), 번호는 **0052**(`down_revision = 0051_service_credentials`)이고 W5는 조정자 결정으로 **0053**으로 이동했다. 로컬 실 PG·Docker·전체 suite는 돌리지 않았다.

## 1. 무엇이 문제였나 — 메시지가 아니라 status code가 누출이다

`uq_model_versions_tenant_id_content_sha256`은 `0004_s10_lineage`부터 있었고 진짜 불변식을 기록한다(S10-ST: "두 이름으로 같은 bytes는 잡을 만한 실수"). 문제는 범위다.

`POST /projects/{p}/models/{m}/versions`는 **project별 `canApprove`** 등급이다. project A만 승인할 수 있는 사용자가 digest를 제출하면 **201이면 이 tenant에 그 bytes가 없고, 409면 있다** — 자기가 볼 수 없고 membership도 없는 project B에 있을 수 있다. 응답 body에서 상대 식별자를 지워도 **존재 bit는 status code에 남는다.** project 범위 등급의 거부가 project를 넘어 답하면 그것은 project 범위가 아니다.

W2에서 내가 한 것은 "어디서 충돌했는지 말하지 않기"까지였고, Codex의 판정은 그것으로 부족하다는 것이다. 동의한다.

## 2. 무엇으로 바꿨나

`uq_model_versions_model_id_content_sha256`. model은 정확히 한 project에 속하므로(`models.project_id` + `projects`로 가는 복합 FK) 이 제약의 충돌은 **호출자가 path에 이미 적은 model 안의 충돌**이다. 원래 불변식은 의미 있는 곳에서 살아남고(한 model 안에서 같은 bytes 두 이름은 여전히 거부), project를 넘는 답은 사라진다.

**데이터 migration이 아니다**: 지우는 제약이 더하는 제약보다 **엄격히 강하다**. `(model_id, content_sha256)`가 같은 두 행은 `(tenant_id, content_sha256)`도 같다(model은 tenant 하나). 그래서 기존 행은 새 제약을 **무조건 만족**한다.

그것은 관찰이 아니라 **논증**이므로 `upgrade`가 바꾸기 전에 데이터베이스를 읽는다 — 논증이 틀렸다면 operator는 절반 적용된 migration이 아니라 **문장 하나**를 본다(위반 group을 model/digest로 최대 10개까지 나열).

## 3. 순서와 잠금

- **생성 → 승격 → 제거**: 새 UNIQUE INDEX를 `CONCURRENTLY`로 만들고 `ADD CONSTRAINT … USING INDEX`로 승격한 **뒤에** 옛 제약을 지운다. 그래서 테이블이 보호 없이 있는 순간이 없고, 둘 사이에서 죽으면 **양쪽이 남는다**(둘 다 성립하므로 재시도가 수렴한다). (**v1.1에서 철회: 양쪽이 남는 것은 맞지만 재시도가 수렴하지 않았다 — §8.**) 반대 순서는 무보호 구간을 만든다.
- **`CONCURRENTLY`**: 평범한 unique 제약 추가는 인덱스 빌드 전체 동안 `model_versions`에 ACCESS EXCLUSIVE를 들고 있어 등록을 막는다(`0050`이 같은 이유로 세운 선례).
- 실패한 `CREATE UNIQUE INDEX CONCURRENTLY`는 **INVALID 인덱스가 이름을 붙잡은 채** 남고 `ADD CONSTRAINT … USING INDEX`가 그것을 거부하므로, upgrade가 그 이름을 **먼저 drop**한다. 그것이 재시도를 안전하게 만든다. (**v1.1 정정: 그 drop은 새 constraint가 없을 때만 한다 — constraint가 소유한 index를 drop하려 해서 재시도가 wedge됐다. §8.**)
- **offline render**: `alembic upgrade --sql`은 mock connection으로 렌더하므로 질의할 수 없다(`MockConnection`에 `exec_driver_sql`이 없다 — 이 migration의 첫 판이 Backend lane의 `Migration renders offline` 단계를 깼고 로컬에서 잡았다). 그 모드에서는 검사를 건너뛴다 — 물어볼 데이터베이스가 없고 출력은 사람이 읽을 SQL이다. 부정 시험이 **bind를 요구하는 것 자체**를 회귀로 잡는다.

## 4. downgrade는 거부한다 — 이유가 둘이다

1. 좁힌 뒤에는 한 tenant의 두 project가 **정당하게** 같은 bytes를 들 수 있으므로 tenant-wide 제약을 다시 만들 수 없다.
2. 다시 만든다면 **좁히려고 닫은 cross-project 존재 oracle을 다시 연다.**

그래서 `RuntimeError`이고 두 이유를 문장으로 적는다. `migration_graph`가 irreversible로 보고하고 head는 **`0052` 하나**다.

## 5. 함께 옮긴 것

- `db/models/lineage.py`의 `ModelVersion.__table_args__`도 같이 좁혔다 — model과 데이터베이스가 스키마에 대해 다르게 말하면 안 된다.
- head marker 둘을 전진시켰다: `tools/definer-policy.json["revision"]` → `0052_model_version_digest_scope`, `tests/core/test_object_store_locator_migration.py`의 head 단언(0051은 중간 링크로 계속 단언). 두 값이 어긋나면 `check_definer_functions`가 잡는다.

## 6. 검증

| 명령 | 결과 |
|---|---|
| `python tools/migration_graph.py` | head `0052_model_version_digest_scope` **단일**, safe downgrade target `0052`(irreversible) |
| `pytest tests/core/test_model_version_digest_scope_migration.py -q` | **11 passed** |
| `pytest tests/core/test_object_store_locator_migration.py tests/core/test_dataset_digest_index_migration.py -q` | 13 passed |
| `pytest tests/test_migrations.py -q` | **26 passed**(offline render 포함) |
| `python tools/export_schemas.py --check` | PASS |
| `check_docs` · `check_doc_single_source --ratchet` | exit 0 |

**변이 3건이 죽었다**(migration을 변이시켜 돌린 뒤 복원):

| 변이 | 죽은 시험 |
|---|---|
| ADD/DROP CONSTRAINT 순서 뒤바꿈 | 2 |
| 사전 데이터 검사 제거 | 1 |
| downgrade를 no-op으로 | 2(하나는 기존 chain 시험) |

시험이 주석을 읽어 통과하던 첫 판도 직접 잡았다 — `ADD CONSTRAINT`가 **설명 주석에** 있어서 순서 단언이 prose를 매칭했다. 그래서 `op.execute` 호출을 AST로 뽑고 **source 위치로 정렬**해(ast.walk는 너비 우선이다) 실행되는 SQL만 본다.

실 PG 6건은 hosted Backend에서 실행된다: 새 제약이 catalogue에 있고 옛 제약은 없음, 컬럼 순서, **한 tenant의 두 project가 같은 digest를 각각 등록 가능**, 한 model 안 두 version 같은 digest는 여전히 거부, 한 project 안 두 model은 허용, 다른 tenant는 영향 없음. hosted가 fixture에서 죽지 않도록 PG-free guard도 넣었다(#167에서 잃은 한 시간).

## 7. 다음 첫 행동

Codex 검토. 승인되면 **#191이 이 head를 merge**해 oracle 시험을 뒤집어 고정한다(목표 시험 "두 project가 같은 digest를 각각 등록"은 지금 #191에 xfail로 둘 수 없다 — xfail은 JUnit `skipped`이고 Backend lane의 exact-skip gate가 거부한다). #191은 이어서 새 #184 head(= #195, 정본 403 denial audit)도 merge해 F4와 register route action 회귀를 고정한다.

## 8. v1.1 — Codex 재검토: "ADD 뒤 중단도 수렴"이 **거짓이었다** (#197, head `d9526198`)

범위 축소 방향은 승인받았고 차단 1건이 왔다. **내가 문서에 적은 수렴 주장이 틀렸다.**

`upgrade()`가 새 UNIQUE INDEX를 constraint로 승격한 뒤 옛 constraint를 drop하기 전에 중단되면 revision은 아직 `0051`이고 새 constraint는 이미 있다. 재실행은 무조건 `DROP INDEX CONCURRENTLY IF EXISTS uq_model_versions_model_id_content_sha256`부터 했는데, **그 index는 새 constraint가 소유**하므로 PostgreSQL이 `cannot drop index ... because constraint ... requires it`로 거부한다. 즉 **"안전하다"고 서술한 바로 그 지점에서 migration이 영구 wedge된다.** 지적이 정확하다.

### 8-1. catalogue를 먼저 읽고 세 갈래로 수렴한다

`CONSTRAINT_SHAPE`가 `pg_constraint`에서 이름·table·`contype`·컬럼 순서를 읽는다(table로 한정해 다른 table의 동명 constraint를 이것으로 오인하지 않는다).

| catalogue 상태 | 하는 일 |
|---|---|
| 새 constraint **없음** | index 이름 정리(실패한 concurrent 빌드가 남긴 standalone/INVALID) → `CONCURRENTLY` 빌드 → 승격 |
| 새 constraint **정확히 있음**(`u`, `(model_id, content_sha256)`) | **아무것도 건드리지 않는다.** 옛 constraint만 제거해 수렴 |
| 이름만 같고 정의가 다름 | **fail-closed.** 이 migration이 아닌 것이 그 이름을 소유하고 있고, 추측이 멈추는 것보다 나쁘다 |

INVALID/standalone index 정리는 **새 constraint가 없을 때만** 수행한다(요구 2). 옛 constraint 제거는 `DROP CONSTRAINT IF EXISTS`로 바꿔 **두 번째 중단 지점**(drop 뒤 revision 기록 전)도 수렴한다.

### 8-2. 시험을 source 읽기에서 **동작 관찰**로 바꿨다

v1.0의 순서 시험은 migration **소스의 부분문자열 순서**를 봤고, 그래서 `ADD CONSTRAINT`를 **설명 주석에서** 매칭해 통과했다(v1.0에서 이미 한 번 잡았다). 이제 `upgrade()`를 stand-in catalogue로 **직접 돌려** 발행되는 SQL을 기록한다. catalogue 상태 네 가지가 각각 시험이다:

- 깨끗 → `autocommit` + DROP INDEX + CREATE UNIQUE INDEX + ADD CONSTRAINT + DROP CONSTRAINT IF EXISTS, **5건 정확히**;
- **승격 뒤 재시도** → **`DROP CONSTRAINT IF EXISTS` 한 건뿐**이고 `DROP INDEX`·`CREATE UNIQUE INDEX`·`ADD CONSTRAINT`·autocommit block이 **없다**. 위반 질의도 돌지 않는다(constraint가 이미 그것을 강제한다);
- 이름 충돌 5종(다른 컬럼·순서 뒤바뀜·컬럼 부족·`contype` 다름·컬럼 없음) → `RuntimeError`, 실행 0건;
- 위반 행 → `RuntimeError`, 실행 0건;
- offline(`as_sql`) → 전체 5건 렌더, **bind 요구 자체가 실패**로 잡힌다.

**무조건 DROP INDEX로 되돌리는 변이에서 6건이 죽는다**(요구 3의 되살림 조건). shape 확인만 없애는 변이에서도 5건이 죽는다.

### 8-3. 실 PG crash-resume 2건

- **`test_a_run_interrupted_after_the_promotion_resumes_and_converges`**: 옛 constraint를 다시 만들고 `alembic_version`을 `0051`로 되돌려 **중단 상태를 실제로 만든 뒤** 진짜 Alembic으로 `upgrade head`를 돌린다. 끝난 뒤 새 constraint의 **oid가 그대로**(drop-and-rebuild였다면 바뀐다), 옛 constraint는 없고, revision은 `0052`다. `finally`로 head 상태를 복원해 뒤 시험에 영향이 없다.
- **`test_the_index_the_new_constraint_owns_cannot_be_dropped_on_its_own`**: PostgreSQL이 그 index 단독 drop을 거부하는 것을 직접 단언한다 — 재시도 로직이 **상상한 오류**를 막는 것이 아니라는 근거다.

실 PG는 6건 → **8건**이 됐다.

### 8-4. 검증(delta)

| 명령 | 결과 |
|---|---|
| `pytest tests/core/test_model_version_digest_scope_migration.py -q` | **19 passed**(v1.0의 11에서) |
| `pytest … test_object_store_locator_migration.py tests/test_migrations.py -q` | 합계 **54 passed** |
| `python tools/migration_graph.py` | head `0052` 단일, safe downgrade target `0052` |
| 변이 | 무조건 DROP INDEX 복원 **6건 사망**, shape 확인 제거 **5건 사망** |

공개 응답 code·route 변화는 없다.
