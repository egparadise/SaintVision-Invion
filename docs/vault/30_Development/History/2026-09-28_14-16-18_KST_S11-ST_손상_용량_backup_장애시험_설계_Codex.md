---
doc_id: "HIST-CODEX-S11-ST-FAILURE-DESIGN-001"
title: "S11-ST 손상·용량·backup 장애 시험 설계"
version: "1.2.0"
status: "review"
author: "Codex"
updated: "2026-09-28T15:47:09+09:00"
source_of_truth: "Git"
task_id: "S11-ST"
reviewer: "Claude"
---

# S11-ST 손상·용량·backup 장애 시험 설계

## 범위와 결정

- S11-ST의 `손상·용량·backup 장애 시험`을 구현하기 전 fault matrix, 계층, fail-closed 판정, 목표를 [[S11-ST_손상_용량_backup_장애시험_설계]] v1.2.0으로 고정했다.
- storage 결과는 PG-free·hosted·물리 모두 reference-only다. #157의 `long-soak`은 열·전원·NTP·스위치·WAN·원격 WS까지 포함하므로 storage-only target을 제거했고, 전체 composite target 승인 전 `NOT_REGISTERED`로 둔다. archive·retention만 약한 기존 target을 교체한 별도 장애 영역 target 후보다.
- 공개 계약·migration·task registry는 바꾸지 않았다. S11-ST `planned`, 전체 AC-11 미완료를 유지한다.

## 정직성 대조

- PR #173 exact head `288ee0b6`의 S3 read-back/hash/metadata와 Local fsync/rename 경계를 읽었다. S3 비가용은 기존 `STORE-0001`/503/retryable로 닫히지만 Local `ENOSPC`·`EDQUOT`·fsync 오류는 raw `OSError` 가능성이 있어 구현 공백으로 남겼다.
- PR #150 exact head `f97c48d5`의 retention planner는 최신·unknown-age backup과 유지 경계 이후 WAL을 보존한다. 반면 apply는 순차 unlink/rmtree이며 중간 실패 journal이 없어 부분 삭제 가능성을 숨기지 않았다.
- readiness와 dry-run은 `pitrVerified:false`이며 실제 WAL 전달·복구·RPO/RTO를 증명하지 않는다. same-host·hosted 결과를 별도 장애 영역 증거로 올리는 경로를 금지했다.

## Claude 검토 반영

- 별도 registry path를 #177 집계기가 전부 거부한다는 probe 결과를 수용했다. `s11-st-failure-target-registry-v0.json`은 삭제하고, #177의 `s11-ac11-target-registry-v0.json` 하나에 patch·repin하는 Codex 선행 카드를 확정했다.
- hosted 또는 physical storage-only 결과로 `long-soak` 전체를 PASS시키던 fail-open을 제거했다. 정본 registry patch에는 PITR target만 남기고 long-soak map은 만들지 않는다.
- 약한 `s11-actual-pitr-v0`를 제거하고 archive refusal·silent exit-0 loss·retention interruption 뒤 복구를 요구하는 target으로 교체하며, 축별 허용 targetId 닫힌 map을 집계기에 둔다.
- raw producer와 AC-11 importer를 분리했다. skip은 `NOT_OBSERVED`, 완결된 목표 미달은 `MEASURED_FAIL`, failed/cancelled run·provenance 위조는 `INVALID_RUN`으로 #177 verdict에 맞췄다.
- 22개 case identity universe와 exact code/status/retryable 또는 failureClass를 [[S11_ST_storage_failure_target_v0]]에 고정했다. 실행 가능한 분모는 PG-free 12개와 hosted 10개로 분리해 각 run이 자기 계층 subset만 완결하도록 했다. 물리 storage reference 3개와 PITR gate 3개도 부류별 identity와 recovery로 닫았다.
- Local byte 변조 case는 `object_store.py`의 mode-first 검사를 피하지 않도록 read 전에 mode를 `0o400`으로 복원하고 단언한다. metric의 `n/successCount/failureCount/skipCount` 합과 zero/minimum/max 의미도 고정했다.
- #173 corruption/quota 시험, recovery drill의 `/bin/false`·`/bin/true`, G-02 #181/#187, #150 retention 도구 재사용 표와 잔여 범위 표를 추가했다.

## 사전 등록

- target 기준 문서는 [[S11_ST_storage_failure_target_v0]]이다. final source commit/blob은 아래 pin commit 뒤 기록하며, 이 commit이 조상으로 남도록 merge commit 병합만 허용한다.
- 정본 registry patch는 `Evidence/s11-st-failure-target-registry-patch-v0.json`에 PITR-only review artifact로 남기되 `consumableAsTargetRef=false`다. predecessor는 #177 head `b246e7dbd597db52ae5c16be4c0a03ffd056ab93`, registry blob `99e64cb4125d47ae681a2e8e7c8f76c05193a892`다. 선행 카드 `CARD-S11-AC11-REGISTRY-REPIN-01`이 #177 병합 뒤 정본 registry·집계기·importer pin을 함께 바꾸기 전 측정 금지다.
- identity SHA-256은 universe 22개 `5d700981...34fd9`, PG-free 12개 `f69d161e...8799`, hosted 10개 `0509d94a...4a33`, physical storage 3개 `f6fef831...90ec`, physical PITR 3개 `a5d0f9e6...cc18`이다.

## 검증과 남은 일

- 로컬 실 PostgreSQL·Docker·전체 suite는 실행하지 않았다. 문서·JSON·정적 게이트만 실행했다.
- head `2a557b8a`까지 `check_docs`, `check_ontology`, `check_contract_bindings`, ratchet은 exit 0이었다. r2 반영 delta에는 pin 확정 뒤 같은 게이트를 다시 실행한다. 로컬 실 PostgreSQL·Docker·전체 suite는 실행하지 않는다.
- 다음 단계는 target source pin 확정, 정적 게이트, push, Claude 재검토다. 승인 뒤 `CARD-S11-AC11-REGISTRY-REPIN-01`, PG-free producer/importer, Local 오류 변환·retention receipt, hosted reference lane, 물리/운영 인수를 분리한다.
