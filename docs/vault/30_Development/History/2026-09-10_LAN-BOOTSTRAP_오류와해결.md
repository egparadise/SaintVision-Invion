---
doc_id: "ERR-LAN-BOOTSTRAP-20260910"
title: "2026-09-10 LAN-BOOTSTRAP 오류와 해결"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-10T23:46:27+09:00"
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

미완료: 상대 PC Node 시작과 실제 네트워크 관측. 연결되지 않은 상태를 정상 연결·장비 합격으로 처리하지 않는다.
