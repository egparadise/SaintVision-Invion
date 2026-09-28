---
doc_id: "HIST-CODEX-CARD36-CX01-HOSTED-CORE-001"
title: "Card36 hosted Core CX01 recovery skip 실행 전환"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T10:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S07-DB"]
tags: ["history", "core", "cx01", "recovery", "ci", "junit"]
---

# Card36 hosted Core CX01 recovery skip 실행 전환

## 범위와 기준선

- base는 PR #117의 `9a837fd7`이며 branch는 `agent/codex/cx01-hosted-core`, owner Codex, reviewer Claude다.
- 목표는 hosted Core의 `CX01_CONTAINER is unset` 19 skip을 mock이나 ownership 단언 완화 없이 CI가 직접 소유한 PostgreSQL 16 컨테이너로 전환하는 것이다.
- 로컬·옛 PC·다른 프로젝트 컨테이너는 검색하거나 재사용하지 않는다. workflow가 run ID/attempt owner label, 고유 이름, tmpfs, loopback host bind, healthcheck, `--cidfile` receipt를 가진 컨테이너 하나를 생성한다.

## 구현과 실패 경계

컨테이너 ID와 두 owner label을 inspect한 뒤에만 `CX01_CONTAINER`와 admin DSN을 job에 전달한다. host pytest는 loopback publish를 사용하고, default bridge의 candidate container는 같은 owned CX01의 inspect된 bridge IP만 받는다. 전체 인터페이스 publish나 runner의 임의 컨테이너 탐색은 없다. 마지막 cleanup은 `if: always()`이며 receipt의 이름과 owner label을 다시 확인한 정확한 ID 하나만 제거한다.

Recovery 파일은 fresh pytest session에서 `dist/cx01-recovery-tests.xml`을 만든 뒤 전체 suite와 분리한다. focused gate는 20 cases, 18 passed, Docker-only internal-network archiver 2 skipped, 0 failed/error를 정확히 요구한다. 이 중 standalone cleanup 1건을 제외하면 기존 setup skip 19건은 17 passed와 2개의 구체적인 body-level 환경 skip으로 바뀐다. backend job은 CX01을 공급하지 않으므로 기존 unset 19 skip을 유지한다.

## red 분류와 격리 근거

첫 run `36351421010`은 owned CX01 생성에는 성공했으나 기존 production-image probe가 bridge gateway를 통해 loopback-only publish에 접속해 red였다. 실패 뒤에도 cleanup은 성공했다. `e9e41c86`은 candidate container에 owned CX01의 정확한 bridge IP를 전달해 이 지점을 통과했다.

두 번째 run `36351804484`는 3,239 passed / 19 skipped / 14 failed였다. 기존 setup skip 19건은 사라졌고 archiver 2건만 구체적인 internal-network 사유로 skip됐지만, recovery 파일이 전체 suite의 공유 session DB 뒤에 실행되어 14건이 fail-closed 했다. 이는 운영 데이터 처리 실패가 아니라 owner-only 부정 시험 오염이다. 로컬의 동일 owned CX01 fresh restore는 1 passed였다. 이어서 `test_shard_completion_rejects_invalid_EvidenceEnvelope_atomically`와 restore를 같은 session에서 실행하자 앞 시험이 trigger를 끄고 만든 orphan `inv.result_commitments` 때문에 다음 FK가 복원 시 거부됐다.

`result_commitments_tenant_id_project_id_run_id_attempt_com_fkey`: commitment의 `(tenant_id, project_id, run_id, attempt, command_id)`에 해당하는 `inv.execution_attempts` 행이 없었다. drill report는 `restoreError=pg_restore_failed`, `restoreExitCode=1`, `integrityVerified=false`로 판정했다. 제품 runtime은 이 owner-only trigger 우회를 만들 수 없고, drill은 손상 source를 통과시키지 않았다. 따라서 recovery를 별도 fresh session으로 분리하되 제품 predicate와 무결성 단언은 변경하지 않았다.

비차단 위생 관찰: 원인을 만든 음성 시험 `test_shard_completion_rejects_invalid_EvidenceEnvelope_atomically`은 DB owner 권한으로 trigger를 비활성화해 orphan commitment를 만든 뒤 같은 session DB에서 그 객체를 정리하지 않는다. 제품 결함과 구분되지만 뒤따르는 무결성·복구 시험을 오염시킬 수 있으므로, 해당 시험 자체의 생성 객체 cleanup 또는 시험별 disposable DB 격리는 별도 test-hygiene 항목으로 남긴다. 이 카드에서는 recovery 파일을 fresh session으로 실행해 제품 판정과 fixture 오염을 분리했고, 음성 시험의 단언은 완화하지 않았다.

## 검증 증거

| 검증 | 결과 |
|---|---|
| `pytest tests/test_core_workflow_cx01.py -q` | 3 passed, exit 0 |
| workflow YAML parse | exit 0 |
| `python tools/check_docs.py` | 893 versioned documents, exit 0 |
| `git diff --check` | exit 0 |
| 로컬 fresh owned CX01 focused restore | 1 passed, exit 0 |
| 로컬 orphan commitment → restore 대조 | 부정 시험 1 passed, restore 1 failed; FK/object 원인 재현 |
| 로컬 진단 컨테이너 정리 | 이름·owner label 재검증 후 제거, inspect exit 1 |
| hosted Core `36351421010` | probe red, always cleanup success |
| hosted Core `36351804484` | 3239 passed/19 skipped/14 failed, setup skip 제거·archiver 2 skip·격리 결함 재현, always cleanup success |
| hosted Core `36353272311` | head `bc27588d`, success, 20m44s; focused 18 passed/2 declared skipped/0 failed·error, main 3236 passed/17 skipped/0 failed·error |
| hosted 후속 단계 | Docker hygiene·exact skip gate·control-plane build·Go test·contracts TypeScript·owned CX01 cleanup·artifact upload 전부 success |
| 로컬 focused | `pytest tests/test_core_workflow_cx01.py -q` 3 passed, exit 0 |
| 문서·계약·무결성 | check_docs 894, contract bindings 54 fixtures/19 types/25 sites, frontend 9 rules, ontology generation/ontology, single-source ratchet 모두 exit 0 |
| route·freshness | route coverage 39 passed; freshness 10/10 report, 각 exit 0 |
| Obsidian | `sync_obsidian.py --check`: 1734 managed, 4 pending exports, 0 conflicts, no writes, exit 0 |
| diff | `git diff --check`, exit 0 |

## 인계와 미완료

Hosted run `36353272311`의 artifact를 직접 파싱해 focused JUnit 20건이 18 passed/2 skipped/0 failed·error임을 확인했다. 두 skip은 모두 owned CX01이 실행 중이고 PostgreSQL-ready log marker가 있으나 host port를 publish하지 않는 Docker internal-network archiver 경계라는 동일한 구체 사유다. main JUnit은 3,253건 중 3,236 passed/17 skipped/0 failed·error이며 정확한 분포는 Windows launcher 10, Windows csc 1, browser opt-in 1, lock-wait 전용 도구 1, 설치되지 않은 agent 네 종류 각 1이다. 기존 `CX01_CONTAINER is unset` 19 skip은 focused evidence에서 0건이다.

구현·hosted CI 증거는 확보했으며 S07-DB의 물리 5노드 인수 상태를 올리지는 않는다. 전체 로컬 게이트와 Obsidian `--check`를 기록한 뒤 Claude가 독립 재검토한다. 사용자가 병합을 금지했으므로 PR을 self-merge하지 않는다.
