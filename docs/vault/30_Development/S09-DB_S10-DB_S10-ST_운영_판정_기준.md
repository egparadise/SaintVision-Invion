---
doc_id: "CLAUDE-DONE-CRITERIA-S09DB-S10DB-S10ST-001"
title: "S09-DB·S10-DB·S10-ST 운영 판정 기준 — 코드가 이미 강제하는 것을 done 기준으로 다시 세지 않고, 코드가 보장할 수 없는 것만 관측·계측·사전 등록 임계치로 고정한다 (카드 106, docs-only)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T23:23:05+09:00"
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

세 task의 코드에는 이미 "정직하게 실패하는" 장치가 들어 있다 — eval gate의 `total_cases > 0`, verify의 measurement 요구, retention pin의 단조성, lineage의 `truncated`·`unresolved` 카운트. 그것들은 **시험이 지키는 불변식**이고, 병합 시점에 이미 참이다. 그것을 done 기준에 다시 적으면 **이미 가진 것을 두 번 세는 것**이고, 09-18 재채점이 "시험 수를 점수로 더하지 않는다"고 한 것과 같은 오류다.

그래서 이 문서의 관측 항목은 **코드가 보장할 수 없는 것**만이다. 세 종류다.

| 종류 | 왜 코드가 보장할 수 없는가 |
|---|---|
| **운영 환경에서만 드러나는 것** | 실제 데이터량에서의 질의 계획, 실제 provider가 만든 결과, 실제 GC 뒤의 바이트 |
| **DB 밖에서 일어나는 것** | out-of-band SQL, 운영자의 수동 조작, 외부 저장소의 보존 |
| **사람·자산이 있어야 성립하는 것** | 측정하는 trusted worker의 배포, release manifest 인수, provider credential |

각 항목은 **관측값 · 계측 방법 · 사전 등록 임계치 · 증거 artefact · 외부 전제**를 갖는다. 임계치는 **결과를 보기 전에** 여기 고정한다.

## 1. 세 task에서 코드가 이미 강제하는 것 (다시 세지 않을 목록)

먼저 명시한다 — 아래는 **done 기준이 아니다.** 이미 참이고, 시험이 지키며, 이 문서의 관측 대상이 아니다.

| task | 이미 강제되는 불변식 | 출처 |
|---|---|---|
| S09-DB | **빈 suite는 pass가 아니다.** `total_cases > 0 and recorded >= total_cases and passed == total_cases and violations == 0` | `services/evaluation.py:223` `def gate_passed` |
| S09-DB | 모든 case가 error인 run이 green이 되지 않는다 — 그 실패 방식이 docstring에 기록돼 있다("**가장 나쁜 방식**: 평가가 일어나지 않은 바로 그때 green이 된다") | 같은 함수 docstring |
| S09-DB | sealed `run_records`·`run_record_artifacts`는 append-only다(app role에 UPDATE·DELETE 없음) | `db/models/__init__.py` `APPEND_ONLY_TABLES` |
| S10-DB | 잘린 답이 완전한 답처럼 보이지 않는다 — `truncated`·`unresolved` 카운트와 `complete` | `services/lineage.py:672` `_bounded`, `:699` |
| S10-ST | **digest만으로 `verified_at`을 세울 수 없다.** kernel accept 경로만 쓰는 `inv.model_version_measurements`의 measurement가 필요하고, digest가 measurement와 row 양쪽과 일치해야 하며, `verified_at`·`verified_measurement_id`는 함께 세워진다(DB CHECK가 한쪽만인 것을 거부) | `services/lineage.py:299` `def verify_model_version` (설계 `#209` v1.1 §4) |
| S10-ST | retention pin은 **늘리기만** 한다 — 나중의 약한 주장이 앞선 강한 주장을 풀지 못한다 | `services/lineage.py:353` `def pin_retention` |
| S10-ST | **측정 신선도를 route가 이미 강제한다** — `Settings.model_measurement_max_age_seconds`(기본 86,400초, 상한 검증 있음)를 넘긴 measurement는 거부된다 | `config.py:90`·`:114`, `api/v1/model_verify.py:402` `_require_fresh(...)` |

**이 목록이 곧 "왜 세 task가 75점인가"의 절반이다.** 나머지 절반이 아래다.

## 2. S09-DB — 불변 Context·RunRecord·eval

### 2-1. 관측 항목

| # | 관측값 | 계측 방법 | 사전 등록 임계치 |
|---|---|---|---|
| **O1** | **out-of-band 수정 0** — 운영 창 동안 sealed `run_records`·`run_record_artifacts`의 행이 바뀐 건수 | 창 시작·종료 시점의 `(record_id, 전 컬럼) ` digest를 비교. app role 권한 snapshot(`information_schema.role_table_grants`)도 함께 기록 | **0건**. app role에 UPDATE·DELETE 권한이 **없음**이 두 시점 모두 |
| **O2** | **context 재현성** — sealed run의 context bundle을 `context_snapshots`에서 다시 만들었을 때 digest 일치 | 무작위 표본 20건 이상에 대해 재구성 digest와 기록된 digest 비교 | 표본 **≥ 20**, 불일치 **0** |
| **O3** | **gate가 실제 모델 결과에서도 정직한가** — `passed_gate = true`인 run 중 `total_cases == 0`이거나 `recorded < total_cases`인 것 | 창 안의 모든 `eval_runs` 행을 집계 | 위반 **0**. 그리고 `total_cases > 0`인 **실제 provider run이 ≥ 1** 존재 |
| **O4** | **run identity를 서비스가 정한다** — 호출자가 `adapter`·`contractVersion`·`modelPinned`를 주려 한 요청의 거부율 | route 시험과 운영 audit(`eval_run.execute` allow 행의 `componentVersions` 출처) | 거부 **100%**, 기록된 값이 서비스 산출과 일치 **100%** |
| **O5** | **provider 장애가 pass로 기록되지 않는다** — 장애 구간의 run 판정 | 장애 주입 또는 실제 장애 구간의 run을 `passed_gate`·`violations`로 집계 | 장애 구간의 `passed_gate = true` **0건** |

### 2-2. 증거 artefact

`eval_runs`·`eval_results` 집계 CSV + 두 시점의 권한 snapshot + 표본 20건의 digest 대조표. **case 내용과 model 출력은 넣지 않는다**(W5 감사 결정과 같은 이유 — eval 표는 널리 읽히고 거기 새어 나온 비밀도 비밀이다).

### 2-3. 외부 전제

**`G-26`** — AC-09 운영 인수: 실제 모델·도구 adapter 실행 환경과 provider credential. **O3의 "실제 provider run ≥ 1"과 O5는 그것 없이 성립하지 않는다.** O1·O2·O4는 **지금 우리 쪽에서 측정 가능**하다.

## 3. S10-DB — Dataset/commit/image/model lineage

### 3-1. 관측 항목

| # | 관측값 | 계측 방법 | 사전 등록 임계치 |
|---|---|---|---|
| **O6** | **역조회 산술 일치** — digest 하나에 대해 `len(items) + unresolved 합`이 그 digest를 가진 실제 model version 수와 같은가 | 운영 데이터에서 digest 표본 30개 이상을 뽑아 route 응답과 직접 SQL 카운트를 비교 | 표본 **≥ 30**, 불일치 **0** |
| **O7** | **잘림이 숨지 않는다** — `truncated`가 비어 있지 않은 응답에서 `complete = false`인 비율 | 경계값(200)을 넘는 digest를 포함한 표본 | **100%** (`truncated` 있으면 `complete=false`) |
| **O8** | **index가 실제 데이터량에서 쓰인다** — digest 역조회 질의의 계획 | 운영 규모 행 수에서 `EXPLAIN (ANALYZE, BUFFERS)` | `dataset_versions(tenant_id, content_sha256)`에 **index scan**, **seq scan 0**. `#174`가 이 지점의 반례다 |
| **O9** | **배포 digest 결속** — released model version의 digest와 실제 배포된 artefact digest | release manifest의 digest와 `model_versions.content_sha256` 대조 | 불일치 **0** |

### 3-2. 증거 artefact

표본 30개의 `(digest, route 응답 카운트, SQL 카운트)` 표 + `EXPLAIN` 원문 + release manifest ↔ DB digest 대조표.

### 3-3. 외부 전제

- **O6·O7·O8은 외부 전제가 없다** — 운영 규모의 데이터만 있으면 **우리 쪽에서 끝낼 수 있다.** O8은 "운영 규모"가 필요하므로 파일럿 데이터량이 전제다.
- **O9는 `G-23`**(Release manifest·사용자 인수)를 기다린다.

## 4. S10-ST — Model immutable version·보존 pin

### 4-1. 관측 항목

| # | 관측값 | 계측 방법 | 사전 등록 임계치 |
|---|---|---|---|
| **O10** | **측정하는 trusted worker가 실제로 존재하고 돈다** — kernel accept 경로가 쓴 measurement로 `verified_at`이 세워진 model version 수 | `model_versions.verified_measurement_id`가 non-null인 행과 `inv.model_version_measurements`의 대응 행을 대조. worker의 공개 identity를 함께 기록 | **≥ 1**, 그리고 그 measurement의 `sha256`이 row·요청 digest와 **3자 일치** |
| **O11** | **digest만으로 verified가 된 행 0** — `verified_at`이 있으나 `verified_measurement_id`가 없는 행 | 전수 SQL | **0**. DB CHECK가 막지만, out-of-band SQL은 막지 못하므로 **관측 대상이다** |
| **O12** | **보존 pin이 줄어든 적 없다** — 창 동안 `retention_pinned_until`이 앞당겨진 건수 | 창 시작·종료의 `(model_version_id, retention_pinned_until)` 비교 | **0건**. 코드는 늘리기만 하지만 out-of-band 조작은 여기서만 보인다 |
| **O13** | **pin이 실제 보존을 만든다** — pin된 version의 바이트가 GC 1주기 뒤에도 존재하는가 | GC 실행 전후에 object store에서 존재·digest 확인 | 손실 **0**, digest 불일치 **0** |
| **O14** | **저장된 행이 신선한 측정으로만 verified다** — route는 이미 거부하므로(§1) 관측 대상은 **out-of-band로 들어온 행**이다: `verified_at`과 대응 measurement의 `observed_at` 차이가 `model_measurement_max_age_seconds`를 넘는 행 | 전수 SQL(두 시각의 차이 계산). 설정값도 함께 기록해 나중에 상한을 바꿔 소급 판정하지 못하게 한다 | **0건** |

### 4-2. 증거 artefact

`verified_*` 전수 SQL 결과 + measurement 3자 일치표 + GC 전후 object store 존재·digest 대조 + worker의 공개 identity 기록(**private key·token·DSN·원문 hostname은 넣지 않는다**).

### 4-3. 외부 전제

- **O11·O12·O14는 지금 측정 가능**하다(DB와 route만 필요).
- **O10은 trusted worker의 배포**가 필요하다 — 실 Node에서 weight를 읽고 해시해 kernel accept 경로로 보내는 주체다. `G-19`(물리 PC 5대)·`G-24`(실 Node→CP 전송)에 걸린다.
- **O13은 `G-20`**(storage 제품 값: contribution 루트·storage-policy·아카이브 대상)과 **`G-21`**(verified off-site backup)에 걸린다. 보존을 말하려면 어디에 보존하는지가 정해져야 한다.

## 5. 지금 할 수 있는 것과 기다려야 하는 것

이 문서의 결론이다. 14개 관측 중 **8개는 외부 전제 없이 측정 가능**하다.

| 지금 가능 (8) | 외부 전제 대기 (6) |
|---|---|
| O1 out-of-band 수정 0 | O3 실제 provider run (`G-26`) |
| O2 context 재현성 | O5 provider 장애 구간 (`G-26`) |
| O4 run identity 출처 | O9 배포 digest 결속 (`G-23`) |
| O6 역조회 산술 일치 | O10 trusted worker 배포 (`G-19`·`G-24`) |
| O7 잘림 표시 | O13 pin ↔ 실제 보존 (`G-20`·`G-21`) |
| O8 index 실사용 (운영 규모 데이터 필요) | — |
| O11 digest-only verified 0 | |
| O12 pin 단조성 | |
| O14 측정 신선도 | |

즉 **세 task의 75 → 100 사이에서 우리 몫은 8개 관측의 실행과 기록**이고, 나머지 6개는 `G-19`·`G-20`·`G-21`·`G-23`·`G-26` 중 하나가 풀려야 시작된다. 8개를 다 채워도 **100은 되지 않는다** — 필수 운영 인수가 범위 안에 있기 때문이고, 그 사실을 여기서 숨기지 않는다.

## 6. 되돌리면 실패해야 하는 시험 (관측을 정직하게 유지하는 장치)

관측 자체가 거짓이 되는 경로를 막는다. 구현 카드가 이 목록을 계약으로 받는다.

| # | 무엇을 고정하는가 | 되돌릴 때 실패하는 방식 |
|---|---|---|
| T1 | O1의 권한 snapshot이 **실제 권한**을 읽는다 | app role에 UPDATE를 주면 snapshot 비교가 실패해야 한다. 하드코딩된 "권한 없음"이면 실패하지 않으므로, snapshot은 `information_schema`에서 읽는다 |
| T2 | O3의 집계가 **모든** `eval_runs` 행을 본다 | 표본만 보도록 바꾸면 실패. 분모가 전수임을 단언한다 |
| T3 | O6의 SQL 카운트가 route와 **독립 경로**다 | route와 같은 함수를 쓰면 실패 — 같은 버그가 양쪽에 있으면 일치가 증명이 아니다 |
| T4 | O8이 **계획**을 본다 | `EXPLAIN` 없이 "빠르다"로 대체하면 실패 |
| T5 | O10의 3자 일치가 **measurement 행에서** 온다 | 요청 digest만 비교하면 실패. measurement·row·요청 셋을 비교한다 |
| T6 | O12·O11이 **out-of-band를 잡는다** | 코드 경로만 시험하면 실패 — 직접 SQL로 pin을 앞당기거나 `verified_at`만 세운 뒤 관측이 그것을 드러내야 한다 |
| T7 | O13이 **GC를 실제로 돌린 뒤** 본다 | GC 없이 존재만 확인하면 실패 |

## 7. 경계 · 미해결

- **임계치의 표본 수(20·30)는 이 문서가 처음 고정한 값**이다. 운영 데이터량을 본 뒤 올릴 수는 있으나, **결과를 보고 내리는 것은 금지**한다 — 내려야 할 이유가 생기면 새 판으로 근거와 함께 바꾼다.
- **O8의 "운영 규모"가 수치로 정해지지 않았다.** 파일럿 데이터량이 정해지면 그 수를 여기 적는다.
- **O13의 GC 주기가 정해지지 않았다.** GC 주체·주기는 storage owner 결정이고 `G-20`에 걸려 있다.
- **이 문서는 판정을 내리지 않는다.** 세 task의 현재 점수는 재채점(PR **#220**) v1.2의 **75**이고, 이 문서는 그 75를 올리는 데 **무엇이 필요한지**만 정한다.
- 실행하지 않았다: 로컬 실 PG·Docker·전체 suite. 이 문서의 실측은 `git show`·`git grep -n -F`로 읽은 코드뿐이고, **관측은 하나도 수행하지 않았다.**
