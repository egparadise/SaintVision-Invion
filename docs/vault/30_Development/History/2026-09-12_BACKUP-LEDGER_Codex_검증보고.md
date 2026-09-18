---
doc_id: "HIST-BACKUP-LEDGER-REPORT-20260912"
title: "2026-09-12 BACKUP-LEDGER Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T01:57:25+09:00"
source_of_truth: "Git"
---

# 2026-09-12 BACKUP-LEDGER Codex 검증보고

CX-01/CX-09 · S11-DB/S11-ST/S12-DB 후속. owner Codex / reviewer Claude pending. base8c7761b, 구현 **420b81c0be034f6b58c49cc4219f240b7d114f3c**, agent/codex/workspace-bridge, PR19 draft. [[2026-09-12_BACKUP-LEDGER_Codex_착수]].

## 변경과 계약 ADR-081

Claude8a8f3b4의 기존 BackupRecord 연결을 현재 recovery_drill.py 정본에 조율했다. 새로운 원장·결과 API를 만들지 않았다. 기존 RPO gate/0036/definer/tenant/measurement 검증을 유지한다. migration 변경 없음.

1. --save-backup은 기존 private Linux 디렉터리의 새 절대 경로만 허용한다. 경로의 symlink·..·공유 디렉터리를 거부한다. 0600 임시 파일에 쓰고 file fsync → 덮어쓰기 없는 link 게시 → 임시 이름 제거 → directory fsync → 단일 링크/owner/mode/inode/bytes 검증을 수행한다. 같은 목적지의 동시 저장은 하나만 성공한다. 기존 파일·디렉터리·symlink를 덮어쓰지 않는다.
2. 복원은 저장 후 읽어 검증한 bytes를 사용한다. 원장 기록 직전에 경로의 실제 파일 identity/hash/크기/권한을 재검사한다. 변조·교체·소실이면 savedBackupIntact=false, backup verified=false, drill outcome failed/met_targets=false로 기록하며 CLI acceptance도 거부한다. 기능 복원이 먼저 성공했어도 현재 저장 파일의 검증과 구분한다.
3. 기존 pilot.record_backup(kind=logical) → 조건부 verify_backup → record_recovery_drill(backup_id)을 한 트랜잭션으로 실행한다. 성공 식별자는 commit 이후에만 report에 둔다. DB 실패는 두 기록 모두 rollback하며 파일은 보존한다. 자동 재시도/중복 성공 선언은 없다.
4. off_site=false와 offSiteVerified=false 유지. 로컬 fsync/readback 관측은 별도 장애 영역·하드웨어 전원 장애·PITR·운영 RPO 보증이 아니다. Windows 네이티브 저장은 아직 지원하지 않으며 검증된 Linux/WSL Linux 실행 환경에서만 새 저장을 허용한다. WSL의 Windows 공유 경로를 지원한다고 간주하지 않는다.

파일 게시와 DB는 분산 원자 트랜잭션이 아니다. file/directory sync 또는 DB 실패 후 private 임시/게시 파일이 남을 수 있다. 자동 삭제하지 않고 운영자가 파일/해시/원장을 대조한다. 사용자는 새로운 파일 이름을 사용하고 기존 파일의 삭제·덮어쓰기로 재시도를 흉내 내지 않는다. DB verified는 해당 관측 시점의 로컬 파일 확인이며 영구 불변성이나 주기 재검증을 뜻하지 않는다. 과거 외부 파일 손상은 별도 재검증 업무다.

## 검증

| 환경·명령 | 결과 | 근거 |
|---|---|---|
| check_kernel_docker.py --tests tests/test_backup_publication.py tests/integration/test_recovery_drill.py tests/test_pilot.py | **63 passed / 0 skipped / exit0**, clean420b81c | [Linux63](../Evidence/backup-ledger-420b81c.json) |
| pytest core recovery_verdict/recovery_capability | **50 passed / exit0** Windows | [검증/재현](../Evidence/backup-ledger-review-20260912.json) |
| 원본8a8f3b4 save block | 기존 합성 파일 덮어쓰기 후 savedBackupIntact=true 실제 재현 | 같은 근거; Windows 일회용 파일, 전체 복원 아님 |
| 원본d63717f snapshot/grants, 격리 PostgreSQL | 문제 재현2개 통과, 기능 합격 의미 아님 | 같은 근거 및 아래 독립 검토 |
| git push origin agent/codex/workspace-bridge |420b81c exit0 | PR19 |
| 같은 SHA GitHub Actions6개 | 계정 결제/한도로 job 시작 전 실패 | [CI ID/annotation](../Evidence/backup-ledger-420b81c-ci.json) |

Linux63은 실제 파일13·실제 복원18·pilot32개다. 저장 경합/기존 경로 보존/파일 및 디렉터리 fsync 실패/동일 바이트 다른 inode/링크/권한/소실/변조/DB rollback을 포함한다. 소유 격리 DB·runner·network만 사용·정리했다. 이전69/90/154개와 합산하지 않는다. 새로운 DB migration이 없어 업그레이드23개를 반복하지 않았으며 이전b49ecd3 증거를 새 코드의 재실행으로 쓰지 않는다.

## Claude d63717f 독립 검토 — 변경 필요

- **P1 프로젝트 비교 범위:** snapshot_permissions의 previous 조회가 tenant·user만 필터링한다. payload에 projectId가 있어도 비교 대상 조회를 제한하지 않는다. 같은 사용자 A→B→A의 동일 권한에서 실제 changed=[null,true,true], 같은 프로젝트 비교의 기대값은 [null,null,false]. 프로젝트/관측 계약 버전으로 비교 범위를 고정하고 동시 snapshot의 순서를 정해야 한다.
- **P1 비활성 운영자 승인 과장:** grants는 operator row enabled=false를 layers.holds=false로 표시하면서 mayApproveAsOperator를 can_approve 하나로 계산해 true를 반환했다. 실제 DB로 재현했다. 현재 Codex 정본은 mayApprove=null을 유지하므로 이 결함을 통합하지 않았다. 관측된 capability와 현재 작업 인가를 분리하고 enabled/person/subject/operation 조건을 고려한다.
- **P2 관측 시점·동시성:** report는 DB를 읽고 연결을 닫은 뒤 다른 transaction에서 snapshot과 now를 기록한다. payload는 읽기 시점 값이지만 taken_at은 이후 시각이다. 같은 사용자의 동시 기록도 직전 비교를 직렬화하지 않는다. 소스 검토 지적이며 동시 crash 시험 완료가 아니다. 관측 시점/기록 시점을 명시하고 같은 일관 snapshot 및 비교 순서 계약을 정한 뒤 통합한다.

[원본 함수 재현 코드](../Evidence/permission-review-reproduction-20260912.txt)는 고정 d63717f를 읽어 기존 서비스/격리 DB로 실행한다. 작성자 권한 snapshot 코드를 현재 운영 도구에 덮어넣지 않았다. Claude의 후속ade5bb8 AC-12 집계 호출자도 수신했지만 이번 독립 검토 범위에는 포함하지 않았다.

## 전달·다음 행동

- Codex: permission snapshot의 프로젝트/관측시점/순서 계약을 정하고 Claude 수정본과 ade5bb8 AC-12 집계의 evidence 범위를 검토한다. 원격 프로필 수신 시 CX-03 실제7개를 재개한다.
- Claude: 420b81c/ADR-081 독립 검토. 위 P1/P2를 d63717f 후속에서 수정하고 프로젝트 A/B·disabled·동시성 재현을 포함한다. 승인 완료로 표기하지 않는다.
- Gemini: backupVerified와 기능 복원/운영 RPO를 구분하며 private 파일 경로나 진단값을 실제 다운로드 권한으로 사용하지 않는다. 기존 UI finding/실장비 인수는 별도다.

전체 추정 **57.29% 완료 /42.71% 잔여 유지**. CI·독립 검토·운영 RPO·물리 장비 인수 미완료로 공식 task done 승격 없음. check_docs.py(원문24·문서294·작업48), check_ontology.py, 변경 Python3개 Black 검사, git diff --check 모두 exit0. Obsidian 사전 check:490개·pending13·충돌0·쓰기0. PR19 설명 갱신, draft 유지. 보고7d18b4a push exit0. 2026-09-12 01:58:06 KST Obsidian490개 해시 일치·pending0·conflict0, check/apply/check exit0. [동기화 영수증](../Evidence/backup-ledger-obsidian-20260912.json). 영수증 포함 최종 문서도 commit/push 후 재동기화한다. OneDrive 클라우드 업로드 완료는 확인하지 않았다.
