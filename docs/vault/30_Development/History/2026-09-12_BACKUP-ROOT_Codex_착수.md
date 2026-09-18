---
doc_id: "HIST-BACKUP-ROOT-START-20260912"
title: "2026-09-12 BACKUP-ROOT Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T02:44:04+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# BACKUP-ROOT 착수

- Task: BACKUP-ROOT / CX-01 Storage 무결성 후속. Owner Codex, reviewer Claude(검토 대기).
- Base: e46d30d33914d9d6d6c3e521e48bf3d4a6628841, branch agent/codex/workspace-bridge, PR19.
- 지침 GUIDE-001 v1.1.0, ADR-INDEX-001 v1.35.3, 공통 진행판 v1.0.27, agent-delivery v1.1.0/core-reliability v1.0.0.
- 목표: 운영자가 명시한 저장소 root 아래의 실제 파일만 읽고, 링크/교체/읽는 중 변경을 거부한다. root 없는 기존 호출은 실패한다.
- 합격 증거: 실제 Windows/Linux 파일 정상 hash, root 누락/탈출/하드링크/심볼릭링크·reparse/교체/변경 차단, 기존 실제 PostgreSQL 백업 검증 회귀.
- 범위: worker 파일 읽기와 백업/복제본 helper 인수. 운영 DB·Node·개인 파일 변경 없음. 실제 원격7개/운영 RPO 인수와 구분.
