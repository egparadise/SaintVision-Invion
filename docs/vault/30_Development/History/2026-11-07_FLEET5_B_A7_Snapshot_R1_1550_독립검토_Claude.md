---
doc_id: "HISTORY-FLEET5-20261107-B-A7-SNAPSHOT-R1-1550-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 B A7 snapshot R1 1550 부분 정적 증거 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T06:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1550453d1f072a87fd9a7baa53d4fe4ce8a98d5d"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105", "FLEET5-B-A7-SNAPSHOT-R1-20261107"]
tags: ["fleet5", "independent-review", "b-contract", "a7", "claude"]
---

# B A7 snapshot R1 1550 부분 정적 증거 독립 검토

Orca `task_8376b6d0ca39` / dispatch `ctx_d6e29070eb5d`에서 한 실제 독립 검토다. owner는 Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`이고, pending 질문은 `msg_577bb9090679`, Root 허가는 `msg_35937c8787d1`이다. helper와 두 번째 검토자는 쓰지 않았다.

- 대상: `1550453d`, 직접 부모 `0e66b5ab`. 추가 109개(Evidence 108, History 1), 수정·삭제 0, `docs/vault` 밖 변경 0. 제품 기준 `72028cba`는 그대로다.
- 먼저 읽은 것: 직전 실제 검토 `90cccfb3`의 History, review.json, commands.json, gate driver, probe log를 그 commit에서 직접 읽었다. 그 ACCEPT는 B9f Low 2건만 닫았고, 모든 caller나 runtime을 부여하지 않았다. 이어서 Root scope(`.work/b-a7-snapshot-r1-root-cut.txt`, `a7r1-source-root-verified.json`, review spec)를 읽었다.
- Root 보드는 read-only로 읽었다(`fleet-five-orchestration-20261105` head `da4f07eb`, Index 1.0.482, Claude board 1.2.130).
- 사전 확인: manifest `2a75a22f…`를 다시 계산했다. 파일 107개와 producer·상속 의존 36개가 commit된 bytes와 모두 같다. proof-final02 3개와 docs-final02 8개 명령도 exit 0이고 raw log hash가 맞다. owner 명령은 다시 돌리지 않았다. 작성자 접두사 아래 CI 이후 영수증은 후보 입력으로 쓰지 않았다.

**판정: REVISION_REQUIRED (LOW 1건, A7R-L1). MEDIUM 이상은 없다. 후보는 PARTIAL/HOLD 그대로다.**

- L1을 빼면 body·helper·import·DB 의존 잠금, NORMAL/관찰 경로 표, 생성자 10곳과 snapshot 10곳 census, 명시된 blocker 19건, HOLD 상태는 건전하고 정직하게 한정되어 있다.
- 이 검토는 아무것도 부여하지 않는다. 전체 A7, caller closure, runtime, source 포함, port 모두 아니다.
- 상세: `docs/vault/30_Development/Evidence/fleet5-b-a7-snapshot-1550-review-20261107-claude/review.json`.

## A7R-L1 (LOW): 파싱만 하고 guard는 걸지 않은 census 후보

census는 lexical 후보 30개를 모두 파싱한다. 그러나 reflection guard와 use-site guard는 12개 파일에만 건다. 대상은 NodeChannels 호출이나 `.snapshot(` 호출이 있는 파일, 그리고 NC/CT/DB/ER이다.

- 원인 코드: `a7_inventory.py` census의 `if not relevant:continue`가 `ra.audit`/`u.module_uses`보다 먼저 온다.
- body 쪽도 node_channels/containment/db/errors 4개만 guard한다.
- 따라서 18개 후보 파일에는 어느 guard도 걸리지 않는다.

유효한 반례:

- 파일: guard 밖 후보 `services/control-plane/src/inv/node_certificates.py`. frozen `6e2bfb2d…`, 입력 `19c2e14e…`.
- 끝에 두 줄을 붙였다(:75 `from .node_channels import NodeChannels as _ReviewerA7NC`, :76 `_ReviewerA7NC.snapshot = lambda self, node, **kw: None`).
- 결과: body는 모든 gate를 지나 ACCEPT다. census는 기준 대비 obligation이 하나도 늘거나 줄지 않는다.
- 같은 입력을 기존 use-site guard에 직접 넣으면 `WRITE_USE:inv.node_channels.NodeChannels.snapshot`으로 거부된다.
- 같은 patch를 guard 대상인 `observation.py`에 넣으면 census에 `A7_FULL_MODULE_USE_SITE_GUARD`가 추가된다. 층이 맞게 갈린다.
- 원인은 census guard 범위다. parser나 stale hash 문제가 아니다. mutant는 compile만 했고, 4개 선택 입력은 frozen 그대로다.

이것이 LOW인 이유:

- class monkeypatch는 owner가 선언한 범주다(`class-monkeypatch` 사례).
- node_channels.py 밖에서 하면 거부도 되지 않고 이름 붙은 blocker로도 남지 않는다. 그래서 19건이 이 경우를 덮지 않는다.
- 19건이 닫히는 날 `callerClosureAccepted = not obligations`가 이를 보지 못한다.
- 지금 상태(`SOURCE_STATIC_UNRESOLVED_RUNTIME_PENDING`)와 어떤 숫자도 바꾸지 않는다.

최소 수정:

- 기존 두 guard를 파싱한 모든 lexical 후보에 건다(parsed == audited). 수락된 B t1 census가 이미 이렇게 한다.
- guard가 거부하면 `A7_RELEVANT_REFLECTION`/`A7_FULL_MODULE_USE_SITE_GUARD` obligation을 낸다.
- 검토자가 frozen 72028의 18개 파일에 두 guard를 돌린 결과는 hit 0, error 0이다. 따라서 이 수정 뒤에도 19건, 30/10/10/7/12, 전역 숫자는 그대로다.
- 이 파일 밖 monkeypatch를 source case로 추가한다. oracle은 기준 대비 차이로 판정한다.
- (선택, 같은 수정) world에 새 제품 파일을 넣으면 census가 `CalledProcessError`로 멈춘다. fail-closed이고 인증도 아니지만, 명시적 obligation이 더 분명하다.

## 경로 표 (72028 원문 기준)

| 조건 | NORMAL | 관찰(observation_only 참) |
| --- | --- | --- |
| `containment.require_execution(conn)` (kill_switch, AUTH-0061) | 필요 | 생략 |
| node `FOR SHARE` + DB 시계, node recovery epoch | 필요 | 필요 |
| online + DB now−heartbeat ∈ [0,15] s | 필요 | 생략 |
| channel 읽기 + channel recovery epoch | 필요 | 필요 |
| `assert_channel`: channel `FOR SHARE`, enabled, 인증서 만료 > DB 시계, proof 동일 | 필요 | 필요 |

- `observation_only`는 Python truthiness이고 기본값은 False다. 정확한 bool 검사는 없다.
- snapshot 자체의 channel 읽기에는 `FOR SHARE`가 없다. share lock은 assert_channel에 있고, History도 그렇게 적었다.

## 검토자 probe (AST 전용, 직렬 1 process)

- 실행: owner `measured_run.py`로 쟀다. 06:35:05~06:36:12 KST, exit 0, peak 105259008 B, 65 s. 단일 process 관측값이고 quota가 아니다.
- 대조군 ACCEPT 5건:
  - 실제 코드.
  - NC 앞에 주석을 넣어 모든 span을 옮긴 경우.
  - containment, db, errors 끝에 각각 주석을 넣은 경우.
- 반례 12건은 모두 이름 있는 gate에서 거부된다(compile만 했다).

| 반례 | 거부 gate |
| --- | --- |
| containment 안의 def 뒤 재대입, no-op 중복 def(앞·뒤), `del` | `CALLEE_REBOUND` |
| containment와 node_channels 안의 `DomainError` 재대입 | `NECESSARY_LEXICAL_BINDING` |
| `assert_channel` module 재대입 | `CALLEE_REBOUND` |
| `ChannelProof.__eq__` patch | `WRITE_USE` |
| heartbeat 하한 −1, online 검사를 관찰에도 강제 | `NORMAL_ONLINE_HEARTBEAT_0_15` |
| assert_channel에서 host 시계 사용 | `CURRENT_CHANNEL_CERTIFICATE_PROOF` |
| 기본값 `observation_only=True` | `SNAPSHOT_SIGNATURE` |

- census: 12개 후보 밖 파일의 문제는 L1에 정리했다.
  - node_transfer.py에서 local alias를 receiver로 쓴 경우는 dynamic mode든 literal mode든 retained use-site guard가 거부한다.
  - inline에서 dynamic mode를 쓴 대조군은 `A7_PURPOSE_PROVENANCE`를 새로 추가한다.
- 독립 git grep 결과는 34개다. `.py` 30개와 비-py 4개(migration SQL 2, baseline txt, rls json)다. 생성자 10곳은 Root가 처음 관찰한 목록과 같다.
- 19건의 구성은 이렇다.
  - 목적 1건: NodeDelivery의 `observation_only or cancel_only`.
  - DB owner 10건.
  - 역방향 root 8건.
- NodeTransfer에는 제품 생성자가 없다. 그래서 이 상태의 event는 0개다.

## INFO (판정에 영향 없음)

- **I1 (지나치게 엄격하지만 fail-closed):** snapshot의 With 블록 안에 주석 한 줄을 넣으면 `A7_NECESSARY_LEXICAL_BINDING:conn`으로 거부된다(입력 `6130676a…`). `lexical_bindings.py:20-24`가 binding event를 감싸는 문장 전체 source의 SHA로 식별하기 때문이다. lexical gate 쪽은 일부 source-text digest이고, statement shape gate가 AST 의미 기준이다.
- **I2:** `otherSnapshotReceivers` 2건은 `blocksGrantForThisReceiver=true`이지만 obligation에는 들어가지 않는다(remote_git.py:285 GitHubRepository `self.snapshot`, workspace_git.py:167 `repo.snapshot`). 둘 다 git snapshot API이고 NodeChannels가 아니라서 지금은 영향이 없다. 선택적 보강: 세거나, 해석된 비-NodeChannels receiver로 기록한다.
- **I3:** owner의 `caller-dynamic-purpose` oracle은 기준에 이미 같은 코드가 있어서 실패할 수 없다. 검토자가 기준 대비 차이로 다시 계산하면 observation.py [17,16,17,70]에 새 `A7_PURPOSE_PROVENANCE`가 생긴다. 따라서 주장된 결과는 맞다.
- **I4:** `BoundDatabase`(db.py:112-133)는 database 모양의 기존 type이다. transaction이 tenant만 비교하고 바깥 conn을 그대로 yield하며, role/epoch/tenant gate 문장이 없다. body의 Database.transaction 증명은 `inv.db.Database`에만 해당한다. 기존 owner closure obligation이 이미 이것을 덮는다. 미래 port를 위해 이름을 적어 둔다.

## 남는 blocker와 하지 않은 것

- 명시적 blocksGrant 19건은 모두 그대로다.
  - NodeDelivery mode 값의 출처 1건.
  - DB owner 10건: `database` ×4, `self.db`, `runtime(state)` ×4, `a.e.db`.
  - 역방향 root 8건: worker.py:122/133, remote_workspace_entry.py:107/111/145, observer_worker.py:58, lan_pilot.py:3945, app.py:1323.
- observer lock, P-DBROLE, 실제 PG READ COMMITTED/SET LOCAL/lock/시계/RLS role/auth/cutover는 19 밖에 남는다.
- 다음은 그대로이고 검토자가 다시 계산하지 않았다. Root가 검증했다.
  - 12 entry, 19 edge(16/3).
  - 598/757/1071/21/573/218.
  - model `f7384016…`과 lifecycle `710c6aaf…`.
  - runtime B 0, real binding NULL/HOLD, A1~A16 PENDING.
- 하지 않은 것:
  - owner proof/docs/seal 명령, generator, 523 assembler, 3485 plan, 거대 ledger.
  - 이전 B9g corpus, model/recovery 시험.
  - 제품·mutant import나 실행, DB/네트워크/crypto, Obsidian apply/adopt/resolve/state 쓰기.
  - 공유 보드·registry·ADR·workflow 수정.
- canonical CHECK(작성 전)는 exit 0, conflict 0이다. state는 `d308e7d8…`에서 변하지 않았다. 작성 뒤 local gate 8개는 `local-doc-gates.txt`에 실제 exit와 state hash로 남긴다.

## 다음 (Root에게)

- 다음 첫 행동: Root가 A7R-L1을 `msg_577bb9090679`의 owner에게 전달하고, 좁은 guard 범위 수정을 허가할지 결정한다. 담당은 Root다.
- 검토자는 다음 범위를 시작하지 않는다.
