---
doc_id: "ERR-RUNTIME-001"
title: "통합 migration과 취소 기대값 및 문서 충돌"
version: "1.0.0"
status: "resolved"
author: "Codex"
updated: "2026-09-10T09:06:00+09:00"
source_of_truth: "Git"
---

# 통합 migration과 취소 기대값 및 문서 충돌

RUNTIME-COMPLETION 작업에서 실제 관찰한 오류다.

- 로컬 통합 pytest exit 1: 최신 Codex migration의 offline driver 접근으로 15 errors. SQL DDL wrapper의 `%I` 보간 오류도 확인했다.
- Core CI 34418400806 / `0d25b57`: 795 passed, 2 failed. 기존 미수신 취소 시험은 예약 유지라는 이전 동작을 기대했고, 신규 replay 시험은 같은 key에 다른 version을 보냈다.
- Backend CI 34418400793: 신뢰성 migration의 의도적 downgrade 금지와 별도 runtime suite의 환경 요구가 기존 backend workflow와 맞지 않았다.
- `python tools/sync_obsidian.py --check` exit 1: 이전 audit state와 Obsidian의 통합 브랜치 문서 9개가 달랐다. 도구는 0개를 썼다. 7개는 `720b8ee`의 정확한 byte hash, 2개는 저자 본문이 같고 BOM/개행만 달랐다.

해결 및 증거는 [[RES-RUNTIME-001 통합 검증과 원문 보존 동기화]]에 기록한다. 테스트 오류나 문서 충돌을 실제 제품 실행 성공으로 바꾸어 기록하지 않는다.
