---
doc_id: "CLAUDE-REVIEW-CODEX-CARD17-ADR100-B890D3AD-001"
title: "Codex 카드 17 착지 b890d3ad(ADR-100 CP 호스트 Node 겸임 + 5노드 lane v1.3, docs-only) 독립 검토 — 판정: 승인 — 분류(등록 5 / 물리 host 5 / CP 독립 4 / 겸임 1)가 S05 timed wave·S07 기본 분모의 사전 제외 규칙과 정합, all-five smoke·상관 장애 drill 분리, registry '5대' 유지 근거 타당(AC-05/AC-07 문구 충돌 0), 미등록·미부하 정직 표기 — 관찰 3(비차단)"
version: "1.0.0"
status: "review"
author: "Claude (reviewer)"
reviewer: "Codex (owner)"
updated: "2026-09-23T03:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "ccca9b8f"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["independent-review", "codex", "ADR-100", "five-node", "control-plane", "co-location", "S05", "S07", "docs-only", "claude"]
---

# Codex 카드 17 `b890d3ad` 독립 검토 (2026-09-23, 03:45 KST)

## 0. 판정 요약

| 항목 | 결과 |
|---|---|
| 대상 | `b890d3ad` "docs(governance): define CP node co-location boundary" — 부모 `a28915bc`, integration tip `ccca9b8f`의 조상. 변경 6파일 214+/29-: 신규 [[ADR-100 CP 호스트의 Node 겸임과 5노드 측정 경계]] v1.0.0(accepted), 신규 [[2026-09-23_03-10-00_KST_CP호스트_Node겸임_ADR100_Codex]], [[Codex 5노드 랩 opt-in lane 정의]] v1.2.0→v1.3.0, [[설계 충돌 정정 및 ADR]] v1.37.0, 진행판·Codex 작업판. `docs/task-registry.json`·ontology·제품 코드·workflow 변경 **0**(stat로 확인) |
| 판정 | **승인**(docs-only). 코디네이터가 물은 4항 모두 정합·정직. 관찰 3건은 비차단이며 lane 구현 카드(카드 15)에서 반영 권고 |
| 검증 | tip `ccca9b8f` 신규 worktree에서 `PYTHONUTF8=1 python tools/check_docs.py` **exit 0**(24 original hashes, 855 versioned documents, 48 tasks, 12 outcomes). 문서 전용이라 제품 시험·빌드·부하는 실행하지 않았고, 물리 Node·랩 호스트는 관측하지 않았다 |

## 1. 분류(5 / 5 / 4 / 1)와 사전 제외 규칙의 정합

| 수량 | ADR-100 | lane v1.3 | History | 정합 |
|---|---|---|---|---|
| `registeredNodeCount=5` | 표 1행 + §inventory | 토폴로지 표 합계·manifest 문장 | 결론 | ✔ |
| `physicalExecutionHostCount=5` | 표 2행(Windows 1 + Ubuntu 4, Docker VM 미계수) | 표·manifest 문장 | 결론 | ✔ (관찰 O1: ADR §"상태와 결정" 마지막 문장의 필수 기록 필드는 3개만 나열) |
| `cpIndependentWorkerHostCount=4` | 표 3행 | 표 "CP 독립 host 4" | 결론 | ✔ |
| `cpColocatedNodeCount=1` | 표 4행 | 표 1행 | 결론 | ✔ |

사전 제외 규칙 대조:

- **S05**: ADR §S05 규칙 2 "`measurementEligible.s05=false`·`exclusionReason=cp-host-colocation`을 읽어 **실행 전에** cordon 또는 offer 0 → Explain 선택 0 확인, 사후 샘플 삭제 금지" ↔ lane v1.3 §물리 adapter "timed wave 전에 … cordon하거나 offer 0 … 사후에 해당 샘플만 삭제해서 P95를 다시 계산하면 실패", 단계 1·2 통과 조건에 "겸임 Node 선택 0", `comparison.json`에 `eligibleNodeCount=4`·`excludedNodeCount=1`·"겸임 Node 선택 0". 세 문서가 같은 시점(candidate 구성 전)·같은 증거(Explain 선택 0)로 일치한다. adapter 옵션 1에도 "`measurementEligible.s05`를 candidate 구성 전에 적용"이 추가됐다.
- **S07**: ADR §S07 규칙 1·2 "기본 반복은 Ubuntu 4대, 20회면 Node별 5회, disruption target은 `measurementEligible.s07=true`만" ↔ lane 신규 §S07 "20회 반복은 Ubuntu Node마다 5회씩", `independent-worker-loss`만 기본 95% 분모, artifact에 `targetNodeId`·`hostId`·`failureDomainId`·`coLocatedWithControlPlane`·`measurementEligible`·`scenarioClass`·observer identity/clock. 일치.
- **판정 기준 3조건**([[2026-09-19_Claude영역_검증상태지도]] v1.5.0 §14.1)과 lane 단계 3(① hold P95 감소 AND ② 내부+외부 `55P03/57014` 합계 감소, "성공 수만으로 통과 금지")은 v1.3에서도 그대로다. 겸임 제외는 분모 정의만 바꾸고 조건은 바꾸지 않는다.

## 2. all-five smoke·상관 장애 drill의 분리 표기

- lane 단계표에 **0a all-five smoke** 행이 새로 들어갔고(5 Node 등록·heartbeat·resource snapshot·Explain 도달, "기능 smoke 실패 → timed wave 금지"), ADR §S05 규칙 1이 이를 "기능 smoke이며 P95 수용 표본이 아니다"로 못 박는다. artifact `five-node-s05-placement-<code_sha>` 필수 내용도 "all-five smoke + eligible Ubuntu 4대 …"로 분리됐다.
- S07은 `independent-worker-loss` / `colocated-node-process-loss` / `correlated-cp-node-host-loss` 세 `scenarioClass`로 분리되고, 뒤 둘은 "기본 95% 분모와 합치지 않음"이 ADR·lane 양쪽에 있다. 상관 장애 drill은 외부 monotonic observer 또는 별도 CP 없이는 `UNMEASURED`다.
- ADR §S05 규칙 5의 `biased-all-five` 비교 wave 이름 규칙은 lane에 아직 없다(관찰 O1과 함께 lane 구현 카드에서 artifact 이름 규칙으로 반영하면 됨. 현재는 ADR이 상위 규칙이므로 충돌 아님).

## 3. registry '5대' 유지 근거 — AC 문구 충돌 여부

tip의 `docs/task-registry.json`을 직접 읽었다.

| 항목 | registry 문구(tip) | ADR-100 해석 | 충돌 |
|---|---|---|---|
| OUT-05 | 제목 "5노드 자원을 초과 예약 없이 설명 가능하게 배치한다" / AC-05 criterion "동일 입력 배치 동일, 50개 동시 예약 초과 0, P95 2초 목표 실측" | 등록 Node 5개(별도 `nodeId`·인증서·epoch)가 배치 대상이고 topology preflight/smoke로 5노드 등록·Explain 도달을 증명; P95·결정성 분모는 CP 독립 4대 | **없음** — AC-05 criterion에 "독립 host 5"나 "5대 모두 부하"라는 문구가 없다. 제목의 "5노드 자원"은 등록 identity 5개로 충족 |
| OUT-07 | 제목 "Node 손실과 분할 상황에서 낡은 실행을 차단한다" / AC-07 "이탈 감지 60초 이내, 오래된 토큰 쓰기 0, 복구 성공률 목표 95%" | 감지·복구율 분모는 Ubuntu 4대×5회; stale write 0·fencing 단조성은 두 분류 모두 검사 | **없음** — Node 수를 규정하지 않음 |
| 5대 PC outcome | 제목 "5대 PC에서 개발부터 배포·장애 복구까지 완료한다"(criterion "5노드 전체 여정·정량 목표·알려진 제한·인수 확인 모두 기록") | 토폴로지 B는 물리 PC 정확히 5대(Windows 1 + Ubuntu 4) | **없음** — 오히려 "알려진 제한 기록"이 ADR의 4개 count 동반 기록과 맞음 |

따라서 "registry 5대 = 등록 실행 Node identity 5개"로 유지하면서 acceptance 분모를 4로 표기하는 것은 AC 문구를 낮추지도, 과장하지도 않는다. ADR §"선택 이유"의 "registry 기준을 낮추지 않고 증거 manifest에 상관 관계를 추가"가 실제 문서 변경(registry diff 0, manifest 필드 추가)과 일치한다. 단, 이 판단은 registry의 **문구**에 대한 것이고, 5노드 인수 자체는 lane 실행 뒤 별도 판정이다.

## 4. 미등록·미부하 정직 표기

- ADR §"현재 확인 범위"·History §"파일럿 provenance와 비주장": 5 Node 등록·online, inventory-bound runner, 20/50 부하, S07 20회, P95·60초·95% 판정 **모두 미실행**이라고 명시. 첫 Ubuntu 후보(IP·state 경로·예약 nodeId)는 "코디네이터 보고를 문서화한 것이고 Codex가 원격 호스트를 독립 관측한 결과가 아니다"로 provenance를 구분했고, private key·cert·DSN·token 원문 없음(diff에서 확인).
- lane v1.3 명령 5개 중 S05 wrapper·S07 inventory-bound wrapper(`run_s07_five_node_recovery.py`, **신규 제안**)·S06 runner는 "제안·미구현"으로 표기됐고, 기존 `measure_s07_recovery.py`는 합성 row 측정이라 물리 증거가 아니라는 문장이 유지됐다. 진행판 한 줄과 Codex 작업판도 "미실행·미측정·S05/S07 review 유지"로 동일하다.
- 나 역시 물리 호스트·Docker Desktop Node를 관측하지 않았으므로 토폴로지 B의 실재는 이 검토에서 확인하지 않는다.

## 5. 관찰(비차단, lane 구현 카드 반영 권고)

| ID | 내용 | 권고 |
|---|---|---|
| O1 | ADR §"상태와 결정" 마지막 문장의 필수 기록 필드가 `registeredNodeCount`·`cpIndependentWorkerHostCount`·`cpColocatedNodeCount` 3개인데 lane v1.3·History는 `physicalExecutionHostCount`까지 4개를 "언제나" 남긴다 | ADR 다음 버전에서 4개로 통일(또는 lane이 ADR을 참조). manifest schema를 만드는 카드 15에서 4 필드 필수로 고정 |
| O2 | `correlated-cp-node-host-loss`의 미측정 처리: ADR 규칙 4는 "`UNMEASURED`이고 exit 3", lane §S07은 "JUnit skip이 아니라 failure/error 또는 도구 exit 3". 미측정을 JUnit failure로 적으면 F-S07 계열 판독에서 실패로 오인될 수 있다(#77/#87·collector 4종에서 확립한 UNMEASURED≠FAIL, exit 3≠1 기준) | JUnit은 사유가 붙은 `error`(또는 skip 금지 유지 + `UNMEASURED` testcase 이름) + exit 3로 ADR 문구에 맞추기 |
| O3 | `coLocatedWithControlPlane=true`가 inventory의 **선언**이지 유도값이 아니다. CP 자신의 `hostId`/`failureDomainId`가 inventory·manifest 필드에 없어 reviewer가 겸임 여부를 대조할 수 없다 | inventory에 `controlPlane.hostId`·`failureDomainId`를 두고 preflight가 `node.hostId == controlPlane.hostId ⇒ coLocated=true, eligible=false`를 유도·검증. 값 불일치면 preflight 실패 |

50동시 wave가 eligible 4대에서 "50/50·초과 0"을 요구하므로 resource offer 합계가 50건 예약을 수용하는 크기여야 하며, 그 offer/policy version은 이미 manifest 필수 항목이다(문서 충돌 아님, 구현 시 유의).

## 6. 다음 인계

- 코디네이터: 카드 17 **승인**. S05-DB·S07-DB `review` 유지, flag off·5노드 승격 없음 그대로.
- Codex(카드 15 lane 구현 시): O1 필드 4개 고정, O2 UNMEASURED/exit 3 정렬, O3 co-location 유도 검증. `run_s07_five_node_recovery.py --eligible-only`는 제안 CLI이므로 구현 시 이름·인자 확정 후 lane 문서 갱신.
- Claude(후속, 별도 카드 필요 없음): [[2026-09-19_Claude영역_검증상태지도]] §14 "AC-05 판정 … 물리 5노드 lane에서만" 행에 ADR-100의 "등록 5·CP 독립 4 분모" 문구를 다음 개정 때 반영.
