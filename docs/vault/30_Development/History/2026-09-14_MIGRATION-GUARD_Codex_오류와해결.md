---
doc_id: "ERR-MIGRATION-GUARD-20260914"
title: "2026-09-14_MIGRATION-GUARD_Codex_오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T13:47:24+09:00"
source_of_truth: "Git"
---

# 공용 로그인 재활성화 감지

[[2026-09-14_MIGRATION-GUARD_Codex_검증보고]] 참조. 온라인 검사에서 `Unsafe migration permission group; operator reconciliation required: inv_app: rolcanlogin` 발생. 9월12일 폐기 후 재활성화가 확인되었으나 작성 주체는 불명이다.

직접 세션0과 서비스 전용 계정 확인 후, 기존 사용자 승인에 따라 동일 NOLOGIN/password NULL SQL 재적용. 권한/정책/schema 해시 보존 및 실제 runtime 조회/guard 재검사 성공. 자동 migration에서 역할을 고치도록 변경하지 않았다. 원인 제거 완료로 보고하지 않으며 구 브랜치의 fixture·관리자 호출 경로 추가 점검이 필요하다.

별도 현황: 원격 Node는 stale/offline, CI는 계정 결제 제한으로 시작 전 실패. 이 둘은 DB role 조치로 해결된 것이 아니다.
