---
doc_id: "HISTORY-FLEET5-20261105-P0-CODE-6C0F-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 P0 plain peer-phase 구현 후보 6c0fc4ad 독립 code 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T21:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "45bc23cb"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "p0", "peer-policy", "claude"]
---

# P0 code 후보 6c0f 검토

Orca task `task_fcd89694c5b7`, dispatch `ctx_d0aa7908032b`. [[2026-11-05_20-40-00_KST_FLEET5_P0_peer_phase_계약_검토_Claude]]의 architecture 수락(M1~M10)을 받아 owner(`ctx_6f0f8253b8a7`)가 낸 구현을 **code로** 따로 판정한다. 앞선 `f012` architecture 판정은 code 수락이 아니다.

- **대상:** `agent/codex/fleet5-compute-storage-contract-20261105`의 `6c0fc4adf53562909e3d8246ddf293d8aadb0d0e` (기준 `5023ce7d`)
  - non-docs 23개 파일, +2450/−360
  - Go: `6c0fc4ad:services/node-agent/runtime/peer_floor_linux.go`, `6c0fc4ad:services/node-agent/transport/peer_floor.go`, `main.go`의 observer flag
  - Python: `6c0fc4ad:deploy/lan/peer_policy_phase.py`, `6c0fc4ad:deploy/lan/worker_peer_floor.py`, `6c0fc4ad:deploy/lan/worker_plain_rotation.py`, 그 밖의 worker helper와 `tools/lan_pilot.py`
  - test와 proof: `6c0fc4ad:tests/test_fleet5_plain_peer_phase_v3.py`, `6c0fc4ad:tests/proofs/run_fleet5_peer_phase_fixed_probe.py`
- **읽은 방식:** Git object만 읽었다. 실행은 `6c0f`에서 분리한 임시 worktree에서 했고, 그 worktree는 제거했다.
- **하지 않은 일:** production·source 수정, Go 수정, physical·SSH·Docker·WSL·PKI, private 설정, automation 변경, 공유 board, Obsidian apply, 다른 agent 사용
- **early BLOCK:** `msg_c19e94fc184d`로 root와 owner에게 보냈다.
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/p0-code-6c0f-review.json`

## source에서 확인한 계약 준수

| 항목 | 확인한 내용 |
|---|---|
| M1 | schema `:3` exact key. 예전 `:1`/`:2` install과 rollback은 mutation 전에 거부한다. 예전 finalize는 이미 finalized된 기록의 replay만 허용한다 |
| M2 | Go가 실제 journal `.peer-policy`를 openat no-follow로 읽는다. regular, 0600, dir uid, nlink 1, 크기 제한, 두 번 읽어 같음, exact key, strict int, hash == 활성 `peer-policy.json`의 sha256. 서명 domain은 `saintvision/node-peer-policy-floor/v1\x00`, Node TLS ed25519 key. 같은 exe, 같은 uid, 정확한 `--serve` cmdline, PID 1, container·volume·consumer 전후 동일을 확인한다. host mirror, 추론, 서명 없는 fallback, floor 없음 수락은 **없다** |
| M2 검증 측 | Python이 exact key, nonce, scope, cert 지문·SAN·EKU·유효기간, freshness −30~120초, 서명을 확인한다 |
| M4 | active 쓰기 전에 expiry > now+630초, ≤ now+7일−30초, scope, version > floor를 확인한다 |
| M5 | host 파일보다 먼저 durable 기록(installing, publicationIntent, peerPhaseBinding, prePeerFloor)을 쓴다. `rollback()`은 언제나 forward-only로 거부한다. restart는 stop → 정지 확인 → 복사 → start 순서다 |
| M6 | restart 후 관측 floor == overlap, 다음 DER. production이 served DER를 따로 확인하지는 않는다. 다만 Go `GetCertificate`가 handshake마다 cert 파일을 다시 읽고 복사는 정지 중에 하므로, 구조상 file DER == served DER다(참고 사항) |
| M7 | 서명된 receipt에 pre·post floor가 있다. archive `:3`과 finalized journal에 peer field가 있다 |
| M8 | CP에 기록된 node policy bytes의 hash와 P를 서명된 관측과 묶는다. batch preflight는 journal이나 어떤 mutation보다 먼저 모든 active member에 대해 돈다. member별 CAS는 그대로이고, 넓은 atomic batch나 새 CAS ladder는 없다 |
| workspace backup | 두 번째 consumer는 Enable-Workspace backup과 정확히 같을 때만 허용한다(phase ready, previousId, backup 이름, upgradeId label, agentImage, 정지, restart=no). 임의 container 선택은 없다 |
| generic helper | `leaf-rotation.lock` O_EXCL로 직렬화한다. 회전 기록이 있으면 repair, workspace, execution, storage helper를 막는다 |
| standalone closure | `WORKER_MODULES` 5개 hash가 `6c0f` blob과 같다. `backend.yml`의 `workerModuleCount`는 2 → 5 |

## BLOCK

### B1 — M10 native 증명이 빨갛다

- Core `42028616559`(`6c0f`)가 "FLEET5 fixed native Go two-cycle proof" 단계에서 `ValueError: mTLS heartbeat rejected`로 실패했다. 뒤의 Core suite는 돌지 않았다.
- artifact `13415121511`(sha256 `3d8e2bb0…`): `proofValid=false`, `completedNormalCycles=0`, floors `[7]`.
  - true: expiry 쓰기 전 거부, floor·CP 불일치 거부, strict old reader 거부
  - false: handshake pin 뒤 rollback 거부
- **원인:** proof script의 `heartbeat()`가 nonce를 base64로 보낸다. `NodeProbeInput` 계약은 `^[0-9a-f]{64}$`다. proof fixture 결함이며, product 결함으로 확인된 것은 아니다.
- **고칠 일:** hex nonce로 바꾸고 같은 dispatch를 다시 돌려 P7→11, C7→9 두 cycle과 모든 음성 case가 true인 녹색을 낸다.

### B2 — 2fb lifecycle 보장이 `:3`에서 다시 증명되지 않았다

`6c0f`에서 예전에 수락된 lifecycle suite가 실패한다.

| suite | 결과 |
|---|---|
| `test_lan_leaf_rotation` | 35 failed, 6 passed |
| consecutive | 42 failed, 1 skipped |
| batch_successor | 46 failed |
| predecessor_residue | 2 failed |
| archive_residue | 3 failed, 7 passed, 4 skipped |
| **합계** | **128 failed** |

- 원인 분류: 서명된 floor 파일과 nonce 요구 67, fresh floor nonce 요구 45, 예전 install 거부 9, 정규식 불일치 7
- `:3` 계약의 예상된 결과이지만, test가 `:3` fixture로 옮겨지지도 대체되지도 않았다. skip이나 삭제는 보지 못했다. 그 결과 full Core가 빨갛고, residue, retirement, successor, consecutive, archive 보장이 `:3`에서 증명되지 않는다.
- **고칠 일:** assertion을 하나도 빼지 않고 서명 floor fixture로 `:3`에 옮긴다. 예전 schema 거부 case는 음성 test로 남긴다.

## 그 밖의 발견

- **F1 (Medium):** `bd96479b`는 `6c0f`의 조상이 아니다. `6c0f`의 `backend.yml`은 module 수만 바꿨다. 통합할 때 `bd96`의 `is True`와 `type(x) is int` assert와 5개 module 수를 field 단위로 합쳐야 한다.
- **F2 (Medium, liveness):** `leaf-rotation.json`이 남아 있으므로, 한 번이라도 finalize한 Node는 repair, workspace, execution, storage helper가 영구히 막힌다. 안전하지만 지나치다. settled-finalized 규칙이나 문서화된 운영 경로가 필요하다.
- **F3 (Medium, liveness):** restart 중 복사 뒤, start 전에 죽으면 container가 정지 상태로 남는다. observer는 실행 중인 container를 요구하므로 BLOCKED가 된다. 복구는 문서에 없는 수동 forward start뿐이다.
- **F4 (Low):** observer가 floor hash == active hash를 요구하므로, active=overlap/floor=P 상태는 관측할 수 없다(정지 중에만 생긴다). 같은 이유로 `:1` finalize를 한 Node(floor ≠ active)는 `:1`→`:3` successor에서 fail-closed다.
- **참고:**
  - workspace rolled-back Node는 막힌다.
  - Go `json.Marshal`의 HTML escape와 Python `ensure_ascii`가 다르다. ID에 비 ASCII나 `<>&`가 있으면 서명 확인이 fail-closed다.
  - batch는 nonce 하나를 같이 쓴다. member마다 서명과 scope로 묶이므로 받아들일 만하다.
  - `_install_files(rotation_publication)`은 strict parser가 아니라 `json.loads`를 쓴다.

## 내 실행

| 항목 | 결과 |
|---|---|
| owner focused 5개 파일, main `.venv` 3.14.7 `-B` | **119 passed, 6 skipped** (Windows symlink skip) |
| `test_fleet5_plain_peer_phase_v3` 범위 | 독립 generation, 알 수 없는 floor 6개 fault(nonce, signature, stale, cp-hash, overflow, expired-current), 예전 install·rollback 거부, generic guard 6개 상태, native gate, 잠금 직렬화 |
| 예전 lifecycle suite | **128 failed** (B2) |
| native | local Go가 없어 돌리지 않았다. hosted Core는 빨갛다 |

## hosted (21:55 KST, `6c0fc4ad`)

| run | 결과 |
|---|---|
| Core 42028616559 | **failure**. 성공으로 세지 않는다 |
| Docs 42028621267 | success (문서 gate만) |
| Portal Login 42028578349 | success (관련 없음) |

## 판정

- **`6c0fc4ad`: code NOT ACCEPTED, 수정 필요.** B1(native 빨강)과 B2(lifecycle `:3` 재증명 없음) 때문이다.
- M1~M9 계약 준수는 source 수준에서만 관측했다. 실제 CI와 physical 수락이 아니다.
- **Go P0 blocker는 그대로다.** 고친 후보가 native 두 cycle 녹색과 `:3` lifecycle 재증명을 낼 때까지 열려 있다.
- **CI:** 받아들인 것 없음. **physical:** 없음.
- `5023..6c0f`는 내 History와 Evidence를 바꾸지 않았다.
- 범위 밖: bootstrap G1~G10 plan(`ctx_ceec`). root가 21:14에 끈 예전 automation 3개는 다시 켜지 않았다(내가 검증하지 않음).

## 다음 첫 행동과 담당

- **`ctx_6f0f8253b8a7`:** proof hex nonce를 고치고 같은 native dispatch를 다시 돌린다. 128개 lifecycle test를 skip 없이 `:3`으로 옮긴다. `bd96` typed check를 field 단위로 합친다. F2와 F3의 운영 경로를 정한다.
- **root:** all-8, 최종 archive, deploy HOLD를 유지한다. Core 42028616559는 세지 않는다.
- **Claude:** 고친 후보가 오면 그 exact SHA의 delta를 검토한다.
