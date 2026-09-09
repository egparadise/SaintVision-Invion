---
doc_id: "RES-DESIGN-001"
title: "RES-DESIGN-001 Lease 조건부 INSERT 동시성 보장 오류 정정"
version: "1.0.0"
status: "design_corrected"
author: "Codex"
updated: "2026-09-09T15:10:54+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# RES-DESIGN-001 Lease 조건부 INSERT 동시성 보장 오류 정정

오류: [[ERR-DESIGN-001 Lease 조건부 INSERT 동시성 보장 오류]]

ADR-005/006과 DB 최종 계획에서 잠금→다음 statement 최신 합계→예약·fencing으로 정정. 실제 SQL 구현·50 connection 시험은 S05-DB에서 수행한다.

resolution_scope: design_documentation. runtime_verified: false.

근거: [[설계 충돌 정정 및 ADR]]. 실제 commit과 검사 결과는 [[개발 과정 인덱스]]에 연결한다.
