---
doc_id: "CLAUDE-F-S02-01-AUDIT-RLS-IMPL-001"
title: "F-S02-01 구현 — audit_events RLS ENABLE+FORCE, 앱 SELECT 회수, NULL-tenant 거부 기록 append primitive (실 PG 실측)"
version: "1.1.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T09:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf045c5a554209aaef601ae4883b64da50a7"
tags: ["f-s02-01", "audit-events", "rls", "security-definer", "s02-db", "claude"]
---

# F-S02-01 구현 — audit_events 테넌트 격리 (2026-09-28)

설계 1쪽: [[2026-09-28_06-10-00_KST_F-S02-01_audit_events_테넌트격리_설계_Claude]]. 계약은 Codex 판정(PR #120 "F-S02-01 정책 판정", baseline 수용 기각) 4항이다. base `1e8baf04`(origin/integration/all-agents-unified), branch `agent/claude/f-s02-01-audit-rls`, worktree `.worktrees/claude-f-s02-01`.

## 1. 착지한 것

| 파일 | 변경 |
|---|---|
| `migrations/versions/0047_audit_events_isolation.py` | 신규. RLS ENABLE+FORCE, 정책 3, `REVOKE SELECT … FROM inv_app`, 역할 `inv_audit_writer`·`inv_audit_reader`, `public.record_auth_denial(...)` SECURITY DEFINER. **가역** downgrade. |
| `src/saintvision/services/audit.py` | `record_denial_out_of_band`를 두 갈래로. tenant 있음 → 자기 트랜잭션 + `tenant_scope` + 기존 `record_event`; tenant NULL → primitive. `outcome != 'deny'`·`reason_code` 없음은 DB 전에 `ValueError`. `record_event`는 무변경. |
| `src/saintvision/db/models/__init__.py` | 새 상수 `AUDIT_TABLES = ("audit_events",)` — "앱이 쓰되 읽지 못하는 append-only" 부류. |
| `src/saintvision/db/models/operations.py` | `AuditEvent` docstring이 실제로 존재하는 역할·migration·primitive를 가리키게 정정(finding의 뿌리는 이 선언과 DDL의 불일치였다). |
| `src/saintvision/db/rls.py` | 선언용 헬퍼가 `AUDIT_TABLES`에는 INSERT만 주도록. (이 헬퍼는 호출자가 없는 선언문이며 정본은 migration이다 — 그래서 고쳤다.) |
| `tools/definer-policy.json` | `revision` → `0047_audit_events_isolation`, 새 항목 `public.record_auth_denial(text, text, text, text, text, text, text, text, jsonb, text, text)`(definitionSHA256 `397bfe69…`, executeRoles `[inv_app]`, kind `tenant-less-audit-append`, sourceMigrationSHA256 `d9e3c774…`). `referenceSource`는 이 관측을 뜬 base 전체 SHA로 갱신. |
| `tools/collect_rls_evidence.py` | 기본 역할에 `inv_audit_writer`·`inv_audit_reader` 추가. |
| `tools/rls-boundary-baseline.json` | `(inv_audit_reader, public.audit_events, E3·E4·E5)` 이유 명시. **E2는 예외가 아니라 통과**다. |
| `tests/test_audit_events_isolation.py` | 신규 15건(아래 §3). |
| `tests/test_migrations.py` | 정적 게이트 3건(RLS·정책 3·grant→revoke 순서·primitive 좁음·읽기 역할 형태). |
| `tests/test_api.py` | `test_a_denial_with_no_tenant_is_still_recorded` — 401 뒤 NULL-tenant 행 1건 확인. |
| `tests/test_database.py` | append-only 시험의 INSERT를 `tenant_scope` 안으로(정책 추가에 따른 정합, 단언 의도 불변). |
| `tests/test_collect_rls_evidence.py` | head 0046에 고정돼 있던 gap 단언 3곳을 닫힘으로 뒤집고(주석이 예고한 지점), 새 역할·primitive 관측 단언 추가. |

정책 세 개를 역할별로 쪼갠 이유와 primitive가 할 수 없는 것 네 가지는 migration docstring에 적었다.

## 2. 실측 (실 PG `127.0.0.1:55432`, disposable DB, detached + UTF-8 로그, 파일 하나씩)

| 명령 | 결과 |
|---|---|
| `pytest tests/test_audit_events_isolation.py` (구현 **전**, red) | **12 failed / 3 passed** — 살아 있던 3건은 RLS 없이도 참인 것(자기 tenant INSERT·append-only)과, 함수 부재로 42883이 떠서 통과해 버린 거부 시험 1건이었다. 그 vacuity를 없애려고 해당 시험이 sqlstate `22023`을 단언하게 고쳤다. |
| `pytest tests/test_audit_events_isolation.py` (구현 후) | **15 passed** exit 0 |
| `pytest tests/test_migrations.py` | **25 passed** exit 0 (오프라인 렌더, DB 불요) |
| `pytest tests/test_database.py` | **19 passed** exit 0 |
| `pytest tests/test_api.py` | **29 passed** exit 0 |
| `pytest tests/test_collect_rls_evidence.py` | **20 passed** exit 0 (131.87s) |
| `pytest tests/integration/test_definer_audit.py` | **22 passed** exit 0 |
| `pytest tests/test_route_coverage.py` · `tests/core/test_serving_anchors.py` · `tests/core/test_definer_audit_cli.py` · `tests/test_migration_prerequisite.py` | **39 · 9 · 3 · 6 passed**, 각 exit 0 |
| 가역 tail 왕복 (backend.yml "The reversible tail reverses"와 같은 절차) | `head=0047_audit_events_isolation`, `downgrade_target=0046_model_manifest_readiness`. upgrade → `{rls True, forced True, policies 3, primitive 1, app_select False, app_insert True}` / downgrade → `{rls False, forced False, policies 0, primitive 0, app_select True, app_insert True, head 0046}` / re-upgrade → upgrade와 동일. **ROUNDTRIP OK** |
| SECURITY DEFINER 카탈로그 관측(disposable, head 0047) | 13 함수. 기존 12건의 `definitionSHA256`이 shipped policy와 **전부 일치**(base에서 재확인), 신규 1건 owner `inv_audit_writer`·execute `[inv_app]`. |

`sync_obsidian.py --check`는 문서 갱신 **전** `1733 managed, 1 pending export, 0 conflicts`(exit 0)였고, 진행판·작업판을 고친 **뒤**에는 그 두 파일이 `both-diverged`로 exit 3이다(`.work/obsidian-sync-conflicts.json`). 공유 Obsidian 사본이 이미 외부에서 편집돼 있다는 뜻이므로 **`--apply` 하지 않았다** — 두 파일은 다른 Agent도 쓰는 공유 문서이고, 덮어쓰면 남의 편집을 지운다. 정본은 docs/vault이고, 사본 병합은 코디네이터 소관이다.

게이트 전부 exit 0: `check_docs`(PASS 894 문서) · `check_contract_bindings`(54 fixture / 19 타입·25 자리 / 14 replay guard) · `check_ontology`(PASS) · `check_frontend_integrity`(0 violations) · `check_doc_single_source --ratchet`(18 pairs, none stale) · `check_response_freshness`.

**중요한 CI 변화**: 0047이 가역이므로 `tools/migration_graph.py --downgrade-target`이 처음으로 head와 달라진다. backend.yml의 "The reversible tail reverses" 단계는 지금까지 "No reversible tail"만 출력했고, 이제 실제로 `downgrade 0046` → `upgrade head`를 실행한다. 그래서 위 왕복을 가정하지 않고 실측했다.

## 3. Codex 계약 4항 ↔ 시험 1:1

- **cross-tenant read 0 / GUC unset·not-UUID read 0** — `test_the_application_role_cannot_read_audit_events_at_all`(세 GUC 상태 모두 권한 거부, 같은 시험에서 owner가 3행을 본다고 먼저 단언해 "0"이 공허하지 않게 함) + `test_the_policy_still_closes_when_select_is_re_granted`(SELECT를 일부러 되돌려 준 뒤: unset 0 · tenant A는 A 한 행만(event_id 동일성) · tenant B에서 타 tenant 0 · NULL-tenant 0 · not-a-uuid는 오류로 fail-closed) + `test_the_application_role_has_no_read_privilege_and_keeps_insert`(권한 표).
- **NULL denial insert 성공** — `test_a_null_tenant_denial_is_recorded_through_the_primitive`(tenant NULL·outcome deny·reason_code·source_ip·서버 시각) + `tests/test_api.py::test_a_denial_with_no_tenant_is_still_recorded`(HTTP 401 → 행 1건, action `GET /v1/nodes`, actor_type `anonymous`).
- **app의 임의 NULL·타 tenant insert 거부** — `test_the_application_role_cannot_forge_a_null_tenant_row[unset|tenant_a]`, `test_the_application_role_cannot_write_another_tenants_row`, 양성 대조 `test_the_application_role_can_still_write_its_own_tenants_row`.
- **append-only 불변식** — `test_append_only_holds_for_the_application_role`(UPDATE·DELETE 거부 후 원래 값 유지 확인), `test_the_writer_role_can_append_only_null_tenant_denials`(정책만으로: NULL+deny 허용, tenant 행 거부, `allow` 거부, UPDATE·DELETE 거부, 총 행수 대조), reader의 INSERT 거부.
- **좁음·도달 불가** — `test_the_primitive_refuses_a_denial_that_says_nothing`(4 필드 NULL → sqlstate 22023), `test_the_primitive_is_owned_by_the_writer_and_executable_only_by_the_app`(owner·prosecdef·search_path·EXECUTE `[inv_app]`), `test_neither_new_role_is_reachable_from_the_runtime_roles`(inv_app·inv_kernel × 두 역할 `pg_has_role` MEMBER 전부 false, NOLOGIN·NOSUPERUSER·NOBYPASSRLS), `test_audit_events_rls_is_enabled_forced_and_policed`(PUBLIC 대상 정책 없음).

## 4. 정직한 미충족·경계

- **이 primitive는 앱이 가짜 거부 기록을 만드는 것을 막지 않는다.** 앱은 이전에도 자기 tenant 행을 쓸 수 있었고, 막은 것은 ① 타 tenant 행 ② NULL-tenant `allow` ③ 읽기 ④ 임의 시각이다. 위조 방지는 별 주제다.
- **`inv_audit_reader`는 전 테넌트를 읽는다.** 목적이 NULL-tenant 행 열람이라 tenant 술어를 걸 수 없다. baseline에 이유와 함께 적었고 수집기 기본 역할에 넣어 증거에 드러나게 했다. tenant 술어를 건 두 번째 읽기 역할이 필요하면 별 카드다(§Codex 확인 1).
- **disposable DB에는 audit 행이 0건**이므로 수집기가 `inv_audit_reader`에 대해 E3/E4/E5를 발화하지 않는다. 즉 수집기 PASS는 이 역할의 범위를 측정한 것이 아니다 — 범위는 §3의 시험이 직접 행을 넣어 확인한다. 이 구분을 지우지 않았다.
- **`WORM`이 아니다.** owner·superuser는 여전히 UPDATE/DELETE할 수 있다(PLAN-DB-001과 동일 경계). 현재 개발·CI의 `invowner`는 superuser라 RLS도 우회하므로, FORCE RLS의 실효는 non-owner 역할에 대해서만 관측된 것이다.
- **`tools/check_definer_functions.py` 자체는 head 0047 DB를 요구**한다. 공유 dev DB(`invdev`)는 0046이므로 이 세션에서 그 DB를 migrate하지 않았고(공유 자원), 대신 disposable DB에서 `tests/integration/test_definer_audit.py` 22 passed와 §2의 카탈로그 관측으로 확인했다. 운영 DB 적용은 코디네이터/운영 인수다.
- **주입 clock 손실**: NULL-tenant 거부 행의 `occurred_at`은 서버 `clock_timestamp()`다. 기존 시험 중 그 시각을 단언하는 것은 없었다(실측). 설계 §7-2에서 Codex 확인 요청 항목으로 올렸다.
- **registry 무변경**: `docs/task-registry.json`에 F-* 카드 항목은 없고 S02-DB는 `review`다. self-close 하지 않았다.

## 6. Codex 보안 검토 반영 (v1.1.0, 2026-09-28 09:05 KST)

`c96f4f60`에 대한 Codex 판정은 **수정 요청**이었고 두 건 모두 맞다. SECURITY DEFINER 본문·`occurred_at` 서버 시계·명시적 cross-tenant reader 역할은 수용됐다.

### F-R1 — reader membership guard가 간접·미승인 멤버십을 못 막았다

원래 guard는 `pg_auth_members`에서 **직접** member가 `inv_app`/`inv_kernel`인 경우만 봤다. `GRANT inv_audit_reader TO bridge; GRANT bridge TO inv_app`이면 통과하면서 `inv_app`은 `pg_has_role` 상 reader를 assume한다. 그 두 역할이 아닌 기존 login member도 검토 없이 cross-tenant reader가 된다.

고친 것: guard가 **member가 하나라도 있으면** 거부하고, 예외 메시지에 그 이름들을 담는다(writer guard와 같은 원칙). 두 번째 `pg_has_role` guard를 덧붙이지 않은 이유를 migration 주석에 적었다 — `inv_audit_reader`에 닿는 모든 멤버십 사슬은 머리에 직접 member가 있으므로, 직접 member를 전부 거부하면 사슬도 거부된다. 도달 불가능한 두 번째 guard를 들고 있는 것보다 정확하다.

시험: `tests/test_audit_events_isolation.py::test_the_upgrade_stops_when_the_audit_reader_already_has_members[direct|chain]` — disposable DB를 0046까지 올린 뒤 (a) 직접 member, (b) `reader → bridge → leaf` 사슬을 시드하고 `alembic upgrade head`가 **중단**되는 것, 그리고 중단이 half-applied가 아닌 것(head 0046·RLS off·정책 0·함수 0)을 확인한다. 사슬 시드가 실제 bypass 형태임을 `pg_has_role(leaf,'inv_audit_reader','MEMBER') = true`로 먼저 단언한다(no-op 시드가 아님). leaf에 `inv_app`을 쓰지 않은 이유도 적었다: 역할은 클러스터 전역이고, 실제 앱 역할에 전 테넌트 감사 경로를 부여하는 것은 시험 방법이 아니라 그 구멍 자체다. guard의 성질은 "member가 있는지"이므로 leaf가 누구인지에 의존하지 않는다. 클러스터 전역 부수효과(수초간 존재, `finally`에서 회수)도 docstring에 명시했다.

정적 게이트도 좁혔다: `test_migrations.py`가 새 메시지를 요구하고, 두 runtime 역할로 범위가 좁혀진 옛 형태를 **거부**한다.

### F-R2 — downgrade가 원래 취약점을 조용히 복원했다

원래 downgrade는 RLS를 끈 뒤 `GRANT SELECT ON audit_events TO inv_app`을 다시 실행했다. 감사 행이 남은 운영 DB를 0046으로 내리는 순간 app role이 전 테넌트·NULL-tenant 감사기록을 읽는다. **보안 수정의 rollback이 그 수정을 되돌리는 경로가 되면 안 된다.**

고친 것: downgrade는 기계장치만 걷어내고 `inv_app`의 SELECT는 **회수 상태로 둔다**(`REVOKE SELECT ON audit_events FROM inv_app`). 호환성 근거도 없다 — 제품 읽기 경로가 그 권한을 쓰지 않는다(트리 안의 유일한 reader는 owner로 읽는 시험이다). 정확한 baseline 복원이 필요하면 자동 downgrade가 아니라 명시적 보안 예외 절차다. 가역성은 유지하되 **대칭이 아니다**를 migration docstring과 module docstring에 적었고, DB만 0046으로 내리고 0047 코드를 남기면 NULL-tenant 거부 경로가 500이 된다는 운영 순서(migrate → deploy, code rollback → schema rollback)도 함께 적었다.

시험: 왕복을 스크래치패드 검증이 아니라 **저장소 시험**으로 승격했다 — `test_the_downgrade_removes_the_machinery_without_restoring_the_read`(head → 0046 → head 세 상태를 카탈로그에서 읽어 비교, 0046 상태에서 `app_select=False`를 요구) + PG-free 소스 단언 `test_migrations.py::test_the_downgrade_does_not_restore_the_insecure_audit_grant`. `--sql`은 downgrade를 렌더하지 않으므로 소스에서 읽는다.

### 이 수정의 검증 상태 (정직)

- PG-free: `pytest tests/test_migrations.py` **26 passed** exit 0(새 downgrade 소스 단언 포함), `tests/core/test_definer_audit_cli.py` 3 passed, `check_docs` exit 0.
- **실 PG는 이 수정분에 대해 로컬에서 돌리지 않았다.** 코디네이터 규칙(가용 1.5GB 이상일 때만 실 PG, 파일 하나씩)에 따른 것이며 측정 시각 가용 메모리는 1.28GB → 0.81GB였다. 따라서 새 시험 3건(`[direct]`·`[chain]`·downgrade 왕복)의 실행 근거는 **hosted Backend**다. 로컬 통과를 주장하지 않는다.
- `definer-policy.json`의 `sourceMigrationSHA256`은 migration 본문이 바뀌었으므로 `82e1126d…`로 갱신했다. `definitionSHA256`은 함수 본문을 건드리지 않았으므로 불변(`397bfe69…`).

## 7. 다음 첫 행동과 담당

1. **Codex** — F-R1·F-R2 수정분 재검토(§6). 설계 §7의 세 확인 항목은 이미 수용 회신을 받았다. 병합은 Codex 판정 후.
2. **Claude** — 회신 반영, 필요 시 두 번째 읽기 역할 카드.
3. **코디네이터/운영** — 운영·공유 DB의 0047 적용과 `inv_audit_reader` 위임 대상 결정(현재는 NOLOGIN·NOINHERIT이므로 명시적 `SET ROLE`이나 member 부여가 필요하다).
