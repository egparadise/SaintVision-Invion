---
doc_id: "HISTORY-2026-10-02-S08-BE-BUILDKIT-NODE-RECEIPTS-CODEX"
title: "S08-BE BuildKit node receipt 계약"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-02T08:38:37+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "e8f2eb56c7dde99a5aacda4fed9ca0d9205d7ac5"
task_ids: ["S08-BE"]
tags: ["history", "s08-be", "buildkit", "contract"]
---

# S08-BE BuildKit node receipt 계약

## 선택 근거

PR #306 카드 214 착수 전 질문에서 health receipt, physical cleanup receipt와
`inv.build.dispatch_completed` 세 계약이 구현보다 먼저 필요하다는 계약 owner 판정을 (a)로
확정했다. train 15 후보 `e8f2eb56`에서 외부 전제 없이 contract와 generated binding을 고정할
수 있으므로 이 카드를 먼저 수행했다.

## 변경

- strict `BuildProviderHealthReceipt`, `BuildPhysicalCleanupReceipt`와 그 중첩 daemon/isolation/
  field-source 타입을 추가했다.
- 기존 `BuildCleanupReceipt`에 physical receipt와 canonical digest를 필수화했다.
- `BuildAuditEvent.event=dispatch_completed`와 redacted `BuildDispatchCompletedPayload`를 추가했다.
- DB migration, 제품 flag, caller, route, transport dispatch는 변경하지 않았다. 영속은 기존
  `inv.evidence`와 `inv.outbox`를 재사용하는 계약이다.

## 검증

- `tests/core/test_buildkit_contracts.py`: 78 passed.
- writer/source/isolation/daemon/stop/disposition/unknown·missing field/digest/audit payload 변이가
  각각 거부된다.
- generated Python/TypeScript/Go와 control-plane/node-agent schema를 같은 source에서 다시
  만들었다.
- node mTLS receipt와 물리 cleanup은 이 PR에서 실행하지 않았고 제품 enable은 계속 off다.
