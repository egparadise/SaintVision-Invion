---
doc_id: "HIST-DB-ROLE-REVOKE-VERIFY-20260912"
title: "2026-09-12 DB-ROLE-REVOKE 검증판정정정"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T20:49:30+09:00"
source_of_truth: "Git"
---

# 인증 거부 판정 정정

[[2026-09-12_DB-ROLE-REVOKE_Codex_운영적용보고]]. 운영 SQL은성공했고역할flag/권한/runtime검증도정상이었으나,private검증wrapper가접속실패SQLSTATE28000/28P01만을인증거부로인정해exit1을냈다. psycopg/libpq접속초기의 OperationalError에서는이번sqlstate가None이었다.

후속검증은서버의명시적 `password authentication failed for user` 응답을확인했고,connection-refused/timeout과구분했다. 기존credential연결은거부됐으며,정상runtime DSN은성공했다. 원문오류/DSN/password는출력하지않았다. 역할NOLOGIN/passwordNULL·변경이후fresh관측까지확인해최종exit0으로기록했다. 이오류를SQL적용실패로보고자격증명을복원하거나재실행하지않았다.
