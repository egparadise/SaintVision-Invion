---
doc_id: "HISTORY-FLEET5-20261106-BOOTSTRAP-CONTRACTS-V2-CB3B-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 bootstrap normative contract proposal v2 cb3b8aee 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T01:42:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "2736aec1"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "bootstrap", "contract-proposal", "claude"]
---

# Bootstrap normative contract proposal v2 cb3b 검토

Orca task `task_c96ddeeb29b9`, dispatch `ctx_289f895a6a61`. [[2026-11-06_00-44-29_KST_FLEET5_bootstrap_normative_contracts_f932_검토_Claude]]의 REVISION REQUIRED에 대한 v2 개정 delta `cb3b8aee`를 판정한다.

- 설계·계약 제안 판정만 한다. 등록된 계약, code 승인, runtime, physical 수락이 아니다.
- **관측 시각:** 01:30:26~01:42:00 KST. 첫 fetch와, 작성 전 마지막 head 확인의 shell `date` 출력이다.
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/bootstrap-normative-contracts-v2-cb3b-review.json`

## 대상과 범위

- **대상:** `cb3b8aee288ab41bd23b070d7bd0eb3bf34ad4c7`. 부모는 `f932283d`다.
  - 파일 44개 추가, +46611/−0. 수정·삭제는 0이다.
  - v2 Evidence 디렉터리 43개, owner History 1개. non-docs는 없다.
- **보존:** v1/f932 판정(78ae0138 REVISION REQUIRED)과 803 plan ACCEPT는 그대로다.
- **Docs 42064006585:** head `cb3b8aee`, docs job success. API로만 봤다.
- **읽은 방식:** cb3b와 f932를 Git object에서 `git archive`로 private scratch에 꺼냈다. 작성자 checkout은 건드리지 않았다.

## 내 독립 확인 (main `.venv` 3.14.7 `-B -I`)

도구는 jsonschema Draft 2020-12와 내 Go Marshal emulator다. Go, 서명, crypto 검증은 쓰지 않았다.

| 확인 | 결과 |
|---|---|
| artifact hash | 42/42 일치(`proposal-validation.json` 자체는 자기참조라 제외). owner gate 11개 exit 0 |
| schema / 구조 양성 | 9/9 metaschema-valid. 6개 + post-seal 1개 VALID |
| 필수 key 제거 | owner 1866/1866 거부. 내가 fixture 7개의 모든 key를 직접 빼봤다: 1920/1920 거부 |
| 원래 adversarial 46 | 41개는 schema에서, 5개는 semantic 층에서 거부된다 |
| 내 leaf 변형 | bool·정수 변형, 객체마다 key 추가: 모두 거부. `1.0`과 불가능한 시각은 schema 층에서 통과한다(L1·L2 설계대로 reader가 먼저 거른다) |
| proof slot | generic `proof`는 `false`다. schema const 77 = registry 77 = fixture 77. contract·domain·kind 28개가 각각 1:1이다. policy가 28개를 모두 덮는다 |
| scope hash | 77/77과 embedded 80/80이 `SHA256(C2(typedSubject))`로 재계산된다. kind tag가 hash에 들어간다 |
| v1 참조 | 원래 proof ref 80개(정규화 74 slot)를 모두 v2가 덮는다. v2는 event slot 3개를 더했다 |
| swap·재사용 | 같은 artifact 안 759/759, 다른 artifact의 같은 contract 143/143을 schema가 거부한다. 승인 swap도 거부한다. 같은 slot인 member 간 signedM2 swap만 schema를 통과하고, subject의 node binding이 잡는다 |
| owner slot 음성 539 | 539/539 거부. schema 층 233, 내 semantic predicate 306(scope 재계산, 기대 subject, strict time, 현재 구간, 120초). 놓친 것 0 |
| plan subject / 실행 결정 | subject를 재계산했고 정확히 세 field만 빠진다. reserve 결정은 계산한 최종 envelope `fc2291…`, operationId, migrationId를 묶는다. plan 안에 실행 결정 field가 없어 자기 hash cycle이 없다 |
| M1 | plan의 `canonicalContractSHA256`, 외부 allowed registry, G2 registry가 같다. 외부 policy를 먼저 검증한다. 배포 binding 11개는 null이다 |
| M3 | journal schema가 내 규칙과 1152/1152 조합에서 일치한다. drop-seal은 schema가 거부한다. clear·replace는 history predicate에서만 거부된다(층을 정직하게 밝힌다) |
| event 표 | 표의 intent/outcome 27행은 모두 valid다. method→effect.kind, recordKind→phase, 이른 inventory·seal ref, intent 없는 outcome은 schema가 묶는다 |
| strict byte / time | J01~J09는 9/9, time 6/6이 내 lexical reader와 parse+roundtrip에서 같은 결과를 낸다 |
| canonical body | 6/6이 body, domain, envelope SHA256까지 재현된다. artifact domain 6개는 서로 다르고 M2 domain과도 다르다 |
| edge case 18 | 18/18이 적힌 결과대로 나온다 |
| ABI·HOLD | 4a 파일 7개의 blob·SHA256·길이가 일치한다(NONBINDING). target 30, Root 18, member, trust binding은 모두 null이고 HOLD다 |

## 발견

- **N-L4 (Low):** 계약 본문은 method, recordKind, priorPhase, phase, targetSlot, effect.kind가 schema/table로 묶인다고 한다. member effect의 target이 top-level target과 같아야 한다고도 한다. 그런데 event schema는 둘 다 묶지 않는다.
  - 표에 없는 priorPhase를 441/441 받는다.
  - `effect.targetSlot`과 `targetSlot`이 달라도 14/14 받는다.
  - schema에 넣거나, verifier 전용이라고 명시하고 red fixture를 추가해야 한다.
- **N-L5 (Low):** seal과 inventory의 backup·current 쌍은 고쳐졌다. 그러나 양성 fixture 안의 proof subject는 자기 recipe를 어긴다. 바로 M2 join에 쓰이는 값이다.
  - inventory의 execReceipt와 runtimeInspection Before/After의 containerId가 member의 current ID가 아니다. PC2와 PC4에 같은 값이 쓰였고, exec daemon도 member daemon과 다르다.
  - event의 receipt·evidence subject가 plan envelope `fc2291…`이 아니라 `b84b1b…`를 묶는다.
  - API captureFenced 요청에서 quiescence subject의 oldContainerId·daemon이 요청 인자와 다르다.
  - post-seal fixture의 latestEvent 순번(1)이 sealOrigin 순번(20)보다 앞서고, previousProjection이 null이다.
  - owner의 static 양성은 자기 template과만 비교하므로, recipe에서 subject를 끌어내는 단계를 아무 fixture도 실제로 돌려보지 않는다.
- **N-I1 (Info):** journal schema는 다음을 받는다. 이것들은 verifier·history 규칙으로 적혀 있다.
  - 봉인 이력이 없는 RESTART_RESTORE
  - 이른 phase의 restore
  - lease NONE인 MIGRATION
- **N-I2 (Info):** failure record가 intent digest와 receipt를 가질 수 있다. 그것이 outcome이 아니라는 의미를 명시해야 한다.
- **N-I3 (Info):** typedSubject의 containerId, execId, point, cohortId는 느슨한 문자열이다. 대문자 hex 15개가 schema를 통과한다. semantic 비교가 잡아야 한다.

## 판정

| 구분 | 판정 |
|---|---|
| **설계·계약 제안 v2 `cb3b8aee`** | **제안 수준 ACCEPT.** M1~M3 닫힘. L1~L3, I1~I3 닫힘(명세와 fixture로). L4와 L5는 부분적으로만 닫혔다(N-L4, N-L5). N-L4·N-L5(Low)와 N-I1~N-I3(Info)은 계약 등록이나 구현 전에 고칠 조건이다. Root의 구현 담당 결정을 막지는 않는다 |
| f932 판정 | REVISION REQUIRED(78ae0138). 이력으로 그대로 둔다 |
| 등록 계약·구현·code 승인 | 없다 |
| runtime·CI | 없다. 실제 Go, 서명, OS lock, Engine, 원자성, 장비 case는 0이다. 미래 product case 40개는 NOT RUN이다 |
| physical | HOLD. 모든 binding이 null이다 |
| P0 맥락 | 4a ABI 참조는 NONBINDING이다. 4f source ACCEPT(2736aec1)는 다른 범위이고, 여기서 빌려 쓰지 않는다 |

## 다음 첫 행동과 담당

- **root:** 조건부 설계 ACCEPT를 기록한다. 구현 담당을 정한다. binding은 null, 운영은 HOLD로 둔다. owner 질문 `msg_cfc760f08979`는 이 판정으로 답한다.
- **Codex(plan owner):** 계약 등록 전에 N-L4와 N-L5(그리고 Info 항목)를 작은 fixture/schema delta로 고친다.
- **Claude:** root가 맡기면 그 delta를 검토한다.
