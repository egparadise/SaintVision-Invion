---
doc_id: "ERR-APPROVAL-001"
title: "ERR-APPROVAL-001 승인 테스트 수집 충돌"
version: "1.0.0"
status: "resolved"
author: "Codex"
updated: "2026-09-09T22:58:56+09:00"
source_of_truth: "Git"
---

# ERR-APPROVAL-001 승인 테스트 수집 충돌

개발 중 core와 integration에 같은 test_approvals.py 파일명을 사용하여 pytest 수집이 import file mismatch로 중단됐다(exit 1). 업무 DB나 제품 실행 단계의 실패가 아니다. 수정과 재실행은 [[RES-APPROVAL-001 테스트 모듈 분리와 재검증]]을 따른다. 승인 migration의 동적 RLS SQL은 작성 후 읽기 검토에서 문자열 인용 누락을 발견해 dollar quote로 고쳤으며 실제 SQL 실행 검증은 CI에서 수행한다.
