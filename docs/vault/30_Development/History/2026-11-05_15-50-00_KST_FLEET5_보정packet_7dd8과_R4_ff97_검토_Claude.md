---
doc_id: "HISTORY-FLEET5-20261105-PACKET7DD8-R4FF97-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 Codex 보정 packet 7dd8fa95와 R4 source ff97cd9e 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T15:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "300f4bca"
task_ids: ["FLEET5-FIRST-WAVE-PLAN-20261105", "FLEET5-STORAGE-WORKSPACE-GUARD-20261105"]
tags: ["fleet5", "independent-review", "five-node", "pki", "firewall", "workspace", "claude"]
---

# 보정 packet 7dd8fa95와 R4 source ff97cd9e 독립 검토

Orca task `task_5fd9ea4e3779`, dispatch `ctx_ac008a621cfe`. coordinator가 relay한 두 대상을 15:43~15:50 KST에 검토했다.

1. Codex 보정 packet: commit `7dd8fa95cd1683780b2b1c713366290e9aeb180c`, branch `agent/codex/fleet5-first-wave-plan-20261105`
2. Codex R4 source: commit `ff97cd9ef01bf9aebda3313cd90631c247a9f63a`, branch `agent/codex/fleet5-storage-workspace-guard-20261105`, 같은 dispatch 중 `msg_807c70188e00`로 받음

판정은 **plan 판정과 source 판정으로 나누어** 적는다. 이번에 한 일은 정적 검토, hash 재계산, `59f0a3c2` source 대조, scratchpad에서 R4 새 test 파일 한 개와 내 probe 4개 실행뿐이다. 실제 Docker, 원격 접속, sudo, 설치, 인증 시도는 하지 않았다. 기계 판독 결과는 `Evidence/fleet5-20261105-claude/packet7dd8-r4ff97-review.json`에 있다. 앞선 기록은 [[2026-11-05_15-33-00_KST_FLEET5_first_wave_22fa3628_검토와_Docker_target_Claude]]다.

## 앞선 CP target 보고의 정정 (추가 기록)

`300f4bca`에는 "engine을 재시작하면 다른 제품의 container 7개(임상 Saintview 포함)가 멈춘다"고 적었다. 이 문장은 틀렸다. 내가 측정한 `cp-inventory-readiness.json`에 따르면 실행 중인 다른 제품 container 7개는 **coco-annotator 2개와 saint-control 5개**다. Saintview는 **실행 0개, 정지 3개**다. 따라서 업그레이드로 멈추는 대상은 coco-annotator와 saint-control의 실행 중 container다. 실행 중인 Saintview가 멈춘다고 말하면 안 된다. 그 밖에 project pilot label이 붙은 옛 node1 pilot DB 1개도 실행 중이다. 원래 문서는 덮어쓰지 않았다. root는 policy와 quota를 혼동한 Low 문제를 `805c6760`에서 이미 고쳤다. 앞선 보고서에 적은 "다운로드하지 않음"은 그 task의 범위였을 뿐이다. 사용자가 금지한 것도 아니고, 새로 포괄 승인을 받아야 한다는 뜻도 아니다. root가 공식 설치 파일의 bytes, hash, 서명을 실행하지 않은 상태로 따로 준비해 두는 것과도 충돌하지 않는다.

root는 `msg_6fc3a8af3ffc`(15:52 KST)에서 두 설치 파일을 모두 실제로 받아 두었다고 알렸다. root가 보고한 값은 다음과 같다(**root 관측, Claude 미검증**):

- 공식 checksum 일치
- Authenticode Valid / Docker Inc
- version 4.98.0.245422와 4.16.3.96739
- LanmanServer Running/Auto
- currentAdmin false
- 실행하지 않음, full rollback 불가(VHDX와 복원 수단 없음)

이 값은 내 `300f4bca`의 "4.16.3 공식 정책상 미보장, 서명 미확인, LanmanServer 미측정" 단계를 대체한다. CP 운영 준비 판정(업그레이드는 별도 승인, full rollback 불가)은 바뀌지 않는다.

## A. 보정 packet 7dd8fa95 (plan 판정)

### 무결성

- 공개 plan blob: `5121cb834016ebf86fd7433bcca3c3c89446374965a05f71a069158afe44d35f`
- 비공개 vector: `bee0f0f86c4fe6cca05aac476a21ce9f5693d43303dae932969ab1c35b7dc8e7`
- 비공개 parameter: `a806685a72b3ad6c5f43206d4f2619309d2f76403a3db7fe0b574b44aba04984`
- 원래 59f archive: `a9f0a3b8…`, 바뀌지 않음
- cap-probe Dockerfile: `f9f6424c6bde6cdd92357975ac9dd020f9c4fb44e27de84107ac97e3c4574c1f`

모두 receipt와 일치한다. vector 13단계는 모두 `executed: false`다.

### P1~P8 (exact bytes 기준)

| ID | plan 판정 | 확인한 근거 | 실행 checkpoint로 남는 것 |
|---|---|---|---|
| P1 | **해결** | `intranet_pki.py init-node-mtls`(59f CLI에 실재)가 새 hierarchy를 만든다. root 유효기간은 3650일, intermediate는 1095일이다. init, enroll, renewal vector는 모두 `--ca-key`, `--ca-key-password-file`, `--ca-chain`을 넘긴다. 59f의 `ensure_pilot_pki`는 이 경우 `caMode=external-intermediate`로 설정한다. issuing key를 state에 복사하는 것과 chain이 다른 것은 거부한다. 기본 7일 self-signed CA로 돌아가는 경로는 없다. | 생성된 key·chain hash와 NotAfter. root key는 암호화된 채로 online CA 폴더에 있다. 이 점은 문서도 `rootOffline=false`로 인정한다. |
| P2 | **vector는 해결, 설치는 BLOCKED** | DOCKER-USER에 넣는 규칙은 다음과 같다. 정확한 Node IP와 `--ctorigdst`/`--ctorigdstport 18515`를 조건으로 한다. CP는 RETURN, 다른 출발지는 tcp-reset REJECT다. comment tag를 붙이고, `-C`로 먼저 확인하며, flush는 하지 않는다. rollback은 정확히 그 규칙만 지운다. `start-node.sh:45`가 port를 IPv4 Node IP에만 publish하므로 IPv6로 우회할 경로는 없다. w1/w2에서 `sudo -n`이 auth-required였다는 것은 Codex가 측정한 값이며, 나는 sudo를 다시 시도하지 않았다. | 권한 있는 operator가 규칙을 실제로 설치하고, CP 성공과 worker3 거부를 동시에 보여야 한다. **새 Low:** 규칙이 host 재부팅이나 firewall 재적재 뒤에 유지된다는 보장이 없다. 재부팅 뒤 다시 증명하거나, 검토된 영속화 방법이 있어야 ingress 증명이 유지된다. |
| P3 | 해결(plan) | probe가 cgroup v1과 v2를 모두 처리한다(memory 1073741824, cpu 200000/100000). 실제 RUN의 HostConfig도 확인한다. client timeout은 daemon 종료를 증명하지 못한다는 계약과 GOPROXY/GOSUMDB 기록이 들어 있다. | 실제 cap 증명. 없으면 abort한다. |
| P4 | 해결(plan) | `PG_MAJOR=16`은 Codex가 측정했다. migration 전에 새 container 안에서 `SHOW server_version_num`을 실행해 160000~169999인지 확인한다. password는 stdin으로 넘긴다. | 실제 server 값 |
| P5 | 해결, 남은 Low | vector에 `r5-reviewed-source` 경로는 0번 나온다. Windows의 python 단계는 모두 `-B`를 쓴다. SSH 단계는 아직 r5의 `known_hosts.pinned`를 읽기 전용으로 쓴다(StrictHostKeyChecking=yes, UpdateHostKeys=no). | F5 전용 복사본을 hash로 고정해 쓰거나, 사용 전후 hash가 같은지 확인한다. |
| P6 | 해결(plan) | 옛 state 10개를 catalog로 만들어 tenant/epoch/ID/CA가 겹치지 않음을 확인하는 gate가 있다. | 생성된 값이 겹치지 않음 |
| P7 | 해결 | vector에서 `workspaces` 0번, 파일 제거됨 | — |
| P8 | 해결 | 제외 구간 계산을 검증했다. 시작 시각 + 600s + 14520s = +4h12m, 따라서 14:20→18:32, 12:15→16:27, 08:00→12:12다. | 구간 안에서는 F5를 시작하지 않는다. |

History 문구 Low:

- step 4가 아직 "existing pinned Python"이라고 적는다(vector는 non-r5 main `.venv`).
- step 5의 bundle 명령에 `-B`가 빠져 있다(vector에는 있다).

실행 bytes에는 영향이 없다.

### 지금 해도 되는 단계와 막힌 단계

- **plan 자체:** 실행하지 않는 plan으로서 받아들일 수 있다.
- **시계와 무관하게 안전한 준비 단계:**
  - 01~02: 새 폴더 준비와 archive SCP
  - 03: worker2의 loopback 전용 새 PG16 생성과 server version gate
  - 07: worker1 cap-probe와 image build
  - 04b: 새 external CA 생성. root와 intermediate는 수명이 길다.
  - 모두 r5 제외 구간 밖에서, owner가 지켜보는 상태로 해야 한다.
- **시계가 시작되는 단계:** 05 init은 CP control leaf와 peer policy의 6일 만료 시계를 시작한다(`lan_pki.issue` 기본 6일, `lan_pilot.py:844`). 09 enroll은 Node leaf의 6일 시계를 시작한다. renewal은 NotAfter 48시간 전에 해야 하고 활성 Node의 CSR이 필요하다. 그래서 init/enroll은 **P2 operator 일정이 약 4일 안으로 확정된 뒤에** 하는 것이 맞다. 그러지 않으면 Node가 설치되기 전에 만료될 수 있고, 그때는 fully-expired recovery 경로로 가야 한다.
- **BLOCKED:** `finish-worker.sh`/start-node가 18515를 LAN에 publish하는 설치와 acceptance observe. scope가 정해진 operator 규칙과 증명이 있을 때까지 막혀 있다.

### 2개 Node에서 FIVE로 가는 실제 경로 (59f source 기준)

**membership은 바뀌지 않는 것이 아니다. 같은 F5 state에 `init`을 다시 실행하는 것이 59f에서 지원하는 확장 경로다.** 새 namespace를 만들거나 다시 init할 필요는 없다.

- **근거:**
  - `tools/lan_pilot.py` `init`: 기존 state가 있으면 `add_requested_nodes`가 새 IP만 추가하고 기존 ID, key, channel, CA, DB, epoch는 그대로 둔다.
  - 그다음 아직 provisioned가 아닌 Node를 provision한다.
  - `deploy/lan/README.md` 27~30행: "A repeated init against the same state may add addresses, but it never removes an existing Node or changes its Node ID, key, channel, CA, database, or recovery epoch".
  - unit test `test_legacy_single_node_state_normalizes_and_addition_preserves_identity`.
  - 별도의 add-node 명령은 없다. 기존 2개 Node의 ID를 복사하거나 지어낼 필요도 없다.
- **조건:**
  1. server IP가 같아야 한다.
  2. 모든 추가 Node가 같은 `--node-port 18515`를 써야 한다. 다르면 `add_requested_nodes`가 거부한다. 따라서 worker3, worker4, CP Windows에서 18515가 비어 있어야 한다.
  3. CA 인자를 넘길 때는 같은 chain이어야 한다. 다른 chain은 거부된다.
  4. CP Node는 `--allow-server-node-colocation`과 Docker API 1.45 이상이 필요하다. 지금 CP는 API 1.41이라 업그레이드가 필요하다.
  5. 확장 뒤에는 `bundle`을 다시 실행하고(전 Node가 provisioned여야 함) `serve` 재시작으로 allowlist를 다시 읽힌다.
  6. renewal batch에는 모든 활성 Node가 들어가야 한다.
- **확인하지 않은 것:**
  - 외부 CA state에서 실제로 끝까지 확장해 보는 live 증명은 없다.
  - leaf-rotation batch가 prepare/stage된 채 commit되지 않은 상태에서 Node를 추가하면 어떻게 되는지 확인하지 않았다. 확장 gate로 "commit되지 않은 batch가 없을 것"을 둘 것을 권고한다.
  - namespace 이름 `…-w12`는 5개 Node를 담게 되어도 그대로 남는다. 이름일 뿐이며, 문서에 적어 두면 된다.
- **plan에 빠진 것(Low):** plan과 History는 이 확장 경로를 명시하지 않는다. "use all active f5 Nodes when expanded"라는 문장만 있다.

## B. R4 source ff97cd9e (source 판정)

delta는 59f 기준 `deploy/lan/worker_workspace.py` +25/−1행과 `tests/core/test_lan_workspace_upgrade.py` +182행이다. 나머지는 History와 Evidence다.

**판정: 수용 가능(ACCEPT), High/Medium 발견 0.**

- **변경 전 거부:** `validate_install_target`은 `install()`에서 idle, volume inspect, credential 확인, `load_image`, `stop`보다 먼저 실행된다. 거부하면 Docker를 바꾸는 일도 image load도 없다. 새 test가 이것을 `calls == [('inspect',name)]`로 확인한다.
- **flag 변형:** `--storage-policy`, `-storage-policy`, `=값` 형태와 빈 값을 모두 거부한다. node-agent는 Go `flag` 패키지로 `storage-policy`를 선언하며(`main.go:51`) 받아들이는 형태가 이 넷뿐이다. 값 자리에 같은 문자열이 있어도 거부하므로 fail-closed다.
- **보존되지 않는 mount:**
  - `/state`는 그대로 허용한다(`validate_target`/`repair_target`이 이미 검증).
  - 허용하는 socket은 "bind, Source와 Destination 모두 `/var/run/docker.sock`, RW, rprivate"인 mount 1개뿐이다.
  - 그 밖의 mount(`/contribution`, `/cache` 등), socket의 RO·rshared 변형, 두 번째 socket은 모두 거부한다.
- **plain 설치는 바뀌지 않음:** 실제 plain Node(`start-node.sh` 생성)는 `/state`만 있고 socket이 없다. 이 형태는 통과한다. 이미 workspace로 바뀐 container(socket bind 있음)를 다시 실행하는 경우도 통과한다.
- **이전 storage backup rollback:** `rollback()`과 `validate_target()`은 바뀌지 않았다. storage가 켜진 recorded backup도 `undo=True`로 복원된다. 새 test가 image load나 create 없이 복원됨을 확인한다.
- **과장된 결합 지원 주장 없음:** 오류 메시지와 History 모두 "Node를 보존하고 workspace에는 별도 plain Node를 쓰라"고만 말한다. storage와 workspace를 함께 지원한다고 말하지 않는다. 실제 Linux/Docker installer 15건은 skip이라고 정직하게 적었다.
- **독립 실행(15:48:49 KST):**
  - 59f 기준 범위 밖 파일을 빼고 scratchpad로 export한 copy에서 main `.venv` Python 3.14.7을 `-B`, `-p no:cacheprovider`로 실행했다.
  - owner의 새 test 30개와 내 probe 4개, 합계 **34 passed**.
  - probe 내용: socket 없는 실제 plain 형태는 통과한다. socket 2개, volume 형태의 socket, 다른 경로의 socket은 거부한다.
  - 넓은 test 재실행과 untouched-source red 재현은 하지 않았다. owner가 적은 15 fail/15 pass는 owner의 측정값이다.
- **Low(test 범위):** fixture의 `current`에는 항상 socket mount가 있다. 그래서 owner test에는 실제 plain Node 형태(`/state`만)가 직접 들어 있지 않다. 내 probe로 동작은 확인했다. test에 socket 없는 경우를 하나 추가할 것을 권고한다.
- **범위 밖 관찰(이번 delta가 만든 것이 아님):** 재생성 container는 mount 말고 다른 HostConfig(device/GPU 요청, env 등)를 옮기지 않는다. 59f에도 있던 동작이다.

## C. 확장 supplement 6cbb2b98 (같은 dispatch 중 `msg_3c754365a126`로 받음, 15:51~15:53 KST)

Codex commit `6cbb2b9801dc5040b5a5ad70bf7b5434130d8ccc`이 보충 자료를 붙였다. 내용은 `extension-and-runtime-env-contract.json`(sha256 `747c513670ee71180320ec0c0cc53e424fcc5de252197a05d81d8ea4a1876228`, 내가 다시 계산해 일치), delivery receipt, History 1.1.1이다. 이 commit에서도 frozen core 공개 plan은 `5121cb83…` 그대로임을 다시 계산해 확인했다.

59f source와 대조한 결과, supplement의 주장은 **모두 맞다**.

- `add_requested_nodes`는 append-only이고 같은 port여야 한다.
- 다시 init하면 F5 kill switch를 다시 고정하고 `version+1`로 올린다(`lan_pilot.py:925`). 따라서 F5 private-state/DB hash는 실제로 바뀐다. 확장 뒤에는 새 expected-state receipt를 만들어야 한다는 결론이 맞다.
- tenant/node INSERT는 `ON CONFLICT DO NOTHING`이다(`:915`, `:919`).
- 다른 chain은 거부되고, 기존 CA/control/signer key는 보존된다(`ensure_pilot_pki`).
- Alembic은 `sys.executable -m alembic`을 `env=dict(os.environ, …)`로 실행하는 자식 process다(`:1117-1119`). 그래서 `-B`는 전해지지 않고 `PYTHONDONTWRITEBYTECODE=1`은 전해진다. owner process 환경에 그 값을 넣으라는 요구가 정확하다.
- 처음 init에서는 옛 catalog와 겹치지 않아야 하고, 확장에서는 현재 F5 tenant/epoch/CA/옛 ID를 보존하고 새 ID만 겹치지 않으면 된다. 이 구분도 맞다.

A절에서 "plan에 확장 경로가 빠져 있다"고 적은 Low는 이 supplement로 **해결**됐다. 남은 것:

- **(Low)** 확장 전제 조건 "rotation state settled"를 실행 gate로 바꿀 때, prepare/stage된 채 commit되지 않은 batch가 0인지를 판정하는 기준을 정확히 적어야 한다.
- Codex가 적은 multinode 39 pass / 3 skip은 Codex의 측정이며, 나는 다시 실행하지 않았다.

## 다음 첫 행동과 담당

- **root:** 이렇게 진행한다.
  - packet `7dd8fa95`: 실행하지 않는 plan과 위 안전 준비 단계로 받아들인다.
  - P2 설치: operator 규칙과 증명이 있을 때까지 BLOCKED로 둔다.
  - R4 `ff97cd9e`: 내 source 판정 ACCEPT와 required hosted Core/Docs 결과를 보고 함께 landing할지 정한다.
- **Codex:** History 문구 Low 2건을 고친다. 2→5 확장 경로와 그 조건을 plan에 적는다. known_hosts를 F5 전용으로 고정한다. firewall 규칙 영속화와 재증명 gate를 넣는다. R4 test에 socket 없는 plain 경우를 추가한다.
- **Claude:** 새 hash가 오면 다시 검토한다.
