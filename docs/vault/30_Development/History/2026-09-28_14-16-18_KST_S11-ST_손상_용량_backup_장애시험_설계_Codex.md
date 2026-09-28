---
doc_id: "HIST-CODEX-S11-ST-FAILURE-DESIGN-001"
title: "S11-ST 손상·용량·backup 장애 시험 설계"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-28T15:17:15+09:00"
source_of_truth: "Git"
task_id: "S11-ST"
reviewer: "Claude"
---

# S11-ST 손상·용량·backup 장애 시험 설계

## 범위와 결정

- S11-ST의 `손상·용량·backup 장애 시험`을 구현하기 전 fault matrix, 계층, fail-closed 판정, 목표를 [[S11-ST_손상_용량_backup_장애시험_설계]] v1.1.0으로 고정했다.
- hosted 객체 손상·부분 쓰기·용량 결과는 reference-only다. AC-11 `long-soak`은 ADR-100의 CP 겸임 Node를 제외한 물리 4 eligible Node·24시간 target으로, archive·retention은 약한 기존 target을 교체한 별도 장애 영역 target으로 분류했다.
- 공개 계약·migration·task registry는 바꾸지 않았다. S11-ST `planned`, 전체 AC-11 미완료를 유지한다.

## 정직성 대조

- PR #173 exact head `288ee0b6`의 S3 read-back/hash/metadata와 Local fsync/rename 경계를 읽었다. S3 비가용은 기존 `STORE-0001`/503/retryable로 닫히지만 Local `ENOSPC`·`EDQUOT`·fsync 오류는 raw `OSError` 가능성이 있어 구현 공백으로 남겼다.
- PR #150 exact head `f97c48d5`의 retention planner는 최신·unknown-age backup과 유지 경계 이후 WAL을 보존한다. 반면 apply는 순차 unlink/rmtree이며 중간 실패 journal이 없어 부분 삭제 가능성을 숨기지 않았다.
- readiness와 dry-run은 `pitrVerified:false`이며 실제 WAL 전달·복구·RPO/RTO를 증명하지 않는다. same-host·hosted 결과를 별도 장애 영역 증거로 올리는 경로를 금지했다.

## Claude 검토 반영

- 별도 registry path를 #177 집계기가 전부 거부한다는 probe 결과를 수용했다. `s11-st-failure-target-registry-v0.json`은 삭제하고, #177의 `s11-ac11-target-registry-v0.json` 하나에 patch·repin하는 Codex 선행 카드를 확정했다.
- hosted 1시간 target으로 `long-soak` 전체를 PASS시키던 fail-open을 제거했다. hosted fault matrix는 reference-only이고 물리 target은 24시간·eligible 4/excluded 1·resource drift와 storage failure zero 기준을 함께 요구한다.
- 약한 `s11-actual-pitr-v0`를 제거하고 archive refusal·silent exit-0 loss·retention interruption 뒤 복구를 요구하는 target으로 교체하며, 축별 허용 targetId 닫힌 map을 집계기에 둔다.
- raw producer와 AC-11 importer를 분리했다. skip은 `NOT_OBSERVED`, 완결된 목표 미달은 `MEASURED_FAIL`, failed/cancelled run·provenance 위조는 `INVALID_RUN`으로 #177 verdict에 맞췄다.
- 22개 case identity와 exact code/status/retryable 또는 failureClass를 [[S11_ST_storage_failure_target_v0]]에 고정했다. CAP-02 기준 시점은 `begin` 직후이고 Local case는 PG-free 전용이다. `/bin/true`·empty/truncated backup의 조용한 성공 `BAK-03`을 추가했다.
- #173 corruption/quota 시험, recovery drill의 `/bin/false`·`/bin/true`, G-02 #181/#187, #150 retention 도구 재사용 표와 잔여 범위 표를 추가했다.

## 사전 등록

- target 기준 문서는 [[S11_ST_storage_failure_target_v0]]이며 고정 commit `0606e594f18172a17415f378b258ff4e0ee8d8e8`, blob `d75132a53b7a879df48e02c8b1caf65b9dfe35cf`를 사용한다. 물리 long-soak은 corruption·capacity·durability 부류별 주입을 포함한 관측 fault 3건과 fault 뒤 recovery 3건을 양의 기준으로 요구해 무주입 zero-count PASS를 막는다. 이 commit이 조상으로 남도록 merge commit 병합만 허용한다.
- 정본 registry patch는 `Evidence/s11-st-failure-target-registry-patch-v0.json`에 review artifact로 남기되 `consumableAsTargetRef=false`다. predecessor는 #177 head `b246e7dbd597db52ae5c16be4c0a03ffd056ab93`, registry blob `99e64cb4125d47ae681a2e8e7c8f76c05193a892`다. #177 병합 뒤 정본 registry·집계기·importer pin이 함께 바뀌기 전 측정 금지다.
- raw case identity 22개의 sorted compact JSON SHA-256은 `5d700981ee429ebbfc66b8ed28d8dc9e37e16e327a673d6061bdec5e7e334fd9`다.

## 검증과 남은 일

- 로컬 실 PostgreSQL·Docker·전체 suite는 실행하지 않았다. 문서·JSON·정적 게이트만 실행했다.
- v1.0에서 실행한 정적 게이트 결과는 당시 exit 0이었으나 v1.1 변경에는 재실행 전이다. 로컬 실 PostgreSQL·Docker·전체 suite는 계속 실행하지 않는다.
- 다음 단계는 target 문서 pin·patch artifact 추가, 정적 게이트, push, Claude 재검토다. 승인 뒤 정본 registry 선행 카드, PG-free producer/importer, Local 오류 변환·retention receipt, hosted reference lane, 물리/운영 인수를 분리한다.
