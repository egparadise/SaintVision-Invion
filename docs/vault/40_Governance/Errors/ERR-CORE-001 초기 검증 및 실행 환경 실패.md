---
doc_id: "ERR-CORE-001"
title: "ERR-CORE-001 초기 검증 및 실행 환경 실패"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-09T17:03:45+09:00"
source_of_truth: "Git"
---

# ERR-CORE-001 초기 검증 및 실행 환경 실패

2026-09-09 Codex core-foundation. 기존 core 시험은 날짜 검증 dependency 누락, 정책 unknown field 미검증, Decimal NaN 비교 예외, 음수 bandwidth 수용으로 4 failed/41 passed(exit 1). jsonschema FormatChecker는 optional date-time dependency가 없으면 해당 검사를 건너뛰었다.

Windows exec/apply_patch sandbox 초기화가 helper_unknown_error로 실패. Docker pg16 시험 컨테이너 생성 후 시작·재시도 모두 newosproc/errno=11로 exit 1. 사용자 컨테이너나 daemon을 재시작하지 않았다. 실패 컨테이너 saintvision-core-test-20260909는 시작되지 않은 상태다.

해결과 범위: [[RES-CORE-001 입력 검증 수정과 CI 대체 검증]].

Core Build #34330563460 (e6336a7)에서 PostgreSQL migration 구문 오류를 재현했다. Run trigger IF 식의 CASE를 괄호로 감싸고 PL/pgSQL block END 구분자를 명시했다. 문서 CI #34330563371은 success. 수정 SHA의 DB 재검증 전 완료 아님.
