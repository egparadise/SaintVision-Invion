---
doc_id: "HIST-VF-SERVICE-REVIEW-001"
title: "VF 서비스 독립 검토와 통합"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-15T14:23:32+09:00"
source_of_truth: "Git"
---

# VF 서비스 독립 검토와 통합

- 카드 VF-CX-01 후속 / VF-CL-01~04 독립 검토. owner Codex, 원본 작성자 Claude; Codex 수정은 Claude 재검토 pending.
- base dd04562; branch agent/codex/vf-service-integration; 검토 대상 Claude7ef9a3c.
- INDEX-PROGRESS-001 1.0.78, WORKBOARD-VF-CODEX-001 1.0.7; GUIDE-001/GOV-AGENT-001/GOV-GIT-001 및 영역 계획1.0.0, ADR-INDEX-001, agent-delivery1.1.0/core-reliability1.0.0 읽음.
- 루트 integration 진행판은 오래됨. 최신 Codex VF05 Git 기록을 기준으로 기존01~04 구현을 반복하지 않는다.
- 범위: URI parser/resolver, replica repair, catalogue/model 시험을 최신0042 코어와 대조. 운영DB/credential/실장비 변경 없음.
- 합격: 격리 PostgreSQL non-owner/RLS, pin 보존과 이탈 처리, URI 왕복, model release gate. 실패는 finding으로 기록한다.

## 독립 재현 결과와 수정

- Claude7ef9a3c 원본 시험: storage catalog/model registry/URI resolver/replica repair 56 passed, exit0, skip0. 격리 PostgreSQL16·Python3.14·non-owner runtime 역할.
- 독립 경계 시험: 4 failed, exit1. R1: ready replica에 pinned_until을 설정하고 이탈 처리하면 ck_data_replicas_only_ready_replicas_pin CheckViolation으로 transaction 실패. R2: dataset/model URI 끝의 slash를 parser가 받아들이지만 builder가 제거해 왕복 불일치(2건). R3: version에 slash를 허용해 version과 path의 구분이 사라짐.
- 0043_replica_retention은 기존0042 뒤의 forward migration. 데이터·pin·과거 migration은 보존하고 stale 상태에도 기존 retention pin이 남도록 제약을 변경한다. 실제 운영 DB에는 적용하지 않았다.
- replica 이탈 writer는 replica_id 순서의 FOR UPDATE로 읽기/쓰기 사이 상태 변경을 직렬화한다. unavailable/corrupt 바이트는 물리 회수 전까지 cache_usage에 남긴다. stale 복제본은 resolver·repair source·eviction 후보에 포함하지 않는다.
- URI builder는 version/identifier에 모호한 slash를 거부하고 parser는 빈 dataset/model path suffix를 거부한다. 물리 경로의 안전성 검사는 기존 pathsafe/open 경계를 계속 사용한다.
- 1차 수정 시험: 관련85 passed, exit0. 이후 반복 이탈, retention, cache 용량, resolver/repair/eviction 제외와 추가 identifier 거부를 보강하고 전체 회귀 실행.
- 원본 서비스 독립 판정: changes requested였으며 이 후보에 Codex 수정 포함. 이 수정에 대한 Claude 독립 재검토는 pending. 작성자 검토를 독립 검토로 세지 않는다.

## 환경 오류

최초 시스템 Python에는 psycopg가 없어 실행되지 않았고, PowerShell 기본 파이프 encoding이 한국어를 손상시켰다. 저장소 .venv Python과 명시적 UTF-8 OutputEncoding으로 재실행하고 착수 문서를 복구했다. 두 초기 실패를 제품 실패/통과 수치에 포함하지 않는다.

## 다음 담당과 미완료

- Codex: 전체 회귀 결과·code SHA·CI·Obsidian 전달 증거 기록.
- Claude: 0043 pin 제약/이탈 writer와 URI 입력 경계 재검토. resolver/repair는 서비스 함수이며 공개API·전송 실행·ModelManifest 확장 인수는 아직 아니다.
- 운영 owner: CI billing·실제 원격 연결/5대·SSO/PITR. 기존57.81%, VF 운영인수0/5 유지.

후보 image build exit0: saintvision-backend-candidate:vf-service-integration / sha256:b21d97dcbdaf3d3a602df07ac62e57b7137d22e1c21747711c6691f15de13217. deployment_surface.py --dockerfile deploy/Dockerfile.backend exit0: 설정 없는 canonical factory 거부.


## 전달 전 검증

새 image digest를 사용한 실제 server container/최종 경계/정본 migration graph 19 passed, exit0. 0042 제약 아래 기존 pin이 있는 행을0043으로 바꾸는 별도 실 PostgreSQL upgrade 1 passed, exit0: 모든 열 보존 후 stale 전이 및 pin 보존 확인. 전체 회귀는 진행 중이며 이 시점에 통과로 기록하지 않는다.

문서 검사 exit0(467문서), ontology exit0. 전체 Obsidian check는 외부/비관리 문서 충돌로 exit1; 전체 apply 미실행. 이번 신규 History/Evidence만 저장소 export 함수로 check→apply→check, 최초4개 파일 hash 일치/최종pending0/conflict0. 공통 진행판과 기존 문서의 공유본 갱신은 아직 대기다.
