---
doc_id: "HIST-VF-MODEL-REVIEW-001"
title: "VF 모델 독립 검토 finding 판정"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T15:11:55+09:00"
source_of_truth: "Git"
---

# VF 모델 독립 검토 finding 판정

## 착수

- VF-CX-02/VF-CL-05 후속, owner Codex/reviewer Claude(후속 재검토 pending).
- branch agent/codex/vf-model-review, base 116e6e518cc697795ec1970a80e1801ed2b165b3, 시작 2026-09-15T15:11:55+09:00.
- INDEX-PROGRESS-001 1.0.81, WORKBOARD-VF-CODEX-001 1.0.10, WORKBOARD-CODEX-001 1.0.49. 기존 최종계획/ADR/역할/운영/보강로드맵/연속정책 및 agent-delivery1.1.0/core-reliability1.0.0 적용.
- Claude 원격9847912의 실제 소스 검토 수신. 5189365의 상한 finding을 Schema 경유로 재검증하고 registry/manifest 경계 결정, migration 분기 상태 확인.
- 합격 증거: 1024 shard 허용, 1025 shard의 파일 읽기 전 VAL-0002/422 거부. Schema 제한 제거 시 시험 실패. DB migration head 및 기존 모델 관련 시험.
- 기존57.81%/VF운영0/5 유지. 독립 소스 검토는 실행시험·CI·운영 인수가 아니다.

## 작업과 확인

- Claude 검토5189365/832397e/9847912를 원작성자 commit 그대로 cherry-pick. 원문 수정 없이 별도 판정한다. CX-01 fixture 제거 및 CX-02/03/04 소스 검토 수신; 이 이후 수정의 독립 재검토는 미완료.
- finding1: reviewed d6d9d87부터 Schema maxItems1024와 shard/replica index maximum1023 존재. manifest_copy가 먼저 Schema 검증하므로 기존 구현은 조기 VAL-0002/422 거부. 중복 런타임 제한 추가 불필요. 정확한1024 허용·1025 거부 시험 추가.
- mutation: 별도 프로세스의 cached Schema에서 개수/두 index 상한 제거 시1failed(exit1). 디스크source 변경0. pytest wrapper exit0은 예상실패 확인 성공. mutation.json 참조.
- 격리 PostgreSQL16: run_vf_security_tests.py로 core manifest, model commit/locality/runtime/retry, S10 registry, prior0042→0043 migration 시험117passed/0skipped/0failed,92.72초,exit0. runtime node-dependent suites는 runner 정책상 제외. 실제5대/운영SSO 인수 아님.
- finding2: [[모델 레지스트리와 실행 Manifest 권한 경계]]1.0.0 및 ADR 보강. 명시적 결속 전 두 구조 유지, inv_app 권한 확장 없음. 커널 정책 선언은 이미 존재; 이름/URI/hash 자동결속 금지. 후속결속/공개API 미구현.
- finding3: alembic heads exit0 단일0043. prior migration 시험 포함; 운영DB 적용은 별도.
- ready replica와 실행 verified_nodes의 동등성 표현은 정정: 현재Node/epoch/프로젝트·bytes 재검증이 추가로 필요하다.
- check_docs474·check_ontology exit0. 전체sync --check exit1(기존 외부/비관리 충돌), 출처 검증한 제한 범위만 동기화 예정.

## 다음 첫 행동

Codex: commit/push/같은SHA CI·제한 Obsidian export 후 소유자 범위 replica 관측API. Claude: 위 판정과 정책 경계 재검토, 명시적 ModelVersion 결속 설계. 운영owner: CI billing/SSO/PITR/실제5대. 기존57.81%/VF운영0/5 유지.


## 전달 결과

e735df91ad4e6e125e7c5879cb6e7d68a78d0efc push 완료. draft PR25 https://github.com/egparadise/SaintVision-Invion/pull/25 (base PR24). 동일SHA CI34936056271/276/290은 billing으로 시작 전 실패(annotation4). 제한Obsidian9파일 hash일치/pending0/conflict0, 일반Codex 공유판은 외부편집 보존. 최종영수증 포함 같은범위 재동기화. 구현/로컬검증과 기존독립소스검토 수신 완료; 새판정 독립재검토/CI/운영 미완.
