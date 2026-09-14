---
doc_id: "HIST-MIGRATION-GUARD-REPORT-20260914"
title: "2026-09-14_MIGRATION-GUARD_Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T13:47:24+09:00"
source_of_truth: "Git"
---

# Migration 진입점 검사와 운영 로그인 재발 복구

CX-01, owner Codex/reviewer Claude pending. [[2026-09-14_MIGRATION-GUARD_Codex_착수]]. 제품 SHA3742f113dfef7fc13facab4a3d1a24fe179a7fe5, CI 설정221d253. branch agent/codex/workspace-bridge. published migration/0037 head는 변경하지 않았다.

## 작업과 확인

Alembic online 진입점에서 schema 쓰기 전에 inv_app/inv_kernel의 LOGIN·SUPERUSER·BYPASSRLS·CREATEDB·CREATEROLE·REPLICATION을 확인한다. 위험한 기존 그룹은 거부하며, 없는 그룹/안전한 그룹은 정상 migration을 허용한다. 역할 변경은 하지 않는다. Offline SQL은 실제 권한 확인이 아니다. 모든 ACL·membership·password 감사나 동시 superuser 변경 봉쇄를 보장하지 않는다. Claude87eeb71 helper가 published0001에서 호출되지 않는 범위를 실제 진입점으로 보완했다.

`INV_TEST_ROLE_GUARD_IMAGE=postgres:16 python -m pytest -q tests/test_migration_role_guard.py --junitxml=.work/migration-guard-tests.xml`: 실제 별도 Docker PostgreSQL16에서 **13 passed/28.03초/exit0**. 그룹2개×위험플래그6개=12개 거부 시 schema 무변경/role flags 보존, absent→head0037→정상그룹 replay1개 성공. ambient DSN을 사용하지 않는다. Evidence migration-guard-tests-20260914.xml. Backend workflow에도 opt-in image 설정을 추가해 이 시험이 skip되지 않도록 연결했다. CI 실행 성공은 별도 미확인이다.

`docker build -f deploy/Dockerfile.backend -t saintvision-backend-candidate:migration-guard .`: exit0, image sha256:bdffd91082fbd40ec09a0a1fb97cb4b050b7f22ef26b1ea5efb9813c8e7c3bb4. 이 단계는 build이며 운영 컨테이너 전환 증거가 아니다.

## 운영 DB 재발과 조치

13:43:39 KST 읽기 전용 검사에서 inv_app LOGIN/password 재활성화 발견. 직접 세션0, 실제 서비스는 inv_lan_runtime. Windows Python 프로세스 명령 패턴에 pytest/alembic/test_ 실행은 없었지만, 이 확인만으로 모든 DB 변경 주체를 배제하지 않는다. 재활성화 주체/시각은 아직 모른다.

2026-09-12 사용자가 승인한 공용 로그인 폐기 범위에 따라 **13:45:50 KST 동일 SQL 재적용**: inv_app NOLOGIN/password NULL 확인, 세션 강제 종료 없음. deploy/remediate-shared-app-role.sql SHA256 b3f0e99b48b7776fa3f53ec03856fa50eeaa12782a5b4b77977d2d31042facf8. 전후 membership·relation ACL/RLS flag·policy·schema head 해시 동일. 서비스 전용 계정으로 inv.nodes 조회 성공. tenant context 없는 이 조회의 행수0은 온라인 Node 없음의 증거가 아니다. 적용 후 online guard 읽기 전용 재검사 통과. Evidence migration-guard-revocation-20260914.json.

13:46 KST 별도 tenant-aware 읽기 전용 점검: .225 offline/fresh=false, 마지막 snapshot **2026-09-13 19:50:38 KST**, lan-observe-v1, killSwitch=true/epoch일치. 운영schema0023, 코드0037. storage 관계2개 없음·관측계정 public storage 조회 제한·공개 교체묶음 미갱신. plan/readiness 명령 exit1은 차단 항목 발견이며 실행 성공이 아니다. Evidence migration-guard-lan-plan-20260914.json 및 migration-guard-lan-readiness-20260914.json. 운영 schema/profile/kill switch 변경 없음.

## CI·인계·남은 작업

3742f11 동일 SHA CI6건은 계정 결제/한도로 job 시작 전 failure: Core34807041392/34807038643, Backend34807041340/34807038612, Docs34807041306/34807038606. Evidence migration-guard-3742f11-ci.json. 로컬 시험을 CI 통합 검증과 동등하다고 보고하지 않는다.

- Codex: Node 재연결 상태 확인, 준비된 운영 후보의 실제 설정/OIDC·migration 계획 연결, 원격 프로필 설치 이후 실행·취소·복구7개 검증. 재활성화 원인 추적은 미완료이며 새 guard는 관리자에 의한 직접 ALTER ROLE을 차단하지 않는다.
- Claude: 본 변경 독립 검토, 구 fixture/운영 스크립트의 공용 역할 재활성화 경로 점검, 운영 OIDC issuer/audience/client ID와 권한 바인딩 준비. F1은 이전 OFFER-SNAPSHOT 실제 잠금 회귀증거로 재확인.
- Gemini: 최신 관측의 offline/stale·관측 전용 상태와 실제 readiness 표시, configured server 정본 연결 후 브라우저 검증.

전체 성숙도 **2775/4800=57.8125% 완료,42.1875% 잔여** 유지. CI/독립검토/운영 인수 미충족으로 task done 또는 통합 완료 선언하지 않는다. 문서검사·ontology·Obsidian sync 결과는 후속 기록한다.

최종 CI 설정221d253 동일 SHA도6건 job미시작/계정결제 failure(Core34807287175/34807284997,Backend34807287203/34807284980,Docs34807287174/34807285007). Evidence migration-guard-221d253-ci.json. 문서372개/48작업 검사 및 ontology 모두exit0, git diff --check exit0.
