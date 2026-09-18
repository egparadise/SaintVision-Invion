---
doc_id: "HIST-STORAGE-NODE-TRANSPORT-START-20260912"
title: "2026-09-12 STORAGE-NODE-TRANSPORT Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T12:47:55+09:00"
source_of_truth: "Git"
---

# Go Node 서명 sample 전송

Base9fe35b64a7da5ee790c2c8fd0ecc9bc826c1e151, agent/codex/workspace-bridge, CX-02/owner Codex/reviewer Claude pending. S12-ST 원 owner Claude 유지. 진행판1.0.31/Codex작업판1.0.16/CONTRACT-STORAGE-SAMPLE-001 v1.1.0/ADR-088, agent-delivery1.1.0/core-reliability1.0.0 확인.

공통 JSON Schema를 기존 Python Challenge에 맞추고 Go Node의 opt-in 폴더 설정·현재 mTLS 인증서·서명 수집 endpoint와 Control Plane client를 연결한다. Linux descriptor로 경로/링크/교체·byte budget을 검사하고 Windows native는 지원 전 거부한다(Windows Docker/WSL의 Linux Node와 구분). 실제 Go 서명→Python verifier와 mTLS/설정 회수 시험을 수행한다. 운영 Node/key/DB 변경은 없다. durable challenge/nonce 소비·기존 Evidence/StorageCheck 원자 기록은 다음 DB 작업이며 이 전송 단계만으로 운영 건강을 갱신하지 않는다.
