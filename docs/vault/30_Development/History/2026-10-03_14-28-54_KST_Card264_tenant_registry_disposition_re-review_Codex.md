---
doc_id: "HISTORY-CARD264-TENANT-REGISTRY-DISPOSITION-CODEX"
title: "Card 264 public.tenants E2-E5 disposition re-review"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-03T14:49:24+09:00"
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
수행한다. downgrade로 옛 노출을 조용히 되살리지 않고 reviewed forward fix를
요구한다. 카드 263이 0065를 조건부 예약했으므로 이 branch는 현재 0064 head를
부모로 둔다. 0065가 실제로 생기면 train 전에 0065 위로 사슬을 다시 잇는다.

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
