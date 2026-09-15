---
doc_id: "HIST-VF-CL-04-001"
title: "VF-CL-04 replica 복구 계획 (Claude)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-15T04:10:00+09:00"
base_sha: "5eea144"
branch: "agent/claude/vf-cl"
task: "VF-CL-04"
source_of_truth: "Git"
tags: ["saintvision", "vf-cl-04", "replica", "repair", "resilience", "tests"]
---

# VF-CL-04 replica 복구 계획 (Claude)

## 목적

VF-CL-04(replica repair, backup/PITR, metrics/runbook)의 **replica repair 부분**을 착수한다. 선행 VF-CL-01 완료, VF-CX-02 불필요 → ready. 아키텍처 rule 3(단일 유실이 전체 유실이 되지 않도록 정책 replica)·rule 6(node 이탈은 replica만 unavailable, manifest 파괴 없음)을 서비스로 구현. 코어 fencing/heartbeat는 건드리지 않는다. 별도 Claude worktree `agent/claude/vf-cl`.

## 구현 (`src/saintvision/services/replica_repair.py`)

기존 `DataReplica`(states: transferring/ready/stale/corrupt/evicted) 재사용. 실제 byte 전송(node runtime, VF-CX-03/04)과 replica factor 정책 값은 경계 밖 — 계획만 낸다.

- `replica_health(location_id, desired=2) -> ReplicaHealth`: ready 수를 replica factor와 비교해 분류 — `healthy`(ready≥desired)·`under_replicated`(0<ready<desired)·`at_risk`(ready=0이나 copy 존재)·`unreplicated`(copy 없음). **ready만 usable로 계수**(transferring/stale/corrupt/evicted는 별도 집계). under-replicated면 재확보 source 노드(ready 보유) 반환.
- `locations_needing_repair(desired, limit)`: tenant의 모든 location 중 repair 필요분. unreplicated 포함(가장 시급).
- `mark_node_replicas_unavailable(node_id, now) -> int`: node 이탈 시 그 노드의 ready/transferring replica를 `stale`로. **data_locations·manifest는 불변**. node 이탈 판단은 caller(heartbeat/containment) 몫이고, 이 함수는 저장 결과만 기록.
- replica factor는 파라미터(기본 2)이며 실제 per-classification 정책은 운영자/Codex 결정.

## 검증 (throwaway postgres:16)

`tests/test_replica_repair.py` **7 passed**:
- ready 2개(desired 2) → healthy, needs_repair False, deficit 0.
- ready 1개 → under_replicated, deficit 1, source_nodes=[해당 노드].
- corrupt+transferring만 → **at_risk**(ready 0, unusable={transferring:1,corrupt:1}, source 없음) — corrupt copy가 있어도 안전으로 보이지 않음.
- replica 없음 → unreplicated.
- `locations_needing_repair`가 healthy 제외(ready를 factor까지 올리면 목록에서 빠짐).
- node 이탈 → 그 노드 copy만 `stale`, **location row 불변**(count=1 유지), health가 손실 반영(ready 1, source=남은 노드), 반환값=1.
- replica factor<1 거부.
- 회귀 없음: 전체 non-postgres 396 passed(모듈 임포트 정상).

## 남은 VF-CL-04 (미착수/blocked)

- **backup/PITR**: 도구 `recovery_drill.py`(`--require-operational-rpo`)는 `review/claude-account-results`에 있고 integration 계열엔 없음. CL-05에서 확인했듯 기본 config는 `archive_mode=off`(PITR 없음). backup/PITR 매체·정책은 운영/배포 결정(blocked). 도구 integration 반영은 후속.
- **metrics/runbook**: 관측 지표·복원 runbook은 후속. replica_health/locations_needing_repair가 그 지표의 소스가 된다.

## 상태

- `implemented`: `services/replica_repair.py`, 시험.
- `locally_verified`: throwaway postgres 7 passed + 회귀 없음. (실 클러스터·CI 아님.)
- `independently_reviewed`: Codex pending.
- `operationally_accepted`: 미완(backup/PITR·metrics는 운영/후속).

## 다음 첫 행동/담당

- Claude: metrics/runbook, backup 도구 integration 반영(계약 무관 부분). VF-CX-02 착지 시 VF-CL-01 model 결속·VF-CL-03 registry.
- Codex: VF-CL-01/02/04 독립 검토, VF-CX-02 계약 제공.
