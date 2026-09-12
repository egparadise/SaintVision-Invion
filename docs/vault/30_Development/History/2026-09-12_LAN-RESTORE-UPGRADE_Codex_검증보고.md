---
doc_id: "HIST-LAN-RESTORE-UPGRADE-REPORT-20260912"
title: "2026-09-12 LAN-RESTORE-UPGRADE Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T18:55:47+09:00"
source_of_truth: "Git"
---

# 실제 데이터 복원과 upgrade

CX-02 Codex 무결성 지원/reviewer Claude pending. 상위S12-ST Claude owner 유지. based046344→코드04bd6177c8827b1b52aeeb68f21660ad5b3f79fc, agent/codex/workspace-bridge, commit/push exit0. [[2026-09-12_LAN-RESTORE-UPGRADE_Codex_착수]].

## 구현

`tools/rehearse_lan_upgrade.py`는 원본READ ONLY REPEATABLE READ exported snapshot 안에서public/inv 모든 테이블의 원래 열·행 digest와pg_dump를 읽는다. 관측 writer를 멈추지 않고 같은 시점의 비교 기준을 확보한다. dump는 같은 프로세스 메모리에서만 사용하고 공개하거나 보관 파일로 쓰지 않는다. Docker 내부 PostgreSQL client의password는argv에서 제거하고환경 전달한다.

UUID로 새로 만든inv_lan_rehearsal_* DB에만 복원/upgrade head 두 번을 실행한다. 원본과복원본의 테이블·열목록·행 digest 일치, upgrade 후 원래 열 projection 보존(alembic_version 제외), 두번째upgrade의 전체열/행 동일성을 확인한다. 최종definer 정책9개와기존runtime 역할·tenant·epoch gate transaction의Node 조회를 확인하고finally에서 자신이 생성한DB만 정리한다.

## 동일 clean SHA 검증

- `python -m pytest tests/core/test_lan_restore_upgrade.py -q --junitxml=.work/lan-restore-upgrade-tests.xml`: exit0,5 passed. 행 누락·개수 변경·내용 변경·upgrade 전version 변경 거부와upgrade 후version만 예외 확인.
- `python tools/rehearse_lan_upgrade.py --state <운영 pilot> --output .work/lan-restore-upgrade.json`: exit0, 실제 snapshot 복원/upgrade1회. 18:54:20~18:54:51 KST. 2,136,565byte archive,130개 테이블 조회 행 합계28,165(파티션부모/자식 중복 조회 가능하므로고유 레코드 수 아님). 원본snapshot과복원본 일치,기존열 보존,전체head replay 일치.0037 도달/definer9 unsafe0/runtime DB transaction 통과/폐기용DB정리 확인.
- 후속 원본metadata/관측 조회:0023 그대로,kill switch true,원격Node fresh/lan-observe-v1. Node·원본schema·원본권한·운영 scheduling 변경 없음.
- 같은 제품SHA CI 18:54:43 KST:5개failure(billing job미시작),Core34687047058 queued. CI성공 아님.

Evidence: [[lan-restore-upgrade-04bd617.json]], [[lan-restore-upgrade-04bd617-tests.xml]], [[lan-restore-upgrade-04bd617-ci.json]].

## 범위와 다음 작업

같은클러스터의기존역할을 재사용한DB복원이며 독립클러스터역할복원/영속백업보관/PITR/RPO/S3/object/Nodejournal/HTTP로그인/실제실행 재개를 입증하지 않는다. archive hash와row digest는현재 데이터 일치 증거이며원본 데이터가이미 손상되지 않았다는증거는아니다. 추가열의의미/모든신규제약/RLS실호출은이시험의완전검증범위밖이다. source 관리접속·덤프는권한있는운영자도구이며대형DB용스트리밍백업저장소가아니다. 정리시간은completedAt 이후일수있으므로표시시간을운영RTO로사용하지않는다.

다음Codex: 기존관측 서비스와최신커널의운영설정·entrypoint 호환성,실제보관백업/복원전제·적용후검증을포함한구체적DB배포계획; 이어Node후보묶음/원격경로/mTLS·Evidence·7개실행시험. Claude: 이번실제복원근거와S12복구훈련의미충족조건독립검토. Gemini: 실제커널연결·준비상태표시/브라우저인수.

전체2775/4800=57.8125%,잔여42.1875% 유지. 운영DB적용/CI/독립검토/실장비인수미완료로정식done/PR병합하지않는다. 최종문서검사·Obsidian영수증은후속기입.

## 최종 전달

문서 349개/48 task 및 ontology 검사 exit0. 18:55:59 KST/a9bae8b에서 로컬 Obsidian 690개 파일 hash 일치, pending0/conflicts0. [[lan-restore-upgrade-obsidian-20260912.json]]. OneDrive cloud 업로드는 미확인. 영수증 추가 후 최종 commit/push/sync를 다시 수행한다.
