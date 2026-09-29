---
doc_id: "HIST-CODEX-POOL-WRITE-AUTH-CONFLICT-001"
title: "Pool 쓰기 live project 권한 결속과 공개 unique 충돌 번역"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-29T02:34:48+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["security", "authorization", "pools", "integrity-error", "card-122"]
---

# Pool 쓰기 live project 권한·unique 충돌

## 보안 경계

카드 122 감사의 Medium pool 권한 finding을 닫는다. member 추가·삭제는 speculative pool→project read 뒤 project row를 먼저 잠그고, live membership과 `canRequest`를 다시 확인한 다음 pool row를 잠가 project 결속을 재검증한다. membership writer가 같은 project lock을 사용하므로 revoke와 pool write가 엇갈리는 경계를 닫고, 없는 pool·권한 없음·viewer는 모두 같은 `AUTH-PROJECT-SCOPE`로 응답해 존재 oracle을 만들지 않는다.

Claude r1에서 pool로부터 유도한 `project_id`가 기존 `require_project_access`의 `extra.projectId`를 통해 비회원에게 노출되는 차이를 확인했다. pool helper는 `AUTH-PROJECT-SCOPE`만 동일한 extra 없는 오류로 다시 만들고 다른 오류는 전파한다. 실제 `require_project_access`를 통과하는 viewer·비회원과 없는 pool의 전체 ProblemDetails가 같고 `projectId`가 없다는 회귀 시험으로 고정했다.

plan 생성은 위 경계에 더해 run row를 잠그고 run→workload→project가 pool project와 같은지 확인한다. tenant만 같은 다른 project의 run을 pool에 배치하는 기존 공백을 거부한다. 최종 write와 권한 검사는 `get_session`의 같은 transaction 안이다.

## 충돌 번역

- `uq_resource_pools_tenant_id_name`와 `uq_distributed_plans_run_id`만 기존 `GRAPH-INVALID-TRANSITION`/409로 번역한다. constraint allowlist 밖 IntegrityError는 그대로 500이어서 새 DB 결함을 caller 충돌로 숨기지 않는다.
- concurrent first `PUT pool member`는 savepoint에서 primary key 경합을 격리한 뒤 exact `(tenant,pool,node)` row가 실제 보일 때만 idempotent 200으로 인정한다. 다른 constraint나 row 부재는 전파한다.
- storage contribution unique 충돌과 legacy audit/idempotency 중복은 별 후속이다. 이 PR은 pool 보안·동시성 경계만 닫는다.

## 검증

- PG-free: 최초 `tests/core/test_pool_write_security.py` + pool response contract **32 passed**. r1 보완 뒤 보안 단일 파일 **8 passed**, `check_docs`·`check_contract_bindings`·`check_ontology` exit 0이다. project→permission→pool lock 순서, viewer/non-member/absent의 전체 ProblemDetails 동일성, cross-project run 거부, denial-before-side-effect, exact member race, constraint allowlist/unknown 전파를 고정한다.
- real PG `tests/test_pools.py`: owner 허용/viewer 거부, duplicate pool 409, cross-project run 거부, duplicate plan 409을 추가했다. 로컬 DSN 부재로 미실행이며 hosted Core에서 검증한다.
- 공개 schema·migration 변경 0. lock timeout은 legacy lane 공통 결정이므로 이 카드에서 새 canonical error surface를 만들지 않았고 후속 설계 항목으로 유지한다.
