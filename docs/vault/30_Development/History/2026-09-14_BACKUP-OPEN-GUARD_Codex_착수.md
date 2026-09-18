---
doc_id: "HIST-BACKUP-OPEN-GUARD-START-20260914"
title: "2026-09-14 BACKUP-OPEN-GUARD Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T19:44:53+09:00"
source_of_truth: "Git"
---

# 보관 백업 읽기 시점 경계

CX-01/CX-07, S12-ST 지원. owner Codex, reviewer Claude pending. base 67c1be070d1c736c04a8db4cf80f0cfc9dd8f90d, branch agent/codex/workspace-bridge. agent-delivery 1.1.0/core-reliability 1.0.0; GUIDE-001 1.1.0, ADR-INDEX-001 1.35.13, GOV-AGENT-001/GOV-GIT-001 1.1.0 기준.

검사 이후 Path.read_bytes/read_text로 다시 여는 백업 입력을 기존 ReadRoot로 연결한다. 열린 파일 크기 제한, 링크/루트 교체 거부, bounded 재읽기, 리허설 종료 시 manifest 보존을 확인한다. 운영 DB/Node 변경 없이 경계 회귀시험과 보관 파일의 독립 PostgreSQL 복원을 수행한다. CI/peer/운영 인수는 별도로 기록한다.
