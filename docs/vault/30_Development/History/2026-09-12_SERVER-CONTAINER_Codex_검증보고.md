---
doc_id: "HIST-SERVER-CONTAINER-REPORT-20260912"
title: "2026-09-12 SERVER-CONTAINER Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T23:15:51+09:00"
source_of_truth: "Git"
---

# 후보 컨테이너 실제 기동·권한 경계

CX-02 owner Codex/reviewer Claude pending. base6ff090b, 시험·절차 구현 **2bfd5fac4b1df437a9be4bd52154d8e7386409bd**, branch agent/codex/workspace-bridge. [[2026-09-12_SERVER-CONTAINER_Codex_착수]]. INDEX1.0.52/Codex1.0.31, agent-delivery1.1.0/core-reliability1.0.0.

## 작업·확인

- `docker build -f deploy/Dockerfile.backend -t saintvision-backend-candidate:6ff090b .`:exit0. 실제 image **sha256:b4cddf9f190906f8f3bc4b97a7b5c5a9584803c9eb1a98b2517452dcd2a29fce**. Dockerfile/source/requirements/migrations 등의 이미지 입력은6ff090b와2bfd5fa에서 동일함을 git diff로 확인했다. 후보 image는 보존하고 운영 배포는 하지 않았다.
- `python -m pytest -q tests/integration/test_server_container.py`:**5 passed,53.86초,exit0**. 실제 Docker 기본 CMD인 saintvision.server:create_app --factory, UID65532, readonly root/config·cap-drop ALL·no-new-privileges·별도 tmpfs Workspace. 최초 동일 시험 파일을 검증한 뒤2bfd5fa에 commit/push했다. 반복 실행으로 시험 수를 늘리지 않았다.
- 새 일반 `postgres:16`의 tmpfs 폐기 클러스터에서 실제 migration head0037 적용·비소유자 로그인 역할 사용. 운영 DB/역할 변경 없음. 현재 migration은 pgvector extension을 사용하지 않는다.
- 정상 설정·Workspace 설정 두 경우 /readyz200, 무토큰401, 실제 grant에 따른 프로젝트 목록 확인. UID65532 실측 및 설정 파일 쓰기 실패 확인.
- 읽을 수 없는 api.json(owner0/mode600), 그룹 쓰기 api.json(mode660), 타인 읽기 signing key(mode644)의 세 경우 모두 nonzero exit로 서버 기동 거부. 정상 readonly/0600 키는 기동했다.
- Workspace는 합성 TLS와 profile·resource 설정만 로딩했다. 응답 `workspaceAdmission=configured`, **executionDispatcher=external-worker-required**를 확인했다. 등록되지 않은 합성 memory resource를 포함하므로 실행 인수 아님. Node mTLS 통신·원격 실행·영속 Workspace 재개/복구는 수행하지 않았다. Linux named volume 시험이며 Windows host bind mount 검증은 아니다.
- 시험마다 난수 컨테이너/volume을 label 확인 후 정리했다. 외부 DB 컨테이너도 제거했고 실제 운영 서비스는 유지했다. 합성 개인키는 폐기 volume에서만 생성했으며 공개 증거에 넣지 않았다.
- `python tools/check_docs.py`:362문서/48작업 exit0. `python tools/check_ontology.py`:exit0. commit/push exit0.
- CI 같은2bfd5fa: Core34698723487/34698721296,Backend34698723551/34698721268,Docs34698723480/34698721295 모두 결제 제한으로 job 미시작/failure. [Core CI](https://github.com/egparadise/SaintVision-Invion/actions/runs/34698723487). 로컬 image build 성공과 구분한다. 독립 reviewer/운영 인수 pending.

Evidence: `../Evidence/server-container-20260912.json`, `../Evidence/server-container-2bfd5fa-ci.json`. 배포 설명은 deploy/CONFIGURED-SERVER.md.

## 이어서 진행

Codex는 후보의 실제 업무 서비스(business) 활성화·역할 연결, 영속 Workspace volume 및 Windows 설정 전달 경로를 검증한다. 이후 운영 issuer·tenant/epoch·권한과 승인 가능한 migration/서비스 전환 계획을 연결하고 .225의 실행 profile·7개 시험을 진행한다. 원격에 임의 인증 자료나 합성 실행 자원을 배포하지 않는다.

Claude는 candidate factory/업무 service 권한·migration 정합성을 독립 검토하고 실제 로그인 provider/운영 계정 준비를 맡는다. Gemini는 configured와 실행 가능 상태를 구분하고 최신 factory에 대한 화면 경로 검증을 진행한다. 다른 Agent 검토 완료를 대신 선언하지 않는다.

전체 **57.81% 완료·42.19% 잔여** 유지. S12 인수·원격 실행·CI·독립 검토가 미완료다. Obsidian 동기화 결과는 후속 기록한다.

동기화: 2026-09-12T23:16:12+09:00 source37408dd0aaa604a0e3ad037400340720cbe0a711, 관리743파일 전부hash일치·pending0·conflicts0, check/apply/check exit0. 로컬 Obsidian 사본 검증이며 OneDrive 업로드는 미확인. 이 기록 추가 후 최종 정본도 같은 절차로 내보낸다.
