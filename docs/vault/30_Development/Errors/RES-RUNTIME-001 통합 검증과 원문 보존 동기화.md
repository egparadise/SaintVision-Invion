---
doc_id: "RES-RUNTIME-001"
title: "통합 검증과 원문 보존 동기화"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T09:06:00+09:00"
source_of_truth: "Git"
---

# 통합 검증과 원문 보존 동기화

[[ERR-RUNTIME-001 통합 migration과 취소 기대값 및 문서 충돌]]의 후속이다.

Alembic offline mode에서는 PostgreSQL 원문 SQL을 그대로 출력하고 online mode에서는 실제 driver로 실행한다. fixture는 두 DSN 변수 모두 각 suite가 새로 만든 disposable DB를 가리키게 한다. Backend는 서비스 migration의 upgrade/downgrade와 전체 신뢰성 chain의 forward upgrade를 구별한다. 전체 Core suite의 skipped/failure/error는 CI에서 거부한다.

취소 시험은 durable non-execution 증명과 동일한 idempotency 요청의 replay를 확인하도록 정정했다. `1de376d` Core 34418862634에서 808개, `d1e1246` Core 34419166305에서 부모 Run을 포함한 812개가 모두 통과했다.

Obsidian 문서 충돌은 원문 byte를 `30_Development/Evidence/runtime-sync-reviewed-proposals.json`에 base64와 SHA-256으로 보존하고 개별 비교했다. 일곱 문서는 이미 병합 검토한 `720b8ee` 정본과 일치하고, 두 저자 보고서는 BOM/개행만 다르다. 저자 History와 모든 인계 기록을 보존하며 Codex 후속 ADR/검증 기록이 빠진 이전 index를 최신 정본으로 통합했다. 자동 채택 대상은 이 9개 hash뿐이며, 이후 외부 변경은 다시 충돌로 보호한다. 전체 apply와 사후 hash 결과는 최종 검증보고에 연결한다.

문서 병합 검토자 Codex. 코드의 독립 검토자 Claude의 실제 검토나 수신을 의미하지 않는다.
