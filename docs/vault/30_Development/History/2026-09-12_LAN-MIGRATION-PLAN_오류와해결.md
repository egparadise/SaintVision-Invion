---
doc_id: "HIST-LAN-MIGRATION-PLAN-ERROR-20260912"
title: "2026-09-12 LAN-MIGRATION-PLAN 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T18:18:23+09:00"
source_of_truth: "Git"
---

# 판정 오류와 실제 재현

[[2026-09-12_LAN-MIGRATION-PLAN_Codex_검증보고]]. 이전 점검의 has_table_privilege만으로는0037의 열별 GRANT SELECT를 인정하지 못한다. 필수 열의 has_column_privilege와 schema USAGE를 함께 확인하도록 수정했다.

첫 실제 PostgreSQL 검증은14 passed/1 failed: inv_app의inv schema 접근이 없어 to_regclass에서InsufficientPrivilege가 발생했다. 권한 없는 metadata도pg_class/pg_namespace로 존재를 먼저 조사한 후schema USAGE=false이면 조회불가를 반환하도록 수정했다. 이후 실제1개 포함15개 모두 통과,0023 upgrade/replay1개 통과. 원시 실패 로그는 private .work에 보존하고 credential-bearing traceback을 공개 Evidence에 복사하지 않았다.

운영 alembic_version을 runtime 역할로 읽을 권한은 없다. 권한 확대 대신 관리 연결에서READ ONLY로 version metadata만 읽었다. 운영 schema/역할 변경 없음. 남은 차단은 실제 backup 복원·운영 적용/프로필·인수와CI 결제 제한이다.
