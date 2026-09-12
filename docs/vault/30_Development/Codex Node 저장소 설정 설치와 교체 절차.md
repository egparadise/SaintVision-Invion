---
doc_id: "RUNBOOK-STORAGE-POLICY-001"
title: "Codex Node 저장소 설정 설치와 교체 절차"
version: "1.4.0"
status: "review"
author: "Codex"
updated: "2026-09-12T16:41:40+09:00"
source_of_truth: "Git"
---

# Node 저장소 설정 설치·교체 절차

이 절차는 f9d69a8의 Go Linux Node `--storage-policy`와 기존 private journal을 사용한다. Windows PC에서는 Docker/WSL의 Linux Node에 적용하며 Windows 네이티브 파일 수집 지원과 다르다. 9848afb부터 LAN Start-Worker/start-node는 새 컨테이너에 명시적 제공 폴더와 policy hash를 받아 읽기 mount/설정/시작 기록 검증을 수행한다. 기존 컨테이너 교체·원격 Windows/WSL 적용은 후속이다.

## 설치 전 확보할 값

현재 tenant/node/epoch, Control Plane이 등록한 node channel/version/endpoint/certificate SHA256, contribution_id와 root_version, 소유자가 허용한 실제 제공 폴더와 Node 내부 읽기 경로가 필요하다. DB의 Windows 호스트 경로를 Linux 컨테이너 내부 경로로 그대로 복사하지 않는다. root_version은 임의로 만드는 숫자가 아니라 서버의 현재 contribution 버전과 일치해야 한다. 등록 소유자·정규화 경로 변경 시 서버와 로컬 설정을 함께 조율한다.

NodeStorageRootConfig의 `channel`, `contribution_id`, `root_version`, `root`를 보호 파일에 기록한다. Node는 그 파일을 `--storage-policy`로 명시한 경우만 활성화한다. 제공 폴더는 기존 사용자 파일을 보존하고 최소 읽기 권한으로 mount한다. 키/journal/다른 사용자 폴더/전체 디스크를 제공 폴더로 선택하지 않는다. 기존 Node identity/key/journal을 새로 만들거나 제거하는 방식으로 설치 오류를 우회하지 않는다.

## 통제된 교체

1. 기존 Node 이름·image·identity/epoch·journal volume·허용 폴더와 현재 설정 파일 bytes/hash를 확인하고 보존한다. 실행 중 작업의 중단 조건과 drain은 기존 운영 계약을 따른다.
2. 같은 contribution의 폴더 경로 변경은 서버 contribution의 root_version을 앞으로 올려 조율한다. 인증 채널 변경은 channel.version을 앞으로 올린다. 두 버전은 각각 역행할 수 없으며 한쪽 증가로 다른 쪽 감소를 정당화하지 못한다. 같은 버전에서 해시가 바뀌는 설정은 거부된다. 숫자만 올려 권한을 얻을 수 없고 서버의 현재 값과 일치해야 한다.
3. Node가 정지된 상태에서 검토된 정확한 policy 파일과 읽기 mount를 교체하고 기존 journal을 연결해 시작한다. live 파일 수정은 현재 sampler의 hash 검사에서 거부되며 자동 재적용되지 않는다.
4. 시작 시 현재 TLS 인증서/키·정체성·pin과 읽기 root를 확인하고 journal floor를 file sync→rename→directory sync로 기록한다. 처음 만드는 항목은 기존 exclusive create와 sync를 사용한다. 같은 설정 재시작도 directory sync를 확인한다. 실패·손상은 자동 초기화하지 않는다.
5. stdout JSON의 listening 및 storagePolicy를 수집한다. tenantId/nodeId/recoveryEpoch와 policySha256·contributionId·rootVersion·channelVersion을 승인 설정/배포 기록과 대조한다. rootSha256는 UTF-8 경로 bytes의 hash, channelSha256는 Go struct JSON 표현의 hash다. 서로 다른 JSON pretty-print를 같은 exact policy bytes로 취급하지 않는다.
6. **이 출력은 서명되지 않은 로컬 시작 확인이며 운영 인수가 아니다.** 서버의 실제 mTLS 호출·현재 DB challenge·서명 sample·Evidence/StorageCheck commit 및 인증 GET 조회를 확인해야 한다. 원격 workload7개 시험·readiness/schedulable 전환은 별도다.

## 거부·복구

NODE-0061은 낮아진 root/channel 버전, 같은 버전의 다른 경로/채널/정확한 bytes, 손상/잘못된 journal 항목을 의미할 수 있다. 실패한 교체가 floor에 기록되기 전이라면 마지막 수락된 정확한 파일로 복구할 수 있다. 새 floor가 기록된 뒤 listen 등 후속 시작 단계가 실패했다면 옛 버전으로 되돌리지 말고 기록된 버전 이상에서 원인을 해결한다. 파일·디렉터리 sync 실패는 성공 기록으로 바꾸지 않는다.

journal에는 contribution별 최소 버전이 남아 다른 contribution을 선택해도 옛 floor를 삭제하지 않는다. 프로세스의 journal lock을 유지하고 시작 시에만 갱신한다. 전체 journal 삭제/백업 롤백이나 호스트 관리자에 의한 변조까지 방지하는 hardware monotonic counter는 아니다. 전원 장애·디스크 손실·복원 후 epoch 조율은 기존 복구 계약으로 별도 인수해야 한다.

다음 담당: Codex 운영 bundle의 명시적 읽기 mount·설정 전달/교체 receipt 확인 자동화, 원격 운영자 실제 허용 폴더/설치, Claude 독립 검토, Gemini local receipt와 서버 인수/현재 health unknown 구분.


## 새 컨테이너 설치 입력 (9848afb)

승인된 storage-policy.json을 bundle 옆에 놓고 root=/contribution, 현재 tenant/node/epoch/channel/기여 버전 및 인증서 pin을 맞춘다. exact bytes SHA256은 별도로 확인한다. Windows 관리자 PowerShell의 Start-Worker.ps1에 기존 -CertificateSHA256 외에 -StorageSource 'D:\SaintVision-Provided' -StoragePolicySHA256 <확인한64자리hash>를 함께 전달한다. 예시 경로는 사용자가 허용한 실제 폴더로 바꿔야 한다. 기존 컨테이너가 있으면 이 경로는 거부되므로 삭제하여 우회하지 않는다.

start-node.sh는 Linux 경로와 policy hash 두 인수를 받고, storage-ready.json에 최소 로컬 기록을 남긴다. 이 파일은 Windows 다운로드 폴더가 아니라 WSL private worker 디렉터리에 있다. 오류 시 journal/키/volume을 보존한다. 서버 검증 전 연결 완료/스케줄링 가능으로 표시하지 않는다. 현 시험은 Linux Docker 설치2개이며 Windows launcher 실제 실행은 미검증이다.

다음 첫 행동: Codex 기존 Node 통제된 교체 및 forward 재개 자동화. Claude ADR-093 독립 검토 pending.


## 기존 Node 읽기 전용 사전 점검 (823b4b8)

검토된 새 storage-plan.json을 준비한 Linux private worker 디렉터리에서 `python3 worker_replacement.py preflight storage-plan.json > replacement-preflight.json`으로 점검하고 `python3 worker_replacement.py recheck storage-plan.json replacement-preflight.json`으로 현재 상태를 다시 대조한다. 실행 중이면 거부하며 이 명령이 Node를 정지하지 않는다. clean exited 관측 Node 전용이다. 실패 컨테이너를 정리하는 수단이 아니다.

결과에 키/파일 원문은 없으며 최대16MiB state를 검사한다. 용량 초과는 자동 생략하지 않고 거부한다. replacementAuthorized=false인 로컬 점검 결과이며 삭제 명령에 대한 승인이 아니다. 점검 후 변경을 원자적으로 차단하는 lock/fence는 후속 교체 executor에서 구현해야 한다. 실제 Windows/WSL/원격 적용은 미수행이다. 다음 Codex durable 교체 단계·forward 재개 구현, Claude ADR-094 검토 pending.


## 정지 Node의 교체·재개 CLI (f766146)

검토한 기존 private worker 디렉터리(소유자 일치/0700)에서 새 storage-plan.json과 교체 전 replacement-preflight.json을 사용한다.

```bash
python3 worker_replace.py storage-plan.json replacement-preflight.json > storage-replace-ready.json
```

실패/중단하면 같은 명령과 같은 두 입력으로 재개한다. storage-replacement.json과 .storage-replace.lock, 보존 컨테이너, 상태 volume을 삭제하지 않는다. plan 변경/손상된 기록은 자동 초기화하지 않는다. 기존 Node는 정상 종료된 lan-observe-v1이어야 하며 이 도구가 실행 중 Node를 자동 정지하지 않는다. 원본 image가 로컬에 있고 새 image는 plan manifest의 filesystem/config 검증을 통과해야 한다.

기존 컨테이너는 이름이 변경되고 restart=no로 남는다. 새 컨테이너도 restart=no이며 JSON은 서버 mTLS 검증 대기 상태다. old 컨테이너는 shared volume을 보므로 독립 데이터 백업으로 취급하거나 수동 재시작하지 않는다. 정책의 버전 floor 이후 실패는 옛 정책으로 되돌리지 않는다. 다른 정책이 필요한 경우 운영자/서버와 forward 버전 계획을 다시 조율해야 한다.

이 명령은 Linux에서 시험했다. Windows/WSL wrapper 및 실제 원격 설치는 다음 Codex 범위, Claude ADR-095 독립 검토 pending이다.

## Windows 진입점 (e512b60)

검토된 새 worker bundle에 현재 서버 등록값과 맞는 storage-policy.json을 포함한다. 기존 Node가 정상 정지된 관측 프로필인지 먼저 확인한다. 아래 경로와 hash는 운영자가 허용한 실제 폴더/정책 값으로 바꿔야 한다. 진입점이 실행 중 Node를 자동 정지하거나 방화벽을 변경하지 않는다.

```powershell
$svScript = Join-Path $env:USERPROFILE 'Downloads\SaintVision-LAN\worker\Replace-Storage.ps1'
$svSource = 'D:\SaintVision-Provided'
$svPolicyHash = '<독립적으로 확인한 정책 SHA256>'
$svPrepared = & $svScript -StorageSource $svSource -StoragePolicySHA256 $svPolicyHash
$svPrepared
# 준비 결과를 확인한 후 같은 입력으로 실행. 중단 시 이 Apply를 반복한다.
& $svScript -StorageSource $svSource -StoragePolicySHA256 $svPolicyHash -Apply -RequestSHA256 $svPrepared.requestSHA256
```

request hash는 WSL 기존 Node 폴더의 storage-replacement-input/request.json exact bytes에 묶인다. 다음 세션에는 같은 prepare를 다시 호출해 기존 hash를 받을 수 있다. 이것은 새 preflight를 수행했다는 의미가 아니며 apply에서 기존 상태/복구 기록을 대조한다. source/policy 변경은 기존 요청에 덮어쓰지 않는다. 새 컨테이너는 restart=no/서버 검증 대기다.

실제 원격 Windows/Ubuntu 경로는 아직 인수하지 않았다. Ubuntu 누락, daemon mount Source 차이, 서버 버전 불일치를 우회하지 말고 기록을 보존한다. 다음 Codex 실제 PC 경로/receipt/mTLS·Evidence 연결, Claude ADR-096 독립 검토 pending.
