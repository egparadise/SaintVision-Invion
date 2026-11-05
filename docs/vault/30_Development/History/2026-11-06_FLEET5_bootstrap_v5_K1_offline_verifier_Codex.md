---
doc_id: "HISTORY-FLEET5-20261106-BOOTSTRAP-V5-K1-CODEX"
title: "FLEET5 bootstrap v5 K1 offline verifier 구현"
version: "1.1.1"
status: "review"
author: "Codex"
reviewer: "Claude via Root pending actual code review"
updated: "2026-11-06T07:50:35+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "e50c148287779add421265868ef16909ed984650"
task_ids: ["FLEET5-BOOTSTRAP-V5-K1-OFFLINE-VERIFIER-20261106"]
tags: ["fleet5", "bootstrap", "offline-verifier", "codex"]
---

# K1 착수와 범위

2026-11-06 수정본의 L5 정정: 아래 06:11·06:16의 235/121 집계는 그 시각의 이전 시도 관측이다. 원 c6f의 실제 최종 attempt4는 06:28:10–06:28:31 KST, 전체 Go61상위/238 PASS event·K1 30상위/124 PASS event였다. 각 시도의 성공·실패 기록은 보존하며 새 수정본의 검증으로 재사용하지 않는다. 실제 c2b 독립 코드 검토는 M1/M2 및5Low 수정 필요이고, 후속 변경은 [[2026-11-06_FLEET5_K1_temporal_corrections_Codex]]에 기록한다. frozen c6f/37fe의 문서는 변경하지 않았다.

Owner Codex, 실제 독립 code reviewer는 Root를 통한 Claude이며 아직 code 검토를 수행하지 않았다. Orca task `task_38393b5d1865` / dispatch `ctx_ceecb3824e33`의 계속 작업이다. Root `msg_a21df0511488`, `msg_bd4f1e921201`가 새 code 범위를 부여했다. 최신 Root Index 1.0.418 / Codex 1.0.379, agent-delivery 1.1.0 / core-reliability 1.0.0과 AGENTS 필수 지침을 적용한다. 공유 board·task registry·원문·Obsidian apply는 작업 범위에서 제외한다.

Orca가 만든 새 worktree `fleet5-bootstrap-v5-k1-offline-verifier-20261106`, branch `agent/codex/fleet5-bootstrap-v5-k1-offline-verifier-20261106`의 실제 초기 HEAD는 위 base와 같다. setup hook을 skip했고 새 agent를 만들지 않았다. 기존 8874 설계 branch를 이동하거나 code base로 사용하지 않았다. 설계 source `8874b2dfe0dda9a019bd5f334636668290702e13`, 실제 설계 review `6b12d3ab0e1f3e3cf623b62c528e0e096ba48af6`의 I-a~I-e를 읽었다. Root 등록 manifest raw SHA256 `a0a05427c40499ac32e52c58982a84bceb4b4e833b68c601f9373d93d80aa562`를 대조했고 후속 Root publication `7ec1af26f56a8a0566c589720cd00f04b89e91a3` 통지를 받았다. 그 Docs 성공은 아직 주장하지 않는다.

구현은 제공된 불변 입력에 대한 pure offline 검증이다. 파일 생성·예약·잠금·journal·Engine·container·DB·SSH·PKI·Node·trust 설치·schedule·물리 clock 작업을 하는 runtime adapter는 없다. 실제 key/binding/배포 trust는 NULL/HOLD이며 K2 효과 구현과 40개 미래 runtime case는 이 카드의 완료로 바꾸지 않는다.

## 초기 실제 확인

환경은 Windows amd64, Go 1.27.0, main `.venv` Python 3.14.7 `-B`다. 외부 설치·pip·Docker·remote 작업은 실행하지 않았다. accepted source의 17 schema와 11 normative/synthetic fixture 총 28개 Git blob을 package-local 새 경로로 가져와 각각 byte 수와 SHA256을 대조했다. 기록은 `Evidence/fleet5-bootstrap-v5-k1-20261106-codex/init.json`이다. 원본 195 object의 dummy 서명은 실제 crypto positive가 아니다.

- 첫 `go test ./migrationverify -count=1`: strict parser/canonical/calendar tests exit 0.
- schema/vector 추가 후 같은 명령 exit 1: Go 기본 regex engine이 pinned ECMA `\\u0000` escape를 받지 못했고 test가 vector의 `derivedDigestSHA256` field 이름을 잘못 읽었다. 실패를 보존하며 schema bytes는 바꾸지 않았다.
- 8개 고정 pattern에만 한정한 ECMA→RE2 NUL escape 대응과 test field 이름 교정 뒤 같은 명령 exit 0. 17개 전체 closure compile, 195 shape/digest 및 4 byte vector를 실제 Go에서 확인했다. 이 결과는 인증·운영 합격이 아니다.

## 현재 계약 질문과 다음 행동

v2 `revision-contract.md`의 proof 규칙은 외부 등록된 exact referenced bytes/closed contract/verifier를 요구한다. 그러나 실제 accepted `proof-slot-registry.json`의 77개 slot은 `actualContractSHA256`와 `actualVerifierSourceArtifactCIReview`가 모두 null이며, 112개 reference의 signed referent wire bytes는 발행하지 않는다. `recipe-definitions.json`은 subject를 정의하고 reference schema는 서명 자체를 포함하지 않는다. K1이 새 producer 서명 wire를 추측해 기존 계약으로 가장하지 않는다.

Root는 실제 공백을 확인하고 `msg_b005ebff62ab`로 새 package-local wire 제안을 승인했다. 실제 publication은 `6e3fc79c22886a7d4424b7831871ce6ed1597d48`, Root 통지는 Docs42105400270 exact head/all jobs SUCCESS와 sync 완료다. Index 1.0.419 / Codex 1.0.380, 범위 governance 1.0.1을 읽었다. 기존 8874/17 schema/등록 hash는 바꾸지 않았다.

## 구현 결과와 신뢰 경계

새 `services/node-agent/migrationverify`에 pure verifier와 package-local proposal 28 contract/schema/codec/field-map/domain/raw hash를 추가했다. 27 normalized proof는 body와 signer의 role/SPKI를 보호하며 fresh만 migration/operation 필드를 갖는다. native codec 하나는 기존 flat M2·Unix seconds·domain·nodeSignature·raw LF identity를 그대로 검증한다. 참조 validUntil은 signed claim으로 가장하지 않고 age/인증서/plan/lease 최소값으로 계산한다. 임시 TEST key/인증서는 `_test.go` 안 메모리에서만 만들고 실제 키를 읽거나 기록하지 않았다.

strict parser, 실제 UTC calendar/C2/argv 분리, 정확한 scope별 외부 key lookup, strict Ed25519 A/R prime-order/nonidentity와 S<L, 77 slot/28 recipe, 112 subject의 containing-source 유도, graph와 별도 proof policy, 원본 crypto/lease/head 인증 후 DAG·unsigned digest, 현재 ordered 양 Node projection 확인을 구현했다. API:2 Node와 cohort prior는 분리한다. 별도 native historical 결과에는 fresh 승인·validUntil·현재 lease를 넣지 않으며 fresh 검증으로 대체할 수 없다.

`InstalledTrust`와 `TrustedContext`는 packet 밖에서 로드된 **신뢰된 application 입력 경계**다. 패키지는 구조·정확한 고정 descriptor/schema/역할·scope·key·metadata·현재 관측 결속을 검사하지만 이 값이 실제 설치/CI/review/관측 producer에서 왔는지 자체 I/O로 입증하지 않는다. K2가 실제 artifact/등록과 신뢰 생산자를 결속해야 한다. caller의 provenance 모양 문자열이나 fixture 정책을 실제 권한으로 바꾸는 adapter/flag는 없고 원래 NULL live pin은 여전히 HOLD다. CLI나 inv-node 연결을 추가하지 않았다.

## 실제 검증과 실패 보존

- 28개 per-contract public ephemeral vector를 실제 Go에서 생성·검증했다. 원래 195 packet에는 없는 optional 두 slot을 TEST packet에 추가해 77/77 slot과 28/28 codec을 다뤘다. 기본 crypto packet은 원래 195 객체/112 참조와 같고 115 새 outer signature +112 참조 검증이다. 원래 dummy signature 검증은 0이다.
- Python 3.14.7 `-I -B`/cryptography가 public vector의 실제 Ed25519 28개, canonical SPKI 28개, raw hash 28개를 별도로 대조하고 message/signature 변조 56개를 거부했다. `public-ephemeral-proof-vectors.json`, `cross-language-vectors.json`, `public-vectors-go.jsonl`에 실제 public bytes/결과를 보존했다. private key는 없다.
- source recipe/policy: 원래 112개 subject와 75 populated slot을 각각 유도했다. 추가 optional TEST evidence로 나머지 두 slot도 실제 crypto를 검증했다. 모든 112 key/subject 변조와 Node/cohort/component의 실제 잘못된 key로 서명·종속 hash를 모두 재결속한 packet을 거부했다.
- RFC8032 vector와 small/mixed-order·noncanonical A/R·S>=L, strict 숫자/Unicode/calendar, fresh/approval/immutable 분리, 원본과 current M2 분리, current nonce/epoch/cert/raw bytes/expiry, API 옛 field 44개와 type 혼동 43개, graph missing/cycle/duplicate/leaf coverage, extra/partial packet/current set, 동시 읽기 4개를 확인했다. K1 30 top-level test에 121 PASS event(부모 subtest 포함), leaf 110개다.
- 최초 Node suite attempt1은 새 API test의 잘못된 기대 때문에 exit 1이었다. response 22개는 schema만으로 종류를 결정하지 않고 authenticated request graph에 결속하는 accepted 설계다. schema 단계 거부 21개와 graph 단계 거부 22개로 test를 정정했고 원본 실패 log/JSON을 `node-go-suite-attempt1.log`, `local-go-validation-attempt1.json`에 보존했다. 재실행 근거는 이 한정 test 수정이며 실패를 숨기거나 제품 계약을 완화하지 않았다.
- 06:11:23–06:11:52 KST 당시 시도 `go test -json -count=1 ./...`, `go build ./...`, `go vet ./migrationverify` 모두 exit 0. 그 시도 Go suite는 top-level 61개, PASS event 235개(leaf 213), test skip 0, 기존 Node 7개 package PASS다. no-test-files package 6개는 시험 skip으로 계산하지 않는다. `local-go-validation.json`과 해당 log는 이 이전 시도의 기록이다.
- Windows Go 1.27.0의 실제 `CGO_ENABLED=0`이므로 local `-race`는 NOT RUN이다. exact source hosted Core의 Linux `go test -race ./...` 결과가 별도 필수다. 전체 Core/Docs CI와 실제 Claude code+wire review는 아직 대기다.
- full Node suite 뒤 nil/zero-state verifier의 missing registry 경계를 두 군데 강화했고 06:16:06 KST 당시 K1 focused 재검증은 30 top-level/121 PASS event/exit 0이다. 이 집계는 뒤의 실제 최종 attempt4와 구분한다. 기존 Node source 변경은 없다. public identity-point forgery는 local Go 표준 verifier와 별도 Python library가 받지만 K1 strict verifier는 거부한다는 실제 offline 반례도 기록했다. stdlib 성공을 prime-order 검증으로 세지 않는다. 이 public adversarial vector는 live fleet 실패 관측이 아니다.
- 06:14:11–06:15:14 KST docs/ontology-generation/ontology/contract-bindings/frontend/path-ratchet/single-source-ratchet/test-sync/build-docs/sync-check 10개가 모두 exit 0이다. 경로 baseline 290과 중복 baseline 16은 unchanged/no new/no stale다. sync-check는 3216 managed/764 pending/0 conflicts와 No writes를 보고했다. 오래된 vault를 export하거나 apply하지 않는다. gate별 실제 argv/시각/exit/log는 `local-source-gates.json`에 있다.
- 기존 설계 branch HEAD와 upstream은 모두 `8874b2dfe0dda9a019bd5f334636668290702e13`이고 실제 status는 clean임을 다시 확인했다. 원본 source vault·board·registry·기존 Node code·protected r5·runtime·장비를 변경하지 않았다.

## 다음 첫 행동과 담당

Codex가 필수 docs/ontology/계약/frontend/path/single-source/sync-check gate와 full staged-path 감사를 마친 뒤 정상 commit/push 및 exact Core/Docs CI를 실행한다. Root가 그 실제 source/CI를 받아 별도 Claude의 code+새 wire/crypto/native adapter 검토를 배정한다. K2 구현·실제 trust 설치·40 future runtime case·물리 장비·기존 원래48-task/VFCL·전체 FIVE 인수는 이 카드에서 완료로 바꾸지 않는다.
