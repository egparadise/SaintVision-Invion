---
doc_id: "HISTORY-CARD225-RLS-E4-MEASURABLE-20261002"
title: "카드 225 — SEC-RLS-001의 미측정 한 행이 측정됐다. 권한을 넓히지도 role을 빼지도 않고, 소유자가 읽을 수 있는 key의 유일성을 같은 snapshot에서 측정하게 한 것이 전부다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T13:11:22+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "89b15488"
task_ids: ["S11-BE", "S02-DB"]
tags: ["ac11", "security", "rls", "e4", "collector", "s11", "claude"]
---

# 카드 225 — E4의 미측정 한 행

## 0. 한 줄

`#319`이 남긴 한 줄은 **`inv_cancel_bridge_owner` / `public.audit_events` / `E4` — row identity 확인 불가**였다. 정본을 읽고 측정한 결과 그것은 **정의상 판정 불가가 아니라 관측 방법의 한계**였고, **권한을 넓히지도 role을 모집단에서 빼지도 않고** 그 행이 측정된다. SEC-RLS-001은 **`NOT_OBSERVED` → `MEASURED_PASS`** 로 움직였다.

## 1. 정본이 그 role에 무엇을 허용하는가

`migrations/versions/0056_kernel_cancel_audit_bridge.py`를 읽었다.

| 정본이 적는 것 | 값 |
|---|---|
| role | `inv_cancel_bridge_owner` — `NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS`, 멤버가 있으면 migration이 **거부**한다 |
| 그 표에 대한 권한 | `GRANT SELECT (tenant_id, event_id) ON public.audit_events` — **두 컬럼뿐**. INSERT는 열두 컬럼 |
| 정책 | `CREATE POLICY cancel_bridge_audit_read ... FOR SELECT USING (tenant_id = NULLIF(current_setting('inv.tenant_id',true),'')::uuid)` |

즉 **정본의 의도는 "자기 tenant의 audit 행만, 두 컬럼만 읽는다"** 이고, 그 두 컬럼이라는 좁힘이 바로 설계다. 넓히는 것은 이 카드의 범위가 아니고 카드가 금지한 것이다.

## 2. 왜 관측이 안 됐나 — 측정했다

`public.audit_events`는 `0001_s02_baseline`에서 **`RANGE (occurred_at)` 로 파티션**되고, PostgreSQL은 파티션 키를 primary key에 넣으라고 요구하므로 **PK는 `(event_id, occurred_at)`** 다.

collector의 E4 identity는 **`ctid`, 없으면 `tenant_id` + PK 전체**를 요구했다. 그런데 이 role은:

- `ctid` → **거부(42501)**: 시스템 컬럼에 대한 권한이 없다
- `tenant_id + event_id + occurred_at` → **`occurred_at`을 읽을 수 없다**(정본 grant가 주지 않는다)

그래서 "identity unverifiable"이었다. **이것은 정책상 접근이 막혀서가 아니다** — role은 자기 tenant의 행을 **두 컬럼으로 볼 수 있고**, 막힌 것은 **collector가 그 두 컬럼을 identity로 인정하지 않았다는 것**이다. 카드 step 2의 두 갈래 중 **첫 번째**(부수 컬럼 권한에 의존한 관측 한계)로 측정됐다.

## 3. 무엇을 고쳤나 — 관측 방법 하나

E4의 의미를 그대로 두고 identity 방법을 **셋째**까지 넓혔다:

1. `ctid`
2. `tenant_id` + PK 전체
3. **`owner-verified-key`** — 그 key에서 **role이 읽을 수 있는 부분**을, **소유자가 같은 snapshot에서 그 비교 대상 행들에 대해 유일함을 측정했을 때만** identity로 쓴다

세 번째가 "값 투영을 믿지 않는다"는 원칙을 어기지 않는 이유: 소유자가 `count(*)`와 `count(DISTINCT 그 tuple)`을 **같은 트랜잭션·같은 행 집합에서** 세고 **같을 때만** 그 tuple을 identity로 쓴다. 두 개의 다른 행이 같은 tuple을 가질 수 없다는 것이 **측정된 사실**일 때 그 tuple은 row identity다 — 믿은 투영이 아니다. 유일하지 않으면 **여전히 unverifiable**이고, 사유에 **두 숫자(행 수 / distinct 수)** 를 적는다.

`tenant_id`가 tuple에 들어 있으므로 다른 tenant의 행이 섞여 들어오면 tuple이 달라져 잡히고, 그와 별도로 foreign-row probe가 같은 누수를 따로 본다 — 한 위반에 **두 관측**이다.

## 4. 실측

| 측정 | 결과 |
|---|---|
| 그 행의 identity | `method: owner-verified-key`, `columns: ["tenant_id","event_id"]`, `ownerDistinctness`와 두 fingerprint를 기록 |
| collector 판정 | `violations 0`, **`unmeasured 0`**, `verdict PASS`(8 role 모집단 그대로) |
| 집계기 평가 | `evaluate_rls` → **`MEASURED_PASS`**(collector pin 회전 뒤) |
| 봉투 | `SEC-SCAN-001` PASS · `SEC-RLS-001` **PASS** · `SEC-VF-001` PASS · `SEC-DEF-001`은 검토 공백으로 `INVALID_RUN` |

**부정 시험(정책 위반을 심었다)**: 그 role의 SELECT 정책을 "tenant A의 행 하나 + 다른 tenant의 행 하나"만 보이게 바꾸면 **행 수는 소유자와 같고 집합은 다르다**. identity fingerprint가 `match: false`를 내고 **E4 위반**이 되며 verdict는 `VIOLATIONS`다. 정본 정책을 되돌리면 같은 측정이 다시 PASS다. (foreign-row probe도 함께 잡는다 — 예상된 일이고, 한 위반을 두 관측이 본다는 뜻이다.)

## 5. 측정하다 발견한 것 — **네 번째 검토 결정**

처음에는 `disposable_database()`(collector의 공용 fixture)에 audit 행을 심어 비교를 비지 않게 하려 했다. 그러면 **`inv_audit_reader`의 accepted E3·E4·E5 세 행이 생기고**, 검토된 AC-11 allowlist의 **dispositions 세 개에는 그 role이 없다** → `evaluate_rls`가 `INVALID_RUN`을 낸다(측정했다: accepted 12행, 그 중 3행이 검토 집합 밖).

즉 **검토된 세 dispositions는 그 표가 비어 있는 동안에만 충분하다.** 그것은 allowlist의 내용에 관한 결정이고(카드 221 §3의 세 결정과 같은 종류, 같은 파일), **fixture가 대신 정할 수 있는 것이 아니다.** 그래서:

- 공용 fixture는 **그대로 두었다**(audit 행을 심지 않는다).
- 행이 필요한 시험은 **그 시험이 심고 그 시험이 지운다**.
- 그래서 **생산자의 실제 run에서 이 비교는 빈 집합끼리다** — `unmeasured`가 아니라 `measured`이고, 기록된 행 수(0/0)가 그 비어 있음을 말한다. 방법의 힘은 행을 심은 시험이 증명한다.

이것을 **네 번째 검토 결정**으로 보고한다: *audit_events에 행이 있는 환경에서 AC-11 RLS 보고가 유효하려면 `inv_audit_reader`의 그 세 규칙을 검토된 dispositions에 넣을지 결정해야 한다.*

## 6. 검증

| 항목 | 결과 |
|---|---|
| `tests/test_collect_rls_evidence.py` | 신설 **다섯**(offline 둘: `owner-verified-key`의 match False/True와 유일하지 않을 때의 unverifiable; 실 PG 셋: 빈 표의 vacuous 측정, 행을 심은 측정, **심은 위반의 FAIL과 복구**) |
| `tests/test_import_ac11_security_scan.py` · `test_run_ac11_security_threat_reports.py` · `test_aggregate_ac11_evidence.py` | **161 passed** |
| 실 PG | 이 PC의 disposable migrated DB로 producer와 시험을 실제 실행 |
| pin 회전 | 집계기의 `RLS_FILES` collector blob(파일이 바뀌었으므로). `s11-security-allowlist-v0.json`은 **건드리지 않았다** |

## 7. 하지 않은 것

- **권한을 넓히지 않았다.** `0056`의 `GRANT SELECT (tenant_id, event_id)`는 그대로다.
- **role을 모집단에서 빼지 않았다.** 측정은 collector의 `DEFAULT_ROLES` 여덟 개 그대로다.
- **E4의 의미를 낮추지 않았다.** 값 투영을 믿지 않는다는 원칙은 유지되고, 유일성이 **측정되지 않으면** 여전히 unverifiable이다.
- **검토된 allowlist를 고치지 않았다.** §5의 네 번째 결정은 보고이고 결정이 아니다.

## 8. 다음 첫 행동

1. **Codex / allowlist owner**: §5의 네 번째 결정(audit 행이 있는 환경에서 `inv_audit_reader`의 세 규칙). 카드 221 §3의 세 결정과 **같은 파일**이므로 함께 보는 것이 맞다.
2. **Claude**: 이 PR의 검토 반영.
