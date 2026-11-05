---
doc_id: "HISTORY-FLEET5-20261105-LOW-CLOSURE-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 Codex Low-closure package 6cbb..af5b 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T16:32:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "087aaf35"
task_ids: ["FLEET5-FIRST-WAVE-PLAN-20261105"]
tags: ["fleet5", "independent-review", "leaf-rotation", "firewall", "known-hosts", "claude"]
---

# Low-closure package 6cbb..af5b 독립 검토

Orca task `task_3122a97a4fef`, dispatch `ctx_5301317b669b`. coordinator가 relay한 Codex `agent/codex/fleet5-low-closure-20261105`의 범위 `6cbb2b98..af5b68e62b0a9e2b724f28fda7676364efa95c31`(commit `095c284e`, `af5b68e6`)을 16:26~16:32 KST에 검토했다.

- 검토 대상: `History/2026-11-05_F5_low_closure_Codex.md`, 공개 overlay, 비공개 effective vector와 parameter
- 한 일: 정적 검토, hash 재계산, `59f0a3c2` source 대조, scratchpad에서 59f 회전 코드에 작은 probe 1개 실행
- 하지 않은 일: 넓은 test, 원격 실행, DB query, SSH, 인증 시도
- 기계 판독 결과: `Evidence/fleet5-20261105-claude/low-closure-af5b-review.json`
- 앞선 기록: [[2026-11-05_15-50-00_KST_FLEET5_보정packet_7dd8과_R4_ff97_검토_Claude]]

## 무결성

- 공개 overlay `low-closure-packet.json` blob: `e756c5fbbbcb346198c515dab20f9a20f223a98da0b47a463e0c74b7ba6d0748` 일치
- 비공개 vector: `b704cdca1eded05c89166da271d1c92d05715dcc14f2e7d0cbd1fc6db8e0cb5f` 일치
- 비공개 parameter: `2ebfa9e35958e1eeed76f015c33e82f1034e1a942caa171613e24c5bcb2f9037` 일치
- planned SQL: `bf0ef949…` 일치
- 그대로인 것: 원래 core vector `bee0f0f8…`, 59f archive `a9f0a3b8…`
- 원래 r5 `known_hosts.pinned`와 F5 사본 `known_hosts.f5.pinned`(8,807B)는 둘 다 `0dcbf0f4cfc363e4affc30810ad8a9e57bd2c4a31991e2c8285bdae7052ec2d2`로, 내가 다시 계산해서 같았다.
- F5 state, F5 private, F5 node-ca 폴더는 local에 없다.
- overlay 값은 다음과 같다. measured acceptance로 바꾸지 않았다.
  - `appendQueryExecuted=false`
  - `appendPendingCount=null`
  - `runtimeAccepted=false`
  - `fiveNodeAccepted=false`
- hosted Docs run 41986726559(`af5b68e6`)은 success다.

## Low 항목별 판정

| 항목 | 판정 | 근거 |
|---|---|---|
| H1 문구/`-B` | 해결 | main History 1.1.2의 step 4는 "non-r5 main `.venv` Python 3.14.7, `-B`, inherited `PYTHONDONTWRITEBYTECODE=1`, no pip"이고, step 5의 bundle 명령에도 `-B`가 들어갔다. 문서만 바뀌었다. |
| F5 전용 strict known_hosts | 해결 | effective vector의 `UserKnownHostsFile`은 모두 `…/f5-low-closure-26607075f612/known_hosts.f5.pinned` 하나다. r5 known_hosts 경로와 r5 venv 경로는 0번 나온다. ssh 3회, scp 2회 모두 `StrictHostKeyChecking=yes`와 `UpdateHostKeys=no`다. 원래 파일과 사본의 전후 hash는 같고 ACL exit는 0이다(receipt 기준). transport 전후로 원래 파일과 사본을 모두 확인하고, 다르면 멈추는 규칙도 맞다. |
| 재부팅/firewall 재적재 시 증명 무효화와 attended-only | 해결 | 무효화 사건 목록(재부팅·boot identity, firewall reload, Docker/backend/network 재시작, 규칙·순서·hash 변경, 알 수 없는 이력), publish·resume 전 재확인, 동시 성공/거부 증명, attended-only, session 끝에 F5 Node 정지가 모두 들어 있다. `unless-stopped` container는 수동으로 멈춘 상태면 재부팅 뒤에도 다시 시작하지 않으므로 "session 끝에 정지" 규칙이 효과가 있다. **남은 위험(받아들일 수 있음):** attended session 도중에 예정에 없던 재부팅이 나면 Node가 자동으로 재시작해 규칙 없이 18515를 publish할 수 있다. 그때도 mTLS는 유지되고, 계약은 그 사건을 무효화와 격리로 다룬다. |
| prepared/staging/staged/switched/terminal/orphan 분류 | 해결(source와 일치) | 59f의 `_load_batch_journal`이 허용하는 phase는 정확히 `{prepared, staging, staged, switched}`다(`lan_pilot.py:1554`). 폐기 기록은 schema `saintvision-lan-abandoned-prepared-batch:1`, `phase="prepared"`, 파일 `leaf-rotation-abandoned-<batchId>.json`이다. 그래서 "파일 이름이나 phase만으로 닫지 않는다"는 규칙이 맞다. 임시 쓰기 파일은 `<name>.next`이므로 orphan 처리 대상과 맞다. CP lock(`exclusive_file`)과 Node lock(`_exclusive`)은 O_EXCL로 만들고 끝나면 unlink한다. 따라서 "lock 없음"은 "보유자 없음"을 뜻하고, 남아 있는 lock은 crash 흔적이므로 BLOCK이 맞다. |
| read-only snapshot gate | 해결 | SQL은 `REPEATABLE READ READ ONLY`, `SHOW transaction_read_only`, transaction 범위의 `set_config('inv.tenant_id',…,true)`, `ROLLBACK` 순서다. 테이블과 열은 59f schema와 일치한다. `inv.control_epoch.epoch`는 `0001_core.sql:4`에 있다. `inv.node_channels`의 `node_id, recovery_epoch, version, certificate_sha256, certificate_not_after, enabled, endpoint`는 `0005_node_channels.sql`에 있고 FORCE RLS다. batch 수를 SQL COUNT가 아니라 파일 분류기로 구한다고 적은 것도 맞다. query는 실행하지 않았고 수는 null이다. 이 구분을 지켰다. |
| CA custody | 해결 | `rootOnline=true`, `rootOffline=false`, `CAExistsNow=false`가 명시돼 있다. |
| stage 판정 | 일치 | stage03 HOLD(Core 실패, 원인 미증명), 05/09 init/enroll HOLD(P2 operator 날짜), publish/observe BLOCKED, append HOLD. root의 판정과 같다. |

## 새 발견: Node가 연속 정상 rotation을 할 수 없을 가능성 (Medium, unit probe로 확인, live 아님)

59f `deploy/lan/worker_leaf_rotation.py`의 `install()`을 보면 이렇다.

- Node journal `leaf-rotation.json`이 있고 superseded bundle이 없으면, identity 비교(`rotationId`, `proposalDigest`, `targetChannelVersion`)가 다를 때 무조건 `"Another leaf rotation or stale channel version is already journaled"`를 낸다(568~569행).
- `finalize()`는 journal을 `phase="finalized"`로 **남겨 둔다**(672~674행).
- journal을 치우는 코드는 만료 supersession 경로(`_supersede_expired_journal`, 505행)뿐이다.

probe 내용(16:30:45 KST, 59f export, main `.venv` `-B`):

1. 59f test fixture로 `install`을 실행한다.
2. journal을 `finalize`가 쓰는 값과 똑같이 `finalized`, `restartRequired=false`로 바꾼다.
3. `rotationId`만 다른 bundle로 다시 `install`한다.

결과는 바로 그 오류였다. 59f test에는 restarted 상태에서 거부되는 경우만 있고, 정상 rotation 2회 연속을 다루는 test는 찾지 못했다.

이 결과가 맞다면 영향은 다음과 같다.

- F5는 leaf가 6일이고 NotAfter 48시간 전에 renewal하므로 약 4일마다 rotation한다. 각 Node의 **두 번째 정상 renewal이 막힐 수 있다.**
- Low-closure의 historical-closed 규칙은 Node 쪽 finalization 증거에 기댄다. 그 증거는 Node마다 `leaf-rotation.json` 하나뿐이고 다음 rotation이 그것을 다룬다. 그래서 F5 registry가 finalize 시점에 각 Node의 finalized journal 사본을 hash로 고정해 두지 않으면, 지난 batch가 UNKNOWN이 되어 append가 계속 BLOCK될 수 있다.

**판정 범위:**

- unit 수준에서 합성한 phase로 확인했다. live 확인은 아니다.
- 다음 rotation 전에 finalized journal을 정리하는 운영 절차가 다른 곳에 있는지는 찾지 못했다.
- r5에서 같은 Node가 정상 rotation을 2회 해 본 실적이 있는지는 확인하지 않았다.
- 이 발견은 Low-closure package의 결함이 아니다. 59f source에 대한 질문이다.

**권고:**

- root가 별도 source 조사를 맡긴다. 그 작업에는 정상 rotation 2회 연속 test와, 필요하면 finalized journal을 archive하는 경로를 넣는다.
- 그동안 F5 renewal 계획에는 "각 Node의 두 번째 renewal은 증명 전까지 HOLD"를 넣는다.
- Low-closure의 snapshot registry에는 finalize 시점의 Node journal 사본 고정을 넣는다.

## 판정

**Low-closure package `6cbb..af5b`는 ACCEPT(문서와 nonexecuting 계약으로서)다.** H1, F5 known_hosts, firewall re-proof와 attended-only, 분류기, read-only gate가 모두 source와 맞고 bytes도 확인했다. 앞으로 측정할 gate를 측정된 acceptance로 쓰지 않았다. 별도로 위의 Medium source 발견 1건이 있다.

이번 relay에서 받은 정보는 기록만 하고 판정하지 않았다.

- stage03 HOLD(Core 실패)와 init/enroll HOLD는 root가 유지한다.
- source DB task `58f4`는 별도로 진행 중이다.
- guard source `30f1`(087 accepted)의 Core attempt2와 no-socket test Low는 아직 남아 있다.
- worker4: 창 제목은 있지만 Computer Use의 Chrome 내용 읽기가 거부되어 endpoint 정보가 없다. 인증 시도나 우회는 없었다.

## 다음 첫 행동과 담당

- **root:** 이렇게 진행한다.
  - Low-closure: ACCEPT 판정을 반영한다.
  - 연속 rotation 발견: 59f source 조사 task를 별도로 배정한다(owner 지정 필요). 결과가 나올 때까지 F5 각 Node의 두 번째 renewal을 HOLD로 둔다.
  - 기존 판정: stage03, init/enroll, P2 HOLD를 그대로 유지한다.
- **Codex:** snapshot registry에 finalize 시점의 Node journal 사본 고정을 추가할지 검토한다.
- **Claude:** no-socket test, DB source, 연속 rotation 조사의 exact delta가 오면 따로 검토한다.
