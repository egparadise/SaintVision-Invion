---
doc_id: "HIST-CODEX-S05-CARD26-BOUNDED-SEMAPHORE-IMPLEMENTATION-001"
title: "S05 Card26 project별 bounded semaphore 구현"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T15:27:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["history", "s05", "placement", "semaphore", "fail-fast", "implementation"]
---

# S05 Card26 project별 bounded semaphore 구현

## 범위와 상태

- branch: `agent/codex/s05-bounded-semaphore`
- base: `1e8baf045c5a554209aaef601ae4883b64da50a7`
- owner/reviewer: Codex/Claude
- registry: S05-DB `review` → `in_progress`, next handoff `Claude — Card26 project별 bounded semaphore 구현 검토`
- delivery: R2 PR, integration 직접 착지·병합 없음

Card25 사양 §4~§8에 따라 candidate short-commit 신규 예약 앞에 canonical `(tenant_id, project_id)`별 process-local permit을 구현했다. 상한 N의 첫 실험값은 4이고 permit queue/future/sleep 없이 즉시 획득 또는 거절하므로 논리적 permit wait는 0ms다. production 설정에는 노출하지 않았고 private flag 기본값은 off다.

## 구현 경계

- commit된 exact replay와 changed-body 409 분류는 permit보다 먼저 수행한다. 신규 candidate 예약만 project/limits writer lock 전에 permit을 획득한다.
- permit은 placement 함수 반환이나 savepoint 종료가 아니라 root transaction commit/rollback 뒤 finalizer가 정확히 한 번 반환한다. `BoundDatabase` 재진입은 root permit 하나를 공유한다.
- commit, DomainError rollback, 일반 exception, cancellation, BaseException 종료를 분류하고 entry count가 0이면 process registry에서 제거한다.
- 상한 초과 공개 표면은 기존 `RES-0007`, HTTP 503, `retryable=true` 그대로다. 내부 reason과 metric에는 tenant/project/principal/idempotency key를 넣지 않는다.
- benchmark schema 1.8은 acquired/reentrant/rejected/released, permit hold, release cause와 registry residue를 기록한다. 성능 게이트의 외부 실패 합계는 `semaphore reject + 55P03 + 57014`이며 빠른 503을 성공으로 세지 않는다.
- migration, 공개 schema/route/response field/error code, candidate lock budget은 변경하지 않았다.

## 실제 검증

실행한 PG-free focused 검증은 다음과 같다.

| 검증 | 결과 |
|---|---|
| `py_compile` (변경 Python 파일) | exit 0 |
| 신규 semaphore focused 시험 | 26 passed, exit 0 |
| semaphore + lock-budget + model-registry + 응답 계약 focused suite | 101 passed, exit 0 |
| Black check (변경 Python 파일) | exit 0 |
| `git diff --check` | exit 0 |
| ontology 생성 | schema 405/data 916 triples, exit 0 |
| `check_docs.py` | 893 versioned documents, exit 0 |
| `check_contract_bindings.py` | 54 fixtures/19 response types/14 replay guards, exit 0 |
| `check_ontology.py` | RDF·SHACL·48 task mappings·mirror, exit 0 |
| `check_doc_single_source.py --ratchet` | 18 pairs, exit 0 |
| `PYTHONUTF8=1 check_frontend_integrity.py` | 0 violations, exit 0 |

PG-free 시험은 N=1/3/4 즉시 거절, tenant/project 격리, commit/rollback/cancel/BaseException release, reentrant/savepoint 경계, exact replay/changed-body 선행, metric redaction, 독립 registry의 `2N` 부정 대조군과 benchmark CLI opt-in을 포함한다.

## 미실행과 다음 단계

실 PostgreSQL focused 시험과 legacy/candidate-B 20동시 wave는 **실행하지 않았다**. idempotency/Lease/event 잔존 0, outer transaction 실 DB release, fencing/RLS/no-overbooking 보존과 세 성능 조건은 코디네이터 승인 뒤 disposable DB에서 확인한다. 20동시 초과, 50동시, 물리 5노드는 승인 범위가 아니다.

R2 PR에서 Claude가 root finalizer, replay-before-permit, process-local 한계, 공개 계약 불변과 시험 강도를 검토한다. flag는 off, S05-DB는 `in_progress`를 유지하며 검토만으로 `review`나 `done`으로 올리지 않는다. 정본 사양은 [[S05 project별 bounded semaphore 사양]]이다.
