---
doc_id: "HIST-CONFIGURED-SERVER-REPORT-20260912"
title: "2026-09-12 CONFIGURED-SERVER Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T22:07:46+09:00"
source_of_truth: "Git"
---

# 정본 서버 설정·실제 HTTP 검증

CX-02 owner Codex/reviewer Claude pending. base 6c3b020, 구현 **510ced45c4250830d9c8afcaa15c592759950978**, agent/codex/workspace-bridge. GUIDE-001 1.1.0, agent-delivery 1.1.0/core-reliability 1.0.0. [[2026-09-12_CONFIGURED-SERVER_Codex_착수]], [[2026-09-12_CONFIGURED-SERVER_Codex_오류해결]].

## 작업한 것

Compose가 정본 factory에 INV_RUNTIME_DSN·INV_RECOVERY_EPOCH·고정 INV_API_CONFIG를 전달하고 기존 디렉터리만 읽기 전용 mount하도록 수정했다. healthcheck는 실제 /readyz다. 배포 절차 deploy/CONFIGURED-SERVER.md에 비소유자 역할, 공개 신뢰 묶음, UID65532 권한, tenant/epoch 준비를 기록했다. migration head/불가역 경계 시험의 오래된 0036 기대값도 현재0037로 수정했다.

## 확인한 것

- `python -m pytest -q tests/integration/test_configured_server.py tests/core/test_deployment_credentials.py tests/core/test_workspace_api_boundary.py`: **14 passed**, exit0, 22.13초. 별도 tmpfs PostgreSQL cluster/localhost 임의 포트, 실제 Alembic head 적용·비소유자 시험 역할, 실제 uvicorn saintvision.server:create_app --factory subprocess와 HTTP 사용. 시험 컨테이너·서버는 종료/제거했다.
- 합성 RS256 토큰 인증·실제 DB 프로젝트 조회, 무토큰/잘못된 토큰401, 권한 없는 사용자 빈 목록, 실행 중 grant 회수 반영. epoch 불일치시 liveness200/readiness503, 신뢰 묶음 만료시 liveness200/readiness503/API401. Workspace 미설정 상태를 ready 응답과 구분했다.
- Compose 정상 설정 및 필수7변수 각각 누락 거부8개, 기존 factory/계약/migration 경계3개 포함. 실제 컨테이너 이미지 build나 전체 Compose up 시험은 아니다. Windows subprocess 검증이며 Linux UID65532 bind mount 인수와 운영 SSO는 별도다.
- `python tools/check_docs.py`:360문서/48작업 exit0. `python tools/check_ontology.py`:exit0. `git diff --check`, commit/push exit0.
- 같은SHA CI6건 모두 **계정 결제 제한으로 job 미시작/failure**. Core34695505559/34695503151,Backend34695505521/34695503193,Docs34695505522/34695503140. [Core CI](https://github.com/egparadise/SaintVision-Invion/actions/runs/34695505559). 독립 검토/통합 build 완료 아님.
- Evidence: `../Evidence/configured-server-20260912.json`, `../Evidence/configured-server-510ced4-ci.json`. 개인키는 시험 프로세스 메모리, DSN은 환경으로 전달했고 공개 증거에 포함하지 않았다.

## 다음 담당과 인수 조건

Codex: 실제 backend 후보 컨테이너 build/비root 설정 mount·DB 확장 요구 및 Workspace/business 활성화 검증을 격리 환경에서 수행한다. 이후 승인 가능한 운영 migration·서비스 전환 계획과 원격 .225 프로필/7개 시험을 연결한다. 운영 서비스·DB schema·Node profile·kill switch는 이번에 변경하지 않았다. 설정 파일 형식 검증만으로 실제 로그인 provider나 실행 가능 상태를 주장하지 않는다.

Claude: 설정/역할·migration 계약 독립 검토, 실제 issuer·운영 계정 준비 및 업무 서비스 활성화 조건 확인. Gemini: /readyz의 workspaceAdmission과 실제 실행 가능 상태 구분, 후보 정본 서버 연결 후 브라우저 검증. 다른 Agent 작업을 대신 완료로 표시하지 않는다.

전체 성숙도 **2775/4800=57.81% 완료,42.19% 잔여** 유지. 원격 실행/통합 CI/독립 검토/운영 인수 게이트 미완료. 동기화 결과는 후속 기록한다.

Obsidian 첫 check는 외부 편집3개로 exit1/쓰기0. 원문·hash 보존 후 공통/Gemini/인계에 수신 요약을 추가했다. 원문을 증거로 보존한 동일 바이트만 sync state로 인수한 뒤 정본을 동기화한다.
