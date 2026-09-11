---
doc_id: "CONTRACT-RESOURCE-OFFER-001"
title: "Codex 자원 제공량과 예약 원자 반영 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T14:42:43+09:00"
source_of_truth: "Git"
---

# 자원 제공량과 예약의 원자 반영

ADR-069, owner Codex/reviewer Claude. Claude 9ab84ab의 업무 제공량 연결을 실제 kernel 예약 상한 및 현재 권한과 통합한다. 일반 등록/관측/제공 의사는 Claude 서비스, kernel 동시성·무결성 및 공통 경계는 Codex가 소유한다.

## 현재 권한과 한 transaction

PUT /v1/capabilities/{capabilityId}/offer는 검증된 JWT의 현재 active 사용자와 별도 resources.manage grant를 요구한다. 서비스 직접 호출과 새 DB definer 모두 같은 권한을 확인한다. 기존 node/kind/숫자만 받던 apply_resource_offer의 inv_app 실행 권한은 회수한다. inv_app에 inv.resources 직접 쓰기 권한을 주지 않는다. 실제 trust principal을 공급하는 것은 인증된 서비스이며 SQL runtime 계정 자체를 일반 사용자에게 배포하지 않는다.

public Node→capability, kernel Node→정렬된 모든 Resource lock을 잡는다. LeaseStore 예약도 kernel Node→Resource를 잠그므로, 잠금 후 새 statement에서 조회한 미반납 lease 합에 따라 제공량 감소/예약 중 하나가 결정된다. expiry·old epoch만으로 물리 반납을 추정하지 않는다. public 제공 이력/상한 변경과 kernel offered 변경은 동일 업무 transaction에 있다. 늦은 flush/audit/DB 실패는 양쪽을 rollback한다.

## 전체 Node 상한과 단위

CPU는 millicores, RAM/storage는 bytes다. 0.25 core는 250 millicores다. 하나의 전체 Node capability에 여러 kernel resource slice가 있어도 첫 번째 행만 고르지 않는다. 먼저 각 slice의 미반납량을 보장하고, 남은 제공량을 resource_id 순서로 각 capacity까지 배분한다. 모든 offered 합이 요청값과 같고, 각 offered는 자기 capacity 이하·자기 미반납량 이상이어야 한다. public total 또는 kernel capacity 합 초과 및 미반납 합 미만은 거부한다.

kernel resource row는 구성된 자원이고 그 존재만으로 현재 실제 관측을 증명하지 않는다. 미등록이면 의도만 public 이력에 남기고 appliedToKernel=false/resource_not_registered를 반환한다. 실제 배치는 mTLS/epoch/channel/heartbeat/snapshot/프로젝트·Node 권한/예약량/kill switch·drain을 다시 확인한다. appliedToKernel=true도 실행 admission이나 schedulable=true를 의미하지 않는다.

GPU capability의 device_index와 현재 inv.resources 사이에는 확정 device identity 매핑이 없다. GPU 제공 의도는 저장하되 device_mapping_required로 보고하고 어느 GPU resource에도 임의 적용하지 않는다. GPU 장치 연결/실행은 별도 검증 후 구현할 범위다.

## 응답과 회귀 기준

기존 offeredQuantity/unit/effectiveFrom 및 history 의미를 유지한다. appliedToKernel, kernelResourceIds, kernelResourceId(정확히 한 행일 때만), kernelCapacity, kernelReasonCode, executionReady=false를 돌려준다. pending reason은 resource_not_registered/device_mapping_required, 정책 오류는 below_unreleased_leases/exceeds_kernel_capacity/invalid_quantity 등이다. 사람용 문자열의 일부를 검색해 성공/실패를 분류하지 않는다.

0030_apply_resource_offer와 0030_provisioning_integrity 공개 이력을 보존하고 0031_resource_offer_integrity에서 병합한다. 기존 subject lookup 최신 guard와 canonical 결과 다운로드 정본은 유지한다. 테스트는 실제 제한 DB role, JWT API, LeaseStore의 예약/제공량 동시성·과거 lease·원자 rollback·GPU 오인 금지와 공개 prior upgrade/replay로 입증한다. 운영 DB 또는 실제 Node 권한은 이 작업에서 변경하지 않는다.
