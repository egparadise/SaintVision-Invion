---
doc_id: "HISTORY-CARD268-AUDIT-READER-DISPOSITION-REMOVAL-001"
title: "Card 268 inv_audit_reader disposition 제거"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-03T17:58:55+09:00"
source_of_truth: "Git"
base_sha: "1d2d52890ca29f902f37fc8c403c34aea04cda5b"
---

# 결정

`inv_audit_reader` / `public.audit_events`의 E3·E4·E5
`accepted-with-expiry`를 연장하지 않는다. Train 43에서 제품 연결, `SET ROLE`, membership grant,
audit read route는 0건이며, 역할은 과거 DDL과 보안 경계 측정에만 남아 있다. 의도된 privileged
visibility를 유지할 제품 근거가 없으므로 dormant privilege를 회수하는 쪽이 더 좁은 경계다.

# 구현

- `0067_audit_reader_revoke`는 reader policy, table `SELECT`, schema `USAGE`를 제거한다.
- downgrade도 세 회수 작업만 반복한다. 이전 노출을 되살리지 않는 security barrier이므로
  `irreversible = True`이고 migration graph는 검토된 정확한 0067 작업 집합만 인정한다.
- 생성 allowlist에서 해당 세 disposition과 모든 `accepted-with-expiry`가 제거됐다.
- collector는 역할을 관측 대상에 유지한다. evaluator는 role 속성·membership, audit-table
  privilege 0, reader policy 0을 원 관측에서 재계산하고 하나라도 되살아나면 `MEASURED_FAIL`이다.
- 제품 문서의 active audit-reader 표현을 제거했다. 읽기 API나 대체 권한은 추가하지 않았다.

# 검증 경계

- 로컬 PG-free: allowlist 생성 14 passed, migration rehearsal 27 passed, aggregator 148 passed,
  collector 25 passed / disposable-PG 8 skipped, security producer 24 passed / disposable-PG
  8 skipped. 변경한 migration-head 소비자 중 Python 3.10에서 실행 가능한 파일은 123 passed다;
  `StrEnum`을 요구하는 파일은 hosted Python 3.12/3.14에서 검증한다.
- 로컬 실 PostgreSQL은 실행하지 않았다. exact-head hosted security lane에서 실제 0067 적용,
  reader SELECT 42501, SEC-RLS-001 재계산을 확인해야 한다.
- allowlist blob을 가리키는 security target과 세 importer pin은 이 코드 commit 뒤 별도 commit에서
  고정한다. 그 전 importer 거부는 의도된 fail-closed 상태다.
- 만료 연장은 없으며 11월 중순 사용자 달력 조치도 제거된다. 점수 변화는 주장하지 않는다.
