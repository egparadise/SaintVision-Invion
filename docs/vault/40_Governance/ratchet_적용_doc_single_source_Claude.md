---
doc_id: "GOV-RATCHET-DOC-SINGLE-SOURCE-001"
title: "ratchet 적용 — doc_single_source: 델타만 막는 게이트, 기준선 변경을 눈에 띄게, 하향 강제"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
built_at_tip: "fea25b45"
updated: "2026-09-22"
source_of_truth: "Git"
tags: ["governance", "ci", "ratchet", "report-only", "baseline"]
---

# ratchet 적용 — doc_single_source

report-only는 안 막으면 무시된다. 하드 게이트는 기존 백로그(doc_single_source 18쌍, dead-contract 등)에서 늑대소년이 된다. 그 사이 = **지금 상태를 바닥으로 삼고 더 나빠지는 것만 막는 ratchet.** 둘 중 doc_single_source에 실제로 적용했다.

## 왜 doc_single_source이고 dead-contract는 아닌가
- **doc_single_source**: report-only인 이유가 **기존 백로그 18쌍**(구조적 병렬 status 문서). ratchet가 정확히 이 경우를 위한 것 — 백로그는 봐주고 새 쌍만 막는다. **적용.**
- **dead-contract**(check_contract_bindings 내부): report-only인 이유가 백로그가 아니라 **오탐 위험**(grep 기반 `_is_served`가 동적 서빙을 죽은 것으로 오판 가능). ratchet는 백로그를 다루지 오탐을 안 없앤다. 게다가 현재 dead=0이라 백로그도 없다. → **부적합**(ratchet가 그 report-only 이유를 안 고침). 오탐이 해소되면 그냥 하드 게이트가 맞지 ratchet가 아니다.

## 구현 (`tools/check_doc_single_source.py --ratchet`)
- **기준선 = 이름 집합**(수가 아님): `tools/baselines/doc_single_source_pairs.txt`에 수용된 doc-pair를 `A.md || B.md` 한 줄씩(18). 
- `--ratchet`:
  - **새 쌍**(current − baseline) 있으면 **FAIL(회귀)** — 통합하거나, 의도면 그 이름 줄을 baseline에 추가.
  - **stale**(baseline − current, 더는 안 나타나는 쌍) 있으면 **FAIL** — 제거해 바닥을 내리라(안 내리면 슬랙 남아 재악화).
  - 둘 다 없으면 PASS.
- 기본(플래그 없음)은 여전히 report-only.
- **양방향 확증**: 유닛시험 3개(baseline==current→0, 새 쌍→1, stale→1) + 라이브 `--ratchet` PASS(18==18). 8 passed.

## 사용자가 짚은 세 위험에 대한 답
1. **기준선을 올려 조용히 무력화 → 막음**: 기준선이 **수가 아니라 이름 집합**이라, 올리는 것 = **명명된 `A || B` 줄 추가**. 전용 작은 파일이라 그 변경이 **커밋 diff에 통째로 드러난다**(숫자 하나 슬쩍 올리기 아님). 리뷰에서 "이 쌍을 왜 수용하나"를 물을 수 있다.
2. **하향 자동화 여부 → 자동 rewrite 대신 하향 강제**: CI가 스스로 커밋하지 않게, stale 항목은 **FAIL로 제거를 강제**한다(고친 뒤 baseline을 안 내리면 CI가 계속 실패). 즉 하향은 자동이 아니라 **눈에 띄는 수동**(diff에 삭제 줄). 슬랙이 안 남는다.
3. **결국 사람이 기준선 변경을 봐야 함 → 그렇다(한계 명시)**: ratchet는 감시 대상을 **로그 깊숙이 → 18줄 전용 파일의 diff**로 줄인다(작고 명명돼 눈에 띔). 그러나 리뷰가 그 줄을 **거수기로 통과시키면 올림이 새어나간다.** 사람 감시 의존을 **줄이지 없애지 못한다** — 오늘 계속 나온 한계. rule 6대로 baseline 수/집합은 **표현값**이라 검사 대상에서 유도하면 안 되고 독립 고정 + 리뷰가 필요.

## 정리 — 델타는 막고 상태는 보인다 (그 사이)
- **게이트(delta)**: `--ratchet`가 새 쌍·stale에 실패 → 회귀를 막되 백로그엔 안 운다(늑대소년 회피).
- **가시성(state)**: 기본 report → `$GITHUB_STEP_SUMMARY`(별건 문안). baseline 변경 → 커밋 diff.
- **남은 사람 몫**: baseline 줄의 추가/삭제를 리뷰가 실제로 본다는 것. ratchet는 그 표면을 작고 명명되게 만들 뿐, 볼 사람이 필요하다는 사실은 그대로다.

## 배선 (Codex — YAML)
docs.yml에 게이트 스텝으로:
```yaml
      - run: python tools/check_doc_single_source.py --ratchet
```
(기존 report-only 문안은 step-summary 가시성용으로 병행 가능. dead-contract는 ratchet 부적합이라 현행 report-only 유지 + step-summary만.)

관련: [[검사도구_CI배선과_리포트가시성_Claude]] · [[문서검사_커버리지와_갭_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
