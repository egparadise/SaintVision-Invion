---
doc_id: "HISTORY-CARD267-AC11-POST-LANDING-EXACT-SHA-ORCHESTRATION-CODEX"
title: "Card 267 AC-11 착지 직후 exact-SHA orchestration 결속"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-03T17:09:36+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "9e9a551cd25b9a237d5d439c317854d927a5640d"
task_ids: ["CARD-267", "S11-BE", "AC-11"]
tags: ["ac11", "post-landing", "exact-sha", "orchestration", "codex"]
---

# Card 267 AC-11 착지 직후 exact-SHA orchestration 결속

## 선택 근거와 범위

train 42 `9e9a551cd25b9a237d5d439c317854d927a5640d`의 착지 직후 정본은
`tools/post_landing_lane_guard.sh` 안에 security와 accessibility 두 producer만 다시 구현하고
migration rehearsal을 누락했다. 카드 260의 `tools/run_ac11_exact_sha_aggregate.py`는 이미 정본
source map에서 세 producer를 읽고 run/SHA/ref/attempt, artifact expiry/digest/run binding, prior
non-success, 중복 후보, aggregate 재계산을 fail-closed로 수행한다. 카드 267은 evaluator,
schema, target, workflow와 migration을 바꾸지 않고 runbook이 그 단일 구현을 사용하게 한다.

## 변경

- `ac11_dispatch_in_order`에서 별도 producer 목록과 직접 `gh` dispatch를 제거했다. 함수는 landed
  SHA, integration ref, repository, receipt path를 exact-SHA orchestrator에 한 번 전달한다.
- runbook §5에 migration rehearsal producer를 명시하고 출력 형식을 TSV run 목록에서 redacted
  orchestration receipt JSON으로 바꿨다. `INVALID_RUN`도 canonical recomputation 결과이며 점수
  승격이 아니라는 경계를 유지했다.
- shell boundary 시험은 canonical orchestrator가 정확한 인자로 한 번 호출되고 직접 `gh` 호출이
  0건인지, orchestrator refusal이 그대로 전달되는지, 짧은 SHA가 orchestrator에 도달하지 않는지
  실행한다.
- 카드 260 fake-gh 시험은 security, accessibility, migration rehearsal 각각이 누락됐을 때 그
  producer 하나와 aggregate만 dispatch하는 parameterized 회귀로 확장했다. 기존 prior failure,
  duplicate, expiry, run/ref/SHA, aggregate canonical recomputation 시험은 그대로 사용한다.
- Claude r1 뒤 새로 dispatch한 producer가 실패하거나, 끝나지 않거나, 목록에 나타나지 않는 세
  경우를 각각 거부하고 aggregate dispatch가 0임을 고정했다. runbook은 `$LAND`로 clean detached
  checkout한 뒤 그 tree의 guard를 다시 읽으며, orchestrator 경로 override는 명시적 test seam
  밖에서 거부한다.

## 로컬 검증

| 명령 | 결과 | 환경 |
|---|---|---|
| `python -m pytest -q tests/test_post_landing_lane_guard.py` | `24 passed` | Windows, Git Bash 실실행, skip 0 |
| `python -m pytest -q tests/test_run_ac11_exact_sha_aggregate.py` | `40 passed` | Windows, fake-gh, skip 0 |
| `bash -n tools/post_landing_lane_guard.sh` / orchestrator `--help` / `git diff --check` | exit 0 | shell·CLI·whitespace gate |
| `python tools/check_docs.py` | PASS | 24 original hashes, 1129 versioned documents |
| `python tools/check_ontology.py` | PASS | RDF/SHACL/48 task mappings |
| `python tools/sync_obsidian.py --check` | exit 0 | 2035 managed, 133 pending exports, conflict 0, write 0 |

첫 guard 실행에서는 fake orchestrator fixture의 newline escape가 생성 파일 안에서 실제 newline로
해석돼 2건 실패했다. fixture source가 `\\n`을 쓰게 고친 뒤 같은 시험 파일을 다시 실행해 23건
전부 통과했다. 제품·workflow·evaluator 동작 실패가 아니며 실패 이력을 삭제하지 않는다.
Claude r1 조건을 더한 최종 focused 재실행은 guard 24건과 orchestrator 40건 모두 통과했다.

로컬 `check_doc_path_citations.py --ratchet --base-ref origin/coord/train42a-ci-1511`은 생성된
프런트엔드 산출물 때문에 기존 citation 5건을 `stale baseline`으로 오판했다. clean hosted
checkout `37108255660`은 그 5건이 여전히 깨진 경로임을 확인했으므로 baseline 원문을
복원했다. baseline의 최종 delta는 0이며 새 예외를 추가하지 않았다.

첫 exact-head Documentation Build `37108118606`은 이전 설명에 쓴 실재하지 않는 빌드
산출물 디렉터리 이름을 새 경로 인용으로 분류해 실패했다. baseline 추가 없이 경로
리터럴을 일반 설명으로 바꿨으며, 제품·orchestrator 동작 실패는 아니다.

## 상태와 다음 행동

실제 hosted producer dispatch는 이 구현 카드에서 수행하지 않는다. 착지 직후 operator가 landed
SHA에서 runbook을 실행할 때만 외부 workflow 상태를 바꾼다. 이 카드의 다음 단계는 문서 gate,
focused 시험과 exact-head hosted CI를 확인하고 Claude 독립 검토를 받는 것이다.
