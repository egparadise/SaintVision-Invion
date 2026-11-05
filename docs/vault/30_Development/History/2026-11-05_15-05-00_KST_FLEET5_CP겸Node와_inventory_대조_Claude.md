---
doc_id: "HISTORY-FLEET5-20261105-CP-INVENTORY-CLAUDE"
title: "2026-11-05 FLEET5 CP 겸 Node와 inventory 대조 (읽기 전용 발견·배치 계획)"
version: "1.0.1"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T15:22:10+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "9b9061ed"
task_ids: ["FLEET5-20261105-CP-AND-INVENTORY"]
tags: ["fleet5", "five-node", "control-plane", "co-location", "inventory", "docker", "claude"]
---

# FLEET5 CP 겸 Node와 inventory 대조

카드 FLEET5-20261105-CP-AND-INVENTORY. 작업은 Claude가 맡고 검토는 Codex root가 한다. Orca task `task_b69ab83fb879`이며 부모 착수 기록은 [[2026-11-05_기존5대_오케스트레이션_착수_Codex]]다. 대상은 사용자가 확정한 Linux 4대(SaintVision-Invion1~4)와 현재 Windows PC(CP 겸 Node)다. 이 카드는 **읽기 전용 발견과 배치 계획**만 다룬다. Node 등록, 자원 부여, 디스크 pool, 계정·trust·CA·SSH 변경, Docker 업그레이드·재시작·다운로드는 하지 않았다. 원격 장비에는 접속하지 않았고 진료·고객 데이터도 열지 않았다.

- base `9b9061ed`(부모 coordinator branch와 같은 tip), product source `59f0a3c2`, report `f020a664`.
- 읽은 문서: AGENTS.md, INDEX-PROGRESS-001 v1.0.393, WORKBOARD-CLAUDE-001 v1.2.126, GUIDE v1.1.0, ADR 정정 v1.37.0, GOV-AGENT-001 v1.1.3, GOV-GIT-001 v1.1.4, 연속 실행 정책 v1.1.0, agent-delivery 1.1.0, [[ADR-100 CP 호스트의 Node 겸임과 5노드 측정 경계]] v1.0.0, `deploy/lan/README.md`, `tools/five_node_lab_preflight.py`, `tools/s01_readiness_preflight.py`.
- 관측 시각: 2026-11-05 14:40~14:56 KST(v1.0.1 정정: 파일명의 15-05는 표지일 뿐 관측 시각이 아니다), Windows PowerShell 5.1과 Git Bash. 기계 판독용 결과는 `Evidence/fleet5-20261105-claude/cp-inventory-readiness.json`이다. 원래 주소·hostname·컴퓨터 이름은 비공개 `.work/fleet5-20261105-claude/cp-inventory-private.json`에만 있다(sha256 `a7fe8615…712e`).

## 1. inventory 대조

`.work/intranet/inventory.json`(sha256 `b8e93435…edb1d`, topology `cp-colocated-plus-four-workers`)에 저장소의 S01 `lint_inventory`를 오프라인 함수로 실행했다(repo `.venv` CPython 3.14.7, 함수 실행 exit 0). 결과는 **BLOCKED `inventory-values-missing`**이고, 누락 74개·무효 0개다. 칸별 누락은 다음과 같다. 1~3번은 각 2개(`certificateSHA256`, `profile`), 4번과 5번은 각 34개(identity·OS·hardware·capacity·allowedResources·folders·NTP·storageRole 전체). 1·3번의 빈 `allowedFolders`는 `storageRole=none`이라 무효가 아니다.

1~3번의 `nodeId`는 2026-09-30 `lan-pilot-6fc0428b-v2` state의 ID다. 현재 r5 state의 ID가 아니므로 **과거 논리 ID**로만 취급한다. 새 namespace에서는 새 ID를 발급받는다.

사용자 그림의 이름과 inventory 칸의 대응은 다음과 같다. 3번은 OS hostname으로 일치를 확인했다. 1번은 hostname 접두만 같아 그럴 가능성이 있는 정도다. 2번은 hostname에 맞는 토큰이 없어 미증명이다. 4번은 프로젝트 증거가 없다. 원격 화면이 online으로 보이는 것은 Node 등록 증거가 아니다.

SSH alias InvizMain/DrSaint/inviz-api/saint_label/webpacs는 접속 없이 설정 파일만 비교했다(`~/.ssh/config` sha256 `b955ad43…f8e`). 다섯 개 모두 공인 주소(RFC1918 아님)이며, inventory의 IP·hostname이나 worker subnet과 하나도 맞지 않는다. 따라서 SaintVision worker가 아니며 손대지 않았다.

**worker4 탐색 결과.** 다음 위치를 범위를 정해 찾았다: `.work/intranet`, `.work/lan-5node`의 모든 state(node1, r2~r5), `.work/lan-pilot`, repo `deploy/`와 `docs/vault`, Orca host 목록과 설정 JSON, ssh config, known_hosts. 어디에도 worker4의 주소·identity·자원 profile이 없다. 9월 28일 실측 초안도 "4번째 PC 미등록"이라고 적었다. known_hosts에는 inventory에 없는 worker subnet의 ed25519 항목이 하나 있다. 이 PC의 주소가 아니고 어떤 프로젝트 state도 참조하지 않는다. **후보일 뿐 worker4 증거가 아니며** 접속하지 않았다. 사용자에게 같은 질문을 다시 하지 않았다.

## 2. CP 물리 identity와 Docker

**관측된 CP.** 이 PC가 CP 호스트라는 근거는 세 가지다. README에 적힌 LAN server 주소가 이 PC에 할당돼 있다. 모든 lan-5node state가 그 주소를 serverIP로 쓴다. r5의 serve 18082, web 3000, DB tunnel 55448이 이 PC에서 listening 중이다. 장비는 Windows 11 Pro build 26300 workgroup, i7-12700(12코어/20스레드), RAM 15.77GB, RTX 3080이다. 표본 시각의 free physical memory는 **0.55GB**였다. 디스크 여유는 C: 276.6GB, D: 1.5TB다. 시간대는 KST다. `w32tm /query /source`는 권한 없이 0x80070005로 거부돼 **시간 동기 상태는 미확인**이다. hosts 파일에는 `cp.sv.lan` 항목이 없다. inventory 5번의 nodeId·hostId·failureDomainId는 아직 없다.

**Docker 재측정**(모든 명령 exit 0): `DOCKER_HOST/CONTEXT/API_VERSION/CERT_PATH/TLS_VERIFY`는 모두 설정돼 있지 않다. `default` context와 `desktop-linux` context는 둘 다 npipe로 같은 서버에 붙는다. 서버는 **Docker Desktop 4.16.3, Engine 20.10.22, API 1.41(min 1.12)**, linux/amd64, WSL2 kernel 5.15이고 client도 20.10.22/1.41이다. 따라서 문제는 client나 env override가 아니라 **실제 서버 비호환**이다(설치기 요구 1.45). 그 밖의 값: VM NCPU 20, Mem 6.2GB(`.wslconfig` memory=6GB), overlay2, cgroupfs **v1**. WSL 2.4.12의 distro는 `docker-desktop`과 `docker-desktop-data`뿐이며, **`Ubuntu` distro는 없다**. `Prepare-Worker.ps1`과 `Start-Worker.ps1`은 `wsl -d Ubuntu`를 호출한다. 다른 지원 runtime(podman, nerdctl, Rancher, Docker가 있는 다른 WSL distro)은 **없다**. 원격 Docker를 CP의 물리 runtime으로 세지 않는다.

**영향 범위**(이름·개수만, payload는 보지 않음): container 25개(running 8), image 146개(52.2GB), volume 83개(8.2GB), build cache 5.0GB, WSL data vhdx 69.6GB. compose project별로 coco-annotator 2/4, saint-control 5/6, saint-label-workstation 0/4, saintview 0/3, training-workstation 0/2, dev-env 0/1(running/전체)이다. saintview는 진료 영상 stack이라 열어 보지 않았다. 프로젝트 소유로 증명된 것은 `ai.saintvision.pilot` label이 붙은 옛 node1 pilot DB 1개(running, 55440)뿐이다. 이름만 프로젝트이고 label이 없는 dev PG 1개는 exited 상태다. 나머지는 다른 제품이다.

## 3. 계약과 CP 경로

[[ADR-100 CP 호스트의 Node 겸임과 5노드 측정 경계]]과 `five_node_lab_preflight.validate_five_node_inventory`가 요구하는 조건은 다음과 같다. 5번은 고유한 nodeId·인증서·IP·hostId를 가져야 한다. `hostId == controlPlaneHostId`, `coLocatedWithControlPlane=true`, `measurementEligible={s05:false,s07:false}`, `exclusionReason=cp-host-colocation`이어야 하고 겸임 Node는 최대 1개다. 독립 4대는 s05/s07이 true이고 exclusionReason은 null이어야 한다. dry-run 합격 조건은 5개 모두 ready, colocated 1, eligible 4다. S05 timed wave는 4대 표본만 쓰고 겸임 Node는 사전에 cordon하거나 offer 0으로 둔다. 사후 삭제는 금지다. S07은 Ubuntu 4대만 대상으로 한다. 겸임 Node를 다루는 시험은 `colocated-node-process-loss`로 따로 기록한다. Windows 전체를 내리는 시험은 외부 observer가 없으면 `correlated-cp-node-host-loss`이며 `UNMEASURED`(exit 3)다. 모든 결과에는 `registeredNodeCount=5`, `cpIndependentWorkerHostCount=4`, `cpColocatedNodeCount=1`을 적는다. CP를 두 번 세지 않는다.

**CP 전제 매트릭스**

| 항목 | 상태 | 관측 |
|---|---|---|
| Linux Docker server API ≥ 1.45 | FAIL | 1.41 |
| 1.45를 내는 Engine | FAIL | 20.10.22. Engine 26.0+가 필요하다. README와 설치기 문구의 "Engine 25+/Desktop 4.27+"는 부족하다(Engine 25는 API 1.44). 정확한 Desktop 버전은 공식 release note로 확인한다 |
| WSL2 Linux containers | PASS | wslEngine true, Windows containers false |
| `Ubuntu` WSL distro | FAIL | 없음 |
| Ubuntu WSL integration | UNKNOWN | 기본 distro integration은 켜져 있고 명시 목록은 비어 있다. distro 생성 후 다시 확인 |
| Node 주소가 Windows에 있음 | PASS | — |
| 관리자 PowerShell(Start-Worker 방화벽 규칙) | 이 task에서 권한 없음 | — |
| 시간 동기 증거 | UNKNOWN | w32tm 접근 거부 |
| 겸임 Node 자원 여유 | RISK | VM 6GB 상한, 표본 시 host free 0.55GB |
| 5번 allowedResources/Folders/storageRole | 사용자 결정 | null |
| 5번 nodeId/cert/hostId/failureDomainId와 ADR-100 제외 필드 | 미배정 | 새 namespace init에서 생성 |
| vhdx 백업 공간 | PASS | 69.6GB, D: 1.5TB 여유 |

**가장 작은 안전 경로(제안이며 실행하지 않음).** 지원되는 runtime이 이 PC에 실제로 없으므로, 아래는 격리된 준비·업그레이드 제안이다.

1. 시점(v1.0.1 정정): 달력 시각이 아니라 상태로 판단한다. 모든 예약 시도가 정산되고, 살아 있는 child와 unknown completion이 없고, 세 pin과 r5 health가 정상이어야 한다. 세부 조건은 [[2026-11-05_15-25-00_KST_FLEET5_worker_readiness_독립검토_Claude]]에 있다. r5 DB는 외부 SSH tunnel 방식이라 local container가 없지만, 설치기가 logoff나 재부팅을 요구하면 r5 process(python/node/ssh)와 Orca 후속이 멈춘다.
2. 실행 경계(v1.0.1 정정): 기존 프로젝트 승인은 유지되며 일반 동의를 다시 묻지 않는다. 실제 경계는 세 가지다. 첫째, 설치·방화벽·`wsl --install`에 OS 관리자 권한이 필요하다. 둘째, Docker Desktop을 종료하면 running 8개가 멈추고 그중 7개가 다른 제품이라 유지보수 조율이 필요하다. 셋째, WSL data를 이전하기 전에 백업해야 한다. 진료 stack은 열지 않는다.
3. 사전 기록: 같은 명령으로 container 25개의 이름·상태·project, volume 83, image 146, `docker version`, r5 health(listener 3개, 2Node fresh)와 Orca 후속 3개를 다시 기록한다.
4. 보존: Docker Desktop을 종료한다. 이때 running 8개가 멈추므로 다른 제품 owner에게 미리 알린다. 다음으로 `%LOCALAPPDATA%\Docker\wsl\data\ext4.vhdx`(69.6GB)와 `distro\ext4.vhdx`, `%APPDATA%\Docker\settings.json`을 D:의 날짜별 백업 폴더로 복사하고 크기와 sha256을 기록한다. 삭제·prune·export는 하지 않는다.
5. 업그레이드: Engine 26 이상(API ≥ 1.45)을 공식 release note로 확인한 Desktop 버전으로 올리고 WSL2 backend는 유지한다. 4.16에서 올리면 `docker-desktop-data` 배치가 바뀔 수 있으므로 해당 버전 note의 data migration 항목을 먼저 읽는다. 그 다음 `wsl --install -d Ubuntu`로 distro를 만들고 Ubuntu integration을 켠다. Ubuntu 안에 `openssl`, `python3`, `curl`, `unzip`을 설치한다.
6. 사후 health: `docker version`이 API ≥ 1.45이고 Min ≤ 1.45여야 한다(node-agent는 1.41~1.45로 협상하고 최대 1.45를 쓴다). container·volume·image 개수와 이름이 사전 기록과 같아야 한다. `ai.saintvision.pilot` DB가 running이어야 한다. r5 listener·2Node fresh·Orca 후속 3개가 변하지 않아야 한다. `wsl -d Ubuntu -- docker version` 결과도 같아야 한다.
7. 롤백: downgrade는 공식 지원 경로가 아니다. 실제 롤백은 Desktop을 재설치하고 백업 vhdx를 복원하는 것이다. 4.16.3 설치 파일이 오프라인에 보관돼 있는지는 **미확인**이며 업그레이드 전에 차단 항목으로 확인한다.
8. 자원: 겸임 Node의 allowedResources는 VM 6GB 안에서 다른 container와 CP를 함께 고려해 사용자가 정한다. 설정하지 않으면 5번은 등록 smoke로만 쓰고 offer는 0으로 둔다.

## 4. r5 보존과 새 namespace

r5는 지금 살아 있다. listener는 18082 python, 3000 node, 55448 ssh이고 databaseMode는 `ssh-tunnel-external`이다. Orca 후속 3개를 다시 읽었다(`orca automations list --json` exit 0). 모두 enabled이며 next는 11-08 14:20, 11-09 12:15, 11-10 08:00 KST이고 lastRun은 없다. 최종 증거 `r5-final-enabled-schedules.json`(sha256 `779332f6…ea57`)의 ID·시각과 같다. 같은 목적의 Windows 예약 작업은 없다. 나는 Run now, Cycle, Transition, Recovery, precheck 우회, 일정이나 pin 변경을 하지 않았다.

이미 쓰고 있는 port는 download 18081/18084/18085/18086/18105, node 18443/18445/18446/18447/18505, db 55440/55447/55448이다. 새 5Node 실행은 아래처럼 계획한다.

- state는 `.work/lan-5node/f5-59f0a3c2-<rand8>`, DB는 `saintvision_lan_f5_<rand8>`로 하고 `prepare-pilot-database.sh`와 `verify-pilot-database.sh`로 role을 분리한다. download와 node port는 위 집합 밖에서 고르고, init 직전에 CP와 각 worker에서 비어 있는지 확인한다.
- 같은 state에서 `init`을 한 번만 실행한다. `--node-ip`에 4대와 CP 주소를 모두 넣고 `--allow-server-node-colocation`을 준다. image는 `59f0a3c2` 정확한 archive를 Linux worker에서 `Dockerfile.node.remote`로 build하고 `bundle --prebuilt-image --prebuilt-inspect`로 묶는다(로컬에는 Go가 없다).
- worker1·2에는 r5 Node가 있다. 새 identity의 Node container는 11-10 후속이 정산된 뒤에 추가한다. r5의 container·key·port·volume은 건드리지 않는다. worker3·4는 전제 측정이 끝나는 대로 먼저 진행할 수 있다.

## 5. Linux Node 구성·공유 방법 (현재 저장소 기준)

Linux에서는 Windows용 `.ps1`을 쓰지 않는다. 아래는 README의 Ubuntu 절차를 그대로 정리한 것이다. Ubuntu 외 배포판은 저장소에 실측 증거가 없으므로, 같은 명령이 있는지 직접 확인하는 조건부 경로다.

**전제(관측 단계).**
1. 필요한 명령: `bash`, `openssl`, `python3`, `docker`, `timeout`, `curl`, `unzip`, `sha256sum`, `timedatectl`. Ubuntu에서는 apt로 설치하고, 다른 배포판은 각 패키지 관리자로 같은 명령을 갖춘다.
2. Docker Engine 26 이상과 서버 API 1.45 이상이 필요하다. `docker version --format '{{.Server.APIVersion}}'`로 확인하고 배포판별 Docker 공식 문서로 설치한다. 1~3번은 docker 29.x로 기록돼 있다.
3. 설치 계정이 Docker socket을 쓸 수 있어야 한다. worker3는 현재 socket 0660에 접근하지 못한다. docker group에 넣는 것은 root와 같은 권한을 주는 일이므로 그 장비 관리자의 별도 권한이 필요하다.
4. `timedatectl show -p NTPSynchronized --value`가 `yes`여야 한다.
5. 예약된 고정 IPv4가 있어야 한다. 이 namespace의 node port 인바운드는 CP 주소에서만 허용하고(host firewall 또는 `DOCKER-USER`), 다른 출발지는 거부되는지 확인한다. CP의 download port로 가는 아웃바운드는 bootstrap 동안만 연다.

**등록.** CP가 `bundle`에서 출력한 Node별 SHA-256은 신뢰된 경로로 받는다.

```bash
curl --fail --output worker.zip http://<CP_LAN_IP>:<DOWNLOAD_PORT>/worker.zip
sha256sum worker.zip                 # 별도 경로로 받은 값과 비교
unzip worker.zip -d saintvision-worker && cd saintvision-worker
bash prepare-worker.sh               # 로컬 Ed25519 키 생성, 공개 CSR만 출력
```

CSR만 CP에 보내고, CP는 `lan_pilot.py --state <f5-state> enroll --csr ...`를 실행한다(외부 CA 옵션 포함). 그 다음 worker에서 아래를 실행한다.

```bash
curl --fail --output node-cert.pem http://<CP_LAN_IP>:<DOWNLOAD_PORT>/node-cert.pem
printf '%s  node-cert.pem\n' '<operator-sha256>' | sha256sum --check -
bash finish-worker.sh                # start-node.sh는 직접 부르지 않는다
```

완료 기준은 CP의 `status`와 `observe --once`에서 그 Node ID가 online이고, 자기 인증서·epoch·heartbeat와 현재 resource snapshot이 보이는 것이다. container가 실행 중이거나 ping이 된다는 것만으로는 완료가 아니다.

**공유(별도 단계).** 폴더 공유는 등록·관측과 따로 한다. 이 pilot은 workload, workspace mount, offer, project grant를 만들지 않는다. 폴더를 공유하려면 **새 Node container를 처음 만들 때** 다음처럼 실행한다.

```bash
bash finish-worker.sh <absolute-folder> <storage-policy-sha256>
```

이때 CP가 발급한 `storage-policy.json`(contribution_id `stc_…`, 그 Node channel에 결속)을 같은 폴더에 둔다. 폴더는 `/contribution`에 read-only로 mount된다. 이미 있는 Node에는 이 방법을 쓸 수 없고 통제된 교체 절차가 필요하다. 루트 경로, `/mnt/<drive>`, symlink, private state 하위 폴더는 거부된다. 자원 offer와 grant는 사용자가 inventory의 `allowedResources`/`allowedFolders`를 정한 뒤 CP 쪽에서 별도로 기록한다.

## 6. 발견(검토 요청)

- Low(문서): `prepare-worker.sh`의 BLOCKED 문구와 README 123/222/230행은 Docker의 하한을 "Engine 25+/Desktop 4.27+"로 적었다. 실제 검사는 API 1.45이고 Engine 25는 1.44를 낸다. README 124행이 이미 이 문제를 언급한다. 정정은 owner(Codex/Claude) 카드로 넘긴다. 이 task에서는 바꾸지 않았다.
- 관측: 5번 Node 계획의 자원 위험(host free 0.55GB)과 cgroup v1 VM은 이후 resource snapshot 정확도와 ADR-100의 CP 경합 기록에 영향을 준다.

## 7. 인계

| 다음 행동 | 담당 |
|---|---|
| worker4 주소와 SSH 사용자(진행 중인 사용자 질문의 답) | root/사용자 |
| 1~4번 `hostnamectl`로 그림 이름과 칸 대응 확정, `docker version` API, `timedatectl`, nproc/mem/disk, 후보 port 비어 있음 확인(읽기 전용) | Codex 운영 worker |
| worker3 docker socket 접근 권한, 5번 allowedResources/Folders | 장비 관리자/사용자 결정 |
| CP Docker Desktop 업그레이드·Ubuntu WSL: 상태 기반 해제 조건, OS 관리자, 다른 제품 유지보수 조율, vhdx 백업과 rollback 자산(v1.0.1 정정) | root(조율), Codex/Claude(오프라인 계획 검토) |
| 위 측정 후 f5 inventory revision 초안과 Codex 실행 계획의 독립 검토 | Claude |
| f5 init/bundle/enroll과 dry-run preflight 실행 | Codex(Claude 검토) |

원래 48-task 상태(2 done/4 blocked/42 planned/0 ready)와 VF-CL 0/5는 바꾸지 않았다. 이 기록은 5Node 등록이나 운영 인수가 아니다. 공통 진행판, task-registry, Obsidian apply도 바꾸지 않았다.
