---
doc_id: "HIST-LEGACY-ROLE-REPAIR-REPORT-20260914"
title: "2026-09-14_LEGACY-ROLE-REPAIR_Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T17:56:33+09:00"
source_of_truth: "Git"
---

# 오래된 Codex 시험fixture와 운영로그인 재발 대응

CX-01 owner Codex/reviewer Claude pending. [[2026-09-14_LEGACY-ROLE-REPAIR_Codex_착수]]. 실제상주서비스의코드경로가 C:/Project/SaintVision-Invion/agent-codex-dev-environment임을프로세스의script경로로확인했다. 이worktree의tests/conftest.py에는공용inv_app LOGIN/password변경코드가남아있었다. integration/currentworkspace의fixture는이미수정돼있었다.

**해당fixture가이번재활성화를실행했다는증거는없다.** 확인시pytest/alembic프로세스및inv_app직접세션은0이었다. 확정한것은재활성화가능한구코드경로와실제DB재발이다. 변경주체/정확한실행시각의규명은미완료다.

## 수정과 검증

별도clean Codex branch agent/codex/dev-environment의base97e68af에서tests/conftest.py와신규시험만변경, **4da131fa24342fafc062fae3bad7a0704b4a64fa** commit/push. 현재workspace의검증된application_test_engine을backport했다. 난수개별login을생성해inv_app권한을상속하고정리하며공용역할의LOGIN/password를변경하지않는다. 상주서비스파일/실행프로세스는변경하거나종료하지않았다.

별도Docker PostgreSQL16에서해당옛branch 자체의 `tests/test_role_fixture_preservation.py tests/test_database.py`: **21 passed/3.67초/warning1/exit0**. 정상/예외종료에서공용그룹불변과개별login정리,실제RLS/tenant격리·schema검증. Evidence legacy-role-4da131f-tests.xml. 다른Agent의작업파일을함께stage하지않았고옛vault전체를export하지않았다.

## 운영 대응

17:51:08 읽기전용검사에서inv_app LOGIN/password=true. 직접세션0/전용서비스inv_lan_runtime확인후,9월12일기존사용자승인범위의 **동일NOLOGIN PASSWORD NULL SQL을17:54:35 KST 재적용**했다. SQL SHA256 b3f0e99b48b7776fa3f53ec03856fa50eeaa12782a5b4b77977d2d31042facf8. 전후membership·ACL/RLS·policy·schemahead해시동일,서비스전용runtime조회성공,online migration guard통과. 세션강제종료없음. tenant설정없는query행수0은Node온라인대수판정이아니다.

Evidence legacy-role-before-20260914.json/legacy-role-revocation-20260914.json. 독립복원report의sourceDatabaseContacted=false는복원도구범위이고,이별도운영역할점검/조치와혼동하지않는다.

4da131f CI3건(Core34825118183,Backend34825118226,Docs34825118316)은결제/한도로job미시작/failure. 검토pending. 구코드경로하나를수정했지만모든과거checkout/외부관리자에의한재활성화를봉쇄했다고주장하지않는다. 다음각Agent 구fixture재사용금지및이수정반영,Claude 독립검토,Codex 운영재발관측/원격프로필/실행7개. 전체57.81% 유지.

최종 정본 문서384개/48작업 검사·ontology·git diff --check 모두exit0. 검증 중 발견한 오류·조치 및 다음 담당을 별도 History/진행판에 기록했다.

동기화 2026-09-14T17:58:11+09:00, source3851a95301ceec88360b69a0eb9367679bf5a6e5, 관리814개 전체hash일치/pending0/conflict0. 로컬 Obsidian 사본 검증이며 OneDrive cloud 업로드는 미확인. receipt 추가 정본도 다시 내보낸다.

17:58:44 KST 읽기 전용 재확인: inv_app LOGIN=false/password 없음 유지, 원격 .225:18443 접속 불가. Evidence continuation-final-observation-20260914.json. 원격 PC 준비 비동기 요청의 응답은 아직 없다. 다음 실장비 단계는 연결 복구 후 진행하며, CI 결제 제한·실제 OIDC 설정·독립 검토·운영 인수는 완료로 바꾸지 않는다.
