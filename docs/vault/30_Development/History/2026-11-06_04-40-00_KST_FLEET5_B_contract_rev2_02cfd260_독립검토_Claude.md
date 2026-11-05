---
doc_id: "HISTORY-FLEET5-20261106-B-REV2-02CFD260-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 B contract revision 2 02cfd260 독립 아키텍처·계약 delta 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T04:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "02cfd260437e1d592cb4bf67e5d6764c4260363a"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105"]
tags: ["fleet5", "independent-review", "architecture", "node-wire", "storage", "claude"]
---

# B contract revision 2 (02cfd260) 독립 delta 검토

Orca `task_d4c4c809ed4e`, dispatch `ctx_c7674e6e1277`. owner는 Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`이다. 이 검토는 e50 검토 뒤에 실행되었다(동시 검토자 1명 유지).

- **판정: REVISION REQUIRED (좁은 rev3).** ACCEPT도 FREEZE도 아니다. 원래 B1–B5의 방향은 대부분 닫혔다. 하지만 새 Node wire ABI와 release 이후 lifecycle에 Medium 7건(R1–R7)이 남는다.
- **새 Node wire ABI(`X-Inv-Node-Role-Use`): 등록 불가.** 등록 전에 Root가 R1(신뢰 key 계층)과 R2(receipts·safety 권한 분류)를 결정해야 한다.
- **기계 판독 결과:** `Evidence/fleet5-b-rev2-review-20261106-claude/review.json`, 명령·exit·hash는 `commands.json`

## 대상과 범위

- **대상:** `02cfd260437e1d592cb4bf67e5d6764c4260363a`, 부모 `72028cba`. 33개 파일 모두 추가(A)이고 수정은 0개다. History 1개와 `Evidence/fleet5-b-contract-rev2-20261106-codex/` 32개이며 모두 docs/vault 안에 있다.
- **읽은 것:**
  - 원래 검토 `2bb959a3`의 History와 JSON
  - Root `implementation-scope-decision-root.json`(ee1e8057, `msg_fa19f6e8d717` D1–D6·L1–L4)
  - Index 1.0.417(e840937b, 04:06:14 KST. 이 task가 e50 뒤에 등록되어 있다)
  - owner History 전체와 Evidence 32개
- **맥락으로만 확인한 것:** exact Docs run `42087817282`(job `127457567268`) success, headSha 02cfd260, 03:48:39–03:49:14 KST. 이 검토자가 `gh run view`로 다시 읽었다. 72028 CI와 e50 검토는 B 증거로 빌려 쓰지 않았다.
- **하지 않은 것:** B code/ADR/registry/board/NodeOps, author checkout, Docker/WSL/SSH/key/clock/schedule, Obsidian apply, process kill이나 pagefile 변경.
- **새 B 실증 건수:** 실제 Go·PG·Linux Docker·crash·동시성·물리 증거는 모두 0건이다.

## 독립 확인

| 확인 | 방법 | exit | 결과 |
|---|---|---|---|
| 46 surface 재해시 | `audit_sources.py`가 git blob만 읽음 | 0 | 46/46이 72028의 기록 sha256과 같다. 4f97ba71·100f와 같고 02cfd260에서도 바뀌지 않았다. anchor 341개 = 정확 329 + 공백만 다름 12, 틀림 0 |
| 11 binding | 같은 스크립트 | 0 | 11/11 hash가 같고 46과 겹치지 않는다 |
| 90/32 census | owner regex로 직접 `git grep` | 0 | source 접미사 기준 90 파일, DIRECT 32가 정확히 같다. 미분류 hit 0. 2bb B2 caller 15개가 모두 분류되어 있다. source가 아닌 4개 파일은 owner 범위 밖이다(L-g) |
| owner fixture 재실행 | scratch 사본에서 `validate_revision_fixtures.py` | 0 | 181/0. stdout·results·inputs가 owner 기록과 byte 단위로 같다 |
| 검토자 adversarial | `adversarial.py` | 0 | 30개 case 중 계약과 일치 15, 불일치 15(schema/mock 수준) |
| unchanged guard | 72028 `deploy/lan` + probe archive | 0 / 1 | 기대값 0 / 1과 같다. 두 log hash 모두 owner와 같다. R4 gap 증거일 뿐이다 |

- **실행 환경:** host 메모리는 125 MB free / 16151 MB(99.2%)였다. 그래서 모든 검사를 순차로 짧게 돌렸다. 시각은 UTC 19:23–19:30, 즉 KST 04:23–04:30이다.
- **181 checks의 성격:** 모두 schema/mock/static 검사다. 실제 runtime 증거로 승격하지 않는다.

## 원래 차단 사항의 상태

- **B1 — 방향은 닫힘. 잔여 R7.**
  - Linux-native source만 허용한다. Desktop·DrvFs·9P·`/run/desktop/mnt/host`·remap과 plain PC5 fallback은 금지한다. 하나라도 불가하면 cohort 전체를 BLOCK한다.
  - mount ID는 namespace-local로 기록하고 namespace 간에 같다고 비교하지 않는다.
  - launcher/probe digest와 API 1.45 probe를 요구한다. 실제 binding은 모두 NULL이다.
- **B2 — 방향은 닫힘. 잔여 R3·R4.**
  - 두 번째 channel이나 counter를 만들지 않는다.
  - admission은 immutable하고 current pointer는 guarded이며 성공 boolean이 없다. member CAS ledger는 channel CAS와 같은 tx에서 쓴다.
  - `observation_only`는 business 면제가 아니다. 미분류 caller는 기본 DENY_B다.
- **B3 — 계약 문장으로는 닫힘. 잔여 R5.**
  - journal과 pin 전에 두 config를 순수 검증한다. DER B NotBefore ≤ now−30, expiry ≥ now+630이다.
  - S4a는 같은 exact intent로만 forward한다. 이전 config restart·restore·reset은 금지한다. floor history 규칙도 있다.
- **B4 — 대부분 닫힘. 잔여 R2·R3·R5.**
  - 노출 전에 durable all-five fence를 둔다. 이전 grant 만료와 quiescence 증거를 요구한다.
  - Node별 CAS가 원자적이라고 주장하지 않는다. lost response는 tuple과 ledger를 함께 본다.
  - release 이후에는 선택된 healthy Node만 본다(ADR100).
- **B5 — 순서는 정의했지만 감사가 불완전하다. 잔여 R6.** 정적 순서는 PG 동시성 증명이 아니라는 점에 owner도 동의한다.
- **L1–L4:** 문장으로는 닫혔다. L1은 denylist라는 한계가 있다(L-f).
- **보존된 항목:** R4/plain floor :2/leaf :3/SF1/RS1, B-MIG1 design-first, 100f·2bb·expected red는 그대로다.

## 남은 차단 사항 (Medium)

**R1 — 신뢰 key 계층 (새 wire)**

- **현재 설계:** `roleConfig`에 key가 하나뿐이다(`releaseAuthorityPublicKey*`). 이 key가 모든 per-request role-use token을 검증한다. token 발급자는 무인 online attestor다.
- **문제:** Node는 release 객체를 보지 못한다. 그래서 "release authority만 새 generation을 승인하고 runtime은 release를 만들 수 없다"는 주장이 Node 쪽에서 암호학적으로 표현되지 않는다. online key가 유출되면 Node가 관측한 어떤 generation에 대해서도 token을 만들 수 있다.
- **결정할 것:** 다음 둘 중 하나다.
  - 계층을 둔다: offline release key → cohort·generation·expiry로 범위가 제한된 online use key
  - 단일 online key를 신뢰한다고 명시적으로 수용한다

  어느 쪽이든 rotation/revocation과 runtime→attestor 요청 인터페이스도 정해야 한다.

**R2 — `/v1/executions/receipts` 분류 충돌 (새 wire)**

- **충돌:** rev2는 receipts를 EXECUTION/MODEL business token에 묶었다. 그런데 72028에서 receipts는 CP의 observe/reconcile 경로다(`dispatch.py:339` `observation_only=attempt.operation == "observe"`, `node_transport.py:83`).
- **결과:** fence 중, 만료 후, generation이 바뀐 뒤에는 business token이 없다. 그래서 다음 세 가지가 receipts를 읽지 못한다.
  - in-flight reconcile
  - lost-response 복구
  - B4 quiescence 증명
- **정의되지 않은 것:** cancel/quarantine/receipts용 "separate typed safety authorization"이 schema에 없다.
- **이미 72028에 있는 것:** `server.go:67`은 POST만 받고 RawQuery/RawPath를 거부한다.

**R3 — release 이후 lifecycle**

- **readmission:** 재시작 후 Node별 재승인에 phase 행·작성자·fence 규칙이 없다. History는 "새 operator-bound release 전이"라고 하고, D4는 Node별 재승인을 금지하며, release는 다섯 Node 모두의 증거를 묶는다. 세 진술이 서로 맞지 않는다.
- **release 만료:** persistence-abi에서 release는 "short expiry"인데 갱신 규칙이 없다. 새 release에는 다섯 Node의 최신 증거가 필요하다. 따라서 release가 만료되는 순간 관련 없는 offline worker 하나가 steady state 전체를 막는다. 이는 ADR100과 충돌한다.
- **owner predicate의 동작:**
  - admission 수명을 120초로 제한한다. attestor가 계속 갱신해야 하고, attestor가 중단되면 전체 거부다.
  - `eligible(selected=[])`와 `eligible(selected=[0,0])`이 True를 반환한다. 빈 선택과 중복 선택이 통과한다.
  - 외부 Node는 표현할 수 없고 `IndexError`가 난다.

**R4 — 권한 matrix**

- **작성자가 산문으로만 정의되어 있다:** "operator attestor", "approval writer", "guarded operator CAS function". DB role 이름, GRANT/function owner, 분리 규칙(attestor는 planner/approval grant를 가질 수 없음)이 없다.
- **persistence-abi 내부 모순:** admissions에는 "FK …release"가 있는데, ordering 규칙은 "이미 있는 release에 대한 FK 없음"이다.
- **runtime 권한 충돌:** commit 시 CP 쪽 one-use nonce/evidence 기록에는 runtime INSERT가 필요하다. "runtime read/lock only"와 양립하려면 이 테이블들을 비권한 runtime-writable로 분류하고 별도 grant를 줘야 한다.

**R5 — phase 표 범위**

- **빠진 행:** 600초 operation 중에 k/5 CAS가 끝난 상태에서 일어나는 다음 사건의 행이 없다.
  - revoke 또는 C 점프
  - epoch 변경
  - grant/approval 만료
- **열린 기준:** 본문은 "무효화, 격리 유지, 새 reviewed intent"라고 한다. 그러나 (P+1, C+1)이 pin된 혼합 cohort나 revoked cohort에서 새 intent를 시작하는 진입 조건이 닫혀 있지 않다.

**R6 — B5 감사 범위**

`currentSourceInversions`에는 4건만 있다. 이 검토자는 72028에서 제안 graph와 반대인 순서를 추가로 찾았다.

- `leases.lock_run`: runs FOR UPDATE(`leases.py:25`) → `lock_resources` inv.nodes FOR UPDATE(`leases.py:44`)
- containment: operator_grants FOR SHARE(`containment.py:23`) → inv.nodes FOR UPDATE(`containment.py:109`)
- `observation.py:141`: fence 없이 online Node 전체를 FOR UPDATE
- 모든 `Database.transaction`: 먼저 control_epoch FOR SHARE(`db.py:202`)

순위별 lock mode도 없다. fence 행을 SHARE로 잡는지 UPDATE로 잡는지, lock_timeout 2s에서 fence writer가 starvation되는지 정해야 한다.

**R7 — CP context capability**

- **schema에 없는 것:** `executionContext`에는 CPU·memory·disk·network 용량 필드가 없다. const-true "verified" boolean과 `capabilityEvidenceSha256`뿐이다. 원시 측정 record의 schema도 없다.
- **물리 차단:** 검토 시점 host 메모리는 99.2%였다. 어떤 guest를 올리기에도 물리적 차단이다. 이와 별개로 Windows CP의 API 1.41 차단도 유지된다.
- **WSL2 종류:** `wsl2-ext4-dedicated-engine-v1`에는 distro/instance identity가 필요하다. automount와 interop도 꺼야 한다. 또 WSL2 distro들은 Docker Desktop distro와 kernel·boot_id를 공유한다는 점을 명시해야 한다. 검토자 권고는 managed VM이다.

## Low

- **L-a:** Python jsonschema는 `re.search`를 쓴다. 그래서 `^…$`가 끝의 `\n`을 허용한다. token과 모든 `^[0-9a-f]{64}$` 필드에서 실제로 True가 나왔다. Go와 ECMA의 동작과 다르다. full-match와 양 언어 vector가 필요하다.
- **L-b:** roleUse의 issuedAt/expiresAt 관계와 ≤120초 조건이 schema와 predicate에 없다. 만료가 발급보다 앞서도, 1e9초 창이어도 통과한다. 시간 단위도 명시되어 있지 않다.
- **L-c:** 문자열 필드가 U+2028·NUL·lone surrogate를 허용한다. Go는 lone surrogate를 U+FFFD로 바꾼다. 서명 입력 bytes가 정확히 무엇인지(domain‖NUL‖decoded canonical payload 여부)도 명시해야 한다.
- **L-d:** MODEL과 EXECUTION이 같은 Node 경로를 쓴다. purpose 구분은 CP/attestor에서만 가능하다는 점을 명시해야 한다.
- **L-e:** 현재 journal은 permit 키의 fsync record다(`journal.go:163`). terminal frame마다 durable nonce를 쓰려면 만료 기준 GC가 필요하다. servingGeneration에 process nonce가 들어 있으므로 generation 메모리 기반 replay set으로 충분한지 결정해야 한다.
- **L-f:** workload inspection은 여전히 denylist다. `docker.go`는 CapAdd/UsernsMode/Sysctls/Runtime/VolumeDriver/CgroupParent를 하나도 참조하지 않는다. HostConfig를 닫힌 allowlist로 decode하기를 권고한다.
- **L-g:** caller 분류는 경로·이름 heuristic이고 `unclassified: []`는 구조상 항상 빈 값이다. call-site 의미 검토는 미래 code review의 몫이다. `app.py` route는 transitive로만 다뤄진다. `tools/rls-table-census.json`은 범위 밖이다.
- **L-h:** root.device/inode의 정규 인코딩이 정해져 있지 않다.

## 미래 code에만 존재하는 제약

- **wire:** token decode/re-encode 동치, Ed25519 검증, unique-key JSON, C2 vector, Node 쪽 nonce·generation 비교
- **CP DB:** GRANT/function/trigger, lock 순서, retry, CAS ledger
- **실행 환경:** capability probe, launcher, host↔Node root 대응
- **전환:** quiescence, CP client switch witness

A1–A16은 여전히 실제 Go/PG/Linux Docker, leaf :4 두 cycle, crash, 동시성, 물리 증거가 필요하다.

## Root 결정 필요 사항

- R1: key 계층과 attestor 신뢰
- R2: typed observation/safety 권한
- R3: readmission과 release 수명 대 ADR100
- R4: DB principal/GRANT matrix
- R7: VM과 WSL2 중 선택, 용량 preflight 필드
- CP 전용 persistence/phase 부분을 먼저 freeze하고 Node wire ABI만 보류할지 여부

hard ABI와 runtime의 owner는 계속 Codex이고, 최종 결정과 ADR 등록은 Root가 한다.

## 다음 첫 행동

- **Codex(owner):** R1–R7과 L-a–L-h를 rev3로 닫는다. 기존 rev2와 100f는 immutable로 둔다.
- **Root:** R1·R2 아키텍처를 결정하고, 부분 freeze 여부를 정한다.
- **Claude:** rev3의 delta만 실제로 검토한다.
