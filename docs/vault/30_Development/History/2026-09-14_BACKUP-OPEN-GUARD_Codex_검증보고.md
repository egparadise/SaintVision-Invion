---
doc_id: "HIST-BACKUP-OPEN-GUARD-REPORT-20260914"
title: "2026-09-14 BACKUP-OPEN-GUARD Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T19:47:26+09:00"
source_of_truth: "Git"
---

# 보관 백업 읽기 경계 보완

CX-01/CX-07/S12-ST 지원. Codex 작성, Claude 독립 검토 pending. 제품 3eced3bf89191f9beb060973c78a09adcc058634 commit/push 완료.

검사 후 일반 Path.read_bytes/read_text로 재개방하던 입력을 기존 ReadRoot로 통합했다. 동일 root identity, 열린 파일의 크기 상한, 링크/교체 거부, bounded 재읽기 검증을 적용했다. 독립 복원 종료 시 archive와 manifest 모두 보존됐는지 비교한다. OS 관리자 공격 방어나 파일시스템 snapshot을 주장하지 않는다.

- Windows `python -m pytest tests/test_independent_restore.py tests/core/test_lan_restore_upgrade.py -q`: exit 0, 24 passed/6.96s. 검사 직후 hardlink 추가, 열린 파일 크기 제한, 같은 크기 내용 변경 거부 포함. 내용 변경 사례는 주입한 stream 경계 시험이다.
- Windows `python -m pytest tests/test_verification_readroot.py -q`: exit 0, 18 passed/1.21s. 기존 실제 파일/링크/Windows 경계 회귀 확인. 합계 42개이며 Linux 시험으로 표시하지 않는다.
- clean 제품 SHA에서 `PYTHONPATH=src;services/control-plane/src`를 지정하고 `tools/rehearse_independent_restore.py --backup <private retained directory> --expected-sha256 <기존 pin> --output <new report>` 실행: exit 0. 19:46:16 KST 완료. 별도 Docker PostgreSQL16, 130테이블/조회행 합계28726(유일 업무행 수 아님), 원본 inventory/hash 일치, 0037 upgrade/replay/기존열 보존, definer9 unsafe0, runtime/tenant격리, 백업보존, 소유 cluster 제거. [복원 증거](../Evidence/backup-open-guard-restore-3eced3b.json).
- 처음 CLI는 PYTHONPATH 미설정으로 ModuleNotFoundError, exit1이었다. DB 접속 전 실패이며 환경 지정 후 성공했다. [[2026-09-14_BACKUP-OPEN-GUARD_Codex_오류와해결]].
- 같은 SHA CI6건 모두 billing 제한으로 job 시작 전 실패. [CI 증거](../Evidence/backup-open-guard-ci-3eced3b.json). CI 통과/통합 완료 아님.
- 실제 .225:18443 TCP 재확인 불가. [관측](../Evidence/backup-open-guard-observation-20260914.json). mTLS/원격7개 시험 미수행.

문서385개/48task 검사 및 ontology exit0(착수 문서 시점). 보고 추가 후 별도 검사 결과를 전달한다. 독립 검토/운영 OIDC/원격 설치·7개/5대 최종 인수/off-device/PITR 미완료, 전체 성숙도2775/4800=57.81% 유지. 다음 Codex는 원격 준비 후 실제 설치·mTLS·7개, Claude는 이 변경과 기존 커널 변경 독립 검토, Gemini는 정본 승인/샤드/ResultView 계약 연결을 확인한다. Obsidian sync는 Git 보고 commit 후 수행하고 실제 영수증을 남긴다.

## 전달 확인

보고 포함 문서387개/48task와 ontology 검사 exit0. 8744d85 commit/push 후 19:48:02 KST Obsidian check→apply→check 모두 exit0, 관리822파일 hash 일치/pending0/conflict0. 로컬 mirror 확인이며 OneDrive cloud 완료 주장은 아니다. [동기화 영수증](../Evidence/backup-open-guard-sync-8744d85.json).
