---
doc_id: "HISTORY-CARD267-AC11-POST-LANDING-EXACT-SHA-ORCHESTRATION-CODEX"
title: "Card 267 AC-11 착지 직후 exact-SHA orchestration 결속"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-03T16:53:11+09:00"
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

## 로컬 검증

| 명령 | 결과 | 환경 |
|---|---|---|
| `python -m pytest -q tests/test_post_landing_lane_guard.py` | `23 passed` | Windows, Git Bash 실실행, skip 0 |
| `python -m pytest -q tests/test_run_ac11_exact_sha_aggregate.py` | `37 passed` | Windows, fake-gh, skip 0 |
| `bash -n tools/post_landing_lane_guard.sh` / orchestrator `--help` / `git diff --check` | exit 0 | shell·CLI·whitespace gate |
| `python tools/check_docs.py` | PASS | 24 original hashes, 1129 versioned documents |
| `python tools/check_ontology.py` | PASS | RDF/SHACL/48 task mappings |
| `python tools/sync_obsidian.py --check` | exit 0 | 2035 managed, 133 pending exports, conflict 0, write 0 |

첫 guard 실행에서는 fake orchestrator fixture의 newline escape가 생성 파일 안에서 실제 newline로
해석돼 2건 실패했다. fixture source가 `\\n`을 쓰게 고친 뒤 같은 시험 파일을 다시 실행해 23건
전부 통과했다. 제품·workflow·evaluator 동작 실패가 아니며 실패 이력을 삭제하지 않는다.

`check_doc_path_citations.py --ratchet --base-ref origin/coord/train42a-ci-1511`은 이 카드가
추가한 새 결함이 아니라 이미 고쳐져 baseline에서 제거해야 하는 기존 citation 5건을
`stale baseline`으로 보고 exit 1이었다. 이 카드 범위 밖 Gemini/Claude/과거 History의
`apps/web/dist`·`node_modules` baseline을 늘리거나 되살리지 않았다.

## 상태와 다음 행동

실제 hosted producer dispatch는 이 구현 카드에서 수행하지 않는다. 착지 직후 operator가 landed
SHA에서 runbook을 실행할 때만 외부 workflow 상태를 바꾼다. 이 카드의 다음 단계는 문서 gate,
focused 시험과 exact-head hosted CI를 확인하고 Claude 독립 검토를 받는 것이다.
