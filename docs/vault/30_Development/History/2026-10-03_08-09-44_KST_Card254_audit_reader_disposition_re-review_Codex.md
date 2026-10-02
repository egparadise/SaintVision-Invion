---
doc_id: "HISTORY-CARD254-AUDIT-READER-DISPOSITION-CODEX"
title: "Card 254 inv_audit_reader E3 E4 E5 disposition 재검토"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-10-03T08:22:39+09:00"
source_of_truth: "Git"
base_sha: "752245861eb0af1e3a4e714cb77c0948ce6f76b7"
reviewer: "Claude"
---

# 선택 근거와 범위

공통 진행판이 allowlist owner의 다음 행동으로 적은 `inv_audit_reader` E3/E4/E5
`accepted-with-expiry`를 만료 전에 재검토한다. 공개 계약·migration·제품 route를 바꾸지
않고, 현재 grant·policy·실제 reader 경로와 hosted SEC-RLS-001 관측만 판정한다.

# 재측정

- `migrations/versions/0047_audit_events_isolation.py`만 role을 정의·변경한다. 이후
  migration의 role 참조는 0건이다.
- role은 `NOLOGIN`, `NOINHERIT`, `NOBYPASSRLS`, direct member 0 guard이고
  `public.audit_events` SELECT-only다. table은 ENABLE+FORCE RLS이며 read policy는
  `audit_events_audit_read USING (true)`, `inv_app` SELECT는 회수돼 있다.
- 제품 `src/`·`services/`의 role 문자열은 설명 세 파일뿐이며 connection/role assumption/
  operational membership 경로는 없다.
- E3/E4/E5는 false positive가 아니라 audit role의 의도된 실제 visibility다. tenant가 없는
  인증 거부를 포함해 읽는 목적을 보존하므로 grant 제거 migration은 필요하지 않다.

# 결정

임시 disposition을 유지하되 만료는 `2026-11-30T23:59:59+09:00`으로 한 달만 연장한다.
collector는 `granted_to`를 live catalogue에서 추가 관측하고, evaluator는 login/inherit/
bypass/member 양방향, SELECT-only, FORCE RLS와 exact read policy가 모두 맞아야 PASS한다.
하나라도 넓어지면 달력 만료 전에도 `MEASURED_FAIL`이다.

# 검증과 남은 단계

- `6ea6d256`에서 collector/evaluator·reviewed source·생성 allowlist를 갱신했고,
  `141ef51d`에서 target registry를 새 allowlist blob에 고정했다. `36c18b3a`는 registry를
  소비하는 importer pin과 dependency/SAST importer self-pin을 회전했다.
- focused PG-free는 **386 passed, 15 skipped**다. 15건은 모두 disposable PostgreSQL DSN이
  필요한 실-PG node이며 hosted security lane에서 실행한다.
- `write_ac11_security_allowlist.py --check`, `check_docs.py`, `git diff --check`는 exit 0이다.
  path-citation ratchet은 이 카드가 추가한 결함이 아니라 현재 작업 트리에 생성된
  `apps/web/dist`·`node_modules` 때문에 기존 baseline 5건이 더 이상 깨지지 않는다고
  보고해 별도 환경 정리 대상으로 남겼다.

아직 hosted 결과가 없으므로 SEC-RLS-001 PASS를 주장하지 않는다. 다음 단계는 이 head를
push한 뒤 PostgreSQL 16 security lane을 실행하고 Claude 독립 검토를 받는 것이다.
