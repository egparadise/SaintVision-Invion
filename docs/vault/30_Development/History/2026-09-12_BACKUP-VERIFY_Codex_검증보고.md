---
doc_id: "HIST-BACKUP-VERIFY-REPORT-20260912"
title: "2026-09-12 BACKUP-VERIFY Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T02:31:57+09:00"
source_of_truth: "Git"
---

# 2026-09-12 BACKUP-VERIFY Codex 검증보고

CX-01/CX-07/CX-09 · S08-ST/S11-ST/S11-DB. owner Codex / reviewer Claude pending. base135b15a → 구현 **4ddb622a1992568c891db321a32bfd1e3993d421**, agent/codex/workspace-bridge, PR19 draft. [[2026-09-12_BACKUP-VERIFY_Codex_착수]].

## 발견과 보완

운영 Evidence 연결을 검토하던 중 기존 services/verification.py의 선행 검증 결함을 발견했다. 기존 파일 verifier를 수정했으며 새 Evidence 저장소/인수 완료 플래그를 만들지 않았다.

| 실제 재현 | 수정 |
|---|---|
| 크기가 다른 파일도 verify_backup이 먼저 verified/checksum을 flush. sweep은 오류를 잡고 커밋하여 실패가 검증됨으로 남음 | tenant/backup 행 잠금·최신 값 재조회 → 실제 파일 읽기 → 모든 크기/hash 비교 → savepoint 안에서만 검증 상태 저장 |
| 직접 호출도 예외를 잡고 같은 transaction을 commit하면 잘못된 검증 상태가 남음 | 비교 실패 전 쓰기0, 검증 상태 갱신 후 추가 오류도 savepoint rollback |
| caller가 expected_sha256을 생략하면 과거 기준 checksum을 새 파일 값으로 덮음 | 저장된 checksum을 항상 기준으로 사용. caller hint는 기준을 대체할 수 없음 |
| 다른 tenant/없는 backup 요청도 파일을 읽은 뒤 대상 row를 거부 | 같은 tenant의 실제 row 확인·잠금이 파일 I/O보다 먼저 |
| 동시 최초 검증 두 개가 다른 bytes를 둘 다 확정 | FOR UPDATE + populate_existing으로 최신 기준을 재조회하여 한쪽만 최초 기준을 확정 |

sweep은 항목별 savepoint와 resolver/read 오류 분리를 적용한다. 실패한 항목은 failed, 다음 정상 항목은 verified로 보고한다. limit은 실제 int1~100만 허용한다. 파일 읽기 오류에서 원본 경로/OS 예외 내용을 반사하지 않는다. migration 변경 없음.

## 실제 검증

| 명령·환경 | 실제 결과 | 근거 |
|---|---|---|
| 수정 전 test_backup_verification_integrity.py 최초5개, 실제 Windows 파일·격리 PostgreSQL | **5 failed, exit1**. 모두 위 결함을 재현 | [원본·보조 증거](../Evidence/backup-verify-review-20260912.json) |
| check_kernel_docker.py: test_backup_verification_integrity/test_verification/test_pilot/integration/test_recovery_drill | **78 passed,0 skipped,exit0**, clean4ddb622 Linux | [case·SHA·이미지·정리](../Evidence/backup-verify-4ddb622.json) |
| cx01_local.py: test_backup_verification_integrity/test_verification/test_pilot | **60 passed,exit0**, clean4ddb622 Windows 클라이언트·실제 PostgreSQL | 같은 보조 증거; Linux와 겹치므로 합산하지 않음 |
| git push origin agent/codex/workspace-bridge |4ddb622 exit0 | PR19 |
| 같은 SHA Actions6개 | 계정 결제/한도로 job 시작 전 failure | [CI ID·annotation](../Evidence/backup-verify-4ddb622-ci.json) |

Linux78은 새 DB/파일 경계12·기존 실제 hash13·pilot35·실제 복원18개다. 초기 코드 수정 후60개 사전 검증은 최종 결과에 가산하지 않는다. Black 변경2개와 git diff --check exit0. 소유 격리 DB·runner·network만 사용·정리했으며 운영 DB/Node/키에는 적용하지 않았다. 새 migration이 없어 이전23개 upgrade를 재실행하지 않았고 과거 결과를 이번 실행으로 표시하지 않는다.

## ADR-084 — 검증의 시간과 한계

verified와 checksum은 과거의 성공 관측이다. 이번 재검증이 실패하면 이전 성공 checksum/size/시각을 변조하지 않고 예외/failed 목록으로 실패를 보고한다. **과거 verified=true가 지금의 bytes도 정상이라는 뜻은 아니다.** 현재 정상 판정에는 새 검증 성공이 필요하다. 재검증 실패의 별도 durable 관측/운영 Evidence 연결은 후속이며, 현재 집계의 evidenceComplete=false를 true로 바꾸지 않는다.

hash_file의 contribution 경로 정규화는 문법 검사다. 아직 허용 root를 descriptor/handle로 고정하는 open-time 보호가 아니다. 이 사실을 docstring에 명시했다. 이번 파일은 테스트가 소유한 경로이며 신뢰된 worker resolver를 전제했다. 임의 사용자 경로를 HTTP에 연결하지 않는다. Linux/Windows 링크·교체 경합 방어와 백업/Evidence의 운영 provenance 연결을 다음 Codex 작업으로 고정한다. 원장 row 잠금은 파일을 읽는 동안 유지되며 대용량의 lock 대기/SLO는 실측하지 않았다.

## 실제 LAN 확인

2026-09-12 02:30:21 KST localhost18082/pilot/v1/overview 읽기: 192.168.45.225, nod_01M25VZZFBYQVFGYB11G7HC10J online/fresh, **lan-observe-v1**, killSwitch=true, userWorkloadSubmission=false. 실행 profile 설치가 완료됐다고 볼 근거가 없어 CX-03 실제7개는 계속 미수행이다. 조회 결과를 5대 인수나 원격 실행 시험으로 표시하지 않는다.

## 다음 담당

- Codex: hash_file/worker resolver의 허용 root·descriptor/handle·파일 교체 경계를 구현/검증한 뒤 실제 운영 Evidence 연결을 진행한다. 원격 profile 수신 시 실제7개 재개.
- Claude: 4ddb622/ADR-084 독립 검토, sweep 실패와 과거 성공 관측을 운영 문서/consumer에서 구분. DB 기록만으로 현재 파일 정상이나 운영 인수 완료를 선언하지 않는다.
- Gemini: 이전 verified와 최근 실패를 구분할 UI 계약은 durable 관측 연계 후 조율. 기존 인증/hash/drain/ticket 인수는 별도.

전체 추정 **57.29% 완료/42.71% 잔여 유지**. CI·독립 review·운영 Evidence/5대/실장비 인수 미완료로 공식 task done을 올리지 않는다. check_docs.py(원문24·문서301·작업48), check_ontology.py, git diff --check exit0. Obsidian 사전 check는510개·pending11·충돌0·쓰기0, PR19 설명 갱신/draft 유지. 최종 push/동기화는 후속 영수증에 기록한다.
