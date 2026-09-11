---
doc_id: "GUIDE-REMOTE-WORKSPACE-20260911"
title: "원격 Workspace Node 설치 안내"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-09-11T11:35:00+09:00"
source_of_truth: "Git"
---

# 다른 PC의 새 Workspace 실행 프로필 설치

대상은 Windows PC `192.168.45.225`, 기존 Ubuntu WSL Node `nod_01M25VZZFBYQVFGYB11G7HC10J`다. 서버는 `192.168.45.99`다. 원격 관리 포트 22/5985/5986이 닫혀 있어 설치만 해당 PC에서 한 번 실행한다. 이미 부여된 배포·검증 승인에 따른 작업이며 별도 승인 요청이 아니다.

아래를 **다른 PC의 Windows PowerShell**에 한 블록으로 붙여 넣는다. 111,708,260 byte 설치본에는 공개 신뢰 자료·Node·Python 실행 이미지와 설치 스크립트만 있다. Node 개인키는 기존 WSL 경로에 그대로 두며 서버로 보내지 않는다.

```powershell
$svRoot = Join-Path $env:USERPROFILE 'Downloads\SaintVision-LAN'
New-Item -ItemType Directory -Path $svRoot -Force | Out-Null
$svZip = Join-Path $svRoot 'workspace-worker.zip'
$svWeb = New-Object System.Net.WebClient
try { $svWeb.DownloadFile('http://192.168.45.99:18081/workspace-worker.zip', $svZip) } finally { $svWeb.Dispose() }
$svHash = 'b651729eec874c947c42ab4a24be493bbe2543bd271bc80f6a20d6fd62a4cbfe'
if ((Get-FileHash -LiteralPath $svZip -Algorithm SHA256).Hash -ne $svHash) { throw '설치본 해시 불일치' }
$svDir = Join-Path $svRoot 'workspace-0123640'
Expand-Archive -LiteralPath $svZip -DestinationPath $svDir -Force
$svScript = Join-Path $svDir 'Enable-Workspace.ps1'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $svScript
```

마지막 JSON에는 `profile: lan-workspace-v1`, 실제 `agentImage`, `executionImage`, `identityPreserved`, `journalPreserved`가 나온다. 이 JSON 또는 오류만 Codex에게 전달한다. Docker의 이미지 저장 방식에 따라 import 후 실제 ID가 달라질 수 있어 서버는 이 출력의 executionImage를 사용한다. Node ID·epoch·인증서·이미지 내용/config를 검증하며 태그만 신뢰하지 않는다.

설치 스크립트는 기존 자격 증명이 일치하고 Node에 미정리 workload 컨테이너가 없을 때만 진행한다. 이전 Node 컨테이너는 정지·백업하고 기존 volume/journal을 재사용한다. 새 Node 시작 실패는 이전 컨테이너로 되돌리며 실패 컨테이너도 보존한다. 설치 도중 PowerShell/WSL 자체가 중단됐다는 오류가 나오면 같은 스크립트의 `-Rollback`으로 기록된 미완료 설치만 복구할 수 있다. 성공 이후 새 작업이 있을 수 있는 상태의 자동 구버전 되돌리기는 거부한다. 키·volume·journal을 삭제하지 않는다.

Node hard limit는 CPU 1 core, RAM 512 MiB, 30초이며 아래 시험은 CPU 0.5 core/RAM 64 MiB 이하로 수행한다. 작업은 non-root·read-only root·network none·host bind 없음·Docker socket 없음이고, 임시 Workspace snapshot만 받는다. 신뢰된 Node 관리 컨테이너만 로컬 Docker socket에 접근한다. 대규모 저장소·장시간 모델 학습·GPU 허용 프로필이 아니다.

설치가 끝나면 Codex는 fresh mTLS profile을 확인하고 **운영 DB와 분리한 시험 DB**에서 최초 Python/CPU 학습·실행 전/실행 중 취소·exit 7·timeout·서버 프로세스 종료 후 출력 복구를 확인한다. JWT/승인자는 그 시험 DB에서만 사용하는 합성 actor다. 실제 물리 Node·파일·receipt/Evidence 검증과 운영 로그인/일반 업무 인수는 구분한다. 기존 운영 DB의 kill switch·grants·offers는 변경하지 않는다.

설치본 코드는 `01236401367c4a430cf73da2b68984ca411e4883`, 이미지 코드는 실제 첫 실행 159개를 통과한 `b6301a9613097122a7574fa647b63d791fe13d2d`다. 기존 `Enable-ExecutionTests.ps1` probe 설치와 다르다. 현재 배포 및 검증 기록은 [[2026-09-11_REMOTE-WORKSPACE_Codex_검증보고]]를 따른다.
