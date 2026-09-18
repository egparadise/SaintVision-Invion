---
doc_id: "HIST-REGISTRY-CONFIG-001"
title: "Registry 운영자 정책의 서비스 설정 연결"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T13:34:32+09:00"
source_of_truth: "Git"
---

# Registry 운영자 정책의 서비스 설정 연결

VF-CX-02/03, base1eaf285, branch agent/codex/model-registry-binding. owner Codex, reviewer Claude(이번 변경 미검토). 공통/개인 진행판 확인, agent-delivery1.1.0/core-reliability1.0.0 적용. 목표는 이미 검증된 실행권한 연결에 운영자 설정 파일의 policy를 전달하는 것이다. 운영 설치·정책 승인·라이선스 판단은 하지 않는다.

## 수신과 검토 범위

사용자 tip1eaf285에서 `pytest tests --ignore=tests/integration`(세파일 수동ignore 없음):1179passed/489skipped/2deselected/0failed,75초. 작성자66.23초 결과와 중복 합산하지 않는다. 이전890초 미완주와 달리 기본경로 완주 확인이다.

Claude c9e6ddf 문서 원문을 확인하고6314c54에 병합했다. e2908a5 소스 독립검토 sound/finding없음. 실제 PG 재실행은 Claude가 하지 않았으며 작성자 증거와 구분한다. Claude Docker 부재 검증은 PATH에서 docker 제거, 세파일22passed/2skipped/0failed,0.16초(당시 기본marker 분리 전). 최신 기본선택의22passed/2deselected와 구분한다. 신규 부재 가드가 필요 없다는 평가는 해당 세파일에 한정되며 별도 Compose두건의 기존 가드 누락 수정과 충돌하지 않는다.

## 작업한 것

INV_API_CONFIG의 선택적 modelRegistryPolicy를 strict parser로 읽고 같은 Database에 전달한다. 필드가 없으면 기존 kernel-only 설정이고, 필드가 있는데 null/빈목록/unknown key/중복pair/타입·길이 위반이면 서비스 시작을 거부한다. pair는 licensePolicy/classification 정확한 두 키만 허용한다. 최대64pair, 각 문자열1~256자, version1~128자. Database의 typed RegistryBindingPolicy와 같은 digest를 만든다.

설정은 trusted_file/strict_object 경계를 재사용하고 HTTP 요청·workload에서 policy를 받지 않는다. 불량설정은 기존 비밀 비반사 startup 오류로 처리하며 잘못된 policy를 None으로 자동변환하지 않는다. ModelRuntimeStore/approval/dispatch/claim의 기존 검사는 그대로다.

## 남은 운영 경계

정책은 시작 시 읽는 운영자 설정이며 hot reload/전역 정책 epoch는 구현하지 않았다. 정책 변경은 모든 승인·delivery·worker 프로세스의 일관된 재시작/구성 배포를 요구한다. 구버전 worker가 떠 있는 상태를 전역 철회 완료라고 주장하지 않는다. registry prepare 공개 API/실제 원격 provider 설치·운영 인증서 인수는 별도다. 사용자 대기4건과 image6/business-kernel-role미검증은 유지한다.

## 최초 PG 검증의 관측용 DSN 차이

test_storage_catalog_api.py 첫 실행은12 setup errors/0passed(exit1). 내부예외를 값·locals 없이 타입과 frame만 추적하니 configured_business:55의 database targets differ ValueError였다. 작성자 runner가 사용자가 준 DSN에 application_name=codex_registry_config를 추가했는데 business fixture는 host/port/dbname/user/password만 URL에 복사한다. 기존 target() 비교는 application_name을 제거하지 않으므로 두 target dict가 달라졌다. 신규 policy parser 오류가 아니며 DB/역할 제약을 완화하지 않았다.

최초 JSON은 registry-config-pg-initial.json에 보존했다. 사용자 원본 DSN 그대로 재실행한다. application_name 관측 메타데이터를 DB identity로 간주하는 기존 비교의 호환성 제약은 별도 후속 검토 사항이며, 이번 정책 설정 연결의 성공으로 이 차이를 숨기지 않는다. 비밀번호/원본 DSN은 문서·예외 로그에 기록하지 않았다.

## 최종 검증과 인계

- `python -m pytest tests/core/test_model_registry_config.py tests/core/test_model_execution_registry.py tests/core/test_workspace_api_boundary.py -q --tb=short`:34passed/0failed/0skip,exit0. 정상 policy 순서 독립digest, 불량설정 시작거부·비밀비반사, factory의 실제 Database 전달과 기존 미설정모드를 검증했다. identity/create_app 종단은 이 시험에서 대역이므로 실제 서버 인수와 구분한다.
- `python -m pytest tests/integration/test_storage_catalog_api.py -q --tb=short`: 사용자 원본 disposablePG16 DSN에서12passed/0failed/0skip,12.35초,exit0. 실제 JWT·기존 configured factory·restricted business 역할·owner scoped API 회귀다. registry policy 활성화의 실장비 인수는 아니다.
- 총46건은 명시한4파일 범위다. 문서524/ontology/diff검사exit0. CI조회/실Docker/image lane 실행없음.

다음 Claude: 신규 configured_registry_policy 입력 경계와 create_configured_app policy 전파 독립검토. e2908a5 sound 수신으로 그 구현의 독립소스검토 대기는 해제하되 이번 설정 구현에 확대하지 않는다. 다음 Codex: 독립 finding 대응, 공개 registry/runtime 준비 API 계약 및 application_name 비교 호환성 후속 검토. 운영policy 선정/전역rollout/CI/원격장비는 미완이다.

## 전달 기록

구현11e9f44와Claude문서병합6314c54를 작업branch/integration에 push(exit0). 변경10파일만 Obsidian check→apply→check:10exported/0pending/0conflict,source11e9f44. CI조회/환경조치/실장비배포 없음. 이번 설정 독립검토는 Claude 대기.
