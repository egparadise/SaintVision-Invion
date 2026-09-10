---
doc_id: "HIST-LAN-BOOTSTRAP-20260910"
title: "2026-09-10 LAN-BOOTSTRAP Codex 서버 구성과 Node 등록"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-10T23:48:46+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "lan", "execution-history"]
---

# 실제 수행 범위

S12-BE/LAN-BOOTSTRAP. Owner Codex, reviewer Claude 검토·전달 대기. 시작 계약은 [[2026-09-10_LAN-BOOTSTRAP_Codex_착수]]. 구현 SHA `b3e44709a6e0a35205043407cbe09ae719f918ef`, 브랜치 `agent/codex/lan-bootstrap`; base `91d2607b3066fd6435ae877e5bda34b0dccf059f`. 제품 main은 별도이며 이번 변경을 병합하지 않았다.

사용자 확인: 서버 `192.168.45.99`, 상대 Windows PC `192.168.45.225`; 상대 Ubuntu에서 Docker 28.0.4/API 1.48 실행 확인. 기존 SSO가 없으므로 웹 로그인은 후속으로 두고 Node 연결부터 진행하기로 했다. 이번 서버는 실제 PostgreSQL 기반 `ObservationWorker`와 공개 설치 파일 배포 서비스다. 사용자용 제품 API·웹 로그인·Workspace·Run 실행이 구성됐다는 뜻이 아니다.

## 실제 변경

- `tools/lan_pilot.py`, `tools/lan_pki.py`: 독립 DB 초기화, 비owner runtime, 관측 전용 tenant, 공개 CSR 검증·인증서 발급·기존 channel 계약의 pin 등록, 관측 loop, 제한된 공개 파일 배포.
- `deploy/lan`: Linux Node scratch 이미지, Windows/Ubuntu 설치 및 시작 절차. 상대 PC 개인키는 해당 PC 안에서 생성한다. bundle에는 CA 공개 인증서, 공개 permit key, peer-policy, 이미지와 스크립트만 포함한다.
- 서버 `.work/lan-pilot`은 사용자·SYSTEM·Administrators만 접근하도록 ACL을 설정했다. DB/CA 비밀 값은 Git·보고서·콘솔에 넣지 않는다.
- DB `saintvision-lan-db-bff1a31d`: 기존 로컬 image content ID로 생성, `127.0.0.1:55440`에서만 접근. CPU 1, RAM 512 MiB, PID 256 제한. 기존 다른 컨테이너·DB를 초기화하지 않았다.
- DB migration head `0023_containment_approvals`. `inv_lan_runtime`은 `inv_kernel` 상속, superuser/RLS bypass/DB 생성/role 생성 권한 없음.
- tenant kill switch `true`; project grant·제공 자원·Run·lease 없음. Node 이미지는 Docker socket을 mount하지 않아 관측만 가능하다. 실제 업무 실행 활성화는 후속 구성이다.
- Windows 방화벽 `SaintVision-LAN-Bootstrap-192.168.45.225`: 서버의 TCP 18081을 상대 IP에만 허용. 프로필 전체 변경·방화벽 비활성화·WSL 포트 전달 변경은 하지 않았다. 관리자 UAC 실행 후 적용을 조회했다.
- 공개 다운로드 서버 `192.168.45.99:18081`은 정해진 세 파일과 자체 healthz만 응답한다. 제품 Control Plane health endpoint라고 표시하지 않는다. 파일의 신뢰는 대화로 별도 전달한 SHA-256을 확인한 뒤 실행하는 방식이다.

## 로컬 합격 증거

| 실제 명령·범위 | 결과 |
|---|---|
| `lan_pilot.py ... init --server-ip 192.168.45.99 --node-ip 192.168.45.225` | exit 0; 독립 DB migration 및 runtime 연결 |
| `lan_pilot.py ... bundle --go <local Go 1.27.1>` | exit 0; Linux/amd64 CGO 없는 Node build·scratch Docker image·zip |
| `pytest tests/integration/test_lan_bootstrap.py tests/core/test_lan_pki.py -q` | exit 0; 9 passed, 6.51초; 별도 시험 DB에서 containment trigger와 다른 tenant 보존 검증 |
| PowerShell parser, Bash `-n` | exit 0; 설치 스크립트 구문 검사 |
| 실제 로컬 Node 이미지 smoke | exit 0; strict TLS 양방향 인증·자원 snapshot 성공·인증서 없는 client 거부 |
| 다운로드 byte 비교와 공개 파일 목록 검사 | exit 0; 원본과 동일, Bash LF, 비밀 경로 4종 404 |
| `check_docs.py`, `check_ontology.py` | exit 0; 문서·RDF·SHACL 검사, 제품 장비 시험과 구분 |

Node image `sha256:77bc2c3be2344f804ea3c75c346abab3311a56d03426a12d78aefb3d3066c755`.
실제 배포 zip SHA-256 `5427f1a7562cc054a0f7041a37404c24feaac8bc2258e7fda490786c56cf1e72`, 7,251,599 bytes.
로컬 smoke는 별도 임시 Node ID·CA로 같은 서버의 Docker 컨테이너에서 수행했다. 상대 물리 PC가 연결됐다는 증거로 사용하지 않는다. 임시 컨테이너와 해당 익명 volume만 정리했다.

## 상대 PC 등록

사용자가 공개 CSR을 전달했다. Node ID `nod_01M25VZZFBYQVFGYB11G7HC10J`와 Ed25519 서명을 확인했다. CSR 확장 요청 없음. 상대 개인키를 수신하지 않았다.

`lan_pilot.py ... enroll --csr <public CSR>` exit 0. Node certificate DER SHA-256 `1b23ec52df857393587ab7990bfdc50dfd404e35fd75b6eaea9dadfaa5c2d15d`, 다운로드 PEM SHA-256 `3f407ec459fd85e4dea031341fcff4d355f2f8ac95a47d7f1b873084394b51bc`. 기존 `provision_channel`로 version 1을 등록했다. Endpoint `https://192.168.45.225:18443`.

상대 PC에 `Start-Worker.ps1 -CertificateSHA256 <검증값>` 실행을 안내했다. 마지막 확인 시 Node는 `offline`, 실제 snapshot 없음. 상대 시작 결과·실제 mTLS heartbeat 및 snapshot이 도착하기 전에는 두 PC 연결 완료로 표시하지 않는다.

## CI·동기화·인계

두 구현 commit의 origin push는 성공했다. 최초 코드 SHA ca2cb77의 Core `34490890193`, Backend `34490890196`, Docs `34490890522`는 계정 결제/지출 제한으로 job 시작 전에 차단됐다. 최종 구현 b3e4470도 Core `34491267941`, Backend `34491267844`, Docs `34491267871`이 같은 사유로 시작 전에 차단된 것을 23:47:42 KST 확인했다. 계정 설정은 사용자 지시대로 변경하지 않았다.

23:48:46 KST `sync_obsidian.py --apply --state .work/lan-sync-state.json --adopt-identical` 및 후속 `--check` exit 0. 3개 신규 파일 export, 전체 295개 destination hash 일치, pending 0, conflicts 0. 이는 로컬 Obsidian 사본 검증이며 OneDrive 클라우드 업로드 완료 증거는 아니다. 이후 본문 갱신도 같은 state로 재검사·동기화한다.

오류·정정은 [[2026-09-10_LAN-BOOTSTRAP_오류와해결]]. CI·독립 검토·상대 PC 검증이 남아 있으므로 S12-BE 완료 상태로 올리지 않는다.

다음 담당: 사용자 상대 PC 시작 → Codex 실제 mTLS·snapshot·offline/복구 확인 및 실행 범위 확정 → Claude 독립 검토·운영 서비스화 → Gemini 실제 인증 설정 이후 웹 상태 연결. CA 7일, peer 인증서/초기 policy 최대 6일이며 갱신은 별도 운영 작업이다. 서버 재부팅 후 observer/배포 프로세스 자동 시작은 아직 구성하지 않았다.
