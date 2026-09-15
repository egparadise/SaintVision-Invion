---
doc_id: "HIST-OFFER-SNAPSHOT-START-20260912"
title: "2026-09-12 OFFER-SNAPSHOT Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T23:37:17+09:00"
source_of_truth: "Git"
---

# Claude F1 동시성 재현과 forward 수정

CX-01/CX-02 Codex owner/Claude reviewer. base6bde158, agent/codex/workspace-bridge. agent-delivery1.1.0/core-reliability1.0.0. 수신원문 Evidence/obsidian-proposals-20260912-business-workspace/proposal-3.txt.

목표: 실제 apply_capability_offer의 slice 쓰기 사이에 실제 LeaseStore.release가 commit되어도 요청 총량과 기록 총량이 일치한다. 합격 증거: advisory barrier로 실제 두 세션의 순서를 고정해 기존900/요청1000 재현, 동일 시험으로 수정후1000 검증. 이미 배포된0031은 수정하지 않고 forward migration으로 snapshot을 한 번만 읽어 계산한다. 운영DB 변경은 하지 않는다.
