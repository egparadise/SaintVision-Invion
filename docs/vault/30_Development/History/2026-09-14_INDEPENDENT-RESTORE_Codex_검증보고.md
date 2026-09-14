---
doc_id: "HIST-INDEPENDENT-RESTORE-REPORT-20260914"
title: "2026-09-14_INDEPENDENT-RESTORE_Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T17:56:33+09:00"
source_of_truth: "Git"
---

# 원래 서버 역할에 의존하지 않는 복원 검증

CX-01/S12-ST지원 owner Codex/reviewer Claude pending. clean **33785f2db6f02ffe27eb7580497da479f5c9934e**, branch agent/codex/workspace-bridge. [[2026-09-14_INDEPENDENT-RESTORE_Codex_착수]]. 신규 tools/rehearse_independent_restore.py 및경계시험10개.

## 실제 수행

17:50:12~17:50:25 KST 기존보관snapshot의고정SHA를확인한뒤 **별도 Docker PostgreSQL16 cluster**에복원했다. 입력SHA256 **361c4f32a211e2029a4d38370d086d913afa58ccfb5eb9e7f32476b602ee9c5c**,2,167,833bytes. 기존보관경로/내용/권한을수정하지않았으며운영DSN을읽거나운영DB에접속하지않는다(별도후속운영역할점검과구분).

bootstrap은 inv_app/inv_kernel/inv_lan_runtime를안전한NOLOGIN으로생성하고난수검증login하나에inv_kernel을부여했다. 운영비밀번호를복사하지않았다. 역할이나grant를무시하는 --no-acl/--no-owner 복원도아니다. 이명시적bootstrap과맞지않는미래backup은자동으로임의role을추가하지않고실패한다.

- **130테이블**, 테이블별조회행수합계 **28,726**의모든열/행hash가보관manifest와일치. partition부모/자식중복집계가능성때문에고유업무row수라고부르지않는다.
- 실제0023→0037 Alembic upgrade 및동일head replay성공. 기존열projection 보존,재실행전체inventory동일.
- 안전한NOLOGIN bootstrap그룹유지. definer9개검사 unsafe0. 새비소유자runtime으로원래tenant의Node조회성공,다른tenant조회0.
- 원본보관백업재읽기동일. 일회cluster삭제확인. 실행report에코드SHA/dirty=false/도구·migration sourcehash/Python·PGimage고정값을기록했다.

`python tools/rehearse_independent_restore.py --backup <private backup directory> --expected-sha256 <pinned hash> --output .work/independent-restore-final.json`: exit0. Evidence independent-restore-33785f2.json.

실제별도cluster에고정hash는맞지만PGarchive가아닌합성파일을입력한음성시험: **exit2/failedStage=restore-pinned-archive**,일회cluster정리확인. 원본문구/DB진단은노출하지않고sanitized failure evidence를남김. Evidence independent-restore-invalid-33785f2.json.

`python -m pytest -q tests/test_independent_restore.py`: **10 passed/0.51초/exit0**. pin변조·크기·hardlink·입력형식·기존report보존. 본경계시험의합성bytes를실제DB복원성공과혼동하지않는다.

## 해소 범위와 잔여

같은cluster role에의존하던복원시험의한계를해소했다. 여전히같은물리PC의폐기Docker이며 **off-device backup/PITR/전원차단/운영전환 인수는 아니다**. full사용자Workspace/Node재개와새OIDC credential 복구도이시험에서완료하지않았다.

동일33785f2 CI6건은결제/한도로job미시작/failure(Core34824750767/34824745462,Backend34824750558/34824745479,Docs34824750606/34824745422). 독립검토·CI·운영인수미완료. 다음Claude 운영백업/복원계약독립검토,S12-ST운영절차반영;Codex 원격재연결/실제Workspace재개및전환준비. 전체57.81% 완료/42.19% 잔여유지.

최종 정본 문서384개/48작업 검사·ontology·git diff --check 모두exit0. 검증 중 발견한 오류·조치 및 다음 담당을 별도 History/진행판에 기록했다.

동기화 2026-09-14T17:58:11+09:00, source3851a95301ceec88360b69a0eb9367679bf5a6e5, 관리814개 전체hash일치/pending0/conflict0. 로컬 Obsidian 사본 검증이며 OneDrive cloud 업로드는 미확인. receipt 추가 정본도 다시 내보낸다.

17:58:44 KST 읽기 전용 재확인: inv_app LOGIN=false/password 없음 유지, 원격 .225:18443 접속 불가. Evidence continuation-final-observation-20260914.json. 원격 PC 준비 비동기 요청의 응답은 아직 없다. 다음 실장비 단계는 연결 복구 후 진행하며, CI 결제 제한·실제 OIDC 설정·독립 검토·운영 인수는 완료로 바꾸지 않는다.
