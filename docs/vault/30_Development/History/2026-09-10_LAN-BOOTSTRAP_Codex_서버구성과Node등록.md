---
doc_id: "HIST-LAN-BOOTSTRAP-20260910"
title: "2026-09-10 LAN-BOOTSTRAP Codex 서버 구성과 Node 등록"
version: "1.1.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T00:08:58+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "lan", "execution-history"]
---

# 실제 수행 범위

S12-BE/LAN-BOOTSTRAP. Owner Codex, reviewer Claude 검토·전달 대기. 시작 계약은 [[2026-09-10_LAN-BOOTSTRAP_Codex_착수]]. 최종 구현 SHA `e4459b0bcdd91a614f8c7f0826ef59af7636e51d`, 브랜치 `agent/codex/lan-bootstrap`; base `91d2607b3066fd6435ae877e5bda34b0dccf059f`. 제품 main은 별도이며 이번 변경을 병합하지 않았다.

사용자 확인: 서버 `192.168.45.99`, 상대 Windows PC `192.168.45.225`; 상대 Ubuntu에서 Docker 28.0.4/API 1.48 실행 확인. 기존 SSO가 없으므로 웹 로그인은 후속으로 두고 Node 연결부터 진행하기로 했다. 이번 서버는 실제 PostgreSQL 기반 `ObservationWorker`와 공개 설치 파일 배포 서비스다. 사용자용 제품 API·웹 로그인·Workspace·Run 실행이 구성됐다는 뜻이 아니다.

## 실제 변경

- `tools/lan_pilot.py`, `tools/lan_pki.py`: 독립 DB 초기화, 비owner runtime, 관측 전용 tenant, 공개 CSR 검증·인증서 발급·기존 channel 계약의 pin 등록, 관측 loop, 제한된 공개 파일 배포.
- `deploy/lan`: Linux Node scratch 이미지, Windows/Ubuntu 설치 및 시작 절차. 상대 PC 개인키는 해당 PC 안에서 생성한다. bundle에는 CA 공개 인증서, 공개 permit key, peer-policy, 이미지와 스크립트만 포함한다.
- 이미지 archive는 tag를 보존하고 수신 Docker의 filesystem layer·실행 설정을 검증한 후 수신 측 content ID로 실행한다. 소프트웨어 image ID와 지속 Node/tenant/epoch/IP identity를 분리했다. 설치 스크립트만 수정할 때 `bundle --reuse-image`로 기존 이미지를 유지한다.
- 파일 복사는 메모리 tar 안에 UID/GID 0:0, mode 600을 지정하고 `docker cp -a`로 수행한다. 5개 파일 모두 내용·권한·소유자를 다시 읽어 검증하고 시작 후 5초간 재시작 여부를 확인한다. `Repair-Worker.ps1`은 지정 Node의 멈춘 컨테이너·identity·경로·owned volume을 확인한 뒤 기존 로컬 파일 5개만 다시 복사한다. 키·journal·container 설정은 유지한다.
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
| `pytest tests/integration/test_lan_bootstrap.py tests/core/test_lan_pki.py tests/core/test_lan_worker_config.py -q` | 2026-09-11 00:05 KST, exit 0; 28 passed, 5.83초; 별도 시험 DB에서 containment trigger와 다른 tenant 보존, strict PKI, portable image·identity·복구 대상 검증 |
| PowerShell parser, Bash `-n` | exit 0; 설치 스크립트 구문 검사 |
| 실제 로컬 Node 이미지 smoke | 2026-09-11 00:04 KST, exit 0; UID 1000/mode 600에서 NODE-0005 재현 → 같은 컨테이너에 실제 installer 파일 복사 함수 적용 → UID 0/mode 600 readback 및 5초 실행 확인 → strict TLS 양방향 인증·자원 snapshot 성공·인증서 없는 client 거부 |
| 다운로드 byte 비교와 공개 파일 목록 검사 | exit 0; 원본과 동일, Bash LF, 비밀 경로 4종 404 |
| `check_docs.py`, `check_ontology.py` | exit 0; 문서·RDF·SHACL 검사, 제품 장비 시험과 구분 |

현재 Node image `sha256:2cc00e5cc24c4d61ea9b49454ec13f3e2945ff7a2ecabdaab2a998efe28cc9aa`, tag `saintvision-lan-node:bff1a31d`. 00:06 KST 실제 공개 URL의 byte 일치와 public-only 구성을 검증한 zip SHA-256 `03ffdf8694d29c82e210df57b898244fc2f8b6494983c79524177d38764f2a8e`, 7,255,680 bytes. 최초 zip `5427f1a7…`과 후속 `a431b76e…`, `59190f60…`은 현재 다운로드 검증값으로 사용하지 않는다.
로컬 smoke는 별도 임시 Node ID·CA로 같은 서버의 Docker 컨테이너에서 수행했다. 상대 물리 PC가 연결됐다는 증거로 사용하지 않는다. 임시 컨테이너와 해당 익명 volume만 정리했다.

## 상대 PC 등록

사용자가 공개 CSR을 전달했다. Node ID `nod_01M25VZZFBYQVFGYB11G7HC10J`와 Ed25519 서명을 확인했다. CSR 확장 요청 없음. 상대 개인키를 수신하지 않았다.

`lan_pilot.py ... enroll --csr <public CSR>` exit 0. Node certificate DER SHA-256 `1b23ec52df857393587ab7990bfdc50dfd404e35fd75b6eaea9dadfaa5c2d15d`, 다운로드 PEM SHA-256 `3f407ec459fd85e4dea031341fcff4d355f2f8ac95a47d7f1b873084394b51bc`. 기존 `provision_channel`로 version 1을 등록했다. Endpoint `https://192.168.45.225:18443`.

상대 PC에서 certificate 검증·image load·owned volume 재사용·container 생성까지 확인했다. 그러나 Node가 `NODE-0005: pinned public key unavailable`로 재시작했다. 사용자가 멈춘 container에서 조회한 공개키는 32 bytes, `-rw------- 1000/1000`, container user는 빈 값(root)이었다. root 프로세스에 capability가 없으므로 UID 1000 소유의 mode 600 파일을 읽지 못하는 문제를 로컬에서 재현했다.

00:06 KST 수정 bundle을 공개 URL에서 검증하고 상대에 `Repair-Worker.ps1` 실행을 안내했다. 배포 직후 서버 DB는 `offline`, `observed: false`, `snapshot: null`이었다. 이후 사용자가 파일 5개의 UID/GID 0:0·mode 600 검증과 Node 5초 실행 성공 출력을 전달했다.

## 실제 두 PC 연결 확인

2026-09-11 00:07:33 KST 서버에서 `192.168.45.225:18443` TCP 연결, 실제 상대 Node의 strict mTLS resource snapshot, `NodeObservation.poll_resources` 결과의 DB 저장을 확인했다. 반환 Node ID는 배정값과 같으며 상태는 `online`이다. 별도 서버 내 smoke와 구분되는 실제 상대 PC 결과다.

00:08:08 KST `.work/lan-pilot/connection-receipt.py` exit 0. 서버 observer의 00:07:17~00:08:06 KST 연속 10회 결과가 모두 `observed: 1`, `unavailable: 0`이고, DB `observed: true`, `online`, 20초 이내 최신 snapshot을 확인했다. 근거 JSON은 비공개 로컬 상태 폴더의 `connection-receipt.json`에 저장했다. `db-receipt.py` exit 0으로 kill switch true, 비owner runtime 권한, 등록 channel 1개도 재확인했다.

측정값은 Node가 보는 Linux 환경의 CPU capacity 16000 millis, memory capacity 8,247,738,368 bytes다. 물리 Windows 전체 사양이나 제공 승인된 자원량이라고 해석하지 않는다. Node 컨테이너의 실행 제한은 여전히 CPU 0.5·RAM 256 MiB다. 이번 확인은 등록·관측 연결이며 실제 Workspace/Run/GPU 작업, 중단·재부팅·복구 시험은 수행하지 않았다.

## CI·동기화·인계

구현 commit의 origin push는 성공했다. 최초 코드 SHA ca2cb77과 후속 b3e4470·631a74e의 workflow는 계정 결제/지출 제한으로 job 시작 전에 차단됐다. 최종 구현 e4459b0의 [Core 34493421532](https://github.com/egparadise/SaintVision-Invion/actions/runs/34493421532), [Backend 34493421419](https://github.com/egparadise/SaintVision-Invion/actions/runs/34493421419), [Docs 34493421463](https://github.com/egparadise/SaintVision-Invion/actions/runs/34493421463)도 같은 사유로 시작 전에 차단된 것을 2026-09-11 00:06:32 KST 확인했다. 계정 설정은 사용자 지시대로 변경하지 않았다.

최초 23:48:46 KST 3개 신규 파일을 동기화했다. 연결 결과를 반영한 2026-09-11 00:08:58 KST `sync_obsidian.py --check`, `--apply --state .work/lan-sync-state.json --adopt-identical`, 후속 `--check`가 모두 exit 0이다. 갱신 2개 파일 export, 전체 295개 destination hash 일치, pending 0, conflicts 0. 이는 로컬 Obsidian 사본 검증이며 OneDrive 클라우드 업로드 완료 증거는 아니다. 이 동기화 결과를 기록한 본문도 같은 state로 재검사·동기화한다.

오류·정정은 [[2026-09-10_LAN-BOOTSTRAP_오류와해결]]. 실제 두 PC 관측 연결은 확인했다. CI·독립 검토와 S12-BE의 나머지 장비/운영 검증이 남아 있으므로 전체 S12-BE 완료 상태로 올리지 않는다.

다음 담당: Codex 후속 실제 작업·offline/복구 검증 및 실행 범위 확정 → Claude 독립 검토·운영 서비스화 → Gemini 실제 인증 설정 이후 웹 상태 연결. CA 7일, peer 인증서/초기 policy 최대 6일이며 갱신은 별도 운영 작업이다. 서버 재부팅 후 observer/배포 프로세스 자동 시작은 아직 구성하지 않았다. 사용자 지시대로 계정 문제는 별도로 두고 실제 업무 실행 시험은 후속으로 남긴다.
