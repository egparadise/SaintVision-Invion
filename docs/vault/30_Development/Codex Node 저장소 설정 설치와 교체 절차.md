---
doc_id: "RUNBOOK-STORAGE-POLICY-001"
title: "Codex Node 저장소 설정 설치와 교체 절차"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T15:24:08+09:00"
source_of_truth: "Git"
---

# Node 저장소 설정 설치·교체 절차

이 절차는 f9d69a8의 Go Linux Node `--storage-policy`와 기존 private journal을 사용한다. Windows PC에서는 Docker/WSL의 Linux Node에 적용하며 Windows 네이티브 파일 수집 지원과 다르다. 현재 LAN Start-Worker/start-node 패키지는 이 옵션과 제공 폴더 mount를 자동 구성하지 않는다. 운영 bundle 수정·허용 폴더 입력·원격 적용은 후속이다.

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
