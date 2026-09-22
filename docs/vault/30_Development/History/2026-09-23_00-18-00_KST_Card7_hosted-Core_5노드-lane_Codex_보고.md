---
doc_id: "HISTORY-2026-09-23-CODEX-CARD7-HOSTED-CORE-FIVE-NODE-LANE-001"
title: "Codex 카드 7 hosted Core 보강과 5노드 opt-in lane 정의"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T00:18:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "6332abef803a6063fb0b86edfbd04461b18c324c"
impl_sha: "21c6a026e905344887c4b536f7287bfb6e79598c"
tags: ["card7", "hosted-ci", "five-node", "S05", "S06", "S07"]
---

# Codex 카드 7 hosted Core 보강과 5노드 opt-in lane 정의

## 범위와 착지

- 카드 6의 exact 구현 SHA `a4bf2cee` hosted Core 완주 결과에서 Windows가 건너뛴 Linux scoped-handle 23건을 직접 집계했다.
- 카드 5 독립 검토 O3를 [[Codex 5노드 랩 opt-in lane 정의]] 1쪽 제안으로 구체화했다. 이번 카드에는 제품 코드·계약·`.github/workflows/core.yml` 변경이 없다.
- content R1 `21c6a026e905344887c4b536f7287bfb6e79598c`(부모 `6332abef803a6063fb0b86edfbd04461b18c324c`)를 origin `integration/all-agents-unified`에 non-force fast-forward로 착지했다.

## hosted Core 증거

[Core run 35742655096](https://github.com/egparadise/SaintVision-Invion/actions/runs/35742655096)는 head `a4bf2cee3c4e396b0884aba7890aa3855e8d5aa8`, conclusion `success`다. `gh run download ... --name saintvision-core-evidence`로 받은 `core-tests.xml`의 SHA-256은 `965a98c8776ac7dd70b6ae7956493d2a600cee1b1ef15d02414ae4230df98bbf`다.

| JUnit classname | Linux 결과 |
|---|---|
| `tests.integration.test_workspace_recovery` | 12 passed / 0 skipped / 0 failed |
| `tests.integration.test_workspace_resume` | 11 passed / 0 skipped / 0 failed |
| 합계 | **23 passed / 0 skipped / 0 failed** |

전체 `core-tests.xml`은 3,134 tests / 35 declared platform skips / 0 failure·error다. 개발 PC의 23 skip 사유는 `Linux scoped handles` 12건과 `Linux bounded Workspace execution` 11건이고, Linux에서는 모두 실행됐다. `workspace-tests.xml`의 resume 11건도 별도 선행 단계에서 11/11 통과했다. 결과는 카드 6 History v1.1.0에 보강했다.

## 5노드 lane 제안과 정직한 경계

제안은 self-hosted lab runner·GitHub Environment 승인, exact code/inventory revision, 4개 image digest, 환경변수와 secret **이름**, S05/S07/S06 순차 명령, 실패에도 보존할 JUnit+JSON artifact 이름을 고정한다. 실제 workflow 변경은 랩 준비 뒤 `agent/codex/five-node-lane`에서만 제안한다.

현재 S05/S07 도구는 실 PG의 합성 node adapter이므로 5-node runner에서 실행만 해서는 물리 5노드 증거가 아니다. 현재 S06 원격 도구의 7-case도 WS/PTY/Git 및 CP/Node 재시작을 포함하지 않는다. 따라서 inventory-bound adapter와 제안된 S06 물리 runner가 구현·실행되기 전에는 AC-05/06/07을 닫지 않는다.

## 검증과 다음 행동

| 명령 | 결과 |
|---|---|
| `gh run view 35742655096 --json ...` | completed/success, exact head 일치 |
| artifact XML 직접 집계 | 대상 23/23 passed, skip/failure 0 |
| `python tools/check_docs.py` | 831 documents, exit 0 |
| `python tools/check_ontology.py` | 48 task mappings, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | 18 pairs / new duplicate 0, exit 0 |

Claude가 content R1의 hosted 집계·제안 입력/secret/artifact 경계와 `core.yml 변경 없음`을 독립 검토한다. S06-DB는 소프트웨어 결속과 hosted Linux 회귀가 통과해도 물리 원격 WS/PTY/Git·CP/Node 재시작 복원 여정이 없으므로 `review`를 유지한다.
