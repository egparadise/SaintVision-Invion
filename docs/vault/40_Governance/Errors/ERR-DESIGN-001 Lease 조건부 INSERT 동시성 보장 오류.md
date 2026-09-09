---
doc_id: "ERR-DESIGN-001"
title: "ERR-DESIGN-001 Lease 조건부 INSERT 동시성 보장 오류"
version: "1.0.0"
status: "design_corrected"
author: "Codex"
updated: "2026-09-09T15:10:54+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# ERR-DESIGN-001 Lease 조건부 INSERT 동시성 보장 오류

발견: 2026-09-09T15:10:54+09:00 / Agent: Codex / 종류: design / 상태: 설계 정정, 제품 구현 대기

Claude DB 보완 §3은 READ COMMITTED의 단일 INSERT를 초과 예약 방지로 설명한다. 서로 다른 트랜잭션이 같은 합계를 읽을 수 있어 이 불변 조건을 보장하지 않는다.

해결: [[RES-DESIGN-001 Lease 조건부 INSERT 동시성 보장 오류 정정]].

이것은 문서 리뷰에서 발견한 문제이며 실행 중 발생한 제품 사고가 아니다.
