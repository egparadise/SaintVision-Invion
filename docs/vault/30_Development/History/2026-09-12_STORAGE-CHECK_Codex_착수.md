---
doc_id: "HIST-STORAGE-CHECK-START-20260912"
title: "2026-09-12 STORAGE-CHECK Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T11:03:26+09:00"
source_of_truth: "Git"
---

# STORAGE-CHECK 착수

CX-01/CX-02/CX-07, owner Codex/reviewer Claude pending. Base3080cf4, PR19 agent/codex/workspace-bridge. 공통 진행판v1.0.28, GUIDE-001v1.1.0, ADR-085/CONTRACT-READROOT-001v1.0.0, agent-deliveryv1.1.0/core-reliabilityv1.0.0.

Claude71cf2c0의 storage_check.py/tests를 독립 검토한다. --node 문자열 비교는 실제 기계 binding이 아니며, zero samples/no checksum도 healthy가 되는 서비스를 보완한다. CLI는 읽기 전용 실제 파일 sample로 연결하고 node 증명 없는 운영 기록 쓰기를 제공하지 않는다. 기존 hash 구현을 복제하지 않고 명시적 operator root와 ReadRoot를 사용한다. 실제 DB/파일·거부·기록0·과거 잘못된 healthy 집계 회귀를 검증한다. 운영 DB/Node/PKI 수정 없음.
