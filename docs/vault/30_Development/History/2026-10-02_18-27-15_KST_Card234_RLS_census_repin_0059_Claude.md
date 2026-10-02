---
doc_id: "HISTORY-CARD234-RLS-CENSUS-REPIN-0059-20261002"
title: "카드 234 — 검토된 RLS census가 migration 0059에서 stale이었다. 손으로 고치지 않고 생성 도구를 만들고, 다음 migration은 같은 PR에서 걸리게 했다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T18:27:15+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "51435c4f"
task_ids: ["S11-BE", "S02-DB"]
tags: ["ac11", "security", "rls", "census", "migration", "ratchet", "claude"]
---

# 카드 234 — RLS census repin (0059)

## 0. 한 줄

`#322`가 표 모집단을 **검토된 census**에 결속했고(155개 표, blob 고정) `#323`의 migration `0059`가 `inv.build_execution_intents`를 더했는데, 둘이 **같은 train 사슬**에 들어오면서 census가 재생성되지 않아 `evaluate_rls`가 그 tree의 모든 RLS 보고를 **`unreviewed ['inv.build_execution_intents']`** 로 거부했다. 이 판은 **손 편집이 아니라 생성 도구**로 census를 다시 만들고(156개 표), pin을 돌리고, **다음 migration부터 같은 PR에서 걸리는 래칫**을 넣었다. hosted lane으로 거부가 사라진 것을 실측했다.

## 1. 무엇이 stale이었나 — 사슬

| 순서 | 무엇 |
|---|---|
| `#322` F-R7 | 보고가 자기 표 모집단을 고르던 fail-open을 닫고 `tools/rls-table-census.json`(그 PR의 tree에서 **155개**)에 결속했다 |
| `#323` | migration **`0059_build_execution_intents`** 가 `inv.build_execution_intents`를 더했다 |
| train 21·22·23 | 둘이 같은 사슬에 들어왔고 **census는 다시 생성되지 않았다** |
| 결과 | 생산자는 **156개**를 관측하고 검토 목록은 155개 → **fail-closed 거부**. `#329` r2에서 train 22의 hosted artifact를 읽다가 발견했다 |

**파일이 요구한 그대로 동작한 것이다** — census의 note가 "migration이 표를 추가하면 stale이고 같은 검토 변경에서 재생성·repin하라"고 적는다. 빠진 것은 그 repin이고, 그래서 이 카드는 **그 repin을 사람의 기억에 맡기지 않는 것**까지 한다(§4).

## 2. 재생성 — 도구가 쓰고, 사람은 명령만 돌린다

`tools/write_rls_table_census.py`를 새로 만들었다. 그것이 하는 일은 **collector가 쓴 관측 JSON의 `table_census` 블록을 검토 파일로 옮기는 것**이고, 그 과정에서 count와 sha256을 **자기가 다시 계산**해 관측과 어긋나면 거부한다. 손으로 목록을 고치는 길은 없다.

```bash
INV_TEST_ADMIN_DSN=<admin dsn> python tools/collect_rls_evidence.py --disposable --out-dir <dir>
python tools/write_rls_table_census.py --observation <dir>/<그 json>
```

이 tree(train 23 후보, migration head `0059_build_execution_intents`)에서 돌린 결과:

| 항목 | 이전 | 이후 |
|---|---|---|
| 표 수 | 155 | **156** |
| `sha256`(정렬된 이름) | `49091998b649…` | **`e3a64e5ebf32…`** |
| `RLS_CENSUS_BLOB` | `c3db5f3edd2a…` | **`f1618c0df1b3…`** |
| `measuredFrom.migrationHead` | `0058_release_acceptance_resolver.py` | **`0059_build_execution_intents`** |

차집합은 **정확히 한 표**였다: `inv.build_execution_intents`(추가), 제거 0.

## 3. 그 표의 ground truth — 정본 규칙으로 읽었다

`0059`가 적는 것: app role은 **`inv_kernel`**, tenant 식별은 `NULLIF(current_setting('inv.tenant_id', true), '')::uuid`, 그리고 그 migration은 route도 CLI도 두지 않는다. collector가 **실제로 관측한 것**(이 PC의 disposable migrated DB):

| role | select | RLS | FORCE | 정책 | GUC 네 상태 | identity |
|---|---|---|---|---|---|---|
| `inv_kernel` | `table` | ✔ | ✔ | `build_execution_intents_tenant_isolation` | unset 0 · tenant-A 0 · foreign 0 · unknown 0 · not-uuid **denied 22P02** | `ctid`, match |
| `inv_runtime_dev` | `table` | ✔ | ✔ | **없음** | 같음(정책이 없으므로 default deny) | `ctid`, match |
| 나머지 여섯 role | — | — | — | — | **그 표가 목록에 없다**(권한·정책·probe가 하나도 없어 compaction이 떨어뜨린다) | — |

**정본 규칙(E1~E5)에 비추면 새 disposition이 필요하지 않다**: 표는 RLS enabled **그리고** forced이고(E2), GUC unset·unknown tenant에서 0행이며(E3·E5), foreign 행이 0이고 identity가 일치한다(E4). 그래서 이 카드는 `rls-boundary-baseline.json`과 검토된 allowlist의 dispositions를 **건드리지 않았다**.

### 3-1. 그러면서 Codex에 보고하는 두 가지 (결정은 하지 않았다)

1. **`inv_runtime_dev`가 이 PC에서는 존재하고, 그 표에 table-level SELECT를 가진다**(정책은 없다). 그 role은 **migration이 만들지 않는 개발자 login**이고 hosted 생산자의 DB에는 **없다**(`#322`가 `RLS_OPTIONAL_ROLES`로 고정한 그 한 role이다). 즉 그 grant는 내 dev cluster의 상태이지 정본이 아니다. **질문**: 개발자 cluster에서 그 role이 intent queue를 읽을 수 있어도 되는가, 아니면 그 cluster의 grant를 좁혀야 하는가. 정본 쪽(lane DB)에는 영향이 없으므로 이 카드는 바꾸지 않았다.
2. **빈 표에서 `ctid` identity는 0행끼리 일치한다.** `#322` F-R1은 **readable-key** 방법의 vacuity를 닫았는데(그 방법은 유일성이 *측정되어야* 성립하므로 0행이면 측정이 없다), `ctid`는 그 자체가 **참 row identity**라서 "빈 표는 빈 표와 같다"가 올바른 진술이다. 그래서 둘을 같은 규칙으로 묶지 않았다 — 다만 156개 표 중 대부분이 빈 표라는 사실은 그대로이고, 축의 의미를 더 키우려면 §5의 `inv_audit_reader` 결정(카드 225 §5)이 먼저다.

## 4. 재발 방지 — `tests/test_rls_table_census_ratchet.py`

migration 파일을 **offline으로 읽어**, 만들어진 표가 census에 없으면 실패한다. 방향은 한쪽이다 — **생성됐고 제거되지 않은 표는 반드시 목록에 있어야 한다**. 반대 방향(census에 있는데 파서가 못 찾는 표)은 **live 측정의 몫**으로 남긴다. 이것은 모집단의 두 번째 정의가 아니라 래칫이다.

**측정하다 찾은 함정**: 처음 판은 `op.drop_table`을 전부 "제거"로 셌는데, alembic migration은 **자기 `downgrade()`에서 자기 표를 drop**하므로 모든 표가 상쇄되어 **래칫이 무력했다** — census에서 `0059`의 표를 지워도 시험이 통과했다. 그래서 Python migration은 **`upgrade()` 절만** 읽는다. 지금은 같은 변이가 그 표 이름을 적으며 실패한다.

**vacuous 래칫도 막았다**: 파서가 찾은 표가 100개 미만이면 그 자체로 실패한다(패턴이 깨져 집합이 비면 어떤 census든 통과하므로 — `#322` F-R1의 0행 교훈과 같은 형태다).

| 시험 | 무엇을 고정하나 |
|---|---|
| `test_the_parser_finds_the_schema_and_not_nothing` | 파서가 100개 이상을 찾고, `0059`의 표를 찾고, 그것을 "제거됨"으로 세지 않는다 |
| `test_every_table_a_migration_creates_is_in_the_reviewed_census` | **이 카드의 이유** — stale이면 실패하고 고치는 명령을 메시지에 적는다 |
| `test_the_census_file_is_self_consistent_and_pinned` | 파일이 자기 count·digest와 맞고, LF이고, `RLS_CENSUS_BLOB`이 그 bytes를 가리키고, loader가 그 집합을 돌려준다 |
| `test_the_census_names_the_migration_head_it_was_measured_at` | provenance의 migration head가 이 tree에 실제로 있는 파일이다 |

## 5. 실측 — hosted lane

| 단계 | 결과 |
|---|---|
| 이전(train 22, `#329` r2에서 읽은 run) | `evaluate_rls` → **`INVALID_RUN`**, 사유 `unreviewed ['inv.build_execution_intents']` |
| 이 branch의 head에서 dispatch한 run **`36989599918`** (artifact **`11218732031`**) | success |
| 그 보고의 census | `count 156`, `sha256 e3a64e5e…` — 검토 파일과 **일치** |
| `rls_report_shape` | **`None`**(통과) |
| `evaluate_rls` | **`NOT_OBSERVED`** — 거부가 사라지고, 남은 것은 그 한 행(빈 audit 표에서 0행 비교)이라는 **정직한 미측정**이다 |
| 봉투 | `NOT_OBSERVED` · `SEC-SCAN-001` MEASURED_PASS · `SEC-RLS-001` NOT_OBSERVED · 사유에 `SEC-DEF-001 (INVALID_RUN)`과 `SEC-VF-001` 부재가 남는다(각각 카드 221 §3의 검토 공백과 카드 233) |

**축 점수는 바뀌지 않는다** — `S11-BE`는 여덟 축의 재계산 PASS를 요구하므로 75 그대로다. 이 카드가 바꾼 것은 **그 축의 RLS report가 admissible해졌다**는 것이다.

## 6. 하지 않은 것

- **census를 손으로 고치지 않았다.** 파일의 모든 줄은 도구가 썼다.
- **dispositions·allowlist를 바꾸지 않았다.** `0059`의 표는 새 disposition을 요구하지 않는다(§3).
- **`inv_runtime_dev`의 dev cluster grant를 바꾸지 않았다.** §3-1의 질문이고 정본 lane에는 영향이 없다.
- **`ctid` identity의 0행 vacuity를 규칙으로 만들지 않았다.** `#322`가 닫은 것과 다른 종류다(§3-1).
- **래칫을 양방향으로 만들지 않았다.** 파서는 PostgreSQL이 아니고, 반대 방향은 live 측정이 본다(§4).

## 7. 다음 첫 행동

1. **Codex**: 이 PR 검토 + §3-1의 두 질문.
2. **Claude**: 카드 233(aggregate lane이 browser artifact를 importer에 넘기게) 계속 — 그 작업은 이 census 위에서 돌아간다.
3. **allowlist owner**: `SEC-DEF-001`의 서명 12 vs 15와 `inv_audit_reader`의 세 disposition — 그 둘이 security 축을 막는 남은 둘이다.
