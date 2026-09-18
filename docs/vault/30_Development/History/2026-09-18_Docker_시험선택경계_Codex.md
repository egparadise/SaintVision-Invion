---
doc_id: "HIST-DOCKER-SELECTION-001"
title: "기본 회귀와 Docker host 시험 선택 경계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T13:26:40+09:00"
source_of_truth: "Git"
---

# 기본 회귀와 Docker host 시험 선택 경계

base0c50f57, branch agent/codex/model-registry-binding, owner Codex(CI/시험 배치), reviewer Claude(미실시). 공통/개인 진행판 및 agent-delivery1.1.0/core-reliability1.0.0 적용. 사용자 승인에 따라 시험 선택 경계를 수정한다. Claude 진단/cleanup 제품 로직은 변경하지 않는다.

## 관측과 판단

사용자 clean0c50f57: tests/integration 및 test_docker_diag.py/test_check_kernel_docker_hygiene.py/test_vf_docker.py 제외 시1157passed/489skipped/0failed,62초. 세 파일 포함 실행은120초 및890초 제한에서 미완주 보고. 이는 그 실행 범위의 회귀 미관측이며489skip 검증이나 전체 제품 무결함 선언은 아니다.

소스 대조 결과 실제 Docker를 호출하는 시험은 hygiene 파일의 prune2건이다. docker_diag12건과 vf_docker6건 및 hygiene4건은 mock/로컬Python 실행이다. 기존 skipif는 CLI 유무만 검사하여 CLI가 있으나 daemon/host가 불안정한 환경을 분리하지 못했다. integration 폴더 제외만으로 자원 의존성이 사라지지 않는 기존 배치는 부적절하다고 판정한다.

## 결정

실Docker2건에 docker_host marker를 붙이고 pyproject 기본 선택을 `-m 'not docker_host'`로 한다. 기본/Backend 경로는22건의 오프라인 회귀를 유지하고 host2건은 deselect한다. skip을 합격처럼 기록하지 않는다. Core CI의 기존 disposable runner에서 명시 `python -m pytest tests/test_check_kernel_docker_hygiene.py -m docker_host --strict-markers --junitxml=dist/docker-host-tests.xml`을 실행한다. CI 증거 검사는 정확히2건 존재와 skip/error/failure0을 요구한다. CI는 수정만 했고 실행·조회하지 않았다.

`-m` 명시 인자는 기본 marker 선택을 대체하므로 `-m docker_host`는 의도적 호스트 실행 요청이다. 로컬에서는 자원 정리를 허용한 격리 호스트에서만 사용한다. 현재 공유 호스트에서는 image/prune 중단 방침대로 collect-only까지만 수행했다.

## 확인한 것

Docker CLI를 없다고 모사하고 실제 docker subprocess 호출 시 즉시 실패하는 probe를 넣은 기본 세 파일 실행:22passed/2deselected,exit0,0.26초. 명시 `-m docker_host --collect-only`: 정확히2건 선택/22제외,exit0. Docker 없는 기본 경로의 실제 실행은22건이며 제외된2건을 검증했다고 기록하지 않는다.

전체 비integration 기본 경로도 동일 probe로 검증 중이다. 사용자 전체 회귀와 중복 합산하지 않는다. e2908a5 frozen workload/승인·dispatch/delivery/claim 구현은 이미 반영됐고 새 구현 독립검토는 Claude에게 정본으로 인계한다. 이전8c/e89 sound를 이번 검토로 확대하지 않는다.

## 기본 경로 확대 점검에서 찾은 별도 CLI 의존

전체 비integration에 Docker 실행을 금지한 probe를 적용한 첫 실행은1166passed/500skipped/2failed/2deselected,64.66초였다. 두 실패는 새 host marker 경로가 아니라 tests/core/test_vf_deployment.py의 기존 Compose config 호출을 probe가 차단한 것이다. source와 traceback으로 확인했다. test_deployment_credentials.py의11건은 CLI 없음 가드로 skip했으나 이2건은 가드가 없었다.

해당2건에 CLI 부재 fixture를 추가했다. CLI 없음 모사:2skipped/exit0/0.07초. 실제 Docker Compose CLI 설정 검사:2passed/exit0/1.08초. 서비스/컨테이너 생성·daemon 조작은 없다. 다른 Compose11건과 같이 CLI가 존재하는 기본 경로에서는 계속 검증한다. 따라서 기본 경로 전체를 Docker-free라고 부르지 않으며 host 자원 변경2건의 기본 제외와 CLI-only config 검사를 구분한다.

최종 전체 비integration은 Compose config/version만 허용하고 모든 다른 Docker 호스트 명령을 실패시키는 probe로 실행한다. 최초 실패 결과와 최종 결과를 구분해 보존한다. Docker가 없는 조건의 이번 신규3파일22건 및 Compose2건 선행조건만 직접 확인했으며 전체 Docker-free 플랫폼 인수는 주장하지 않는다.

## 최종 확인·다음 담당

최종 명령 `python -m pytest tests --ignore=tests/integration -p no_host_probe -q --tb=short -r f --junitxml=.work/nonintegration-host-separated.xml`: **1179passed/489skipped/2deselected/0failed,66.23초,exit0**. 세 파일을 통째로 제외한 사용자1157보다22건의 오프라인 검증을 유지하며 기본 경로가 완주했다. 반복 가능한 성능 보장이나 호스트 원인 인과 실험으로 확대하지 않는다. skip489와 deselect2는 합격이 아니다.

Evidence/docker-test-selection/verified.json 및 두 probe 원문에 최초 실패/최종 성공, 소스 hash, JUnit hash, 범위를 보존했다. 문서522개/ontology exit0, YAML/TOML parse exit0, git diff --check exit0. 실제host2건은 재실행하지 않았고 이미지 미검증6건/business-kernel-role 미검증도 그대로다. CI는 구성 수정만 했으며 인증/결제 대기와 독립검토·운영 인수는 미완이다.

다음 Claude: e2908a5 registry frozen 입력과 현재 권한 재검사 독립검토 및 이번 시험 배치/CI 선택 경계 검토. 다음 Codex: finding 수신·수정, registry 운영자 정책 구성 연결의 API 경계 검토. 원격 설치/호스트 조치/CI 인증·결제는 사용자 대기4건 유지. 중간 승인 요청 없음.

## 전달 기록

구현3afe227, 작업 branch/integration push exit0. 변경6파일만 Obsidian check→apply→check:6exported/0pending/0conflict,source3afe227. CI조회/실host시험 재실행 없음. 독립검토는 Claude 대기.
