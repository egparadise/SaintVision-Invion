---
doc_id: "HISTORY-CARD264-TENANT-REGISTRY-DISPOSITION-CODEX"
title: "Card 264 public.tenants E2-E5 disposition re-review"
version: "1.0.0"
status: "in_progress"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-03T14:28:54+09:00"
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

최종 hosted security run ID와 `SEC-RLS-001` 재계산 결과는 exact-head 실행 뒤 이
문서에 추가한다. 이 카드에서 AC-11 점수나 전체 gate 완료를 주장하지 않는다.
