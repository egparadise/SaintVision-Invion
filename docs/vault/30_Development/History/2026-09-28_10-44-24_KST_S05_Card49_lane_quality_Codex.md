---
doc_id: "HIST-CODEX-S05-CARD49-LANE-QUALITY-001"
title: "S05 Card49 hosted lane fail-closed 품질 보강"
version: "1.0.1"
status: "implemented-review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T10:59:32+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["history", "s05", "hosted-ci", "fail-closed", "provenance", "testing"]
---

# S05 Card49 hosted lane fail-closed 품질 보강

## 범위

PR #151 Claude r1 검토의 후속 결함 3~5와 생존 변이 1~7을 다음 계단 실행 전에 닫았다. base는 #151 final head `6bb94a2a62cdfb65cf354ccdb2e82722183ad3fa`이며 제품 placement·DB·공개 계약·migration·registry status는 바꾸지 않는다. S05-DB는 `in_progress`, flag와 semaphore 제품 코드는 integration에 없고 물리 5노드 AC-05는 별도다.

## 구현

1. `errorsBySqlState` 필수·정수·합계 일치와 미분류 실패 0을 검증한다. 위반은 성능 gate 결과가 아니라 `INVALID_RUN`이다.
2. workflow concurrency를 opt-in job 안으로 옮기고 `cancel-in-progress: false`로 고정했다.
3. dirty checkout을 거부하고, run purpose·정본 decision run ID·measurement scope를 CLI 입력과 report 교차 검증으로 바꿨다.
4. 검증하지 않은 `semaphoreProductCodePresent` 상수는 `semaphoreProductCodeExpected`로 개명했다. report의 `projectSemaphore` 부재 검증은 유지한다.
5. wave·aggregate 이전 산출물을 실행 전에 지워 stale JSON/JUnit 재사용을 막았다.
6. topology를 `placement_benchmark.py`에서 환경으로 전달해 wave JSON/JUnit scope가 hosted 측정을 정직하게 기록하도록 했다.
7. 요청·성공·실패의 정수성과 합계, all-request P95 사용을 고정하고 aggregate JUnit에도 measurement scope를 기록했다. workflow concurrency는 YAML 구조로 job-level임을 검증하며 dirty checkout은 DB 접근 전에 거부한다.

## 시험과 경계

`tests/test_s05_legacy_staircase.py` focused PG-free 재실행은 **31 passed**다. 첫 실행은 새 요청 합계 검사가 기존 부정 fixture 두 건의 `20 success + 1 failure` 모순을 먼저 잡아 **29 passed / 2 failed**였고, fixture를 `19 success + 1 failure`로 교정한 뒤 exit 0을 확인했다. `main()`을 subprocess·DB monkeypatch로 직접 호출해 첫 degraded rung 뒤 중단과 `DEGRADE_AT_20`, SQL timeout·요청 합계, 이전 산출물 삭제, CLI provenance와 dirty checkout DB 선차단을 검증했다. 별도 부정 시험은 잘못된 SHA/scope/fingerprint/lifecycle, 누락·불일치 SQLSTATE, fingerprint 재사용, unexpected exit, success-only P95 대체를 거부한다.

YAML parse와 Python compile은 exit 0이고 수정 Python 3파일 Black check도 exit 0이다. 로컬 PostgreSQL·Docker·브라우저·전체 suite와 legacy staircase 측정은 실행하지 않았다. 이 카드의 hosted Backend는 코드 품질 증거이며 Card46 정본 run `36362386530`이나 Card47 compatibility run `36363327477`을 재판정하지 않는다.

정본 사양: [[S05 legacy 동시성 계단 hosted lane 사양]]. 결정 경계: [[S05 bounded admission 후속 결정 제안]].
