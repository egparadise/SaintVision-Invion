---
doc_id: "HISTORY-S11-AC11-MIGRATION-REHEARSAL-R2-20260928-CODEX"
title: "S11 AC-11 migration rehearsal r2 — Claude F1~F5 보강과 hosted 증거"
version: "1.2.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T14:43:45+09:00"
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

artifact `10952510591`, GitHub digest `sha256:d4437410c8273241cf535dd994ef8825fb6127825e5e423f16c295640632b343`, expiry `2026-10-28T04:56:39Z`다. 아래 r3 importer가 다운로드 zip을 직접 hash하고 GitHub run/artifact metadata와 대조한 결과에서만 restore 축 봉투의 expected/observed digest 일치를 인정한다.

## Claude r2 재검토 N1~N4 대응

- N1: importer 입력을 report+호출자 digest에서 **artifact zip + GitHub run JSON + artifact JSON**으로 바꿨다. zip byte를 직접 SHA-256하고 GitHub digest와 비교하며, zip 안의 report/JUnit만 읽는다. run `id/status/conclusion/head_sha`, artifact `name/digest/expired/expires_at/workflow_run.id/head_sha`, report `sourceRunId/sourceHeadSha/junitSha256`를 서로 exact 결속한다. 축 봉투에는 실제로 관측한 artifact/report/JUnit digest를 각각 보존한다.
- N1 부정 시험은 다른 digest, API expired와 과거 expiry, failed run, run head 불일치, workflow run ID 불일치, artifact name 불일치, sourceRunId 누락, JUnit failure를 모두 거부한다. `ImportError` builtin shadow는 `EvidenceImportError`로 바꿨다.
- N2: 0009 downgrade 실패는 이제 `UniqueViolation` 또는 SQLSTATE `23505`만 인정한다. 새 connection에서 `alembic_version=fixture_head`, `uq_ac11_fixture_project` 생존, old constraint 부재, `project_id` 생존을 확인해 transaction rollback을 고정한다. 다른 오류나 반쪽 rollback은 실패다. 기존 객체 삭제·ellipsis fixture는 catalog `tables` 차이여야 한다.
- N3: JUnit의 세 negative testcase는 실제 `EXPECTED_FINDING` 진행 목록으로 계산한다. 실행되지 않거나 finding이 아닌 case는 통과 testcase가 아니라 failure다.
- N4: 현재 tail 0 경계는 유지하되, future reversible 분기의 catalog+sentinel 검증을 공통 helper로 묶고 양성·catalog drift·sentinel drift 단위 시험과 runner 호출 구조 시험을 추가했다. revision별 영향 테이블 sentinel은 실제 reversible tail이 생기는 카드의 선행 조건으로 남는다.

정본 run `36379743674` artifact `10952510591`을 다시 다운로드해 importer CLI를 실행한 결과 exit 0이다. 직접 계산한 `artifactObservedSha256`은 GitHub `artifactSha256`과 같은 `d4437410c8273241cf535dd994ef8825fb6127825e5e423f16c295640632b343`, report file hash는 `cfa3b678a3361146be560d40fbca1eef57d20c667ebc73919504961d17595c28`, JUnit hash는 report의 `1cbc2ffed3f809554a8cae24f017a13c1587e46b29119432f65277d0e651c1ef`, source run은 `36379743674`, conclusion은 `success`다.

### r3 증거 경계(N5·N6)

- 정본 hosted run `36379743674`는 runner head `abe8435a`의 산출물이다. r3 head `b2b4db3c`에서 강화한 N2의 `UniqueViolation`/`23505`·새 connection rollback-state 검사와 N3의 실제 negative-case JUnit 귀속은 **PG-free 단위 시험만** 거쳤으며 hosted PostgreSQL rehearsal에서는 아직 실행되지 않았다. 따라서 위 정본 증거는 세 부정 fixture가 당시의 더 느슨한 0009 판정을 통과했다는 사실만 증명하고, 강화된 runner의 hosted 통과를 주장하지 않는다. release evidence를 만들기 전에는 최종 release SHA에서 lane을 다시 실행해야 한다.
- importer는 GitHub API를 직접 호출하거나 metadata의 서명을 인증하지 않는다. 운영자는 인증된 `gh` 세션에서 `gh api repos/egparadise/SaintVision-Invion/actions/runs/36379743674`, `gh api repos/egparadise/SaintVision-Invion/actions/artifacts/10952510591`, `gh api repos/egparadise/SaintVision-Invion/actions/artifacts/10952510591/zip`으로 run JSON, artifact JSON, zip을 각각 취득한 뒤 importer에 전달해야 한다. 재검증할 때는 report의 `sourceRunId`로 `gh api repos/egparadise/SaintVision-Invion/actions/runs/36379743674/artifacts`도 조회해 artifact id·name·digest를 다시 대조한다.
- importer는 zip byte·report·JUnit·두 metadata JSON 사이의 모순을 fail-closed로 거부하지만, 호출자가 zip과 JSON을 일관되게 위조하면 출처 진정성을 증명할 수 없다. 즉 이 도구는 **metadata 인증기**가 아니라 다운로드된 GitHub evidence의 결속 검사기다. canonical repository/workflow 결속과 `artifactId`의 축 봉투 보존은 후속 hardening 항목이다.

## 게이트와 경계

- PG-free AC-11 관련 시험: r3 focused importer/runner/aggregator **87 passed**.
- `check_docs`, `check_ontology`, `check_contract_bindings`, `check_doc_single_source --ratchet`, `git diff --check`: 모두 exit 0.
- 이 증거는 hosted 단일 PostgreSQL service의 합성 restore-forward와 부정 migration fixture만 증명한다.
- 새 cluster role restore, 운영 PITR·archive, 물리 5노드·실장비 복구는 계속 미측정이며 AC-11 전체 done을 뜻하지 않는다.
- label 기반 lane은 새 push만으로 재실행되지 않으므로 label 재부착 또는 `workflow_dispatch`가 필요하다.
