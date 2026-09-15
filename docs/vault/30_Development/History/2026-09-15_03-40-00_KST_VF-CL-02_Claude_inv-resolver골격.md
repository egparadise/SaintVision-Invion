---
doc_id: "HIST-VF-CL-02-001"
title: "VF-CL-02 inv:// resolver 골격 (Claude)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-15T03:40:00+09:00"
base_sha: "de52a03"
branch: "agent/claude/vf-cl"
task: "VF-CL-02"
source_of_truth: "Git"
tags: ["saintvision", "vf-cl-02", "inv-uri", "resolver", "tests"]
---

# VF-CL-02 inv:// resolver 골격 (Claude)

## 목적

VF-CL-02(`inv://` resolver, workspace materialization/write-back)의 **계약 무관 부분**을 기존 substrate 위에서 착수한다. 모델 매니페스트 확장(`kind='model'` URI → shard URI)은 VF-CX-02 계약 대기이므로 만들지 않는다. 별도 Claude worktree `agent/claude/vf-cl`.

## 구현

1. `src/saintvision/storage/pathsafe.py`에 **`parse_uri`** 추가 — `build_uri`의 엄격한 역함수(ADR-010). `ParsedUri` dataclass. round-trip 보장: `build_uri`가 낸 어떤 URI든 `parse_uri`로 읽어 다시 `build_uri`하면 동일. 문법 밖은 추측하지 않고 거부.
2. `src/saintvision/services/resolver.py` 신규 — 기존 `DataLocation`/`DataReplica` 재사용:
   - `resolve_location(session, tenant_id, uri) -> DataLocation`: parse 후 `(tenant_id, uri)` 조회. 미등록은 not-found(빈 성공 아님).
   - `resolve(...) -> (ParsedUri, DataLocation)`.
   - `ready_replica_nodes(...) -> list[str]`: **ready replica를 가진 노드만**. transferring/stale은 읽을 수 없으므로 제외.
   - `is_materialisable(...) -> bool`.
   - **노드 선택(placement)은 하지 않는다** — 서빙 가능한 노드 집합만 반환하고, 어느 노드에서 실행할지는 Scheduler(VF-CX-03) 몫.

## 검증 (throwaway postgres:16)

- `tests/test_uri_resolver.py` **24 passed**:
  - parse_uri: 6종 round-trip(dataset/model/artifact/workspace), 11종 malformed 거부(scheme·namespace·`@version` 누락·segment 수·빈 입력), dataset field 읽기.
  - resolver: 등록 uri 조회 성공, 미등록 uri not-found, malformed uri는 lookup 전 거부, **ready replica만 반환**(node0 ready + node1 transferring → [node0]), catalogued이나 ready 없으면 not-materialisable, **RLS 은닉 실증**(tenant_a id로 조회하되 scope는 tenant_b → WHERE는 매치하나 RLS가 가려 not-found. RLS 없으면 이 시험은 실패한다).
- 회귀 없음: `tests/test_pathsafe.py` 56 passed(내 추가가 기존 깨지 않음), 전체 non-postgres 396 passed(378→396, parse_uri 단위 18개 포함).

## 계약 대기

- `kind='model'` URI → ModelManifest.shards[] 확장은 **VF-CX-02 계약** 착지 후. resolver는 그때 model 경로를 추가한다.
- workspace materialization/write-back(로컬 mount·충돌·rollback)은 다음 VF-CL-02 후속으로, 실행 Node/PTY 계약과 맞물리는 부분은 Codex 경계를 finding으로 보낸다.

## 상태

- `implemented`: `parse_uri`, `services/resolver.py`, 시험.
- `locally_verified`: throwaway postgres 24 passed + 회귀 없음. (실 클러스터·CI 아님.)
- `independently_reviewed`: Codex pending.
- `operationally_accepted`: 미완.

## 다음 첫 행동/담당

- Claude: workspace materialization/write-back 설계 착수(계약 무관 부분), VF-CX-02 착지 시 model 경로.
- Codex: VF-CX-02 계약 제공, VF-CL-01/02 독립 검토.
