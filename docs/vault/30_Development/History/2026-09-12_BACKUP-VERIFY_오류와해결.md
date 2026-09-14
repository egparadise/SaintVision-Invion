---
doc_id: "HIST-BACKUP-VERIFY-ERROR-20260912"
title: "2026-09-12 BACKUP-VERIFY 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T02:31:57+09:00"
source_of_truth: "Git"
---

# 2026-09-12 BACKUP-VERIFY 오류와해결

[[2026-09-12_BACKUP-VERIFY_Codex_검증보고]]의 실제 오류 기록.

- base135b15a 기존 verification 서비스에 새 실제5개 시험 적용 →5 failed/exit1: 검증 선기록, baseline 대체, tenant 확인 전 I/O, 동시 첫 검증 덮어쓰기 재현.
- 4ddb622: 비교 전 row 잠금·최신값·baseline 확인, 비교 후 savepoint 기록, 항목별 sweep 실패 격리. Linux78/Windows DB60 통과. 재검증 실패가 이전 성공 관측을 삭제하지 않는다는 한계를 명시.
- CI6개: 계정 결제/한도로 시작 전 failure. 운영 책임자 해소 후 동일 SHA에서 재검증 필요.
- 남은 경계: hash_file은 경로 문법 검사만 수행. open-time root/links/교체 검증은 다음 작업이며 이번 합격으로 표시하지 않음.
