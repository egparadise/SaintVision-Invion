---
doc_id: "HISTORY-FLEET5-20261106-B-REV4-2A08284A-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 B contract revision 4 2a08284a 독립 결합 계약 delta 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T07:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "2a08284a97fb8cd40c9e6de5c923c7864a7f76af"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105"]
tags: ["fleet5", "independent-review", "architecture", "node-wire", "authority", "claude"]
---

# B contract revision 4 (2a08284a) 독립 결합 delta 검토

Orca `task_72d23bdd01a8`, dispatch `ctx_c1e01403f409`. owner는 Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`이다. 검토자는 1명이다. `task_5627222e0f59` 의존은 검토자 자원 순서일 뿐이며, K1·e50·bootstrap 결과는 B 증거로 쓰지 않았다.

- **판정: REVISION REQUIRED (좁은 rev5).** ACCEPT, 부분 freeze, 등록, 코드 grant 모두 아니다.
  - B3-M2(승인 갱신)와 B3-M3(gate·delivery·scope 산출물)는 설계 수준에서 닫혔다.
  - B3-L1/L2/L4/L5는 닫혔다.
  - 결합 잔여는 Medium 2건(B4-M1, B4-M2)과 Low 4건(B4-L1~L4)이다.
- **기계 판독:** `Evidence/fleet5-b-rev4-2a08-review-20261106-claude/review.json`
- **명령·argv·exit·시각·검토자 실패:** `commands.json`
- **원시 결과와 스크립트:** `census-audit-result.json`(`census_audit.py`), `adversarial-result.json`(`adversarial.py`)

## 대상과 범위

- **대상:** e9932f30 → 2a08284a. 파일 39개가 모두 추가(A)이고 +10747이며, 전부 docs/vault 아래(History 2, Evidence 37)다. 72028 대비 product diff는 0이다. 리뷰 시점 원격 ref도 2a08284a였다.
- **Docs 42118500179:** job 127564375746, headSha 2a08284a, ref는 owner branch, workflow_dispatch, docs=success다. `gh run view`로 읽기만 했다.
- **읽은 것:**
  - owner History 2건(revision4 본문, 별도 census error)과 Evidence 37개 전부
  - 이전 검토 638109ab (REVISION REQUIRED, Medium 3 / Low 6)
  - Root f71fdea2의 `b-rev4-root-decision.json` (`msg_94ff5bb7a0e6`)
  - 72028 source의 lease/placement/build_preparations/runs/observation/containment/node_channels/quarantine 경로, `node_auth.py` 99–140, `src/saintvision/services/nodes.py`, `src/saintvision/services/storage.py`
- **보존 확인:**
  - e993→2a08 구간에 수정·삭제가 0건이다.
  - `prior-*` 5개 파일은 638109ab와 byte가 같다.
  - census decorator 오류와 staged whitespace 실패는 기록으로 남아 있다.
  - 100f/02cf/15823/e993과 이전 33 probe는 손대지 않았다.

## 독립 재현 (실제 실행)

- **owner census CLI:** exit 0. 494/185/2933/615/823/1374가 그대로 나왔다.
  - 5개 negative는 모두 exit 1, `CENSUS_MISMATCH`, stderr 0이다.
  - 재생성된 `source-census-results.json`과 commit본의 차이는 argv의 스크립트 경로뿐이었다. 이 파일은 `git checkout`으로 복원했다.
  - 단, 5개 negative는 저장된 JSON 사본에서 요소를 지운 비교기 자기검사다. source 변이 검사가 아니다.
- **owner schema/authority/fixtures:** 476 pass / 0 fail. stdout이 log와 같다.
  - 재생성된 5개 산출물(schema, matrix, fixture-results, stateful-positive, phase-cases)이 byte까지 같다.
- **unchanged R4 probe:** 기본 exit 0, `--require-coexistence` exit 1(예상대로)이다. 둘 다 log와 같다. 이것은 source baseline이며 B 성공이 아니다.
- **commit된 log 해시:** 14/14 일치한다.
- **검토자 census audit**(owner `analyze()`를 72028 Git bytes의 메모리 변이에 다시 실행했다)
  - helper textual call 91개 중 edge가 없는 것은 0이다.
  - S1(build_preparations:223 lock_run 제거), S2(node_auth:111 with_for_update 제거), S3(alias import로 lock_run을 부르는 새 caller)는 모두 검출됐다.
  - S4(dotted import), S5(instance receiver wrapper), S6(SQL 상수 `inv.nodes FOR UPDATE`)는 reach·scope·record 어느 쪽에도 잡히지 않는 blind spot이다.
- **검토자 adversarial:** 30 probe 중 24개가 계약과 일치한다. 불일치는 A1, A4, A5, B7, B7b, B8이다.

## 닫힌 것

- **B3-M2:**
  - per-Node APPROVAL_RENEW_SAME_CONFIG(만료 전)와 REAPPROVE_SAME_CONFIG(시간 만료 후에만)가 정의됐다.
  - 이전 approval은 불변 lineage로 남고, 새 approval은 24h 이하이며 grant/trust 범위에 묶인다.
  - revocation, fence, quarantine, containment, 8개 drift, cert/trust/grant 만료는 모두 거부된다.
  - 관련 없는 worker가 offline이어도 갱신을 막지 않는다(A9).
  - A0가 switch 도중에 만료돼도 A1이 권한을 준다(A2/A2b). fence가 append 뒤에 걸리면 commit이 거부된다(A8). sibling fork는 활성화될 수 없다(A6). 만료 후 REFRESH/READMIT는 거부된다(A7).
  - phase trace 20행 어디에서도 business가 미리 열리지 않는다.
- **B3-M3:**
  - closed 산출물(gateAck, challenge, PoP, receipt, ObservationScope)이 정의됐다.
  - ARM/INVALIDATE는 operator-release 목적으로만 서명된다.
  - gate ack 기록 권한은 operator와 verifier뿐이다.
  - 두 proof가 분리돼 있다. issuer는 controller receipt를 기록하거나 서명할 수 없다.
  - hash를 다시 묶는 rebinding, cross-node challenge(B1), scope를 권한으로 바꾸는 시도(B3/B3b)는 모두 거부된다.
- **B3-L1/L2/L4/L5:**
  - not-yet-CAS revoke 10행이 모두 refuse한다. P 102는 overlap 단계이고 final 103은 별도로 필요하다. C는 7→8, R은 2로 그대로다.
  - lost response 사건이 UNRESOLVED_AFTER_EXACT_LEDGER_REREAD와 RESOLVED_EXACT_COMMIT_FORWARD로 나뉘었다.
  - safety path는 literal enum이다. alias 4종은 거부된다(B4).
  - 별도 budget approver가 정의됐다.
  - clock은 30000ms 경계를 포함하고, bool과 범위 밖 정수를 거부한다(B5).
- **B3-M1:** 대부분 닫혔다. 494파일, 이전 anchor 전부, credential_registry, node_auth108을 포함하고 unknown receiver를 명시한다. 잔여는 B4-M2다.
- **B3-L3/L6:** 방향은 닫혔다. SD lock-only이며 sentinel UPDATE가 없다. matrix가 typed되고 실제 interval을 쓰며, READMIT(old,old)는 거부된다. 잔여는 B4-M1이다.

## 남은 결함

- **B4-M1 (Medium) — authority matrix가 실제 writer와 대조되지 않았다.**
  - matrix는 표마다 "ALL writer procedures"를 선언하고, 온라인 principal의 authority DML을 모두 false로 둔다. 그런데 census가 직접 기록한 72028 writer 중 다음은 어디에도 매핑되지 않았다.
    - `inv.nodes`: runtime fail-closed quarantine 두 곳 — `build_execution.py:304`, `node_transport.py:247`
    - `inv.node_channels`: `provision_channel` INSERT(:183), `revoke_channel` UPDATE(:218)
    - `inv.evidence`: plain INSERT 5곳
    - `public.nodes` (ORM): enroll INSERT, `status='lost'`, 그리고 `lock_current`가 검사하는 retired/certificate binding
    - `public.storage_contributions`: create와 revoke(`status`, `revoked_at`)
  - `inv.nodes.status`는 온라인 verifier의 observation과 containment가 함께 쓴다. `public.nodes.status`는 runtime이 쓴다. 둘 다 one-way 전이 규칙이 없다(B7/B7b).
  - 결과적으로 둘 중 하나가 된다.
    - plain 경로가 sv_b_runtime으로 돌면, quarantine이 permission denied로 실패해 격리가 사라진다.
    - legacy online pool이 직접 DML을 계속 쓰면, DML 금지와 SD lock 순서를 우회한다.
  - **수정:** census의 writer마다 procedure, principal, column, 허용 전이를 정한다. 아니면 대체 경로를 명시해 폐기한다. plain 경로를 실행하는 pool을 명시한다. census↔matrix 인과 검사를 추가한다.
- **B4-M2 (Medium) — census 계획의 폐포가 helper seed에만 의존한다.**
  - instance receiver로 helper에 닿는 호출 24개가 edge에도 unknown에도 없다. Root가 금지한 "구성상 미분류" 상태다.
    - `build_preparations._terminalize`는 plan 자체가 없다(approval→runs FOR UPDATE→RunStore).
    - reached 함수의 helperEdges도 불완전하다. 예: `placement.reserve:130 _admit_locked`
  - helper를 거치지 않고 canonical table을 row lock하는 18개 함수(record 25개)에 plan이 없다. `build_execution_worker:212`와 `lock_current:108`도 여기에 들어간다.
  - canonicalBPlan, outerTransaction, requiredBPlan이 343개 plan과 2933개 record 전체에서 각각 문자열 하나다.
  - lock mode 오표기가 17건이다.
    - `FOR NO KEY UPDATE`가 inv.projects 3곳에 있다.
    - `with_for_update=` kwarg 5곳과 advisory lock 5곳이 MVCC로 표기됐다.
    - `read=True`와 `skip_locked`가 plain FOR UPDATE로 표기됐다.
  - projects, limits, approval_requests, shard_plans에 canonical rank가 없다.
  - S4–S6 blind spot이 있다.
  - **수정:** canonical/matrix table을 lock하는 모든 record에서도 seed를 시작한다. 생성자로 타입을 알 수 있는 receiver는 해석하고, 아니면 UNKNOWN+BLOCK으로 남긴다. mode를 바르게 인식하고, rank를 명시하고, 함수별 구체 plan을 쓰고, negative를 source 변이로 바꾼다.
- **B4-L1:** approval revocation이 lineage로 전파되지 않는다. A1을 append한 뒤 A0를 revoke해도 A1 commit이 True다(A1). 하위 승인까지 막도록 하고 commit, delivery, REFRESH에서 다시 검사한다.
- **B4-L2:** Node gate가 단조적이지 않다.
  - invalidate된 이전 release를 다시 ARM할 수 있다(A4).
  - restart 뒤 다른 generation의 release를 ARM할 수 있다(A5).
  - business는 receipt gateAckHash, generation 검사, CP CAS 덕분에 여전히 거부된다(A4b/A4c).
  - lost/stale ARM ack에서 durable record와 ack를 다시 읽는 경로가 정의돼 있지 않다(A3b).
- **B4-L3:** challenge와 receipt에 operator-release anchor를 쓴다. 그런데 controller의 caller→purpose 제한이 명시돼 있지 않다(B8). 별도 key를 두거나 purpose allowlist와 negative를 추가한다.
- **B4-L4:** fixture 충실도
  - `valid_matrix`가 golden equality뿐이라 의미 불변식이 없다.
  - observationScope `oneOf`의 required negative가 0이다.
  - phase trace에 시간 진행이 없다.
  - census negative가 JSON 변이다.

## 정보 (정직하게 이월)

- **정수:** exact-int는 decoder 규범이다. schema의 `integer`는 2.0도 허용한다.
- **displayLabel:** 128 code point이면 512 byte를 넘을 수 없으므로 512 byte 제한은 중복이지만 해가 없다. NFC 정규화는 하지 않는다.
- **서명 입력:** domain‖NUL 1개‖C2이고 LF는 없다.
- **terminal frame:** Sequence/Nonce는 bodySHA로 전이적으로 보호되지만, sequence/replay/expiry 검사도 따로 통과해야 한다.
- **use key 침해 시 Node가 강제하는 한계:** delegation/release/approval/cert expiry와 ack된 gate invalidation이다. 300s CP lease가 아니다. +301에서 node_accepts는 true이고 CP는 거부한다. signer/custody 가용성은 미래 전제 조건이다.
- **SYMBOLIC:** 서명은 SYMBOLIC이므로 외부 crypto 유효성은 아무것도 증명되지 않는다.
- **가용성 비용:** per-Node 갱신은 24h마다 그 Node를 한 번 pause한다. 안전 문제는 아니다.

## 미수행·보류

- **실제 증거 없음:** 실제 Go/crypto/PG/Linux Docker/crash/concurrency/equipment B 증거는 0이고 A1–A16은 pending이다. 실제 binding은 모두 NULL/HOLD다. 실제 PG 권한·lock trace는 미래다.
- **하지 않은 일:** product·owner 파일, ADR, registry, 공유 보드, NodeOps, PKI, SSH, key, config, Docker, WSL, VM, clock, schedule, Obsidian apply, 프로세스 종료 중 어느 것도 하지 않았다.
- **owner Evidence 재생성:** byte 비교를 위해 그 자리에서 재생성했고, 변경된 1개 파일은 복원했다.

## 다음 첫 행동과 담당

- **Codex:** B4-M1/M2와 B4-L1~L4를 고치는 좁은 rev5를 낸다(docs/schema/static만).
- **Root:** 이 판정을 받아들이거나 조정한다. `msg_ede52e676ef7`는 열어 둔다. 코드나 ADR grant는 아직 없다.
- **Claude:** dispatch가 오면 rev5 delta를 한 번 검토한다.
