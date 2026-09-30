---
doc_id: "HISTORY-20260930-CARD160-S04-CANCEL-PRODUCT-BRIDGE-CODEX"
title: "CARD-160 S04-DB core cancel 제품 경로 결속 설계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-30T13:52:17+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "c9c1d836ff8fcd606b5bca3862c6cd764eadf4fd"
task_ids: ["S04-DB"]
tags: ["card-160", "s04-db", "cancel", "product-route", "atomic-bridge"]
---

# CARD-160 S04-DB core cancel 제품 경로 결속 설계

## 선택 근거

- CARD-159/PR #256 최종 head
  `c9c1d836ff8fcd606b5bca3862c6cd764eadf4fd`에서 core 취소 상태와
  `run.cancel.requested` audit의 원자적 producer, 동시 취소 직렬화, hosted
  Backend/Core green을 확보했다.
- 그러나 production HTTP는 kernel `Control.cancel`을 호출하고 core
  `cancel_run` 호출자는 0이므로 clean C1은 여전히 `RECORDED_ONLY`다. 추가 PC,
  물리 Node, 원격 WS 없이 닫을 수 있는 가장 직접적인 S04-DB 공백이다.
- S05/S07의 5노드 성능·복구와 S08의 실제 PITR/보존 관측은 외부 자원이 필요하므로
  이 카드보다 뒤다.

## 조사 결과

- 공개 route·입력·응답은 이미 kernel에 확정돼 새 계약이 필요하지 않다.
- production `BusinessDispatch`도 run 실행 경로를 kernel에 남기도록 의도적으로
  제한한다.
- kernel role은 public run의 identity를 읽고 잠글 수 있지만 상태 UPDATE와 audit
  INSERT 권한은 없다. 별도 transaction으로 core service를 호출하면 kernel 취소와
  public audit 사이 crash gap이 생긴다.

## 결정

공개 계약은 변경하지 않는다. business-mapped run에만 같은 kernel PostgreSQL
transaction 안에서 좁은 SECURITY DEFINER primitive를 호출해 public run 상태와
exact audit를 함께 갱신한다. actor는 request가 아니라 인증 subject의 현재 business
user mapping에서 파생하며, 구조 불일치는 기존 `SYS-0001/503`으로 fail-closed한다.

normal·shard·replay 잠금 순서, privilege 최소화, downgrade, 부정 시험과 hosted 실
PG 판정은 [[S04-DB_core_cancel_제품경로_결속_설계]]에 고정했다. migration 번호가
필요하므로 보안 설계 승인과 번호 배정 뒤 구현한다. 이 단계에서는 코드·migration·
registry 상태를 바꾸지 않았고 S04-DB는 `review`를 유지한다.
