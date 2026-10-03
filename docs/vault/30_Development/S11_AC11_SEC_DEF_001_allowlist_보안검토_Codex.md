---
doc_id: "S11-AC11-SEC-DEF-001-ALLOWLIST-REVIEW-CODEX"
title: "AC-11 SEC-DEF-001 SECURITY DEFINER allowlist 보안 검토"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-10-03T08:09:44+09:00"
source_of_truth: "Git"
base_sha: "752245861eb0af1e3a4e714cb77c0948ce6f76b7"
reviewer: "Claude"
---

# 범위와 결정

Card 221의 exact-head hosted 관측은 `tools/definer-policy.json`과 live catalogue가
SECURITY DEFINER 함수 15개를 일치하게 보고했지만, AC-11 검토 allowlist는 12개만
고정해 `SEC-DEF-001=INVALID_RUN`을 냈다. 이 문서는 차이인 세 함수만 새로 보안
검토한다. 기존 12개는 기존 DB 함수 감사의 승인을 유지하며 정의나 권한을 바꾸지
않는다. 0060의 `inv.build_execution_admission_guard()`는 `SECURITY INVOKER`이고
`PUBLIC`과 `inv_kernel`의 EXECUTE를 모두 회수하므로 privileged-function 집합에
추가되지 않는다.

검토 결과 세 함수 모두 allowlist에 포함할 수 있다. 포함은 현재 definition hash와
execute grant를 승인한다는 뜻이지, 함수가 하는 비즈니스 결과나 운영 인수를 PASS로
간주한다는 뜻이 아니다. `tools/write_ac11_security_allowlist.py`가 이 문서에 연결된
review source와 definer policy·RLS baseline의 exact set이 일치할 때만 allowlist를
생성한다.

# 함수별 보안 검토

| 함수 | 고정 search path·동적 SQL | 호출 권한·owner 경계 | 입력 검증·tenant 경계 | 권한 상승 결론 |
|---|---|---|---|---|
| `public.model_version_measurement(text)` | `pg_catalog`; SQL은 schema-qualified 정적 SELECT 하나이며 동적 SQL 없음 | `PUBLIC` 회수, `inv_app`만 EXECUTE. 함수·kernel table owner는 runtime role이 아니고 `inv_app`/`inv_kernel`이 owner role 멤버가 아니어야 migration resume가 통과 | caller 입력은 measurement ID 하나. `current_setting('inv.tenant_id', true)`에서 tenant를 서버가 정하고 `(tenant_id, measurement_id)` exact 조회. `inv_app`은 kernel table 직접 권한이 없고 다른 tenant ID는 빈 결과 | tenant predicate를 우회하는 projection·writer 권한이 없으므로 승인 |
| `public.record_auth_denial(text,…,jsonb,text,text)` | `pg_catalog`; schema-qualified INSERT 하나, 동적 SQL 없음 | owner `inv_audit_writer`는 NOLOGIN/NOBYPASSRLS이고 migration은 direct/transitive membership의 첫 grant를 거부. `PUBLIC` 회수, `inv_app`만 EXECUTE, owner의 schema CREATE는 같은 transaction에서 회수 | event/actor type/action/reason은 non-null; table CHECK가 ID와 enum을 검증. caller는 detail·관계 식별자를 주지만 `tenant_id=NULL`, `outcome='deny'`, `occurred_at=clock_timestamp()`는 함수 상수이고 writer RLS WITH CHECK도 이를 재검증 | tenant 없는 인증 거부 한 행만 append 가능하고 SELECT/UPDATE/DELETE가 없어 승인 |
| `public.record_kernel_run_cancel(text,text,text,text,text)` | `pg_catalog`; 모든 relation·함수 이름이 schema-qualified, 동적 SQL·caller SQL 없음 | owner `inv_cancel_bridge_owner`는 NOLOGIN/NOINHERIT/NOBYPASSRLS·무멤버십을 migration이 강제. `PUBLIC`·`inv_app` 회수, `inv_kernel`만 EXECUTE. 직접 table grant는 필요한 column으로 제한 | tenant는 GUC에서 재도출. event ID·trace 형식을 검증하고 event 중복을 거부. kernel run이 같은 tenant/project에서 이미 cancelled인지, business mapping·active subject/user/project와 owner/maintainer/operator 권한, workspace/workload/project 결속을 재검증하고 public run을 `FOR UPDATE` | 변경 column은 cancel state/reason/time/version뿐이고 audit actor/action/outcome/target/detail은 서버 상수. cross-tenant·inactive mapping·terminal run·중복 event·partition/권한 실패는 transaction 전체 rollback이므로 승인 |

근거 시험은 `tests/integration/test_model_version_measurements_real_pg.py`,
`tests/test_audit_events_isolation.py`,
`tests/integration/test_kernel_cancel_bridge_real_pg.py`와 각각의 PG-free migration guard다.
정의 hash와 실제 EXECUTE role은 `tools/check_definer_functions.py`가 live catalogue에서
다시 대조한다.

# `inv_audit_reader` E3/E4/E5 disposition

`public.audit_events`에는 tenant 없는 인증 거부도 보존된다. 전용 audit reader가
`USING (true)`로 그 행과 모든 tenant의 감사를 읽는 것은 역할의 목적 자체이므로,
E3(GUC unset), E4(foreign tenant), E5(unknown tenant) 관측은 실제 privileged visibility다.
따라서 세 건을 `false-positive-with-proof`로 낮추지 않고
`accepted-with-expiry`로 분류한다.

수용 경계는 0047이 강제하는 `NOLOGIN`, `NOINHERIT`, `NOBYPASSRLS`, direct member 0,
SELECT-only, `inv_app` SELECT 없음이다. 만료는 `2026-11-30T23:59:59+09:00`이다.
그 전에 실제 운영 reader membership·grant 경로를 재검토하지 않으면 canonical evaluator가
`MEASURED_FAIL`을 내며, 만료를 자동 연장하지 않는다. 정의·E1~E6 자체는 완화하지 않는다.

## Card 254 재검토 — 0061 tree

`752245861eb0af1e3a4e714cb77c0948ce6f76b7`에서 다시 대조한 결과는 다음과 같다.

- `migrations/versions/0047_audit_events_isolation.py`만 role을 이름으로 참조한다. 이후
  migration은 role의 속성·membership·grant·policy를 바꾸지 않는다.
- 0047은 role을 `NOLOGIN`, `NOINHERIT`, `NOBYPASSRLS`로 재고정하고 direct member가
  하나라도 있으면 migration을 거부한다. `public.audit_events`에는 SELECT만 주며
  FORCE RLS와 `audit_events_audit_read USING (true)`를 유지한다. `inv_app` SELECT는 없다.
- 제품 `src/`·`services/`의 role 문자열 세 곳은 모델·서비스 경계 설명뿐이다. role로
  연결하거나 `SET ROLE` 하는 제품 경로와 운영 reader membership 발급 경로는 0건이다.
- role의 목적은 tenant를 해석하지 못한 인증 거부를 포함한 감사 조회다. SELECT를 지금
  회수하면 이 목적을 없애므로 grant 축소 migration은 만들지 않는다. 대신 다음 운영
  reader 경로가 생기기 전 다시 review하도록 한 달 단위로만 갱신한다.

이번 갱신은 문구에 의존하지 않는다. collector가 role을 직접 보유한 principal 목록
`granted_to`를 live catalogue에서 기록하고, evaluator는 login/inherit/bypass/member 양방향,
SELECT-only, FORCE RLS, exact policy가 모두 일치해야만 임시 disposition을 적용한다. 하나라도
달라지면 만료 전이라도 `MEASURED_FAIL`이다.

# 생성·pin 절차

1. reviewer-owned source
   `docs/vault/30_Development/Evidence/s11-security-allowlist-reviewed-source-v1.json`을
   변경한다.
2. `python tools/write_ac11_security_allowlist.py`로 allowlist를 생성한다. policy 함수
   set 또는 collector baseline disposition set이 다르면 exit 2다.
3. 생성된 allowlist의 Git blob·canonical SHA-256을 집계기에 고정한다.
4. 이 allowlist가 들어간 commit을 security target의 `sourceDocument`로 repin하고,
   target registry blob을 집계기와 모든 importer에 같은 commit에서 회전한다.
5. exact-head hosted security lane에서 `SEC-DEF-001` canonical verdict가 더 이상
   `INVALID_RUN`이 아님을 확인한다. RLS는 빈 audit 표면 `NOT_OBSERVED`일 수 있으며 이를
   PASS로 올리지 않는다.
