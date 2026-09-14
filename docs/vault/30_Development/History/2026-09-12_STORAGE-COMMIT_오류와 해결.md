---
doc_id: "ERR-STORAGE-COMMIT-20260912"
title: "2026-09-12 STORAGE-COMMIT 오류와 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T13:23:04+09:00"
source_of_truth: "Git"
---

# 2026-09-12 STORAGE-COMMIT 오류와 해결

첫 PostgreSQL 실행19개 중16통과/3실패(exit1). 실패는 fixture의 revoked_at 누락, channel.enabled 수정 시 version CAS 누락, Run version만 바꾸는 금지 전이였다. 실제 schema 규칙에 맞게 revoked_at/forward version/state=cancelled를 함께 변경했다. 최종 Windows22 및 clean fd0c081 Linux156 통과(exit0). DB 제약을 완화하지 않았다.

Studio 로그인401은 서버가 살아 있는 상태에서 세션이 없는 경우였다. 실제 바탕화면에 없던 시작 바로가기를 현재 실행 checkout의 기존 Start-DevStudio.ps1로 복구하고 새 세션 생성을 확인했다. 인증 우회/키·토큰 출력 없음. 사용자 화면 직접 재확인은 미수행.

GitHub6개 CI는 account payments/spending limit으로 job 시작 전 실패. 코드를 재시도해 해소할 오류가 아니므로 반복 rerun하지 않고 운영 책임자 조치 후 동일 SHA 실행을 기다린다.
