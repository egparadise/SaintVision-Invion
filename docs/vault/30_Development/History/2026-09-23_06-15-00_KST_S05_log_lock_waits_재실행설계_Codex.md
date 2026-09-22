---
doc_id: "HIST-CODEX-2026-09-23-S05-LOCK-WAIT-DIAGNOSTIC-DESIGN"
title: "S05 log_lock_waits 재실행 카드 설계"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T07:00:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "4143f375a2198572455a442cf2d80086d70f5b6b"
task_ids: ["S05-DB"]
tags: ["placement", "postgresql", "log-lock-waits", "deadlock-timeout", "workflow-dispatch", "design-only"]
---

# S05 log_lock_waits 재실행 카드 설계

## 결과

Card19의 depth-1·waiter 19·timeout 0 관측과 Claude 카드 21의 KEY SHARE/tuple-FIFO 우회 probe 가설을 제품에서 반증 가능하게 확인하는 [[S05 log_lock_waits opt-in 재실행 설계]] v1.1을 작성했다. 실행은 하지 않았고 제품 코드·계약·migration·workflow도 변경하지 않았다.

- disposable `inv_test_<uuid>` DB에만 `ALTER DATABASE ... SET log_lock_waits=on`, `deadlock_timeout=50ms`를 적용하고 새 runtime session의 SHOW로 확인한다. `ALTER SYSTEM`, config 편집/reload/restart, 운영 DSN은 금지한다.
- legacy 20동시 1 wave에서 request별 application name, server lock-wait/acquired pair, `pgrowlocks('inv.projects')`를 연결한다. holder별 다른 xid segment 반복·tuple wait 0·다수 Key Share+하나 No Key Update·55P03 0을 함께 본 경우만 `KEY_SHARE_RESET_SUPPORTED`다.
- sampler 5ms는 명목값이고 Card19 실제 간격은 약 17ms다. 0.793ms arrival spread는 client barrier 기준이며 DB 첫 Lock 표본은 515ms였다. 다른 role/DB PID가 표본 밖이면 depth가 끊기는 O-c는 전용 DB/role과 invalidation 조건으로 차단한다.
- 후속 옵션은 (A) limits 최종 lock까지 `FOR NO KEY UPDATE`로 낮추는 선행 약한 잠금 변형과 (B) FIFO queue 깊이 상한으로 분리했다. KEY SHARE 뒤 기존 `FOR UPDATE`는 교착 가능성 때문에 제외하고, A의 기아·thundering herd·fail-fast 상충과 B의 admission 원자성을 판정 기준·rollback에 명시했다.
- CI는 integration/Core 자동 lane이 아닌 Environment 승인형 `workflow_dispatch` 별도 workflow를 제안했다. 정확한 승인 SHA, pinned Postgres image, 단일 integration file, raw log/PID map 미업로드를 고정했다.
- 제안 runner·parser와 workflow는 미구현이고 실제 실행은 coordinator의 명시 승인 뒤 별도 카드다. Claude의 실수로 수행된 50동시 1회는 절차 이탈로만 남기며 그 수치는 이 설계의 근거에 사용하지 않는다. 현재 flag off·S05 `review`·candidate/50/5노드 미승격이다.

## 검증 범위

Card20 자체는 docs-only라 PostgreSQL·부하·빌드·브라우저를 실행하지 않았다. PR #96 계약 교차검토를 위해 focused `tests/core/test_pool_placement_response_contract.py`와 `tests/test_route_coverage.py`만 실행해 63 passed/exit 0을 확인했다. reviewer는 Claude다.

| 검증 | 결과 |
|---|---|
| `python -m pytest -q tests/core/test_pool_placement_response_contract.py tests/test_route_coverage.py` | 63 passed, exit 0 |
| `python tools/check_docs.py` | 최신 integration tip `bab8f76f` 위 R1 합성 트리에서 24 original hashes, 868 versioned documents, 48 tasks, 12 outcomes, exit 0 |
| `python tools/check_contract_bindings.py` | 54 fixtures, 19 bound response types, 14 replay guards, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | 18 pairs, exit 0 |
| `D:\Project\SaintVisionI-Invion\.venv\Scripts\python.exe tools/check_ontology.py` | 48 task mappings, SHACL/competency/Obsidian mirror PASS, exit 0 |
| `python tools/check_response_freshness.py` | 10/10, exit 0 |
| `PYTHONUTF8=1 python tools/check_frontend_integrity.py` | 9 rules, 0 violations, exit 0 |
| `python tools/export_schemas.py --check` | 58/58, exit 0 |

시스템 `python`의 최초 ontology 호출은 `rdflib` 미설치로 import 단계 exit 1이었다. 이는 ontology 내용 실패가 아니며, 저장소 공용 문서 venv(`rdflib 7.1.4`)로 같은 게이트를 재실행해 위 exit 0을 얻었다.

현재 오래된 Orca worktree에는 `bab8f76f`에서 새로 들어온 LAN pilot History가 없어, 최신 작업판을 보존해 합친 뒤 로컬 checkout에서만 `check_docs`를 실행하면 그 링크가 깨진다. 따라서 R1 private-index 합성 commit을 별도 shared clone으로 checkout해 위 문서·계약·ontology·ratchet·freshness·frontend·schema 게이트를 모두 다시 실행했고 exit 0을 확인했다. 이 검증은 최신 tip의 다른 작성자 파일을 작업판 갱신 과정에서 덮어쓰지 않았음을 함께 확인한다.

## 병행 PR #96 백엔드 계약 검토

- 대상 head `90991423c1f9a7f79760311ebb84db4be7e6c680`, 판정은 **수정 요청**, 코멘트는 <https://github.com/egparadise/SaintVision-Invion/pull/96#issuecomment-5783083226>이다.
- 정합: `/v1/pools`·capacity·placement-preview·plans 라우트, 3원 용량, 120초 freshness, idle-first 정렬, preview 실패 시 미검증 상태 제거, 분할 선언·부분 배치 거부.
- 문서 정정: strict PoolListResponse 필수 필드 누락, 미존재 pool은 404가 아니라 `RES-NODE-NOT-FOUND`/409, 실제 AUTH 부정 시나리오 누락, `RES-PARTITION-EXHAUSTED`를 pool route 오류처럼 열거한 표현.
- 계약/어댑터 정정: preview는 후보만 반환하는데 UI가 `shd_*`를 합성해 Zero Fake Shards와 모순한다. UI `spread|binpack`은 서버 `single_node|data_parallel|sharded`와 맞지 않아 정상 plan 201에 도달하지 못한다. 관측 전용 node 편입은 client guard뿐이고 server 직접 호출을 막지 않는다.
- `core.schema.json`의 ResourceOffer는 `capacity`와 `offered`를 각각 제한하지만 상호 대소를 표현하지 않는다. offered≤capacity는 node 등록 서비스 경계에서 검증되며 pool response 자체의 단언으로 승격하지 않는다.
