---
doc_id: "HISTORY-FLEET5-20261106-B-REV3-E9932F30-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 B contract revision 3 e9932f30 독립 결합 계약 delta 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T06:00:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "e9932f306550a07e4893ab7a1a7dc6944b31e271"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105"]
tags: ["fleet5", "independent-review", "architecture", "node-wire", "authority", "claude"]
---

# B contract revision 3 (e9932f30) 독립 결합 delta 검토

Orca `task_deba0c63a626`, dispatch `ctx_ba55264f86fb`. owner는 Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`이다. 동시 검토자는 1명이다.

- **판정: REVISION REQUIRED (좁은 rev4).** ACCEPT도, 부분 freeze도, 등록도 아니다.
  - R1–R7의 설계 방향과 L-a–L-h는 대부분 닫혔다.
  - 결합 계약에 Medium 3건(B3-M1–M3)과 Low 6건(B3-L1–L6)이 남는다.
- **기계 판독 결과:** `Evidence/fleet5-b-rev3-review-20261106-claude/review.json`
- **명령·exit·시각:** `commands.json`
- **원시 결과:** `census-result.json`, `logs-result.json`, `adversarial-result.json`. 각 결과를 만든 스크립트도 함께 있다.

## 대상과 범위

- **대상:** `02cfd260 → 15823c2a → e9932f30` 전체 delta를 본다. 폐기된 15823만 보지 않았다.
  - 파일 37개가 모두 docs/vault 아래에 추가(A)되었다. 72028 대비 product diff는 0이다.
  - 15823→e993 구간은 10개 파일, +82/−9다.
- **Docs 42105739288:** job 127519951449, headSha e9932f30, workflow_dispatch, docs=success다. `gh run view`로 읽기만 했다.
- **읽은 것:**
  - 이전 검토 `ac9182c3`의 History와 JSON
  - Root `7ec1af26`의 `b-rev2-root-revision3-decision.json`(`msg_f7caf4c96b16`)
  - owner History 431줄과 Evidence 35개
  - 72028 source
    - `db.py` 174–215, `leases.py` 23–50, `build_preparations.py` 218–267
    - `node_auth.py` 99–112, `storage.py` 330–345
    - node `server.go` 63–67·281, `TerminalFrameInput`
- **B 증거로 쓰지 않은 것:** bootstrap 8874, K1, e50 all8, Root packet, R-L1 결과
- **실행 환경:** host 메모리 압박 때문에 Python process를 하나씩 순서대로 돌렸다(`-I -B`).
  - owner 스크립트는 private scratch 사본에서 실행했다.
  - 검토자 스크립트는 git object만 읽는다.

## 독립 확인

| 확인 | exit | 결과 |
|---|---|---|
| owner fixture 재실행 | 0 | 242/0. `fixture-results.json`과 `synthetic-positive-fixtures.json`이 byte 단위로 같다. stdout도 `rev3-fixtures.log`와 같다 |
| owner `verify_source_ledger.py` | 0 | 65 파일, 602 expression, 138 asset, 불일치 0. 다만 owner가 고른 집합 안의 정합성만 보여준다 |
| 13개 raw log hash | 0 | 13/13이 committed bytes와 같다. 초기 red(207/5, positive 5건 실패)가 보존되어 있다 |
| 15823 grant 검사 재실행 | 1(기대 1) | `missingExecuteGrants: [b_record_key_delivery]` |
| e993 grant delta | — | operator에 `b_record_key_delivery`와 `b_read_observation_scope`, safety에 `b_read_observation_scope`가 추가되었다. runtime의 execute 목록은 바뀌지 않았다(권한 확대 없음) |
| 검토자 census 감사 | 0 | ledger 밖의 CP module 10개가 canonical-rank lock을 잡는다. ledger 파일 안에서도 ORM 호출 40개가 빠져 있다(B3-M1) |
| 검토자 adversarial | 0 | 33개 case 중 계약과 일치 14, 불일치 19. 불일치는 모두 schema·fixture·입력의 누락이다 |
| phase matrix 독립 재도출 | — | 77/77 행이 검토자 규칙과 맞는다. revoked node0의 C jump까지 반영한 결과다 |

- **242 checks의 성격:** 모두 SCHEMA/STATIC/SYMBOLIC 검사다. signature, 시간, custody, 원자성의 실제 증거가 아니다.
- **새 실제 증거:** Go, crypto, PG, Linux Docker, crash, 동시성, 장비 B 증거는 모두 0건이다.

## 닫힌 것

- **R1 — 방향 수용:**
  - 별도 operator-release anchor를 둔다. CA·root-fence·TLS·use·safety key를 재사용하지 않는다.
  - use key는 Node·release별로 위임된다.
  - Node는 anchor→RELEASE→DELEGATION→ROLE_USE 사슬을 검증한다. tuple 전체(generation·gateId 포함)와 purpose·method·path·body·nonce·expiry를 확인한다.
  - issuer는 caller label을 믿지 않고 권위 있는 현재 tuple을 직접 load한다.
- **R2:**
  - lane 표는 정확한 raw POST 경로를 쓰고, 72028 `server.go:67`·`:281`과 맞는다.
  - receipts와 observe는 business token 없이 동작한다. safety는 별도 key를 쓴다.
  - MODEL과 EXECUTION은 인증된 caller와 issuer가 구분한다.
- **R3:**
  - per-Node `REFRESH_SAME_GENERATION`은 300초 이하이고, `READMIT_SAME_CONFIG`에는 all-five 의존이 없다.
  - 선택 집합이 빈 값·중복·외부 ID·비문자열이면 거부한다.
- **R4:**
  - NOLOGIN owner와 login principal을 분리한다.
  - SECURITY DEFINER는 pg_catalog search_path와 session_user/service binding을 쓴다.
  - FK가 비순환이고, activation은 닫힌 tx 하나다. Node와 key 쪽 효과는 원자적이라고 주장하지 않는다. eligibility 전에 receipt를 요구한다.
- **R5:** quarantine, B-FRESH1의 차단, 별도 B-RECOVERY1이 있다.
- **R6:** epoch-first 순서가 실제 `db.py` guard와 맞는다. control_epoch FOR SHARE 다음에 tenant SHARE/UPDATE를 entry에서 고르고, 승격하지 않는다.
- **R7:** managed separate-kernel VM을 고르고, WSL은 fallback이 아니다. raw 측정 schema와 승인된 budget을 요구한다. planning default만 있고 실제 값은 모두 NULL이다.
- **L-a–L-h:** 계약 수준에서 닫혔다. 예외는 아래 Info다.

## 남은 차단 사항 (Medium)

**B3-M1 — R6 census가 선택한 파일 집합 안에서만 완전하다**

ledger 밖에서도 canonical-rank lock을 잡는 경로가 있다.

- **run-before-Node 경로:**
  - `build_preparations.py:223` lock_run → project_resource_limits/storage_budgets FOR UPDATE → `:267` lock_resources(`leases.py:44` inv.nodes FOR UPDATE)
  - `shards.py:48` shard_plans → `:53` lock_run → `:58` approval_requests SHARE → `:65` lock_resources
- **lock_run만 쓰는 module:** `runs.py`, `workspace_start.py`, `output_ingestion.py`, `business_handoff.py`, `shard_completion.py`, `result_view.py`
- **runs FOR SHARE:** `build_execution_worker.py:212`

이 module들에는 callsite 행도 entry plan도 없다. `currentInversions`에는 `leases.py` 자체만 있다.

AST filter도 너무 좁다. `execute`/`executemany`와 `session.get`/`add`/`flush`/`delete`만 센다. 그래서 ledger 파일 안의 ORM 호출 40개가 빠졌다. 그중 하나가 `node_auth.py:108` `NodeAuth.lock_current`의 `select(Node).with_for_update()`다. 이 호출은 observation write에 묶인 public.nodes FOR UPDATE인데, ledger에는 `:225`만 있다.

- **수정:**
  - lock_run, lock_resources, require_execution의 모든 caller를 따라가는 transitive call graph로 census를 다시 만든다.
  - session alias가 무엇이든 모든 ORM 실행 method를 포함한다.
  - 새 B procedure(key delivery, gate 기록, issuance, reconcile receipt, observation scope)에 entry plan을 둔다.

**B3-M2 — approval 갱신 lane이 없다 (R3 잔여)**

- **현재 설계:** approval은 24시간 이하이고 release와 delegation의 상한이 된다. REFRESH와 READMIT은 모두 만료되지 않은 approval을 요구한다. 만료되면 Node를 거부하고 "새 protected approval은 외부 권한 경계"라고만 한다.
- **정의되지 않은 것:** 같은 frozen config를 다시 승인하는 절차가 Node별인지 cohort 전체의 fresh activation인지, 그 phase 행, fixture가 모두 없다.
- **위험:** cohort 전체 fresh activation이라면, 관련 없는 offline worker 하나가 24시간마다 모든 Node를 막는다. ADR100 결합이 lease에서는 빠졌는데 approval 주기로 다시 생긴다.
- **수정:** `APPROVAL_RENEW_SAME_CONFIG`를 정의한다.
  - 만료 전 overlap을 둔다.
  - 관련 없는 member의 새 증거를 요구하지 않는다.
  - 이어서 per-Node release/delegation 재발급 → gate ARM → key delivery를 거친다.
  - 다른 길을 고른다면, 이 결합을 Root가 명시적으로 수용하게 한다.

**B3-M3 — 새 gate·key-delivery·ObservationScope가 아직 계약 객체가 아니다 (R1/R2 잔여)**

bootstrap 순환은 산문으로는 끊겼다. commit 전 ARM은 business를 열지 않고, use key는 commit 후에만 전달하며, eligibility는 receipt를 요구한다. 하지만 이 gate들이 의존하는 객체가 계약으로 정의되어 있지 않다.

- **schema가 없는 것:**
  - key-delivery/possession receipt. 무엇이 소유를 증명하는지, 그리고 ledger·release hash·use-key hash·issuer identity에 묶이는지가 빠져 있다.
  - fresh activation이 기다리는 ARM ack. table·writer·grant도 없다.
  - ObservationScope 결과(AUTHORITY_UNAVAILABLE 포함)
- **keyHierarchy 누락:** release anchor의 서명 용도에 ARM이 없다.
- **fixture 공백:**
  - gateControl·safety·observeInput·signedEnvelope·roleConfig schema에는 fixture가 0건이다.
  - chain model에는 gate 상태와 receipt 입력이 없다.
- **수정:**
  - 위 schema들을 닫힌 형태로 추가한다. receipt에는 protected challenge에 대한 서명 domain을 둔다.
  - ARM ack의 writer와 EXECUTE를 정하고, ARM을 keyHierarchy에 넣는다.
  - 다음 negative fixture를 추가한다.
    - use 또는 safety key로 ARM을 서명하면 거부한다.
    - gate가 무효이거나 없으면 거부한다.
    - restart하면 gate가 없다.
    - receipt가 맞지 않으면 거부한다.
    - commit 전 delivery는 거부한다.
    - ObservationScope로 business proof를 얻을 수 없다.

## Low

- **B3-L1:** revoke는 node0에서만 모델링된다. node0은 k≥1에서 항상 CAS를 마친 member다.
  - 아직 CAS하지 않은 member가 revoke되면 C+1=8이 renewal 목표 C와 같아진다. DER은 A로 남는다.
  - 이 행을 추가하고, CAS 거부와 함께 C만으로 CAS 완료를 판정하지 않는다는 것(ledger와 DER이 판정)을 assert한다.
- **B3-L2:** authority가 모두 VALID인 LOST_RESPONSE 6행이 전부 B-RECOVERY1로 간다. 그런데 History R4·R6은 lost response를 ledger 재조회로 해결한다고 한다. 이 행이 "ledger 재조회로도 미해결"을 뜻한다고 명시하고, ledger로 해결되는 행을 추가한다.
- **B3-L3:** runtime의 "constant lock_sentinel UPDATE"는 "authority DML 회수"와 모순된다. 실제 UPDATE가 일어나기 때문이다. trigger로 막거나 SECURITY DEFINER lock procedure로 바꾸고, key_deliveries 쪽 표현과 통일한다.
- **B3-L4:**
  - safety envelope에 method/path가 없다. action→path mapping을 규범으로 정하거나 path field를 추가한다.
  - fixture의 context budget을 release anchor가 서명하는데, keyHierarchy에 그 용도가 없다. budget 서명자와 custody를 명시한다.
- **B3-L5:** capability에 host/VM과 CP 사이의 clock offset 측정이 없다. 모든 창은 30초 skew에 의존한다. offset field와 offset ≤ skew predicate를 추가한다.
- **B3-L6:**
  - grant 일치 검사가 실제로는 1/16 table만 검사한다.
  - release ≤ approval 검사는 상수(`NOW+4000`)와 비교한다.
  - `readmit(old, old)`가 같은 generation인데도 True다. 같은 generation이면 REFRESH로 보내야 한다.

## Info

- JSON Schema의 integer는 2.0e9 같은 float를 허용한다. 따라서 parser에서 float를 거부하는 동작을 규범으로 정해야 한다.
- purpose↔path 결합은 predicate에만 있다. 거기서는 올바르게 동작한다.
- displayLabel의 길이 단위(code point인지 byte인지)가 정해져 있지 않다.
- terminal의 sequence는 bodySha256을 통해 간접적으로 묶인다(72028 `TerminalFrameInput`의 Sequence/Nonce).
- online use key가 유출되면 Node가 강제하는 상한은 delegation 만료(최대 24시간)와 gate 무효화다. 300초 lease는 Node가 강제하지 않는다.
- BEFORE_INTENT의 짧은 만료를 "preflight 실패"로 분류한다. 보수적인 선택이다.
- restart 후 READMIT에는 protected signer가 가용해야 한다.
- matrix의 P는 101→102인데, 본문은 "P+2"라고 한다. final 단계가 matrix 밖에 있기 때문이다.

## 다음 첫 행동

- **Codex(owner):** 좁은 rev4로 M1–M3과 L1–L6을 닫는다. rev3과 이전 판은 immutable로 둔다.
- **Root:**
  - M2의 approval 갱신 형태를 결정한다.
  - `msg_e269bdd34436`은 이 판정을 근거로 처리한다.
  - B wire와 authority 계약은 등록하지 않고, code grant도 하지 않는다.
- **Claude:** rev4의 delta만 실제로 검토한다.
