---
doc_id: "HIST-STORAGE-WINDOWS-20260912"
title: "2026-09-12_STORAGE-WINDOWS_Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T16:41:40+09:00"
source_of_truth: "Git"
---

# Windows/WSL 교체 진입점 검증

Product `e512b60b8a4569caf1483384efd9ea52a17e4945`, base773e3e6, agent/codex/workspace-bridge. CX-02/S12-ST Codex owner, Claude reviewer pending. GUIDE/GOV-AGENT/GOV-GIT1.1.0, agent-delivery1.1.0/core-reliability1.0.0. [[2026-09-12_STORAGE-WINDOWS_Codex_착수]], ADR-096.

## 작업한 것

Replace-Storage.ps1에 특정 로컬 폴더·policy SHA256 입력과 prepare/apply 경로를 추가했다. 드라이브 전체·junction/reparse 조상·bundle과 겹치는 source·잘못된 policy hash·배정 PC IP 불일치를 거부한다. WSL Ubuntu Python을 인수 배열로 호출하며 bash -c 문자열을 만들지 않는다. 결과의 Node/tenant/epoch/정책/request hash/상태/현재·이전 컨테이너 ID를 대조하고 operationalAcceptanceAssessed=false를 확인한다. 키/정책 경로 원문은 결과에 포함하지 않는다.

worker_storage_bridge.py는 기존 WSL private Node의 manifest 정체성을 먼저 확인한다. 기존 root의 키나 manifest를 복사·갱신하지 않는다. root와 고정 storage-replacement-input 디렉터리를 잠그고 승인 bundle image를 가져와 layers/config를 검증한다. 새 policy exact bytes는 임시 파일 fsync→배타적 hardlink 게시→임시 이름 제거→directory fsync로 준비한다. plan+preflight receipt를 0600 request.json으로 원자 기록하고 SHA256을 반환한다. prepare는 이미지 저장소/준비 파일을 바꾸지만 Node를 정지·교체하지 않는다.

Apply는 준비 결과의 requestSHA256을 명시해야 하며 같은 policy/source/manifest/기록 bytes만 사용한다. request를 새로 생성하지 않고 기존 worker_replace의 durable 재개를 사용한다. 준비/실행 재시도는 같은 요청을 유지하며 변경된 source나 hash는 거부한다. 완료는 awaiting-server-mtls-verification/restart=no이며 스케줄링 승인이나 건강 판정이 아니다. 기존 컨테이너·키/journal 보존 규칙은 ADR-095와 같다.

## 확인한 것

- clean 동일 SHA Windows **121 passed/exit0**: `python -m pytest -q tests/core/test_storage_windows_launcher.py tests/core/test_lan_replace.py tests/core/test_lan_replacement.py tests/core/test_lan_storage.py tests/core/test_lan_worker_config.py tests/core/test_lan_workspace_upgrade.py --junitxml=.work/storage-windows-boundaries.xml`. 신규10개는 실제 powershell.exe로 진입점을 실행하되 wsl.exe와 Get-NetIPAddress는 모사한다. 공백·& 폴더를 하나의 인수로 전달, prepare/apply 정상, 정책·Node·주소·운영 인수 true·request hash·종료 코드·중복 컨테이너 ID·bundle 중첩 거부를 확인했다. [개별 case](../Evidence/storage-windows-boundaries-e512b60.json).
- clean 동일 SHA 실제 Linux Docker Python CLI **1 passed/0 skipped/exit0**: `python tools/check_storage_bundle.py --prepared .work/sv-kernel-6a9f62c3c81c/prepared.json --bridge-only`. 새 WSL HOME을 모사한 Linux private 경로와 실제 Go Node로 prepare 반복 동일 hash·다른 source/request hash 거부·실제 교체·apply 반복 새 ID 유지·원래 manifest 보존·키 미복사를 확인했다. [image/hash/코드 SHA](../Evidence/storage-windows-linux-e512b60.json). 기존 교체11개는 이번에 선택하지 않았고 f766146의 별도 검증 기록을 참조한다. Go 소스가 같아 f9d69a8 검증 바이너리를 재사용, runtimeCodeSHA 구분.
- 실제 `wsl.exe --list --quiet` exit0: 이 서버에는 docker-desktop/docker-desktop-data만 있으며 Ubuntu는 없다. **Windows→Ubuntu→Docker 전체 경로 및 원격 .225 배포는 미수행**이다. Windows 드라이브 경로가 Docker daemon에서 다르게 표현되면 기존 exact mount 검사가 거부할 수 있으므로 실제 PC에서 확인해야 한다.
- git push exit0. [같은 SHA CI](../Evidence/storage-windows-e512b60-ci.json)는 결제/한도 때문에 job이 시작되지 않았다. 조회 당시5개 failure/1개 queued이며 queued 항목에도 같은 미시작 annotation이 있다. 재실행·병합·운영 DB 변경 없음. PR19 draft/Claude 독립 검토 pending.

## 다음 작업

Codex: 원격 PC의 Ubuntu/Docker 경로와 준비/교체 receipt를 실제 검증하고, 허용 폴더·서버의 현재 policy를 맞춘 뒤 서버 mTLS→서명 sample→Evidence/StorageCheck→인증 조회까지 확인한다. 임의 폴더·버전을 만들어 배포하지 않는다. 서버 계정/원격 운영 인수 없이 schedulable을 올리지 않는다. 잘못된 정책의 forward 변경, 장비 전원 장애, remote7/5대/GPU 검증은 별도다.
Claude: ADR-096 입력·prepared request 해시/잠금·bridge/executor 경계를 독립 검토. Gemini: prepare/로컬 설치/서버 인수 상태를 분리 표시하고 실제 커널 계약 브라우저 검증을 수행한다.

전체 **2775/4800=57.81% 완료 /42.19% 잔여 유지**. Windows 모사 시험과 Linux 시험을 물리 Windows/원격 인수로 합쳐 표현하지 않는다. [[Codex Node 저장소 설정 설치와 교체 절차]]에 운영 입력 예제를 기록했다.

전달 검사: check_docs exit0(문서340/작업48), check_ontology exit0, git diff --check exit0. PR19 갱신/draft 유지. 보고ea5eff8 push exit0. 첫 Obsidian check는 외부3개 변경으로 exit1/쓰기0. 원문/hash를 보존하고 Gemini ea508ea 주장을 독립 검증과 구분해 수신 기록했다. 동일 bytes 보존을 확인한 뒤 쓰기0 인수·정본 동기화를 진행한다.
