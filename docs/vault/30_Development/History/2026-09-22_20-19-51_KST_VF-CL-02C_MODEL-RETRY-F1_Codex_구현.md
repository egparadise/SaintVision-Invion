---
doc_id: "HIST-CODEX-2026-09-22-VF-CL-02C-MODEL-RETRY-F1"
title: "VF-CL-02(c) 실행 Manifest 관측 계약과 model-retry F1 보정"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-22T20:19:51+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "b877c601f8e981c960a4f3d33f3af6bcb33e18fe"
implementation_sha: "4473c7f1668eb3ea459b217d6af59bb9e6c113d3"
task_ids: ["VF-CL-02", "MODEL-RETRY-F1"]
tags: ["model-manifest", "authorization", "postgresql", "contract", "serving-anchor"]
---

# VF-CL-02(c) 실행 Manifest 관측 계약과 model-retry F1 보정

## 작업한 것

- `POST /v1/projects/{project}/runs/{parent}/model-retries`가 타 tenant의 보이지 않는 project를 idempotency ledger에 먼저 기록하다 FK/RLS 예외로 `503 SYS-0001`을 내던 순서를 보정했다. ledger 이전에 기존 `can_request` grant 경계를 확인하고, 본 트랜잭션의 재확인은 유지해 권한 철회 race를 열지 않았다. HTTP 결과는 기존 존재 노출 정책과 같은 `403 AUTH-0030` ProblemDetails다.
- `GET /v1/projects/{project}/models/{modelId}/versions/{version}/execution-manifest`를 추가했다. 응답은 `manifestHash`, 연속 `ModelShard[]`, `shardIndex/locationId/locationVersion`, `readyNodes`, `materialisable`, `observedAt`을 strict 계약으로 고정하고 실행 권한이 아님을 `executionAuthorized=false`, `requiresExecutionRevalidation=true`로 명시한다.
- manifest와 저장 mapping의 집합이 다르거나 shard가 빠지면 전체 요청을 `409 MODEL-0001`로 거부한다. replica가 stale이거나 location version이 바뀌었거나 ready replica가 없으면 해당 mapping을 `readyNodes=[]`, `materialisable=false`로 명시한다. 기존 commitment API와 `currentAvailability=unknown` 의미는 변경하지 않았다.
- 커널은 새 `SECURITY DEFINER` 함수의 tenant-bound 최소 projection만 호출한다. `inv_kernel`에 `public.data_replicas` 원시 SELECT를 주지 않았고 `inv_app`에는 함수 EXECUTE도 주지 않았다. group role 변경은 없다.
- JSON Schema, Python/TypeScript/Go 생성 타입, fixture, 실 PostgreSQL HTTP serving-anchor, route coverage, freshness report-only 기준선과 아키텍처 경계 문서를 함께 갱신했다.

## 확인한 것

환경은 Windows 새 PC, Python 3.14.7, `.env`의 `INV_TEST_ADMIN_DSN` PostgreSQL 16이며 모든 Python 실행에 `PYTHONPATH=src;services/control-plane/src`, `PYTHONUTF8=1`을 사용했다. 전체 suite는 메모리 경보 지시에 따라 실행하지 않고 단일 파일·게이트만 순차 실행했다.

| 명령/범위 | 결과 |
|---|---|
| `python tools/generate_contracts.py` 두 번째 실행 전후 생성물 SHA-256 비교 | exit 0, drift 0 |
| `pytest tests/core/test_model_execution_manifest_contract.py tests/test_route_coverage.py tests/test_migrations.py tests/test_response_freshness.py -q` | 68 passed, exit 0 |
| `pytest tests/integration/test_model_execution_manifest_http.py -q` (`INV_TEST_ADMIN_DSN`) | 2 passed, 0 skipped, exit 0 |
| `python tools/check_contract_bindings.py` | 52 fixtures, 17 response types, 20 anchor sites, 12 replay guards, exit 0 |
| `python tools/check_anchor_weight.py --modules model_view` | rejection-tested 1, called-only 1(기존 commitment), gap 0, exit 0 |
| `python tools/check_frontend_integrity.py` | 9 rules, 0 violations, exit 0 |
| `python tools/check_docs.py` | 797 versioned documents, exit 0 |
| `python tools/check_ontology.py` | 48 task mappings, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | 18 baseline pairs, new/stale 0, exit 0 |
| `python tools/check_response_freshness.py` | 10/10 present, report-only, exit 0 |
| `git diff --check` | exit 0 |

R1은 부모 `b877c601`에서 개인 index로 작성한 `4473c7f1`을 non-force fast-forward push했다. 같은 SHA hosted CI는 Documentation [35720753478](https://github.com/egparadise/SaintVision-Invion/actions/runs/35720753478), Frontend [35720753415](https://github.com/egparadise/SaintVision-Invion/actions/runs/35720753415), Desktop Browser [35720753385](https://github.com/egparadise/SaintVision-Invion/actions/runs/35720753385)가 success이며 Backend [35720753407](https://github.com/egparadise/SaintVision-Invion/actions/runs/35720753407), Core [35720753383](https://github.com/egparadise/SaintVision-Invion/actions/runs/35720753383)는 이 기록 갱신 시 pending이다.

## 이어서 할 첫 행동과 담당

- **Claude reviewer:** `4473c7f1`에서 타 tenant 403 존재 노출 정책, SECURITY DEFINER의 tenant binding·권한 최소성, missing mapping 전체 409, stale/ready 판정을 독립 검토한다.
- **Codex:** 남은 hosted Backend/Core 2개를 같은 SHA로 확인하고 최종 상태를 이 History와 작업판에 반영한다. 이 카드는 작성자가 `done`으로 self-close하지 않는다.
- **운영 인수:** 물리 노드/실 replica fleet 인수는 별도이며 이번 단일 PC PostgreSQL 증거로 대체하지 않는다.
