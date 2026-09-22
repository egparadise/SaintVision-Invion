---
doc_id: "HIST-CODEX-2026-09-23-S05-SHORT-COMMIT-F-S05-03"
title: "S05 옵션 1 short-commit 구현과 F-S05-03 경합 재배치"
version: "1.2.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T03:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "83bc1434cba23258627e4aedb86fa9a56088bc46"
implementation_source_sha: "a0f7dba2"
task_ids: ["S05-DB"]
tags: ["placement", "short-commit", "postgresql", "concurrency", "F-S05-03", "feature-flag"]
---

# S05 옵션 1 short-commit 구현과 F-S05-03 경합 재배치

## 결론

코디네이터가 조건부 승인한 옵션 1을 `placementShortCommit` 기본 off flag로 구현했다. 당시 commit lock-hold P95 중앙값은 **1399.883ms → 122.126ms**로 기록됐지만, 카드 19 F-C1에서 legacy만 잠금 대기를 포함한 비대칭 계측임을 확인해 **hold 감소 통과 판정을 철회한다**. 내부 SQL timeout은 legacy 0/0/0건에서 candidate 14/10/11건으로 늘었다. 모두 project limit row 획득의 `55P03`이고 최대 3회 내부 retry가 최종 응답의 실패를 숨겼다. 단계 3 미통과·flag off 결론은 유지한다.

이를 **F-S05-03 경합 재배치**로 기록한다. flag는 켜지 않으며 5노드·50동시 카드로 승격하지 않는다. S05-DB는 `review`를 유지하고 Claude 카드 18 구현 검토 뒤 limit-row 잠금 입도/배치 갱신 또는 내부 retry 없는 fail-fast를 별도 결정한다.

## 구현

- flag off는 외부 동작이 기존 placement와 동등하지만, 내부 구현은 direct lease와 shared admission/prepared primitive를 쓰도록 리팩터됐다. 바이트 무변경이 아니다. 운영자 설정은 strict boolean이며 기본값은 `false`다.
- flag on은 speculative read에서 pool·관측·capacity·Explain을 만들고, final transaction에서 idempotency·Run·네 admission 검사 뒤 project ceiling과 선택 Node/Resource만 잠근다.
- membership, limits, resource offered/capacity, Node heartbeat/skew/epoch, snapshot/channel을 final lock 아래 재검증한다.
- `active_total` 변화 자체는 stale로 취급하지 않고 잠긴 선택 resource에서 fit을 다시 계산한다. fit이 깨지거나 나머지 mutable 입력이 바뀌면 savepoint rollback 뒤 후보 계산부터 최대 3회 재시도한다.
- direct lease와 placement는 `require_execution` → recovery → handoff → start admission 및 prepared lease commit primitive를 공유한다. 중복 project mutex는 flag-on placement에서 제거한다.
- public placement 응답, `ProblemDetails`, idempotency replay, fencing 형식은 바꾸지 않았다. model-retry가 caller-owned outer transaction에서 placement를 호출할 때 stale attempt의 lock/ledger를 savepoint로 해제한다.
- lock-hold metric은 project limit row를 획득한 직후부터 outer commit/rollback까지 측정한다. parameter나 tenant/project/run 식별자를 로그에 넣지 않는다. SQL observer는 실패 statement template·phase·SQLSTATE만 수집한다.

## F-S05-02 반영

83bc1434의 분리 실측에 따르면 project heavyweight Lock 대기는 `lock_timeout=500ms`에서 `55P03`, 비-Lock 서버 대기는 `statement_timeout=2s`에서 `57014`이며 둘 다 `RES-0007` / 503 / retryable이다. 과거 20동시 3건의 `57014`는 당시 wait-event가 없어 project Lock으로 귀속하지 않는다. 이번 단계 3은 오류가 발생한 정확 statement와 SQLSTATE를 observer로 수집했다.

## 실 PG 불변식 시험

- `tests/integration/test_placement_short_commit.py`: 당시 **10 passed / 14.41s / exit 0**. 다만 Claude 카드 18 되살림에서 active fit 재계산과 caller-owned savepoint 제거가 모두 살아남아, 이 두 항목의 시험 무게는 당시 미확인이었다. 카드 16에서 tight-fit과 실제 `55P03` 경계를 추가해 두 mutation을 각각 exit 1로 KILL했다.
- `tests/integration/test_model_retry.py::test_retry_short_commit_flag_preserves_atomic_response_and_replay`: **1 passed / 12.32s / exit 0**. model-retry 응답, exact replay, 새 fencing, frozen input/approval 요구를 보존했다.
- config/benchmark 단위 시험: **33 passed / exit 0**. 구현 뒤 compile과 `git diff --check`도 exit 0이다.
- 각 실 PG 시험과 benchmark는 일회용 DB를 사용했고 fixture가 정리했다. DSN·role password·tenant/project/run 식별자는 문서 증거에 없다.

## 단계 3 비교

조건은 legacy/flag off와 candidate/flag on을 각각 20동시 3회 실행해 lock-hold P95와 `55P03+57014`가 모두 감소하는지 보는 것이다. 성공 수만으로 통과시키지 않는다.

| 모드 | 회차 | 성공/실패 | 요청 성공 P95 | hold p50 / p95 / max | SQL 진단 timeout | exit |
|---|---:|---:|---:|---:|---:|---:|
| legacy | 1 | 20/0 | 2342.143ms | 1068.215 / 1803.721 / 1861.308ms | 0 | 0 |
| legacy | 2 | 20/0 | 1607.483ms | 721.740 / 1325.524 / 1371.845ms | 0 | 0 |
| legacy | 3 | 20/0 | 1771.763ms | 680.040 / 1399.883 / 1533.428ms | 0 | 0 |
| candidate | 1 | 20/0 | 1862.488ms | 43.558 / 118.644 / 147.771ms | `55P03` 14 | 0 |
| candidate | 2 | 20/0 | 1697.737ms | 45.587 / 130.355 / 149.917ms | `55P03` 10 | 0 |
| candidate | 3 | 20/0 | 1656.683ms | 45.939 / 122.126 / 123.818ms | `55P03` 11 | 0 |

요청 P95 중앙값은 1771.763ms에서 1697.737ms로 **74.026ms, 약 4.2%**만 개선됐다. hold P95 1399.883→122.126ms는 비대칭 계측이므로 조건 1 판정은 **미확정**으로 정정한다. timeout 중앙값/합계는 0에서 11/35로 증가해 조건 2는 실패했다. candidate의 timeout statement는 전부 `SELECT * FROM inv.project_resource_limits WHERE project_id=%s FOR UPDATE`다. 대칭 후속은 [[2026-09-23_03-45-00_KST_S05_P1_P2_대칭계측_Codex]]를 따른다.

구현 중 제외한 두 calibration도 숨기지 않는다. `1487a18f` 후보 첫 실행은 active 사용량 변화 자체를 digest 불일치로 보아 3회 재계획을 소진했고 4/20만 성공했다. 이를 잠금 아래 fit 재계산으로 고친 뒤 20/20을 확인했다. `ec0461a1` 한 회는 hold timer가 limit row 획득 대기를 포함해 instrumentation 의미가 달랐으므로, timer를 실제 획득 직후로 옮기고 최종 3회를 새로 실행했다. 구조화 집계는 [[s05-short-commit-stage3-a0f7dba2.json]]이다.

## 착지 전 게이트

최신 integration `7deb0fe4` 위로 rebase해 먼저 착지된 S08 PITR 문서·진행판을 보존한 뒤 실행했다.

- `python tools/check_docs.py`: 846 versioned documents, exit 0
- `python tools/check_contract_bindings.py`: 54 fixtures / 19 types / 25 sites / 14 replay guards, exit 0
- `python tools/check_ontology.py`: 48 task mappings, exit 0
- `python tools/check_doc_single_source.py --ratchet`: 18 baseline pairs, exit 0
- `python tools/check_response_freshness.py`: advisory 10/10, exit 0
- `PYTHONUTF8=1 python tools/check_frontend_integrity.py`: 83 files / 9 rules / 0 violations, exit 0. 최초 기본 cp949 실행은 결과 출력의 `✔` 문자 인코딩에서 exit 1이었고 규칙 위반이 아니므로 UTF-8 환경으로 재실행했다.
- `pytest -q tests/core/test_serving_anchors.py`: 9 passed / exit 0
- `pytest -q tests/test_route_coverage.py`: 39 passed / exit 0
- `git diff --check origin/integration/all-agents-unified`: exit 0

## 판정과 다음 결정 입력

- feature flag 기본 off 유지. 운영 활성화 없음.
- 50동시와 물리 5노드 미실행·미측정. AC-05 판정 없음.
- S05-DB `review` 유지. registry/ontology 변경 없음.
- report schema v1.3에 요청별 limit-row 획득 시도, `55P03` timeout retry 횟수, 대기 p50/p95/max를 별도 필드로 추가했다. 단계 3 원본에는 없던 필드라 값을 소급 생성하지 않았으며, 후속 3동시 smoke는 3/3·exit 0, 대기 p50/p95/max 42.859/162.104/162.104ms, retry 0이었다.
- 후속 옵션은 (1) ceiling 원자성을 보존하는 limit-row 잠금 입도/배치 갱신, (2) 내부 retry를 제거하고 기존 503/retryable을 클라이언트에 즉시 위임하는 fail-fast다. 둘 다 Claude 카드 18 검토와 코디네이터 결정 전 구현하지 않는다.

## 카드 16 F-R3 정정

카드 18은 코드 sound와 공개 계약 불변을 확인했지만, 당시 “반례를 잡는다”는 표현 중 fit 재계산·savepoint 두 건은 되살림 민감도가 없었다. 카드 16은 `offered - need + 1` tight-fit과 BoundDatabase의 실제 limit-row `55P03` 뒤 같은 outer transaction 재호출을 추가해 두 되살림을 각각 실패시켰다. 또한 “flag off 기존 경로 그대로”는 외부 동작 동등성이지 구현 무변경이 아니며, shared primitive 리팩터를 포함한다. 후속 fail-fast·재측정과 현재 판정은 [[2026-09-23_02-50-00_KST_S05_fail-fast_F-R1_F-R2_Codex]]가 정본이다.
