---
doc_id: "CODEX-FIVE-NODE-LAB-LANE-001"
title: "Codex 5노드 랩 opt-in lane 정의"
version: "1.0.0"
status: "proposed"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T00:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["five-node", "lab", "workflow-dispatch", "S05", "S06", "S07"]
---

# Codex 5노드 랩 opt-in lane 정의

이 문서는 S05/S07 opt-in 측정과 S06 원격 WS/PTY/Git 재시작 여정을 **물리 5노드 랩에서만** 실행하기 위한 수동 lane 제안이다. 이번 카드에서는 `.github/workflows/core.yml`을 바꾸지 않는다. 랩 준비 뒤 `agent/codex/five-node-lane` 브랜치에서 별도 `workflow_dispatch` job과 아직 없는 S06 물리 여정 runner를 구현·검토하고, GitHub Environment 승인 전에는 실행하지 않는다.

## 실행 경계와 입력

- runner: `[self-hosted, linux, x64, saintvision-five-node-lab]`, environment `five-node-lab`, 동시 실행 1개. GitHub hosted runner와 개발 PC는 물리 5노드 판정에 쓰지 않는다.
- 필수 입력: `code_sha`(40 hex), `inventory_revision`, `control_plane_image`·`node_agent_image`·`worker_image`·`postgres_image`(모두 immutable digest), `s05_requests=50`, `s07_repetitions=20`, `liveness_timeout_seconds=60`, `poll_interval_seconds=0.1`, `run_s06_remote=true`.
- 환경변수: `PYTHONUTF8=1`, `PYTHONPATH=src:services/control-plane/src`, `INV_TEST_ADMIN_DSN=${FIVE_NODE_INV_TEST_ADMIN_DSN}`, `INV_S07_EXECUTOR=five-node-lab`, `LAB_INVENTORY_PATH`(runner의 read-only 파일), `LAB_EVIDENCE_ROOT`(run별 빈 디렉터리).
- secret 이름만 workflow에 선언한다: `FIVE_NODE_INV_TEST_ADMIN_DSN`, `FIVE_NODE_CA_PEM`, `FIVE_NODE_CONTROL_CERT_PEM`, `FIVE_NODE_CONTROL_KEY_PEM`, `FIVE_NODE_SIGNER_KEY_PEM`, 필요 시 `FIVE_NODE_REGISTRY_USERNAME`·`FIVE_NODE_REGISTRY_TOKEN`. 값·DSN·private state는 로그나 artifact에 넣지 않는다. node별 endpoint, 공개 인증서 fingerprint, OS/profile은 revision이 고정된 inventory에 두고 private key는 GitHub Environment 또는 runner secret store에서만 materialize한다.

사전 조건은 정확한 SHA의 clean checkout, digest pull·검증, 5개 서로 다른 물리 node의 mTLS preflight와 `lan-workspace-v1` profile, 격리된 disposable PostgreSQL, 모든 node의 시계 동기와 시작 전 active lease 0이다. 하나라도 없으면 전체 lane은 실행하지 않고 unavailable evidence를 남긴다.

## 한 lane에서 순차 실행할 명령

```text
python tools/placement_benchmark.py --requests 50 --concurrency 50 --report "$LAB_EVIDENCE_ROOT/s05-placement.json" --junit "$LAB_EVIDENCE_ROOT/s05-placement.xml"
python tools/measure_s07_recovery.py --nodes 5 --repetitions 20 --liveness-timeout-seconds 60 --poll-interval-seconds 0.1 --target-recovery-success-rate 0.95 --json-out "$LAB_EVIDENCE_ROOT/s07-recovery.json" --junit-out "$LAB_EVIDENCE_ROOT/s07-recovery.xml"
python tools/check_remote_workspace.py --state "<node-state-dir>" --prepared "<prepared.json>" --image "<worker-image-digest>" --preflight-only
python tools/check_remote_workspace.py --state "<node-state-dir>" --prepared "<prepared.json>" --image "<worker-image-digest>"
python tools/run_s06_five_node_journey.py --inventory "$LAB_INVENTORY_PATH" --code-sha "<code_sha>" --control-plane-image "<digest>" --node-agent-image "<digest>" --worker-image "<digest>" --json-out "$LAB_EVIDENCE_ROOT/s06-remote.json" --junit-out "$LAB_EVIDENCE_ROOT/s06-remote.xml"
```

앞의 네 명령은 현재 도구의 실제 인터페이스다. 다만 S05 기본 adapter와 S07 measurement는 실 PostgreSQL의 합성 node row를 측정하므로, 단지 5노드 runner에서 실행해도 물리 5노드 증거가 되지 않는다. 제안 브랜치는 두 도구에 inventory-bound lab adapter를 추가하거나 동일 JSON/JUnit 형식의 물리 wrapper를 제공해야 하며, 그 전 결과는 preflight/control로만 분류한다. 마지막 명령은 그 브랜치에서 추가할 S06 runner의 고정 인터페이스이며 현재 저장소에는 없으므로, 이 문서만으로 S06 물리 여정을 통과했다고 주장할 수 없다. runner는 실제 Git commit/push 또는 격리 remote publish, PTY 명령·resize·재접속, Control Plane 재시작, 대상 Node 재시작, 새 ticket으로 resume, snapshot restore hash 일치, 중복 실행 0을 한 여정으로 증명해야 한다. 기존 `check_remote_workspace.py`의 7개 case(`python`, `ai`, 두 cancel, `failure`, `timeout`, `output-recovery`)는 선행 원격 실행 증거일 뿐 WS/PTY/Git 재시작 증거를 대신하지 않는다.

S05 → S07 → S06 순서로 한 번에 하나만 실행한다. S07의 감지 상한은 커널 predicate를 바꾸지 않고 `60초 timeout + 0.1초 poll`이며, JSON의 synthetic recovery는 물리 byte 복구 성공률로 승격하지 않는다. 실패·timeout 때도 owned DB/container만 보존 또는 정리하고 red artifact를 업로드한다.

## 증거 artifact와 판정

| artifact 이름 | 필수 내용 |
|---|---|
| `five-node-lane-manifest-<code_sha>` | code/inventory revision, 4개 image digest, 5개 node 공개 identity·OS, 명령·exit code·UTC/KST, runner label, secret redaction 검사 |
| `five-node-s05-placement-<code_sha>` | `s05-placement.json/xml`, 50동시 2회 결과, P95, Explain/snapshot/fencing/no-overbooking |
| `five-node-s07-recovery-<code_sha>` | `s07-recovery.json/xml`, 5-node×20회 분포, timeout+poll 감지, stale write 0, 물리 shard byte 복구 receipt |
| `five-node-s06-workspace-<code_sha>` | 기존 7-case 결과, `s06-remote.json/xml`, WS/PTY transcript hash, Git remote receipt, CP/Node restart timeline, restore before/after hash |

artifact는 실패에도 `if: always()`로 30일 보존하되 private key·token·DSN·원문 terminal secret은 제외한다. 네 artifact의 SHA·run URL·exit code가 모두 있고 독립 reviewer가 내용과 물리 inventory를 대조한 뒤에만 AC-05/06/07 판단 자료로 쓴다. 현재 S06-DB가 `review`인 이유는 소프트웨어 결속과 Linux hosted 회귀가 물리 5노드 원격 WS/PTY/Git 및 CP/Node 재시작 복원 여정을 측정하지 않기 때문이다.
