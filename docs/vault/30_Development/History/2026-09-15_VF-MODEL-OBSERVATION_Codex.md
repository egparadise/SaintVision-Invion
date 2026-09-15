---
doc_id: "HIST-VF-MODEL-OBSERVATION-001"
title: "VF 프로젝트 권한 기반 모델 커밋 관측"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T15:24:19+09:00"
source_of_truth: "Git"
---

# VF 프로젝트 권한 기반 모델 커밋 관측

## 착수

- VF-CX-02 후속, owner Codex/reviewer Claude pending. base c74ce2e6a9db4e83e9255867893bd9439158a99e, branch agent/codex/vf-model-observation. 시작2026-09-15T15:24:19+09:00.
- INDEX-PROGRESS-0011.0.83/WORKBOARD-VF-CODEX-0011.0.12 및 기존 최종계획/ADR/역할/운영/보강로드맵/연속정책, agent-delivery1.1.0/core-reliability1.0.0 적용.
- 범위: 현재 kernel project grant와 linked business 사용자/프로젝트 권한 교차검사, committed manifest의 digest/Schema 재검사 후 최소요약 GET. root verifier 설정이나 파일I/O를 요구하지 않는 읽기경계.
- 합격: 실제JWT/PG/기존 full-byte commit 뒤 관측, 권한회수·다른project/tenant·위조identity·저장digest불일치 거부, 파일이바뀌어도 historical기록이며 currentAvailability unknown, 읽기로새실행/커밋없음.
- [[모델 레지스트리와 실행 Manifest 권한 경계]]1.0.0 준수. registry 자동결속/실행허가/파일접근/운영배포범위아님. 기존57.81%/VF운영0/5유지.


## 구현과 검증 범위

- 정본kernel GET /v1/projects/{project}/models/{model_id}/versions/{version}/commitment. can_request 및linked business 사용자/프로젝트/멤버십을기존잠금순서로검사한다. inv_app권한확장·운영migration없음.
- ModelManifest Schema/연속shard·길이/식별자·digest 재검증뒤최소요약. 현재가용성unknown/실행재검증true. node/location/keyRef/root상세제외, no-store 유지. 기존ModelManifestStore의worker설정을HTTP에노출하지않는다.
- ModelCommitObservation을정본JSONSchema에추가해Python/TS/Go/Node schema생성. 재생성5파일SHA동일. TypeScript tsc --noEmit exit0. Windows PATH에Go실행파일이없어Go컴파일은미실행으로기록한다.
- 초기79pass/1fail(불변mapping fixture 삭제거부), 확장140pass/1fail(미등록tenant containment503)을각각격리owner누락주입/실제생성other tenant로정정. [[2026-09-15_VF_오류와_해결]]. 제품권한우회가발생한것은아니다.
- 새이미지sha256:1d325403aef4fdc5262227dd34059e44e417816ce754c6e6ea34e3a4dc07257e build exit0. 운영배포미수행. 마지막회귀에실제컨테이너시험포함.
- check_docs476/check_ontology exit0. 전체sync --check exit1은기존외부/비관리파일충돌이므로출처확인된제한범위만export한다.

## 다음 담당

Claude: 현재인가·manifest무결성·최소정보응답독립검토. Gemini: Model Studio에서정확한project/model/version의과거커밋요약조회·unknown표시·브라우저확인. Codex: 같은SHA CI/인계후finding반영. ModelVersion자동결속·현재bytes재검증·대규모분산실행은별도카드이며이GET으로완료처리하지않는다. 운영owner: CI billing/SSO/PITR/실제5대. 기존57.81%/VF운영0/5유지.


## 최종 로컬 검증

최종run_vf_security_tests.py:141passed/0skipped/0failed,exit0. 이중실제후보컨테이너8개포함(별도합산하지않음). 실제JWT/격리PostgreSQL16 제한role/실bytes커밋·조회·권한회수·손상주입·다른tenant/미존재version·JSONSchema/route경계를확인했다. 최신source및생성물기준이며운영인수아님.
