---
doc_id: "HIST-STORAGE-CHECK-REPORT-20260912"
title: "2026-09-12 STORAGE-CHECK Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T11:12:57+09:00"
source_of_truth: "Git"
---

# STORAGE-CHECK 검증보고

CX-01/CX-02/CX-07 · S12-ST. owner Codex(검토/교차 구현), 원래 task owner Claude/reviewer Codex. 보완본 독립 reviewer Claude pending. base3080cf4 → 제품8c6805f → Linux harness **a7d0f5ef62e5aba2ca15e943270050d6403bf3ef**, PR19 draft. [[2026-09-12_STORAGE-CHECK_Codex_착수]].

## 확인한 문제와 구현

Claude71cf2c0의 --node는 문자열 비교뿐이라 기계 신원 증명이 아니었다. 원본은 입력 node와 일치하는 DB 폴더에 로컬 파일 결과를 운영 기록으로 썼다. 기준 hash가 없어0개를 검증한 경우·byte_size가 다른 경우도 healthy였다. 원본3개 실제 파일/DB 시험에서 각각 기록1개(기대0), healthy true(기대false) 두 건을 재현했다. [[2026-09-12_STORAGE-CHECK_오류와해결]].

같은 tools/storage_check.py에서 operator root·tenant/contribution/declared node가 일치할 때만 ReadRoot로 hash/size를 검사한다. 입력은 --dsn-env, SQL은 READ ONLY+REPEATABLE READ, sample은1~1000이며 SQL LIMIT도 적용한다. 운영 기록/승인 옵션은 제공하지 않는다. local sample/Node 증명 없음/기록0/미검사 수를 분리한다. [[Codex 로컬 폴더 점검과 Node 증명 계약]](ADR-086).

기존 service healthy는 zero sample·검증 불가 항목을 성공으로 취급하지 않는다. 주의 대상 집계가 과거 잘못된 healthy/같은 최신 시각의 실패/미래 시각/오래된 ORM cache를 재평가한다. migration·과거 row는 변경하지 않았다. 직접 SQL의 과거 boolean 제약까지 보강한 것은 아니므로 raw healthy만으로 인수하지 않는다.

## 실제 검증

| 명령·환경 | 결과 | 근거 |
|---|---|---|
| cx01_local.py -p conftest .work/test_storage_check_original.py | 원본3개 assertion failure, exit1; 실제 Windows 합성파일/PostgreSQL | [원본 재현](../Evidence/storage-check-original-71cf2c0.json) |
| cx01_local.py tests/test_storage_check_integrity.py tests/test_pilot.py tests/test_verification.py tests/test_verification_readroot.py tests/test_backup_verification_integrity.py | **105 passed,0 skipped,exit0**, clean8c6805f Windows/실제 DB | [Windows cases](../Evidence/storage-check-windows-8c6805f.json) |
| check_kernel_docker.py --prepared ... --tests 위5개+tests/test_operational_readiness.py+tests/integration/test_recovery_drill.py | **138 passed,0 skipped,exit0**, clean a7d0f5e Linux/실제 DB | [Linux cases/source hashes/images/cleanup](../Evidence/storage-check-a7d0f5e.json) |
| git push origin agent/codex/workspace-bridge |8c6805f/a7d0f5e exit0|PR19|
| 같은 SHA Actions6개 | 계정 결제/한도로 job 시작 전 failure | [CI ID/annotation](../Evidence/storage-check-a7d0f5e-ci.json) |

Linux138 = 새 Storage25+pilot35+파일13+root23+백업14+readiness10+복원18. Windows105는 root18이며 readiness/복원은 Linux에서만 이번 실행에 포함했다. 서로 겹치는 시험을 합산하지 않는다. a7d0f5e는 테스트 이미지에 tools/storage_check.py를 포함하는 allowlist1줄 변경뿐이며 제품 코드/새 시험은8c6805f와 같다. 초기57개 사전검증, private fixture setup3개 오류, 첫 Linux 이미지 준비는 최종 통과 수에 세지 않는다.

## 실제 환경과 인계

[읽기 전용 LAN](../Evidence/storage-check-lan-20260912.json):11:11 KST .225 online/fresh, lan-observe-v1, killSwitch=true, userWorkloadSubmission=false. 실제 원격7개/실행 프로필 설치는 여전히 미완료. 운영 DB·계정·Node·PKI 변경 없음.

다음 Codex는 기존 Node mTLS/epoch/승인 root 설정에 challenge와 결과를 묶고, 실제 인증된 관측만 기존 StorageCheck/Evidence에 원자 기록하는 경계를 구현한다. CLR/Node identity를 hostname이나 --node 문자열로 대신하지 않는다. 실제 .225 profile 수신 시 CX-03을 재개한다. Claude는 보완본 독립 검토/운영 문서 조율, Gemini는 sample 일치·Node unverified·운영 unknown을 구분한다. 인계 수신은 대기이며 다른 Agent 검토를 대신 완료하지 않았다.

Gemini fa01d77은 서버/스모크2파일 변경과 작성자133/106/63/5 보고를 수신했다. 이번에 해당 UI·서버 여정을 독립 재실행하지 않았고 기존 finding을 삭제하지 않는다. [외부 원문/hash](../Evidence/obsidian-proposals-20260912-storage-check/manifest.json).

## 진척 재계산

[48개 row와 계산](../Evidence/development-progress-storage-check-20260912.json): S12-ST **25→50만 변경**한다. 설계/기록 함수에서 실제 허용 폴더 파일 점검·read-only DB/CLI까지 확보했기 때문이다. Node 인증 결과 기록·object bytes·운영 매체 전체 복구·사용자 인수가 남으므로75/100이 아니다. 원래 owner Claude를 보존하고 Codex 교차 구현 증거를 붙였다. **2775/4800=57.81% 완료,42.19% 잔여**는 개발 성숙도 추정이며 운영 합격률/남은 시간의 비율이 아니다. 이전 요약의 owner별 stale 집계도48개 row에서 다시 계산했다. 공식 task done0, CI/peer/운영 인수는 계속 미완료다.

문서 검사·보고 push·Obsidian 결과는 전달 영수증에 추가한다.

전달 준비: check_docs.py exit0(원문24·문서309·작업48), check_ontology.py exit0, git diff --check exit0. Python 변경3파일 Black 적용. PR19 설명 갱신/draft 유지. 외부2파일의 원문/hash를 보존했고 최종 보고 commit 뒤 동일 bytes 인수·정본 sync를 수행한다.

보고5cca4eb commit/push exit0. 2026-09-12T11:13:49+09:00 외부 원문2개 동일 bytes 인수(목적지 쓰기0) 후 Obsidian check/apply/check exit0:540개 해시 일치·pending0·충돌0. [동기화 영수증](../Evidence/storage-check-obsidian-20260912.json). 이 영수증을 포함한 최종 문서도 commit/push 후 재동기화한다. OneDrive 클라우드 업로드 완료는 확인하지 않았다.
