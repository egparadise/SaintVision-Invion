---
doc_id: "RES-APPROVAL-001"
title: "RES-APPROVAL-001 테스트 모듈 분리와 재검증"
version: "1.0.0"
status: "resolved"
author: "Codex"
updated: "2026-09-09T22:58:56+09:00"
source_of_truth: "Git"
---

# RES-APPROVAL-001 테스트 모듈 분리와 재검증

원인 [[ERR-APPROVAL-001 승인 테스트 수집 충돌]]. core 파일을 test_approval_contracts.py로 변경했다. 수정 후 python -m pytest -q --junitxml=.work/approval-local-tests.xml: exit 0, 63 passed / 38 PostgreSQL skipped. DB 동작은 이 결과로 보증하지 않으며 실제 CI PostgreSQL 결과는 검증 보고에 연결한다. runtime grant 잠금에는 고정 sentinel 컬럼 권한을 사용해 실제 권한 projection 컬럼의 변경을 차단한다.
