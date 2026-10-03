---
doc_id: "HISTORY-CARD264-TENANT-REGISTRY-DISPOSITION-CODEX"
title: "Card 264 public.tenants E2-E5 disposition re-review"
version: "1.0.3"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-03T16:02:08+09:00"
source_of_truth: "Git"
base_sha: "2ed65f5f9f16d06ce3d4f55953f9338df422d78e"
---

# 결정

`inv_app` / `public.tenants`의 E2·E3·E4·E5를 다시 만료 연장하지 않는다.
`0001_s02_baseline.py:465`의 table-wide SELECT는 모든 tenant의 `slug`와
`display_name`을 읽게 하지만 현재 제품 `src/`·`services/`에는 tenant registry를
조회하는 실행 SQL이 0건이다. 권한이 기능을 지지하지 않고 cross-tenant metadata
열거만 남기므로 migration 0066에서 회수한다.

# 실제 조회자와 경계

- `tools/provision_account.py:91,172`는 operator가 제공하는 schema-owner용
  `INV_PROVISION_DSN`으로만 registry를 읽는다. `inv_app` 제품 경로가 아니다.
- `tools/discovery_credential.py:87,196`은 tenant 존재만 확인한다. 0045는 별도
  `inv_discovery_issuer` NOLOGIN 역할에 `SELECT(tenant_id)`만 부여하며 slug와
  display name은 읽지 못한다. 이 false-positive-with-proof disposition은 유지한다.
- `src/saintvision/db/rls.py`의 선언 helper에서도 0001 legacy grant를 제거한다.
  새 제품 호출자가 생기면 이 정적 ratchet과 hosted RLS 측정이 실패하며, 그때
  필요한 열과 tenant 경계를 새로 검토해야 한다.

# migration과 fail-closed rollback

`0066_tenant_registry_revoke`는 `REVOKE SELECT ON public.tenants FROM inv_app`만
수행한다. 최초 구현은 downgrade를 예외로 막았으나 Backend run `37101100471`에서
기존 0054·0058 왕복 시험이 head에서 내려오는 첫 단계에서 중단됐다. 수정된
downgrade는 옛 grant를 복원하지 않고 같은 REVOKE를 다시 실행한다. 따라서 이전
revision rehearsal은 계속할 수 있지만 cross-tenant 노출은 fail-closed로 남는다.
`irreversible = True` 명시 marker를 migration graph와 AC-11 정적 판정기가 읽으므로
복원 장벽 분류도 유지된다. 카드 263이 0065를 조건부 예약했으므로 이 branch는 현재
0064 head를 부모로 둔다. 0065가 실제로 생기면 train 전에 0065 위로 사슬을 다시
잇는다.

이 장벽 때문에 `migration-reversible-segment`의 현재 tail은 기존 0053–0064의
12개에서 0개로 바뀌며 판정은 구조적 `NOT_APPLICABLE`이다. 짝인
`irreversible-restore-forward`가 `MEASURED_PASS`일 때만 집계기가 이 예외를
허용한다. 다음 가역 migration이 0066 뒤에 생기면 tail은 다시 1 이상이 되어 실제
downgrade·catalog fingerprint 측정을 수행한다. 즉 이번 변경은 축 정의를 낮춘 것이
아니라 최신 보안 장벽 뒤에 아직 가역 revision이 없다는 현재 graph의 결과다.

# allowlist와 검증

reviewed source와 collector baseline에서 `inv_app/public.tenants` 행을 제거하고,
생성기로 allowlist를 다시 만들었다. SECURITY DEFINER 함수 15개는 변하지 않았고
policy revision만 0066 head에 재결속했다. aggregator pin은 생성된 allowlist와
baseline·policy Git blob에 맞춰 함께 회전했다.

로컬 focused 결과(실 PostgreSQL은 hosted lane에서 실행):

- allowlist writer: 14 passed
- AC-11 aggregator: 146 passed
- security threat producer: 24 passed, PostgreSQL 7 skipped
- RLS collector: 25 passed, PostgreSQL 8 skipped
- migration rehearsal PG-free: 21 passed
- migration graph·head consumer focused: 150 passed
- security importer·RLS collector focused: 153 passed, PostgreSQL 8 skipped

hosted security run `37100881089`는 source head
`4fc5a11729f92e8f4d9f0259020a7526cab0d39d`에서 모든 step을 통과했다. artifact
`11266490616`의 GitHub digest는
`sha256:23b9b46a83ca25f83470f6b795bc9e1fd06a3fc22d1f74c9d5a58915683c1999`이고
만료 시각은 `2026-11-02T05:47:00Z`다. artifact의 RLS 원관측을 정본
`evaluate_rls()`로 다시 계산한 결과는 `MEASURED_PASS`였다. `inv_app`의
`public.tenants` privilege 네 종류는 모두 null이고 visible probe 자체가 없었으며,
violations/unmeasured는 각각 0이었다. accepted는 discovery issuer의 tenant-id-only
E2-E5, budget guard E2, audit reader E3-E5뿐이다.

이 보고서의 `cleanCheckout`은 scanner가 먼저 만든 evidence 파일 때문에 false로
기록된다. checkout 대상 SHA와 artifact 결속은 run metadata에서 일치하지만, 이
필드는 AC-11 전체 envelope의 clean-checkout 증거라고 주장하지 않는다. 최종 문서
commit 뒤 같은 security lane을 한 번 더 실행해 exact final head를 PR 코멘트에 남긴다.
이 카드에서 AC-11 점수나 전체 gate 완료를 주장하지 않는다.

# Claude r2 조건 — 검토된 irreversible 경계

실행 가능한 irreversible marker는 더 이상 임의 migration의 탈출구가 아니다. migration
graph, rehearsal runner, 정본 AC-11 evaluator가 공유하는 검토 집합은
`0066_tenant_registry_revoke` 하나뿐이다. 이 revision의 downgrade도 검토된
`REVOKE SELECT ON public.tenants FROM inv_app`와 정확히 같아야 한다. 검토되지 않은
marker, GRANT, table drop, 그 밖의 연산은 reversible 축을 `NOT_APPLICABLE`로 바꾸지
못하고 거부된다.

`2026-10-03T16:02:08+09:00` 기준 PG-free focused 검증은
`tests/test_ac11_migration_rehearsal.py`, `tests/test_aggregate_ac11_evidence.py`,
`tests/test_migrations.py` 합계 **201 passed**다. GRANT와 `drop_table` 반례를 세 consumer
각각에 결속했다. exact-head Backend, Core, security 결과는 hosted 완료 뒤 PR 코멘트에
기록한다.
