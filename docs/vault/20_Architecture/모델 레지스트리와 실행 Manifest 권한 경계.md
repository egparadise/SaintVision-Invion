---
doc_id: "ARCH-MODEL-REGISTRY-BOUNDARY-001"
title: "모델 레지스트리와 실행 Manifest 권한 경계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-15T15:12:44+09:00"
source_of_truth: "Git"
---

# 모델 레지스트리와 실행 Manifest 권한 경계

## VF-CX-02 / VF-CL-03 결정

현재 두 저장 구조를 유지한다. 목적과 권한이 다르며 이름·버전·checksum이 같다는 이유로 자동 결속하지 않는다. 영구 분리 결정이 아니라 명시적 결속 계약과 검증이 생길 때까지의 경계다.

| 구조 | 책임 | 보증하지 않는 것 |
|---|---|---|
| public.models/model_versions/lineage | S10 모델 등록·업무 버전·평가/승인 추적 | 커널 manifest 존재, 현재 bytes 일치, 실행 permit |
| inv.model_manifests/model_shard_locations | tenant/project/model/version별 불변 실행 manifest, source Run 및 DataLocation 버전 참조, 커밋 당시 full-byte 검증 | S10 released 상태, 현재 복제본 가용성, 새 실행 권한 |

inv_app의 커널 테이블 권한을 확장하지 않는다. 공개 조회가 필요하면 커널의 현재 사용자·프로젝트 인가를 거친 API로 최소 메타데이터를 제공한다. 공개 API 및 ModelVersion 결속은 아직 미구현이다.

## 정책 필드와 후속 결속 합격 조건

- 커널 manifest의 licensePolicy/classification은 이미 존재하며 manifest digest에 포함되는 불변 선언이다. licensePolicy 문자열은 라이선스 허가를 자체 증명하지 않는다.
- Claude의 registry 정책 필드는 업무 metadata로 추가할 수 있으나 커널 값이나 기존 커밋을 자동 수정하지 않는다. 두 값이 다르거나 결속이 없으면 UI는 연결 미확인으로 표시한다.
- 후속 명시적 결속은 현재 tenant/project 인가, registry의 정확한 version ID, 커널 (tenant,project,model,version,manifest_sha256), 내용 식별 및 정책 적합성 검증을 요구한다. 결속 레코드의 불변성·동시 변경 방어·최소 권한을 별도 migration/시험으로 검토한다.
- 식별자/URI 문법이 두 체계에서 다를 수 있으므로 문자열 동등성이나 URI 해석만으로 FK 관계를 만들지 않는다. checksum 일치도 정책/권한 승인을 대체하지 않는다.
- 등록/결속/조회와 실행 인가는 별도다. 실행은 현재 승인·lease/fence·Node와 bytes 재검증을 유지한다.

## 독립 검토 정정

Claude 5189365의 shard 상한 finding은 reviewed SHA d6d9d87에서도 JSON Schema의 maxItems=1024와 manifest_copy 첫 단계 validate_contract에 의해 이미 거부된다. 1025개는 DB CHECK까지 도달하기 전에 VAL-0002/422가 된다. 런타임에 중복 상수를 추가하지 않고 경계 회귀시험으로 보호한다. shard_index 0..1023과 일치한다.

0039 이전 분기 문제는 현재 후보116e6e5의 단일0043 migration 체인에서 확인한다. 운영DB의 upgrade 완료를 의미하지 않는다. 기존 Claude 검토의 storage ready 상태와 locality verified_nodes는 동등하지 않다. 후자는 현재 Node/epoch/프로젝트·bytes 검증 등 추가 조건을 요구하므로 ready 행만으로 실행 가능을 표시하지 않는다.

실제 검증과 인계: [[2026-09-15_VF-MODEL-REVIEW_Codex]]. 후속 변경의 독립 재검토는 Claude, API·결속 구현은 Codex/Claude 각 owner 카드로 진행한다.
