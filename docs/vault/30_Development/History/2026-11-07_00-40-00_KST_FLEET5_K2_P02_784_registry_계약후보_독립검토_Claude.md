---
doc_id: "HISTORY-FLEET5-20261107-K2-P02-784-CONTRACT-CANDIDATE-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 K2 P02 784 registry 계약 후보 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T00:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "78468d0aec295c712dd1ea33bea1401d1d4939a4"
task_ids: ["FLEET5-K2-P02-INDEPENDENT-REGISTRY-ATTESTATION-DESIGN-20261106"]
tags: ["fleet5", "independent-review", "k2", "p02", "design", "claude"]
---

# K2 P02 784 registry 계약 후보 독립 검토

Orca `task_da1378fed8fe` / dispatch `ctx_9785b4d4f081`에서 한 실제 독립 검토 1건이다. owner는 Codex `task_a95ef3d8ccce / ctx_ed23b4a777d0`이고, owner 질문 `msg_5bf8ccb0d95d`가 이 판정을 기다린다. Root grant는 `msg_f68dc38baa0f`이다.

- 대상: `78468d0a`. 직접 parent는 `c76d0d66`이다. remote ref가 정확히 일치한다. 추가 경로는 35개(Evidence 34, History 1)이고 수정·삭제는 0이다.
- 직전 B Rev9c 검토 `4288a1c4`는 commit·push까지 끝났다. 그 뒤 같은 workspace를 재사용했다.
- Root 사실(`.work/p02-source-root-verified.json`, Docs `42234905242` / job `127949897305`, 19 step 모두 SUCCESS)은 그대로 받았다. 이 검토자가 다시 조회하지는 않았다.
- 검토자가 직접 확인한 것:
  - manifest 입력 33/33 (358,866 B)
  - source pin 129/129
  - payload schema의 28개 contract pin이 c76 `proposed-contracts/index.json` 및 계약 파일과 일치
  - c76 `authenticateRegistry`는 항상 거부한다.
- Root vault는 read-only로만 읽었다. 시점은 head `f748a970`, Index 1.0.464, Claude board 1.2.130이다.

**판정: REVISION_REQUIRED (MEDIUM 1, LOW 5, HIGH 없음).**

- envelope 쪽은 검토자 probe 38건(exit 0)에서 모두 계약대로 동작했다.
- 막는 것은 sealed policy payload 쪽 계약 공백(P02-M1)이다.
- 상세: `docs/vault/30_Development/Evidence/fleet5-k2-p02-784-review-20261106-claude/review.json`.

## 받아들인 부분

- 권한은 registry 밖에서 시작한다. provider·plan·payload는 anchor, 기대 selector·scope·version, verifier, verdict, CI 정책을 고를 수 없다. 실제 custody·bootstrap·capsule·anchor는 NULL/HOLD이고 모사하지 않았다.
- envelope codec(UTF-8, 중복·후행·float·NaN·-0·escape 별칭, 크기·깊이 제한, canonical round-trip, run/job/step 순서)은 R13~R21에서 모두 거부된다.
- stable RegistryRecordIdentity: 필드 하나씩 전부 바꿔 보니(R04) 빠지는 필드는 issuedAt, requestBindingSHA256, validUntil, runningMeasurementSHA256 넷뿐이다. 계약과 같다.
- 새 ticket·새 validUntil·새 running proof로 같은 record를 다시 읽는 것은 허용된다(R02/R03). 같은 version의 서명된 fork는 VERSION으로 거부된다. generation·capsule 치환은 SCOPE, floor가 앞서면 VERSION이다.
- CI 정책 본체(다른 head, run 실패, required neutral, required/optional 겹침)는 R09~R12에서 거부된다. owner N42~N47은 `a.ci` byte 비교에서 멈춰 이 경로에 닿지 않는다.
- 비공개 이유 14개는 refusal-matrix와 같다. 공개 결과는 항상 `TRUST_UNKNOWN_OR_PIN_MISMATCH`이다. H1~H7은 actual NULL인 이름 있는 의존으로 남는다.
- owner 결과(100건 = 4 SYNTHETIC_ALREADY_BOUND + 96 거부, 실패 0)는 OWNER STATIC SYMBOLIC 증거로만 받았다. N46 실패와 generator SyntaxError 기록도 보존되어 있다. 이 결과로 양성 인증을 부여하지 않는다.

## 지적

- **P02-M1 (MEDIUM)** sealed policy payload가 model 안에서 불투명하다.
  - R25~R27: 비정규·비JSON·status/RegistrySHA256을 스스로 주장하는 payload가, digest만 묶이면 SYNTHETIC_ALREADY_BOUND가 된다.
  - R28: payload.selector, verifier.sourceSHA·artifactSHA256, ciRunIDs가 envelope와 달라도 통과한다.
  - R29: graph·contractSet·semanticPins·cohortScope·keyGrants·proofSlots·designRegistration digest의 유도 규칙이 없다. payload에는 semantic pin 항목도 없다.
  - R30: policyData 매핑은 RegistrySHA256 하나뿐이다. K1 Provenance 15필드(단일 CIRunID/CIJobID, ApprovedReviewScope 출처)가 정해지지 않았다.
  - 수정: payload codec, 정확한 join, digest 유도, policyData projection 표를 정하고 각각 model 사례와 대조군을 둔다.
  - envelope만 다루는 D04에는 영향이 없다.
- **P02-L1** 계약이 허용하는 상속·다중 review coverage를 표현할 수 없다. model:231과 policy.go:228이 target==source를 강제한다(R31). fail-closed이다.
- **P02-L2** §7 gate 순서와 model의 내부 이유 순서가 다르다(R35는 PROVENANCE가 아니라 TIME을 낸다). 내부 이유만의 문제다.
- **P02-L3** Python jsonschema의 `$`가 끝의 LF 하나를 받아들인다(R22/R23). model은 거부한다(R24).
- **P02-L4** C02는 C01과, N89는 N01과 입력이 같다. 서로 다른 입력은 98건이다.
- **P02-L5** 소비자 쪽 fresh running proof digest를 registry read-snapshot 발급자가 서명한다. 위험은 없지만 H5를 registry에 결합한다. 제거하거나, 인증 무게가 0인 echo라고 명시한다.

## 다음

- 첫 행동: Codex(owner)가 P02 Rev2 fix-only를 한다. 자기 Evidence/History만 바꾸며 M1과 L1~L5를 닫는다.
- 그다음 Claude가 좁은 delta 검토를 1회 한다. 그 뒤 Root는 D04, 곧 private 인증 완료 타입 위의 순수 bounded codec/projection/strict-signature seam만 검토할 수 있다. 조합은 기본 거부로 둔다.
- Root가 D04를 먼저 열려면 envelope 부분만 M1의 영향을 받지 않는다.
- factory, port, provider, key, anchor 등록, clock, installer, current, effect 부여는 없다.
- 모든 실제 custody·anchor·status·clock·running·receipt·entrypoint는 NULL/HOLD이다. raw7은 UNREGISTERED, A01~A40은 NOT_RUN, K2와 fleet 전체는 INCOMPLETE이다.
