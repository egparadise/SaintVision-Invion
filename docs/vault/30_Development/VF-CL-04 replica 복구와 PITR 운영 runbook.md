---
doc_id: "OPS-VF-CL-04-001"
title: "VF-CL-04 replica 복구와 PITR 운영 runbook"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-18T10:00:00+09:00"
branch: "agent/claude/vf-cl"
task: "VF-CL-04"
source_of_truth: "Git"
tags: ["saintvision", "vf-cl-04", "runbook", "replica", "pitr", "operations"]
---

# VF-CL-04 replica 복구와 PITR 운영 runbook

내 lane 도구를 운영 절차로 묶는다. 실제 byte 전송·node 이탈 판단·backup 매체는 각각 node-runtime(VF-CX-03/04)·heartbeat/containment·운영자 몫이며, 여기서는 관측→판정→조치의 경계를 명확히 한다. 모든 판정은 **기록된 상태**이지 실행 자격 증명이 아니다(`requiresExecutionRevalidation`).

## 1. replica 건강도 관측

- 지표 소스: `services/replica_repair.fleet_replica_summary(tenant, desired)` → `{locations, healthy, underReplicated, atRisk, unreplicated, needingRepair}`.
- 개별: `replica_health(location_id, desired)` → `healthy | under_replicated | at_risk | unreplicated`, `source_nodes`(재확보 원본), `deficit`.
- **ready만 usable로 계수**한다. transferring/stale/corrupt/evicted는 factor를 채우지 않는다.
- replica factor(desired)는 정책 파라미터(기본 2). 실제 per-classification 정책은 운영자/Codex가 정한다.

## 2. 분류별 조치

| 분류 | 의미 | 조치 | 담당 |
|---|---|---|---|
| `healthy` | ready >= factor | 없음 | -- |
| `under_replicated` | 0 < ready < factor | source_nodes에서 부족분만큼 replica 재확보(bounded prefetch). 실 전송은 node-runtime. | VF-CX-03/04 |
| `at_risk` | copy는 있으나 ready 0 (transferring/stale/corrupt) | 긴급: 하나의 node-loss/손상이면 유실. corrupt는 재-verify, transferring은 완료 대기, 없으면 새 원본 필요. | 운영자 + node-runtime |
| `unreplicated` | copy 없음 | 최긴급: 원본 위치 자체가 없음. catalog는 살아 있으나 materialize 불가. | 운영자 + VF-CX |

- `locations_needing_repair(desired, limit)`로 목록을 뽑아 우선순위(unreplicated→at_risk→under_replicated) 처리.

## 3. Node 이탈

- 판단(이탈 여부)은 heartbeat/containment(Codex) 몫. 이탈 확정 시 저장 결과만 기록:
  - `replica_repair.mark_node_replicas_unavailable(node_id, now)` → 그 노드의 ready/transferring replica를 stale로. data_locations·manifest는 불변. 반환값 = 영향 replica 수(blast radius).
- 이후 실행-side 복구는 failed Run이 물리 자원 lease를 release한 뒤 Codex의 replacement-node retry(최대 3 Run, 현재 epoch fencing)로 진행. 저장-side(stale 표시)와 실행-side(retry)는 상보적이며 lease release가 두 단계의 경계다.
- 저장-side 재확보: stale로 빠진 만큼 2절의 under_replicated/at_risk 절차로 replica factor를 회복.

## 4. PITR (backup) readiness

- 도구: `python tools/pitr_readiness.py --dsn <libpq DSN> [--require-pitr]`.
- 판정: possible(archive_mode on + archive_command + wal_level>=replica) / absent(하나라도 결여 → 시점 복구 없음) / inconclusive(설정 미판독 → 미확정, 'no' 아님).
- 논리 dump는 PITR이 아니다 -- dump 시점으로만 복원된다. absent를 backup 있음으로 기록하지 않는다.
- 기본 배포(archive_mode off)는 absent다. PITR을 요구하는 배포는 --require-pitr로 게이트(exit 1 unless possible)한다.
- backup 매체·보존·오프사이트는 운영자 결정. 이 runbook은 readiness 판정만 제공한다.

## 5. 하지 않는 것 (경계)

- byte 전송/replica 생성: node-runtime(VF-CX-03/04). 이 lane은 계획만 낸다.
- node 이탈 판단: heartbeat/containment(Codex).
- 실행 재시도·permit: Codex retry(fencing). permit 전이·취소 override 없음.
- backup 매체/키/오프사이트: 운영자.
- 어떤 관측도 실행 자격이 아니다 -- 실행 직전 물리 bytes 재검증 필요.

## 검증 상태

- replica_health/locations_needing_repair/fleet_replica_summary/mark_node_replicas_unavailable: throwaway postgres:16 8 시험 통과.
- pitr_readiness.assess/read_settings: 9 시험 통과(default 클러스터 absent 실측 포함).
- 로컬 clean-room 검증이며 CI·실장비 인수는 아님.
