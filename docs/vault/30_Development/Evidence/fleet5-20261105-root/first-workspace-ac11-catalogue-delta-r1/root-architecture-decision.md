---
doc_id: "FLEET5-FIRST-WORKSPACE-AC11-CATALOGUE-R1"
title: "첫 Workspace AC11 함수 목록 변경의 Root 아키텍처 결정"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-07T19:48:57+09:00"
source_of_truth: "Git"
---

# 결정과 범위

Root Codex는 작성자 B와 분리하여 후보 `a88fd60094339e55da2536e5485eed00b8eaa5ed`의 새 0068 SQL 전체와 definer policy 차이를 읽었다. 기존 Root R1 계약의 최소 권한 브리지 두 함수가 필요하다는 아키텍처 결정을 근거로 **이 두 시그니처만** AC11 검토 입력의 목록에 추가하고 revision을 `0068_first_workspace_intent`로 바꾸는 것을 승인한다. 실제 최종 코드 수락, 보안 CI 성공, 실측 catalogue PASS 또는 Claude 독립 검토 완료를 선언하지 않는다. 보고된 Backend 3.12의 14 실패/9076 성공은 남겨 두고 담당 B가 교정한다.

- `inv.append_first_workspace_intent(text, text, jsonb, text, text, text, bigint)`
- `inv.append_first_workspace_run(text, text, text, text, bigint, bigint, text, text)`

기존 15 함수의 policy 값과 기존 `secVf001`, `rlsAcceptedDispositions`, collector baseline이 그대로임을 고정 Git 객체의 JSON/bytes로 대조했다. 전체 함수 목록은 정확히 17개다. 기존15에 대한 결정은 [기존 보안 검토](../../../S11_AC11_SEC_DEF_001_allowlist_보안검토_Codex.md)의 이력을 유지한다. 정확한 후보 hash와 당시 선언된 definition hash는 [Root 결정](root-decision.json)과 [입력 pin](inspected-source-pins.json)에 있다. definition hash를 Root가 실제 DB에서 측정한 것은 아니다.

# 두 브리지의 요구 경계

후보 SQL은 dedicated writer의 NOLOGIN/NOSUPERUSER/NOBYPASSRLS/NOINHERIT와 양방향 membership·schema/table ownership 부재를 검사한다. 두 함수는 `SECURITY DEFINER`, `search_path=pg_catalog`, `row_security=on`, schema-qualified SQL을 사용하며 PUBLIC/inv_app EXECUTE를 회수하고 inv_kernel만 허용한다. CREATE는 함수 owner 변경 때만 같은 migration 안에서 일시 부여 후 회수한다. 필요한 SELECT/INSERT와 잠금 sentinel의 column 권한만 사용해야 한다. 이 읽기 결과는 실제 migration/role/RLS 시험을 대체하지 않는다.

함수는 현재 epoch와 tenant kill switch, 활성 project/requester/subject mapping, ready인 정확한 Workspace와 버전, workload scope/hash, target membership을 다시 검사하고 제한된 metadata 또는 세 Run/mapping 행만 append한다. 실제 허용 profile 검증, lock 순서와 원자성, 직접 호출/교차 tenant/hostile search_path/권한 회수/동시성/rollback/commit 후 GUC 누출 부재는 최종 restricted-role PostgreSQL 시험과 독립 코드 검토에서 증명해야 한다. subject GUC는 신뢰된 서비스 문맥이며 SQL 서비스 credential 탈취에 대한 암호학적 사용자 증명이 아니다.

# 허용된 기계적 반영

[승인된 입력](reviewed-source-authorized.json)을 B의 기존 reviewer-owned source 경로로 그대로 반영한다. 바뀌는 값은 `verifiedAt`와 `definerReview`뿐이다. 새 reviewDocument는 이 문서이고 기존 보안 결정을 위 링크로 이어 받는다. 기존 writer로 output을 생성하고 allowlist blob/canonical hash 및 변경된 definer policy blob을 집계기에 정확히 고정한다. 필요하면 기존 sourceDocument/registry/importer의 동일 source pin 연쇄를 기존 절차대로 회전하되 ID·필수 축·평가 의미·threshold는 바꾸지 않는다. exact count 회귀는 15에서17로 바꾸고 집합 일치 및 누락/추가/중복/revision/RLS 변조 거부는 유지한다.

기존 writer, 15개 함수 정의·권한, SEC-VF browser 근거, RLS 예외/기준, Critical/High 분류, approval quorum, containment, AC11 acceptance 기준을 완화하지 않는다. 세 번째 함수나 이 경계 변경은 이 결정에 포함되지 않는다. 두 helper의 R1 범위 오류 교정은 실제 최종 정의/소스 hash를 다시 측정·pin하고 변경 사유를 기록한 후 CI와 실제 Claude 검토로 전달한다. 이 문서는 미지의 후속 코드 전체를 선승인하지 않는다.

실제 DB/schema/role/서비스 변경은 여기서 수행하지 않는다. 최종 Frontend/Core/Backend/Docs 성공과 실제 Claude 독립 검토 전 배포하지 않는다. Original19HOLD와 실제 Run/5대 운영 인수 미완료는 유지한다.
