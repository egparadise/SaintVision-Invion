---
doc_id: "RES-CORE-001"
title: "RES-CORE-001 입력 검증 수정과 CI 대체 검증"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-09T17:03:45+09:00"
source_of_truth: "Git"
---

# RES-CORE-001 입력 검증 수정과 CI 대체 검증

[[ERR-CORE-001 초기 검증 및 실행 환경 실패]] 대응. requirements-test/core/docs를 기존 .venv에 설치하고 date-time checker 없으면 fail-closed, PolicyDecision 전체 스키마 검증, NaN/음수 bandwidth 거부를 적용했다. 재실행 exit 0, 45 passed. 소스/스키마 입력 값은 오류 메시지에 출력하지 않는다.

sandbox 오류는 승인된 외부 실행으로 작업했고 환경 자체 복구를 주장하지 않는다. Docker 환경은 미복구이며 PostgreSQL 검증은 Core Build의 격리 service에 구성했다. 실제 CI 결과는 개발 보고 참조; 구성만으로 통과를 주장하지 않는다.

수정 `c36f41d`의 Core Build #34331695971, Documentation Build #34331696095 success. PostgreSQL 포함 66 tests/0 failures/0 errors/0 skipped의 JUnit을 [[core-c36f41d-tests.xml]]에 보존했다. Windows Docker/sandbox 환경 자체는 미복구이며 CI 검증과 구별한다.
