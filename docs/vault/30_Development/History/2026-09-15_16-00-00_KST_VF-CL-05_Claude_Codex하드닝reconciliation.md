---
doc_id: "HIST-VF-CL-05-004"
title: "VF-CL-05 Codex 하드닝 reconciliation (Claude)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-15T16:00:00+09:00"
base_sha: "9847912"
reviewed_sha: "origin/agent/codex/vf-storage-api"
branch: "agent/claude/vf-cl"
task: "VF-CL-05"
source_of_truth: "Git"
tags: ["saintvision", "vf-cl-05", "reconciliation", "resolver", "replica-repair", "concurrency"]
---

# VF-CL-05 Codex 하드닝 reconciliation (Claude)

## 발견

Codex `agent/codex/vf-storage-api`(및 `vf-replica-observation`)가 **내 `agent/claude/vf-cl` 브랜치를 병합**했다(내 커밋 de52a03·5eea144·68f6036·ae739ee가 그 브랜치의 조상). 내 **시험 4종은 동일하게 유지**됐고, 내 서비스 2개(`resolver.py`·`replica_repair.py`)에 Codex가 **고난도 동시성·보안 하드닝**을 더했다. CLAUDE.md 그대로 — 중난도 서비스는 내가, 고난도 동시성·보안은 Codex가.

## Codex 변경 독립 검토 (verdict: 둘 다 건전, 채택)

1. **`resolver.resolve_location`에 `reader_user_id` 추가**(owner-scoping): 제공 시 그 사용자의 **active contribution**의 location만 보이게. 기본 None은 내 원래 내부-caller 동작(후방호환). VF-CX-02의 owner-scoped storage 규율과 정합. → 건전, RLS 위 추가 인가 계층.
2. **`replica_repair.mark_node_replicas_unavailable`에 `.order_by(replica_id).with_for_update()`**: node-loss 마킹 대상 replica에 행 잠금 + 결정적 순서(deadlock 회피). 동시 node-loss race 방지 — 커널 전반의 FOR UPDATE·lock-order 규율과 일치. → 건전, 내 원본의 미비(무잠금)를 보완.

diff 확인: resolver 28줄·replica_repair 4줄, **정확히 이 두 변경뿐**(숨은 변경 없음).

## 조치

- Codex의 하드닝판 2파일을 내 브랜치에 **채택**(hash 일치 확인). 내 브랜치가 canonical 하드닝판과 일치.
- Codex 추가 보안 동작(owner-scoping) **커버 시험 추가**: `reader_user_id` 소유자는 조회 성공, 동일 tenant 비소유자는 not-found. 내 동일-시험은 None 경로만 덮었으므로 이 새 경로를 보강.
- **검증(throwaway postgres:16)**: 하드닝판에서 resolver+replica_repair 시험 통과(채택 시 32 passed), owner-scoping 추가 후 test_uri_resolver 25 passed.

## 상태

- `independently_reviewed`(Codex의 내-코드 하드닝): **완료**, 둘 다 건전·채택.
- 시그니처 호환성 확인: Codex 진화판의 storage/locality 서비스(register_contribution·catalogue_location·mark_verified·register_replica·mark_replica_ready)는 시그니처 불변 — 내 시험은 CX-01 병합 후에도 작동.
- 이 검토의 재검토는 Codex/타 Agent.

## 다음 첫 행동/담당

- Codex: `vf-storage-api`/`vf-replica-observation`를 CX-01로 integration에 병합(내 VF-CL 작업 포함). VF-CX-02 finding 1·2 결정.
- Claude: 병합 후 storage HTTP API(`/v1/storage/*`) 시험·record_deployment 등 잔여 substrate acceptance. Codex finding 2 결정 오면 VF-CL-03 license 결속.
