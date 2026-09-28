---
doc_id: "CLAUDE-DONE-CRITERIA-S09DB-S10DB-S10ST-001"
title: "S09-DB·S10-DB·S10-ST 운영 판정 기준 v1.1 — 코드가 이미 강제하는 것을 다시 세지 않고, 12개 관측을 '지금 가능 4 · 두 시점 순변화 2 · 임계치 결정 대기 1 · 외부 전제 5'로 분류하고 O6을 service 수준 판정으로 고정한다 (카드 106, docs-only)"
version: "1.2.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T23:47:27+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "9f1c2be4"
task_ids: ["S09-DB", "S10-DB", "S10-ST"]
tags: ["done-criteria", "s09-db", "s10-db", "s10-st", "operational-acceptance", "claude"]
---

# S09-DB·S10-DB·S10-ST 운영 판정 기준

48 task 진행률 재채점(PR **#220**, `docs/vault/30_Development/2026-09-28 48 task 진행률 재채점.md`) §5가 세 task를 "**코드는 있고 '무엇을 보면 done인가'가 없다**"로 남겼다. 이 문서가 그 빈자리를 채운다. 카드 106이고 **docs-only**다 — 코드·migration 변경 0, 측정 실행 0.

분석 tree는 **`9f1c2be4`**(`origin/coord/train-ci-2207`)이고, 세 task의 구현이 전부 그 tree에 있다. 인용한 경로·줄은 그 tree에서 `git show`로 확인했다.

재채점 문서는 **wiki link가 아니라 평문(PR 번호·파일 경로)으로** 인용한다 — 그 문서가 아직 병합 대기이므로, wiki link로 두면 그것이 없는 branch에서 `check_docs`가 깨진다.

## 0. 이 문서를 지배하는 규칙 하나

**코드가 이미 강제하는 것을 done 기준으로 다시 세지 않는다.**

그것은 **시험이 지키는 불변식**이고 병합 시점에 이미 참이다. done 기준에 다시 적으면 **이미 가진 것을 두 번 세는 것**이고, 09-18 재채점이 "시험 수를 점수로 더하지 않는다"고 한 것과 같은 오류다.

그래서 관측 항목은 **코드가 보장할 수 없는 것**만이다.

| 종류 | 왜 코드가 보장할 수 없는가 |
|---|---|
| **운영 환경에서만 드러나는 것** | 실제 데이터량에서의 질의 계획, 실제 provider가 만든 결과, 실제 GC 뒤의 바이트 |
| **DB 밖에서 일어나는 것** | 제약을 **떼어낸 뒤**의 조작, 운영자의 수동 SQL, 배포 drift |
| **사람·자산이 있어야 성립하는 것** | 측정하는 trusted worker의 배포, release manifest 인수, provider credential |

**v1.1에서 이 규칙을 더 엄격히 적용해 두 항목을 관측에서 빼고 §1로 옮겼다**(v1.0의 O4·O7). 자세한 것은 §7이다.

## 1. 이미 강제되는 것 (다시 세지 않을 목록)

**아래는 done 기준이 아니다.** 이미 참이고, 시험·스키마·route가 지키며, 이 문서의 관측 대상이 아니다.

| task | 이미 강제되는 불변식 | 출처 |
|---|---|---|
| S09-DB | **빈 suite는 pass가 아니다** — `total_cases > 0 and recorded >= total_cases and passed == total_cases and violations == 0`. 모든 case가 error인 run이 green이 되지 않는다 | `services/evaluation.py:223` `def gate_passed` |
| S09-DB | sealed `run_records`·`run_record_artifacts`는 append-only(app role에 UPDATE·DELETE 없음) | `db/models/__init__.py:233` `APPEND_ONLY_TABLES` |
| S09-DB | **run identity를 서비스가 정한다** — 호출자가 `adapter`·`contractVersion`·`modelPinned`를 보내면 경계에서 **422로 거부**된다 (v1.0의 O4) | `api/v1/eval_runs.py` `_reject_service_owned_versions` |
| S10-DB | **잘린 답이 완전한 답처럼 보이지 않는다** — `truncated`가 있으면 `complete`는 false다 (v1.0의 O7) | `services/lineage.py:672` `_bounded`, `:699` |
| S10-ST | **digest만으로 `verified_at`을 세울 수 없다** — kernel accept 경로만 쓰는 measurement가 필요하고 digest가 measurement·row 양쪽과 일치해야 한다 | `services/lineage.py:299` `def verify_model_version` |
| S10-ST | **DB가 반쪽 verified를 거부한다** — `CHECK ((verified_at IS NULL) = (verified_measurement_id IS NULL))`가 **validated** 상태로 설치된다 | `migrations/versions/0054_model_version_measurements.py` `CHECK`·`EXPECTED_CHECK`(세 번째 요소 `True` = `convalidated`) |
| S10-ST | retention pin은 **늘리기만** 한다 | `services/lineage.py:353` `def pin_retention` |
| S10-ST | **측정 신선도를 route가 거부한다** — `Settings.model_measurement_max_age_seconds`(기본 86,400초, 상한 검증) | `config.py:90`·`:114`, `api/v1/model_verify.py:402` `_require_fresh(...)` |

## 2. S09-DB — 불변 Context·RunRecord·eval

| # | 관측값 | 계측 방법 | 사전 등록 임계치 | 분류 |
|---|---|---|---|---|
| **O1** | **두 관측 시점 사이 sealed row의 순변화** — 시작 시점에 존재한 row **cohort를 고정**하고, 그 cohort의 `(record_id, 전 컬럼)` digest가 종료 시점에 같은가 | 두 시점의 cohort digest 비교 + 두 시점의 app role 권한 snapshot(`information_schema.role_table_grants`에서 읽는다) | 순변화 **0**, 두 시점 모두 app role에 UPDATE·DELETE **없음** | **순변화만** (§5) |
| **O2** | **context 재현성** — sealed run의 context bundle을 `context_snapshots`에서 다시 만들면 digest가 같은가 | 무작위 표본에 대해 재구성 digest와 기록된 digest 비교 | 표본 **≥ 20**, 불일치 **0** | **지금 가능** |
| **O3** | **gate가 실제 모델 결과에서도 정직한가** — `passed_gate = true`인 run 중 `total_cases == 0`이거나 `recorded < total_cases`인 것 | 창 안의 **모든** `eval_runs` 행을 집계(표본이 아니다) | 위반 **0**, 그리고 `total_cases > 0`인 **실제 provider run ≥ 1** | 외부 대기 `G-26` |
| **O5** | **provider 장애가 pass로 기록되지 않는다** | 장애 구간의 run을 `passed_gate`·`violations`로 집계 | 장애 구간의 `passed_gate = true` **0건** | 외부 대기 `G-26` |

**증거 artefact**: `eval_runs`·`eval_results` 집계 + 두 시점의 권한 snapshot + 표본 20건의 digest 대조표. **case 내용과 model 출력은 넣지 않는다**(W5 감사 결정과 같은 이유 — eval 표는 널리 읽히고 거기 새어 나온 비밀도 비밀이다).

## 3. S10-DB — Dataset/commit/image/model lineage

| # | 관측값 | 계측 방법 | 사전 등록 임계치 | 분류 |
|---|---|---|---|---|
| **O6** | **역조회 산술 일치** — **모든 page를 합산한** item 수 + `unresolvedModelVersions`가 실제 model version 수와 같은가 | **§3-1의 규칙대로** 측정한다 | 표본 **≥ 30**, 불일치 **0** | **지금 가능** |
| **O8** | **index가 실제 데이터량에서 쓰이는가** | `EXPLAIN (ANALYZE, BUFFERS)` | **미정 — §3-2** | **임계치 결정 대기** |
| **O9** | **배포 digest 결속** — released model version의 digest와 실제 배포된 artefact digest | release manifest ↔ `model_versions.content_sha256` 대조 | 불일치 **0** | 외부 대기 `G-23` |

### 3-1. O6은 pagination 계약에 맞춰 정의해야 한다 (v1.1 정정)

v1.0은 "`len(items) + unresolved` == SQL count"라고 적었다. **그 정의는 정상 제품을 FAIL시킨다.**

`services/lineage.py:895-923`을 읽으면 두 수의 범위가 다르다.

- `unresolvedModelVersions`는 **전체 `wanted` 집합** 기준이다 — `len(wanted) - resolvable`이고, 주석이 "**page 1과 page 4에서 같은 뜻이도록** 전체 집합에서 센다"고 적는다.
- `items`는 **현재 page**다 — `statement.limit(limit + 1)`로 잘라 `build_page`가 만든다.

그래서 resolvable이 100이고 `limit=50`이면 첫 응답은 `len(items)=50`·`unresolved=0`인데 SQL count는 100이라 **불일치가 정상**이다.

**v1.1의 규칙**:

1. `nextCursor`가 없어질 때까지 **모든 page를 따라가 item을 합산**한다.
2. `unresolvedModelVersions`는 **한 번만** 더한다(page마다 같은 값이 온다).
3. 비교는 **같은 snapshot 안에서** 한다. 단, **HTTP route를 순회하는 방식으로는 그것이 불가능하다** — v1.1의 문구를 v1.2에서 고쳤다(§3-3).
4. **`datasetVersionIds`가 200에서 잘린 응답은 표본에서 제외**한다. 그 경우 `wanted` 자체가 잘려 있어 "실제 수"의 정의가 달라지므로, 잘린 표본은 **§1의 `truncated`→`complete=false` 불변식**이 담당하고 O6은 잘리지 않은 표본만 본다.

### 3-3. O6은 **service 수준 판정**이다 — HTTP 순회로는 한 snapshot을 만들 수 없다 (v1.2 정정)

v1.1은 "`REPEATABLE READ` transaction에서 **page 순회와 독립 SQL count를 함께** 수행한다"고 적었다. **현재 제품 경계로는 실행할 수 없다.**

`api/deps.py:61` `def get_session`은 **요청마다** `make_session_factory(...)` → `factory()` → `session.begin()` → `tenant_scope(...)`를 열고 그 session을 `yield`한다. `api/v1/lineage_query.py:227`의 route는 그것을 `Depends(get_session)`로 받는다. 그러므로 **cursor의 다음 HTTP 요청은 다른 transaction**이고, 외부 collector의 SQL을 그 snapshot에 참여시킬 **snapshot token이나 API가 없다.** 없는 계약을 있다고 쓴 것이 잘못이었다.

**O6을 service 수준 판정으로 고정한다.**

| | |
|---|---|
| **무엇을 측정하는가** | collector가 **한 `REPEATABLE READ` session**에서 `services.lineage.models_from_dataset_digest(..., cursor=...)`를 모든 page에 대해 호출하고, **같은 transaction의** 독립 SQL count와 비교한다 |
| **무엇을 측정하지 않는가** | HTTP route의 응답이 아니다. 이것은 **service + serializer** 판정이고, **route wiring은 기존 route 시험**(`tests/core/test_lineage_query_routes.py`)이 담당한다 |
| 왜 이 분리가 정직한가 | 한 snapshot이 필요한 것은 **산술**이고, 그 산술은 service 함수가 만든다. route는 그 결과를 직렬화할 뿐이며 **직렬화의 정확성은 다른 질문**이다 |

**HTTP 수준 판정을 원한다면** 다른 절차가 필요하다 — write를 **quiesce한 측정 창**에서 모든 page와 독립 SQL을 수행하고, 창 **전후의 high-water/count가 불변**임을 함께 증명해야 한다. 그것은 운영 창을 요구하므로 "지금 가능"이 아니고, 이 문서는 그 길을 택하지 않았다.

### 3-2. O8은 "지금 가능"이 아니다 — 임계치가 없다 (v1.1 정정)

v1.0은 O8을 "지금 가능"으로 두고 임계치를 `seq scan 0`으로 적었다. **둘 다 틀렸다.**

PostgreSQL은 데이터량·selectivity·통계에 따라 **seq scan을 올바르게 고를 수 있다.** 그러면 `seq scan 0`은 안정적인 합격 계약이 아니고, 정상 planner 판단을 FAIL로 만든다. §7도 "운영 규모" 수치가 미정이라고 인정하고 있었으므로 "지금 가능"이라는 분류와도 모순이었다.

**O8을 임계치 결정 대기로 옮긴다.** 측정 전에 다음을 **결과를 보기 전에** 고정해야 한다.

| 정해야 하는 것 | 왜 |
|---|---|
| 최소 row cardinality | 그 아래에서는 seq scan이 옳다 |
| digest selectivity | 선택도가 낮으면 index가 무의미하다 |
| `ANALYZE` 상태 | 통계가 낡으면 계획이 데이터를 반영하지 않는다 |
| 허용 plan node 집합 | "index scan"만인지, bitmap heap scan도 되는지 |
| latency·buffer 임계치 | 계획이 맞아도 느릴 수 있다 |

정해지면 이 표를 채우고 분류를 "지금 가능"으로 옮긴다. 그 전에는 **done 근거로 쓰지 않는다.**

## 4. S10-ST — Model immutable version·보존 pin

| # | 관측값 | 계측 방법 | 사전 등록 임계치 | 분류 |
|---|---|---|---|---|
| **O10** | **측정하는 trusted worker가 실제로 존재하고 돈다** | `model_versions.verified_measurement_id`가 non-null인 행과 `inv.model_version_measurements`의 대응 행 대조. worker의 **공개** identity를 함께 기록 | **≥ 1**, measurement의 `sha256`이 row·요청 digest와 **3자 일치** | 외부 대기 `G-19`·`G-24` |
| **O11′** | **강제가 운영 DB에 아직 설치돼 있는가** — §4-1 | §4-1 | §4-1 | **지금 가능** |
| **O12** | **두 관측 시점 사이 `retention_pinned_until`의 순변화** — 시작 cohort를 고정하고 앞당겨진 행이 있는가 | 두 시점의 `(model_version_id, retention_pinned_until)` 비교 | 앞당겨진 행 **0**(순변화 기준) | **순변화만** (§5) |
| **O13** | **pin이 실제 보존을 만든다** — pin된 version의 바이트가 GC 1주기 뒤에도 존재하는가 | GC **실행 전후**에 object store에서 존재·digest 확인 | 손실 **0**, digest 불일치 **0** | 외부 대기 `G-20`·`G-21` |
| **O14** | **저장된 행이 신선한 측정으로만 verified다** — route는 이미 거부하므로(§1) 대상은 **제약 밖에서 들어온 행**이다: `verified_at`과 measurement `observed_at`의 차이가 `model_measurement_max_age_seconds`를 넘는 행 | 전수 SQL(두 시각 차이). **설정값도 함께 기록**해 나중에 상한을 바꿔 소급 판정하지 못하게 한다 | **0건** | **지금 가능** |

### 4-1. O11을 O11′로 바꾼 이유 — v1.0의 서술이 사실과 반대였다 (v1.1 정정)

v1.0은 O11을 "`verified_at`이 있으나 `verified_measurement_id`가 없는 행 = 0"으로 두고 "**DB CHECK가 막지만 out-of-band SQL은 막지 못하므로 관측 대상이다**"라고 적었다. **그 문장은 반대다.**

`0054_model_version_measurements.py`가 `CHECK ((verified_at IS NULL) = (verified_measurement_id IS NULL))`를 설치하고, 같은 migration의 `EXPECTED_CHECK`가 `convalidated = True`를 단언한다. 즉 **직접 SQL이어도 DB가 즉시 거부한다.** 그러므로 v1.0의 O11은 관측이 아니라 **이미 강제된 불변식을 다시 센 것**이고, T6의 "직접 SQL로 `verified_at`만 세운다"는 **실행 불가능한 되살림 시험**이었다.

**대신 코드가 보장할 수 없는 것을 관측한다 — 그 강제가 아직 설치돼 있는가.** 제약은 떼어낼 수 있고, 권한은 바뀔 수 있고, 배포는 drift한다.

| 관측값 | 계측 방법 | 사전 등록 임계치 |
|---|---|---|
| CHECK의 **존재·정의·validated 상태** | `pg_constraint`를 `0054`의 `CHECK_SHAPE` 질의로 읽어 `EXPECTED_CHECK`와 대조 | `(contype, 정의, convalidated)`가 **정확히 일치** |
| FK의 존재·정의·validated | 같은 migration의 `FK_SHAPE` | 일치 |
| 비소유 role의 권한 shape | `information_schema`에서 읽는다(하드코딩하지 않는다) | `0054`가 기대하는 집합과 일치 |
| **제약을 훼손한 fixture에서 invalid row가 드러나는가** | 시험 DB에서 CHECK를 떼고 반쪽 row를 넣은 뒤 **읽기가 fail-closed**하는지 확인 | 그 row가 `RECORDED`/정상으로 나오면 실패 |

마지막 줄이 O11′의 핵심이다 — 제약이 사라진 세계에서 **reader가 스스로 막는지**를 보고, 그것은 제약이 있는 동안에는 관측할 수 없다.

**증거 artefact**: 제약·권한 shape 대조표 + measurement 3자 일치표 + GC 전후 대조 + worker 공개 identity(**private key·token·DSN·원문 hostname은 넣지 않는다**).

## 5. 분류와 개수

v1.0은 "14개 중 8개 지금 가능"이라고 적었으나 실제 열에는 **9개와 5개**가 있었고, 그중 둘(O4·O7)은 route·schema가 강제하는 불변식이었다. v1.1의 정확한 분류다.

| 분류 | 관측 | 개수 |
|---|---|---:|
| **지금 측정 가능** | O2 · O6 · O11′ · O14 | **4** |
| **두 시점 순변화만** (done 근거로 쓰지 않는다 — §5-1) | O1 · O12 | **2** |
| **임계치 결정 대기** (§3-2) | O8 | **1** |
| **외부 전제 대기** | O3·O5(`G-26`) · O9(`G-23`) · O10(`G-19`·`G-24`) · O13(`G-20`·`G-21`) | **5** |
| | **합계** | **12** |

v1.0의 O4·O7은 §1로 옮겼으므로 14 → 12다.

**세 task의 75 → 100 사이에서 우리 몫은 "지금 가능" 4개의 실행과 기록**이고, 그것을 다 해도 **100은 되지 않는다** — 필수 운영 인수가 범위 안에 있기 때문이고(`G-19`·`G-20`·`G-21`·`G-23`·`G-26`), 그 사실을 숨기지 않는다.

### 5-1. O1·O12는 "동안 한 번도"를 증명하지 못한다 (v1.1 정정)

v1.0은 시작·종료 두 snapshot으로 "운영 창 **동안** out-of-band 수정 0건"과 "pin이 줄어든 적 없음"을 주장했다. **두 장의 사진은 그것을 증명하지 못한다** — 중간에 바꿨다가 되돌리거나, pin을 낮췄다가 복구하면 두 digest·두 시각이 같아 **PASS한다.**

v1.1이 한 것:

- 주장을 **"두 관측 시점 사이 순변화 0"** 으로 낮췄다. 그것이 두 snapshot으로 말할 수 있는 전부다.
- 시작 시점의 **row cohort를 고정**해, 창 중에 생긴 신규 row가 불일치로 보이는 오탐을 없앴다.
- **done 근거로 쓰지 않는다.** "동안 한 번도"를 말하려면 **연속 증거**가 필요하다 — append-only audit, temporal history table, 논리 변경 로그 중 하나의 seam이다. **그 seam은 지금 없다.**

seam을 만드는 것은 이 카드의 범위가 아니고 §7의 미해결이다. 그것이 생기면 O1·O12는 "지금 가능"으로 올라간다.

## 6. 되돌리면 실패해야 하는 시험 (관측을 정직하게 유지하는 장치)

구현 카드가 이 목록을 계약으로 받는다.

| # | 무엇을 고정하는가 | 되돌릴 때 실패하는 방식 |
|---|---|---|
| T1 | O1의 권한 snapshot이 **실제 권한**을 읽는다 | app role에 UPDATE를 주면 비교가 실패해야 한다. "권한 없음"을 하드코딩하면 실패하지 않으므로 `information_schema`에서 읽는다 |
| T2 | O3의 집계가 **모든** `eval_runs` 행을 본다 | 표본만 보도록 바꾸면 실패. 분모가 전수임을 단언한다 |
| T3 | O6의 SQL 카운트가 **service 함수와 독립 경로**다 | `models_from_dataset_digest`가 쓰는 같은 질의를 재사용하면 실패 — 같은 버그가 양쪽에 있으면 일치가 증명이 아니다 |
| T4 | O6이 **모든 page를 합산**하고 **한 `REPEATABLE READ` service session**에서 비교한다 | 첫 page만 세면 실패(§3-1). HTTP route를 순회해 "같은 snapshot"이라 주장하면 실패 — 요청마다 transaction이 새로 열린다(§3-3) |
| T5 | O10의 3자 일치가 **measurement 행에서** 온다 | 요청 digest만 비교하면 실패 |
| **T6′** | O11′이 **제약의 정의·validated 상태**를 읽고, **제약을 뗀 fixture에서 reader가 fail-closed**한다 | shape 비교를 이름 존재 확인으로 바꾸면 실패. 제약을 뗀 fixture의 반쪽 row가 정상 응답으로 나오면 실패. (v1.0의 T6은 **validated CHECK가 즉시 거부**하므로 실행 자체가 불가능했다 — §4-1) |
| T7 | O13이 **GC를 실제로 돌린 뒤** 본다 | GC 없이 존재만 확인하면 실패 |
| **T8** | O1·O12가 **"동안 한 번도"라고 주장하지 않는다** | 판정 문구가 "순변화"를 넘어서면 실패(§5-1). 연속 증거 seam 없이 done 근거로 쓰면 실패 |

## 7. 경계 · 미해결

- **v1.1에서 다섯 지점을 고쳤다.** 전부 "방향은 맞지만 그 정의로는 실제 판정이 성립하지 않는" 종류였다.
  1. **O6**이 pagination 계약과 어긋나 **정상 제품을 FAIL**시켰다(§3-1). 두 수의 범위가 다른 것을 읽지 않고 산술을 적었다.
  2. **O11/T6**이 `0054`의 **validated CHECK와 모순**이어서 실행 불가능한 시험이었고, "DB는 막지만 out-of-band는 못 막는다"는 서술이 **반대**였다(§4-1). O11′로 바꿨다.
  3. **O1·O12**가 두 snapshot으로 "동안 한 번도"를 주장했다 — 바꿨다 되돌리면 통과한다(§5-1). 주장을 순변화로 낮추고 done 근거에서 뺐다.
  4. **O8**이 임계치 없이 "지금 가능"이었고 `seq scan 0`은 안정적 계약이 아니다(§3-2). 결정 대기로 옮겼다.
  5. **개수와 분류가 서로 맞지 않았고**(8이라 적고 9+5를 열거) O4·O7은 이미 강제되는 불변식이었다(§5). §1로 옮기고 12로 맞췄다.
- **v1.2에서 한 곳을 더 고쳤다** — O6의 "한 snapshot" 절차가 **실행 불가능**했다(§3-3). `get_session`이 요청마다 transaction을 열므로 HTTP 순회로는 snapshot을 공유할 수 없고, **없는 계약을 있다고 쓴 것**이다. O6을 service 수준 판정으로 고정하고 route wiring은 기존 route 시험에 분리했다.
- **연속 증거 seam이 없다**(§5-1). append-only audit·temporal history·논리 변경 로그 중 무엇을 둘지는 이 카드의 범위가 아니다.
- **O8의 다섯 임계치가 미정**이다(§3-2). 파일럿 데이터량이 정해지면 채운다.
- **O13의 GC 주체·주기가 미정**이다(`G-20`).
- **`CHECKLIST`·suite 계약이 올라갈 때의 비교 규칙**은 별 카드다(PR #218 §6과 같은 미해결).
- **이 문서는 판정을 내리지 않는다.** 세 task의 현재 점수는 재채점(PR **#220**) v1.3의 **75**이고, 이 문서는 그 75를 올리는 데 **무엇이 필요한지**만 정한다. registry의 세 task는 모두 `planned`이며 이 문서가 상태를 올리지 않는다.
- 실행하지 않았다: 로컬 실 PG·Docker·전체 suite. 이 문서의 실측은 `git show`·`git grep -n -F`로 읽은 코드뿐이고, **관측은 하나도 수행하지 않았다.**
