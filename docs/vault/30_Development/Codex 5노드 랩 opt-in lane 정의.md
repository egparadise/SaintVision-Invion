---
doc_id: "CODEX-FIVE-NODE-LAB-LANE-001"
title: "Codex 5노드 랩 opt-in lane 정의"
version: "1.1.0"
status: "proposed"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T02:06:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["five-node", "lab", "workflow-dispatch", "S05", "S06", "S07", "benchmark", "NTP", "mTLS"]
---

# Codex 5노드 랩 opt-in lane 정의

이 문서는 S05/S07 opt-in 측정과 S06 원격 WS/PTY/Git 재시작 여정을 **물리 5노드 랩에서만** 실행하기 위한 수동 lane 제안이다. v1.1은 S05의 legacy/candidate 20·50동시 실행 계획과 lock-hold/limit-row wait evidence, 랩 준비 대응표를 추가한다. 이번 카드에서는 workflow·제품 코드·계약을 바꾸지 않는다. 랩 준비와 F-S05-03 후속 결정 뒤 `agent/codex/five-node-lane` 브랜치에서 별도 `workflow_dispatch` workflow와 아직 없는 inventory-bound S05/S06 runner를 구현·검토하고, GitHub Environment 승인 전에는 실행하지 않는다.

## 실행 경계와 입력

- runner: `[self-hosted, linux, x64, saintvision-five-node-lab]`, environment `five-node-lab`, concurrency group `saintvision-five-node-lab`, `cancel-in-progress: false`, 동시 실행 1개. GitHub hosted runner와 개발 PC는 물리 5노드 판정에 쓰지 않는다. 기존 `core.yml` job 안에 넣지 않고 별도 workflow로 분리해 일반 push가 물리 측정을 취소하지 못하게 한다.
- 공통 필수 입력: `code_sha`(40 hex), `inventory_revision`, `control_plane_image`·`node_agent_image`·`worker_image`·`postgres_image`(모두 immutable digest), `s07_repetitions=20`, `liveness_timeout_seconds=60`, `poll_interval_seconds=0.1`, `run_s06_remote=true`.
- S05 필수 입력: `s05_modes=legacy,short-commit`(고정 집합), `s05_request_waves=20,50`(고정 순서), `s05_repetitions=3`, `s05_timeout_seconds=90`, `s05_candidate_setting=placementShortCommit`, `s05_candidate_default=false`, `s05_require_followup_decision_sha`(카드 18 이후 코디네이터 결정 SHA). 임의의 mode 누락·50 단독 실행·결정 SHA 부재는 preflight 실패다.
- 환경변수: `PYTHONUTF8=1`, `PYTHONPATH=src:services/control-plane/src`, `INV_TEST_ADMIN_DSN=${FIVE_NODE_INV_TEST_ADMIN_DSN}`, `INV_S05_EXECUTOR=five-node-lab`, `INV_S07_EXECUTOR=five-node-lab`, `LAB_INVENTORY_PATH`(runner의 read-only 파일), `LAB_EVIDENCE_ROOT`(run별 빈 디렉터리). `PYTHONPATH`의 `:`는 Linux 구분자이며 Windows 개발 PC에 그대로 복사하지 않는다.
- secret 이름만 workflow에 선언한다: `FIVE_NODE_INV_TEST_ADMIN_DSN`, `FIVE_NODE_CA_PEM`, `FIVE_NODE_CONTROL_CERT_PEM`, `FIVE_NODE_CONTROL_KEY_PEM`, `FIVE_NODE_SIGNER_KEY_PEM`, 필요 시 `FIVE_NODE_REGISTRY_USERNAME`·`FIVE_NODE_REGISTRY_TOKEN`. 값·DSN·private state는 로그나 artifact에 넣지 않는다. node별 endpoint, 공개 인증서 fingerprint, OS/profile은 revision이 고정된 inventory에 두고 private key는 GitHub Environment 또는 runner secret store에서만 materialize한다.

사전 조건은 정확한 SHA의 clean checkout, digest pull·검증, 5개 서로 다른 물리 node의 mTLS preflight와 `lan-workspace-v1` profile, 격리된 disposable PostgreSQL, 모든 node의 시계 동기와 시작 전 active lease 0이다. 하나라도 없으면 부하를 시작하지 않고 unavailable evidence를 남긴다. S05 50동시는 20동시 양 모드가 invariant·redaction gate를 먼저 통과하고, F-S05-03 후속 결정 SHA가 현재 `code_sha`의 조상임을 확인한 경우에만 실행한다.

## S05-DB 5노드 실행 계획

### 물리 adapter와 동일 조건

현재 `tools/placement_benchmark.py`의 `--mode legacy|short-commit`, JSON schema 1.3, JUnit 출력은 실행 형식의 정본이지만 fixture가 만드는 합성 node row를 사용한다. 따라서 lane 구현 카드는 다음 중 하나를 먼저 제공해야 한다.

1. 같은 도구에 `--adapter five-node-lab --inventory "$LAB_INVENTORY_PATH"`를 추가해 실제 5개 node heartbeat/resource snapshot과 mTLS identity를 읽는다.
2. 동일 JSON/JUnit schema를 내는 `tools/run_s05_five_node_benchmark.py` wrapper를 추가한다.

둘 다 현재 저장소에는 없으며, 구현 전 `placement_benchmark.py` 실행은 **하네스 control**일 뿐 AC-05 물리 증거가 아니다. adapter는 DB에 합성 node/resource row를 만들거나 heartbeat를 대신 갱신해서는 안 된다. 매 wave는 동일 `code_sha`·inventory revision·image digest·policy version·resource offer·요청 body를 사용하고 mode만 바꾼다. 순서 편향을 보기 위해 repetition별 `legacy→candidate`, `candidate→legacy`, `legacy→candidate` 순서를 manifest에 고정한다.

### wave와 승격 게이트

| 단계 | 실행 | 통과 조건 | 실패 시 |
|---|---|---|---|
| 0 preflight | 5 node·NTP·mTLS·inventory·disposable PG·active lease 0 | 아래 준비표 전 항목 `ready`, 비밀 redaction 0건 | 부하 미실행, unavailable JSON/JUnit과 원인만 업로드 |
| 1 canary | mode별 20동시 × 3회 | 각 요청 결과 기록, overbooking 0, fencing 유일, stale epoch 수락 0, 실행 전후 active lease 기대값 일치 | 50동시 금지, red artifact 보존 |
| 2 acceptance wave | mode별 50동시 × 3회 | 50/50, P95 ≤2초, 결정성, overbooking 0, duplicate active Run 0, stale epoch 수락 0 | AC-05 미달, `review` 유지 |
| 3 비교 | legacy와 candidate 중앙값 비교 | candidate lock-hold P95 감소 **AND** 내부+외부 `55P03/57014` 합계 감소. 성공 수만으로 통과 금지 | F-S05 후속 finding, flag off 유지 |

각 repetition 뒤 모든 Lease를 stop receipt로 해제해 active 0을 확인하고 observation freshness를 실제 heartbeat로 다시 채운다. 실패 요청도 index·완료 순서·지연·public code/status/retryable·cause SQLSTATE·내부 retry 횟수를 남긴다. 같은 초기 상태에서 Explain의 canonical decision 입력과 선택 node가 반복 간 같아야 결정성 통과이며, generated ID·timestamp만 제외한 canonical digest 규칙을 manifest에 기록한다.

### 필수 S05 artifact

`five-node-s05-placement-<code_sha>`에는 다음을 모두 넣는다.

- `manifest.json`: code/inventory/image/policy SHA, 실행 순서, 입력 body hash, node 공개 fingerprint, 명령과 exit code, 시작·종료 UTC/KST.
- `s05/<mode>/<wave>/<repetition>/placement.json`: 요청별 sample, Explain/snapshot/canonical decision digest, leases/fencing, no-overbooking, active before/after.
- 같은 경로의 `placement.xml`: JUnit failure/skip/error를 숨기지 않는다.
- schema 1.3의 `lockHold` p50/p95/max와 `limitRowWait` attempt/acquired/timeoutRetryCount/p50/p95/max. project/limit/node/resource lock 종류별 wait가 추가되면 기존 필드를 지우지 않고 additive version으로 낸다.
- `comparison.json`: mode·wave별 3회 중앙값, 내부와 외부 `55P03/57014`, retry 분포, candidate gate 두 조건, AC-05 항목별 pass/fail/unmeasured.
- `redaction.json`: DSN·private key·token·원문 terminal secret 탐지 0건과 검사 명령/exit code.

카드 14의 개발 PC 결과(hold P95 중앙값 1399.883→122.126ms, 요청 P95 1771.763→1697.737ms, 내부 limit-row `55P03` 0/0/0→14/10/11)는 랩 예상값이 아니라 비교 schema의 회귀 기준이다. 랩 결과가 다르면 물리 결과를 우선하고 원인을 새 finding으로 남긴다.

## 랩 준비 체크리스트 대응표

| 준비 항목 | 고정 입력·비밀 | preflight 증거 | 차단 기준 |
|---|---|---|---|
| 물리 node 5대 | inventory의 node ID·endpoint·OS/profile·NIC, 동일 node-agent digest | 서로 다른 hardware/host identity 5개, 각 `/health`·heartbeat·resource snapshot, `lan-workspace-v1`, 공개 fingerprint | 5개 미만, 중복 host identity, 합성 row, offline/stale node가 하나라도 있으면 중단 |
| 자원 기준선 | inventory revision, resource offer/policy version | node별 CPU/RAM/GPU/disk 관측과 합계, active lease 0, 격리/unschedulable 상태 | 관측 누락·offer 불일치·active 잔존·epoch 불일치 |
| NTP/시각 | NTP source 목록은 inventory, 인증정보 없음 | node별 UTC, offset, stratum, sync state, `chronyc tracking/sources` 상당의 redacted 출력 hash | unsynchronised, 허용 source 외 사용, `abs(clock_skew_seconds)>5`; 목표 `≤1s` 미달은 warning과 실제 값 보존 |
| CA·control cert | `FIVE_NODE_CA_PEM`, control cert/key secret 이름 | CA chain, SHA-256 fingerprint, SAN/usage, not-before/not-after, control endpoint handshake | chain/SAN/usage 불일치, 만료·미개시, key 파일 권한 초과, private material 로그 탐지 |
| node cert 5개 | runner/node secret store; inventory에는 fingerprint·expected subject만 | node ID↔subject/SAN↔fingerprint 1:1, 양방향 handshake, revoked/unknown cert 부정 대조 | 공유 cert, identity 불일치, 부정 대조 수락, cert 5개 미만 |
| 네트워크 | inventory의 허용 endpoint/port | control↔5 node reachability와 비허용 endpoint 거부, RTT 분포 | 필요한 경로 실패 또는 비허용 경로 성공 |
| PostgreSQL | `FIVE_NODE_INV_TEST_ADMIN_DSN` secret 이름, immutable postgres digest | 일회용 DB 이름 hash, PG version/image digest, runtime non-owner/RLS, 시작 active 0 | ambient/운영 DB, owner/bypass role, cleanup ownership 불명 |
| checkout·images | `code_sha`와 4개 immutable digest | clean checkout, commit ancestor, pull digest equality, SBOM/provenance 위치 | tag-only·dirty tree·digest mismatch |
| evidence root | run ID별 새 `LAB_EVIDENCE_ROOT` | empty-before, owner/permission, free space, artifact retention 30일 | 기존 artifact 혼입, 쓰기 불가, secret redaction 미설정 |
| 승인·직렬화 | GitHub Environment reviewer, concurrency group | 승인 actor/time, group `saintvision-five-node-lab`, cancel false | 승인 없음, 다른 lab run active, 일반 push가 취소 가능 |

## 한 lane에서 순차 실행할 명령

```text
python tools/placement_benchmark.py --mode legacy --requests 20 --concurrency 20 --rounds 1 --report "$LAB_EVIDENCE_ROOT/control/s05-legacy-20.json" --junit "$LAB_EVIDENCE_ROOT/control/s05-legacy-20.xml"
python tools/run_s05_five_node_benchmark.py --inventory "$LAB_INVENTORY_PATH" --modes legacy,short-commit --waves 20,50 --repetitions 3 --json-root "$LAB_EVIDENCE_ROOT/s05" --junit-root "$LAB_EVIDENCE_ROOT/s05"
python tools/measure_s07_recovery.py --nodes 5 --repetitions 20 --liveness-timeout-seconds 60 --poll-interval-seconds 0.1 --target-recovery-success-rate 0.95 --json-out "$LAB_EVIDENCE_ROOT/s07-recovery.json" --junit-out "$LAB_EVIDENCE_ROOT/s07-recovery.xml"
python tools/check_remote_workspace.py --state "<node-state-dir>" --prepared "<prepared.json>" --image "<worker-image-digest>" --preflight-only
python tools/check_remote_workspace.py --state "<node-state-dir>" --prepared "<prepared.json>" --image "<worker-image-digest>"
python tools/run_s06_five_node_journey.py --inventory "$LAB_INVENTORY_PATH" --code-sha "<code_sha>" --control-plane-image "<digest>" --node-agent-image "<digest>" --worker-image "<digest>" --json-out "$LAB_EVIDENCE_ROOT/s06-remote.json" --junit-out "$LAB_EVIDENCE_ROOT/s06-remote.xml"  # 제안·미구현
```

첫째·셋째·넷째 명령은 현재 도구의 실제 인터페이스다. 둘째 S05 물리 wrapper와 마지막 S06 runner는 **제안·미구현**이다. S05 control과 S07 measurement는 실 PostgreSQL의 합성 node row를 측정하므로, 단지 5노드 runner에서 실행해도 물리 5노드 증거가 되지 않는다. 제안 브랜치는 inventory-bound lab adapter 또는 동일 JSON/JUnit 형식의 물리 wrapper를 제공해야 하며, 그 전 결과는 preflight/control로만 분류한다. S06 runner는 실제 Git commit/push 또는 격리 remote publish, PTY 명령·resize·재접속, Control Plane 재시작, 대상 Node 재시작, 새 ticket으로 resume, snapshot restore hash 일치, 중복 실행 0을 한 여정으로 증명해야 한다. 기존 `check_remote_workspace.py`의 7개 case(`python`, `ai`, 두 cancel, `failure`, `timeout`, `output-recovery`)는 선행 원격 실행 증거일 뿐 WS/PTY/Git 재시작 증거를 대신하지 않는다.

S05 → S07 → S06 순서로 한 번에 하나만 실행한다. S07의 감지 상한은 커널 predicate를 바꾸지 않고 `60초 timeout + 0.1초 poll`이며, JSON의 synthetic recovery는 물리 byte 복구 성공률로 승격하지 않는다. 실패·timeout 때도 owned DB/container만 보존 또는 정리하고 red artifact를 업로드한다.

## 증거 artifact와 판정

| artifact 이름 | 필수 내용 |
|---|---|
| `five-node-lane-manifest-<code_sha>` | code/inventory revision, 4개 image digest, 5개 node 공개 identity·OS, 명령·exit code·UTC/KST, runner label, secret redaction 검사 |
| `five-node-s05-placement-<code_sha>` | 20·50동시 × legacy/candidate × 3회 JSON/JUnit, request P95, Explain/canonical decision digest, snapshot/fencing/no-overbooking, `lockHold`, `limitRowWait`, retry·SQLSTATE, comparison/redaction manifest |
| `five-node-s07-recovery-<code_sha>` | `s07-recovery.json/xml`, 5-node×20회 분포, timeout+poll 감지, stale write 0, 물리 shard byte 복구 receipt |
| `five-node-s06-workspace-<code_sha>` | 기존 7-case 결과, `s06-remote.json/xml`, WS/PTY transcript hash, Git remote receipt, CP/Node restart timeline, restore before/after hash |

artifact는 실패에도 `if: always()`로 30일 보존하되 private key·token·DSN·원문 terminal secret은 제외한다. 네 artifact의 SHA·run URL·exit code가 모두 있고 독립 reviewer가 내용과 물리 inventory를 대조한 뒤에만 AC-05/06/07 판단 자료로 쓴다. 현재 S06-DB가 `review`인 이유는 소프트웨어 결속과 Linux hosted 회귀가 물리 5노드 원격 WS/PTY/Git 및 CP/Node 재시작 복원 여정을 측정하지 않기 때문이다.
