---
doc_id: "HIST-CLAUDE-ABSENCE-GUARD-REVIEW-001"
title: "독립 검토 — Codex 부재주장 회귀가드(2679f0c7): sound·non-vacuous 확인"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["independent-review", "codex", "regression-guard", "closed-domain", "non-vacuous"]
---

# 독립 검토 — Codex 부재주장 회귀가드 `2679f0c7`

AGENTS.md의 "Codex 작성 코드는 Claude가 독립 검토한다"에 따라, 진행판이 "Claude 독립 검토 대기"로 지목한 `2679f0c7`(test: guard negative retry and closed input claims)를 통합 tip에서 검토했다. **Codex 큐를 늘리지 않는다**(검토는 내 역할, 그의 대기열 밖).

## Provenance

- 검토 SHA: `2679f0c76b81f078b40e21d1461f7af4dac95050`, integration에 병합됨(검토 시 origin tip `cf1c0079`). 변경 파일: `tests/core/test_external_closed_domain_guards.py`(신규 +116), `tests/test_run_state.py`(+10), 진행판 3.
- 인터프리터 `.venv/Scripts/python.exe`(py3.14.6, pytest 9.1.1), cwd `C:\Project\SaintVision-Invion`. 시험 전용 변경이라 PG/CI/실Node 불요(가드는 순수 Pydantic·상태머신 단위).

## 무엇을 가드하는가

미지의 외부 제어값을 strict 스키마·상태머신이 **fail-closed로 거부**하는지의 변경 감시(sentinel). 새 capability kind·node OS·placement strategy·retry를 지원하려면 계약+DB/단위/경로+이 단언을 **함께** 바꿔야 하며, 조용한 미지값 수용은 forward-compat이 아니라는 것.

## 실행 결과 (내 손)

- `test_external_closed_domain_guards.py`: **29 passed** (0.36s).
- `test_run_state.py`: **47 passed** (0.09s, 신규 retry-terminal 포함).

## Non-vacuity 독립 확인 (통과가 실제로 가드함을 별도 확인 — "green ≠ guards")

설계상 각 negative에 positive 짝이 있어(같은 fixture/dict에서 한 필드만 변경) positive 통과가 negative의 거부 원인을 그 필드로 못 박는다. 나는 이를 넘어 **거부의 위치를 직접 조회**했다:

- 미지값 거부의 `ValidationError` loc가 전부 **정확히 그 enum 필드**였다: capability `kind`(npu), node `osType`(freebsd), placement `strategy`(automatic). 엉뚱한 필수필드 오류로 인한 vacuous 통과가 아니다. positive(gpu/linux/sharded 등)는 전부 clean 통과.
- retry-terminal: 실제 코드에서 `is_terminal(RunState.FAILED)=True`, `reachable_from(RunState.FAILED)=∅`, `can_transition(FAILED, RUNNING)=False`를 직접 확인. 시험은 여기에 더해 `assert_transition`의 오류 메시지 `not a legal transition`까지 매칭하므로, 잘못된 이유로 통과할 수 없다.

## 판정

**Sound·non-vacuous.** 닫힌 도메인 가드는 미지 제어값을 그 필드에서 정확히 거부하고, retry 가드는 FAILED의 종단성을 실제 상태머신으로 고정한다. Codex의 자기검증(여섯 변형 각 exit 1 후 원복)과 일치하며, 내 독립 실행·loc 조회가 이를 강화한다.

## 한계(정직)

- 단위 수준 가드다. 실제 HTTP 라우트가 이 스키마를 실제로 통과 경로에 쓰는지(서빙 강제)는 이 시험 범위 밖이며 `check_contract_bindings`의 서빙앵커 커버리지 소관이다. 이 검토는 "스키마가 도메인을 닫는가"를 확인했지 "모든 라우트가 이 스키마를 쓰는가"를 확인한 것은 아니다.
- 새 accelerator/OS/strategy를 실제 지원할 때 이 가드가 의도대로 **시끄럽게** 깨지는지는 그 변경 시점에 확인된다(sentinel의 목적).
