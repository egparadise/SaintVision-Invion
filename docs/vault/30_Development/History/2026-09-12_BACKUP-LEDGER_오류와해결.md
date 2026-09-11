---
doc_id: "HIST-BACKUP-LEDGER-ERROR-20260912"
title: "2026-09-12 BACKUP-LEDGER 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T01:57:25+09:00"
source_of_truth: "Git"
---

# 2026-09-12 BACKUP-LEDGER 오류와해결

[[2026-09-12_BACKUP-LEDGER_Codex_검증보고]]의 실제 재현과 해결 기록.

- B1 원본8a8f3b4: 기존 합성 백업 파일을 덮어써도 savedBackupIntact=true. 420b81c에서 새 파일만 게시·기존 경로 보존·동시 저장 한 승자로 수정, 실제 파일13개 검증.
- B2 원본은 write/readback만 수행하고 fsync/게시 경계 없음. 수정은 file/directory sync와 확인 후 수신. 주입한 두 sync 오류에서 영수증 없음, DB rollback은 원장/drill0행 및 파일 보존으로 확인.
- P1/P2 d63717f: 프로젝트 A→B→A가 false drift, disabled operator가 mayApproveAsOperator=true. 원본 실제 DB2개로 재현. 수정본 수신/통합 대기이며 현재 Codex 진단은 승인 unknown 유지.
- CI420b81c: 6개 모두 계정 결제/한도로 job 시작 전 실패. 로컬 성공을 CI 성공으로 쓰지 않음. 운영 책임자 해소 후 같은 코드 SHA 재실행 필요.
