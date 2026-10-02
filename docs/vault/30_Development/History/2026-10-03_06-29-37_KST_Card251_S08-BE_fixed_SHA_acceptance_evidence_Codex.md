---
doc_id: "HISTORY-CARD251-S08-FIXED-SHA-EVIDENCE-CODEX-001"
title: "Card 251 S08-BE fixed-SHA acceptance evidence"
version: "1.1.0"
status: "implementation"
author: "Codex"
updated: "2026-10-03T06:46:20+09:00"
source_of_truth: "Git"
---

# Card 251 S08-BE fixed-SHA acceptance evidence

## 선택과 기준

Card 247의 승인 제품 경로를 다시 흉내 내지 않고, hosted Core가 이미 실행하는 실제
제품 시험의 JUnit 원문을 고정 SHA 증거로 만드는 방식을 선택했다. 기준 branch는 Card 247
승인 head에 train 32 보안 evidence revision을 재결속한 `#343` 계열이다. 이 변경은 migration,
제품 flag, 공개 계약을 바꾸지 않는다.

## 고정 관측 집합

고정된 13개 node는 다음 성질을 각각 관측한다.

1. prepare → 두 사람 승인 → enqueue → admission → intent → dispatch 정확히 1회
2. product flag off에서 enqueue가 DB·storage·admission을 건드리지 않고 dispatch 0회
3. flag off runtime이 ready admission을 보존하면서 intent·dispatch 0회
4. caller가 넣은 `BuildPlan`·provider 등 raw authority 거부
5. 다른 tenant plan 거부와 rollback
6. 위조 `approvedBy` 거부
7. admission replay 멱등과 tenant 격리
8. 두 worker loop 경합에서 dispatch 정확히 1회
9. intent claim → service 호출 → complete 정확히 1회
10. project permission 부재에서 admission 0
11. 반복 실패 quota/rate limit
12. quorum 뒤 source drift의 terminal 처리와 admission 0
13. legacy direct-build quorum 무회귀

## fail-closed evaluator

`tools/collect_s08_build_acceptance_evidence.py`의 collector는 관측만 추출한다. evaluator는
collector verdict를 받지 않고 다음을 원문에서 다시 계산한다.

- `core-tests.xml`, `build-product-runtime-real-pg.xml`의 SHA-256·case identity·outcome·counts
- `tools/specs/s08-build-acceptance-worker-v1.json`의 고정 canonical digest와 redaction 경계
- evaluator 인자로 독립 전달한 exact source SHA/tree, workflow run id/attempt와 고정 `core` job
- exact 13-case 집합과 cross-field 합계
- real-PG JUnit 전체 13 case·skip 0, 두 artifact 전체 failure/error 0

모든 object는 exact key set이며 기본값이 없다. 필수 key drop, extra key, case drop/add/duplicate,
digest/count/outcome/source/claim 변조와 JSON duplicate key를 PG-free 시험으로 거부한다. 필수
case가 passed여도 같은 JUnit의 다른 case가 failure/error이면 `MEASURED_PASS`가 될 수 없다.

## 실행 경계

`.github/workflows/core.yml`의 `workflow_dispatch.run_s08_acceptance=true`일 때만 Core의 실제
JUnit 두 개로 JSON evidence와 독립 evaluation을 만든다. PR merge ref를 정본으로 세지 않기
위해 dispatch checkout의 `HEAD == GITHUB_SHA`와 clean tree를 먼저 요구한다.

개발 중 호환성 확인에는 승인된 이전 exact-head Core run `37060259771`의 실제 artifact를
사용해 13/13 `MEASURED_PASS` 재계산을 확인했다. 이 재계산은 run id·attempt·checkout tree를
evidence 내부 값이 아니라 evaluator 입력과 대조했다. 이것은 새 Card 251 정본 run이 아니다.
정본 run ID와 artifact는 이 PR exact head dispatch 뒤 기록한다.

## 비주장 경계

- product flag 기본 off를 유지한다.
- 실제 physical/rootless builder 인수는 `NOT_OBSERVED`다.
- S08-BE 완료나 50→75 점수 변경을 주장하지 않는다. 점수 판정은 Card 247 착지와 Card 251
  hosted 증거 검토 뒤 별도 재산정 문서의 몫이다.
