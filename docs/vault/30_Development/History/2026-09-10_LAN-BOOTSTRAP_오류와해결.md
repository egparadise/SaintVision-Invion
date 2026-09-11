---
doc_id: "ERR-LAN-BOOTSTRAP-20260910"
title: "2026-09-10 LAN-BOOTSTRAP 오류와 해결"
version: "1.2.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T00:33:25+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "error", "lan"]
---

# 오류와 해결

실행 기록: [[2026-09-10_LAN-BOOTSTRAP_Codex_서버구성과Node등록]].

1. 기존 Docker/WSL 응답 정지: Docker CLI 종료 요청은 exit 0이었지만 프로세스가 남았고, `wsl --shutdown`은 30초 timeout. 일반 권한 서비스 종료는 Access denied. 사용자의 Docker/WSL 재시작 승인과 Windows UAC 승인 후 서비스 종료를 요청했다. 첫 30초 대기에는 timeout이었지만 이후 실제 Stopped를 확인했고 WSL 조회로 재기동됐다. Docker 재실행 후 양쪽 context에서 Engine 20.10.22/API 1.41 응답과 기존 컨테이너 실행을 확인했다. 원인 자체는 확정하지 않는다.
2. 배포 전 PKI 검토: strict X.509 검증에 필요한 SKI/AKI 확장을 초기 생성 코드에서 보완했다. 아직 상대에게 전달하지 않은 공개 인증서를 같은 기존 개인키로 다시 발급하고 peer-policy를 version 2로 올렸다. 원래 공개 파일은 비공개 상태 폴더에 보존했다. 이후 실제 Go Node와 Python strict mTLS 검증이 성공했다. 별도의 양방향 strict TLS 회귀 시험을 추가했다.
3. 관측 tenant 초기값: `INSERT ... ON CONFLICT DO NOTHING`이 기존 DB의 tenant 생성 trigger가 만든 `kill_switch=false` 행을 그대로 두는 문제가 DB 확인 assertion으로 발견됐다. 관측 tenant 생성 트랜잭션에서 `true`를 명시적으로 pin하고 시작 완료 전에 재확인하도록 수정했다. 실제 파일럿은 Run·grant·lease 0건을 확인한 뒤 해당 행만 true로 정정했다. 다른 tenant를 유지하고 실행을 거부하는 실제 DB 회귀 검증 통과. 변경 SHA `b3e44709a6e0a35205043407cbe09ae719f918ef`.
4. PowerShell `python -c` 중첩 따옴표로 로컬 검증 한 건이 SyntaxError. 별도 `.py` 파일로 실행해 공개 다운로드 hash·경로 차단 검증을 완료했다. 제품 오류와 구분한다.
5. GitHub CI: 최초 push의 3개 workflow는 계정 결제 또는 지출 제한으로 시작하지 못했다. 계정을 건드리지 않았고 로컬 통과를 CI 통과로 바꾸어 보고하지 않는다.
6. 상대 PC 시작 명령 복사: 사용자 출력에서 `powershell.exe`가 빠져 `-NoProfile`을 명령으로 인식했고 파일명 `Start-Worker.ps1` 중간에 줄바꿈이 들어갔다. 경로·파일명·해시를 변수로 분리한 네 줄 명령을 안내했다. 이 오류에서는 설치 스크립트 자체가 시작되지 않았다.
7. Docker image 주소: 초기 source image ID `77bc2c3b…`로 수신 Docker에서 조회했을 때 `No such image`가 발생했다. tag를 보존하여 save/load하고, 수신 이미지의 OS·architecture·RootFS layers·실행 설정을 검증한 후 수신 ID를 사용하도록 수정했다. 실제 사용자 출력에서 `Loaded image: saintvision-lan-node:bff1a31d`와 container 생성 확인. Docker image store 설정은 변경하지 않았다.
8. 설치 재시도 identity: 기존 manifest 비교가 `agentImage`까지 불변으로 취급해 수정 bundle의 `Existing Node identity differs` 오류가 발생했다. 이전·새 bundle에서 Node/tenant/epoch/IP/port가 같고 image만 다른 것을 확인했다. 이미지 검증은 유지하며 지속 identity에서 소프트웨어 image ID를 제외했다. 회귀 시험 통과, 사용자의 owned volume 재사용 및 container 생성 확인. `--reuse-image`로 설치 스크립트 수정 시 Go VCS metadata 때문에 이미지를 다시 만드는 것을 피한다.
9. 공개키 읽기 권한: 2026-09-11 사용자 출력에서 signer.pub는 32 bytes, UID/GID 1000/1000, mode 600이었고 container user는 root였다. `--cap-drop ALL`인 Node가 읽지 못해 `NODE-0005`로 재시작했다. 같은 조건을 별도 로컬 컨테이너에서 재현하고 UID/GID 0/0·mode 600으로 명시한 tar를 `docker cp -a`로 전달해 해결했다. 5개 파일의 내용과 소유권 readback, 실제 strict mTLS·snapshot 검증 통과. 수정 SHA `e4459b0bcdd91a614f8c7f0826ef59af7636e51d`; 물리 상대 PC의 복구 결과는 별도 확인이 필요하다.
10. 복구 명령 복사: tar 파이프라인이 복사 중 여러 줄로 나뉘어 `option requires an argument -- f`, `must specify at least one container source`가 발생했다. 복구 성공으로 처리하지 않았다. 긴 셸 명령 대신 independently verified bundle에 `Repair-Worker.ps1`을 포함했고 짧은 Windows 실행 명령으로 안내했다. 개인키는 상대 PC 안에서만 처리한다.
11. 실제 화면 API 초안: 존재하지 않는 node_channels.revoked_at을 조회해 실패했다. 실제 공통 계약의 enabled/certificate_not_after 및 snapshot channel_version 검사로 수정하고 실측 DB 조회를 확인했다.
12. 실행 시험 launch 초안: privileged/hostAccess 명시 필드 누락으로 NodeExecutionPermit schema 검증 4건 실패. 두 값을 false로 명시해 네 모드 모두 통과했다. 실제 원격 실행 성공과 구분한다.
13. 새 worktree Obsidian state 복사: .work 폴더가 없어 Copy-Item 실패. 해당 폴더를 생성하고 기존 baseline state를 복사한 뒤 check/apply/check를 수행했다. 기존 Obsidian 문서를 강제로 덮어쓰지 않았다.
14. Orca 브라우저: 탭 생성 후 `runtime_unavailable: The Orca runtime closed the connection before responding`으로 snapshot/screenshot 실패. 사용자 Orca는 재시작하지 않았고 별도 Edge/Playwright로 실제 화면·상태·오류 복구 검증을 완료했다. 브라우저 실패 원인 자체는 확정하지 않는다.

2026-09-11 00:07 KST 사용자 복구 실행 성공 후 실제 상대 PC의 mTLS snapshot과 DB online 전이를 확인했다. 00:08:08 KST 연속 10회 관측 성공까지 기록했다. 공개키 오류 및 두 PC 관측 연결은 해결됐으며, 실제 업무 실행·재부팅 복구·웹 인증 구성·CI/독립 검토는 후속이다.

후속 실제 화면과 시험 준비는 [[2026-09-11_LAN-LIVE_Codex_실제화면과시험준비]]에 기록했다. 원격 실행 준비 결과는 아직 대기 중이다.
