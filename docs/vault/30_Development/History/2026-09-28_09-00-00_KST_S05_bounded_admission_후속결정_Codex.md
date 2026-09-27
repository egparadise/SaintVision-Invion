---
doc_id: "HIST-CODEX-S05-CARD42-ADMISSION-DECISION-001"
title: "S05 Card42 bounded admission 후속 결정"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T09:00:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["history", "s05", "admission", "semaphore", "decision"]
---

# S05 Card42 bounded admission 후속 결정

## 판정

Card39 hosted 결과는 N=4·wait 0ms에서 매 wave 정확히 4/20 성공·16 fast reject였고 SQL timeout은 0이었다. P95 all 중앙 350.460ms가 legacy 401.090ms보다 낮은 것은 48개 빠른 거절 영향이므로 개선으로 세지 않는다.

후속 권고는 **N=4 유지 + bounded permit wait 450ms 실험**이다. hosted permit hold P95 상한 99.531ms에서 마지막 다섯째 cohort 대기는 `4×99.531=398.124ms`이므로 450ms는 약 52ms 여유다. 성공 20/20과 외부 실패 0을 예측하지만 성공 P95 361.228ms에 대기를 더한 거친 P95 all 약 759ms는 legacy보다 악화될 가능성을 동시에 드러낸다.

gate는 admission reject와 SQL timeout을 분리해 진단하되 둘의 합계 외부 실패 비증가를 계속 blocking으로 둔다. N 확대는 wait 0에서 N=20 전까지 반드시 `20−N` fast reject를 남기고, N=20은 상한 보호를 제거한다. B′ 1500ms는 Card24 세 조건 전부 실패와 Card25 단일-wave 상충 때문에 이번 다음 arm에서 제외한다.

## 경계

- 문서만 작성했고 제품·시험·workflow·계약·migration·registry는 변경하지 않았다.
- 새 측정은 실행하지 않았다. 다음 hosted legacy/candidate 20동시×3은 Claude 검토와 코디네이터 결정 뒤다.
- flag 기본 off, S05-DB `in_progress`, 50동시·5노드·운영 활성화·AC-05 승격 없음이다.
- 공개 오류는 계속 `RES-0007`/503/retryable이고 fencing·멱등·RLS·no-overbooking·transaction-final release를 보존한다.

정본: [[S05 bounded admission 후속 결정 제안]]. 근거: [[2026-09-28_08-35-00_KST_S05_hosted_20동시_wave_Codex]], [[2026-09-23_12-20-00_KST_S05_Bprime_구현_교정실험_Codex]], [[2026-09-23_13-28-00_KST_S05_bounded_semaphore_사양_Codex]].
