---
doc_id: "CLAUDE-F-S02-01-AUDIT-RLS-DESIGN-001"
title: "F-S02-01 설계안 — audit_events RLS ENABLE+FORCE, 앱 읽기 회수, NULL-tenant 인증 거부 기록을 좁은 SECURITY DEFINER append primitive로 보존"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T06:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
impl_sha: "(구현 커밋 — Claude 작업 현황 항목 참조)"
tags: ["f-s02-01", "audit-events", "rls", "security-definer", "design", "claude"]
---

# F-S02-01 설계안 — audit_events 테넌트 격리 (2026-09-28)

계약: Codex 판정(PR #120 코멘트 "F-S02-01 정책 판정", baseline 수용 기각). 이 문서는 그 4항 권고를 그대로 계약으로 받아 구현 형태를 1쪽으로 고정한 것이며, **Codex 확인 요청 항목은 §7**이다.

## 1. 현재 상태 (실측, base `1e8baf04`)

- `migrations/versions/0001_s02_baseline.py:468` — `GRANT SELECT, INSERT ON audit_events TO inv_app`. 같은 함수의 `TENANT_SCOPED` 루프(470-476행)에만 `ENABLE`/`FORCE`/`*_tenant_isolation` 정책이 붙고 **audit_events는 루프 밖**이다. 따라서 RLS 없음.
- `src/saintvision/db/models/operations.py:80-83` 주석은 "NULL tenant row는 RLS 밖이므로 audit **read role은 application role과 분리**된다"고 선언하는데, 그 read role은 저장소에 **존재하지 않는다**. 선언과 DDL 불일치가 이 finding의 실체다.
- 수집기 판정: `docs/vault/30_Development/Evidence/rls-boundary/rls-disposable-head-20260922.json` → `verdict: VIOLATIONS`, 유일한 위반 `E2 inv_app public.audit_events`. E3/E4/E5가 조용한 이유는 disposable DB에 audit 행이 0건이기 때문이며(`disposable_database`는 tenants/projects만 seed) **격리가 확인된 것이 아니다**.
- 앱 경로 실측: 쓰기는 `services/audit.py::record_event`(요청 트랜잭션, 6 라우트 모두 `tenant_id=principal.tenant_id`이고 `tenant_scope` 안) + `record_denial_out_of_band`(자기 트랜잭션, `api/app.py:114` AUTH/SEC 처리기에서만; tenant는 알려질 수도 NULL일 수도 있다). **읽기 경로는 제품 코드에 0건** — `tests/test_api.py:252`가 owner로 읽는 것이 전부다. 즉 app role의 SELECT는 쓰이지 않으면서 전 테넌트 감사기록을 열어두고 있었다.

## 2. 새 migration `0047_audit_events_isolation` (head `0046` 다음, 기존 migration rewrite 없음)

1. `ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY`.
2. 역할 둘을 새로 만든다(둘 다 `NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS`, 0045의 issuer 역할과 같은 형태):
   - `inv_audit_writer` — **함수 소유 전용**. 0045의 `inv_discovery_issuer_guard`와 같은 이유로 "이미 member가 있으면 migration 중단" 가드를 둔다. 소유권 이전은 0045와 동일한 `GRANT … TO CURRENT_USER` → `ALTER FUNCTION … OWNER TO` → `REVOKE CREATE ON SCHEMA public` → `REVOKE … FROM CURRENT_USER` 절차.
   - `inv_audit_reader` — 감사/시스템 읽기 전용. `inv_app`·`inv_kernel`이 이 역할의 member면 migration 중단(가드).
3. 정책 셋(테이블 하나에 셋, 역할별로 분리):
   - `audit_events_tenant_isolation` `FOR ALL TO inv_app USING (tenant_id = NULLIF(current_setting('inv.tenant_id',true),'')::uuid) WITH CHECK (같은 식)` — app의 **쓰기**는 현재 tenant와 일치할 때만. `USING`은 SELECT 권한이 회수된 뒤에도 남겨 둔다(누군가 SELECT를 재부여하면 정책이 먼저 닫는다: fail-closed 이중화).
   - `audit_events_denial_append` `FOR INSERT TO inv_audit_writer WITH CHECK (tenant_id IS NULL AND outcome = 'deny')` — primitive가 쓸 수 있는 것은 **NULL-tenant 거부 기록뿐**이다.
   - `audit_events_audit_read` `FOR SELECT TO inv_audit_reader USING (true)` — NULL-tenant 행을 읽는 것이 목적이므로 tenant 술어를 걸 수 없다. 이 역할이 전 테넌트를 읽는다는 사실은 §5에서 baseline에 **이유와 함께 명시**한다.
4. 권한: `REVOKE SELECT ON audit_events FROM inv_app`(INSERT 유지 = append-only 불변식 유지) · `GRANT INSERT ON audit_events TO inv_audit_writer` · `GRANT SELECT ON audit_events TO inv_audit_reader` · 두 역할에 `GRANT USAGE ON SCHEMA public`.
5. 파티션: audit_events는 RANGE 파티션이며 파티션 자식에는 ACL이 상속되지 않는다(`resource_snapshots`와 동일 구조, 부모 경유 접근만 권한 검사를 통과). 따라서 부모에 RLS를 걸면 자식 직접 접근 우회는 권한 부재로 닫힌다 — 새 파티션을 만드는 `ensure_partitions`는 GRANT를 하지 않는다(실측).
6. `downgrade()`는 **실제로 되돌린다**(정책 3 DROP, `NO FORCE`/`DISABLE`, 함수 DROP, `GRANT SELECT` 복원). 역할은 클러스터 공유 가능성 때문에 baseline과 같은 이유로 DROP하지 않는다. 결과적으로 `tools/migration_graph.py`의 안전 downgrade target은 `0046`에 그대로 머물고, 0047은 그 위의 가역 tail이 된다(불가역 revision을 새로 만들지 않는다).

## 3. 좁은 append primitive

```
public.record_auth_denial(p_event_id text, p_actor_type text, p_action text,
  p_reason_code text, p_actor_id text, p_trace_id text, p_target_type text,
  p_target_id text, p_detail jsonb, p_source_ip text, p_user_agent text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
```

- 본문은 `public.audit_events`에 **한 행만** INSERT하며 `tenant_id`는 상수 NULL, `outcome`은 상수 `'deny'`, `occurred_at`은 **서버 `clock_timestamp()`**다. 호출자가 고를 수 있는 것은 사실 필드(actor/action/reason/trace/target/detail/ip/ua)뿐이다.
- `p_event_id`·`p_actor_type`·`p_action`·`p_reason_code`가 NULL이면 `ERRCODE 22023`으로 거부한다. "이유 없는 거부 기록"은 감사기록이 아니다.
- `occurred_at`을 인자로 받지 않는 이유: (a) NULL-tenant 행은 귀속할 tenant가 없어 유일한 고정점이 서버 시계다, (b) 인증 실패 경로 자체가 "모든 파티션 밖 타임스탬프" 때문에 실패하는 부류를 없앤다. 대가로 주입 clock(`create_app(clock=…)`)은 NULL-tenant 거부 행의 시각에 반영되지 않는다 — 기존 시험 중 그 시각을 단언하는 것은 없다(실측: audit_events를 읽는 시험은 `tests/test_api.py:252` 한 곳, `reason_code`/`outcome`만 본다).
- EXECUTE는 `REVOKE ALL … FROM PUBLIC` 후 `inv_app`에만. `tools/definer-policy.json`에 `revision`을 `0047_audit_events_isolation`으로 올리고 새 항목(정확 definition SHA256 + executeRoles + `sourceMigrationSHA256`)을 추가한다. 0046 사례(누락 시 CI red)와 같은 절차다.
- 능력 경계의 정직한 서술: 이 primitive는 앱이 **가짜 거부 기록을 만들 수 있다**는 점을 없애지 않는다(앱은 이미 자기 tenant 행을 쓸 수 있었다). 없애는 것은 ① 다른 tenant 행 쓰기 ② NULL-tenant `allow` 쓰기 ③ 감사기록 읽기 ④ 임의 시각 부여다.

## 4. 앱 코드 이전

`services/audit.py::record_denial_out_of_band`를 두 갈래로 나눈다. `outcome != 'deny'`는 `ValueError`로 먼저 거부한다(이 함수의 이름이 곧 계약이다).
- `tenant_id is None` → primitive 호출(자기 트랜잭션). 이것이 AC-02가 지키라는 "tenant로 해석되지 않은 자격증명 거부" 기록이다.
- `tenant_id` 있음 → 자기 트랜잭션 + `tenant_scope(session, tenant_id)` + 기존 `record_event`. GUC를 세우지 않으면 새 정책이 닫으므로 이 SET이 곧 수정의 실질이다(401 AUTH-MISSING-CREDENTIAL은 앞 갈래, 403 authorization 거부는 보통 뒤 갈래).

`record_event`(요청 트랜잭션)는 **무변경**이다. 6 라우트 전부 `tenant_scope` 안에서 같은 tenant를 쓰므로 새 `WITH CHECK`를 이미 만족한다(실측). 읽기 경로 이전은 없다 — 제품 코드에 없기 때문이며, 대신 `src/saintvision/db/rls.py`의 선언용 헬퍼가 audit 테이블에 SELECT를 주던 줄을 고쳐(모델의 새 `AUDIT_TABLES` 상수 사용) 선언과 DDL이 다시 일치하게 한다.

## 5. 관측·게이트 반영

- `tools/collect_rls_evidence.py` 기본 역할 목록에 `inv_audit_reader`를 추가한다. 추가하지 않으면 "어떤 역할도 전 테넌트를 못 읽는다"로 **잘못 읽히는** 증거가 남는다.
- `tools/rls-boundary-baseline.json`에 `(inv_audit_reader, public.audit_events, E3·E4·E5)`를 이유와 함께 넣는다. 이 역할의 존재 목적이 NULL-tenant 행 열람이므로 tenant 술어를 걸 수 없다는 것이 이유이고, `E2`는 예외가 아니라 **통과**한다(RLS enabled+forced). disposable DB에서는 audit 행이 0건이라 이 셋이 실제로 발화하지 않으므로, 격리 자체는 §6 시험이 행을 넣어 직접 확인한다.
- 정적 게이트: `tests/test_migrations.py`에 오프라인 렌더 기준으로 (audit_events FORCE RLS · 정책 3개 · `REVOKE SELECT … FROM inv_app` · primitive의 `SECURITY DEFINER`/EXECUTE 회수) 단언을 더한다.
- 뒤집히는 기존 단언(의도된 것): `tests/test_collect_rls_evidence.py`의 "head 0046 고정 gap" 3곳(`violations == [("E2","inv_app","public.audit_events")]` · `after == ["public.audit_events"]` · CLI `returncode == 1`)이 각각 `[]`·`[]`·`0`으로 바뀐다. 파일 주석이 "migration이 audit_events를 scope하면 []로 뒤집힌다"고 이미 예고한 그 지점이다.

## 6. 시험 (실 PG, 새 파일 `tests/test_audit_events_isolation.py` + `test_api.py` 1건)

Codex 계약 4항을 1:1로 덮는다.
1. cross-tenant read 0 · GUC unset read 0 · GUC not-UUID read 0 — app role은 SELECT 권한 자체가 없으므로 "권한 거부"로 0이고, `inv_audit_reader`로 `SET LOCAL ROLE`했을 때만 보인다(두 쪽을 같은 시험에서 대조한다).
2. NULL-tenant 거부 기록 INSERT 성공 — primitive 경유(직접 SQL)와 HTTP 경유(`GET /v1/nodes` 무자격 → 401 → `tenant_id IS NULL`, `reason_code='AUTH-MISSING-CREDENTIAL'` 행) 두 층.
3. app의 임의 NULL insert 거부 · 타 tenant insert 거부 — 직접 INSERT는 정책 `WITH CHECK` 위반으로 거부, primitive로도 `outcome='allow'`나 다른 tenant를 쓸 수 없음(인자에 없다).
4. append-only 불변식 — app의 UPDATE/DELETE 거부(기존 시험의 INSERT를 `tenant_scope` 안으로 옮겨 유지), `inv_audit_writer`의 UPDATE/DELETE 거부, `inv_audit_reader`의 INSERT 거부.
5. primitive 자체의 좁음 — NULL `reason_code` 거부, EXECUTE가 PUBLIC에 없음, 소유자가 `inv_audit_writer`이고 `inv_app`이 그 역할의 member가 아님.

금지 범위 준수: 전체 suite·브라우저·20동시 부하 없음. 실 PG는 관련 파일 하나씩 disposable DB로 돌린다.

## 7. Codex 확인 요청

1. **읽기 역할의 범위** — 계약 3항 "별도 audit/system 역할만 허용"을 `inv_audit_reader` + `USING (true)` + baseline 명시로 구현했다. tenant 술어를 건 두 번째 읽기 역할(테넌트 감사용)까지 필요하면 별 카드로 받겠다.
2. **occurred_at 서버 시계 고정**(§3) — 주입 clock을 NULL-tenant 거부 행에서 포기하는 대가를 수용하는지.
3. **downgrade 가역 유지**(§2-6) — 0045/0046처럼 불가역으로 두는 편을 원하는지. 현재 판단은 "RLS 추가는 되돌릴 수 있고, 되돌릴 수 있게 두는 편이 운영에 정직하다"이다.
