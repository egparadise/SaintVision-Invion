---
doc_id: "HIST-OFFER-SNAPSHOT-START-20260911"
title: "2026-09-11 OFFER-SNAPSHOT Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T23:49:57+09:00"
source_of_truth: "Git"
---

# OFFER-SNAPSHOT 착수

- 카드 CX-01, 부모 S05-DB/S05-BE/S08-DB, owner Codex, reviewer Claude. base `ade67213501dc7663a80c0580858e31b4d16d9fb`, branch agent/codex/workspace-bridge.
- 공통 진행판 INDEX-PROGRESS-001 v1.0.16, Codex board v1.0.2, GUIDE/GOV-AGENT/GOV-GIT v1.1.0, ADR-INDEX v1.29.0, agent-delivery1.1.0/core-reliability1.0.0을 따른다.
- Claude cdf98ad F1 수신: 제공량 분배의 전체 lease 합과 개별 held 조회 사이 release가 완료하면 기록과 실제가 달라질 수 있다.
- 목표: 실제 HTTP→definer 실행 중 lease release를 겹쳐 재현하고, 하나의 snapshot에서 고정한 held로 분배한다. 기존 migration 원문은 보존한다.
- 합격 증거: 수정 전 실패, 수정 후 동일 경합/tenant/권한/예약 경합/rollback/upgrade·정본 정책/복원 회귀. 운영 DB와 Node에는 적용하지 않는다.
- 구현→고정SHA 시험→commit/push/CI→Obsidian→Claude 재검토. CI 제한/운영 인수와 로컬 성공을 구분한다.

## 실제 재현에 따른 범위 정정

- 23:54 KST: 실제 release 호출은 `_locked_lease`에서 Run→Node→Resource 잠금을 획득한다. d14db0a에도 같은 코드가 있다. 초회 재현은 해제 대기 시간초과 RES-0007로 실패했으며, 기록 1000/적용 900을 재현한 것이 아니다.
- 따라서 이번 단위는 F1 전제의 독립 재검증과 결정론적 경합 회귀 추가로 변경한다. 잠금 제거 변이에서만 시험 실패를 확인하고 원본 bytes를 복구했다. 기존 함수/migration/정책은 변경하지 않는다.
- F1 수정 필요 여부는 이 근거를 받은 Claude가 재검토한다. F2 pre-dispatch intent 감사는 다음 작업으로 유지한다.
