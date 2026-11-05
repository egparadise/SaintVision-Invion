---
doc_id: "HISTORY-FLEET5-20261106-BOOTSTRAP-NORMATIVE-CONTRACTS-F932-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 bootstrap 규범 contract 제안 f932283d 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T00:44:29+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "315411bc"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "bootstrap", "contract-proposal", "claude"]
---

# bootstrap 규범 contract 제안 f932 검토

Orca task `task_c5957c5bb2f5`, dispatch `ctx_8d0de000717d`. [[2026-11-06_00-26-51_KST_FLEET5_P0_test_isolation_46b4_검토_Claude]]로 46b 작업을 끝낸 뒤 맡은 별개의 architecture·contract 제안 검토다.

- **판정 범위:** 설계 contract 제안만 판정한다. 등록된 product contract, code, runtime CI, physical, 운영 수락이 아니다.
- **관측 시각:** 00:38:04~00:44:29 KST. 첫 fetch와, 작성 전 마지막 branch 확인의 shell `date` 출력이다.
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/bootstrap-normative-contracts-f932-review.json`

## 대상과 방식

- **대상:** `agent/codex/fleet5-consecutive-leaf-rotation-20261105`의 `f932283de3fd96f3816a99ea5c38d6d14969b930`
  - base는 `803ad270`. 32개 문서, +15238. non-docs는 0개다.
  - 제안 History는 v1.0.0이고, evidence 디렉터리에 31개 파일이 있다.
- **읽은 방식:** `git archive`로 Git object만 scratch에 꺼냈다. 작성자 checkout은 건드리지 않았다.
- **ABI 참고:** `4a928310`은 binding이 아닌 참고로만 본다. 8baaa6b5에서 exact head NOT ACCEPTED로 판정했다.
- **제안 Docs 42054280142:** root가 확인했다고 알려 왔다. 나는 다시 확인하지 않았다.
- **도구:** main `.venv` 3.14.7 `-B -I`, jsonschema 2020-12와 referencing registry, 내 Go `Marshal` emulator. Go 실행과 서명은 하지 않았다.

## 독립 확인

| 항목 | 결과 |
|---|---|
| artifact hash | **30/30** 같다. `proposal-validation.json` 자신은 self-reference라 hash 대상에서 빠진다 |
| schema | 9/9가 metaschema에 맞는다 |
| 구조 양성 fixture | 6/6 VALID |
| adversarial | **46/46.** schema 층 41개는 schema가 거부한다. semantic 층 5개는 schema는 통과하고, 내 semantic predicate가 거부한다. owner의 층 표시가 정직하다 |
| 필수 field 제거 | owner 1083/1083 거부. 내가 6개 artifact의 모든 key를 따로 세어 봐도 같은 1083개이고, 모두 거부된다 |
| 내 mutation | 아래 참고 |
| API | 14개 method 모두 valid. 내 음성 case 70/70 거부(force, workerRoot, argv, bool epoch, 틀린 method). 응답의 `sideEffectPermitted`는 const false다 |
| strict byte | J01~J05: 입력 SHA256과 거부 이유가 5/5 같다 |
| canonical body | 6/6 재현했다: body bytes와 SHA, domain, domain+body, envelope. body에 newline이 없고, `signatureVerified`는 false다 |
| domain | ASCII domain 6개가 서로 다르고, M2 floor domain과도 다르다 |
| plan subject | 세 field(`planSubjectSHA256`, `independentPlanReview`, `rootPublicationIntent`)를 빼고 다시 계산하면 fixture 값과 같다 |
| binding | 803의 이름 target 30개, root 18개, member 60개가 모두 projection group에 들어 있다. HOLD 파일에서 모든 값은 null이고, `executionAuthorized`는 false다 |
| ABI 참고 파일 | 7/7: blob, SHA256, 길이가 `4a` object와 같다 |
| epoch | Go `Config.Epoch`는 string flag이고, `lan_pilot`은 `str(uuid4())`로 만든다. 제안의 string `recoveryEpoch`가 ABI와 맞는다 |

**내 mutation 결과:**

- 거부된 것: bool 뒤집기 17/17, int를 bool로 60/60, int를 1.5로 60/60, int를 문자열로 60/60, hex 대문자 430/430, 모든 object에 key 추가 158/158
- **schema 층이 받아들인 것:** int를 1.0으로 바꾼 경우 **60/60**(L1)

## 설계 판단 (맞는 부분)

- **hash 순환 없음:**
  - lease는 이전 inventory head를 묶는다.
  - inventory는 lease와 BOOTSTRAP_VERIFIED event를 묶는다.
  - seal은 event와 inventory를 묶는다.
  - terminal event는 seal을 묶는다.
  - normal3 lease는 seal 두 개를 묶는다.
- **유지되는 기존 의미:**
  - Cmd `--image` permit과 전역 CP `agentImage`는 고정된다. 현재 runtime의 진실은 typed inventory로 옮긴다.
  - C, cert, enabled, endpoint는 바뀌지 않는다.
- **authority:**
  - backup은 정적 binding이다.
  - 현재 P/H/C는 새로 서명된 M2와 승인된 normal plan으로만 확인하고, migration 기준값과 비교하지 않는다.
  - normal3에는 **새** common lease가 필요하다.
- **lease:**
  - OS lock과 logical fence를 작업 전체에 걸쳐 쥔다.
  - fence epoch는 quiescence를 증명한 뒤 CAS로만 올린다.
  - 나이, PID, 만료만으로 회수하지 않는다. ownership을 모르면 BLOCKED_UNKNOWN이다.
- **앞으로만 간다:**
  - 행동 전에 intent를 남긴다. 결과를 모르면 BLOCKED이다.
  - 옛 container 재시작, downgrade, 두 번째 migration, predecessor 교체, reset은 없다.
- **실행 경로:**
  - 표지가 있으면 generic mutator를 막는다.
  - scheduler entrypoint와 새 등록도 막는다.
  - raw 특권 script는 관리 밖이라고 정직하게 적었다. 그런 경로가 남으면 G9는 HOLD다.

## 발견

| ID | 심각도 | 내용 | 필요한 수정 |
|---|---|---|---|
| **M1** | Medium | **trust anchor가 자기 증명이 될 수 있다.** 서명 key와 role은 plan 자신의 `canonicalContractSHA256`이 묶는 trust 설정에서 오고, verifier contract도 plan이 고정한 set에서 고른다. 그래서 plan 작성자가 자기 root-plan key나 더 약한 verifier를 등록한 set을 고정할 수 있다 | 다섯 role(root-plan, root-fence, root-seal, cp-inventory, host-helper)의 anchor와, 검토된 verifier set을 검증 대상 plan 밖(검토된 helper build나 등록된 trust)에 고정한다. plan은 그 안에서 고르기만 한다고 명시한다 |
| **M2** | Medium | **proof slot에 type이 없다.** 아래 참고 | 고정된 contract set 안에 slot별 registry(field 경로 → contract, 서명 role, scope 계산법, freshness)를 닫힌 형식으로 둔다. slot 바꿔치기와 다른 종류 재사용을 잡는 red fixture도 둔다 |
| **M3** | Medium | **seal 뒤의 실패를 적을 수 없다.** 아래 참고 | blocked phase에서도 기존 seal을 유지하게 한다(SEALED event가 있으면 필수). lease 규칙은 operation별로 정한다. red/green fixture를 둔다 |
| L1 | Low | 1.0, 1e0, -0이 schema 층에서 모든 integer field를 통과한다(60/60). strict byte fixture는 1.5만 시험한다 | 1.0, 1e0, 1E2, -0 거부 case를 추가한다. schema 평가 전에 Go와 Python reader가 같은 판정을 내야 한다 |
| L2 | Low | timestamp가 `format: date-time`에 기대는데, 2020-12에서 format은 주석일 뿐이다. format checker가 없으면 `2026-02-30T25:61:61Z`가 valid다 | 엄격한 RFC3339 parse를 의무로 하고 red fixture를 둔다 |
| L3 | Low | `OLD_FENCED`라는 phase 하나가 두 상태를 덮는다. restart=no만 적용되고 아직 실행 중인 상태와, 정지해 quiescent인 상태다(`stopOld`는 OLD_FENCED에서 OLD_FENCED로 간다). `captureFenced`가 stop 결과 receipt를 필요로 한다는 것은 설명 글에만 있다 | stop 결과를 선행 조건으로 `state-machine.json`에 명시하거나 phase를 나눈다 |
| L4 | Low | event의 inventory/seal hash가 phase에 묶이지 않는다(BOOTSTRAP_VERIFIED에서도 valid). `effect.kind`도 phase에 묶이지 않는다(S08 설명 글뿐) | phase별 nullable 조건과 method/phase/effect 표를 둔다 |
| L5 | Low | VALID seal과 inventory fixture에서 backup과 current의 daemon이 다르다. seal은 두 container에 같은 이름을 쓴다. S05에 어긋난다. harness는 S05 중 restart만 본다고 정직하게 적었다 | 양성 fixture를 semantic으로도 맞추거나, 구조 전용이라고 표시한다 |
| I1 | Info | OS lock과 logical fence CAS의 획득·해제 순서, 중첩 재진입 규칙이 PC2→PC4와 "호출마다 일치" 외에는 없다 | |
| I2 | Info | envelope hash가 서명 bytes를 포함한다. RFC 8032 엄격 검증을 명시하면 좋다. 변형된 중복은 no-overwrite로 막힌다(fail-closed) | |
| I3 | Info | `failureExits`는 같은 phase의 실패 event를 허용하는데, 명세는 같은 phase event를 intent와 readback으로만 제한한다. 문구를 맞춘다 | |

**M2 상세:**

- proof ref 56개가 모두 같은 모양이다. slot마다 contract, 서명 role, scope 계산법을 정한 규범 표가 없다.
- `independentPlanReview`와 `rootPublicationIntent`를 서로 바꿔도 schema는 valid이고 subject도 그대로다.
- fixture의 승인 scope는 subject digest가 아니다. 그 typed scope를 어떻게 계산하는지도 정하지 않았다.
- reserve의 `rootExecutionDecision`이 최종 envelope를 scope로 삼는다는 것도 설명 글에만 있다.

**M3 상세:** journal은 BLOCKED_FORWARD_ONLY와 QUIESCENCE_UNKNOWN에서 seal을 null로, lease를 필수로 강제한다. 그래서 SEALED 뒤 restart policy 복원이 실패하거나 결과를 모를 때, seal 참조를 버려야만 그 상태를 적을 수 있다.

| journal 상태 | schema 결과 |
|---|---|
| blocked phase + seal 유지 | invalid |
| blocked phase + seal 유지 + lease | invalid |
| blocked phase + seal 제거 + lease | valid |

## 판정

| 구분 | 판정 |
|---|---|
| **설계 contract 제안 `f932283d`** | **REVISION REQUIRED.** M1~M3 Medium, L1~L5 Low, I1~I3 Info다. 구조, hash, fixture, ABI 참고, epoch, binding 범위는 확인했다. 앞으로만 가는 구조, ownership, inventory/seal 구조는 타당하다 |
| 등록된 product contract | 없다. 수락하지 않는다 |
| implementation | 없다. 수락하지 않는다 |
| runtime CI | 없다. 실제 Go, 서명, OS lock, Engine, filesystem case는 0개다 |
| physical·운영 | HOLD. target 30개, root 18개, member binding이 모두 null이다 |
| P0 맥락 | 그대로다. 4a NOT ACCEPTED(8baaa6b5). 500 vector는 Python·source 수준 ACCEPT. 46b isolation은 test source ACCEPT(315411bc) |

## 다음 첫 행동과 담당

- **Codex(plan owner):** M1~M3(가능하면 L1~L5도)를 fixture와 함께 고친다. 기다리고 있는 질문 `msg_7d7fb1adc3de`에는 이 판정으로 답한다.
- **root:** REVISION REQUIRED를 기록한다. binding은 null로, 운영은 HOLD로 둔다. 고친 delta의 검토를 맡긴다.
- **Claude:** 맡으면 고친 제안 delta를 검토한다.
