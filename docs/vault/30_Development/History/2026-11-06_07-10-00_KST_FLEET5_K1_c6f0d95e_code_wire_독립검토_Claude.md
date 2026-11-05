---
doc_id: "HISTORY-FLEET5-20261106-K1-C6F0D95E-CODE-WIRE-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 K1 offline verifier c6f0d95e code·wire·crypto·native 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T07:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "c6f0d95ecbcd79fac96673c194e2368b510ad827"
task_ids: ["FLEET5-BOOTSTRAP-V5-K1-OFFLINE-VERIFIER-20261106"]
tags: ["fleet5", "independent-review", "offline-verifier", "ed25519", "node-wire", "claude"]
---

# K1 offline verifier c6f0d95e 독립 code+wire 검토

Orca `task_5627222e0f59`, dispatch `ctx_0918954c585c`. owner는 Codex `task_38393b5d1865 / ctx_ceecb3824e33`다. 이 CODE와 새 package-local wire에 대한 첫 실제 독립 검토다. 이전 설계 검토(6b12d3ab), Root packet, e50, R-L1은 code 승인으로 세지 않았다.

- **판정: REVISION REQUIRED.** blocking은 Medium 2건(M1, M2)이다. Low는 5건(L1–L5)이다.
  - crypto, strict JSON/C2, source pin, 정규화 wire, key 범위 조회, native M2 byte 호환은 실제 실행으로 확인했고 결함을 찾지 못했다.
  - 남은 결함은 현재 projection 유도와 이력 시간 모델에 있다.
- **기계 판독 결과:** `Evidence/fleet5-k1-c6f-code-wire-review-20261106-claude/review.json`
- **명령·exit·시각:** `commands.json`
- **원시 결과와 probe source:** 같은 Evidence 폴더에 있다. `*_test.go.txt`는 scratch worktree에서만 실행한 reviewer probe이며 product package에 넣지 않았다.

## 대상과 범위

- **대상:** `agent/codex/fleet5-bootstrap-v5-k1-offline-verifier-20261106`의 `c6f0d95e`, parent `e50c1482`.
- **변경 범위:** 실제 `git diff`로 139개 파일이 모두 A다. 위치는 `services/node-agent/migrationverify`와 owner History/Evidence뿐이다.
  - owner의 139 경로 주장과 정확히 같다.
  - package tree `378a3230`과 107개 blob/SHA256/byte 주장이 실제 Git과 일치한다(`source-audit.json`).
- **읽은 것:** package README, Go source 10개와 test 10개, resources·testdata, owner History와 Evidence, Root `6e3fc79c`의 `k1-proof-wire-gap-decision-root.json`(`msg_b005ebff62ab`), 기존 `transport/peer_floor.go`·`peer_floor_canonical.go`·`cmd/inv-node/main.go`의 native 생산 경로.
- **신뢰 경계 기준:** `InstalledTrust`와 `TrustedContext`는 신뢰된 application 입력이다. K2 adapter가 없다는 이유로 결함을 만들지 않았다. Packet이 trust·key·grant·codec·clock·schema·digest mode를 고를 수 있는지는 따로 확인했다.

## 확인되어 받아들이는 부분

### Source와 wire 고정

- 28개 source pin은 8874b2df 원본 blob, package 복사본, 고정 SHA256/byte가 모두 같다. offline schema resource는 17개다.
- 제안 contract 28개의 raw/schema hash가 index와 같다. slot은 77개다.
  - codec은 normalized 27개, native 1개다.
  - freshness는 fresh 18개, immutable-provenance 7개, validity-bounded-approval 3개다.
- 28개 schema는 모두 닫혀 있다. `migrationId`·`operationId`는 fresh 18개 schema에만 있다. signer는 `{role,keySPKISHA256,signatureHex}`로 닫혀 있다.
- 정규화 wire는 Root 결정과 같다.
  - 서명 입력은 `domain || 00 || C2({body, signer:{role,keySPKISHA256}})`다.
  - referent bytes는 C2와 정확히 같아야 한다. LF 별칭은 없다.
  - reference metadata는 고정 contract에서 오고, typedSubject와 scopeSHA256은 포함 source에서 다시 계산해 전부 비교한다.

### Strict parser와 C2

- 다음을 거부한다: unescape 뒤 중복 key, 짝 없는 surrogate, 비정수·지수·`-0`, 2^53 이상, trailing data, 16MiB 초과, depth 128 초과.
- 시간은 whole-second UTC 왕복이 같아야 한다.
- C2는 검증된 값의 Go `json.Marshal`이다. argv codec은 HTML·U+2028/2029 escape를 하지 않는 별도 규칙이다.
- graph expression은 compile 시점에 operator·depth를 검사하고, add는 safe-integer 합만 허용한다.

### Ed25519

- `decodePrimePoint` 수학을 직접 확인했다.
  - d, sqrt(−1), a=−1 complete extended 덧셈, y<p, x=0 sign, `[L]P == O` 그리고 `P != O`가 맞다.
- S<L을 검사하고, A와 R 모두 prime-order를 요구한다. 검증식은 stdlib의 pure Ed25519에 맡긴다. prehash·context 변형은 없다.
- **독립 재현:** reviewer가 product code 없이 pure-Python RFC8032를 새로 작성했다(`ed25519_independent.py.txt`).
  - RFC8032 TEST 1–3 서명을 서명 계산으로 재현했다.
  - 공개 vector 45개에서 product와 독립 판정이 45/45 같다(`ed25519-go-results.json`).
  - **adversarial vector 15개:** identity forgery 2, 차수 2·4·8 torsion T1–T7, mixed-order A 3, 비정규 3. Go stdlib과 Python cryptography 50.0.1이 모두 받지만 product strict는 거부한다(`crypto-lib-crosscheck.txt`).
  - 이 vector는 offline 반례다. live fleet 실패 관측이 아니다.
- SPKI는 SHA256(PKIX DER)이다. 독립 계산 18/18, cryptography DER 4/4가 일치한다.

### Key 범위와 rebind 공격

- role은 contract가 고정한다. scope는 다시 계산한 subject에서 Node·component·cohort로 정한다.
- key는 `role + C2(scope) + SPKI`로 외부 grant에서 찾는다. grant 기간은 trusted Now와 서명된 observedAt 둘 다에서 확인한다.
- reviewer의 full-rebind probe는 모두 해당 인과 이유로 거부됐다. 무관한 hash 불일치로 거부된 경우는 없다.
  - node-floor-v2, independent-code-review: `proof signer differs from exact containing Node/reviewer key`
  - build-provenance, inventory-head-readback, 다른 Node의 같은 role key로 서명한 process-quiescence: `key not authorized for exact current role/scope`
  - owner test는 `e != nil`만 확인한다. 이번 probe가 거부 이유를 처음 기록했다.

### Native M2

- 기존 생산 경로로 receipt를 다시 만들었다.
  - 생산자 Go type(int64 observedAt, int servingPID, uint32 journalUID)을 썼다.
  - `transport.CanonicalPeerFloorBody`, `transport.PeerFloorDomain`, `json.Encoder`(끝 LF 포함)를 썼다.
- 결과 bytes가 K1 fixture receipt와 byte 단위로 같고 `AuthenticateNativeHistory`가 인증한다.
- `NativeHistory`는 fresh가 아닌 별도 type이다. 정규화 re-sign이나 fallback은 없다.

### 경계와 출력

- Packet에는 Records와 Referents만 있다. plan은 설치된 RegistrySHA256을 선택해야 한다.
- NewVerifier는 입력을 deep copy한다. 다음은 fail-closed로 거부한다: zero/nil/all-zero registry, 빈 grant, 비UTC Now.
- nil·zero Verifier의 각 method는 error를 돌려준다. Report digest map은 내부 상태와 별칭이 아니다.

## 결함

### M1 (Medium) VerifyCurrentProjectionSet가 대체된 set을 현재로 유도한다

- **증거(`current-probe-results.json`):** 각 set 자신의 필드로 Current를 만들어 시험했다.
  - cohort-01–33은 operation `fixture-operation-migration`, epoch 1, lease-migration HELD다. 모두 ACCEPT였다.
  - cohort-35는 cohort-36으로 대체됐지만 ACCEPT였다.
  - 같은 인증 packet 안에 `fence-released`(같은 operation, epoch 1, RELEASED)와 `lease-restore`(epoch 2 HELD)가 있는데도 그렇다.
  - cohort-34의 거부는 우연이다(`current original Node projection binding mismatch`).
- **owner test의 공백:** owner negative `released epoch1 substituted for current restore-held epoch2`는 SetID 불일치(`no trusted current set context`)로만 통과한다. 해제된 epoch를 Current로 준 경우를 시험하지 않는다.
- **원인:** lease를 hash, operation, migration, epoch, expiresAt으로만 찾는다. 다음을 검사하지 않는다.
  - mode가 HELD인지
  - `Current.LeaseEnvelopeSHA256`이 trusted operation의 lease와 같은지
  - 같은 operation·epoch의 인증된 RELEASED나 더 높은 epoch lease가 없는지
  - set이 해당 operation의 최신 sequence인지
- **수정:** 위 네 조건을 추가한다. cohort-33, 34, 35로 hash가 모두 일관된 Current를 만들어 negative test로 넣는다.

### M2 (Medium) 이력 시간 모델이 해제된 operation을 현재 operation으로 제공하게 만든다

- **현재 동작:** Verify는 포함된 모든 fresh proof를 trusted Now 기준으로 평가한다. 조건은 age ≤ min(plan, 120s)와 now < validUntil이고, 해당 operation이 TrustedContext.Operations에서 유효해야 한다.
- **fixture의 가정(`time-probe-results.json`):**
  - 두 operation의 모든 proof를 한 시각(2030-01-01T00:00:00Z)에 서명했다.
  - 두 operation에 같은 창 00:00:00–00:01:00을 줬다.
  - 따라서 RELEASED된 epoch-1 operation도 동시에 현재 유효 operation으로 주어져야만 통과한다.
- **결과:** 실제 이력에서 epoch-1 fresh proof가 120s보다 오래되었거나 epoch-1이 정당하게 현재가 아니면 Verify를 통과할 수 없다. 어느 결과가 맞는지 계약도 test도 정하지 않았다.
- **수정 (둘 중 하나):**
  - 이력 모드를 정의한다. fresh proof를 자신의 인증된 lease 창과 서명 시각으로 검증하되, 현재 권한으로 이전되지 않게 한다. 현재 Now/120s/현재 operation 조건은 현재 유도에만 적용한다.
  - 또는 Verify를 단일 시각 packet으로 제한한다고 계약에 명시한다.
  - 어느 쪽이든 epoch-1 획득·해제 뒤 epoch-2가 오는 다시각 timeline fixture로 두 결과를 시험한다.

### Low

- **L1:** 형식이 잘못된 trusted SemanticInputs가 fail-closed 대신 panic을 일으킨다. 예: `plan.expiresAt`이 숫자면 `interface conversion` panic이 난다(verifyNative, freshness). Packet으로는 도달할 수 없다. 관련 schema가 모두 닫혀 있고 type을 정하기 때문이다.
- **L2:** native leaf의 EKU 검사가 생산자보다 약하다. `x509.Verify(ServerAuth)`는 EKU가 없는 leaf를 받는다(probe로 확인). 생산자는 명시적 ServerAuth를 요구한다. 정확히 등록된 DER만 쓰므로 위험은 완화되지만, 명시적 EKU와 digitalSignature를 요구해야 한다.
- **L3:** native 서명 observedAt이 trusted challenge 창에 묶이지 않는다. IssuedAt보다 5초 이른 관측도 ACCEPT였다. `IssuedAt−30s ≤ observed < ExpiresAt`를 요구해야 한다.
- **L4:** Packet bytes를 방어적으로 복사하지 않는다. hash, parse, 재정규화가 caller 소유 slice를 각각 따로 읽으므로, caller가 동시에 바꾸면 TOCTOU가 생길 수 있다. 정적 발견이며, 진입 시 한 번 복사하면 된다.
- **L5:** owner History의 test 수가 오래됐다.
  - 본문은 06:11의 61/235와 K1 30/121을 최종으로 적었다.
  - 실제 최종은 `local-go-validation.json` attempt 4(06:28:10–06:28:31 KST)의 61/238, K1 30/124다. `node-go-suite.log`, attempt 3, reviewer 실행과 같다.
  - 235는 attempt 2이고, 121은 06:16 focused 실행이다. 그 뒤 subtest 3개가 추가됐다.
  - attempt 1 실패(`TestAPI2RejectsEveryOldFieldAndNodeCohortTypeConfusion`)는 보존돼 있다.

## 실제 실행과 증거

- **도구:** Go 1.27.0 windows/amd64, CGO_ENABLED=0. Python 3.14.7 `-I -B`. 실행은 한 번에 하나씩, 저메모리로 했다.
- **reviewer 실수 보존:** 06:54:15에 처음 실행한 `GOFLAGS=-mod=mod go build`가 scratch worktree의 go.mod에서 indirect 표기를 지웠다. 되돌린 뒤 모든 기록 결과를 다시 만들었다.
- **Node 전체 (06:54:59–06:55:40):** `go build ./...`, `go vet ./migrationverify`, `go test ./... -count=1 -json` 모두 exit 0이다.
  - top-level 61개, PASS event 238개다. fail 0, test skip 0이다.
  - no-test-files package 6개는 test skip이 아니다.
- **K1 (07:09:29–07:09:49):** clean tree에서 30/124, exit 0이다.
- **Crypto probe:** 06:58:03–06:58:38. **source audit:** 07:01:04. **의미 probe:** 07:04:31–07:07:37. 모두 exit 0이다.
  - probe는 결과를 기록만 하고, ACCEPT나 PANIC이어도 test를 실패시키지 않는다.
- **source Core `42113810160`:** 07:07:58 KST에 읽기만 했다. rerun과 cancel은 하지 않았다.
  - headSha c6f0d95e이고 아직 in_progress다.
  - job 127548012850의 step `Test Linux Node concurrency and crash boundaries`는 06:36:46–06:40:07 KST success다. job 127548013352 s01도 success다.
  - Linux race는 보조 증거로만 쓴다. local race는 NOT RUN이다. 전체 Core·installer·kernel·Python 승인은 PENDING이며 주장하지 않는다.
- **비밀 정보:** 공개 vector와 owner fixture의 메모리 내 ephemeral TEST key만 썼다. production key는 읽거나 만들지 않았다. scratch 경로 prefix는 commit하지 않았다.

## 하지 않은 것

- K2 adapter와 trust 설치는 하지 않았다.
- 미래 runtime 효과 40개, OS lock, Engine, DB, PKI, 물리·원격 작업, 전체 제품은 NOT RUN이다. live registry와 key는 NULL/HOLD다.
- product 코드, owner 파일, ADR, 공유 board, registry, Obsidian apply, process 조작은 하지 않았다.
- 이 검토는 K1 승인도, K2 code gate도 아니다.

## 다음 첫 행동과 담당

- **Codex:** M1·M2 수정과 test를 담은 K1 revision을 만든다. L1–L5는 같은 revision에서 닫을 것을 권한다.
- **Root:** 그 revision과 terminal 상태의 실제 full Core를 묶은 뒤 Claude에게 delta 재검토를 배정한다.
