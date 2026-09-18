---
doc_id: "HIST-STORAGE-BUNDLE-START-20260912"
title: "2026-09-12 STORAGE-BUNDLE Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T15:31:25+09:00"
source_of_truth: "Git"
---

# LAN 신규 생성 경로 저장소 연결

Basebc87f7c0cec078ca531230339c6c1513e97789d8 / agent/codex/workspace-bridge / CX-02 Codex owner, Claude reviewer pending. 진행판1.0.38/Storage계약1.5.0/ADR-092, agent-delivery1.1.0/core-reliability1.0.0 확인. 기존 LAN installer는 기존 container를 보존/거부한다. 이번 범위는 그 신규 container 생성 경로에 명시 source+독립 policy SHA256, 고정 /contribution read-only/nonrecursive mount, 보호 policy 복사와 시작 receipt 대조를 연결하는 것이다. 기존 container 교체/자동 rollback과 운영 .225 설치는 별도다.
