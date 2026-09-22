---
doc_id: "HIST-CODEX-2026-09-22-VF-CL-02D-INV-URI-RESOLVER"
title: "VF-CL-02(d) inv URI resolver 운영 바인딩"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-22T21:18:16+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "e31ce3f317d529142527c7e7e9f14f89551f3765"
implementation_sha: "b06fc199da02a59165bccd5cd11ab1287e78183b"
task_ids: ["VF-CL-02"]
tags: ["inv-uri", "model-manifest", "authorization", "postgresql", "contract", "replay-guard"]
---

# VF-CL-02(d) inv URI resolver 운영 바인딩

## 작업한 것

- `GET /v1/projects/{project}/models/resolve?uri=inv://models/<name>@<version>/<path>`를 추가했다. 응답은 카드 2의 strict `ModelExecutionManifestObservation`을 그대로 사용하며 기존 commitment와 execution-manifest API를 바꾸지 않았다.
- 커널의 현재 `can_request`와 linked business permission을 모델 조회 전에 확인하고, `resolve_model`의 주입식 reader에는 매 요청 새 `ModelExecutionManifestObservation.get`을 연결했다. 성공 결과를 idempotency ledger나 메모리에서 재생하지 않는다.
- 별도 restricted `inv_app` engine에서 public model을 `(tenant, project, name, version)`으로 찾고, 커널이 보고한 모든 location/version/ready node를 RLS와 기존 reader scope로 다시 확인한다. 최종 `readyNodes`는 두 관측의 교집합이며 stale·version drift·ready 소실은 빈 배열과 false로만 강등한다.
- `resolve_model`은 기존 immutable `ModelManifest` reader와 새 strict observation reader를 모두 지원한다. 새 `LocationResolution`은 business-role 재검사 결과를 명시하며 기존 호출자의 반환 의미와 시험 7개는 유지했다.
- core.schema의 기존 계약 설명, packaged schema, fixture 기반 계약 시험, 두 번째 serving anchor, rejection-weight 시험, route coverage와 아키텍처 경계 문서를 함께 갱신했다. 생성 TypeScript/Go 형태는 이미 동일 계약을 표현하므로 내용 drift 없이 재생성됐다.

## 확인한 것

환경은 Windows 새 PC, Python 3.14.7, PostgreSQL 16이고 Python 실행은 `PYTHONPATH=src;services/control-plane/src`, `PYTHONUTF8=1`로 고정했다. 메모리 경보 지침에 따라 전체 pytest는 실행하지 않고 단일 실 PG 파일과 관련 게이트만 순차 실행했다.

| 명령/범위 | 결과 |
|---|---|
| `pytest tests/integration/test_model_uri_resolver_http.py -q` | 실 PG 1 passed, 0 skipped, exit 0 |
| 위 실 PG 시험의 권한 경계 | 난수 login role 생성·정리, `inv_app`의 `inv.model_manifests` 직접 SELECT 거부, tenant 미설정 public model 0행, 타 project `403 AUTH-0030`, 권한 scope 미존재 `404 MODEL-0004` |
| 위 실 PG 시험의 replay/stale 경계 | 성공 뒤 동일 요청에서 membership 폐기 시 `403 AUTH-0030`; replica stale 뒤 `readyNodes=[]`, 매핑·전체 `materialisable=false` |
| 관련 네 파일 focused pytest | 53 passed, exit 0 |
| `python tools/generate_contracts.py` 재실행 | exit 0, 생성 drift 0 |
| `python tools/check_contract_bindings.py` | 52 fixtures, 17 response types, 21 anchor sites, 12 replay guards, exit 0 |
| `python tools/check_anchor_weight.py --modules model_uri_resolver` | 1 rejection-tested, called-only/named-only/gap 0, report-only exit 0 |
| `python tools/check_response_freshness.py` | 10/10 present, report-only exit 0 |
| `python tools/check_frontend_integrity.py` | 9 rules, 0 violations, exit 0 |
| `python tools/check_docs.py` | 800 versioned documents, exit 0 |
| `python tools/check_ontology.py` | 48 task mappings, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | 18 baseline pairs, new/stale 0, exit 0 |
| standalone TypeScript `tsc --noEmit` / `packages/contracts-go go test ./...` | 각각 exit 0 |
| `git diff --check` | exit 0 |

R1 개인 index로 부모 `e31ce3f3`에 구현 `b06fc199`를 만들고 non-force fast-forward push했다. 같은 SHA hosted CI는 Backend [35726028276](https://github.com/egparadise/SaintVision-Invion/actions/runs/35726028276), Documentation [35726028423](https://github.com/egparadise/SaintVision-Invion/actions/runs/35726028423), Frontend [35726028287](https://github.com/egparadise/SaintVision-Invion/actions/runs/35726028287), Desktop Browser [35726028426](https://github.com/egparadise/SaintVision-Invion/actions/runs/35726028426)가 success다. Core [35726028397](https://github.com/egparadise/SaintVision-Invion/actions/runs/35726028397)는 후속 integration push로 cancelled되어 통과로 세지 않는다.

## 이어서 할 첫 행동과 담당

- **Claude reviewer:** 구현 `b06fc199`에서 두 DB role의 권한 경계, project-first 비노출, observation 교집합, 성공 후 권한 폐기 replay guard를 독립 검토한다.
- **Codex:** 보고 커밋·Obsidian sync까지 착지하고 Claude 독립 검토로 넘긴다. 작성자가 카드를 `done`으로 self-close하지 않는다.
- **운영 인수:** 이 시험은 단일 PC disposable PostgreSQL 증거다. 물리 노드의 실제 모델 bytes materialization과 실행 permit 인수는 대체하지 않는다.
