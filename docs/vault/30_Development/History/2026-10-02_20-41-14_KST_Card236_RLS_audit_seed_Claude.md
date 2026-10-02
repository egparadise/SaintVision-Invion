---
doc_id: "HISTORY-CARD236-RLS-AUDIT-SEED-20261002"
title: "카드 236 — 빈 audit 표 위의 비교를 제품의 쓰기 경로로 채웠다. 그 축은 처음으로 PASS도 FAIL도 아닌 상태를 벗어나 MEASURED_FAIL을 측정했다"
version: "1.1.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T21:09:19+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "68ccba07"
task_ids: ["S11-BE", "S02-DB"]
tags: ["ac11", "security", "rls", "audit-events", "seed", "claude"]
---

# 카드 236 — SEC-RLS-001의 마지막 미측정 행

## 0. 한 줄

`public.audit_events`는 생산자가 만드는 **disposable DB에서 언제나 비어 있었다.** 그래서 `E3`·`E4`·`E5`는 **행 0개와 행 0개를 비교**했고, "이 role은 남의 tenant 행을 못 본다"는 **볼 행이 없어서** 참이었다. 이 판은 그 표를 **제품의 쓰기 함수 그대로** 두 tenant 분량으로 채우고, 보고서가 **자기가 말한 기준으로 판정되게** 고쳤다. 결과는 hosted에서 측정됐다: 그 축의 RLS 보고가 **처음으로 측정된 판정(`MEASURED_FAIL`)** 을 내고, 그 실패가 무엇인지 **세 행으로 이름을 댄다.**

## 1. seed 경로 — 제품이 쓰는 그 함수

| 행 | 경로 | 무엇이 그 행을 받아들였나 |
|---|---|---|
| 거부(`deny`) | `saintvision.services.audit.record_denial_out_of_band(engine, tenant_id=…)` — API가 **principal이 해석된 인가 거부**에 쓰는 경로. 자기 트랜잭션을 열고 tenant scope를 스스로 설정한 뒤 ORM으로 INSERT | `0047`의 `audit_events_tenant_isolation` (`WITH CHECK tenant_id = current_setting('inv.tenant_id')`) |
| 허용(`allow`) | `record_event(session, …)` 를 `saintvision.db.session.tenant_scope` 안에서 — **요청 트랜잭션**이 쓰는 경로 | 같은 정책 |

연결은 **`SET ROLE inv_app`** 이다. 이 lane의 DSN은 DB를 만들고 지워야 하므로 owner/superuser이고 **superuser는 모든 정책을 우회**한다 — 그 연결로 쓴 행은 *제품이 쓸 수 없었던 행*이다. `SET ROLE`은 `collect_rls_evidence`가 각 role의 시야를 측정할 때 **이미 쓰는 같은 수단**이고, 그것이 이 쓰기를 정책 *안으로* 넣는다.

**하지 않은 것**: 권한 확대 없음, role 제외 없음, 정의 완화 없음, 정책을 우회한 임의 INSERT 없음. 심는 행은 tenant당 **2행**(거부 1 + 허용 1), tenant **2개**, 합계 4행이다. `tenant_id IS NULL` 행은 심지 않는다(그 행은 `public.record_auth_denial`만 쓸 수 있고, 그것은 이 카드의 대상이 아니다).

## 2. seed가 거짓말하지 못하게 — fail-closed 세 겹

1. **정책이 정말 검사했는가**: `_prove_policy_enforced()`가 **다른 tenant의 행을 이 tenant의 scope로** 쓰려 하고 **거부를 요구**한다. 실측된 거부는 PostgreSQL 자신의 문장이다 — `new row violates row-level security policy for table "audit_events"`. 통과하면 `ProducerError`다("정책이 검사하지 않은 행 위의 가시성 측정은 기록하지 않는다").
2. **쓴 것이 말한 것과 같은가**: owner가 tenant별로 센 수가 seed가 말한 수(2×2)와 **정확히** 같아야 한다. `tenant_id IS NULL` 행이 하나라도 생겼거나 제3의 tenant 행이 있으면 거부다.
3. **어긋나면 아무것도 측정하지 않는다**: 위 둘 중 하나라도 실패하면 생산자는 두 보고를 `unavailable`(exit 2)로 쓴다 — `evaluate_definer`/`evaluate_rls`가 그 쌍을 `NOT_OBSERVED`로 읽는다. **빈 표 위의 PASS는 어떤 경로로도 만들어지지 않는다.**

## 2-1. r1 — "거부되었다"가 아니라 **그 정책이 거부했다**

Codex r1(차단, High): `_prove_policy_enforced()`가 **모든 `DBAPIError`를 거부 성공으로** 읽었다. 그러면 `sqlite://` engine으로도, 오타로도, 없는 표로도, 끊긴 연결로도 "정책이 강제됐다"가 나온다 — **증명이 아무것도 증명하지 않았다.** 맞는 지적이다.

`rls_refusal(error, table, policy)`가 세 가지를 **모두** 요구한다.

| 요구 | 실측 기준값(PostgreSQL 16, `0047` 정책) |
|---|---|
| SQLSTATE | **`42501`** (`sqlalchemy.exc.ProgrammingError`가 `psycopg.errors.InsufficientPrivilege`를 감싼다) |
| 문장 | **`new row violates row-level security policy for table "audit_events"`** |
| 이름 | 그 문장이 **이 표**를 가리켜야 하고, 서버가 정책 이름을 함께 적으면 그 정책이 `audit_events_tenant_isolation`이어야 한다 |

`diag.table_name`은 이 오류에 **채워지지 않는다**(측정했다) — 그래서 표 이름은 메시지에서 읽는다. 그 밖의 오류는 `ProducerError`이고 두 보고가 `unavailable`(exit 2)이 된다. **거부 메시지의 원문은 인용하지 않는다** — 연결 실패 메시지는 host·user를 담을 수 있으므로 예외 클래스와 SQLSTATE만 적는다.

**문장이 증명의 일부이므로 locale을 고정한다**: probe 연결은 `SET ROLE` 전에 `SET lc_messages = 'C'`를 요청한다. 그것은 `PGC_SUSET`이라 실패할 수 있고 그때는 치명적이지 않다 — 번역된 메시지는 문장 검사에서 떨어져 **`unavailable`** 이 되고, 증명되지 않은 seed가 통과하지는 않는다.

**sqlalchemy wrapper에는 `sqlstate`가 없다**(변이로 확인했다: 드라이버 예외를 풀지 않으면 진짜 거부조차 `sqlstate=None`으로 거절된다). 그래서 `error.orig`를 본다.

**hosted 재측정** (head `6c9624ba`): AC-11 Security Critical High Scan **`37004766458`** success, artifact **`11225606236`** — 그 보고가 여전히 `VIOLATIONS` exit 1이고 정본 평가기가 **`MEASURED_FAIL`** 이다. 즉 CI의 PostgreSQL이 **그 영어 문장 그대로** 거부했고 더 엄격해진 검사가 그것을 증명으로 받아들였다(아니면 보고가 `unavailable`이 됐을 것이다).

시험 **31건**(순수 24 + 실 PG 7). 부정 6건: 다른 SQLSTATE · 같은 `42501`의 다른 문장 · 다른 표 · 다른 정책 · 연결 실패(원문 비인용까지 단언) · **`sqlite` engine을 통한 probe 전체**. 변이 **5/5 사살**(어떤 SQLSTATE나 허용 · 어떤 문장이나 허용 · 표 이름 미검사 · 정책 이름 미검사 · 드라이버 예외 미해제).

## 3. 보고서가 말한 기준으로 판정한다

seed를 넣자마자 드러난 것: 보고서의 `baselineAccepted`는 **검토된 disposition 3개**를 가리키는데, 판정은 collector의 **4개 superset**(`tools/rls-boundary-baseline.json`, S02-DB lane용)으로 했다. 그래서

- 네 번째 항목이 `inv_audit_reader`의 **실제 관측 3건**을 "수용"하고,
- 보고서는 **3개 기준으로 PASS**라고 말하고,
- `evaluate_rls`는 "`accepted`에 검토 집합 밖 행이 있다"며 **`INVALID_RUN`** — PASS도 FAIL도 아니다.

`reviewed_baseline(allowlist)`로 **같은 목록을 양쪽에 쓴다**. 확대가 아니라 **평가기가 이미 전제하던 축소**다(`evaluate_rls`는 검토 집합 밖 `accepted` 행을 거부한다). 검토된 allowlist에 없는 예외는 **위반**이고, 그것이 측정된 판정을 만든다.

## 4. 측정 — 같은 DB를 비었을 때와 심은 뒤

`tests/test_run_ac11_security_threat_reports.py`의 `before_and_after` fixture가 **한 DB에서** 두 번 측정한다(두 측정이 서로 다른 DB로 갈라지지 않게).

| | 비었을 때 | 심은 뒤 |
|---|---|---|
| `ground_truth[public.audit_events]` | `total 0 · tenant_a 0 · other_tenants 0` | **`total 4 · tenant_a 2 · other_tenants 2`** |
| `inv_audit_reader`의 cell | `guc_unset 0 · guc_tenant_a 0 · foreign 0 · unknown 0 · not_uuid 0` | **`guc_unset 4 · guc_tenant_a 4 · foreign 2 · unknown 4 · not_uuid 4`** |
| identity (`ctid`) | owner 0행·role 0행, fp 둘 다 `d41d8cd9…`(빈 입력의 digest) | **owner 2행 `984b2be3…` · role 4행 `8a69b784…` · `match false`** |
| collector 판정 | `UNMEASURED` exit 3 | **`VIOLATIONS` exit 1** |
| 정본 평가기 | `NOT_OBSERVED` | **`MEASURED_FAIL`** |

위반 3건은 전부 같은 쌍이다:

```
E3  inv_audit_reader  public.audit_events  4 rows visible with inv.tenant_id unset
E4  inv_audit_reader  public.audit_events  2 rows of other tenants visible
E5  inv_audit_reader  public.audit_events  4 rows visible for an unknown tenant
```

`inv_app`에는 이 표의 `SELECT`가 **없다**(`0047`이 회수했다) — 그래서 응용 role은 이 표에서 어떤 E 규칙도 만들지 않는다. 즉 **이 비교의 주체는 audit 독자 role**이고, 그것이 cross-tenant인 것은 `0047`이 **의도한 설계**다(§6).

## 5. hosted 실측

| lane | run | 결과 |
|---|---|---|
| AC-11 Security Critical High Scan (`workflow_dispatch`, head `56dfff58`) | **`37002036034`** | success, artifact **`11224410626`**(26,479 bytes, digest `9209086f80e20fc7…`) |

그 artifact의 `s11-ac11-security-rls.json`을 내려받아 **정본 평가기로** 돌린 결과 — 로컬 측정과 **같다**:

```
verdict VIOLATIONS · exit 1 · reportAvailable true
ground_truth public.audit_events: total 4 · tenant_a 2 · other_tenants 2
inv_audit_reader: guc_unset 4 · foreign 2 · identity owner 2행 / role 4행 / match false
unmeasured: []            (빈 표에서 나던 inv_cancel_bridge_owner E4가 사라졌다)
rls_report_shape: ok      evaluate_rls -> MEASURED_FAIL
```

같은 artifact를 importer에 넣으면 **봉투가 그 판정을 싣는다**:

```
threatReportVerdicts: {"SEC-RLS-001": "MEASURED_FAIL", "SEC-SCAN-001": "MEASURED_PASS"}
axis verdict: NOT_OBSERVED
reason: no admissible report for SEC-DEF-001, SEC-VF-001;
        refused by the canonical evaluator: SEC-DEF-001 (INVALID_RUN);
        SEC-RLS-001 recomputes MEASURED_FAIL
```

**축은 아직 `NOT_OBSERVED`다** — 네 report가 모두 있어야 축이 말을 하고, `SEC-DEF-001`은 검토 공백(서명 12 vs 15), `SEC-VF-001`은 이 head에 브라우저 증거가 없다. 바뀐 것은 **`SEC-RLS-001`이 처음으로 측정된 판정을 냈다**는 것이고, 그 판정은 **행이 있는 비교**에서 나왔다.

## 6. Codex 결정 요청 (결정하지 않았다)

**요청 1 — `inv_audit_reader`의 `E3`·`E4`·`E5`.** 카드 225 §5가 이미 같은 결정을 요청했고, 그때는 "행을 심으면 보고 전체가 `INVALID_RUN`이 된다"가 이유였다. 이 카드는 그 결과를 **`INVALID_RUN`에서 `MEASURED_FAIL`로 바꿨다** — 즉 결정이 없어도 축은 이제 **무엇이 실패인지 이름을 대며 측정한다**. 결정 자체는 그대로 남는다:

- `0047`은 그 role의 정책을 `USING (true)`로 **의도해서** 만들었다. `audit_events.tenant_id`는 nullable이고(AC-02가 tenant를 해석하지 못한 거부도 남기라고 요구한다) tenant 술어는 **그 role이 존재하는 이유인 행들을 가린다.** S02-DB baseline은 그 사유를 적고 세 규칙을 예외로 둔다.
- 검토된 AC-11 disposition 3개에는 **그 role이 없다.** 그 파일(`s11-security-allowlist-v0.json`)은 **AC-11 target registry의 `sourceDocument`** 이므로 거기에 항목을 넣는 것은 **축의 정의 변경**이다 — 내가 할 일이 아니다.
- **결정**: 그 예외를 검토된 disposition에 넣을 것인가(그러면 이 축의 RLS 행은 PASS가 된다), 아니면 `MEASURED_FAIL`을 그 축의 참값으로 둘 것인가. 카드 221 §3의 세 결정과 **같은 파일**이므로 함께 보는 것이 맞다.

**요청 2 — `RLS_FILES`의 baseline pin.** 이 카드 이후 AC-11 보고는 `tools/rls-boundary-baseline.json`을 **판정에 쓰지 않는다**(검토된 allowlist를 쓴다). 그 파일은 여전히 S02-DB lane의 정본이고 collector의 도구 표면이므로 pin은 **그대로 두었다**. 그 pin이 "이 판정에 쓰인 파일"을 뜻해야 한다면 `RLS_FILES`에서 빼는 것이 맞고, 그것은 집계기의 검토된 pin 쌍을 바꾸는 **계약 변경**이므로 결정을 요청한다.

**요청 3 — 빈 표의 `ctid` identity.** 카드 234 §3-1이 "`ctid`는 참 row identity이므로 빈 표끼리 일치가 올바른 진술"이라고 정리했고 나도 바꾸지 않았다. 다만 이제 **그 논증이 이 표에서는 쓰이지 않는다**(행이 있다). 156개 표 중 대부분이 여전히 빈 표라는 사실은 그대로이므로, "비어 있는 표에서 verified identity를 주장해도 되는가"는 **축의 의미**에 관한 결정으로 남는다.

## 7. 검증

| 항목 | 결과 |
|---|---|
| `tests/test_run_ac11_security_threat_reports.py` | **31 passed**(실 PG 7 포함, 105s; r1에서 +8). 순수 24: 검토 기준 판정·검토 밖 예외는 위반·accepted의 `reason`/`since`가 문자열·seed 실패 시 unavailable·seed가 측정보다 먼저 |
| 실 PG 7 | 빈 표는 아무것도 관측하지 않음 / seed가 두 tenant×2행을 제품 경로로 씀 / **bypass가 아님**(다른 tenant·scope 없음·`inv_app`의 SELECT 거부 각각) / 비교가 실제 행으로 성립 / 축이 `NOT_OBSERVED` → `MEASURED_FAIL` / 정책이 검사하지 않은 seed 거부 / 쓴 수가 말한 수와 다르면 거부 |
| 네 suite 합계 | **331 passed**(producer 23 · aggregator 138 · importer 98 · collector 33 · manifest 39 중 해당분, 실 DSN으로 399s) |
| 단독 변이 **13/13 사살, 생존 0**(r1의 5건 포함) | superset baseline 복귀 · 정책 증명 생략 · 외부 tenant 쓰기 허용 · owner 계수 생략 · seed를 측정 뒤로 · 거부된 seed 무시 · `SET ROLE` 제거(owner로 쓰기) · 검토 baseline에서 `since` 누락 |
| 정직하게 | 처음 변이판에서 "`accepted`의 null 제거" 한 건이 **생존**했다. 그 코드는 `reviewed_baseline`이 항상 `since`를 주므로 **죽은 코드**였고, 시험이 아무것도 고정하지 않았다. 코드를 지우고 시험을 strict(`reason`/`since`가 비지 않은 문자열)로 바꾼 뒤 그 자리의 변이가 죽는다 |
| pin | 회전 없음 — 생산자 파일은 blob pin 대상이 아니다. **`s11-security-allowlist-v0.json`은 건드리지 않았다** |

## 8. 다음 첫 행동

1. **Codex**: 이 PR 검토 + §6의 결정 요청 세 건(요청 1은 카드 221 §3·카드 225 §5와 같은 파일이므로 함께).
2. **Claude**: 결정이 나오면 같은 head에서 security lane을 다시 돌려 그 축의 RLS 행이 `MEASURED_PASS`로 바뀌는지(또는 `MEASURED_FAIL`이 참값으로 남는지) 재측정.
3. **Claude**: `SEC-VF-001`을 이 lane에 넣는 것은 `#332`(카드 233)가 한다 — train에 들어오면 같은 head에서 네 report가 모두 있는 봉투를 처음으로 만들 수 있다.
