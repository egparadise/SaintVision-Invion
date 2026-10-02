---
doc_id: "HISTORY-CARD-246-S08-BE-BUILD-REQUEST-ENTRY-001"
title: "Card 246 S08-BE BuildRequest 제품 진입점 설계"
version: "1.0.2"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-03T01:25:07+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "53458da3604027e91d428e11db02bc09d279097c"
task_ids: ["S08-BE", "CARD-246"]
---

# Card 246 S08-BE BuildRequest 제품 진입점 설계

## 선택 근거

train 28 후보 `53458da3604027e91d428e11db02bc09d279097c`에서
`ApprovalStore.dispatch()` 제품 호출자는 세 곳이지만 모두 기존 `WorkloadSpec` 경로이고,
build plan/evidence를 전달하는 제품 호출자는 0건이다. 0060 admission과 worker가 생겨도 사용자
intent를 서버 소유 BuildRequest/BuildPlan/PolicyDecision으로 바꾸는 앞단이 없으므로 카드 246을
외부 전제 없이 진행 가능한 다음 S08-BE 설계로 선택했다.

## 결정

- raw build 문서를 받지 않는 prepare/enqueue 2단계 route를 선택했다.
- caller 입력은 checkout/profile/run-version selector로 제한하고 source SHA, paths, policy,
  provider, lease, evidence, approval actor는 모두 서버가 구성하거나 DB에서 재구성한다.
- 기존 approval review/challenge/decision과 distinct quorum을 재사용한다.
- prepare-review 사이 immutable authority를 저장할 새 table이 필요하다. coordinator는 Claude가
  이 필요성을 승인하는 조건으로 0061을 예약했다. 승인 전 migration 파일은 만들지 않으며,
  승인 뒤 0060 단일 부모·만료/최소 35일 보존·DB-backed rate window·RLS census 생성·필요한
  definer 재검토를 적용한다. v1은 DELETE를 허용하지 않고 별도 GC 계약 전까지 보존한다.
- flag 기본 off, 실제 builder/LAN 인수 NOT_OBSERVED, S08-BE 점수 불변이다.

설계 PR은 [#341](https://github.com/egparadise/SaintVision-Invion/pull/341)이며 reviewer는 Claude다.

상세 정본은 [[S08-BE_BuildRequest_제품_진입점_설계]]이다.
