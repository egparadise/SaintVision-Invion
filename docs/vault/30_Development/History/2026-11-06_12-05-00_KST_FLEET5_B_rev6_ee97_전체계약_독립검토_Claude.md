---
doc_id: "HISTORY-FLEET5-20261106-B-REV6-EE97-WHOLE-CONTRACT-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 B rev6 ee97 전체 결합 계약 delta 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T12:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "ee97c27a5d135a4059256124290731cd2b791193"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105"]
tags: ["fleet5", "independent-review", "b-contract", "design", "claude"]
---

# B rev6 ee97 전체 결합 계약 delta 독립 검토

Orca `task_98d80a7c3d96`, dispatch `ctx_6b02886ebfc1`의 실제 독립 검토다. owner는 Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`이며 owner 질문 `msg_4b5c1d55aea3`은 Root 결정 전까지 pending이다.

- 대상은 `ee97c27a`이고 부모는 `228e2a20`이다. remote ref가 정확히 일치한다.
- Docs `42150067167`(job `127670869695`, workflow_dispatch, attempt 1)은 19/19 step 모두 성공했다. 이것은 내가 `gh run view`로 다시 확인한 결과다.
- 제품 diff는 72028 대비 0이다. 228e 대비로도 own Evidence/History 바깥의 diff는 0이다.
- 직전 실제 검토는 `8bac0838`(Docs `42137554199`)이고 판정은 B5-M1/M2와 L1–L5였다.
- Root 결정 JSON(`580b79f9…`)과 Gov v1.4.0(`089e0003…`)은 읽기만 했다. Root worktree는 checkout하거나 수정하지 않았다.

**판정: REVISION_REQUIRED.** 범위는 Root가 고른 해결책 아래의 전체 B 설계 계약(DESIGN 축)이다.

- **blocking:** B6-M1, B6-M2.
- **grant 전 수정 필요:** B6-L1~L4.
- **Info:** B6-I1, B6-I2.
- partial freeze, code grant, runtime acceptance는 없다.
- 상세 내용은 `docs/vault/30_Development/Evidence/fleet5-b-rev6-ee97-review-20261106-claude/review.json`에 있다.

## 이전 지적별 종결 상태

| 이전 | 상태 | 남은 것 |
| --- | --- | --- |
| B5-M1 | 부분 종결 | B6-M1. effect class와 scope 구분이 없어 OP 전용 복구와 Node 전체 거부가 생긴다. |
| B5-M2 | 부분 종결 | B6-M2. 기본 분류 bucket이 fail-open이다. |
| B5-L1 | 부분 종결 | B6-L1 |
| B5-L2 | 부분 종결 | B6-L2, B6-I1 |
| B5-L3 | 설계 종결 | 서명 starvation(A10)은 B6-M1에 포함했다. |
| B5-L4 | 설계 종결 | INVALIDATE 송신 실패 후 OP 복구 문제는 B6-M1에 포함했다. |
| B5-L5 | 설계 종결 | 문구 drift는 B6-L4다. |

### 수용한 부분

- CommittedIOHandle에는 capability가 없다. 같은 hash로 위조한 handle은 거부된다.
- commit이 증명된 뒤에만 IO가 나간다. 원래 요청의 body, path, nonce, claim 치환은 거부된다. send는 handle당 1회다.
- poison 또는 persistence-unknown이면 PENDING 또는 UNCERTAIN으로 남는다. restart 후 capability를 재구성할 수 없다.
- ACTIVE observation은 claim을 그대로 둔다. terminal release는 원래 receipt 경로로만 일어난다.
- 오답 목적, 다른 operation, 중복 응답은 거부된다.
- 직교 denial fact가 drain을 보존한다.
- 다른 Node, tenant, epoch의 obligation은 이 Node의 admission을 막지 않는다.
- 13 reader의 exactLine이 72028과 일치한다.
- 서명 service는 내부에서 전체 chain을 읽고, 조건부 publication 전에 version을 다시 확인한다.
- unsigned CP tombstone과 INVALIDATE outbox가 있다. SAFE/REV는 invalidate만 할 수 있고, 다른 Node 대상이나 outbox를 통한 ARM은 거부된다.
- plain activation은 owner와 not-revoked만 확인한다. B-only FolderRootObservation은 닫힌 schema이고 1회용이며 30초 만료다.
- 46 surface, R4 guard, plain floor2/leaf3는 그대로다.

## Blocking

### B6-M1 — IO obligation lifecycle이 효과 종류와 scope를 구분하지 않는다

16개 kind에 같은 실패 규칙이 적용된다. 그 결과 읽기 전용 관측의 실패도 OP 전용 복구가 된다.

1. **A1 heartbeat timeout:** heartbeat 하나가 timeout되면 UNCERTAIN이 된다. 13 reader가 모두 거부한다. 다음 heartbeat가 성공해도 회복되지 않는다. OP의 physical proof로만 풀린다.
2. **A1b in-flight:** 실패하지 않아도 heartbeat가 진행 중인 동안 Node 전체의 admission이 거부된다.
3. **A2 renewal:** heartbeat timeout 후에는 같은 config의 renewal 서명도 거부된다. Node가 만료로 흘러갈 수 있다.
4. **A10 서명 starvation:** 준비된 ARM 서명이 있을 때 같은 Node에 관측 하나만 등록돼도 publication이 None이 된다. 등록이 authorityVersion을 올리기 때문이다.
5. **A3 single flight:** 같은 Node에서 두 번째 EXECUTE가 거부된다. plain profile도 같은 reader/procedure를 쓰므로 72028의 동시 lease 동작이 선언 없이 바뀐다.
6. **A5 다른 Node까지 번지는 fence:** node-1의 fuse 영속화가 실패하면 completion authority 전체가 fence된다. node-2의 정상 성공이 거부되고, restart 후에는 node-2도 OP가 필요하다.
7. **A4 drain 중 terminal:** DRAIN 상태에서 terminal frame을 등록할 수 없다. 그런데 72028 `terminal.py:78`과 catalog R12는 이를 허용한다.

**Root 선택이 필요하다.** 대안은 세 가지다.

- **A(권장):** kind별 effectClass를 둔다.
  - SIDE_EFFECT는 protected settle을 유지한다.
  - IDEMPOTENT_SAFETY(CANCEL, QUARANTINE_RECONCILE, B_GATE_INVALIDATE)는 정확한 command hash의 ACK나 readback이 있으면 일반 경로로 닫는다.
  - READ_ONLY는 실패하면 일반 경로의 NO_EFFECT_ABANDONED로 닫는다. UNRESOLVED에도 넣지 않고 anchor version도 올리지 않는다.
- **B:** obligation은 Root가 명시한 side-effect 지점에만 등록한다.
- **C(비권장):** 현행대로 둔다.

함께 고쳐야 할 것이 세 가지 있다.

- fence는 해당 operation의 capability로 좁힌다.
- PENDING의 admission 범위를 Root가 정한다. 겹치는 claim/resource만 막거나, Node 전체 single flight를 plain 동작 변경으로 명시한다.
- continuation kind는 정확히 claim된 operation이나 parent handle을 기준으로 등록한다.

### B6-M2 — 분류가 fail-open이라 "unjustified blocker 0"이 실제 실현 가능성이 아니다

`NONAUTHORITY_UNRESOLVED_EXTERNAL_BACKLOG` bucket에는 provenance가 없다. 이 bucket은 closure에서도, blocker에서도 빠진다. 전체 call site 47,608개 중 29,573개가 여기에 들어간다.

- **실제 72028 반례:** `shard_recovery.py:179`의 tuple unpack 다음 `:186 runs.transition`(run 상태 writer)이 누락된다. 그런데도 ShardRecovery.prepare는 SUPPORTED로 표시된다. 단일 대입으로 바꾼 대조 C1b는 정상적으로 resolve된다.
- **critical 4개의 외부 transaction 미기록:** `self.db.transaction`이 transaction owner로 기록되지 않는다. 해당 위치는 observation.py:52/:139, results.py:164, shard_completion.py:46이다. 이런 미해결 transaction 호출이 모두 107개다.
  - owner의 runtime fixture는 synthetic `Database(...)` literal이 있을 때만 통과한다.
- **dynamic dispatch 누락:** dict dispatch(C4)와 타입 없는 주입 receiver(C7)가 BLOCK이 아니라 backlog로 분류된다.
- **반대로 과잉 BLOCK:** 28개 BLOCK 중 9개는 dataclass 값 객체 생성자, 3개는 `in_transaction` 조회다.
  - 이 때문에 plain API인 post_heartbeat, enroll_node, register_contribution이 일반 사유 하나로 UNSUPPORTED가 된다. scope, binding, future work 기록도 없다.

수정 방향은 다섯 가지다.

- 미해결 receiver의 기본값을 UNRESOLVED로 바꾸고, 영향받는 plan에 인과적으로 연결한다.
- tuple/starred 대입, 생성자 주입 속성, module alias 생성자, runtime()을 resolve한다.
- dict dispatch는 BLOCK으로 분류한다.
- 남은 unknown마다 scope, binding, futureWork, blocksGrant를 기록한다.
- 실제 source fixture를 추가한다.

## Grant 전 Low

- **B6-L1:** 26 mutant 밖의 반례가 있다. 현재 72028에서는 발견되지 않았다.
  - `%` format과 문자열 연결로 만든 동적 식별자가 STATIC_NAMED_SCOPE로 처리되고, audit도 침묵한다. Root가 명시적으로 금지한 경우다.
  - `query().update({...})`와 `bulk_update_mappings`에서 writer가 누락된다.
  - 같은 SQL에 xact lock과 session advisory lock이 함께 있으면 TRANSACTION으로 오분류된다.
  - from/to semantic check는 함수명 약 10개에만 hard-code되어 있다.
- **B6-L2:** 39개 join 중 12개에서 procedure가 FOR SHARE를 잡은 뒤, 감싼 원본 본문이 FOR UPDATE를 잡는다. 그 결과 같은 Node의 두 entry가 upgrade deadlock에 빠진다. entry별 병합 lock list와 upgrade 금지 check가 필요하다.
- **B6-L3:** IO anchor 4개의 줄 번호가 틀렸고, artifact의 function field 자체에 불일치가 드러난다. 실제 호출 경계도 빠졌다: observation:119/124, buildkit_transport:855/978, model_remote:98, node_transfer:43, terminal:277, storage_check_collect:309, storage_commit:398.
- **B6-L4:** plan_specs의 `_owned_for_update`에 "activation still requires Node folder confirmation" 문구가 남아 있다. 이 문구가 critical plan에 1회 포함되어 Root의 L5 정정과 충돌한다.

## 재현과 한계

owner 스크립트 결과는 모두 owner 기록과 일치했다.

- schema.py, authority.py, fixtures.py(547), R4 probe는 exit 0이었다. `--require-coexistence`는 예상대로 exit 1이었다. 출력 hash도 owner `proof-checks.json`과 같았다. 실행 후 git status는 clean이었다(byte-identical).
- source-analysis.json은 1 MiB chunk로 streaming만 했다.
  - 크기 74,373,915 byte, sha256 `19944f32…`, blob `33a43ad0`이다. source-command-record와 일치한다.
  - 523 files, 1669 records, 632 plans(464 supported/168 unsupported), 21 critical, 28 unknown, 63 SQL issue를 재현했다.
- prior review 9개 파일과 old snapshot 4개는 blob 단위로 동일하다.

다시 실행하지 않은 것도 있다.

- 11:48 KST 측정에서 available RAM이 190–356 MB였다. 그래서 source_analysis, reconcile, source_fixtures, link_plans 전체 재실행은 하지 않았다. 대신 실제 72028 파일 5개를 subset으로 잡아 probe 9개를 돌렸다.
- run_checks.py, PG, Docker, Node, crypto, crash, 장비, Obsidian apply는 수행하지 않았다.
- 실제 신규 B Go/crypto/PG/Engine/crash/concurrency/equipment 증거는 0이다. 모든 real binding은 NULL/HOLD이고 A1–A16은 PENDING이다.

## 다음 첫 행동과 담당

1. Root가 B6-M1의 effect-class 대안(A/B/C)과 PENDING admission 범위를 정한다.
2. 그 다음 Codex가 rev7 DOCS/schema/static delta에서 B6-M1/M2와 L1–L4를 닫는다.
3. 이후 별도의 실제 Claude 검토가 진행된다.

구현 grant 후보 범위와 runtime CI 요구 사항은 review.json `nextImplementationScopeIfRevisedAndAccepted`에 정리했다. reviewer는 grant를 부여하지 않는다.
