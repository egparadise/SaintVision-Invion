---
doc_id: "HIST-OFFER-SNAPSHOT-REVIEW-20260912"
title: "2026-09-12 OFFER-SNAPSHOT Codex 독립확인"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T23:41:42+09:00"
source_of_truth: "Git"
---

# F1 — 현재 release 경로에서는 재현되지 않음

CX-01/CX-02 Codex 확인, Claude 재확인 pending. 시험 SHA **51f4004b7e65328aed30f20763cb96c21ec8ade6**, basee7f1844, agent/codex/workspace-bridge. 원문은 Evidence/obsidian-proposals-20260912-business-workspace/proposal-3.txt, [[2026-09-12_OFFER-SNAPSHOT_Codex_착수]].

## 확인 결과

F1의 “release는 lease 행만 잠근다”는 전제가 현재 실제 호출 경로와 다르다. `LeaseStore.release`→`_locked_lease`→`lock_resources`로 **Run→Node→Resource→Lease** 순서로 잠근다. `_locked_lease`의 자원 잠금은 `e6336a7a`(2026-09-09)부터 있으며 Claude가 재검토한6ff090b에도 존재했다. 이번에 고친 것이 아니다.

실제 apply_capability_offer의 첫 slice UPDATE 후 시험용 advisory barrier로 멈추고 실제 LeaseStore.release를 호출했다. 최초 “중간 해제 성공”을 기대한 시험은 Node 행 lock_timeout/RES-0007로 실패했다. 이 증거는900/1000 버그 재현이 아니라 **원문의 전제 반증**이다. 이에 계획을 정정하고 정상 잠금·해제 재시도를 회귀 시험으로 고정했다. 구0031을 수정하거나0038 migration을 추가하지 않았다. 준비 중이던0038 초안은 .work에만 있으며 배포/저장소 migration graph에 포함하지 않는다.

## 실제 검증

`python -m pytest -q tests/integration/test_resource_offer_integrity.py`: **12 passed,11.67초,exit0**, warning26. 격리 PostgreSQL16/tmpfs cluster, 실제 schema0037/비소유자 역할/definer/HTTP adapter/LeaseStore 사용. 원래 잘못된 시험 기대값에서의 실패와 구별한다.

추가 시험 `test_release_waits_for_offer_and_retry_keeps_exact_requested_total`: 두 세션 순서를 advisory barrier로 고정한다. 해제는RES-0007, released_at은NULL 유지, barrier해제 후 제공량1000, release 재시도 성공 후에도 제공량1000. 자원 잠금을 우회하는 SQL 문장 재생은 실제 API 경로와 동등한 재현으로 볼 수 없다. 테스트 hook은 해당 폐기DB에만 설치·정리했다.

추가 코드 독해: NodeReceiptStore 수신 경로는 lock_resources 후 release update, reclaim_unclaimed 호출의 control.cancel/containment/shards도 자원 잠금 후 진입한다. 이 독해를 모든 장애 시나리오의 실행 검증이라고 부르지 않는다. offer fixture URL은 runtime의 connect_timeout 등 연결 옵션을 보존하도록 수정했다.

Evidence `../Evidence/offer-snapshot-20260912.json`. 이 작업의 제품 잠금코드/migration/운영상태 변경은 없다. 시험 commit/push 완료. CI 상태는 후속 기록, 독립 reviewer의 원 finding 철회/재현 조건 정정은 Claude에게 인계하며 대신 승인했다고 쓰지 않는다.

## 다음 행동과 전체 상태

Claude는 F1 재현에서 `_locked_lease`의 잠금을 생략했는지 확인하고, 차이가 남으면 **실제 writer 호출 경로와 해당 SHA**를 제공해야 한다. Codex는 위 회귀시험 결과를 기준으로 운영 전환 후보와 계속 연결한다. [[2026-09-12_RUNTIME-CUTOVER_Codex_후보계획]]의 운영 OIDC 설정 입력·critical 전환·원격 profile/7개시험·CI가 남아 있다. 전체 **57.81%/잔여42.19%** 유지.

동일51f4004 CI6건은 계정결제 제한으로 job미시작/failure다(Core34699996446/34699994169,Backend34699996296/34699994219,Docs34699996295/34699994199). Evidence offer-snapshot-51f4004-ci.json. 문서/ontology 검증과 최종 sync는 아래 후속 기록한다.
