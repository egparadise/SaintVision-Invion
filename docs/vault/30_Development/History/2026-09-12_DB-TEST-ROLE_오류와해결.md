---
doc_id: "HIST-DB-TEST-ROLE-ERROR-20260912"
title: "2026-09-12 DB-TEST-ROLE 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T20:10:58+09:00"
source_of_truth: "Git"
---

# 실패와 수정

[[2026-09-12_DB-TEST-ROLE_Codex_검증보고]]. 첫 관련 DB45개/Compose5개는 통과했으나 추가 bootstrap 검증을 포함한7b8b118 최종 시험에서 init-db.sql의 UTF-8 BOM 때문에 SyntaxError가 발생했다.4ec4c5d에서 BOM을 제거했다.

운영 클러스터에 새 폐기용 DB를 만들었던 중간 시험에서는 외부 before/after 공용 역할 상태 비교가 달라짐을 감지했다. 변경 주체는 확인하지 못했으며 최종 불변성 증거로 채택하지 않았다. 최종 시험은 별도 PostgreSQL 컨테이너로 옮겼고51개 통과/공용 그룹 불변/임시 역할 정리를 확인했다. 원시 실패 로그·credential/hash는 private .work에만 보존한다.

기존 운영 inv_app은 아직 LOGIN 가능 상태다. 소스 파일 수정은 이미 설치된 credential 폐기가 아니며, 구 fixture가 다시 실행되면 재발할 수 있다. 검증된 remediation SQL은 critical 운영 적용 승인 대기다.
