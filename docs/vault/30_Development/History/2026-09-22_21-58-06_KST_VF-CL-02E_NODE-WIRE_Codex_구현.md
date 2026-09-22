---
doc_id: "HIST-CODEX-2026-09-22-VF-CL-02E-NODE-WIRE"
title: "VF-CL-02(e) node-agent wire 계약 소비와 resolver M1 회귀"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-22T21:58:06+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "c97565270e5b1634081e70ddd134f6424bbf2dcd"
implementation_sha: "9c5197744629034b66d4f826e6e93ff4083688a1"
task_ids: ["VF-CL-02"]
tags: ["node-agent", "model-manifest", "wire-contract", "postgresql", "mutation", "authorization"]
---

# VF-CL-02(e) node-agent wire 계약 소비와 resolver M1 회귀

## 작업한 것

- Claude의 카드 3 독립 검토(PR #64)가 살려낸 M1을 먼저 판별 시험으로 고정했다. kernel 관측 뒤 storage contribution의 reader scope만 폐기해 kernel은 ready node를 계속 반환하지만 business resolver는 빈 `readyNodes`와 `materialisable=false`로 강등해야 하는 경로다.
- `services/node-agent/internal/wire`에 `ModelExecutionManifestObservation`을 embedded canonical schema로 검증하고 생성된 `contracts-go` 타입으로 역직렬화하는 경계를 추가했다. 호출자가 고정한 project/model/version/manifest hash와 응답을 대조하고, `executionAuthorized=false` 및 `requiresExecutionRevalidation=true`가 아니면 `NODE-0070`으로 전체 입력을 거부한다.
- 계약 우선으로 Go 소비 시험을 먼저 추가해 `DecodeModelExecutionManifest` 미구현 compile red를 확인한 뒤 구현했다. canonical fixture의 shard/location/ready mapping을 실제 소비하고 project/hash/authority drift를 거부한다.
- canonical schema와 fixture는 카드 2 계약을 그대로 사용했다. `tools/generate_contracts.py` 재실행 뒤 node-agent packaged schema와 `packages/contracts-go/contracts.go`는 내용 drift 0이었고, 누락은 node-agent schema allowlist와 typed 소비 경계였음을 고정했다.
- 아키텍처 정본 `ARCH-MODEL-REGISTRY-BOUNDARY-001`을 1.11.0으로 올려 resolver 관측이 실행 permit이 아니며 node-agent도 identity/hash/권한 플래그를 다시 묶는다는 경계를 기록했다. 기존 commitment와 execution-manifest API는 바꾸지 않았다.

## 확인한 것

환경은 Windows 새 PC, Python 3.14.7, PostgreSQL 16, Go 1.27이다. Python은 `PYTHONPATH=src;services/control-plane/src`, `PYTHONUTF8=1`로 고정했고 실 PG는 `.env`의 `INV_TEST_ADMIN_DSN`을 사용했다.

| 명령/범위 | 결과 |
|---|---|
| 계약 우선 `go test ./internal/wire` | decoder 미구현 compile red 확인 후 구현본 2 passed, exit 0 |
| 실 PG `pytest tests/integration/test_model_uri_resolver_http.py -q` | 원본 1 passed; reader-scope 교집합 두 줄 제거 M1은 ready node 잔존 assertion에서 1 failed; 복원 뒤 1 passed, 0 skipped, exit 0 |
| M1 판별 경계 | kernel `/execution-manifest`는 ready node 유지, business `/models/resolve`는 `readyNodes=[]`, 매핑·전체 `materialisable=false`; M1 KILLED |
| node-agent `go build ./...`, `go vet ./...`, `go test ./...` | 모두 exit 0 |
| `packages/contracts-go` `go test ./...` | exit 0 |
| `python tools/generate_contracts.py` | exit 0; node-agent schema mirror와 Go 생성 타입 drift 0 |
| contract + route focused pytest | 45 passed, exit 0 |
| `python tools/check_contract_bindings.py` | 52 fixtures, 17 response types, 21 anchor sites, 12 replay guards, exit 0 |
| `python tools/check_anchor_weight.py` | 10 rejection-tested, 7 called-only, gap 0, report-only exit 0 |
| `python tools/check_response_freshness.py` | 10/10 present, report-only exit 0 |
| `python tools/check_frontend_integrity.py` | 9 rules, 0 violations, exit 0 |
| `python tools/check_docs.py` | 구현 후보 811 versioned documents, exit 0 |
| `python tools/check_ontology.py` | 48 task mappings, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | 18 baseline pairs, new/stale 0, exit 0 |
| `git diff --check` | exit 0 |

R1 개인 index로 시작 base `c9756527`의 작업을 최신 origin 부모 `80d4e748` 위에 재기준화해 구현 `9c519774`를 만들고 non-force fast-forward push했다. 부모가 추가한 S01 문서 다섯 경로와 이번 제품·경계 문서에는 겹침이 없었다.

같은 SHA hosted CI는 Documentation [35730310514](https://github.com/egparadise/SaintVision-Invion/actions/runs/35730310514), Frontend [35730310623](https://github.com/egparadise/SaintVision-Invion/actions/runs/35730310623), Desktop Browser [35730310535](https://github.com/egparadise/SaintVision-Invion/actions/runs/35730310535), Core [35730310519](https://github.com/egparadise/SaintVision-Invion/actions/runs/35730310519)가 success다. Backend [35730310466](https://github.com/egparadise/SaintVision-Invion/actions/runs/35730310466)은 후속 integration 문서 push 뒤 job 0인 채 한 번 cancelled되어 통과로 세지 않았고, 같은 run/head SHA rerun의 Python matrix 두 job이 모두 success해 최종 run conclusion도 success다.

## 이어서 할 첫 행동과 담당

- **Claude reviewer:** 구현 `9c519774`에서 reader-scope 강등 M1 KILL, embedded schema/생성 Go 타입의 실제 소비, project/model/version/hash 및 비권한 플래그 fail-closed를 독립 검토한다.
- **Codex:** 보고 R1과 Obsidian sync를 마친 뒤 Claude 독립 검토로 인계한다. 작성자가 카드를 `done`으로 self-close하지 않는다.
- **운영 인수:** 이 경계는 resolver 응답의 안전한 wire 소비다. 물리 노드 모델 bytes materialization, signed execution permit, approval/lease/fence 인수는 대체하지 않는다.
