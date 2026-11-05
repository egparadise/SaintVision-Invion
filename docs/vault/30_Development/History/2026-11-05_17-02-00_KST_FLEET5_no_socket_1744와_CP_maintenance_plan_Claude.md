---
doc_id: "HISTORY-FLEET5-20261105-NO-SOCKET-1744-CP-MAINTENANCE-CLAUDE"
title: "2026-11-05 FLEET5 no-socket test 1744 검토와 CP Docker maintenance 기술 조건·staged plan"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T17:02:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "d7a4e450"
task_ids: ["FLEET5-FIRST-WAVE-PLAN-20261105"]
tags: ["fleet5", "independent-review", "docker-desktop", "maintenance", "control-plane", "claude"]
---

# no-socket test 1744 검토와 CP maintenance plan

Orca task `task_4a4927d2b60d`, dispatch `ctx_55be7bd3f015`. 판정은 둘이고 **따로** 적는다.

- **A. source:** Codex `17447988d631cb575fbe7d04e28c5dd7e0e9774e`(test-only delta, branch `agent/codex/fleet5-storage-workspace-guard-20261105`, 부모 `f40c3805`)
- **B. plan:** CP Docker Desktop 4.16.3 → 4.98.0 maintenance의 기술 release 조건과 staged script·rollback checklist. **실행하지 않았다.**
- 검토 시각: 16:41~17:02 KST
- 하지 않은 일: install, stop, backup, OS 변경, elevation, 인증 시도, data 변경, payload 열람, r5·pin·automation·registry·board 변경
- 기계 판독 결과: `Evidence/fleet5-20261105-claude/no-socket-1744-cp-maintenance-review.json`
- 앞선 기록: [[2026-11-05_16-36-00_KST_FLEET5_DB_readiness_84bb_source검토_Claude]], [[2026-11-05_15-33-00_KST_FLEET5_first_wave_22fa3628_검토와_Docker_target_Claude]]

## A. no-socket test delta 1744 — ACCEPT (source), hosted Core pending

**무결성**

- `tests/core/test_lan_workspace_upgrade.py` blob `f4ccf241`, sha256 `ca86b49e5c1be86273ceeb550e3e44fd2b1a7db4ffebc26b943d7544b244273d`. relay 값과 같다.
- `deploy/lan/worker_workspace.py` blob `c1e51ddb`, sha256 `83930f4d40be82ba211ba57ea9e8c13218a3f8217cf6d13ae4d6b127536e5b7d`. ff97(087에서 ACCEPT)과 **같다**. helper는 바뀌지 않았다.
- 부모 `f40c3805`는 ff97 기준 docs만 바꿨다. 1744의 non-docs 변경은 이 test 파일 한 개, 6행 추가와 1행 삭제다.

**내용**

- 기존 plain upgrade test에 `socket_mounted` parametrize(`with-socket`, `state-only`)를 더했다. 세 profile과 곱해 6 case다.
- `state-only` case는 현재 container의 `Mounts`를 첫 항목(state mount)만 남긴다. 그 뒤 backup container의 `Mounts`가 원래와 같은지(`original_mounts`)까지 확인한다.

**이번 bytes로 내가 직접 한 확인** (앞선 34 case 검토 결과를 재사용하지 않았다)

- 1744 export, main `.venv` Python 3.14.7, `-B`: test 파일 **33 passed**(17:01 KST에 다시 실행해도 같다).
- mutation probe: `validate_install_target`의 `return args` 앞에 `if sockets != 1: raise`를 넣으면 `state-only` 3 case가 **fail**하고 나머지 30은 pass한다. 원본은 `ww.orig`에서 되돌렸다. 즉 새 case는 "socket 없는 설치를 받아들인다"는 동작을 실제로 지킨다.

**hosted**

- Docs 41988236953(`17447988`): **success**
- Core 41988233523(`17447988`): 17:00:20 KST에 **in_progress**. Codex가 보고한 focused 104 pass, 0 skip은 그쪽 측정값으로 기록만 했다. 이 판정에 Core success는 들어 있지 않다.

## B. CP maintenance — 기술 release 조건

### 이전 조건 철회

앞선 기록의 "Nov 8~10 follow-up이 모두 terminal 결과를 낸 뒤"라는 조건을 **철회한다**. 그 조건은 r5가 Docker에 의존한다는 증거 없이 시간으로 막는 것이었다. 실제로 확인해 보니 의존하지 않는다(아래 pin 점검).

### pin 점검 결과 (actual 106 pin + 6 executable)

- r5 `pilot_guard.py`(`acf8b4f6`), config `pilot-config.private.json`(`ca684b45`), `release-parameters.actual.json`(`d46ddd2a`)을 읽었다.
- 실행 파일 6개: r5 reviewed-source `.venv`의 `python.exe`, OpenSSH `ssh.exe`·`scp.exe`, `powershell.exe`, `node.exe`, `git.exe`
- cycle-plan pin 106개(`{path, sha256}`): 104개는 `supervision-codex-20261104/.work` 아래, 2개는 C:의 Python314 `python.exe`·`python314.dll`
- **Docker나 WSL 경로·문자열은 0개다.** r5 Cycle은 Docker를 쓰지 않는다. Docker upgrade 때 r5 쪽에서 바뀌거나 멈추는 pin은 없다.

### 새 조건 (모두 기술 상태이며, 날짜가 아니다)

maintenance는 아래가 **시작 직전과 종료 직후에 모두** 참일 때만 한다.

1. **진행 중인 r5 작업 없음:** active attempt, latch, `lock`, `lock.guard`, completion-unknown, orphan intent, 살아 있는 Cycle child process가 모두 0
2. **시간:** 작업 전체가 세 run window(Nov8 14:20–18:32, Nov9 12:15–16:27, Nov10 08:00–12:12 KST)와 grace 밖이다. 권고 기준은 "다음 window 시작 2시간 전까지 post-check 끝"이다. 오늘(Nov 5) 시작하면 여유가 3일 가까이 된다.
3. **follow-up 3건:** enabled 상태와 pin이 바뀌지 않는다. 확인 대상은 config `ca684b45`, parameters `d46ddd2a`, guard `acf8b4f6`, 106 pin 전체, 6 executable hash, private state hash의 전후 일치다.
4. **session:** Windows 재부팅, logoff, 사용자 전환, session 변경이 없다. `sessionId=1`, logon time, boot time의 전후가 같다.
5. **r5 runtime:** 18082 overview에서 두 Node가 전후 모두 fresh다. `127.0.0.1` listener 18082(python), 3000(node), 55448(ssh)이 전후 모두 같은 process로 떠 있다. 외부 PG는 건드리지 않는다.

### 16:57~16:58 KST read-only 측정 (내가 CP에서 직접)

| 항목 | 값 |
|---|---|
| Docker Desktop | all-users 설치, `C:\Program Files\Docker\Docker`, 4.16.3.96739. per-user 설치는 없음 |
| 권한 | 현재 process는 비승격. Administrators SID가 "deny only"로 들어 있다(UAC 분리 token). `EnableLUA=1`, `ConsentPromptBehaviorAdmin=5`, `PromptOnSecureDesktop=1`, `AutoAdminLogon=0` |
| session | `sessionId=1`, `docker-users` 구성원 |
| listener | 18082 python, 3000 node, 55448 ssh, 모두 `127.0.0.1`. 15408은 없음 |
| 55440 | `com.docker.backend`(예전 node1 pilot DB container). 양방향 established 연결 0 |
| 서비스 | `com.docker.service` Running/Automatic |
| WSL | 2.4.12.0. pending reboot 표시 없음 |
| VHDX | `%LOCALAPPDATA%\Docker\wsl\data\ext4.vhdx` 74,746,691,584B, `…\wsl\distro\ext4.vhdx` 5,654,970,368B, `docker_data.vhdx`는 없음(4.16 배치) |
| 여유 공간 | C: 296.8GB, D: 1,616.6GB. 사본 두 개 합계 약 80.4GB는 D:에 들어간다 |
| 참고 | 그 순간 free physical memory 약 496MB였다. gate는 아니지만 사본 작업 때 다른 부하를 줄인다 |

root가 전달한 값(내가 다시 재지 않음): 두 installer(4.98.0.245422, 4.16.3.96739)를 staging했고 SHA와 Authenticode(Docker Inc)가 유효하다. LanmanServer는 Auto/Running이다. `rootAdmin=false`이고, full rollback은 아직 불가하다. 16:41 물리 재확인 결과도 기록만 한다(1번·2번 SSH 0, Docker 1.52/1.56, group true. 저장된 SSH 계정 3개는 inviz가 아니며 group false, Docker denied. 사용자가 준 inviz key login은 3번에서 거부됐다. 4번은 mDNS 결과가 없고 inventory가 비어 있다. `sudo -n` firewall query는 모두 interactive authentication required다).

## B. 공식 문서 기준 사실

- **4.98.0**(build 245422, 2026-11-03): installer SHA256 `cd6273d9…4388`, Engine 29.x(API 1.56, 최소 1.40). 요구사항은 Windows 11 23H2(22631) 이상, WSL 2.1.5 이상이다. CVE-2026-112917 수정에는 WSL 3.0.3 이상이 필요하다.
- **설치 flag:** `install`, `--quiet`, `--accept-license`, `--backend=wsl-2|hyper-v|windows|docker-vmm`, `--installation-dir=<path>`(기본 `C:\Program Files\Docker\Docker`), `--always-run-service`, `--no-windows-containers`, `--wsl-default-data-root`, `--admin-settings`, `--allowed-org`, proxy flag, `--user`(per-user)
- **mode:** all-users 설치와 update에는 admin이 필요하다. 문서에 "mode를 바꾸려면 uninstall 후 reinstall"이라고 되어 있다. 그래서 `--user`는 in-place upgrade가 아니라 mode 전환이다.
- **재부팅:** Docker 문서는 설치 뒤 Docker Desktop이 자동 시작하지 않는다고 한다. installer가 재부팅을 요구하지 않는다는 보장은 문서에 없다. 다른 admin 계정으로 설치할 때 사용자를 `docker-users`에 넣으라는 안내는 있다. 이 계정은 이미 구성원이다.
- **WSL:** Docker 문서와 Microsoft 문서 모두 `wsl --install`/`wsl --update`를 "administrator mode"로 실행하라고 하고 "restart를 요구할 수 있다"고 쓴다. 비승격 `wsl --update`가 되는지는 문서로 확인하지 못했다.

## B. admin 인증과 project 동의는 다르다

- 이 계정은 Administrators 구성원이지만 UAC 분리 token으로 돈다. `ConsentPromptBehaviorAdmin=5`이고 secure desktop prompt가 켜져 있다. 따라서 승격은 **PC 앞의 사람이 secure desktop에서 UAC 동의를 누르는 일**이다(password 입력이 아니라 동의 클릭이다).
- agent는 secure desktop을 조작할 수 없다. 조작해서도 안 된다.
- 사용자나 root의 "진행하라"는 project 동의다. 그것이 승격된 token을 만들지는 않는다. 따라서 `rootAdmin=false`인 동안 all-users upgrade는 실행할 수 없다.

## B. 해결되지 않은 정확한 gate

| id | gate | 해소 조건 |
|---|---|---|
| G-a | all-users in-place upgrade에 실제 승격 필요 | 사용자가 attended 상태에서 installer 실행 시 UAC 동의 1회 |
| G-b | per-user(`--user`) 경로는 all-users uninstall을 먼저 해야 함 | 받아들이지 않는다. VHDX 사본 없이 uninstall하면 data distro를 잃을 위험이 있다 |
| G-c | WSL 3.0.3 update에 admin 필요, restart 요구 가능 | 승격 1회. restart를 요구하면 **그 자리에서 멈추고 미룬다**(조건 4). 대안: WSL을 2.4.12로 둔 채 Docker만 올린다. 설치 최소(2.1.5)는 넘지만 CVE 수정은 미완으로 기록한다 |
| G-d | 비승격 Ubuntu 등록은 문서로 증명 안 됨 | Docker Desktop은 Ubuntu가 필요 없다. 이번 maintenance 범위에서 뺀다. 필요하면 별도 attended 확인 |
| G-e | installer가 재부팅·sign-out을 요구하지 않는다는 보장 없음 | attended 실행에서 prompt가 나오면 거절하고 중단한다. exit code와 prompt 유무를 기록한다 |
| G-f | 복원 경계 미확보 | Docker 정지(quiesce) 후 두 VHDX를 D:에 복사하고 hash로 맞춘다. 4.16.3 서명 installer를 보관한다. 정지와 복사는 실행 승인이 따로 필요하다 |

"남은 follow-up이 다 끝날 때까지 기다린다"는 조건은 더 쓰지 않는다. 막는 것은 위 G-a, G-c, G-e, G-f뿐이다.

## B. 영향 범위

- r5 Cycle, tunnel, overview, 외부 PG는 Docker와 무관하다(pin 점검 기준).
- Docker를 멈추면 다른 제품 container 7개(coco-annotator 2, saint-control 5)와 55440 예전 pilot DB가 함께 멈춘다. Saintview는 실행 중 0, 종료 3이다. payload는 열지 않는다. 이름과 상태만 기록한다.
- upgrade 뒤 Engine 29가 data를 바꿀 수 있다. 그 뒤로는 4.16.3/Engine 20.10으로 되돌릴 때 VHDX 사본이 **유일한** 복원 경로다.

## B. staged script (실행 금지 초안, service action 없음)

아래 script는 **읽기 전용 pre-check와 post-check만** 들어 있다. 정지, 복사, 설치는 operator가 손으로 하는 단계로 남기고 주석으로만 적었다. 경로는 placeholder다. 실제 host 값은 private `.work`에 둔다.

```powershell
# F5-CP-DOCKER-MAINT staged check v1 — read-only; run unelevated before AND after
param([Parameter(Mandatory)][string]$Out, [string]$Installer, [string]$OldInstaller)
$ErrorActionPreference = 'Stop'
$r = [ordered]@{ at = (Get-Date).ToString('o') }
$r.session = (Get-Process -Id $PID).SessionId
$r.boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('o')
$r.listeners = Get-NetTCPConnection -State Listen -LocalAddress 127.0.0.1 |
  Where-Object LocalPort -in 18082,3000,55448 |
  ForEach-Object { '{0}:{1}' -f $_.LocalPort, (Get-Process -Id $_.OwningProcess).ProcessName }
# r5 gates: attempt/latch/lock/lock.guard/completion-unknown/orphan intent/live child must all be 0
# (paths from the private r5 config; abort if any exists)
# pins: recompute sha256 of 106 cycle-plan pins + 6 executables + config/parameters/guard/private-state
# and compare with the recorded baseline; abort on any difference
# overview: GET http://127.0.0.1:18082 overview, both Nodes fresh; abort otherwise
$r.docker = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Docker Desktop').DisplayVersion
$r.containers = docker ps --format '{{.Names}}|{{.Status}}'   # names/status only, no payloads
$r.wsl = (Get-AppxPackage MicrosoftCorporationII.WindowsSubsystemForLinux).Version
foreach ($f in $Installer, $OldInstaller) { if ($f) {
  $s = Get-AuthenticodeSignature $f
  $r["inst:" + (Split-Path $f -Leaf)] = @((Get-FileHash $f -Algorithm SHA256).Hash, $s.Status, $s.SignerCertificate.Subject) } }
$r | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 $Out
# --- operator-only steps, NOT in this script (each needs explicit go + attended):
# 1 quit Docker Desktop; wait for com.docker.backend exit; `wsl --list --running` shows no docker distros
# 2 copy both ext4.vhdx to D:\<backup>\ ; Get-FileHash source == copy
# 3 elevated (UAC consent): Start-Process $Installer -Wait -ArgumentList 'install','--quiet','--accept-license','--backend=wsl-2'
#   do not pass --user; record ExitCode; any restart/sign-out prompt -> decline, stop, record G-e
# 4 optional elevated `wsl --update`; any restart request -> stop, keep 2.4.12, record G-c
# 5 start Docker Desktop unelevated; then run this script again and diff with the pre file
```

## B. rollback checklist

**시작 전에 모두 참이어야 한다**

- [ ] pre-check JSON이 있고, 조건 1~5가 모두 참이다.
- [ ] 4.98 installer hash가 `cd6273d9…4388`이고 Authenticode가 Valid(Docker Inc)다. 4.16.3 installer도 Valid다.
- [ ] 두 VHDX 사본의 hash가 원본과 같다(G-f 해소).
- [ ] 사용자가 PC 앞에 있고 UAC 동의를 할 수 있다(G-a).
- [ ] post-check까지 마치고도 다음 window 시작 2시간 전이다.

**중단 조건 (하나라도 나오면 즉시 멈춘다)**

- restart나 sign-out prompt(거절한다)
- installer ExitCode가 0이 아님
- r5 listener, overview, pin이 하나라도 바뀜
- 새 r5 attempt, lock, child가 생김

**post-check (모두 참이어야 끝낸다)**

- [ ] `docker version`의 server API가 1.56, Desktop이 4.98.0이다.
- [ ] session과 boot time이 pre와 같다.
- [ ] listener 3개가 같은 process 이름이다. overview에서 두 Node가 fresh다.
- [ ] 106 pin, 6 executable, config·parameters·guard·private state hash가 모두 pre와 같다. follow-up 3건이 enabled다.
- [ ] 다른 제품 container의 이름 목록이 pre와 같다(restart policy가 없는 것은 해당 제품 owner에게 넘긴다).

**되돌리기 (Engine이 뜨지 않거나 data가 맞지 않을 때)**

1. Docker Desktop을 끝낸다.
2. 승격해서 4.98을 uninstall한다.
3. 보관한 4.16.3 서명 installer로 all-users 재설치한다.
4. VHDX 사본을 원래 위치로 되돌리고 hash를 확인한다.
5. Docker를 시작하고 post-check를 다시 한다.
6. r5 조건 3~5가 깨졌으면 Docker 작업과 상관없이 r5 쪽 사고로 다루고 root에게 올린다.

## 따로 추적하는 것

- S1(연속 정상 rotation이 막힐 수 있음, Medium)은 이 plan과 별개다. root가 Codex fix를 따로 배정한다. 두 번째 renewal 전에 닫아야 한다.
- FLEET5 worker 계정, SSH, firewall `sudo` 문제는 root의 새 admin target 정보를 기다린다. 나는 인증이나 재시도를 하지 않았다.

## 판정

- **A:** `17447988` test-only delta **ACCEPT**(source, 내 33 pass, mutation이 잡힘). hosted Core 41988233523은 pending이다.
- **B:** plan **ACCEPT-AS-PLAN**. 기술 조건 1~5와 staged check, rollback checklist가 준비됐다. **실행 가능 판정은 아니다.** G-a(실제 UAC 동의)와 G-f(VHDX 사본)가 풀려야 실행할 수 있다. G-c와 G-e는 attended 실행 중 중단 규칙으로 다룬다.

## 다음 첫 행동과 담당

- **root:** Core 41988233523 결과를 확인한다. B plan을 반영한다. 사용자에게 attended session(UAC 동의 가능, window 밖)을 잡을지 묻고, 그 전에 quiesce와 VHDX 사본의 실행 승인을 받는다.
- **사용자(PC 앞):** step 3의 UAC 동의 1회. restart prompt는 거절한다.
- **Claude:** 실행 결과(pre/post JSON diff, ExitCode)가 오면 검토한다.
