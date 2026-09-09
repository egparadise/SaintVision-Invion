---
doc_id: "RES-DESIGN-002"
title: "RES-DESIGN-002 Storage hash 및 보존 계약 충돌 정정"
version: "1.0.0"
status: "design_corrected"
author: "Codex"
updated: "2026-09-09T15:10:54+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# RES-DESIGN-002 Storage hash 및 보존 계약 충돌 정정

오류: [[ERR-DESIGN-002 Storage hash 및 보존 계약 충돌]]

ADR-011/012로 실제 bytes 검증·Evidence pin·staging ledger·GC 경합 검증을 지정. 제품 전송 시험은 S04-ST/S08-ST에서 수행한다.

resolution_scope: design_documentation. runtime_verified: false.

근거: [[설계 충돌 정정 및 ADR]]. 실제 commit과 검사 결과는 [[개발 과정 인덱스]]에 연결한다.
