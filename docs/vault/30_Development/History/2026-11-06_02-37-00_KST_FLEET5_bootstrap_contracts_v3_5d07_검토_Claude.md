---
doc_id: "HISTORY-FLEET5-20261106-BOOTSTRAP-CONTRACTS-V3-5D07-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 bootstrap normative contract v3 Low delta 5d0753e5 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T02:37:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "60bfc722"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "bootstrap", "contract-proposal", "claude"]
---

# Bootstrap normative contract v3 Low delta 5d07 검토

Orca task `task_eaa694171f31`, dispatch `ctx_8434b4be8010`. [[2026-11-06_01-42-00_KST_FLEET5_bootstrap_contracts_v2_cb3b_검토_Claude]]가 남긴 조건 N-L4·N-L5(Low)와 N-I1~N-I3(Info)에 대한 Codex v3 delta를 판정한다.

- 설계·계약 제안 판정만 한다. 계약 등록, code 승인, runtime, physical 수락이 아니다.
- **관측 시각:** 02:24:44~02:36:46 KST. 검토 첫 명령과, 작성 전 마지막 remote head 확인의 shell `date` 출력이다.
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/bootstrap-normative-contracts-v3-5d07-review.json`
- **원시 출력:** `Evidence/fleet5-20261105-claude/bootstrap-normative-contracts-v3-5d07-review-raw.json` (synthetic 값만 있다)
- **읽은 진행판:** Index 1.0.413(02:10:53), Claude 작업판 1.2.130. Codex 작업판 1.0.374는 Root가 전한 버전이다. 진행판·registry는 고치지 않았다.

## 대상과 범위

- **대상:** `5d0753e561149f1c4dface08583c232f10be15fc`. 부모는 `cb3b8aee`다. 02:36:46에 Codex branch head가 여전히 이 SHA임을 확인했다.
  - 파일 37개 추가, 수정·삭제 0. v3 Evidence 디렉터리 36개와 owner History 1개다. non-docs 0이다. v1·v2 디렉터리는 건드리지 않았다.
- **Docs 42073588927:** head `5d0753e5`, workflow_dispatch, docs job 1/1 success. GitHub API로 읽기만 했다.
- **읽은 방식:** 5d07의 v3 파일과 cb3의 v2 디렉터리를 Git object에서 `git archive`로 private scratch에 꺼냈다. 작성자 checkout과 다른 Claude의 workspace는 건드리지 않았다.
- **맥락:** v2 ACCEPT(b47371c3), f932 REVISION REQUIRED(78ae0138), 803 plan ACCEPT는 그대로다. P0 source 4f의 CODE ACCEPT·full CI·native 증거는 범위가 다르다. bootstrap 수락으로 빌려 쓰지 않는다.

## 내 독립 확인

도구는 main `.venv` Python 3.14.7(`-B -I`), jsonschema 4.26.0(Draft 2020-12), retrieve 없는 referencing Registry, 내 Go Marshal emulator다. 검토 프로그램은 scratch에만 두고 hash만 기록했다(helper code 미승인). 내 프로그램의 첫 실행에 harness 오류가 두 개 있었다. owner의 `topTarget` field를 무시했고 `api:<method>` 문서 이름을 잘못 읽었다. 그래서 transition 14건과 recipe 113건이 가짜로 통과·미처리였다. 고친 뒤 다시 돌렸다. owner 결함이 아니다.

| 확인 | 결과 |
|---|---|
| owner hash | 35/35와 History hash가 일치한다. 아래 판정에는 owner 결과 JSON을 쓰지 않았다 |
| dependency closure | v2 문서 9개의 bytes·sha256이 선언과 같다. overlay 7개는 `$id`로, v2는 `.invalid/v2` URI로 등록했다. 등록 안 된 `$ref`는 오류로 닫힌다. network를 쓰지 않는다 |
| schema | overlay 7개와 v2 9개가 metaschema를 통과한다. artifact 10개, failure 양성 1개, API 14개가 VALID다 |
| envelope 재계산 | plan `70574bc3`, inventory `0e187212`, migration lease `2fbecf53`, restore lease `5f987490`, seal PC2 `b7fc0081`, seal PC4 `f83d35b1`, predecessor `715ac10f`, current `ba865d26`. plan subject도 재계산했다 |
| N-L4 prior | owner 양성 28/28 VALID, 음성 577/577 거부. 내 sweep은 28 × 24 phase = 672건이다. 표에서 허용된 prior 123건은 모두 받고, 표 밖 prior는 0건 받는다 |
| N-L4 target | member effect의 top/effect target 불일치 92/92 거부. 둘 다 null인 member effect도 거부. **잔여:** cohort effect `publishInventory`는 top이 null일 때 effect.targetSlot PC2/PC4를 4/4 받는다 |
| N-L5 derivation | recipe DSL을 내 해석기로 돌렸다. context 선택은 산문을 보고 내가 따로 구현했다. 대상은 containing product/CI/head, member·memberState·seal·arguments.slot·event target, plan input·inventory current·Node별 dummy fact다. 최종 plan envelope와 cohort scope vector는 재계산했다. embedded 91개(failure fixture 제외 87개 = owner 수), 77/77 slot, mismatch 0, BLOCK 0 |
| N-L5 음성 | 내 단일 field 변형 + hash 재계산 529/529 거부. owner 음성 501/501을 내 해석기가 거부한다. PC2/PC4 signedM2 swap도 거부한다 |
| signer 권한 | node-floor signer = 그 member의 SPKI 5/5. code-review signer = 소속 reviewer SPKI 7/7 |
| 이전 N-L5 사례 | exec·inspection containerId/daemon = member current이고 Node마다 다르다. exec ID는 container ID와 다르고 Node마다 다르다. argv hash, nonce·node·tenant·epoch가 일치한다. receipt·evidence는 최종 plan `70574bc3`을 묶는다. v3 양성 어디에도 v2 envelope hash가 없다. captureFenced 인자 oldContainerId = plan old ID이고 daemon도 같다. post-seal은 21→22, previousProjection = env(predecessor), seal origin 20을 유지한다 |
| join 통과 | plan envelope는 10개 artifact, failure fixture, API 14개 모두 같다. seal 둘은 inventory와 자기 verified event·current·backup·volume을 묶는다. restore lease는 seal 둘, 새 operation, epoch 2, prior fence를 가진다. post-seal은 restore lease와 seal PC2를 가리킨다. policy cohort·scope가 맞다 |
| N-I1 | journal 552 조합에서 위반 0. restore는 sealed history와 허용 phase가 필요하고 SEALED·INTENT에서 HELD다. MIGRATION은 HELD/UNKNOWN만 된다. release 표현은 ownerLease null일 때만 가능하다 |
| N-I2 | failure outcome은 unknown·known-failure·not-attempted만 받는다. known-success는 hash를 다시 계산해도 거부된다. blocked/unknown 밖의 failure phase 4/4 거부. outcome record의 unknown receipt와 null receipt도 거부된다 |
| N-I3 | ID·point·cohortId 변형 156건이 모두 거부된다. cohortId는 256자와 non-ASCII를 받는다(bounded opaque). owner Info 음성 20/20 거부 |
| 층 구분 | schema 층: N-L4, N-I1~I3. semantic recipe/fixture 층: N-L5 derivation, join, signer key. 실행 안 함: 실제 서명, Go reader/verifier, OS lock, Engine, 원자성·CAS, 서명된 전체 event history replay, 장비 |
| HOLD | target 30, Root 18, member, 배포 trust binding은 모두 null/HOLD다. policy와 fact는 fixtureOnly이고 actualTrust는 false다. 이 검토는 key·hash 출처를 지어내지 않았다 |

## 발견

- **N-L4·N-L5(Low), N-I1~N-I3(Info): 닫혔다.** 증거는 위 표와 같다. N-L5는 proof subject 수준에서 닫혔다.
- **V3-L1 (Low):** cohort effect target이 schema에 묶이지 않는다.
  - `publishInventory` intent/outcome은 targetSlot이 null이어도 effect.targetSlot PC2/PC4를 받는다(4/4).
  - 계약의 "Cohort effects remain target=null"과 어긋난다.
  - inventory-cas일 때 두 target을 const null로 묶고 red fixture를 추가해야 한다.
- **V3-L2 (Low):** proof가 아닌 artifact join에 v2 template 값이 남아 있다.
  - inventory `leaseEnvelopeSHA256` `1a76e856…`은 v2 값 그대로다. 발행된 어떤 lease와도 맞지 않는다(migration lease는 `2fbecf53…`).
  - pre-seal journal, post-seal predecessor, post-seal current의 volume(`6a8f83ff…` 등)과 workerRoot(`47d2bf04…`)는 v2 template 값이다. 이 projection들은 seal PC2를 가리키지만, PC2의 plan·lease·seal 값(`d8442d4f…`, `132971ad…`)이 아니다.
  - pre-seal journal daemon `f5333b90…`도 PC2 daemon이 아니다.
  - 계약의 "exact plan/inventory/seal/lease/projection joins verify"와 어긋난다.
- **V3-L3 (Low):** API와 lease의 상태가 맞지 않는다.
  - 발행 뒤의 seal·restore 요청과 restore lease가 inventory head를 ABSENT/null로 선언한다. v1 규칙상 ABSENT는 인증된 not-found readback일 때만 쓴다.
  - restore 요청은 restore operation인데 expectedFenceEpoch가 1이다. 그 lease의 epoch는 2다.
  - 같은 요청의 expectedPriorProjectionSHA256은 null이다.
  - 고치거나, 이 API case들이 상태와 무관한 shape case라고 명시해야 한다.
- **V3-I1 (Info):** owner의 frozen-boards gate pathspec이 mojibake(`Agent? ??`)로 기록돼 아무것도 매치하지 않았다. delta가 37개 추가뿐이라 영향은 없다.

## 판정

| 구분 | 판정 |
|---|---|
| **v3 Low delta `5d0753e5`** | **제안 수준 ACCEPT.** N-L4·N-L5와 N-I1~N-I3을 실제로 닫았다. 새 V3-L1~V3-L3(Low)은 계약 등록이나 구현 전에 고칠 fixture/schema 정합 조건이다. Root의 구현 담당 결정은 막지 않는다. High·Medium은 없다 |
| 이전 판정 | v2 ACCEPT(b47371c3), f932 REVISION REQUIRED(78ae0138), 803 plan ACCEPT를 그대로 둔다 |
| 등록 계약·구현·code 승인 | 없다. 이 검토는 등록을 주장하지 않는다 |
| runtime·CI | 없다. 실제 Go, 서명, OS lock, Engine, 원자성, 장비 case는 0이다. 미래 product case 40개는 NOT RUN이다 |
| physical | HOLD. 모든 binding이 null이다 |

## 다음 첫 행동과 담당

- **Root:** 조건부 ACCEPT를 기록한다. 그 다음에 canonical 등록과 구현 담당을 정한다. binding은 null, 운영은 HOLD로 둔다. `msg_18c3e56963c1`은 이 판정으로 답한다.
- **Codex(plan owner):** 등록 전에 V3-L1~V3-L3을 작은 v4 fixture/schema delta로 고친다.
- **Claude:** Root가 맡기면 그 delta를 검토한다.
