---
doc_id: "CLAUDE-INDEP-REVIEW-APPLIED-FRESHNESS-001"
title: "독립 검토 — appliedToKernel true 경로 + 신선도 시각 셋(stateUpdatedAt·stateAsOf·completedAt) 의미"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex(피검토)"
reviewed_at_tip: "0f491b69"
updated: "2026-09-22"
source_of_truth: "Git"
tags: ["independent-review", "resource-offer", "freshness", "source-confirmed", "pg-accepted"]
---

# 독립 검토 — appliedToKernel + 신선도 시각 셋

오늘 밤 Codex 착지 중 내 검토 안 받은 것 중 위험 큰 둘. 고정 tip **`0f491b69`**. 인터프리터 무관(소스), **PG 부재**(런타임은 Codex 실-PG 수용).

## ① appliedToKernel true 경로 — 소스 확증(자원 없으면 true 불가), 런타임은 Codex PG 수용
- **경로**: `settings._apply_to_kernel`가 SQL `public.apply_capability_offer(t,c,u,o)`를 호출해 `(applied,reason,ids,capacity)`를 받고 **`appliedToKernel = bool(applied)`로 그대로 중계**. 파이썬은 판정을 안 한다.
- **SQL 함수 소스 확증**(migration 0031_resource_offer_integrity):
  - `FOR resource IN SELECT r.resource_id FROM inv.resources r ...`(자원 조회) → **비면 `resource_not_registered`, applied=false**(라인 42/51).
  - 이어 capacity/leased 검사(`exceeds_kernel_capacity`·`below_unreleased_leases`·`leased_capacity_inconsistent`) 통과 + `UPDATE inv.resources SET offered` 후에야 **마지막 라인에서 `RETURN QUERY SELECT true,...`**.
  - 즉 **`true`는 등록된 커널 자원이 있고 검사 다 통과할 때만 도달**한다. **시드를 빼거나 `inv.resources` 자원을 지우면** FOR 루프가 비어 `resource_not_registered` → applied=false → **appliedToKernel=false.** `true`(마지막 라인)는 자원 없이는 **텍스트상 도달 불가.**
- **되살림(사용자 요청 "시드 빼면 true 안 나오는지")**: **PG 부재로 실행 못 함** → 소스 제어흐름으로 확증(자원 없음 → resource_not_registered → false; true 도달 불가). **실 PG 되살림(시드→true, 자원 제거/거부 대조군→false, 3회)은 Codex 결과 수용**(작성자 실행, 내 실행 아님). 소스-층은 sound, DB-층은 PG-대기.
- **판정 ①**: 소스 상 sound — appliedToKernel은 등록 자원 + 검사통과 뒤에만 true. 파이썬 중계 정확. 자원 할당 위험 지점이나 게이트가 SQL 함수에 집중돼 있고 false 경로(미등록·초과·리스 미달)가 명시적.

## ② 신선도 시각 셋 — 의미가 구현과 일치(확증), Gemini 화면 설명 옳음
셋이 **다른 것을 뜻한다**는 Codex 서술을 소스로 검증:
- **`stateUpdatedAt`**(RunResultView, result_view.py:125) = `run["updated_at"]` — **단일 Run의** 마지막 durable 상태변경 시각. RunResultView가 한 Run이라 단일 updated_at이 맞음. 주석 "not the time this HTTP read ran" 정확.
- **`completedAt`**(result_view :142/190/220) = `row["completed_at"]`(= `c.completed_at`, result-completions 행, migration 0011; **완료 전엔 NULL**, 비완료 분기는 `NULL AS completed_at`). **updated_at과 다른 소스·다른 의미**(종단 완료 시각). ✓ 구별됨.
- **`stateAsOf`**(ShardObservation, shards.py:315) = `max(parent["updated_at"], *[r["run_updated_at"] for r in rows])` — **부모 Run + 모든 샤드 멤버 Run의 updated_at 중 최대.** 즉 **포함된 Run들의 최신 상태변경 시각이지 단일 스냅샷이 아니다.** Codex 서술과 **정확히 일치.** 주석도 "Latest durable run-state update represented here ... does not date delivery, receipt, or object rows"로 **범위를 정직히 한정**(run-state만; delivery/receipt/object 행은 각자 시각).
- **판정 ②**: 세 시각 의미가 모두 구현과 일치. Gemini가 화면에 그대로 반영한 것 **옳음**(화면 설명 틀린 것 없음).
- **정밀 주의(오류 아님, 화면 표기 권고)**: `stateAsOf`는 **run-state 기준**이지 전체 관측 기준이 아니다(object/receipt는 더 최신일 수 있음). 화면은 "실행 상태 기준 시각"으로 표기해야 하고 "전체가 이 시각 기준"으로 과대표기하면 안 된다 — Codex 주석이 이미 한정했으니 Gemini가 그 한정을 지키면 정확.

## 판정
- ① appliedToKernel: **소스 sound**(자원 없으면 true 불가, true는 등록+검사통과 뒤에만). 런타임 되살림은 PG-대기(Codex 실-PG 수용).
- ② 신선도 시각 셋: **의미가 구현과 일치**(stateUpdatedAt=단일 run updated_at, completedAt=종단 완료(distinct), stateAsOf=포함 Run 최신 updated_at·비스냅샷). Gemini 화면 옳음. stateAsOf의 run-state 한정만 화면 표기에서 지킬 것.

## 직접 확인 vs 보고 수용
- **직접(소스)**: apply_capability_offer 제어흐름(자원 조회→resource_not_registered/true), 파이썬 중계, 세 시각의 소스·max 집계·distinct 컬럼 (전부 tip `0f491b69` 소스).
- **보고 수용(미실행, PG 부재)**: appliedToKernel 실-PG 되살림(시드→true·대조군→false·3회) = Codex 결과. 신선도 시각의 실 DB 값은 소스로 의미 확증, 실행값은 PG-대기.

관련: [[2026-09-22_응답_관측시각_신선도_백엔드축_Claude]] · [[2026-09-22_쓰기응답_잔여위험_재판정_Claude]] · [[2026-09-22_세_축_종합_실물성_정직함_신선도_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
