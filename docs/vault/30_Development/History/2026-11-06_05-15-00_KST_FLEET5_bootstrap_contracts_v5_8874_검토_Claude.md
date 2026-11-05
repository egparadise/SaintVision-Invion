---
doc_id: "HISTORY-FLEET5-20261106-BOOTSTRAP-V5-8874-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 bootstrap contract v5 8874b2df 보조 delta 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T05:15:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "8874b2dfe0dda9a019bd5f334636668290702e13"
task_ids: ["FLEET5-LEGACY-CAPABILITY-BOOTSTRAP-PLAN-20261105"]
tags: ["fleet5", "independent-review", "bootstrap", "derived-digest", "claude"]
---

# Bootstrap contract v5 8874 보조 delta 검토

Orca `task_48bd227e309c`, dispatch `ctx_6b1494bf1d33`. 실제 v4 검토(commit `d2fab4a2`, `History/2026-11-06_03-54-00_KST_FLEET5_bootstrap_contracts_v4_eed8_검토_Claude.md`, 이 base에는 없다)의 V4-M1(Medium)과 V4-I1~I3에 대해 Root가 `msg_c12b3f544036`로 서명 없는 derived digest를 선택했다. 이 검토는 Codex v5 delta가 그 결정을 지켰는지 판정한다.

- **판정: ACCEPT (보조 delta, 제안·설계 수준).** 남은 보조 차단 사항은 없다. V4-M1, V4-I1, V4-I2, V4-I3를 모두 닫았다.
- **범위:** 설계 수락만 한다. 정식 등록, ADR, helper·runtime code, NodeOps는 Root가 별도로 결정한다.
- **실행하지 않은 것:** 실제 Go, 서명, OS lock, Engine, 원자성, 장비는 0건이다. 미래 product case 40개는 NOT RUN이다. 실제 binding은 모두 NULL/HOLD다.
- **기계 판독 결과:** `Evidence/fleet5-bootstrap-v5-8874-review-20261106-claude/review.json`. 검토 스크립트 4개와 결과 4개도 같은 폴더에 있다.

## 대상과 범위

- **대상:** `8874b2df`, 부모 `eed826e7`. 29개 파일 추가(A)이고 그 밖의 변경은 0이다. owner History 1개와 v5 Evidence 28개다.
- **읽은 것:**
  - 실제 v4 검토 `d2fab4a2`
  - Root 결정 `bootstrap-v4-derived-digest-decision-root.json`(e840937b)
  - owner History와 v5 Evidence 28개 전부
- **맥락으로만 확인한 것:** source Docs run `42096953590`(job `127489386393`) success, 8874b2df, 04:45:40–04:46:18 KST. 검토 증거로 세지 않았다.
- **실행 방식:** v5와 v4 파일은 Git object를 `git archive`로 scratch에 꺼냈다. owner 프로그램은 실행하지 않았다. 검토자 스크립트는 main `.venv` Python 3.14.7 `-I -B`, jsonschema Draft 2020-12, network 없는 offline registry를 썼다.
- **host 조건:** 메모리 98–99%라서 process 하나씩 순서대로 돌렸다. 실행 시각은 UTC 19:57–20:09, 즉 KST 04:57–05:09다.

## 독립 확인 결과

| 확인 | 결과 |
|---|---|
| Git audit | `git diff --no-renames --name-status -z eed8 8874`를 strict UTF-8로 읽었다. 29쌍 모두 A이고 raw sha256 `273774b7…`가 owner와 같다. owner 명령은 working tree와 비교했지만 결과가 같다(I-d) |
| hash | artifact 27/27과 History가 owner 기록과 같다 |
| 재사용한 v4 context | trust contract·slot registry·recipe·HOLD 파일이 v3/v4와 byte 단위로 같다 |
| object | 195개 = signed-shape 115 + transport 44 + derived 36. kind로 고정한 digest가 195/195 맞는다. caller가 붙인 label과 고정 kind는 모두 일치한다 |
| graph | rule 3469개 실패 0. 의존 edge 803개, cycle 0. 재생성 digest 차이 0. 비-proof leaf 6671개가 각각 정확히 한 번 덮인다. 미분류 proof 참조 112개 |
| schema | 문서 17개 hash가 일치한다. 195/195 VALID. 거부된 v4 서명 set은 closure에 없고, v4 set 36개 중 v5 schema가 받는 것은 0개다 |
| byte vector | 양성 4개: body·domain·message hex와 digest가 모두 일치하고 body에 LF가 없다. 음성 7개: 순서 반전·중복·누락과 signer·signature·key·grant field를 schema가 모두 거부한다 |
| context 음성 432 | 내가 의존 값을 모두 다시 묶은 뒤 후보 digest가 owner와 432/432 같다. 432/432 거부되고 매번 대상 rule만 실패한다 |
| signer 음성 342 | 후보 digest가 342/342 같다. outer 230건은 graph의 signer mapping rule이 거부한다. proof key 112건은 내 role@scope policy 검사가 거부한다(I-a) |
| 옛 field 44, Node·cohort swap 43, label 390 | API:2가 옛 field를 받는 경우는 0이다. swap은 schema 21/21, graph 22/22 거부다. label 390건은 고정 kind로 모두 거부된다 |
| I3 | blob `b8c66b46…`: type blob, 61973 bytes, sha256 `51c03704…`. 발행 파일과 byte 단위로 같다. v4 rule이 쓰는 input pointer 102개가 최종 v4 seed `d40a7486…`와 C2 기준으로 모두 같다 |
| stale 검사 | proof typedSubject 안의 hex 값 235개를 분류했다. v4에만 있는 digest는 0개다 |

## Root 요구별 판정

- **V4-M1: 닫힘.**
  - derived record 36개에 signature/signer/key/grant/producerRole 키가 0개다.
  - digest = SHA256(ASCII domain ‖ `00` ‖ C2 record)이고, 일반 SHA256(C2)와 같은 값이 되는 경우가 없다.
  - root-fence가 서명하는 것은 `lease-migration`, `fence-released`, `lease-restore` 셋뿐이다.
  - derived record는 서명 할당에 없고, policy·trust·slot·recipe registry에서 이 type을 언급하는 곳이 0이다. `derivedSetsAreTrustAnchors`는 false다.
  - 공급된 digest만으로는 증거나 M2 fallback이 될 수 없다. 원래 권한의 Node projection과 실제 lease·head를 먼저 검증한 뒤 재계산한다는 dataflow가 계약에 적혀 있다. 이는 설계 문장이며 실행 증명은 아니다.
- **V4-I1: 닫힘.** 이 판정에는 rule을 쓰지 않고 trace로 직접 대조했다.
  - 36/36 record가 plan·migration·cohort·operation·epoch·lease·head·readback·sequence와 완전히 정렬된 [PC2, PC4] journal envelope를 묶는다.
  - epoch 1이 34개다. 그중 33개는 `lease-migration`이고, release 뒤 1개는 `fence-released`다. epoch 2는 `lease-restore` 2개다.
- **API:2: 닫힘.**
  - 요청 22개는 member 17, cohort 5다. prior가 없는 것은 genesis 요청 `request-01` 하나뿐이다.
  - 각 요청의 prior 참조가 trace 직전 상태와 22/22 일치한다.
  - derived digest를 참조하는 것은 요청 4개와 응답 5개뿐이고, journal은 참조하지 않는다.
  - PC2 fallback은 없다.
- **V4-I2: 닫힘 (synthetic 범위).**
  - dummy signature bytes 115개가 모두 다르다.
  - outer signer 115개와 proof 참조 112개가 모두 policy의 role@scope와 일치한다. 이벤트의 scope는 trace의 slot으로 정했다.
  - PC2와 PC4의 host-helper·node-leaf·root-seal key가 서로 다르다.
  - `keysAreReal`은 false이고 실제 crypto는 없다.
- **V4-I3: 닫힘.** 위 I3 행과 같다. 복원한 seed는 historical v4 증거로 표시되어 있고 v5 양성 사례가 아니다.

## Info (차단 아님)

- **I-a:** graph 비교는 typed proof를 벗기고 한다. 그래서 proof key swap 112건은 role@scope policy 층에서만 거부된다. 미래 verifier는 이 층을 반드시 구현해야 한다. graph 동치만으로는 부족하다.
- **I-b:** v2 schema 7개에 `$id`가 없다. v3 상대경로 규칙으로만 해석된다. accepted v4와 같은 상태이며, 정식 등록 때 `$id`를 명시해야 한다.
- **I-c:** rule 목록은 node별로 묶여 있을 뿐 topological 순서가 아니다(처음 앞으로 가는 참조: response-request-01 → cohort-01). 발행된 object 순서에는 forward 참조가 0이고 DAG는 비순환이다. 평가기는 목록 순서가 아니라 의존 순서를 따라야 한다.
- **I-d:** owner path audit은 working tree를 eed826e7과 비교했다. raw 결과가 검토자의 commit 범위 결과와 같아 동치다.
- **I-e:** 112 proof subject의 전체 v3 recipe 유도는 이번에 다시 돌리지 않았다. 대신 위 stale 검사를 했다. recipe·registry 파일은 accepted v3/v4와 byte 단위로 같다.

## 검토자 harness 오류 (보존)

모두 내 harness의 문제이고 owner 결함이 아니다. 고친 뒤 다시 돌렸다.

- **run1 exit 1:** `changedPaths`를 목록으로 읽었다. 실제로는 개수다.
- **run2 exit 1:** 패치가 vector 블록에 NUL 문자를 그대로 넣었다.
- **run3 exit 1:** rule 목록 순서로 평가했다. 의존 순서로 바꿨다.
- **run4 exit 1:** v2 schema에 `$id`가 없었다. 경로에서 id를 만들고 기본 Draft 2020-12를 지정했다.
- **run5 exit 0이지만 오류:** 나쁜 field를 넣기 전에 planSubject를 다시 묶어서, 후보 digest가 33건 가짜로 어긋났다. run6에서 고쳤다.
- **signer scope:** 처음에 이벤트를 COHORT scope로 보았다. trace의 slot을 쓰자 불일치가 0이 되었다.

## 다음 첫 행동

- **Root:** 이 보조 delta의 실제 ACCEPT를 확인한 뒤, 수락된 canonical 계약(domain·type·역할 분리)만 freeze/register하고 구체적인 code 범위를 정한다.
- **Codex:** Root가 범위를 주면 구현한다. I-a(proof role@scope 층)와 I-b(명시 `$id`)를 함께 반영한다.
- **Claude:** 구현 code가 오면 실제로 독립 검토한다.
