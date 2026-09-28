---
doc_id: "HISTORY-S11-AC11-MIGRATION-REHEARSAL-R2-20260928-CODEX"
title: "S11 AC-11 migration rehearsal r2 — Claude F1~F5 보강과 hosted 증거"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T13:57:32+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tasks: ["S11-BE", "S11-DB"]
acceptance: ["AC-11"]
tags: ["s11", "ac-11", "migration", "restore", "hosted", "fail-closed"]
---

# S11 AC-11 migration rehearsal r2

## Claude 검토 F1~F5 대응

Claude의 PR #177 head `d74d32e6` 검토에서 Backend shallow checkout, reversible downgrade 기준 DB 비교 부재, 실행 부정 fixture 부재, AC-11 집계기 입력 형식 부재, CHECK 정규화 범위가 차단 항목으로 확인됐다.

- F1: 일반 Backend 시험은 검토 blob 값을 주입해 shallow checkout과 분리했고, 도달 불가 blob 부정 시험을 남겼다. opt-in lane은 `fetch-depth: 0`과 exact historical commit fetch를 계속 요구한다.
- F2: future reversible tail이 생기면 `head → restore barrier` downgrade DB와 barrier 기준 DB를 별도로 만들고 catalog fingerprint와 preservation sentinel을 비교한다. 현재 tail 0은 구조적 `NOT_APPLICABLE`이다.
- F3: hosted disposable DB와 임시 Alembic으로 기존 객체 삭제, 0009 중복 key downgrade, ellipsis no-op을 실제 실행한다. 세 변이는 모두 `EXPECTED_FINDING`이어야 PASS다.
- F4: [[S11_AC11_migration_restore_target_v0]]에 목표 3개를 사전 등록하고 target registry blob을 갱신했다. 다운로드 뒤 importer가 GitHub artifact digest와 만료를 축별 `ac11-axis-evidence` 봉투에 결속한다. producer의 JUnit hash는 `junitSha256`으로 구분한다.
- F5: 정규화는 CHECK 내부의 `ANY (ARRAY['…'::character varying…])` 부분식에만 적용한다. 그 밖의 cast는 바꾸지 않는다.

## 실행 이력

첫 보강 run `36379589596`(head `22cbf3f1`)은 전역 치환을 좁힌 최초 정규식이 `OR (... ANY (...))` 형태 11건을 놓쳐 catalog mismatch로 fail-closed 종료됐다. disposable DB 2개 residue는 0이었다. 이 실패는 감추지 않고 calibration으로 남긴다.

정본 보강 run은 [36379743674](https://github.com/egparadise/SaintVision-Invion/actions/runs/36379743674), exact head `abe8435a99dc8f073fa781e5156ba36ce8099fab`, checkout tree `e8b86fff5b5fd71ddfd56b93e8361005ed11b778`, clean checkout `true`다. PostgreSQL `16.15`, JUnit **6 tests / 0 failures / 0 errors / 1 structural skip**, disposable DB **7개 시도 / residue 0 / cleanup error 0**이다. restore-forward와 세 부정 fixture가 PASS했고 catalog 9 section hash는 `df97a8f84c63901870efad6393554e164afe7464340af54d62c57ac6170ba902`다.

artifact `10952510591`, GitHub digest `sha256:d4437410c8273241cf535dd994ef8825fb6127825e5e423f16c295640632b343`, expiry `2026-10-28T04:56:39Z`다. importer CLI도 이 digest로 exit 0이며 restore 축 봉투의 `artifactSha256`과 `artifactObservedSha256`이 동일하다.

## 게이트와 경계

- PG-free AC-11 관련 시험: **75 passed**.
- `check_docs`, `check_ontology`, `check_contract_bindings`, `check_doc_single_source --ratchet`, `git diff --check`: 모두 exit 0.
- 이 증거는 hosted 단일 PostgreSQL service의 합성 restore-forward와 부정 migration fixture만 증명한다.
- 새 cluster role restore, 운영 PITR·archive, 물리 5노드·실장비 복구는 계속 미측정이며 AC-11 전체 done을 뜻하지 않는다.
- label 기반 lane은 새 push만으로 재실행되지 않으므로 label 재부착 또는 `workflow_dispatch`가 필요하다.

