---
doc_id: "HIST-CODEX-S11-AC11-COMPOSITE-LONG-SOAK-001"
title: "S11 AC-11 composite long-soak target 설계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T19:59:12+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "ec86fce6f5cade2b2ccc3abfd2ae1a7f1ef4e316"
task_id: "CARD-S11-AC11-COMPOSITE-LONG-SOAK-DESIGN-01"
tags: ["S11", "AC-11", "long-soak", "design", "Codex"]
---

# S11 AC-11 composite long-soak target 설계

## 작업한 것

- #157의 필수 `long-soak` 축과 #185의 storage-reference-only 경계를 결합해 [[S11_AC11_composite_long_soak_target_v0]]을 결과 관측 전에 commit `938ad3eb1c1664890c714f6ec86f409b7dab65b9`, blob `0bf74f90557a237b50ebdf571ed9e3dac89ea23b`로 고정했다.
- ADR-100에 따라 5개 등록 Node, Ubuntu 4대 timed 분모, CP 겸임 1대 제외를 required environment로 고정했다.
- 열·전원·NTP·스위치·WAN·실 WS/PTY·물리 storage·hosted drift의 관측값, 계측법과 임계치를 고정했다. 14개 exact case SHA-256은 `d4638030330f8c2ba857e63976cc050bf2d631491d59472fab225142eccd49c3`, 20개 fault-class SHA-256은 `62aa166b06ac2b91adef51b5af10d2d2939da5e8a9e008e2a4104b8865cfd27b`다.
- #192 predecessor를 가리키는 non-consumable registry patch proposal을 만들고, 실제 registry/blob/importer repin은 별도 선행 카드로 분리했다.

## 확인한 것

- `git grep -n -F`로 #157 `:238/:254`, #185 storage 설계 `:22/:88`, target `:29`, ADR-100 `:29/:35/:43/:54`, registry pin과 `REQUIRED_TARGET_BY_AXIS` 위치를 복사했다.
- source target 첫 commit 전 `python tools/check_docs.py`는 895 versioned documents, exit 0; `git diff --check` exit 0이었다.
- 이 카드에서는 PostgreSQL, Docker, browser, Node 중단, 전원·network fault, hosted CI를 실행하지 않았다. 수치 실측과 AC-11 PASS는 없다.

## 현재 판정과 다음 행동

- 운영자 fault-injection 자원과 외부 observer가 없으므로 `long-soak=BLOCKED_EXTERNAL(G-19/G-24)`다. hosted green이나 storage-only result로 PASS를 만들 수 없다.
- 다음 담당은 Claude reviewer다. 승인 뒤 Codex가 `CARD-S11-AC11-LONG-SOAK-REPIN-01`에서 단일 registry, aggregator와 모든 importer pin을 한 commit으로 갱신하고 부정 시험을 추가한다. 그 뒤에도 실제 운영자 자원이 제공되기 전에는 측정하지 않는다.
