---
doc_id: "HIST-CODEX-FIVE-NODE-PREFLIGHT-PG-GATE-001"
title: "5노드 등록 mTLS preflight 실 PostgreSQL 영구 게이트"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T12:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S07-DB"]
tags: ["history", "s07", "five-node", "postgresql", "ci", "preflight"]
---

# 5노드 등록 mTLS preflight 실 PostgreSQL 영구 게이트

## 결과

카드 17 PR #110의 `tests/integration/test_five_node_lab_preflight.py`를 영구 실 PostgreSQL 경계로 고정했다. shared disposable fixture가 unique database와 난수 login role을 만들고 migration head를 적용한 뒤 `inv.tenants`, `inv.nodes`, `inv.node_channels`, `inv.node_resource_snapshots`에 5개 실제-shaped identity를 시드한다. `write_registration_mtls_preflight` 1회 뒤 DB before/after row가 같고 `databaseReadOnly=true`, report의 tenant ID·DSN 부재, ready 5·CP 겸임 1·독립/timed 4를 단언한다. fixture는 database와 role을 정리한다.

Backend CI는 PostgreSQL을 제공하므로 이 시험을 skip해서는 안 된다. `.github/workflows/backend.yml`의 exact skip `Counter`에 local PG-free 사유 `Set INV_TEST_ADMIN_DSN to a disposable PostgreSQL 16+ test server`를 **expected 0**으로 등록했다. Python `Counter`에서 absent와 zero는 동일하되 실제 1 skip은 drift로 실패하므로 ratchet을 우회하거나 skip을 통과로 세지 않는다.

[[S07 5노드 실 Node adapter 사양]] v1.1.1은 `services/control-plane/src/inv/observation.py:146`의 `interval '60 seconds'` 하드코드를 명시했다. 물리 AC-07 감지는 이 predicate를 더 짧게 해석하지 않고 60초 liveness timeout + observer poll 간격으로 판정하며, 등록 preflight의 15초 freshness와 구분한다.

## 증거와 정직성

- base stack: PR #110 rebased head `034413fced9607cec8a326b107627c3dcdafa4a6`
- implementation commits: `ad715574`, `3640c180`
- 실 PG: `pytest -q tests/integration/test_five_node_lab_preflight.py` → 1 passed / 8.76s / exit 0, disposable DB/role 정리. serialized report에서 tenant UUID·`tenantId`·full DSN 부재를 직접 단언
- PG-free: `pytest -q tests/test_placement_benchmark_five_node_adapter.py` → 16 passed / exit 0
- no-DSN: integration file 1 skipped / exit 0, exact declared local reason 확인
- Backend skip baseline zero-count 의미 대조, workflow YAML parse, `check_docs.py` 886 documents, `git diff --check` → exit 0

실 Node, Docker, heartbeat 갱신, 이탈·복구 wave는 실행하지 않았다. 실 PG 첫 준비 실패에서 credential-bearing fixture repr 위험을 발견해 시험은 `request.getfixturevalue("postgres")`로 지연 취득하도록 고정했다. 비밀 값은 저장소·artifact에 남기지 않았고 로컬 transcript 노출에 대한 credential 회전 여부는 코디네이터 판단 대기다.

다음 담당은 Claude 독립 검토다. Hosted Backend에서 이 시험이 skip 0으로 실행되고 전체 exact skip map이 유지되는지 확인한 뒤에만 병합한다. S07-DB `review`, AC-07 물리 미측정은 불변이다.
