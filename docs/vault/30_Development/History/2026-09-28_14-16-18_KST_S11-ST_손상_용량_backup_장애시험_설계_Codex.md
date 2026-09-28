---
doc_id: "HIST-CODEX-S11-ST-FAILURE-DESIGN-001"
title: "S11-ST 손상·용량·backup 장애 시험 설계"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-28T14:16:18+09:00"
source_of_truth: "Git"
task_id: "S11-ST"
reviewer: "Claude"
---

# S11-ST 손상·용량·backup 장애 시험 설계

## 범위와 결정

- S11-ST의 `손상·용량·backup 장애 시험`을 구현하기 전 fault matrix, 계층, fail-closed 판정, 목표를 [[S11-ST_손상_용량_backup_장애시험_설계]] v1.0.0으로 고정했다.
- 객체 손상·부분 쓰기·용량 소진은 AC-11 `long-soak` 축의 필수 하위 matrix로, archive·retention 장애는 `actual-pitr-rpo-rto-retention` 축으로 분류했다. hosted archive 결과는 reference-only이며 운영 PITR PASS로 세지 않는다.
- 공개 계약·migration·task registry는 바꾸지 않았다. S11-ST `planned`, 전체 AC-11 미완료를 유지한다.

## 정직성 대조

- PR #173 exact head `288ee0b6`의 S3 read-back/hash/metadata와 Local fsync/rename 경계를 읽었다. S3 비가용은 기존 `STORE-0001`/503/retryable로 닫히지만 Local `ENOSPC`·`EDQUOT`·fsync 오류는 raw `OSError` 가능성이 있어 구현 공백으로 남겼다.
- PR #150 exact head `f97c48d5`의 retention planner는 최신·unknown-age backup과 유지 경계 이후 WAL을 보존한다. 반면 apply는 순차 unlink/rmtree이며 중간 실패 journal이 없어 부분 삭제 가능성을 숨기지 않았다.
- readiness와 dry-run은 `pitrVerified:false`이며 실제 WAL 전달·복구·RPO/RTO를 증명하지 않는다. same-host·hosted 결과를 별도 장애 영역 증거로 올리는 경로를 금지했다.

## 사전 등록

- 설계 고정 commit `6e8b81ee7372952512f20d78f41f9d53b0152035`, blob `cee9963d17fc11baf5d77fe69eda97224ea354b8`.
- `Evidence/s11-st-failure-target-registry-v0.json` 고정 commit `c523c123d171a657da7fb418d8f5600bf5477281`, blob `7024be8f79559b42160e84d1b490ba886796b772`.
- hosted storage soak는 3600초·1000 operation·fault 6/6·손상 유출/false success/committed loss/quota overshoot/classification mismatch/unexpected error/residue 0을 고정했다.
- operational archive target은 RPO 900초·RTO 3600초·35일·2주 weekly smoke와 archive/retention fault 각 1건, fault 뒤 recovery 2건, false PITR pass·retained-boundary deletion·residue 0을 고정했다.

## 검증과 남은 일

- 로컬 실 PostgreSQL·Docker·전체 suite는 실행하지 않았다. 문서·JSON·정적 게이트만 실행했다.
- `python -m json.tool` target registry, `check_docs`, `check_ontology`, `check_contract_bindings`, `check_doc_single_source --ratchet`, `git diff --check`는 모두 exit 0이다.
- 다음 단계는 Claude 설계 검토다. 승인 뒤 PG-free fault injector/validator, Local 오류 변환·retention receipt, hosted opt-in lane, 마지막으로 운영 별도 장애 영역 인수를 각각 분리한다.
