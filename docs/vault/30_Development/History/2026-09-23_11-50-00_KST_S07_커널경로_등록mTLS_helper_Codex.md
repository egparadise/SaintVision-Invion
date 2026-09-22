---
doc_id: "HIST-CODEX-S07-CARD17-KERNEL-PATH-PREFLIGHT-001"
title: "S07 Card17 커널 복구 경로와 등록 mTLS preflight helper"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T11:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S07-DB"]
tags: ["history", "s07", "kernel", "five-node", "preflight", "mtls", "statistics"]
---

# S07 Card17 커널 복구 경로와 등록 mTLS preflight helper

## 기준과 결과

- base/integration SHA: `9e3827aca952db91fef305706e63de01baf66318`
- implementation SHAs: `de8a9b7def0fc88ec049057ce32a9dd46415230b`, `58ad1cb03b024bff22bb330a5cf80809e7405314`
- branch/PR: `agent/codex/s07-preflight-v11`, PR #110
- owner/reviewer: Codex / Claude

물리 AC-07 제품 경로는 core replica planner나 새 bridge가 아니라 커널 `inv` 경로로 권고했다. 실 Node heartbeat는 `services/control-plane/src/inv/observation.py`에서 `inv.nodes`를 offline으로 전이하고, `inv/shard_recovery.py`가 source plan/shard를 명시한 fresh approval/run을 만든다. 성공은 `output_ingestion.py`의 receipt-bound byte size/SHA-256·storage object와 `shard_completion.py`의 stored byte 재검증·manifest/hash/evidence commit까지 완결된 경우만 센다. `src/saintvision/services/replica_repair.py`는 assessment/plan이며 byte를 옮기지 않으므로 기존 합성 owner fixture 결과는 개발 proxy로만 유지한다.

`tools/placement_benchmark.py`의 strict inventory parser와 등록/heartbeat/resource snapshot/mTLS read-only 분류를 `tools/five_node_lab_preflight.py`로 동작 보존 추출했다. placement는 그 함수를 import/re-export하므로 두 parser가 생기지 않는다. 공개 report의 `tenantId`를 제거하되 동일 tenant 검사는 내부에서 계속하고, `write_registration_mtls_preflight`는 현재 실행 전에 stale report를 삭제한다. inventory와 report 경로가 같으면 inventory를 지우지 않고 fail closed한다.

## 사양 v1.1 판정

- F-B: 공개 JSON에는 tenant/project ID를 남기지 않는다. Node ID와 공개 certificate SHA-256만 revision-fixed inventory provenance로 허용한다.
- F-C: validation·DB 오류가 나기 전에 이전 report를 삭제하고, 성공한 현재 관측만 다시 쓴다.
- F-D: `19/20`은 시연 임계 통과와 점추정 0.95이지 모집단 성공률 95%의 증명이 아니다. 양측 95% Clopper-Pearson 하한 약 0.751을 병기한다.
- F-E: 이탈은 inventory로 고정한 Ubuntu node-agent container의 bounded `docker stop`(SIGTERM)만 사용한다. volume·journal·키·인증서를 보존하고 rm/prune/reboot/network kill을 금지하며 같은 container의 `docker start`와 identity/baseline 재확인으로 복원한다.
- CE-4: future `--allow-four-node-pilot`은 ADR-100에 따라 겸임 Node가 비활성이고 독립 Ubuntu 4대가 ready일 때만 pilot을 연다. 이 경우에도 `topologyReady=false`, `recoveryWaveReady=false`, `fiveNodeAcceptanceEligible=false`라서 5노드 인수로 승격하지 않는다.

## 검증

환경은 Windows 11, Python 3.14.7 `.venv`, `PYTHONUTF8=1`, `PYTHONPATH=src;services/control-plane/src`다. 실제 Node, Docker, browser와 shard wave는 실행하지 않았다. Codex tab 카드 24의 PG 측정 종료 뒤 disposable 실 PostgreSQL 단일 파일만 순차 실행했다.

| 명령 | 결과 |
|---|---|
| `pytest -q tests/test_placement_benchmark_five_node_adapter.py` | 16 passed, exit 0 |
| `pytest -q tests/integration/test_five_node_lab_preflight.py` | 실 PG 1 passed / 8.47s, exit 0; unique DB/login role 정리 |
| `python -m py_compile tools/five_node_lab_preflight.py tools/placement_benchmark.py` | exit 0 |
| `python tools/placement_benchmark.py --help` | exit 0 |
| `python tools/check_docs.py` | 24 hashes, 884 documents, exit 0 |
| `python tools/check_contract_bindings.py` | 54 fixtures, 19 response types, 25 sites, 14 replay guards, exit 0 |
| `python tools/check_frontend_integrity.py` | 9 rules, 0 violations, exit 0 |
| `python tools/check_ontology.py` | 48 task mappings, 4 rejected fixtures, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | 18 baseline pairs, 0 new, exit 0 |
| `pytest -q tests/test_route_coverage.py` | 39 passed, exit 0 |
| `python tools/check_response_freshness.py` | advisory 10/10, exit 0 |

첫 PG-free pytest 호출은 별도 worktree에 없는 상대 `.venv` 경로를 써 PowerShell command resolution exit 1이었다. 같은 소스에서 프로젝트의 절대 `.venv` interpreter로 재실행한 결과만 제품 회귀 증거로 사용한다.

실 PG 첫 준비 실행은 migration의 정본 Node ID 형식을 쓰지 않아 setup `CheckViolation`으로 실패했고 helper에는 도달하지 않았다. 이 실패 중 pytest가 credential-bearing fixture repr을 로컬 Orca transcript에 렌더링하는 위험을 발견했다. 시험은 fixture를 `request`로 지연 취득하고 `new_id("nod")`를 사용하도록 보정해 실패 표현에 DSN이 들어가지 않게 했으며, 재실행은 5개 실제-shaped node/channel/snapshot row의 read-only `SHOW`, before/after 동일성, ready 5·CP 겸임 1·timed 4, `tenantId` 비출력을 확인했다. 비밀 값은 저장소·History·GitHub artifact에 남기지 않았고 credential 회전 여부는 코디네이터에게 별도 통지했다.

## CI와 인계

PR #110의 첫 code head `de8a9b7d`에서 docs run `35788634457`과 desktop-browser run `35788634538`은 success였고 Backend run `35788634498`은 후속 push로 대체됐다. Core run `35788634458`은 path filter로 skipped라 통과로 세지 않는다. 최종 code head `58ad1cb0`의 CI와 Claude 검토는 진행 중이다. Claude는 helper 추출의 동작 보존, tenant redaction/stale 삭제, 커널 경로 선택과 4-node pilot의 비승격 경계를 독립 검토한다.

다음 첫 행동은 Backend CI 완주와 Claude 검토 확인이다. 이후 별도 승인 카드만 커널 source plan/shard·stop receipt·lease/fence·output storage·ShardCompletion readiness를 포함한 물리 adapter와 wave를 구현한다. S07-DB와 AC-07은 계속 `review`/미측정이다.
