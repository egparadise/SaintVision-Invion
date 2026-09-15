---
doc_id: "HIST-CONFIGURED-SERVER-ERROR-20260912"
title: "2026-09-12 CONFIGURED-SERVER Codex 오류해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T22:06:28+09:00"
source_of_truth: "Git"
---

# 기동 설정과 오래된 시험 기대값

Compose가 INV_DATABASE_URL만 전달하고 정본 factory의 INV_RUNTIME_DSN/INV_RECOVERY_EPOCH/INV_API_CONFIG 및 신뢰 파일 mount를 누락했다. healthcheck도 존재하지 않는 /v1/health였다. 필수 변수와 읽기 전용 mount, 실제 /readyz로 수정했다. 운영 스택 기동을 수행했다는 의미는 아니다.

격리 PostgreSQL과 실제 HTTP를 포함한 첫 시험은 13 passed/1 failed(exit 1). 실패는 기존 migration 경계 시험의 downgrade_target 기대값이 0036이었던 것. 현재 0037은 불가역 migration이므로 head와 안전한 downgrade 경계를 0037_storage_sample_commit으로 갱신했다. 과거 미병합 graph 시험은 이후 revision의 수동 제외 목록 대신 당시 정렬 prefix를 사용한다. 수정 후 해당 경계 3개 통과(exit 0). FastAPI/Starlette deprecation warning 2개는 별도 의존성 후속이다.
