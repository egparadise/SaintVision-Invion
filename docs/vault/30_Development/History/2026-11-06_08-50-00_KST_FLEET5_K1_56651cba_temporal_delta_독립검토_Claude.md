---
doc_id: "HISTORY-FLEET5-20261106-K1-56651CBA-TEMPORAL-DELTA-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 K1 56651cba temporal·current 수정 delta 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T08:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "56651cba697f2ab6fcd7166ca4e6ea11eac28113"
task_ids: ["FLEET5-BOOTSTRAP-V5-K1-OFFLINE-VERIFIER-20261106"]
tags: ["fleet5", "independent-review", "offline-verifier", "temporal", "claude"]
---

# K1 56651cba temporal·current delta 독립 검토

Orca `task_eeb63f89fecd`, dispatch `ctx_c6a8ddbbde6d`, run `run_e57ecd84a7bc`이다. owner는 Codex `task_38393b5d1865 / ctx_ceecb3824e33`다. 첫 실제 code 검토 `c2b15b70`(REVISION REQUIRED M1/M2, L1–L5)의 수정본에 대한 실제 delta 검토다. Root 결정 `msg_87002d358dbb`의 JSON과 Root `c10e7f35`(Index 1.0.427)를 읽었다. 검토 중 Root 상태 `msg_b020041e659c`를 받았다.

- **판정: ACCEPT.** 범위는 K1 package code delta(IMPLEMENTATION 축)다.
  - blocking finding은 없다. M1, M2, L1–L5는 모두 실제 실행으로 닫혔다.
  - 비차단 residual은 R1(Low, 문서)과 R2–R6(Info)이다.
- **CI 축은 별도다.** exact-source Core `42126222201`은 terminal **FAILURE**다.
  - 원인은 K1과 무관한 Python 시험 1건이다.
  - whole-Core 성공을 주장하지 않는다.
  - TRUST-INTEGRATION(K2)과 PHYSICAL은 NOT RUN이다.
- **기계 판독 결과:** `Evidence/fleet5-k1-temporal-56651-review-20261106-claude/review.json`
- **명령·exit·시각:** 같은 폴더의 `commands.json`
- **probe source:** 같은 폴더의 `*_test.go.txt`
  - 저장소 밖 scratch module(`go.mod`/`go.sum`/`migrationverify` 복사본)에서만 실행했다.
  - product package에는 넣지 않았다.

## 대상

- **대상 commit:** `56651cba`, branch `agent/codex/fleet5-bootstrap-v5-k1-temporal-fixes-20261106`
  - parent `c6f0d95e`, package tree `d8321059`. 이 값들은 local Git에서 확인했다.
- **delta:** 49개 파일이다.
  - 제품 변경은 `migrationverify` 하나다. `current.go`·`temporal.go`가 새로 생겼고 `native/proofs/trust/verify.go`와 README·test가 바뀌었다.
  - 나머지는 owner History 2개와 owner Evidence다.
- **바뀌지 않은 것:** 다음 파일의 c6f→56651 diff가 비어 있다.
  - `ed25519.go`, `json.go`, `graph.go`, `recipes.go`, `contracts.go`, `schemas.go`
  - `resources/`, `testdata/`, `vectors_test.go`, `ed25519_test.go`
  - 따라서 27 normalized+1 native wire, C2, parser, strict Ed25519, source 28 pin은 변경되지 않았다.
  - 첫 검토의 45개 Ed25519 vector를 56651에서 다시 돌렸다. 결과 JSON은 c6f 결과와 byte 단위로 같다(45/45).
  - Python signer, 15 forgery, SPKI18/DER4는 code가 바뀌지 않아 다시 돌리지 않았다. 첫 검토 결과를 그대로 받아들인다.

## 첫 finding 해소

### M1 — 닫힘

각 cohort set으로 **완전히 일관된 live context**를 만들었다.

- Current를 그 set에서 다시 만들었다.
- 그 set 자신의 op를 current Operations로 넣었다.
- 새 current challenge를 발급했다.
- 두 native witness를 그 nonce로 Now에 다시 서명했다.

single-instant fixture와 durable fixture에서 각 8회 반복했다. 반복은 map 순서 영향을 보려는 것이다.

| set | 결과 | 거부 gate |
|---|---|---|
| 33 | DENY | RELEASED-in-history 또는 higher epoch superseded |
| 34 | DENY | lease not HELD |
| 35 | DENY | not latest sequence |
| 36 | ACCEPT | — |

**인과 확인:** scratch mutant에서 `latestCurrent`를 제거했다.

- single-instant에서 33과 35, durable에서 35가 ACCEPT로 바뀌었다(24건).
- durable 33은 op 만료 gate에서, 34는 HELD gate에서 멈췄다.
- 따라서 새 gate가 실제 인과 차단이다. SetID 불일치로 우연히 막힌 것이 아니다.

### M2 — 닫힘

durable timeline을 썼다. epoch1 HELD 0..300, release 68, epoch2 600..1200, Now 630이다.

**ACCEPT 확인:**

- current Operations에 epoch1이 없어도 Verify가 통과한다.
- Operations·Challenges·Current가 모두 nil이어도 통과한다.

**DENY 확인:**

- **History 이상:**
  - epoch1 또는 restore가 History에 없음
  - epoch1을 current에만 넣음
  - History 창을 넓힘, epoch가 틀림
  - RELEASED hash를 HELD로 넣음
- **historical challenge 이상:**
  - observation보다 30초 넘게 늦게 발급됨
  - observation 시각에 만료됨
  - nonce 또는 epoch가 틀림
  - current map에만 있음
- **key 구간이 실제 사용 시각을 덮지 않음:**
  - host-helper 키가 release event(68) 전에 만료됨
  - node-leaf 키가 관측 32 뒤에 시작하거나 52 전에 만료됨
  - root-fence 키가 600 전에 만료됨
- **Now·현재 상태:**
  - Now가 마지막 서명 event(620)보다 앞섬
  - Now 기준 cert가 REVOKED이거나 상태가 121초 지남
  - publication이 REVOKED이거나 Now 뒤에 게시됨

host-helper 키가 마지막 사용 뒤·Now 전인 625에 만료되는 경우는 ACCEPT다. 의도한 historical 의미 그대로다.

기록 시각을 −5초로 바꾼 경우는 모두 거부된다.

- 재서명하지 않으면 Ed25519 검증에서 거부된다.
- 정상 키로 재서명해도 causal journal join이나 pinned graph에서 거부된다.

### L1–L5 — 닫힘

- **L1:** SemanticInputs 365개 경로에 {nil, number, object}를 넣어 830 case를 돌렸다.
  - panic은 0건이다. constructor 거부 16, verify/current 거부 370, 영향 없음 444다.
  - nil History·Certificates·Publications·Current·head·member projection은 panic 없이 거부된다.
  - nil verifier와 빈 packet도 panic 없이 거부된다.
- **L2:** native leaf는 명시적 `ServerAuth` EKU와 `DigitalSignature`를 요구한다.
  - 생산 쪽 `transport/trust.go hasUsage`와 같다.
  - owner의 세 음성 시험이 이번 실행에서도 통과했다.
- **L3:** live probe 결과다.
  - 관측이 Now−30초면 ACCEPT, Now−31초면 DENY다.
  - challenge가 Now에 만료되면 DENY다.
  - owner의 historical 경계 시험도 이번 실행에서 통과했다.
- **L4:** NewVerifier 뒤 caller가 입력을 바꿔도 결과가 그대로다.
  - 바꾼 입력은 History op·challenge, witness byte, member projection, member DER이다.
  - 반환된 `Report.Digests`를 바꿔도 Verify·current 결과가 그대로다.
  - race 안전은 주장하지 않는다. 호출 중 caller가 입력을 단독으로 소유한다는 계약에서만 성립한다.
- **L5:** 원 owner History에 날짜가 붙은 정정이 들어갔다.
  - 235/121은 이전 시도로 표시됐다. 최종은 attempt4 61/238, K1 30/124다.
  - frozen c6f/37fe 참조는 다시 쓰지 않았다.

## 새 app API 검토

- **History:** live Operations·Challenges와 분리된 typed 입력이다.
  - Verify는 current 입력이 필요 없다.
  - History의 모든 op는 인증된 HELD lease와 정확히 같아야 한다.
- **NativeWitnesses:** 등록 순서대로 member당 하나다.
  - Now에서 current challenge, op/epoch, cert nonrevocation, key, 120초 age를 다시 인증한다.
  - 다음 witness는 모두 거부됐다: 옛 retained, 시각만 바꾼 것, 틀린 nonce, 다른 member, historical challenge를 current로 바꿔 붙인 것.
- **historical head를 current로 쓸 수 없다.** current head는 두 조건을 모두 만족해야 한다.
  - set field와 같아야 한다.
  - Now에서 다시 검증한 readback(120초 이내)과 같아야 한다.
  - +121초 readback은 거부된다.
- **ABSENT head fail-closed:** 명시적 K1 경계로 수락한다.
  - current 유도는 head가 PRESENT인 set에만 정의된다. cohort-01..27처럼 publication 전 단계는 항상 거부된다.
  - 이 거부는 맞다. ABSENT head에 대해 K1이 인증할 수 있는 native 기대 상태가 없다. 이를 새로 만들면 새 trust 입력이 된다.
  - 쓰임새의 한계도 있다. 그 단계에서는 K1이 current view를 주지 않는다. 이력 인증은 계속 된다.
- **K2가 할 일:** History·witness·challenge·status·installed trust를 실제로 생산하고 인증하는 것은 K2다. K1의 API assertion은 그 구현을 대신하지 않는다.

## 비차단 residual

- **R1 (Low, 문서):** README에 PRESENT-only 경계가 없다. 이 경계는 owner History에만 적혀 있다.
  - `VerifyCurrentProjectionSet`의 ABSENT 분기는 이제 성공할 수 없다.
  - 다음 K1 수정이나 K2 인계 때 README에 반영한다. code 변경은 필요 없다.
- **R2:** 서로 다른 migration 사이의 fence 비교는 K1 범위가 아니다. K2 live Operations가 맡는다.
- **R3:** 만료됐지만 grant가 남은 키를 가진 사람은 기록 시각을 앞당겨 서명할 수 있다. causal join과 graph의 시각 pin이 이를 완화한다. offline 검증에 원래 있는 한계다.
- **R4:** historical native는 challenge 발급 30초 전까지 소비를 허용한다. Root의 30초 skew 결정 안이다.
- **R5:** 동시성 시험은 Verify만 다룬다. `VerifyCurrentProjectionSet`은 정적 검토(생성 뒤 쓰기 없음)에 기댄다.
- **R6:** 읽지 않는 SemanticInputs field는 nil이어도 결과에 영향이 없다. c6f부터 있던 동작이며 delta가 아니다.

## 실행과 CI

- **환경:** Windows amd64, Go 1.27.0, `CGO_ENABLED=0`. local `-race`는 NOT RUN이다.
- **K1 focused:** 08:13:45–08:14:27 KST.
  - 42 top / 165 PASS event / 0 fail / 0 skip, exit 0.
  - owner 주장과 같지만 owner 증거와 별개로 직접 실행했다.
- **전체 Node:** 08:14:42–08:15:30 KST.
  - build, vet, test 모두 exit 0.
  - 73 top / 279 PASS event / 0 fail / 0 test skip.
  - 7개 package pass, test 파일이 없는 package 6개.
- **probe 실행:**
  - attempt1은 exit 1이다. M1/M2/current probe 104건은 모두 기대대로였다. 그 뒤 L1 fuzz가 Go 기본 10분 timeout에 걸렸다(harness 문제). 기록은 보존했다.
  - L1/L4만 attempt2로 다시 돌렸고 exit 0이다.
  - mutant 실행은 의도대로 exit 1이다.
- **hosted Docs `42126225708`:** job `127591021794` SUCCESS, exact head.
- **hosted Core `42126222201`:** terminal FAILURE.
  - s01 job은 success다.
  - core job step 15 Linux `go test -race -json ./...`는 success다. count는 artifact를 받지 않아 파싱하지 않았다.
  - step 33 pytest는 1 failed / 9214 passed / 46 skipped다.
    - 실패 시험은 `test_build_preparations_real_pg.py::test_prepare_rate_limit_is_enforced_before_repeated_failed_work`다.
    - delta에 Python 변경이 없다. 같은 시험이 c6f Core `42113810160`에서는 통과했다.
    - 그래서 **UNRELATED CI GATE FAILED**로 분류한다.
    - 원인은 확정하지 않았다. 재현하지 않았다(DB 작업은 범위 밖).
  - step 40 `go test ./...`는 앞 실패 때문에 skipped다.
  - 선택 native proof와 S08 skip은 pass가 아니다.
- **job log:** sha256 `ae92c0f5…54ae`(417144 byte). hash와 파싱 요약만 남겼다. raw log, ZIP, JUnit은 commit하지 않았다.

## 다음

- Root가 실제 판정을 수신한다.
  - all-success exact Core를 위해 재실행할지, 결합 source로 갈지 정한다. Codex의 test-only clock card가 `msg_b020041e659c`에 있다.
  - 그 뒤 K1 bounded completion을 판단한다.
- K2, runtime 40 case, 5대 PC 운영 인수는 NOT RUN이다.
- R1은 다음 K1 수정 때 README에 반영한다.
