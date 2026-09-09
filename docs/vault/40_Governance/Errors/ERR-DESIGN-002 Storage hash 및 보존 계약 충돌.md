---
doc_id: "ERR-DESIGN-002"
title: "ERR-DESIGN-002 Storage hash 및 보존 계약 충돌"
version: "1.0.0"
status: "design_corrected"
author: "Codex"
updated: "2026-09-09T15:10:54+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# ERR-DESIGN-002 Storage hash 및 보존 계약 충돌

발견: 2026-09-09T15:10:54+09:00 / Agent: Codex / 종류: design / 상태: 설계 정정, 제품 구현 대기

Claude Storage 보완의 metadata 기반 hash 비교와 Artifact 90일 GC는 내용 무결성·Evidence 1년 재현 요구를 충족하지 못한다.

해결: [[RES-DESIGN-002 Storage hash 및 보존 계약 충돌 정정]].

이것은 문서 리뷰에서 발견한 문제이며 실행 중 발생한 제품 사고가 아니다.
