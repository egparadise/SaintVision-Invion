---
doc_id: "HIST-STORAGE-REPLACE-START-20260912"
title: "2026-09-12 STORAGE-REPLACE Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T15:54:21+09:00"
source_of_truth: "Git"
---

# 저장소 Node 교체 실행과 forward 재개

CX-02/S12-ST Codex owner, Claude reviewer pending. base d1366f7394b59a3ff1bf9c42e7d3620778a250ba, agent/codex/workspace-bridge. GUIDE-001/GOV-AGENT-001/GOV-GIT-0011.1.0, ADR-094, agent-delivery1.1.0/core-reliability1.0.0.

목표: 정지 관측 Node의 기존 컨테이너/키/journal/volume을 보존하면서 읽기 mount/정책을 설치한 새 컨테이너로 전환. private local lock·fsync 단계 기록·중단 후 같은 계획으로 forward 재개. 이전 컨테이너 자동 재시작 차단, 정책 pin 후 rollback 금지. 실제 Docker 합성 Node만 사용, 운영 .225 변경 없음. CI/독립 검토/운영 인수는 별도 기록한다.
