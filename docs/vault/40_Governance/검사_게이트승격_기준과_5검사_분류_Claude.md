---
doc_id: "GOV-CHECK-GATE-PROMOTION-001"
title: "검사 게이트 승격 기준 — 백로그0·오탐낮음·명확한 대응 셋 다면 게이트, 아니면 ratchet/report-only; 5검사 재분류"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
decided_at_tip: "bbfb42b6"
updated: "2026-09-22"
source_of_truth: "Git"
tags: ["governance", "ci", "gate", "ratchet", "report-only", "false-positive"]
---

# 검사 게이트 승격 기준 + 5검사 재분류

ratchet을 doc_single_source에 적용한 뒤 나머지(dead-contract)를 같은 눈으로 봤다. 성격이 달라 기준 자체를 세운다.

## 기준 (셋 다여야 게이트)
검사는 **하드 게이트**로 올릴 수 있다 ⇔ 셋 다 참:
1. **백로그 = 0** — 지금 정당하게 위반하는 것이 없다(있으면 기존 상태에서 늑대소년).
2. **오탐률 낮음, 표본 충분** — 낮다고 말할 **근거(표본)**가 있어야 한다. 한 번만 발동한 검사는 근거 부족.
3. **대응 명확** — 실패 시 무엇을 할지가 분명하다.
- 백로그>0인데 2·3은 참 → **ratchet**(델타만 막음).
- 오탐 우려가 있거나 대응이 불명 → **report-only**(+ step-summary로 가시화).
- **주의**: 백로그=0이면 **ratchet ≡ 하드 게이트**(빈 기준선 → 어떤 위반에도 실패). 그래서 ratchet은 **백로그>0일 때만** 도움이 되고, **오탐 문제는 못 줄인다**(빈-기준선 ratchet도 오탐 하나에 CI를 막는다).

## dead-contract 판단 — 게이트 승격 안 함, report-only 유지
- **백로그 = 0 확인**: check_contract_bindings 실행 시 dead WARN 없음(LegacyProjectCatalog 제거로 0). 기준①은 충족.
- **오탐률 = 근거 부족(기준② 불충족)**: 진짜 양성 **표본 1건**(LegacyProjectCatalog). 개발 중 오탐 여러 건(RunResultView/Artifact/Attempt=행기반 export 오판, DiscoveryCandidateResponse=중첩항목 오판)을 잡아 **보수적으로 고쳤으나**, 설계가 grep 기반이라 오탐-경향은 남는다(도구 docstring이 한계 명시: 완전 동적 구성으로만 서빙되는 계약은 죽은 것으로 오판 가능). **표본 1로는 프로덕션 오탐률이 낮다고 판단할 근거가 없다.**
- **ratchet도 안 맞음**: 백로그=0이라 ratchet≡게이트 → 오탐 하나가 CI를 막는 위험이 동일. ratchet이 이 검사의 report-only 이유(오탐)를 안 고친다.
- **결론**: **report-only 유지 + step-summary로 가시화.** 승격은 (a) 오탐 track record가 쌓여 낮음이 입증되거나 (b) 탐지를 AST 기반으로 견고화(간접/동적 서빙도 인식)한 뒤 재검토. 기준②가 채워지는 시점.

## 오늘 5검사 재분류 (기준 적용)
| 검사 | 백로그 | 오탐 | 대응명확 | → 위치 |
|---|---|---|---|---|
| check_contract_bindings (검사1·2) | 0 | 낮음(관계·구조 검사) | 예(시험 추가) | **게이트** (현행) |
| check_frontend_integrity | 0 | 낮음(결정적) | 예 | **게이트** (현행) |
| test_serving_anchors | 0 | 낮음(되살림 확증) | 예(앵커 시험) | **게이트/스위트** (현행) |
| check_doc_single_source | 18(구조적) | 중(정당 색인요약 포함) | 예(통합 or baseline) | **ratchet** (적용됨) |
| check_response_freshness | 1(ShardObservation) | 낮음(필드존재, 결정적) | 예(필드 추가) | **ratchet 후보**(baseline={그 1건}; 새 부재에 실패) — 권고, 미착수 |
| dead-contract (check_contract_bindings 내부) | 0 | **근거 부족(표본 1)** | 예 | **report-only + surface** (승격 보류) |

- 정리: **게이트 3, ratchet 2(1 적용·1 후보), report-only 1.** 기준이 각 검사의 자리를 정한다.
- check_response_freshness는 백로그 1·오탐 낮음이라 **ratchet가 게이트보다 맞다**(백로그≠0이므로 ratchet이 실제로 델타만 막음). doc_single_source와 같은 패턴으로 baseline={ShardObservation.observedAt} 두면 새 신선도-필드 부재에만 실패. 착수는 지시 대기.

## 한계 (오늘 반복된 것)
- 기준②의 "표본 충분"은 결국 **사람이 track record를 본다.** 자동으로 "이 검사 오탐률이 낮아졌다"를 선언할 장치는 없다 — 승격 판단은 주기 리뷰의 사람 몫. baseline·기준선과 같은 **사람-감시 의존**이 여기도 있다.

관련: [[ratchet_적용_doc_single_source_Claude]] · [[검사도구_CI배선과_리포트가시성_Claude]] · [[계약검증_자동화대판단_검사목록]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
