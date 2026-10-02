---
doc_id: "HISTORY-CARD225-RLS-E4-MEASURABLE-20261002"
title: "카드 225 — E4는 소유자가 유일성을 측정한 readable key로도 판정된다. 다만 비교 대상이 0행인 run은 PASS가 아니라 UNMEASURED다"
version: "1.2.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T15:21:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "89b15488"
task_ids: ["S11-BE", "S02-DB"]
tags: ["ac11", "security", "rls", "e4", "collector", "s11", "claude"]
---

# 카드 225 — E4의 미측정 한 행

## 0. 한 줄

`#319`이 남긴 한 줄은 **`inv_cancel_bridge_owner` / `public.audit_events` / `E4` — row identity 확인 불가**였다. 정본을 읽고 측정한 결과 그것은 **정의상 판정 불가가 아니라 관측 방법의 한계**였고, **권한을 넓히지도 role을 모집단에서 빼지도 않고** 그 두 컬럼으로 판정할 방법이 있다.

**r2에서 한 번 더 고쳤다.** 첫 판에서는 그 방법이 **비교 대상이 0행일 때도 `match: true`로 PASS**를 냈다(#322 Codex F-R1). 0행 비교는 어떤 투영이든 단사이고 어떤 fingerprint든 같으므로 **아무것도 측정하지 않는다.** 이제 0행·NULL·중복·미등록 쌍은 전부 `unverifiable`이고, 그래서 **hosted run의 그 행은 PASS가 아니라 UNMEASURED**다. 방법이 위반을 잡는다는 증명은 **행을 심은 실 PG 시험**이 하고, hosted에서 그 행을 진짜로 측정하려면 §5의 **검토 결정이 먼저** 필요하다.

## 1. 정본이 그 role에 무엇을 허용하는가

`migrations/versions/0056_kernel_cancel_audit_bridge.py`를 읽었다.

| 정본이 적는 것 | 값 |
|---|---|
| role | `inv_cancel_bridge_owner` — `NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS`, 멤버가 있으면 migration이 **거부**한다 |
| 그 표에 대한 권한 | `GRANT SELECT (tenant_id, event_id) ON public.audit_events` — **두 컬럼뿐**. INSERT는 열두 컬럼 |
| 정책 | `CREATE POLICY cancel_bridge_audit_read ... FOR SELECT USING (tenant_id = NULLIF(current_setting('inv.tenant_id',true),'')::uuid)` |

즉 **정본의 의도는 "자기 tenant의 audit 행만, 두 컬럼만 읽는다"** 이고, 그 두 컬럼이라는 좁힘이 바로 설계다. 넓히는 것은 이 카드가 금지한 것이다.

## 2. 왜 관측이 안 됐나 — 측정했다

`public.audit_events`는 `0001_s02_baseline`에서 **`RANGE (occurred_at)` 로 파티션**되고, PostgreSQL은 파티션 키를 primary key에 넣으라고 요구하므로 **PK는 `(event_id, occurred_at)`** 다.

collector의 E4 identity는 **`ctid`, 없으면 `tenant_id` + PK 전체**를 요구했다. 그런데 이 role은:

- `ctid` → **거부(42501)**: 시스템 컬럼에 대한 권한이 없다
- `tenant_id + event_id + occurred_at` → **`occurred_at`을 읽을 수 없다**(정본 grant가 주지 않는다)

그래서 "identity unverifiable"이었다. **이것은 정책상 접근이 막혀서가 아니다** — role은 자기 tenant의 행을 **두 컬럼으로 볼 수 있고**, 막힌 것은 **collector가 그 두 컬럼을 identity로 인정하지 않았다는 것**이다. 카드 step 2의 두 갈래 중 **첫 번째**(부수 컬럼 권한에 의존한 관측 한계)로 측정됐다.

## 3. 무엇을 고쳤나 — 관측 방법 하나, 그리고 그 방법의 울타리

E4의 의미를 그대로 두고 identity 방법을 **셋째**까지 넓혔다:

1. `ctid`
2. `tenant_id` + PK 전체
3. **`owner-verified-key`** — 그 key에서 **role이 읽을 수 있는 부분**을, **소유자가 같은 snapshot에서 그 비교 대상 행들에 대해 유일함을 측정했을 때만** identity로 쓴다

세 번째가 "값 투영을 믿지 않는다"는 원칙을 어기지 않는 이유: 소유자가 `count(*)`와 `count(DISTINCT 그 tuple)`을 **같은 트랜잭션·같은 행 집합에서** 세고 **같을 때만** 그 tuple을 identity로 쓴다. 두 개의 다른 행이 같은 tuple을 가질 수 없다는 것이 **측정된 사실**일 때 그 tuple은 row identity다 — 믿은 투영이 아니다.

### 3-1. r2에서 닫은 다섯 구멍 (#322 Codex)

| 구멍 | 지금 |
|---|---|
| **0행 비교가 PASS가 됐다** (F-R1, fail-open) | `rows == 0`이면 `unverifiable`. 사유에 "compared over 0 rows … matches trivially and measures nothing"을 적는다 |
| key 직렬화가 **구분자 충돌**에 취약 (F-R2) | `concat_ws`에서 **`jsonb_build_array(…)::text`** 로. 구분자를 값 안에 넣어 다른 tuple을 흉내내던 쌍이 서로 다르게 적힌다 |
| **NULL**이 조용히 생략됐다 (F-R2) | 같은 snapshot에서 `nullRows`를 세고 0이 아니면 `unverifiable` — 암묵이 아니라 **명시적 fail-closed** |
| 방법이 **모든 role/table로 번질 수 있었다** (F-R2) | `OWNER_VERIFIED_KEY_SCOPE`에 `(inv_cancel_bridge_owner, public.audit_events, (tenant_id, event_id))` **한 쌍만** 등록. 이 파일 blob은 집계기의 `RLS_FILES`에 고정돼 있으므로 쌍을 늘리면 **pin 회전과 함께 검토**를 받는다 |
| 집계기가 **`match`를 믿었다** (F-R3) | `match`는 결론이므로 **두 fingerprint에서 다시 계산**한다. owner 관측이 distinctness를 측정한 그 관측인지(`owner_a.rows == ownerDistinctness.rows`), 두 fingerprint가 digest인지 확인하고, **재계산된 불일치는 측정된 위반**이므로 `exit 0 PASS`도 `exit 3 UNMEASURED`도 될 수 없다(`INVALID_RUN`). 정직하게 적힌 같은 관측은 `exit 1 VIOLATIONS` → `MEASURED_FAIL`이다 |

세 겹으로 같은 질문을 묻는다: **살아있는 probe**(`_identity`), **기록된 보고의 판정**(`unverified_identities`), **정본 집계기**(`evaluate_rls`). 마지막 겹이 중요한 이유는 보고가 *tree에 대한 증거*이고 *그것을 쓴 도구의 약속*이 아니기 때문이다 — 집계기는 등록 밖·0행·중복·NULL key를 `INVALID_RUN`으로 거부한다.

`tenant_id`가 tuple에 들어 있으므로 다른 tenant의 행이 섞여 들어오면 tuple이 달라져 잡히고, 그와 별도로 foreign-row probe가 같은 누수를 따로 본다 — 한 위반에 **두 관측**이다.

## 4. 실측

| 측정 | 결과 |
|---|---|
| 행을 심은 실 PG | `method: owner-verified-key`, `columns: ["tenant_id","event_id"]`, `ownerDistinctness {rows 2, distinct 2, nullRows 0}`, `match: true` → 그 행이 **측정된다** |
| 심은 위반 | 같은 수·다른 집합을 심으면 `match: false` → **E4 위반** → `VIOLATIONS`, 정본 정책 복구 후 다시 PASS |
| **빈 표** | `unverifiable`("compared over 0 rows") → `unmeasured` 1 → **UNMEASURED**. r2 이전에는 이것이 PASS였다 |
| 직렬화 | 실 PG에서 구분자 충돌 쌍이 `rows 2 / distinct 2`로 **구별되고**, NULL 한 행이 들어오면 `unique: false` |
| 미등록 쌍 | `OWNER_VERIFIED_KEY_SCOPE`를 비우면 같은 행이 `unverifiable`("not registered") |

### 4-1. hosted 재실측 — 실제 run

| run | head | 결과 |
|---|---|---|
| security `36963704528` + browser `36963707158` (r1) | `2e87dc12` | `SEC-RLS-001` PASS, 그러나 **그 비교가 0행**이었다 — 이것이 F-R1이 가리킨 fail-open이고, 이 run은 그 행에 대해 **reference-only**다 |
| security **`36967195872`** (r2) | `12be0822` | `exit 3` · `verdict UNMEASURED` · `violations 0` · **`unmeasured 1`** · `accepted 9` |
| security **`36969295226`** + browser **`36969297736`** (r3) | `762a3c67` | 같은 `exit 3 / UNMEASURED / unmeasured 1`. 네 입력 import exit 0, 봉투 `SEC-SCAN-001` MEASURED_PASS · `SEC-RLS-001` **NOT_OBSERVED** · `SEC-VF-001` MEASURED_PASS(#319 F2의 tree 결속 포함), 축 `NOT_OBSERVED` |

r2 run이 그 한 행에 대해 적는 것:

```
E4 inv_cancel_bridge_owner public.audit_events
row identity unverifiable: ctid denied 42501; the readable identity columns
['tenant_id', 'event_id'] were compared over 0 rows of the owner's tenant-A set:
an empty comparison matches trivially and measures nothing
```

importer와 **따로** 돌린 정본 집계기도 같은 결론이다:

| 집계기 호출 | 결과 |
|---|---|
| `evaluate_rls(hosted 보고, 검토된 allowlist, now)` | **`NOT_OBSERVED`** |
| 봉투 `threatReportVerdicts` | `SEC-SCAN-001` MEASURED_PASS · `SEC-RLS-001` **NOT_OBSERVED** |
| `evaluate_axis` | `NOT_OBSERVED` (사유에 `SEC-DEF-001 (INVALID_RUN)`과 `SEC-RLS-001 recomputes NOT_OBSERVED`가 함께 적힌다) |

**정직하게**: 이 카드는 그 행을 hosted에서 PASS로 **올리지 못했다.** 올린 것은 *방법*이고, 그 방법이 참임을 증명하는 것은 행을 심은 실 PG 시험이다. hosted에서 그 행이 진짜로 측정되려면 §5의 결정이 먼저다.

## 5. 측정하다 발견한 것 — **네 번째 검토 결정** (이제 차단 사유다)

처음에는 `disposable_database()`(collector의 공용 fixture)에 audit 행을 심어 비교를 비지 않게 하려 했다. 그러면 **`inv_audit_reader`의 accepted E3·E4·E5 세 행이 생기고**, 검토된 AC-11 allowlist의 **dispositions 세 개에는 그 role이 없다** → `evaluate_rls`가 `INVALID_RUN`을 낸다(측정했다: accepted 12행, 그 중 3행이 검토 집합 밖).

즉 **검토된 세 dispositions는 그 표가 비어 있는 동안에만 충분하다.** 그것은 allowlist의 내용에 관한 결정이고(카드 221 §3의 세 결정과 같은 종류, 같은 파일), **fixture가 대신 정할 수 있는 것이 아니다.** 그래서:

- 공용 fixture는 **그대로 두었다**(audit 행을 심지 않는다).
- 행이 필요한 시험은 **그 시험이 심고 그 시험이 지운다**.
- 그래서 **생산자의 실제 run에서 이 비교는 빈 집합끼리이고, r2부터 그것은 PASS가 아니라 UNMEASURED다.**

**결정 요청**: *AC-11 evidence lane의 disposable DB에 비식별 audit 행을 심어 이 비교를 non-vacuous하게 만들려면, `inv_audit_reader`의 E3·E4·E5를 검토된 dispositions에 넣을지 먼저 결정해야 한다.* 결정 없이 행을 심으면 보고 전체가 `INVALID_RUN`이 된다. Codex r2도 같은 순서를 지시했다("미결인 disposition/allowlist를 먼저 결정").

## 6. 검증

| 항목 | 결과 |
|---|---|
| `tests/test_collect_rls_evidence.py` | **33 passed**(실 PG 8 포함, 582s). 신설: offline 7(0행·NULL·중복·미등록 columns·distinctness 없음·미등록 쌍·정상), 실 PG 3(빈 표 UNMEASURED / 직렬화·NULL fail-closed / 미등록 쌍 거부) |
| `tests/test_aggregate_ac11_evidence.py` | 신설 **13** — 등록·측정된 key만 MEASURED_PASS, 나머지 열한 변형(미등록 쌍·미등록 columns·0행·중복·NULL·불일치를 PASS로·fingerprint 불일치인데 match true·같은데 match false·owner 0행·digest 아닌 fingerprint·role 관측 없음)은 `INVALID_RUN`, 그리고 **UNMEASURED에 숨긴 불일치는 거부·정직한 VIOLATIONS는 MEASURED_FAIL** |
| `test_import_ac11_security_scan.py` · `test_run_ac11_security_threat_reports.py` | **전부 통과**(후자는 실 PG) |
| 단독 변이 **10/10 사살** | 0행 허용·`concat_ws` 복귀·0행 거부 삭제(offline과 실 PG 각각)·NULL 거부 삭제·scope 검사 삭제·기록 재검사 삭제·집계기 scope 검사 삭제·**`match` 재계산 삭제**·**PASS 직전 불일치 무시** |
| pin 회전 | 집계기의 `RLS_FILES` collector blob. **`s11-security-allowlist-v0.json`은 건드리지 않았다** |

## 7. 하지 않은 것

- **권한을 넓히지 않았다.** `0056`의 `GRANT SELECT (tenant_id, event_id)`는 그대로다.
- **role을 모집단에서 빼지 않았다.** 측정은 collector의 `DEFAULT_ROLES` 여덟 개 그대로다.
- **E4의 의미를 낮추지 않았다.** 값 투영을 믿지 않는다는 원칙은 유지되고, 유일성이 **측정되지 않으면**(0행도 측정이 아니다) 여전히 unverifiable이다.
- **검토된 allowlist를 고치지 않았다.** §5는 보고이고 결정이 아니다.
- **evidence lane에 행을 심지 않았다.** §5의 결정이 먼저다.

## 8. 다음 첫 행동

1. **Codex / allowlist owner**: §5의 결정(`inv_audit_reader`의 세 규칙). 카드 221 §3의 세 결정과 **같은 파일**이므로 함께 보는 것이 맞다. 그 결정이 나오면 그 행은 hosted에서도 non-vacuous하게 측정된다.
2. **Claude**: 이 PR의 r2 검토 반영.
