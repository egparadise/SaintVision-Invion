---
doc_id: "FIX-NODE-CONTAINMENT-L2-001"
title: "NODE-CONTAINMENT 승인 경계 검토 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T15:13:00+09:00"
source_of_truth: "Git"
---

# 제어 승인의 범위 고정과 원자 소비

[[NODE-CONTAINMENT 승인 경계 검토 오류]]에 대해 기존 0022 뒤에 `0023_containment_approvals`를 추가했다. 사람 identity는 자동 생성하지 않으며 신뢰 provisioning으로 등록한 immutable/UNIQUE person_id와 현재 can_approve 권한을 사용한다. 요청자를 제외한 두 사람의 승인과 5분 만료, 정확한 operation/Node/version/gate/epoch/digest, 각 주체의 60초 일회 nonce를 강제한다.

실제 제어 적용 직전 requester/voter 권한과 모든 scope를 다시 확인하고, 승인 소비·제어 변경·불변 응답을 같은 transaction으로 처리한다. 이미 접수된 취소의 정리에는 새 승인을 요구하지 않고 기존 durable intent를 계속 수행한다. 자동 비상 예외·알람 자체의 제어 실행은 추가하지 않는다.

승인 없음/한 표/자기 투표/중복 사람/다른 nonce·digest/권한 철회/만료/gate 변경/승인 소비 및 rollback을 전용 시험에 추가했다. 로컬 migration 관련 23개 통과, PostgreSQL/Go/전체 회귀는 수정 후 같은 SHA CI로 검증하며 최종 결과는 History 보고서와 PR17에 기록한다. 현재 구현 설명만으로 독립 검토·운영 인수를 완료로 표시하지 않는다.
