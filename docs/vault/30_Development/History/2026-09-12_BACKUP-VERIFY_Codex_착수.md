---
doc_id: "HIST-BACKUP-VERIFY-START-20260912"
title: "2026-09-12 BACKUP-VERIFY Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T02:26:14+09:00"
source_of_truth: "Git"
---

# 2026-09-12 BACKUP-VERIFY Codex 착수

CX-01/CX-07/CX-09, S08-ST/S11-ST/S11-DB 후속. owner Codex / reviewer Claude pending. base135b15ad3c608318fdc4a677b674c1ea17c6123d, agent/codex/workspace-bridge PR19. GUIDE-001/GOV-AGENT-001/GOV-GIT-001 v1.1.0, INDEX-PROGRESS-001 v1.0.26, PLAN-DB-001/PLAN-STORAGE-001 v1.0.0, ADR082/083, agent-delivery1.1.0/core-reliability1.0.0 기준.

운영 Evidence 경로 검토 중 verification.verify_backup_bytes가 크기 비교 전에 verified를 flush하고 sweep이 예외를 잡고 계속하는 선행 결함을 발견했다. 실제 파일/격리 PostgreSQL로 실패 뒤 verified 상태 보존, 기존 checksum 재검사, 다른 tenant 요청의 읽기 전 거부를 재현·수정한다. 새 증거 저장소를 만들지 않고 기존 검증 서비스 경계를 보완한다. 경로 resolver/실장비/전체 운영 Evidence 인수는 별도이며 운영 DB·키·Node에 적용하지 않는다.
