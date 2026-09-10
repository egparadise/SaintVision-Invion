---
doc_id: "RES-CONTROL-001"
title: "RES-CONTROL-001 비실행 검증과 추적 오류 응답"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T02:31:57+09:00"
source_of_truth: "Git"
---

# RES-CONTROL-001 비실행 검증과 추적 오류 응답

heartbeat-only fixture는 command/container를 만들지 않는 목적에 맞게 Node.intent 부재를 검사하도록 수정했다(3ab41c8). 취소 시험도 실제 JWT HTTP cancel 요청을 경유하게 바꿨다. 해당 SHA Core #34382252138와 Documentation #34382252127 success.

후속 87600e9e4b5edb90a85517ebeb6c617614fbd765에서 ProblemDetails 정본 및 nullable TS/Go 생성, 요청별 nonzero trace/span ID, 무효 traceparent 대체와 일치하는 오류 body/header를 구현했다. 인증/HTTP 단위 33 passed; Core #34382890931의 전체 Python 283 tests / 0 failures / 0 errors / 0 skipped 및 Go race 24 top-level / 57 leaf cases / 0 failures / 0 test skips. [[integration-87600e9-provenance.json]]·[[integration-87600e9-tests.xml]]·[[integration-87600e9-unit.jsonl]]에 원본 근거를 보존했다.

운영 IdP·실장비·SLO 시험을 수행했다고 주장하지 않는다. [[ERR-CONTROL-001 Heartbeat fixture와 오류 계약 누락]]의 대응이다.
