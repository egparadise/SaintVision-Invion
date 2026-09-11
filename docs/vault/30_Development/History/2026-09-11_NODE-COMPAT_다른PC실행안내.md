---
doc_id: "GUIDE-NODE-COMPAT-WORKER-20260911"
title: "다른 PC 실행 시험 연결 안내"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T09:32:53+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["guide", "node", "lan"]
---

# 다른 PC 실행 시험 연결

서버 `192.168.45.99`의 준비는 끝났다. worker `192.168.45.225`는 mTLS 관측 전용으로 연결되어 있다. 원격 관리 셸 22번에 접속할 수 없어 아래 설치만 해당 PC에서 실행해야 한다. Node 개인키를 서버로 전송하지 않는다.

**다른 PC의 Windows PowerShell**에서 다음 블록을 실행한다. Windows 사용자 `egpar`, Ubuntu WSL, 기존 SaintVision Node 설치를 전제로 한다. 기존 Node 인증서/identity/epoch/volume/journal을 유지하고 observation 컨테이너를 백업한 다음 고정 probe 실행 시험 프로필을 설치한다. 일반 프로젝트나 GPU 실행을 허용하는 설치는 아니다.

```powershell
$svRoot = Join-Path $env:USERPROFILE 'Downloads\SaintVision-LAN'
$svZip = Join-Path $svRoot 'worker.zip'
$svHash = 'f9167bb15402dffc3ba00dc08e8effca7bf0cf4124229ba39f0931240cc3cdd1'
Invoke-WebRequest -UseBasicParsing -Uri 'http://192.168.45.99:18081/worker.zip' -OutFile $svZip -TimeoutSec 60
if ((Get-FileHash $svZip -Algorithm SHA256).Hash -ne $svHash) { throw '설치 파일 해시 불일치' }
$svDir = Join-Path $svRoot 'worker'
Expand-Archive -LiteralPath $svZip -DestinationPath $svDir -Force
$svSetup = Join-Path $svDir 'Enable-ExecutionTests.ps1'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $svSetup
```

출력의 `nodeId`, `executionImage`, `profile` JSON만 Codex에게 알려주면 된다. 기대 프로필은 `lan-test-v1`이다. 설치 오류가 나면 그 오류를 전달하고 키·volume·journal을 삭제하지 않는다. 서버는 새 프로필의 fresh mTLS 관측을 확인한 뒤 실제 고정 probe 정상/출력/실패/timeout, 중복 전달 및 전송 중단 뒤 복구 시험을 실행한다.

현재 이 설치 결과는 아직 받지 않았다. 서버 로컬 Node 시험 통과와 이 두 PC 시험은 별개다. 이 공개 ZIP은 기존 worker Node 소프트웨어를 사용하는 시험 설치본이며, 새 Docker 호환성 커밋 08d8dde를 원격 배포했다고 해석하지 않는다.

서버가 다시 로그인한 직후에는 웹/Studio 자동 시작과 별도로 공개 설치본 전송 서비스 18081을 켜야 할 수 있다. 다운로드 연결 실패 시 서버 상태부터 확인한다. [[2026-09-11_NODE-COMPAT_Codex_검증보고]]에 현재 확인 범위가 있다.
