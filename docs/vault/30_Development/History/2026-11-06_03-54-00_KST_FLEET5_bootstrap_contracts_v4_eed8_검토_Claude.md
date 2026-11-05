---
doc_id: "HISTORY-FLEET5-20261106-BOOTSTRAP-CONTRACTS-V4-EED8-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 bootstrap normative contract v4 closed graph eed826e7 독립 검토"
version: "1.0.1"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T03:54:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "a81f7330"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "bootstrap", "contract-proposal", "claude"]
---

# Bootstrap normative contract v4 closed graph eed8 검토

Orca task `task_65f5ad416040`, dispatch `ctx_f5268654ce53`. [immutable actual v3 independent review](https://github.com/egparadise/SaintVision-Invion/blob/a81f73309a43ced0f777b10b3c0781c98aa54e96/docs/vault/30_Development/History/2026-11-06_02-37-00_KST_FLEET5_bootstrap_contracts_v3_5d07_%EA%B2%80%ED%86%A0_Claude.md)가 남긴 V3-L1~V3-L3(Low)과 V3-I1(Info)에 대한 Codex v4 delta를 판정한다. 새로 제안된 cohort-projection-set ABI도 따로 검토한다.

- 설계·계약 제안 판정만 한다. 계약 등록, code 승인, runtime, physical 수락이 아니다. v3 설계 ACCEPT를 v4 closure로 빌려 쓰지 않았다.
- **관측 시각:** 03:38:04~03:53:13 KST. 검토 첫 명령과, 작성 전 마지막 확인의 shell `date` 출력이다. 03:53:43에 Codex branch head가 여전히 `eed826e7`임을 확인했다.
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/bootstrap-normative-contracts-v4-eed8-review.json`
- **원시 출력:** `Evidence/fleet5-20261105-claude/bootstrap-normative-contracts-v4-eed8-review-raw.json` (LF, synthetic 값만 있다)
- 진행판·registry·ADR·shared board·Obsidian은 고치지 않았다.

## 대상과 범위

- **대상:** `eed826e7fb066193d3a2d9d28abda15216264f77`. 부모는 `5d0753e5`다.
  - 파일 22개 추가, 수정·삭제·rename 0. v4 Evidence 디렉터리 21개와 owner History 1개다. v1·v2·v3 디렉터리는 바뀌지 않았다.
- **Docs 42084619690:** head `eed826e7`, workflow_dispatch, docs job 1/1 success. GitHub API로 읽기만 했다.
- **읽은 방식:** eed8의 v4 파일과 History를 Git object에서 `git archive`로 private scratch에 꺼냈다. 작성자 checkout과 다른 Claude의 workspace는 건드리지 않았다.
- **host:** Root가 알린 대로 메모리가 거의 없는 host다. 모든 확인을 Python process 하나씩 순서대로 돌렸다. process를 죽이거나 pagefile·보안 설정을 바꾸지 않았다.

## 내 독립 확인

도구는 main `.venv` Python 3.14.7(`-B -I`), jsonschema 4.26.0(Draft 2020-12), retrieve 없는 referencing Registry, 내 Go Marshal emulator다. 9-operator graph 문법 해석기는 내가 따로 구현했다. 검토 프로그램은 scratch에만 두고 hash만 기록했다(helper code 미승인).

내 harness 오류가 세 번 있었다. 고친 뒤 다시 돌렸다. owner 결함이 아니다.

- verifyBootstrap을 outcome event에서 찾았다. 이 scenario는 readback으로 기록한다.
- rule 값을 비교할 때 proof object를 벗기지 않았다. 계약은 proof만 벗기라고 한다. 그래서 rule 61개가 가짜로 실패하고 재생성이 어긋났다.
- 넓은 변형에서 field swap 2건이 "통과"했다. 바꾼 값이 proof metadata만 달랐다. proof를 벗기면 같은 값이다.

| 확인 | 결과 |
|---|---|
| Git audit (V3-I1) | 내가 `git diff --no-ext-diff --no-renames --name-status -z 5d07 eed8`를 돌리고 strict UTF-8로 읽었다. 22쌍 모두 A이고 owner 목록과 같다. raw sha256 `0047e0a1…`도 owner와 같다. 원래 v3 기록(blob `fab17377…`)의 `Agent? ??` pathspec gate는 바이트 그대로 남아 있다 |
| owner hash | artifact 20/20, History hash가 일치한다. 아래 판정에는 owner 결과 JSON을 쓰지 않았다 |
| dependency | 유효 schema 문서 18개(v2 9, v3 7, v4 2)의 bytes·sha256이 선언과 같고 metaschema를 통과한다. 등록 안 된 `$ref`는 오류로 닫힌다. network를 쓰지 않는다 |
| object | node 195개: plan 1, lease·fence 3, 요청 22, 응답 22, event 36, journal 72(Node당 36), cohort set 36, inventory 1, seal 2. 195/195 schema VALID, node sha256 = SHA256(C2(payload)) 195/195 |
| rule | 3173/3173 성립한다. 자기 참조는 plan의 planSubject 하나다(자기 field를 빼고 계산). 앞쪽 node를 가리키는 rule은 없다 |
| coverage | proof가 아닌 leaf 6411개(null·빈 container 포함)가 각각 정확히 rule 하나에 덮인다. 미포함 0, 중복 0. proof 안을 가리키는 rule은 없다. proof object 112개 |
| 재생성 | scenario-inputs에서 graph 순서대로 모든 node를 새로 만들었다. 발행된 payload 195개와 sha256이 바이트 단위로 같다 |
| proof | embedded 112/112가 내 v3 recipe 해석기와 graph context로 유도된다. slot 75개. registry·recipe·trust contract·HOLD binding은 v3와 바이트가 같다 |
| owner 변형 341 | 내 후보 node sha256이 owner 값과 341/341 같다. 341/341 거부되고, 매번 고른 rule 하나만 실패한다. 159건은 schema에서도 거부되고 182건은 graph에서만 거부된다 |
| 내 변형 | 1221건을 만들고 의존 hash를 모두 다시 계산했다. 내 artifact 2건을 빼면 실제 1219건이다. digest swap 377, field swap 339, PC2↔PC4 input swap 398, 정수·add +1 75, member event target swap 30. 1219/1219 거부, 매번 바꾼 rule만 실패한다. 1130건은 변형 후에도 schema VALID라서 graph 층이 거부한다 |
| V3-L1 | 5개 cohort method에서 top·effect target이 schema const null이다. owner Cartesian 324건과 324/324 일치한다(VALID 66, REJECT 258). 내 324건 sweep에서 cohort target이나 member top/effect 불일치를 schema가 받는 경우는 0이다. member slot(PC2/PC4) 정체성은 graph가 묶는다(30/30 거부) |
| V3-L2 | inventory `leaseEnvelopeSHA256` = env(lease-migration). inventory previousHead는 ABSENT다. journal 72개의 scope·daemon·workerRoot·volume이 그 member의 plan 값이다(이탈 0). seal 둘은 inventory와 자기 current·backup·volume, 그 Node의 실제 verifyBootstrap event를 묶는다 |
| V3-L3 | released fence는 leaseId·operation·token·owner가 같고 epoch 1, RELEASED, priorFence = migration lease다. restore lease는 epoch 2, priorFence = released fence, 새 leaseId·operation·token·ownerGeneration, seal 둘, PRESENT head를 가진다. restore 요청은 epoch 2이고 prior projection = released된 sealed PC2 projection(SEALED/RELEASED/NONE)이다 |
| admission 재생 | 요청마다 첫 event에서 받는다. expectedPriorProjection = 그때의 Node projection(member) 또는 cohort set(cohort)이다. expectedFenceEpoch = 활성 lease epoch이다. head는 발행 전 ABSENT, 발행 뒤 PRESENT env(inventory)다. 22/22 통과 |
| lifecycle 재생 | event 36개의 sequence·previousEvent chain이 맞다. intent·outcome은 같은 요청 bytes를 쓴다. 순서: inspect→reserve→restart=no 두 개→PC2 chain(7–16)→PC4 chain(17–26)→publish(27–28)→seal PC2·PC4(29–32)→readState(33)→release(34)→restore PC2 intent(35)→QUIESCENCE_UNKNOWN 실패(36). 36 뒤 event는 없다. 끝 상태는 PC2 QUIESCENCE_UNKNOWN, PC4 SEALED, 둘 다 HELD restore lease다. seal은 한번 생기면 빠지지 않는다 |
| 응답 | 22개 모두 자기 요청·event·projection·inventory를 묶고 sideEffectPermitted는 false다. release 응답의 lease는 env(fence-released)다. release 뒤 기록을 돌려주는 것이라 결함이 아니다 |
| input seed | rule이 쓰는 input pointer 102개가 모두 풀린다. plan seed = v3 plan body에서 proof와 옛 planSubject를 뺀 것이다. policy는 v3와 같다. facts는 v3에 `registeredFenceIdentitySHA256`, `allowedManagedEntrypoints` 두 개가 더해졌다. 안 쓰는 input leaf 113개는 proof context fact·policy, flag, plan canonicalContractSHA256이다 |
| 실행 안 함 | 실제 서명·RFC8032, Go reader/verifier, OS lock, Engine, 원자성·CAS, 서명된 전체 history, 장비: 0. 미래 product case 40개 NOT RUN. target 30, Root 18, member, 배포 binding은 모두 null/HOLD |

## 새 cohort-projection-set ABI

- **schema:** 닫혀 있다. members는 정확히 [PC2, PC4] 순서다. 순서 반전, slot 이름 바꾸기, member 셋, 다른 signer role, 추가 field를 모두 거부한다.
- **binding:** set 36개, digest 36개가 모두 다르다. 각 set은 plan envelope, event sequence, 두 Node의 현재 projection digest와 plan scope를 묶는다. 같은 slot의 지난 projection을 넣으면 schema는 받지만 graph가 거부한다.
- **쓰임:** cohort 요청 4개의 expectedPriorProjection과 cohort 응답 5개의 projectionEnvelopeSHA256이 가리킨다. Node method는 계속 자기 projection을 쓴다.
- **domain:** `saintvision/migration-cohort-projection-set/v1`, suffix `00`. 제안 HOLD 파일의 actual 값은 모두 null이고 implementationAuthorized는 false다.
- **signer:** role `root-fence`. 서명 key는 lease와 같은 fixture key다. trust contract·registry·policy roles는 바뀌지 않았다. 이 domain에 대한 root-fence 권한·verifier·anchor는 아직 없다.

## 발견

- **V3-L1·V3-L2·V3-L3(Low), V3-I1(Info): 닫혔다.** 증거는 위 표와 같다.
- **V4-M1 (Medium, 보조 ABI만):** cohort set을 root-fence가 event마다 서명한다(migration당 36번).
  - mutation fence key에 새 권한이 생긴다. 자기가 만들지 않은 Node 상태를 자주 증명해야 하고, event마다 hot path에 끌려 나온다.
  - set은 Node가 서명한 projection 둘, plan, sequence에서 완전히 유도된다. 서명이 더하는 정보가 없다.
  - 누가 언제 만들고 서명하는지, key 보관은 어떻게 하는지 정하지 않았다.
  - **등록 전 조건:** 서명 없는 domain-separated 유도 digest(domain ‖ 00 ‖ C2 body의 SHA256)로 바꾼다. verifier는 인증된 projection 둘에서 다시 계산한다. 아니면 fence 권한 없는 aggregator role을 따로 등록한다. 어느 쪽이든 producer, verifier, 실패 동작을 적는다.
- **V4-I1 (Info):** set 자체는 migrationId·operationId·lease·epoch·head를 묶지 않는다.
  - swap 방지는 plan, sequence, member projection digest에 기댄다.
  - lease는 member ownerLease로만 묶인다(release 뒤에는 null). head·epoch는 요청이 묶는다.
  - 보조 계약에 이 경계를 적어야 한다.
- **V4-I2 (Info):** fixture signer key가 fixture policy role key와 하나도 맞지 않는다. 두 Node의 projection 72개가 host-helper key 하나와 같은 signatureHex 하나를 쓴다. UNTRUSTED_SIGNATURE_SHAPE로 선언됐다. 그래서 role별·Node별 signer binding은 시험되지 않았다. 미래 verifier 작업이다.
- **V4-I3 (Info):** prune 전 seed `51c03704…`는 발행되지 않았다. owner의 "unchanged" 주장은 직접 확인할 수 없다. 대신 발행된 seed를 v3 fixture와 대조했다.

## 판정

| 구분 | 판정 |
|---|---|
| **v4 Low delta `eed826e7`** | **제안 수준 ACCEPT.** V3-L1~V3-L3과 V3-I1을 실제로 닫았다. closed graph 주장(195/36/22+22/72+36, rule 3173, leaf 6411, proof 112, case 341·324)을 독립으로 재현했다 |
| **cohort-projection-set ABI** | **제안대로 등록하는 것은 ACCEPT하지 않는다(V4-M1 Medium).** 모양과 binding은 맞다. root-fence 서명 권한은 근거 없는 trust 확장이다. Root가 schema·domain·role 등록 전에 정한다 |
| 이전 판정 | v3 조건부 ACCEPT(a0cb83b8), v2 ACCEPT(b47371c3), f932 REVISION REQUIRED(78ae0138)를 그대로 둔다 |
| 등록 계약·구현·code 승인 | 없다. 이 검토는 등록을 주장하지 않는다 |
| runtime·CI | 없다. 실제 Go, 서명, OS lock, Engine, 원자성, 장비 case는 0이다. 미래 product case 40개는 NOT RUN이다 |
| physical | HOLD. 모든 binding이 null이다 |

## 다음 첫 행동과 담당

- **Root:** v4 closure ACCEPT를 기록한다. 보조 schema·domain 등록 전에 V4-M1(cohort set의 signer·role)을 정한다. 그 다음에 등록과 구현 범위를 정한다.
- **Codex(plan owner):** Root가 aggregate를 유지하면 V4-M1·V4-I1에 대한 보조 ABI만의 작은 delta를 만든다.
- **Claude:** Root가 맡기면 그 delta를 검토한다.


Root aggregation citation adaptation only: the earlier v3 History remains at its immutable source because connection-like fixture bytes were withheld from the aggregate. This wrapper replaces one missing wiki target with the verified exact-source link; the actual d2fab4a2 report and its verdict remain unchanged.
