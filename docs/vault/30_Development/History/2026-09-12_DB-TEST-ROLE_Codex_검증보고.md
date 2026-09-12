---
doc_id: "HIST-DB-TEST-ROLE-REPORT-20260912"
title: "2026-09-12 DB-TEST-ROLE Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T20:10:58+09:00"
source_of_truth: "Git"
---

# 공용 역할 오염 경로 수정

CX-01 Codex owner/Claude reviewer pending. base0c771b5→제품7b8b118→BOM 수정4ec4c5df5382a4a43bab99d0feb5290503665721, agent/codex/workspace-bridge. commit/push exit0. [[2026-09-12_DB-TEST-ROLE_Codex_착수]].

## 변경

`tests/conftest.py`는 더 이상 공용 inv_app의 LOGIN/password를 변경하지 않는다. 시험별 inv_backend_login_<uuid> 역할과 난수 password를 만들고 기존 inv_app 그룹을 상속한다. NOSUPERUSER/NOBYPASSRLS/NOCREATEDB/NOCREATEROLE/NOREPLICATION을 지정하며 engine dispose 후 자신이 만든 역할만 DROP한다. 정상·본문 예외 시 정리와 공용 역할 flag/password 불변을 실제 DB에서 검증했다. 프로세스 강제 종료 시의 자동 janitor는 범위 밖이다. 이 login도 클러스터 역할이며 살아 있는 동안 그룹 권한을 상속하므로 테스트 전용 PostgreSQL 클러스터를 사용해야 한다.

`deploy/init-db.sql`에서 고정 password LOGIN 역할 생성과 광범위 GRANT를 제거했다. migration이 NOLOGIN 그룹/권한의 정본이다. 파일의 기존 UTF-8 BOM이 PostgreSQL 실행 오류를 일으켜 제거했다. `docker-compose.prod.yml`은 DB login DSN·PostgreSQL admin password·MinIO admin/password를 명시적 필수 환경값으로 요구하며 기본값이 없다. 기존 DB credential을 자동 교체하는 변경은 아니고, 완전한 factory 설정/API 인증·설정 파일 mount는 후속이다.

## 최종 검증

- 최종 clean4ec4c5d: 별도 폐기용 PostgreSQL 컨테이너(임시 localhost 포트,메모리data),운영DSN 미사용에서 `python -m pytest tests/test_database_login_isolation.py tests/test_database.py tests/test_projects.py tests/core/test_deployment_credentials.py -q --junitxml=.work/db-test-role-isolated.xml`: exit0,51 passed/0 skipped. 실제 DB46/Compose config5. Alembic path_separator deprecation warning1개. 공용 그룹 NOLOGIN/password 유지, 임시 역할 목록 원복, 컨테이너 정리 확인.
- 7b8b118의 remediation SQL: 별도 network-none PostgreSQL 컨테이너에서 실제 inv_app 시험 세션을 만든 뒤 실행하여 거부/원상태 유지 확인. 그 시험 세션을 종료한 뒤 NOLOGIN/passwordNULL과 동일 SQL replay 통과. 운영 클러스터에는 실행하지 않았다. 이후4ec4c5d 변경은 init-db.sql BOM뿐이며 remediation SQL 동일.
- CI4ec4c5d/20:10:03 KST:6개 모두 billing 제한으로 job 미시작/failure. 독립 reviewer pending,main merge 미완료.

Evidence: [[db-test-role-4ec4c5d.json]], [[db-test-role-4ec4c5d-tests.xml]], [[db-role-remediation-7b8b118.json]], [[db-test-role-4ec4c5d-ci.json]].

## 운영 조치 제안과 다음 담당

제안 파일 `deploy/remediate-shared-app-role.sql`은 startup/migration에 연결하지 않았다. 관리자 연결에서 현재 inv_app 세션이 있으면 거부하고, 없으면 transaction 안에서 `ALTER ROLE inv_app NOLOGIN PASSWORD NULL`을 수행한다. inv_app 그룹 권한과 배포별 login membership은 유지한다. 기존 세션을 강제 종료하지 않으며 검사와commit 사이 신규접속 경합/구버전 테스트 runner의 재변경까지 막는 자동 fencing은 아니다. 적용 전 구버전 runner 중지·다른 Agent의 최신 fixture 반영·서비스 직접 inv_app 의존 확인이 필요하다.

운영 DB 접속권한을 바꾸는 critical 작업이므로 사용자의 기존 비critical 자동승인 범위에 포함해 실행하지 않았다. 최종 응답에서 위 조치의 운영 적용 승인을 요청한다. 승인을 받으면 Codex가 현재 연결/설정을 다시 확인하고 새 로그인 차단을 적용한 뒤 난수 배포 login과Node 관측이 유지되는지 검증한다. 활성 세션이 있으면 SQL이 중단되므로 임의 종료하지 않는다.

Claude: 코드/SQL 독립 검토와 현재 작업 lane의 구 fixture 변경 반영. Gemini: 배포 환경 변수 주입/정본 factory 설정·인증 준비,기본 credential fallback 재도입 금지. 모든 Agent는 예전 공용 inv_app ALTER ROLE fixture를 운영 연결에서 다시 실행하지 않는다.

전체2775/4800=57.8125%,잔여42.1875% 유지. 재발 방지 코드는 수정됐지만 기존 운영 credential 폐기/CI/독립 검토/실제 운영 인수는 미완료. 보관 백업은 앞선 [[2026-09-12_LAN-RETAINED-BACKUP_Codex_검증보고]]를 따른다. 최종 문서 검사와 sync 영수증은 후속 기록한다.
