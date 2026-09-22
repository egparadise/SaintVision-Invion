---
doc_id: "ADR-100"
title: "ADR-100 CP 호스트의 Node 겸임과 5노드 측정 경계"
version: "1.0.0"
status: "accepted"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T03:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["ADR", "five-node", "control-plane", "co-location", "S05", "S07", "measurement-bias"]
---

# ADR-100 CP 호스트의 Node 겸임과 5노드 측정 경계

## 상태와 결정

2026-09-23 사용자 결정으로 토폴로지 B를 채택한다. 한 Windows 물리 호스트가 Control Plane을 실행하고, 같은 호스트의 Docker Desktop Linux VM에서 실행 Node 1개를 겸임한다. 별도 Ubuntu 물리 호스트 4대가 실행 Node 4개를 제공한다.

따라서 이 랩의 정직한 수량 표기는 다음과 같다.

| 항목 | 수량 | 의미 |
|---|---:|---|
| 등록 실행 Node identity | 5 | 서로 다른 `nodeId`·인증서·epoch을 갖는 스케줄 대상 |
| 실행 Node 물리 호스트 | 5 | Windows 호스트 1대 + Ubuntu 호스트 4대; Docker VM을 별도 물리 호스트로 세지 않음 |
| Control Plane에서 독립적인 실행 호스트 | 4 | Ubuntu 4대. Windows의 겸임 Node는 CP와 전원·CPU/RAM·storage·NIC·host clock·Docker Desktop 장애 영역을 공유 |
| CP와 상관된 실행 Node | 1 | Windows CP 호스트의 Docker Desktop Linux Node |

이 구성을 “5개의 독립 Control Plane 장애 영역” 또는 “CP와 독립적인 worker 5대”라고 부르지 않는다. 모든 결과에는 `registeredNodeCount=5`, `cpIndependentWorkerHostCount=4`, `cpColocatedNodeCount=1`을 함께 기록한다.

## 선택 이유와 registry 기준

현재 S05/S07 registry의 “5대” 기준은 스케줄링·identity·certificate·epoch 경계를 가진 **등록 실행 Node 5개**를 요구하는 것으로 유지한다. 겸임 Node도 별도 Node identity와 mTLS 인증서, heartbeat, offer, lease, fencing 경계를 가지므로 실행 토폴로지의 다섯 번째 Node다. 따라서 `docs/task-registry.json`의 S05-DB·S07-DB 상태, acceptance ID, evidence 요구와 5대 기준은 변경하지 않는다.

반면 Node 수는 Control Plane 장애 독립성이나 성능 표본 독립성을 자동으로 뜻하지 않는다. 이 ADR은 registry 기준을 낮추지 않고 증거 manifest에 상관 관계를 추가한다. 5개 Node가 모두 online인 topology preflight와, CP와 독립적인 Ubuntu 4대만 쓰는 수용 지표를 한 evidence bundle에 분리한다.

## S05 배치 성능 측정 규칙

Windows 겸임 Node는 CP와 자원을 공유한다. loopback·짧은 네트워크 경로 때문에 빠르게 보일 수도 있고 CPU/RAM/disk/NIC/Docker VM 경합 때문에 느리게 보일 수도 있으므로 방향이 정해진 보정값을 적용할 수 없다.

1. `all-five topology smoke`에서는 5개 Node의 등록·mTLS·heartbeat·resource snapshot·Explain 도달성을 확인할 수 있다. 이는 기능 smoke이며 P95 수용 표본이 아니다.
2. S05의 20/50 동시 timed wave에서는 겸임 Node를 candidate와 지연 분모에서 제외한다. inventory의 `measurementEligible.s05=false`, `exclusionReason=cp-host-colocation`을 읽어 실행 전에 cordon 또는 offer 0을 적용하고 Explain에서 선택되지 않았음을 확인한다. 결과를 만든 뒤 샘플만 사후 삭제하는 방식은 금지한다.
3. timed wave의 manifest와 JUnit에는 `eligibleNodeCount=4`, `excludedNodeCount=1`, 제외 Node의 공개 identity·host/failure-domain ID와 `coLocatedWithControlPlane=true`를 남긴다. P95·결정성·timeout·lock-hold는 Ubuntu 4대 표본으로만 계산한다.
4. reviewer가 five-node topology preflight와 four-CP-independent-worker timed wave를 함께 대조하기 전에는 AC-05 판정 자료가 아니다. 통과하더라도 “다섯 Node가 모두 P95 부하를 처리했다” 또는 “독립 worker 5대 P95”라고 쓰지 않는다.
5. 겸임 Node를 포함한 별도 비교 wave가 필요하면 결과 이름에 `biased-all-five`를 붙이고 acceptance 분모와 합치지 않는다.

## S07 감지·복구 측정 규칙

Windows 호스트 전체 장애는 Node 1개뿐 아니라 Control Plane observer도 함께 잃는다. 그러므로 같은 CP가 재기록한 시간으로 이 장애의 감지 지연을 측정하면 관측 공백을 숨길 수 있다.

1. AC-07의 기본 이탈 감지·복구율 반복은 Ubuntu 4대를 대상으로 한다. 20회라면 Node별 5회로 균등 배분하고 겸임 Node는 감지 지연과 복구 성공률 분모에서 제외한다.
2. 매 반복 전 5개 등록 Node의 online·epoch·certificate·heartbeat를 확인하되, disruption target은 `measurementEligible.s07=true`인 Ubuntu Node만 허용한다.
3. Docker Desktop의 Node 컨테이너만 정지하는 시험은 `colocated-node-process-loss`로 별도 기록할 수 있다. 이는 독립 물리 호스트 이탈이 아니며 기본 95% 분모에 넣지 않는다.
4. Windows 물리 호스트 전체를 내리는 시험은 `correlated-cp-node-host-loss`다. 외부 monotonic observer 또는 별도 CP가 사전에 준비되지 않았다면 감지 시간과 복구율은 `UNMEASURED`이고 도구는 exit 3을 내야 한다.
5. 겸임 Node 결과와 Ubuntu 결과를 한 P95/성공률로 합산하지 않는다. stale write 0, fencing/epoch 단조성 같은 안전 불변식은 두 분류 모두에서 별도로 검사할 수 있다.

## inventory와 증거 필드

revision이 고정된 inventory의 각 Node에는 최소한 다음 공개 메타데이터가 필요하다.

- `nodeId`, public certificate fingerprint, `hostId`, `failureDomainId`, OS/profile, immutable image digest
- `coLocatedWithControlPlane`
- `measurementEligible.s05`, `measurementEligible.s07`, `exclusionReason`
- NTP source/offset/sync state와 network endpoint의 비밀 없는 식별 정보

Windows CP와 Docker Desktop Node의 시각 관측은 둘 다 남기되 서로 독립적인 NTP 표본 2개로 세지 않는다. 겸임 Node도 다른 Node의 인증서·private key를 재사용하면 안 된다. private key·DSN·token·원문 credential은 inventory와 artifact에 넣지 않는다.

## 영향과 위험

- 장점: 사용자 보유 장비로 등록 Node 5개를 구성하면서 CP와 겸임 Node의 공유 자원 편향을 감추지 않는다.
- 비용: S05/S07 수용 지표의 실질 부하·장애 표본은 CP 독립 Ubuntu 4대이고, 겸임 Node에는 별도 smoke·상관 장애 분류가 필요하다.
- 남는 위험: Windows/Docker Desktop의 CPU·메모리·디스크·NIC contention이 CP 자체를 흔들 수 있다. Ubuntu 대상 wave에서도 CP 지연이 커질 수 있으므로 CP host utilization과 throttling을 동일 timeline에 기록한다.
- 구현 영향: 제품·HTTP·오류 계약, migration, task registry에는 변경이 없다. inventory-bound lab adapter·workflow·artifact schema가 아직 미구현이므로 본 ADR만으로 AC-05/07이 통과하지 않는다.

## 롤백

겸임 Node가 CP 안정성을 해치거나 증거 분리가 불가능하면 해당 Node를 cordon하고 등록·identity 이력을 보존한 채 실행 대상에서 비활성화한다. 이때 랩은 “CP + Ubuntu 4대의 4-Node pilot”로 강등하며 5노드 acceptance를 주장하지 않는다. 이후 별도 Ubuntu 호스트를 다섯 번째 실행 Node로 추가하면 새 inventory revision과 인증서로 topology preflight를 다시 수행한다.

## 현재 확인 범위

이 ADR은 토폴로지와 측정 경계를 정한 docs-only 결정이다. 5개 Node의 실제 등록·online, inventory-bound runner, 20/50 동시 물리 부하, Node 이탈 20회, P95·60초·95% 판정은 아직 실행하지 않았다. 첫 Ubuntu 파일럿 준비 상태는 History에서 provenance를 구분해 기록하며 이 문서가 운영 인수를 대신하지 않는다.
