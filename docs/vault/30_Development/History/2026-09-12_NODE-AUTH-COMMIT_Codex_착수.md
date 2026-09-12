---
doc_id: "HIST-NODE-AUTH-COMMIT-START-20260912"
title: "2026-09-12 NODE-AUTH-COMMIT Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T11:40:18+09:00"
source_of_truth: "Git"
---

# Node 관측 인증 선행 보강

Base345cc1a / agent/codex/workspace-bridge / PR19. CX-01/CX-02, owner Codex/reviewer Claude pending. 공통 진행판v1.0.29, ADR-086, agent-deliveryv1.1.0/core-reliabilityv1.0.0.

StorageCheck/Evidence 연결을 준비하며 inbound node_auth가 ASGI client_cert_error를 무시하고, heartbeat가 인증 세션 종료와 실제 기록 사이 회수/인증서 교체를 재검증하지 않는 것을 확인했다. 이 선행 보안 경계를 먼저 구현/검증한다. TLS 오류/잘못된 direct 인증은 proxy fallback으로 우회하지 않고, 현재 tenant/node/certificate binding을 기록 transaction에서 잠가 확인한다. signed storage challenge/원자 Evidence 기록은 이 보강 후 계속할 작업이며 이번 착수에서 완료로 주장하지 않는다. 운영 Node/계정/PKI 변경 없음.
