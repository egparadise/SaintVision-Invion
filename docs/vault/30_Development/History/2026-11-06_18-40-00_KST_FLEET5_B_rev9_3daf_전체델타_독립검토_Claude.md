---
doc_id: "HISTORY-FLEET5-20261106-B-REV9-3DAF-WHOLE-DELTA-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 B rev9 3daf 전체 delta 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T18:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "3daf1a0d24c220586474a4b376609e62960b8ca6"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105", "FLEET5-B-REV9-T1-20261106"]
tags: ["fleet5", "independent-review", "b-contract", "design", "claude"]
---

# B rev9 3daf 전체 delta 독립 검토

Orca `task_522bf43089d4`, dispatch `ctx_de2750e94f9d`에서 수행한 실제 독립 검토다. owner는 Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`이다. owner 질문 `msg_ae8b4176e148`은 Root가 답할 때까지 pending이다. 선행 combined 검토 `task_b234a0f9df1a`(`7d979761`)는 착수 전에 이미 완료되었다. 그 검토의 결과와 CI는 이 검토에 쓰지 않았다.

- 대상은 최종 `3daf1a0d`이고 base는 `6a656658`이다. remote ref는 정확히 일치한다. 6a65 대비 추가된 경로는 86개(Rev9 Evidence 85 + History 1)이고, 수정·삭제된 경로는 없다. 72028 대비 docs 밖 diff는 0이다.
- owner Docs `42191613681`을 `gh`로 직접 다시 확인했다. job `127804769842`, workflow_dispatch, `.github/workflows/docs.yml`, attempt 1, correlation `fleet5-rev9-t1-task_a8fd2969f0b3-3daf…`, 19/19 step 성공이다.
- 읽은 것: Root 결정 `b-rev9-t1-root-scope.json`(`msg_78b82487362a`), 직전 실제 검토 `0440d1ca`, Rev9 코드와 산출물 전부. 72028 원문도 직접 읽었다: terminal.py, observation.py, db.py, containment.py, node_channels.py, node_transport.py, observer_worker.py, lan_pilot.py.
- Root는 그 사이 `05b8d2bc`(Index 1.0.452)로 진행했다. 여기에는 provenance로만 기록한다.

**판정: REVISION_REQUIRED (bounded, narrow).**

- blocking: B9-M1, B9-M2.
- 재사용 전 수정: B9-L1.
- Info: B9-I1~I6.
- B8-M1, B8-L3, B8-L2는 이번 cut 범위에서 닫혔다. B8-L1은 부분 종결이고, 남은 부분은 B9-L1로 넘겼다.
- 상세: `docs/vault/30_Development/Evidence/fleet5-b-rev9-3daf-review-20261106-claude/review.json`.

## 이전 지적별 상태

| 이전 | 상태 | 확인한 것 |
| --- | --- | --- |
| B8-M1 | matched-claim 결함과 BUILD_CLEANUP_READ 분리는 종결. 남은 Node 상태 parity는 → B9-M1 | 검토자 공격 102건(PLAIN/B). 원 EXECUTE와 CANCEL receipt로 claim별 tombstone이 된다. 다른 claim이 있든 없든 같다. 다른 claim의 rights와 version은 바뀌지 않고, 그 claim의 frame은 여전히 허용된다. 재승인된 claim에서 옛 parent는 거부되고 새 parent는 허용된다. prepare 후 lease가 만료되거나 now+5에 도달하면 거부된다. rights version 불일치, 비EXECUTE parent, verifier 재시작, cross-node는 모두 거부된다. Node boolean은 대체 근거가 되지 않는다. recovery ACK는 claim을 release하지 않는다. 이중 release가 없다. tombstone 뒤에도 CANCEL identity를 조회할 수 있다. UNKNOWN parent 상태는 유지된다. cleanup read 쪽: 현재 인증 필드, read grant 폐기와 prepare 후 만료, 잘못된 purpose, EXECUTE parent fixture는 모두 거부된다. QUARANTINE 중 read는 상태를 바꾸지 않는다. UNKNOWN parent를 settle하지 않는다. TERMINAL_CLEAN label은 거부되고 claim은 그대로다. cross-node와 중복 op는 거부된다. lineage tombstone은 observe 폐기로 취급되지 않는다. owner regression을 재현했다: exit Rev7 1, Rev8 1, Rev9 0(raw defect true/true/false). |
| B8-L3 | 종결 | owner의 필드별 음성 시험에 더해 확인했다: liveness, grantLive, expiresAt, cert, cross-node 연결은 AUTHORITY_DENIED다. 재시작하면 자기 Node만 UNKNOWN hold이고 다른 Node는 영향이 없다. missing scope는 상태를 바꾸지 않는다. 위조 footprint는 무시된다. lineage tombstone이면 business는 denied다. 어느 경우에도 version이나 fact가 바뀌지 않았다. |
| B8-L1 | 부분 종결 → B9-L1 | Rev8에서 지적한 형태는 모두 producer sanity를 통과한 뒤 거부된다. 원래 16-case script는 blob `2b2837af`로 바뀌지 않았다. script가 보고하는 나머지 3건은 owner 설명이 맞다. ① 옛 test를 재구성한 결과라 구조상 항상 HASH_MISMATCH가 나온다. ② caller 항목은 predicate 호출 없이 구문만 단정한다. ③ 미바인딩 `field`는 import 시 NameError가 난다. Root는 정확한 import를 요구하고, 정상 import positive는 통과한다. 새 harness는 실제 predicate를 호출한다. |
| B8-L2 | 종결(이번 cut 한정) | 6 ref/14 row의 file hash와 expression hash가 72028과 일치한다. 모두 blocksGrant=true, binding null이다. OneConnection.connect의 9개 IO link는 NodeTLSClient 메서드의 production caller 전부를 덮는다(git grep). 재계수: 598 row 중 touched 25, outside 573. fallback은 227에서 9를 빼 218이 UNREVIEWED backlog다. 전역 분류 종결은 아니다. |

## 새 지적

- **B9-M1 (MEDIUM, Rev7부터 유지, 97bb와 0440 검토가 놓침): TERMINAL_FRAME lane에 실제 `terminal._current`의 Node 상태 조건과 tenant 실행 조건이 없다.**
  - 실제 72028 `_current`:
    - :65 `require_execution`(tenant kill_switch).
    - :76-84 node status ∈ {online, draining}.
    - `frame()`은 :229에서 `_current`를 호출한 뒤 :275에서 `snapshot(observation_only=True)`를 호출한다. 이 snapshot은 status/heartbeat를 보지 않는다.
  - 모델 `_terminal_parent_current`와 register/invoke는 `liveness`를 보지 않는다.
  - 반례(PLAIN/B): parent EXECUTE를 invoke한 뒤 Node를 offline으로 둔다(실제 `mark_offline` 동작이며, lease는 반환되지 않는다). TERMINAL_FRAME register와 invoke가 성공한다. prepare 뒤 offline이 되어도 invoke가 성공한다. 같은 frame에 대해 모델 자신의 R12 `eligible()`은 False를 낸다. Rev7과 Rev8 모델도 같다.
  - 해결:
    - frame lane의 register/invoke/confirm에 `projection(n) ∈ {online, draining}`과 tenant 실행 containment를 추가한다.
    - offline(register 전/prepare 후), draining positive, tenant stop 회귀를 PLAIN/B로 추가한다.
    - cleanup/CANCEL/RECEIPT lane은 바꾸지 않는다.
- **B9-M2 (MEDIUM): narrow A8의 "모든 production NodeObservation.db chain"에 `tools/lan_pilot.py` observe root가 빠졌다.**
  - 실제 :3945 `ObservationWorker(runtime(state), …)`가 있고, :902-903 `runtime`은 `Database(...)`를 반환한다. owner도 lan_pilot:903을 production Database site로 센다.
  - `t1_provenance`는 ObservationWorker 호출 site를 열거하지 않는다.
  - 반례: lan_pilot 한 곳만 `ObservationWorker(object(), …)` 또는 `foreign_database`로 바꾸거나, `runtime = foreign_runtime`을 덧붙인다. owner provenance는 여전히 `SOURCE_PROVEN_RUNTIME_PENDING`이고 union은 `{Database}`이며, mark_offline A1c도 증명된다.
  - 실제 bytes에서 결론 {Database}는 참이다. 하지만 기록된 closure 증명이 이를 증명하지 못하므로, 지금 쓰인 SOURCE_STATIC_CLOSED 주장은 정당화되지 않는다. runtime/grant 영향은 없다.
  - 해결:
    - ObservationWorker 호출 site를 모두 열거한다. production은 observer_worker:58, lan_pilot:3945이고 harness는 test_node_extensions:47이다.
    - lan_pilot.runtime이 `Database`를 반환하는 단일 local def이고 다시 바인딩되지 않음을 묶는다(remote_workspace_entry.database와 같은 형식).
    - expected chain을 손으로 쓴 dict 대신, 경로 위 생성자 caller census에서 도출하도록 권고한다.
    - 이것은 미뤄 둔 A7(모듈 간 import)이 아니다.
- **B9-L1 (LOW, 재사용 전): 강화된 A1c/A8/A2 변이 검사가 형태별 denylist라서 빠지는 형태가 있다.**
  - 새로 reparse/rebase하고 producer sanity가 통과한 상태에서, owner pipeline이 다음 48개 형태를 받아들인다.
    - 수신자 escape: `foreign(c=conn)`, `[conn]`, `*[conn]`, lambda capture, dict box, `foreign.attach(conn=conn)`, `foreign(conn.execute)`. 수신자 3개 모두에서 같다.
    - owner patch: mark_offline 또는 `__init__` 안의 `self.db.transaction = foreign`, `self.db.__class__ = foreign`, `vars(self.db).update(...)`. 그리고 `from .db import Database as _D; _D.transaction = foreign`.
    - root site에서 `Database(...)` 생성 뒤 다시 대입: `db.transaction`, `db.statement_observer = socket`, `db.placement_metric_sink = subprocess`.
    - `import psycopg as _pg` 또는 `from psycopg import Connection as _PC` alias를 거친 `.execute =`.
    - `_ObservedConnection`에 대한 `builtins.setattr`, `type.__setattr__`, `globals()[...]`.
    - A2: class 정의 전 `builtins.Exception = foreign`. DomainError에 대한 `type.__setattr__`, `builtins.setattr`, `globals()`. caller의 `from . import errors as _e; _e.DomainError.__init__ = foreign`.
  - 직접 형태의 대조군은 거부된다: `foreign(conn)`, `conn.__class__.execute =`, `Database.transaction =`, `psycopg.Connection.execute =`, `DomainError.__init__ =`.
  - 실제 입력 10개 파일에는 이런 형태가 없다. 있는 것은 lan_pilot:4258의 `globals()` command dispatch뿐이다. 따라서 실제 16 edge closure에는 영향이 없다.
  - 해결: denylist를 use-site allowlist로 바꾼다.
    - 증명된 수신자를 Load하는 곳은 기록된 execute/fetch*/cursor 호출의 수신자이거나 with-as 바인딩이어야 한다. 그 밖의 Load는 거부한다.
    - import alias는 보호 class 집합으로 해석한다.
    - owner instance(`self.db`, root `db`)를 root로 갖는 Attribute Store/Del은 거부한다.
    - setattr, `__setattr__`, globals(), vars(), `__dict__`는 철자와 무관하게 거부한다.
    - A2: builtins 재바인딩과 모듈 alias 경로를 거부한다.
    - 이 형태들을 span-shift 음성 시험으로 추가한다.
- **Info:**
  - I1: tombstone이 (claim, admittedClaimVersion, attempt)에 대한 CAS가 아니다. receipt도 이 두 값을 묶지 않는다. fixture 전용 probe에서는 늦게 온 receipt가 새로 seed된 rights를 tombstone한다. register로는 도달할 수 없다(PENDING overlap이 막는다). 방어 심층화 차원에서 권고한다.
  - I2: lifecycle.py:249-251은 도달 불가능한 코드다.
  - I3: release 뒤에 늦게 도착한 frame 확인은 fail-closed로 처리된다. row는 UNCERTAIN, cap은 POISONED가 되고, 같은 Node의 모든 admission이 protected settle 때까지 hold된다. 정상적인 종료 race가 Node를 막는다. 이 경우의 settle 경로를 명시하는 것이 좋다.
  - I4: lock 안의 statement observer 호출이 named RUNTIME_PENDING row가 아니고 note로만 남아 있다.
  - I5: harness 목록이 grep 두 개로만 만들어졌다. tests의 NodeObservation/ObservationWorker 생성이 빠져 있다.
  - I6: 검토자 자신의 Rev8 probe는 잘못된 경로를 받으면 script 옆의 모델을 조용히 import한다.

## T1 판단

- 19 edge는 불변 functionPlans(`7d650fbe…`)의 mark_offline remaining과 정확히 같다. 구성은 A1c 2+3, A2 4, A3 4, A5 1, A8 attr 2이고, P-DBROLE 1과 T1-OBSERVABILITY 2는 pending이다. Root scope의 줄 번호와 일치한다.
- 실제 bytes 기준 positive는 모두 맞다: A1c 5, ContextVar, local list, DomainError, observed union.
- SOURCE_INPUT_DISAGREEMENT 가드는 실제로 동작하는 가드다.
- 명시된 runtime pending은 거부 사유가 아니다: P-DBROLE, READ COMMITTED/SET LOCAL/timeout, lock trace, clock cutoff, log handler, B role/auth/cutover.
- 출력 형태(SOURCE_STATIC_CLOSED_RUNTIME_PENDING, notGrantable, 12 entry, upgrade 0)는 맞다. 다만 B9-M2를 고치기 전에는 closed 주장이 정당화되지 않는다.

## Root를 위한 다음 cut (구체)

1. **Rev9b (fix-only):** 같은 Codex owner, reviewer는 Root를 거친 Claude delta 검토. base는 `3daf1a0d`이고 DOCS/static/symbolic 범위다.
   - 처리할 것: B9-M1, B9-M2, B9-L1(+선택 I1).
   - 바꾸지 않을 것: T1 19 edge, 12 entry, 598/757/1071/21, 573, 218, 모든 실제 binding NULL.
2. **Rev9b 수용 뒤 A7 cut:** owner 제안을 **NodeChannels.snapshot 하나로** 좁힌다.
   - entry: node_channels.py:124-149. terminal:275의 observation_only frame과 node_transport:264 deliver가 공유한다.
   - subgraph:
     - Database.transaction은 T1의 hash로 재사용한다.
     - `require_execution` containment.py:15-18 (A1c + A2).
     - fetchone 2건(inv.nodes FOR SHARE + clock_timestamp, inv.node_channels).
     - `proof()` ChannelProof :84-101 (A2 dataclass 변형).
     - `assert_channel` :104-117.
     - observation_only branch의 의미(kill switch와 online/heartbeat 생략)를 정확히 기록한다.
   - A7: `from lan_pilot import runtime`(lan_execution.py:19, check_remote_workspace.py:21) → lan_pilot.runtime:902-903.
   - A8: NodeChannels( site 전수 census.
     - build_product_runtime:532
     - node_transfer:18
     - node_transport:231
     - observation:14
     - terminal:275 (workspace.db)
     - check_remote_workspace:116
     - lan_execution:83/137/172
     - remote_workspace_entry:205
     - BoundDatabase가 나오면 union {Database, BoundDatabase}로 증명한다. {Database}로 강제하지 않는다.
   - 제외: NodeDelivery.deliver(T2 exchange, NodeReceiptStore, GPU quarantine writer, event)는 다음 cut으로 미룬다. 전체 A8과 assembler도 제외한다.
   - 오류 상태: RULE_NOT_APPLICABLE, RECEIVER_UNION_UNPROVEN, MISSING_PRODUCER_RECORD, HARNESS_ONLY_PROVENANCE, DYNAMIC_BLOCK, RUNTIME_PENDING.
   - runtime pending: 실제 clock/heartbeat freshness, 실제 cert not_after, PG lock, kill-switch writer 권한.
3. 이 검토는 아무것도 부여하지 않는다: B 제품, code, port, credential, registration, partial freeze, runtime, PKI, Node, VM, clock.

## 재현과 증거

- **owner proof 16건:** 하나씩 직렬로 다시 실행했다.
  - 모두 예상 exit다: Rev7/Rev8 regression 1, Rev9 0, R4 0, `--require-coexistence` 1.
  - 재생성된 산출물은 byte가 같다. 예외 두 개는 producer-order의 KST와 retained-probe-results의 절대 worktree 경로이고, 둘 다 복원했다.
  - producer와 artifact hash 33/33을 재계산했다. 순서는 pending_contracts(`e0dd1ee5`) → stage1 `61daff8a`(NOT_FINAL) → edge_categories(`d16ae559`) → final `79a03d49`이다.
  - 이것은 owner 증거의 재실행이다. B runtime 증거가 아니다.
- **검토자 script:** `.py.txt` 5개와 결과 5개.
  - M1/L3 공격 102건
  - offline probe Rev7/8/9
  - L1/T1 변이 70건(변이는 parse만 하고 실행하지 않았다)
  - L2 6건 대조
  - 늦은 frame 확인 wedge
- **검토자 실수 기록:** `commands.json`에 보존했다.
  - 처음 재실행에서 디렉터리 이름만 넘겨 0/0/0이 나왔다. 절대 경로로 다시 실행해 1/1/0을 얻었다.
  - M1 공격 첫 실행에 fixture 실수(run-1 기본값)가 있었다.
  - binding() fixture의 부작용이 있다.
- **자원:** 직렬로 실행했고, 선택 source는 동시에 10개 이하다. owner 명령의 최대 peak는 62,840,832 B(t1_tests)다. 설치나 OS 변경은 없다.
- **NOT RUN:**
  - full assembler/523/3485/aggregate ledger.
  - PG, Docker, SSH, Node, Go, crypto, TLS, crash, 동시성, 장비, VM, clock, PKI.
  - Obsidian apply/adopt/resolve/state write.
- **B 상태:** 새 실제 B 증거는 0이다. A1–A16은 PENDING이고, 모든 실제 binding은 NULL/HOLD다.

## 다음 행동

Root가 이 실제 판정, SHA, Docs를 보고 Rev9b 범위를 하나 정한다. owner 질문 `msg_ae8b4176e148`에는 Root가 답한다.

다음은 수정하지 않았다: 공유 진행판, registry, ADR, 원문, Card150, pins, workflow, deps, author/product/test/schema 파일. Obsidian apply도 없다.
