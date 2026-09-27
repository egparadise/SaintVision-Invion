---
doc_id: "HIST-20260928-CODEX-S07-FIVE-NODE-DRY-RUN-001"
title: "S07 Card33 5노드 실 Node adapter dry-run 구현"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T00:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S07-DB"]
base_sha: "1e8baf045c5a554209aaef601ae4883b64da50a7"
impl_sha: "4d3221569f991ab2041574972464a9727af5960a"
tags: ["s07", "five-node", "adapter", "dry-run", "postgresql", "read-only"]
---

# S07 Card33 5노드 실 Node adapter dry-run 구현

## 시작 계약

- KST 시작: 2026-09-28 00:20.
- branch/worktree: `agent/codex/s07-five-node-adapter` / `D:\Project\SaintVisionI-Invion\agent-codex-s07-five-node-adapter`.
- 기준: `AGENTS.md`, `GUIDE-001` v1.1.0, `GOV-AGENT-001` v1.1.3, `GOV-GIT-001` v1.1.4, `CODEX-S07-FIVE-NODE-ADAPTER-SPEC-001` v1.1.0, Claude PR #109/카드 23 검토와 PR #110 helper 검토.
- 승인 범위: `measure_s07_recovery.py`의 `five-node-lab + inventory + dry-run`만. Node/Docker 중단·repair·20회 wave·JUnit 실측은 금지, synthetic 기본 동작·공개 계약·registry 불변.

## 구현

- `tools/five_node_lab_preflight.py` writer에 변환 콜백을 추가해 inventory parser, DB SQL, read-only 확인, identity fail-closed, stale report 삭제를 복제하지 않고 재사용했다.
- `tools/measure_s07_recovery.py`는 five-node 경로에서 측정 knob와 JUnit을 거부한다. 공용 관측을 `s07-five-node-preflight:1`로 투영해 provenance·안전 플래그·Node readiness·topology/selection count·CP 겸임 제외·Ubuntu 4대의 future 20회 균등 계획만 기록한다.
- `topologyReady`와 `recoveryWaveReady`는 등록/mTLS 후보 분류다. kernel source plan/shard·stop receipt·lease/fence·storage/shard completion 준비, active health와 operational acceptance는 판정하지 않는다.
- 기존 synthetic adapter는 기본값이며 기존 JSON/JUnit 측정 경로를 그대로 사용한다. 계약/schema/migration/registry/workflow 변경은 없다.

## 검증

환경: Windows, Python 3.14.7, base에서 생성한 전용 Orca worktree. `PYTHONUTF8=1`, `PYTHONPATH=src;services/control-plane/src`. 비밀 DSN 값은 기록하지 않았다.

| 명령 | 결과 |
|---|---|
| `python -m pytest -q tests/core/test_s07_recovery_measurement.py` | 10 passed, exit 0 |
| `python -m pytest -q tests/test_placement_benchmark_five_node_adapter.py` | 16 passed, exit 0 |
| `python -m pytest -q tests/integration/test_five_node_lab_preflight.py` | disposable 실 PostgreSQL 1 passed / 6.65s, exit 0 |
| `python -m py_compile tools/five_node_lab_preflight.py tools/measure_s07_recovery.py` | exit 0 |
| `git diff --check` | exit 0 |
| `python tools/check_docs.py` | 893 versioned documents, exit 0 |
| `python tools/check_contract_bindings.py` | 54 fixtures / 19 types / 25 sites / 14 replay guards, exit 0 |
| `python tools/check_frontend_integrity.py` | 9 rules, 0 violations, exit 0 |
| `python tools/check_ontology.py` | RDF/SHACL/tasks/mirrors pass, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | 18 baseline pairs, none stale, exit 0 |
| `python tools/check_response_freshness.py` | advisory 10/10 present, exit 0 |
| `python -m pytest -q tests/test_route_coverage.py` | 39 passed, exit 0 |

실 PG 시험은 실제-shaped `inv.nodes`·`inv.node_channels`·`inv.node_resource_snapshots` 5행을 난수 tenant/DB/role에 시드했다. adapter 1회 실행 전후 조회 결과가 같고 실제 transaction read-only, ready 5, S07 selected 4, CP 겸임 disruption 0, report의 tenant ID·DSN 비노출을 확인했다. fixture가 disposable DB와 난수 login role을 정리했다.

## 미실행·판정

- 실제 LAN Node와 Docker를 중단하거나 시작하지 않았다.
- kernel offline observer, shard recovery, output byte/hash/receipt, repair 성공률과 JUnit을 실행하지 않았다.
- 20회 중 19회 시연 임계와 Clopper-Pearson 하한은 미래 물리 wave의 규칙일 뿐 이번 결과가 아니다.
- AC-07과 5노드 운영 인수는 미측정, S07-DB는 `review`다. 구현 작성자는 독립 검토를 대신하지 않는다.

## 다음 첫 행동

Claude가 PR 고정 SHA에서 공용 helper 단일성, synthetic 무변경, read-only 무변이, CP 겸임 제외, measurement/JUnit fail-closed를 독립 검토한다. 병합은 사용자가 금지했으므로 코디네이터/사용자 결정 전 수행하지 않는다.
