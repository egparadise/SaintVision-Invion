---
doc_id: "HISTORY-FLEET5-20261105-P0-PEER-PHASE-CONTRACT-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 P0 standalone plain-mode peer-phase 수리 계약 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T20:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "d06f93f7"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "architecture", "node-agent", "leaf-rotation", "claude"]
---

# P0 peer-phase 수리 계약 검토

Orca task `task_3529eefa626c`, dispatch `ctx_ba275b06ce0c`, 우선 요청 `msg_c811f47cc4a1`. 같은 task의 통합 후보 판정은 [[2026-11-05_20-10-00_KST_FLEET5_통합후보_9a8f와_1e64_검토_Claude]]에 따로 있다. 판정 요지는 20:1x KST에 structured status `msg_ab9e13adf7dd`로 먼저 보냈다. 이 문서는 그 판정의 기록이다.

- 대상: `agent/codex/fleet5-compute-storage-contract-20261105`의 `fe7ebeff1f695e0744a7f25eace52c7321dcc1d7`(probe)와 `5023ce7d72b7f13431cb6a7182e2677eb6926662`(보고)
  - `5023ce7d:docs/vault/30_Development/History/2026-11-05_FLEET5_compound_lifecycle_B_contract_Codex.md`의 "P0 standalone plain-mode repair proposal"
  - `5023ce7d:docs/vault/30_Development/Evidence/fleet5-compute-storage-contract-20261105-codex/proposed-contract-v1.schema.json`, `lifecycle-source-2fb.json`
  - `5023ce7d:docs/vault/30_Development/Evidence/fleet5-compute-storage-contract-20261105-codex/hosted-native-peer-phase/native-go-result.json`
- 범위: **최소 standalone P0 plain-mode 수리만** 본다. 넓은 B compound 설계는 받아들이지 않았다. S1 `ctx_4194506d5037`의 설계 의견은 내 판정에 넣지 않았다.
- 읽은 방식: Git object만 읽었다. 실행한 것은 없다(Go 미설치). native 결과는 작성자의 hosted 증명이며, 내 실행이 아니다.
- 하지 않은 일: production이나 source 수정, floor 약화나 state reset, physical·remote·CA·private key·host Docker·WSL 접근, 공유 board, Obsidian apply, 다른 agent 사용
- 기계 판독 결과: `Evidence/fleet5-20261105-claude/p0-peer-phase-contract-review.json`

## 1. 증명이 실제로 보여주는 것

- `5023ce7d:tests/proofs/fleet5_peer_phase_probe_test.go`는 실제 `transport` package 안에서 `node.OpenJournal`, `NewAuthority`, `authority.TLS`, `journal.PinPeerPolicy`를 쓴다. 입력은 `5023ce7d:tests/proofs/run_fleet5_peer_phase_probe.py`가 2fb `tools/lan_pilot.py` bytes로 만든 policy다. 대역(mock)이 아니다.
- `fe7ebeff`와 `5023ce7d`의 non-docs 추가는 proof test뿐이다. production 변경은 없다.
- `native-go-result.json`(Linux, Core 42014770700, 의도된 failure):
  - initial v7 받아들임
  - cycle-1 overlap v8 받아들임, final v8(다른 hash)은 `NODE-0041: peer policy rollback rejected`. floor는 overlap hash에 남는다
  - cycle-2 overlap v9 받아들임, final v9도 같은 거부
  - **만료된 v10은 "expired or unbounded"로 거부되지만 floor는 v10으로 남는다**
  - `attemptedNormalCycles=2`, `completedNormalCycles=0`
- 내 정적 분석과 일치한다: `tools/lan_pilot.py:2030-2049`, `2fb52bbe:deploy/lan/worker_leaf_rotation.py:199` `_policy`, `services/node-agent/runtime/journal.go:341-366`, `services/node-agent/transport/trust.go:67-93`, `services/node-agent/cmd/inv-node/main.go:88-108`.

**결론: P0는 확인된 기준선 결함이다.** 연속 rotation이 아니라 첫 정상 finalize부터 막힌다.

## 2. 판정

**ACCEPT-AS-ARCHITECTURE(제한적).** schema `:3`으로 peer policy version을 channel version에서 떼어 내는 방향은 맞다(overlap P+1, final P+2, channel C+1, Go floor 그대로). **구현 acceptance는 아니다.** 아래 M1~M10을 모두 갖춘 구현과 실제 Go 2 cycle 녹색이 필요하다. 그중 **M2, M4, M5, M10은 지금 해결되지 않은 blocking 항목**이다.

## 3. 반드시 필요한 guard와 field 결속

| id | 내용 | 상태 |
|---|---|---|
| M1 | `:3`은 새 SCHEMA와 정확한 key 집합이다. 2fb `:1` reader는 mutation 전에 `:3`을 거부해야 한다(지금도 SCHEMA·key 검사로 거부하지만 test가 필요). `:1`→`:3` successor 규칙을 명시한다 | test 필요 |
| M2 | **실제 floor 읽기.** Node 쪽에서 `<state>/.peer-policy` {`Version`,`Hash`}를 읽는다. lstat regular·symlink 아님·소유자=journal uid·mode 0600·크기 상한·정확한 key·bool이 아닌 int·64 hex. Go lock을 잡거나 경쟁하지 않는다(atomic rename 의미만 기댄다). 읽을 수 없거나 없으면 정상 rotation은 **BLOCK**한다. channel이나 CP 상태로 추정하지 않는다. `Version == currentPeerPolicyVersion`, `Hash == sha256(현재 active peer-policy.json bytes) == currentPeerPolicySHA256` | **blocking 설계 항목**: journal은 container uid 소유 0600이라 host operator Python이 읽는 경로와 인증 방식이 정해지지 않았다. 예: Node가 서명한 startup receipt로 floor를 보고(보고 추가일 뿐 약화가 아님) |
| M3 | strict int. P+2 ≤ 9007199254740991, overflow 확인, bool·float 거부. channel C+1은 독립 | 구현 필요 |
| M4 | **Go는 expiry 확인 전에 pin한다**(v10 증명). active policy를 쓰기 **전에** scope(tenant·node·epoch), version > floor, `now + margin < expiresAt ≤ now + 7d`(Go 한도, Node 시계 차이 포함)를 확인한다. 지금 leaf 최대 6일(`--leaf-valid-seconds` ≤ 518400)은 맞지만, 가정하지 말고 강제해야 한다 | **blocking** |
| M5 | **2fb worker `rollback()`은 기존 결함이다.** `2fb52bbe:deploy/lan/worker_leaf_rotation.py:1070`은 `installing`·`installed`·`restarted`·`rolled-back`에서 version P backup을 복원한다. 그런데 overlap P+1이 restart **또는** 연결마다 부르는 `Authorize`로 이미 pin됐다면, Go floor가 P를 거부해 Node가 시작하지 못한다. rollback은 실제 floor를 읽어 floor==(P, 예전 hash)일 때만 허용한다. 아니면 forward finalize나 별도 검토된 복구만 남는다. 모든 자동 실패 경로에도 같다 | **blocking** |
| M6 | Node가 서명한 install receipt는 관측한 이전 floor (P, hash)와 restart 뒤 pin된 (P+1, overlap hash)를 결속한다. CP commit receipt는 final P+2 hash를 결속한다. CP가 기록하는 node policy는 CAS 뒤에만 정확한 final bytes로 바뀐다 | 구현 필요 |
| M7 | finalized evidence·attestation·CP archive에 peer field가 들어간다. successor는 `new.currentPeerPolicyVersion/SHA == old final P+2 bytes`로 결속한다. 2fb의 exact-byte archive, `.next` 거부, retirement는 그대로 둔다 | 구현 필요 |
| M8 | batch preflight는 모든 member의 CP 기록 P == Node가 관측한 floor를 요구한다. 아니면 batch 전체를 거부한다(일부 subset 진행 없음) | 구현 필요 |
| M9 | 만료·부분·미상 상태는 BLOCKED로 두고 별도 검토된 offline 복구로 넘긴다. 새 +1 CAS 사다리, trigger jump, floor reset은 없다(root 결정과 같다). 미상 첫 pin은 forward replay만 허용한다 | 원칙 확정 |
| M10 | 포함 전 실제 Linux Go 2 cycle 녹색: 7→8→9, 다시 →10→11에서 final이 받아들여진다. 음성 case: 같은 version final, 쓰기 전 만료(Python이 거부), pin 뒤 rollback(거부), floor와 CP 불일치(거부) | **blocking** |

## 4. 운영 주의 (판정 아님)

예전에 `:1` finalize를 한 번이라도 실행한 Node는 이미 floor = overlap hash, active = final 상태라 restart하면 시작하지 못할 수 있다. root가 r5 기록을 **읽기 전용으로** 확인한 뒤 restart를 정해야 한다. 나는 아무 Node에도 손대지 않았다.

## 5. 통합 판정에 미치는 영향

- 9a8f와 1e64의 source 통합·artifact 판정은 **확인된 Go blocker를 진다.** 수리가 검토되기 전에는 정상 renewal runtime이나 Go NORMAL cycle을 받아들이지 않는다.
- CI와 physical acceptance는 없다. 42014770700 failure는 의도된 증명 결과이며 성공으로 세지 않는다.

## 다음 첫 행동과 담당

- **계약 owner `ctx_6f0f8253b8a7`:** M2의 floor 읽기 경로와 인증 방식을 먼저 정한다. 그다음 M1~M10대로 `:3`을 구현하고 실제 Go 2 cycle 증명을 낸다.
- **root:** r5 Node가 `:1` finalize를 거쳤는지 읽기 전용으로 확인한다. P0 구현 검토와 Go 녹색 전에는 all-8, landing, deploy HOLD를 유지한다.
- **Claude:** P0 구현 delta가 오면 독립 검토한다.
