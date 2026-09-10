---
doc_id: "RES-DISPATCH-001"
title: "RES-DISPATCH-001 명시적 fixture 및 Node 예약 직렬화"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T02:47:29+09:00"
source_of_truth: "Git"
---

# RES-DISPATCH-001 명시적 fixture 및 Node 예약 직렬화

fixture dependency를 명시적으로 import했다. ToolGateway의 claim 및 permit은 하나의 transaction으로 저장하며, Node 행 잠금 아래 같은 Node의 활성 execute worker를 확인해 뒤의 Run은 queued를 유지한다. 다른 Run의 idempotency key를 분리한 실제 PostgreSQL 시나리오를 추가했다.

구현 `3a3858eb9b1b3be63e250dc5e9b1bbb5156cd117` Core #34384656712 success. Python 301 tests / 0 failures / 0 errors / 0 skipped, Go 57 leaf cases / 0 failures / 0 test skips. 새 DB 경합·guard·원자성·취소·회복 13개 및 mTLS/Go/Docker/실제 worker CLI 5개를 검증했다. [[dispatch-3a3858e-provenance.json]]·[[dispatch-3a3858e-tests.xml]]·[[dispatch-3a3858e-unit.jsonl]]에 원본을 보존했다. [[ERR-DISPATCH-001 Fixture 의존성과 Node 실행 슬롯 경계]]의 해결이며 운영 장비나 SLO 시험을 의미하지 않는다.
