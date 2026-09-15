---
doc_id: "HIST-VF-REPLICA-OBSERVATION-001"
title: "VF 소유자 범위 복제본 상태 관측"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T15:16:03+09:00"
source_of_truth: "Git"
---

# VF 소유자 범위 복제본 상태 관측

## 착수

- VF-CX-01/02 후속 owner Codex/reviewer Claude pending. base1f71d89/agent/codex/vf-replica-observation, 시작2026-09-15T15:16:03+09:00.
- INDEX-PROGRESS-0011.0.82/WORKBOARD-VF-CODEX-0011.0.11, 기존GUIDE/ADR/역할/운영/로드맵/연속정책, agent-delivery1.1.0/core-reliability1.0.0 적용.
- 범위: URI로 현재 사용자가 등록한 active contribution의 location에 대한 기록상 replica 상태별 개수만 조회. tenant/소유권/활성 gate와 집계를 단일 SQL snapshot으로 묶는다.
- 합격: 실제JWT/non-ownerPG/정본factory에서 소유자·tenant격리·상태별집계·빈집합·폐기·잘못된URI·GET전용. 집계 하나가 다른 시점의 허가/합계와 섞이지 않는다.
- node ID/경로/복사후보/현재실행가능 여부는 응답하지 않는다. availability unknown, 실행시재검증 필요를 고정한다. 프로젝트공유/ModelVersion결속/복구실행/운영배포 범위 아님.

## 작업과 확인

- 새 GET /v1/storage/replica-status?uri=... 및 필수 reader_user_id service. 소유권·active gate/tenant별 replica join/상태count를 단일SELECT로 수행. SQL에서최대5행만반환하며 node/path 후보정보를 공개하지 않는다.
- location/version/DB statement시각·5상태count·total을 반환. 현재가용성unknown/실행재검증true는 strict 응답Schema로 고정. 기록상ready와 현재실행권한을 구분한다.
- 최초31pass/3fail 및 확장136pass/1fail은 fixture/요청형식 오류로 정정. [[2026-09-15_VF_오류와_해결]] 참조.
- 최종 run_vf_security_tests.py: 실제JWT/제한inv_app·격리PostgreSQL16/정본factory로 관련137passed/0skipped/0failed exit0. 자기/타사용자/타tenant/빈집합/회수/계정정지/가짜토큰/숨긴URI/오류비반사/메서드·실제단일SELECT 확인. fixture Node는lost인데도 ready기록을보여주되 현재가용성unknown 유지.
- Dockerfile.backend image build exit0, sha256:ab9e4e56ca1e8855e9f0dabec8bf392b633019977fa0bb31a9303e9f02c9cde9. 실제image 컨테이너8passed/0skipped exit0. 새route 무인증401/알려지지않은URI404/POST거부 확인. 실제운영SSO/실장비 아님.
- Schema export20개일치/check_docs475/check_ontology exit0. [[저장소 카탈로그 조회와 URI 해석 계약]]1.1.0. 운영migration/배포변경 없음.

## 다음 담당

Codex: commit/push/동일SHA CI·제한Obsidian 동기화·인계. Claude: PR의 소유권·단일snapshot·관측의미 독립검토. Gemini: 네 storage GET을 실제화면에 연결하고브라우저검증. ModelVersion결속은 [[모델 레지스트리와 실행 Manifest 권한 경계]] 독립검토 후 별도카드로. CI billing/SSO/PITR/실제5대는운영owner. 기존57.81%/VF운영0/5 유지.
