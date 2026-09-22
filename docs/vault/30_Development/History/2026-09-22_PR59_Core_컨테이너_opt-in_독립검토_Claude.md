---
doc_id: "HIST-CLAUDE-PR59-CORE-CONTAINER-OPTIN-REVIEW-001"
title: "PR #59 Codex 카드 6 hosted Core 컨테이너 검증 23건 opt-in — hosted artifact 대조(3100/3065/35/0, 전환 23 실행) → 승인"
version: "1.1.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T21:15:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["review", "pr-59", "core-ci", "skip-ratchet", "container-lane", "codex"]
---

# PR #59 독립 검토 — Core 컨테이너 opt-in

대상 `agent/codex/core-container-optin`: 워크플로 커밋 **`0d02f343`** + 보고 `9202ccfc`(docs). 내 [[2026-09-22_hosted_Core_첫완주_skip58_분류표_Claude]] §3 "machinery로 줄일 수 있는 23건"의 후속. 검토는 **hosted artifact 읽기 전용 대조**(로컬 pytest 없음 — 메모리 경보 지침).

## 판정: **승인** (finding 0)

| 검증 | 결과 |
|---|---|
| Core run 35720205341(`0d02f343`) `core-tests.xml` | **3100 / 3065 passed / 35 skipped / 0 fail / 0 error** |
| 남은 35 분포 | CX01 19 · PowerShell 10 · csc 1 · 브라우저 smoke 1 · CLI 4 = ratchet과 일치 |
| 전환 23 | `test_migration_role_guard` 13 실행·통과, `test_server_container` 8, `test_server_config_volume` 7(이전 5+2 skip) |
| YAML | `INV_TEST_ROLE_GUARD_IMAGE: postgres:16`(backend와 동일), 후보 이미지 ID를 SERVER/CONFIG 변수로 재사용(추가 빌드 없음), bridge gateway + `pg_isready` 선검사, ratchet 3 사유 제거 외 변경 없음 |
| Codex 보고 vs artifact | 수치·모듈 전부 일치 |

## 추가 확인 (head `90a002f9`, 코디네이터 요구 3항)
- **정책 유지**: 헤더(트리거·`labeled`·concurrency group/`cancel-in-progress` main·integration 제외·`run-core` opt-in, a7f2ecf2)가 tip과 바이트 동일; 전체 diff는 opt-in 20줄뿐. `90a002f9`는 integration merge라 `core.yml` 변화 0.
- **junit 직접 집계**: 3100 케이스 중복 identity **0**; skip→pass 전환 **정확히 23**(13·8·2; config_volume 기존 5+2=7); skip 58→35; 두 run 사이 신규 114 케이스는 integration 착지분(이 PR 무관).
- **ratchet 정합**: head expected map 8 사유 합 **35** = artifact 분포; Codex 보고·내 #50 분류표의 58→35 서술과 일치.

관찰(비차단): 같은 SHA에 concurrency로 `skipped`된 Core run 1건 있으나 성공 run이 exact-head 증거; PR은 tip과 CONFLICTING(rebase는 큐). 코멘트: https://github.com/egparadise/SaintVision-Invion/pull/59
