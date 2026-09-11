---
doc_id: "ERROR-RESOURCE-OFFER-20260911"
title: "RESOURCE-OFFER 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T14:42:43+09:00"
source_of_truth: "Git"
---

# 자원 제공량 통합 검토와 정정

Claude 9ab84ab를 b5d265a로 가져와 검토했다. 원저자 코드는 Git 이력에 보존하며 Codex 수정은 Claude 독립 검토 대기다.

- P1: 기존 SQL은 동종 resource를 LIMIT 1로 골랐다. 다른 slice의 offered가 남아 사용자 요청 상한과 전체 예약 가능량이 다를 수 있다. 현재 Node의 동종 전체 slice를 잠그고 요청 총량으로 배분한다.
- P1: GPU는 capability별 device_index가 있지만 kernel resource에는 device key가 없다. 같은 종류의 첫 행을 선택하지 않고 device_mapping_required로 미연결 의도를 표시한다.
- P1: 기존 definer는 tenant만 확인하고 actor/capability/현재 resources.manage 권한을 입력으로 받지 않았다. 서비스와 새 definer에서 현재 사용자와 별도 grant를 검사하고 기존 함수의 runtime EXECUTE를 회수한다. inv_app 직접 UPDATE 금지는 유지한다.
- P1: 기존 writer는 Resource만 잠갔고 core 예약은 Node→Resource 순서를 사용한다. 새 writer도 같은 Node→Resource lock과 잠금 후 별도 lease 합 조회를 사용한다.
- 사실 정정: inv.resources 행은 구성된 자원이며 실제 mTLS snapshot 관측과 별개다. 미등록/pending과 정책 적용/실행 가능을 분리한다. 문자열 검색 대신 reason code를 사용한다.
- Claude가 보고한 과거 0026 subject lookup의 tenant 결함은 이미 Codex 0028 및 0030 최종 정의에서 보강됐다. 과거 migration을 편집해 이력을 깨지 않고 최종 head에서 tenant·active 계정·subject 일치 검사를 검증한다. 과거 함수만 실행한 재현과 최신 통합 head를 구분한다.
- 작업 중 테스트 호출에 actor 키워드를 추가하면서 생긴 positional argument 순서 오류는 테스트 실행 전 구문 점검에서 정정했다. 기존 false/empty 데이터로 검증 결과를 꾸미지 않는다.

실제 테스트 결과·실패가 발생한 경우의 재현·SHA·CI·sync는 후속 검증보고에 고정한다. 원격 프로필/운영 계정은 변경하지 않았다.

실제 검증 중 0031 PL/pgSQL의 IF 안 CASE 표현식에서 syntax error가 발생해 첫 10개가 fixture setup 오류로 중단됐다(exit 1). CASE 전체를 괄호로 감싸 수정했다. 오프라인 SQL 생성 검사와 실제 DB upgrade를 구분한다.

재시도 시 Docker가 `could not find an available, non-overlapping IPv4 address pool`로 시험 네트워크 생성을 거부했다. 이번 작업의 종료된 시험 runner/DB 및 정확한 label·빈 endpoints를 확인한 뒤 그 빈 네트워크 1개만 해제했다. 운영 네트워크·실행 중 컨테이너는 변경하지 않았다. 반복 누적을 막기 위해 harness는 매 실행 후 소유 label·internal bridge·빈 endpoints·컨테이너 정지를 확인한 네트워크만 ID로 제거하며 컨테이너/로그를 보존하도록 보강했다.

두 번째 격리 실행은 43개 중 41개 통과, 2개 실패(exit 1)였다. 두 실패는 시험 구성 오류였다. inv_app에는 inv schema USAGE 자체가 없어 그 역할로 has_table_privilege를 조회하는 것부터 거부됐다. 실제 연결 역할을 확인한 뒤 owner 연결에서 그 역할의 권한을 검사하도록 수정했다. 또한 직접 서비스 호출 시험이 UUID 대신 문자열 tenant를 넘겨 목표인 늦은 flush 실패에 도달하지 못했으므로 UUID로 고쳤다. 원래 rollback 검증은 유지했다. 해당 실행이 종료된 뒤 같은 소유권 검사 helper로 이번 작업의 빈 시험 네트워크를 해제했다.
