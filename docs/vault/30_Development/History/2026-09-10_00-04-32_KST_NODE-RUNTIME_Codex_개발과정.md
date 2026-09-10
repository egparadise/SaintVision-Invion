---
doc_id: "DEV-NODE-RUNTIME-001"
title: "Codex Linux Node 실행기 개발 과정"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T00:04:32+09:00"
source_of_truth: "Git"
---

# Codex Linux Node 실행기 개발 과정

Task node-runtime; owner Codex; reviewer Claude; branch agent/codex/node-runtime; base `85a8747a92efd56d14ed7fdfcba85fe03f60463f`.

입력: GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND-001/PLAN-S03 v1.0.0, ADR-INDEX-001 v1.3.0, TOOL-CONTRACT-001 v1.0.0, agent-delivery/core-reliability v1.0.0. 사용자 다음 작업 진행 및 critical 외 일반 작업 승인 유지.

OUT-03/AC-03·OUT-04/AC-04 → 실제 CI Linux Docker 합성 probe의 격리/종료 증거, 서명 위조·재전달·crash·timeout·stop 확인 실패 시험 → 서명된 NodeExecutionPermit·durable Node inbox·Docker driver·NodeStopReceipt → S03-BE Node 실행 코어. 기존 선행/독립 검토 미완료로 baseline task는 승격하지 않는다.

scope: Linux Go Node 실행 library/제한 CLI, Ed25519 허가, 단일 로컬 Docker socket driver, durable inbox·보수적 복구·monotonic watchdog, 종료 receipt와 원자 Lease 반환, canonical schema/생성물, 관련 tests/CI/docs. 운영 PKI/mTLS bootstrap·Windows OS driver·GPU·실제 5대 장비 배포는 후속. 사용자 Docker/WSL 재시작 없이 CI의 전용 합성 컨테이너만 시험한다.

공식 근거: Docker Engine API v1.45, Go time monotonic clock, santhosh-tekuri/jsonschema v6.0.2, Cryptography 50.0.1 changelog/Ed25519 API. 구현·명령·exit·SHA·CI ID·hash·동기화 결과는 후속 보고에 기록한다.

환경: 로컬 Go/cryptography 없음. Go는 기존 CI 1.23 계열과 같은 1.23.12 portable toolchain을 프로젝트 .work에 설치하고 다운로드 공식 SHA-256을 확인한다. 신규 cryptography는 고정 50.0.1을 사용한다. Windows sandbox 초기화 실패는 승인된 외부 실행으로 대응한다. 작업별 Obsidian check에서 이전 기록으로 돌아간 외부 사본 10개 충돌을 확인했으며 쓰지 않았다.

## 2026-09-10T00:50:04+09:00 로컬 구현 검증

Go 1.23.12 portable SHA 검증 후 프로젝트 전용 설치. Go 단위 검사 및 Linux cross-build exit 0. Python pytest exit 0: 89 passed / 실제 PostgreSQL·Linux가 없는 로컬 105 skipped. 실제 통합 성공 증거는 CI에서 별도로 확보한다. duplicate key/JSON depth 경계 시험 최초 실패 후 root depth를 1로 계산하도록 수정하고 회귀 통과. 제품 사고가 아닌 개발 중 발견이다.

[[Codex Node 실행 격리와 정지 영수증 계약]] NODE-RUNTIME-CONTRACT-001 v1.0.0 / ADR-INDEX-001 v1.4.0(ADR-027/028). cryptography 50.0.1, Go JSON Schema v6.0.2, JSON Schema v1alpha1 생성 타입·embedded validator·migration 0004 구현. 후속 CI 및 reviewer Claude pending.

## 2026-09-10T01:16:02+09:00 원격 검증 및 전달

`git commit`·`git push -u origin agent/codex/node-runtime` exit 0. 구현 `98d02be8528c3a09c5d38239fd8fcce93affa39e`의 Core #34373543925 및 Documentation #34373543859 success. GitHub artifact 원본에서 Python 194/0/0/0 및 Go 14 top-level/37 leaf case 통과를 확인했다. [[2026-09-10_01-16-02_KST_NODE-RUNTIME_Codex_검증보고]]에 실제 증거를 보존했다. reviewer Claude 독립 검토 pending.
