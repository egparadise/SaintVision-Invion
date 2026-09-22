---
doc_id: "HIST-CODEX-2026-09-22-S04-S05-S07-DB-OWNER-REVIEW"
title: "S04-DB·S05-DB·S07-DB owner 판정 — review 진입, done 차단 조건 유지"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-22T19:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "04d88d58d67f2464ec724cce77b4de7782d418cb"
task_ids: ["S04-DB", "S05-DB", "S07-DB"]
tags: ["owner-review", "task-registry", "ontology", "real-pg", "hosted-core"]
---

# S04-DB·S05-DB·S07-DB owner 판정

## 결론

Codex는 Claude reviewer 인계 패키지 `04d88d58`의 AC↔증거 대조표를 기존 실 PostgreSQL·hosted Core 증거와 독립 대조했다. 세 카드 모두 구현·경합·실패 경계 증거가 있어 **`planned`에서 `review`로 진입할 수 있다**. 이 판정은 완료 판정이 아니며, 아래 물리 환경·성능·선행 카드 조건이 남아 있으므로 **`done` 전환은 금지**한다.

## 증거 대조

| 카드 | review 진입을 지지하는 증거 | owner 판독 |
|---|---|---|
| S04-DB | `d01c931a` 실 PG S04/S05 묶음 74 passed·0 failed, 승인·취소·idempotency·outbox 원자성. hosted Core `35706465645` 전체 2948 passed·58 skipped·0 failed에서 `test_node_delivery.py` 18건과 `test_output_ingestion.py` 5건 실행. 후자는 실제 stdout/stderr 바이트 SHA-256 일치, receipt 이후 재시작·publication crash 재개, 재실행 0을 고정한다. | 승인 전 실행 0·중복 부수효과 0·재개 시 동일 결과/해시 경계가 review 수준으로 연결된다. |
| S05-DB | 실 PG 경합 묶음의 50 동시 예약 초과 0·fencing·provisioning 무결성. hosted Core에서 `test_placement.py` 12건 실행; 동일 요청 결과 equality, `weightsVersion`, Explain 발행 실패 전체 롤백, node observation·scope·ceiling 경계를 포함한다. | 단일 fixture 결정성과 설명 가능 경로는 확인됐지만 5노드 성능 인수는 남는다. |
| S07-DB | `d01c931a` S07 묶음 92 passed·19 CX01 skip·0 failed, stale token·recovery verdict·liveness stale 표시. hosted Core에서 `test_shard_recovery.py` 21건, `test_containment.py` 28건, `test_workspace_recovery.py` 12건 실행. | 분할·late result·경합·복구 실패 경계가 review 수준으로 연결되지만 물리 시간/성공률 목표는 미측정이다. |

hosted 수치는 `gh run view 35706465645 --job 106679187483 --log`의 파일별 진행선과 최종 요약을 판독했다. 인계 문서가 S07 행에 적은 `shard_recovery 15`·`containment 21`은 실제 파일별 수치 `21`·`28`과 다르다. 이는 증거를 약화시키는 결손이 아니라 인계 문서의 집계 오기이며, 이 owner 기록이 실제 로그 수치를 보정한다.

## done 차단 조건

- **S04-DB:** 물리 Node 전송 재개 인수와 로컬 WSL2 경계가 남고, 선행 S03-FE·S03-BE·S03-ST가 완료되지 않았다.
- **S05-DB:** 동일 입력의 5노드 배치 결정성 반복 측정과 P95 2초 실측이 없으며, 선행 S04 카드들이 완료되지 않았다.
- **S07-DB:** heartbeat 기반 이탈 감지 60초 상한과 다회 복구 성공률 95%의 5노드 통계가 없고, CX01 복원 19건 및 S06 선행 카드가 남아 있다.
- 세 카드 모두 이번 변경으로 acceptance/outcome 자체를 `done`으로 바꾸지 않는다. 외부·물리 조건을 실제로 채운 뒤 owner/reviewer가 다시 판정해야 한다.

## 적용

- `docs/task-registry.json`: S04-DB·S05-DB·S07-DB의 `status`만 `planned` → `review`로 변경했다.
- `python tools/generate_ontology.py`: registry 변경을 정본 ontology와 vault mirror에 재생성했다.
- 착지 후보 `0407a98b` 부모 기준 경량 게이트: `check_docs.py` **796 documents / exit 0**, `check_ontology.py` **48 task mappings / exit 0**, `check_ontology_generation.py` **4 artifacts graph-equivalent / exit 0**, `check_doc_single_source.py --ratchet` **18 pairs / exit 0**, `git diff --check` **exit 0**. 시험 suite는 메모리 경보 지침에 따라 재실행하지 않고 위 기존 증거만 판독했다.

## PR #53 문서 정직성 교차검토

PR #53 HEAD `9a7a3651`은 수정 요청으로 판정했다. Gemini 작업판에 잔여 충돌 표식이 있어 `git diff --check`가 실패하고, 스크린샷 수(5 표기/7 목록), #39·#40·#44 최종 head SHA, 제어문자성 본문 손상, 미래 `updated` 시각이 실제 상태와 맞지 않았다. #36·#39·#40·#44의 `MERGED` 상태 자체와 #36 `c6094d71` → `8f3c80c8`은 일치했다. 코멘트: https://github.com/egparadise/SaintVision-Invion/pull/53#issuecomment-5775051728

## 다음 행동

코디네이터는 PR #53 수정 뒤 재검토를 요청한다. S04/S05/S07은 물리 5노드·CX01 조건이 열릴 때 위 차단 항목만 이어서 측정하고, 그 전에는 `review`를 유지한다.
