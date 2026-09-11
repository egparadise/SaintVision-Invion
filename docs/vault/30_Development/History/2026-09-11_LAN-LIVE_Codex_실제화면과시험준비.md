---
doc_id: "HIST-LAN-LIVE-20260911"
title: "2026-09-11 LAN-LIVE Codex 실제 화면과 시험 준비"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T00:33:25+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "lan", "execution-history"]
---

# 실행 결과

Task S12-BE/LAN-LIVE; owner Codex; reviewer Claude 및 Frontend 인계 Gemini 검토 대기. 시작 기록 [[2026-09-11_LAN-LIVE_Codex_착수]]. Base bc614c63c2067cc8f5c80c147a177bf354c5b7da, 구현 SHA `6aba42a29862a0e02a3844faf4e830e7a9fbd215`, branch `agent/codex/lan-live-execution`. 원격 push 성공. 제품 main 병합 및 독립 검토는 수행하지 않았다.

## 실제 화면 변경

기존 App.tsx는 가상의 Node 5대·Run·승인을 초기값으로 두고 빈 응답 또는 API 실패 시 그대로 유지했다. 자원 값이 0이어도 기본 CPU·RAM 수치로 바꾸고, 임의의 CPU 변화와 현재 시각 heartbeat를 생성했다. Header도 5/5로 고정돼 있었다.

기본 진입 화면을 `LiveApp`으로 바꿨다. 기존 예시 App·기능 모듈 소스는 유지하지만 기본 화면과 production bundle에서 사용하지 않는다. 메뉴는 실제로 연결된 전체 현황·Node 목록·시험 기록·사용 안내다. 가상 작업 실행/취소/승인 버튼을 현재 기능처럼 노출하지 않는다.

`tools/lan_console.py`가 기존 PostgreSQL 파일럿 tenant를 비owner runtime으로 읽는다. 현재 epoch·channel version·enabled·인증서 만료를 확인하고 20초 이내 resource snapshot만 현재 capacity로 표시한다. 60초가 지나면 offline이다. 폐기·만료·누락·오류일 때 예시 데이터로 대체하지 않는다. CPU 0%와 메모리 사용량 0도 그대로 보존한다. 미수집 GPU·디스크는 null이다.

서버 역할 `192.168.45.99`, 실제 원격 Node `192.168.45.225` 1대와 배정 Node ID를 확인했다. 16 논리 코어·약 7.68 GiB는 Node가 관측하는 Linux 환경이며 일반 작업에 제공 승인된 자원은 0이다. 사용자 Run도 0건이다.

API는 `127.0.0.1:18082/pilot/v1/overview`에만 읽기 서비스를 연다. Vite `/pilot` proxy를 사용하고 비밀 값·서명·업로드·임의 파일·작업 mutation을 제공하지 않는다. 회사 SSO나 일반 제품 API의 인증을 우회해 업무 기능을 노출하지 않는다.

기존 `3000` 포트의 이 저장소 Vite PID 25764를 command line으로 확인한 뒤 종료했다. 새 worktree Vite PID 13816으로 같은 포트에 실제 화면을 반영했다. PACS의 별도 5173/8000 서비스와 기존 8080 업무 서비스는 중지하지 않았다. Node.js Public TCP 방화벽 허용 규칙은 기존 그대로다. `Start-LiveConsole.ps1`로 기존 DB·observer·console·web을 재사용하는 실행을 확인했다. Windows 부팅 자동 시작이나 인증서 자동 갱신을 구현했다고 표시하지 않는다.

## 검증 증거

| KST / 명령·범위 | 결과 |
|---|---|
| 00:22 `lan_console.py --state <기존 state> --once` | exit 0; 실측 Node 1개, online, runs 빈 목록, offered 빈 값, gate true |
| 00:28 `pytest tests/core/test_lan_console.py tests/core/test_lan_execution.py tests/core/test_lan_worker_config.py tests/core/test_lan_pki.py -q` | exit 0; 38 passed, 0.94초 |
| 00:28 `npm test --prefix apps/web` | exit 0; 19 files, 94 tests passed |
| 00:28 `npm run build --prefix apps/web` | exit 0; TypeScript 및 Vite 6.4.3 build |
| 00:25 preview 3001, 00:28 실제 3000 Edge/Playwright 검사 | exit 0; 실제 Node ID/count, 주기 조회, 메뉴·안내·light theme·390px 너비·키보드, 503 후 화면 제거·자동 복구, 빈 목록에 예시 없음, page error 0 |
| 00:29 `Start-LiveConsole.ps1` | exit 0; 실행 중 서비스 재사용 및 접속 주소 출력 |
| 00:31 `check_docs.py`, `check_ontology.py`, `git diff --check`, PowerShell parser | exit 0; 문서/계약/구문 검증 |

브라우저의 정상 조회는 실제 DB/mTLS 데이터를 사용했다. 503과 빈 목록은 브라우저 응답 주입으로 UI만 검증한 것으로, 실제 Node 장애·작업 복구 시험과 구분한다. 로컬 증거는 `.work/lan-pilot/browser-verification.json`, `live-dashboard.png`에 있다. 일반 사용자 계정의 인증·Workspace·전체 Run/Evidence 여정 합격을 주장하지 않는다.

## 실제 원격 실행·복구 시험 준비와 남은 단계

공개 worker bundle에 `Enable-ExecutionTests.ps1`, `worker_execution.py`, 지정 `/probe`와 `inv-supervisor` 이미지가 추가됐다. byte 비교·공개 파일 16종만 포함·이미지 layer/config 검증을 완료했다. 전달 SHA-256 `f9167bb15402dffc3ba00dc08e8effca7bf0cf4124229ba39f0931240cc3cdd1`, 12,936,139 bytes. 기존 Node image·키·journal·volume을 유지하며 관측 container는 멈춘 backup으로 남긴다. 생성 실패 시 기존 container를 다시 시작한다. 시험 Node에만 로컬 Docker socket을 연결하고, 실행되는 작업에는 socket/사용자 폴더/네트워크를 주지 않는다.

`lan_execution.py`는 운영자 CLI 전용 Node 구성요소 시험이다. 서명된 합성 acceptance claim/allocation 식별자를 사용하며 DB의 실제 사용자 승인·Lease·Evidence를 만들었다고 주장하지 않는다. 입장 claim이 없는 독립 파일럿 tenant만 허용하며 시험 동안 gate를 열고 finally에서 다시 닫는다. 각 실행 전 현재 gate·Node 상태·channel을 재검사한다. 작업은 CPU 500 millis, RAM 64 MiB, nonroot UID, read-only rootfs, PID 64, 네트워크 없음, 고정 `/probe`이며 3~10초 제한이다. 출력·stop receipt identity·SHA-256과 종료 결과를 확인한다. timeout 시험은 단순한 nonzero exit로 통과시키지 않는다.

격리, stdout/stderr, exit 7 실패 감지, 3초 timeout/정리, 송신 프로세스 exit 17 이후 새 프로세스의 observation-only 영수증 회복을 준비했다. 마지막 복구는 duplicate와 원래 영수증의 동일성을 확인해야 통과한다. 시험 보고서는 원자 교체하며 실제 결과만 콘솔에 표시한다.

**현재 미수행:** 상대 PC의 `Enable-ExecutionTests.ps1` 실행 완료와 수신 image ID가 아직 전달되지 않았다. 따라서 원격 실제 작업·복구 시험은 실행하지 않았고 보고서도 없다. Node는 여전히 `lan-observe-v1`로 관측 중이다. 화면의 ‘대기 중’은 이 상태를 반영한다. 다음 담당은 사용자 상대 PC의 준비 실행 → Codex 수신 image 확인 및 실제 시험 수행·결과 기록이다. 사용자 지시의 실제 시험 목표가 아직 남아 있으므로 완료 상태로 올리지 않는다.

## 오류·CI·인계

오류와 해결은 [[2026-09-10_LAN-BOOTSTRAP_오류와해결]] 11~14번에 분리 기록했다. 별도 Edge 프로필과 Playwright 1.63.0으로 검증했으며 기존 브라우저·세션을 사용하지 않았다. 자동화용 의존성은 무시된 로컬 도구 폴더에만 설치했다.

00:32:11 KST 동일 구현 SHA의 [Frontend 34496216664](https://github.com/egparadise/SaintVision-Invion/actions/runs/34496216664), [Core 34496216668](https://github.com/egparadise/SaintVision-Invion/actions/runs/34496216668), [Backend 34496216671](https://github.com/egparadise/SaintVision-Invion/actions/runs/34496216671), [Docs 34496216666](https://github.com/egparadise/SaintVision-Invion/actions/runs/34496216666)는 기존 계정 결제/지출 제한 때문에 job 시작 전에 차단됐다. 계정은 사용자 지시대로 변경하지 않았다.

사용 안내: [[2026-09-11_LAN-LIVE_사용안내]]. Claude 독립 검토, Gemini 실제 API/로그인/Workspace UI 인계 및 CI 계정 문제는 pending이다. 운영 화면은 기존 주소에 반영했지만 저장소 main으로 병합한 것은 아니다. 00:33:25 KST check/apply/check exit 0, 신규 3개 export 및 전체 298개 hash 일치, pending/conflicts 0을 확인했다. 이 결과와 오류 링크를 추가한 본문도 같은 state로 동기화한다. 로컬 Obsidian 사본 검증이며 OneDrive 클라우드 업로드 증거는 아니다.
