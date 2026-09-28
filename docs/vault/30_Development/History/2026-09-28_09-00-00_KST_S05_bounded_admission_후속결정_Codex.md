---
doc_id: "HIST-CODEX-S05-CARD42-ADMISSION-DECISION-001"
title: "S05 Card42 bounded admission 후속 결정"
version: "1.3.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T17:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["history", "s05", "admission", "semaphore", "decision"]
---

# S05 Card42 bounded admission 후속 결정

## v1.0 검토 결과

Card39 hosted N=4·wait 0ms는 매 wave 4/20 성공·16 fast reject였고 legacy는 60/60·외부 실패 0이었다. v1.0은 permit hold P95 99.531ms를 `h` 상한처럼 써 W=450ms에서 20/20 가능성을 제안했다.

Claude 검토 F1~F6과 코디네이터 결정으로 이 제안은 철회됐다.

- candidate 허용 표본은 wave당 4개라 P95와 max가 같을 뿐이다. 정확한 표기는 hosted `h_obs_max=99.531ms`, W가 허용하는 구간 한계는 `h_limit(W)=W/4`다. W=450의 한계 112.500ms는 관측 max 대비 여유가 약 13%뿐이다.
- candidate success P95 361.228ms에 한 cohort max 99.531ms만 더해도 460.759ms로 legacy 401.090ms보다 느리므로 gate 2는 모든 W>0에서 확정 실패한다.
- 현재 permit은 루트 트랜잭션 안에서 idempotency `FOR UPDATE` 뒤에 있어 W>0 대기가 row lock·connection·worker를 붙잡는다. replay-before-permit과 wait-outside-transaction을 동시에 만족하는 별도 설계 없이 W>0을 실행하지 않는다.
- admission reject와 SQL timeout은 분리 계측하되 합계 외부 실패 blocking gate는 유지한다(F6).

## v1.1 결정

W=450 arm은 실행하지 않고 세 gate도 바꾸지 않는다. 다음 측정은 hosted opt-in lane의 **legacy-only 20→35→50 staircase**다.

- 각 rung `20×3`, `35×3`, `50×3`을 순차 실행하며 첫 degrade에서 중단한다.
- 사전 degrade 기준은 (1) 한 wave라도 `55P03+57014>0`, 또는 (2) 세 wave request P95 all 중앙값 `>2000.000ms`다.
- degrade가 확인된 concurrency에서만 candidate(W=0, N 후보) 비교 사양을 별도로 낸다.
- 50까지 degrade가 없으면 semaphore 라인을 현 hosted 부하에서 불필요한 것으로 닫고 legacy를 확정한다.

## 경계

- 이번 수정은 docs-only다. 새 wave·제품·workflow·계약·migration·registry 변경은 0이다.
- legacy staircase lane 구현·실행은 v1.1 승인 뒤 별도 카드다.
- flag 기본 off, S05-DB `in_progress`, 운영 활성화·승격·AC-05 주장 없음이다.

정본: [[S05 bounded admission 후속 결정 제안]]. 근거: hosted Card39 run `36359052826`, [[2026-09-23_12-20-00_KST_S05_Bprime_구현_교정실험_Codex]], [[2026-09-23_13-28-00_KST_S05_bounded_semaphore_사양_Codex]].

## v1.2 실행 전 정정

Claude 승인 조건과 코디네이터 결정을 Card46 실행 전에 반영했다.

- timeout 기준은 세 wave 최대값(any wave), request P95 all은 세 wave 중앙값을 쓰며 혼용은 의도적이다.
- `2000.000ms` 기준은 개별 SQL timeout을 대신하지 않고 여러 statement를 포함한 요청 전체 누적 경로만 판정한다. 따라서 `57014=0`인 상태에서도 도달 가능하다.
- 각 wave를 새 pytest session·새 일회용 DB에서 실행한다. 9개 fingerprint의 유일성과 wave 전후 DB 잔존 0을 집계 증거가 fail closed로 확인한다. 이는 rung별 새 DB 요구보다 강하다.
- 구현/실행 정본은 [[S05 legacy 동시성 계단 hosted lane 사양]]과 [[2026-09-28_16-50-00_KST_S05_legacy_동시성_계단_Codex]]로 분리한다.

## Card47 clean-base 결정

#115·#141은 병합하지 않으며 제품 semaphore 코드도 integration에 넣지 않는다. #145의 결정 내용과 #148의 legacy-only lane·정본 evidence·종료 결정을 integration `1e8baf04` 위 새 PR로 재구성한다. 새 lane은 schema 1.7 benchmark의 legacy 경로와 redacted disposable DB fingerprint만 사용하고, clean-base hosted run은 기존 결론을 교체하지 않는 실행 호환성 확인이다.
