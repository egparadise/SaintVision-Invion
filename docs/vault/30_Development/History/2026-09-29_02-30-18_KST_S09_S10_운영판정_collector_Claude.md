---
doc_id: "HIST-CLAUDE-S09-S10-OPERATIONAL-COLLECTOR-001"
title: "S09-DB·S10-DB·S10-ST 운영 판정 collector — 측정 가능한 넷만 측정하고 여덟은 이유와 함께 미관측"
version: "1.1.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-29T03:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S09-DB", "S10-DB", "S10-ST"]
tags: ["s09-db", "s10-db", "s10-st", "evidence", "collector", "postgresql", "operational-acceptance", "claude"]
---

# S09-DB·S10-DB·S10-ST 운영 판정 collector (카드 128)

## 범위와 결론

제 판정 기준 v1.2(`6db0899a`, PR **#222** Codex 승인)가 정의한 판정을 실행 가능한 collector로 옮겼다. 12개 관측 중 **입력이 있는 넷만 측정**하고 나머지 여덟은 **이유와 함께 미관측**으로 남는다 — `tools/collect_s09_s10_operational_evidence.py`.

| 관측 | 무엇을 실행하는가 | 사전 등록 임계치 |
|---|---|---|
| **O2** context 재현성 | 표본 bundle마다 `services.context.verify_bundle`로 snapshot에서 hash를 다시 만들어 저장된 hash와 비교 | 표본 ≥ 20, 불일치 0 |
| **O6** 역조회 산술 | **한 REPEATABLE READ session**에서 `models_from_dataset_digest`의 모든 page를 따라가 item 합계 + `unresolvedModelVersions`를 **같은 transaction의 독립 SQL**과 비교 | 표본 ≥ 30, 불일치 0 |
| **O11′** 강제가 설치돼 있는가 | migration `0054`의 **자기 질의**(`CHECK_SHAPE`·`FK_SHAPE`)로 `pg_constraint`를 읽어 `EXPECTED_CHECK`·`EXPECTED_FK`와 대조, 비소유 권한은 `information_schema`에서 읽는다 | shape 정확히 일치 |
| **O14** 측정 신선도 | `verified_at`과 measurement `observed_at`의 차이를 **전수** SQL로 세고 **판정에 쓴 상한을 함께 기록**한다 | 0건 |

측정하지 않은 여덟: **O1·O12**는 두 관측 시점이 필요한 순변화(§5-1), **O8**은 사전 등록 임계치가 없고(§3-2), **O3·O5**(`G-26`)·**O9**(`G-23`)·**O10**(`G-19`·`G-24`)·**O13**(`G-20`·`G-21`)은 외부 전제 대기다. 어느 경로로도 **통과가 되지 않는다** — `validate_evidence`가 O1·O12의 `MEASURED_PASS`, O8의 `MEASURED_PASS`, 외부 다섯의 재분류를 각각 거부한다.

## 골격은 새로 만들지 않고 공용으로 뺐다

`#237`(카드 123, Codex)이 먼저 올라왔으므로 **재구현하지 않았다.** 대신 두 collector가 공유하는 부분을 `tools/operational_evidence.py`로 **추출**하고 `#237`의 collector가 그것을 import하게 고쳤다 — 상태 집합, 판정 재계산, database identity, provenance 결속, 비밀 누출 검사, evidence 쓰기, 종료 코드. 복사본을 하나 더 두면 두 파일이 조용히 갈라진다.

`#237`의 기존 시험 7건은 이 refactor 뒤에도 **그대로 통과**한다(`tests/core/test_s04_s08_operational_evidence.py`, 7 passed).

## base를 바꾼 이유 — 두 제안 base에는 측정 대상이 없다

카드는 `#222` branch 위, 코디네이터 보충은 `#237` branch 위 stack을 제안했다. **둘 다 이 collector를 담을 수 없다.**

| tree | `0054`(CHECK·FK) | `models_from_dataset_digest` |
|---|---|---|
| `#222` branch `6db0899a` | **없음** | **없음** |
| `#237` branch `0d37a610` | **없음** | **없음** |
| 착지 후보 `b91ab72f` | 있음 | 있음 |

O11′는 `0054`의 제약을 읽고 O6은 그 service 함수를 호출하므로, 둘이 없는 tree에서는 **실 PG 시험이 성립하지 않는다.** 그래서 branch를 **착지 후보에서 시작**하고 `#237`(골격)과 `#222`(판정 기준 문서)를 **merge**했다. 두 merge는 해소만 했고(양쪽 보드 줄 모두 보존) 새 편집은 없다.

## 시험

- **PG-free 부정 시험 46건** — `tests/core/test_s09_s10_operational_evidence.py`. 표본이 최소치보다 하나 적으면 통과가 아니고(19 → `NOT_OBSERVED`, 20 → `MEASURED_PASS`), 표본이 커도 불일치 1건이면 실패, 합계가 맞지 않으면 실패, 상한을 기록하지 않으면 실패, 손으로 쓴 verdict·`acceptanceClaim`은 거부, 잘린 표본은 일치로 세지 않고 제외로 센다. **46 passed**(#237의 7건과 합쳐 53 passed).
- **실 PG 시험 12건** — `tests/integration/test_s09_s10_operational_evidence_real_pg.py`(`pytest.mark.postgres`). 모든 SQL과 service 호출이 실 스키마에서 해석되고, **빈 DB는 통과가 아니며**, 가장 중요한 것은 **제약을 떼면 O11′이 `MEASURED_FAIL`이 된다**는 것이다(transaction 안에서 `DROP CONSTRAINT` → 판정 → rollback → 제약이 되돌아왔음을 재확인). 제약이 실제로 있어야 떼어 볼 수 있으므로 **이것은 fake로는 보일 수 없는 축**이다.
- **로컬에서 실 PG 시험을 실행하지 않았다** — 이 PC의 Python은 3.10이고 integration conftest가 `enum.StrEnum`(3.11+)을 쓴다. `#237`의 integration 시험도 같은 이유로 수집되지 않는다. **hosted Core(`run-core`)가 실행 주체**다.

## 경계 — 이 collector가 하지 않는 것

- **운영 데이터를 심지 않는다.** 그래서 O2·O6·O14의 `MEASURED_FAIL` 방향은 PG-free로 고정했고, 실 PG에서는 "문장이 실 스키마에서 성립하고 빈 DB가 통과가 아니다"까지다. 표본이 있는 실 DB에서의 값은 운영 실행이 만든다.
- **HTTP 수준 O6은 범위 밖이다**(§3-3). `excludedBoundaries`에 그대로 적어 두었다.
- **O11′의 "제약이 사라진 세계에서 reader가 fail-closed인가"** 는 시험의 몫이고 production read가 아니므로 역시 `excludedBoundaries`에 있다.
- **migration을 만들지 않았다.** 읽기 전용 collector이고 새 표는 없다.

## v1.1 — 독립 검토 4건 반영 (차단 지적 전부 맞았다)

| # | 무엇이 틀렸나 | 고친 것 |
|---|---|---|
| **F1** [high] | **O6이 한 snapshot 안에서 돌지 않았다.** `collect_database`가 psycopg `conn`과 별도 `engine`의 `Session`을 **각각** 열어, service page walk와 독립 SQL이 **서로 다른 transaction**을 봤다. 통합 시험도 그 분리를 그대로 재현했다. **§3-3의 핵심 계약을 내가 쓰고 내가 깼다** | `SnapshotHandle`을 만들어 **session의 DBAPI connection**(`session.connection().connection.driver_connection`)으로 raw SQL을 돌린다. identity·O11′·O14·O2·O6이 **한 connection·한 transaction**에서 수행된다. 실 PG 시험이 두 경로의 `pg_backend_pid`·`txid_current_snapshot`이 **동일**함을 단언하고, 세 번째 connection의 pid가 **다름**을 함께 단언해 우연한 일치를 배제한다. 다른 connection이 commit한 것이 수집 도중 **보이지 않음**도 단언한다 |
| **F2** [high] | **O11′의 권한 shape가 판정에 참여하지 않았다.** grant를 세기만 하고 어떤 값이어도 `MEASURED_PASS`였다. 게다가 evidence에 source를 `role_table_grants`로 적었는데 실제 질의는 `column_privileges`였다 | grantee **목록**을 읽어 migration `0054`의 `GRANT` 문에서 추출한 **정확한 집합**과 대조한다. **PUBLIC이면 FAIL**, 집합이 다르면 **FAIL**. 이름은 hash로만 기록한다(판정은 "선언된 role 하나, PUBLIC 없음"이고 이름 공개를 요구하지 않는다). source 문자열도 실제 질의로 고쳤다. 실 PG 시험이 **transaction 안에서 PUBLIC에 grant를 추가하면 FAIL**임을 확인하고 rollback으로 되돌린다 |
| **F3** [medium] | **O2가 "무작위 표본"이 아니라 가장 오래된 ID만 봤다.** 앞 20개가 정상이면 뒤쪽 손상을 못 본다 | `ORDER BY md5(seed \|\| bundle_id)`로 바꿨다 — **사전 고정 seed**(`O2_SAMPLE_SEED`)라 재현되면서 표본이 전 구간에 퍼진다. **seed를 결과와 input binding에 기록**하고, seed가 없으면 `MEASURED_FAIL`이다(재현할 수 없는 표본은 측정이 아니다) |
| **F4** | **hosted가 red였다.** ① core/integration에 같은 basename 시험 파일이 있어 Python 3.12·3.14 모두 collection error(실 PG 7건 미실행) ② 새 기준 문서들의 축약 경로가 실제 repo 경로가 아니어서 Docs citation ratchet 실패 | ① 두 쌍 모두 저장소 관례(`*_real_pg.py`)로 rename했다 — **#237의 파일도 같은 충돌**이었으므로 함께 고쳤다. ② **13개 인용을 실제 경로로 확장**했다(축약형 lineage service 경로 → `src/saintvision/services/lineage.py` 처럼 `src/saintvision/` 접두를 붙였다). **#222·#223 두 문서 모두에 있던 결함**이므로 두 문서를 함께 고쳤다 — 이대로 두면 그 두 PR이 착지할 때 같은 곳에서 깨진다 |

PG-free 시험은 **46건**(신규 8건: seed 없는 표본 거부, 표본 순서 계약, PUBLIC grant FAIL, 추가 grantee FAIL, grantee 집합 일치 시에만 PASS, migration에서 읽은 기대 grantee, 그리고 **connection 분리를 되살리면 실패하는 구조 시험**). `#237`의 7건을 포함해 **53 passed**.

## 다음 첫 행동

Codex 검토(계약·비밀 경계·공용 모듈 추출의 타당성). 그리고 `#237`·`#222`가 착지하면 이 branch는 그 위에서 정리된다.
