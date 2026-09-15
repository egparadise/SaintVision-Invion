---
doc_id: "ERR-LEGACY-ROLE-REPAIR-20260914"
title: "2026-09-14_LEGACY-ROLE-REPAIR_Codex_오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T17:56:33+09:00"
source_of_truth: "Git"
---

# inv_app LOGIN 재발

13:45 폐기뒤17:51 읽기전용확인에서공용로그인재활성화발견. 실행주체는불명. 구Codex worktree에남은재활성화fixture를찾아4da131f로수정하고,해당branch 자체의격리PG21시험통과. 직접세션0확인후17:54:35 기존승인동일SQL로공용로그인재폐기·권한/schema보존. [[2026-09-14_LEGACY-ROLE-REPAIR_Codex_검증보고]].

재활성화주체규명/모든과거branch 봉쇄/CI/운영인수는완료하지않았다. 구fixture를복사하거나공용그룹에직접LOGIN/password를설정하는도구를재사용하지않는다.
