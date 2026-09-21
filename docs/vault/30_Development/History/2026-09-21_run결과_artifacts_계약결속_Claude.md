---
doc_id: "CONTRACT-RUN-RESULT-ARTIFACTS-CLAUDE-001"
title: "run result / artifacts 응답 계약 결속 — 공유 fixture, 양방향 변형. 프런트 배선은 Gemini"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T22:30:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["contract", "run-result", "artifacts", "shared-fixture", "mutation-testing", "handoff-gemini", "adapter"]
---

# run result / artifacts 응답 계약 결속

**묶지 않으면 무엇이 조용히 깨지나(먼저 적는 한 줄)**: 커널이 서빙하는 `/v1/projects/{p}/runs/{id}/result`·`.../artifacts` 응답이 프런트가 공유하는 fixture에 묶여 있지 않았다. `DeveloperStudio`는 result 실패 시 **artifacts 폴백 여부와 폴백 시 UNVERIFIED 표시**를 전적으로 그 응답의 **shape**로 판별하는데, 백엔드가 shape를 바꿔도 프런트 판별이 조용히 어긋나고 프런트 18개 시험은 전부 모의 응답을 써 그 모의가 실물과 같다는 보장이 없다. 이 지점을 공유 fixture로 묶는다.

## 결속 구조 (Codex projects/discovery 패턴을 커널 계약에 적용)
run-result/artifacts는 **커널(inv)** 서빙이라 계약 정본은 `services/control-plane/src/inv/generated/core.schema.json`($defs `RunResultView`·`RunArtifactList`, mirror `contracts/v1alpha1/core.schema.json`)이다. 백엔드는 이미 `inv/result_view.py`의 `_checked("RunResultView", …)`=`validate_contract`로 **자기 출력을 이 스키마에 검증**한다(백엔드 측 결속 기존재). gap은 **프런트가 수기 타입(`apps/web/src/contracts/types.ts:511 RunResultView`, `:554 RunArtifactList`)을 쓰고 이 계약과 공유 fixture로 안 묶인 것**이었다.

**내가 만든 것(공유 fixture 지점까지)**:
- `contracts/fixtures/run-result-view.json`, `contracts/fixtures/run-artifact-list.json` — 완료·검증된 run 예시. 커널 계약(`validate_contract`)에 유효.
- `tests/core/test_run_result_contract.py` — ① 공유 fixture가 커널 계약에 유효함(백엔드 `_checked`가 쓰는 **바로 그 validator**로), ② 모든 top-level 필수 필드를 하나씩 빼면 `VAL-0002`로 거부됨(공허 아님)을 단언. PG 불필요, 4 passed.

**사슬**: 백엔드 출력 →(result_view `_checked`)→ core.schema.json ←(공유 fixture, 내 Python 시험)→ core.schema.json ←(프런트 Ajv)→ 공유 fixture. 세 지점이 **하나의 스키마**에 묶여, 백엔드가 shape를 바꾸면(=generate_contracts로 스키마가 바뀌면) fixture와 프런트가 함께 깨진다.

## 변형 양방향 확증 (실측)
필수 필드 하나(`output`)를 fixture에서 제거:
- **Python**(커널 `validate_contract("RunResultView", …)`): **VAL-0002 실패**.
- **프런트**(apps/web `ajv/dist/2020.js` + ajv-formats, mirror 스키마 `contracts/v1alpha1/core.schema.json#/$defs/RunResultView`): **실패**.
- 정상 fixture는 양쪽 **통과**. 두 fixture 모두 전 필드가 load-bearing(어느 필드 제거도 Ajv에서 통과 안 함).
- **둘 다 실패** → 사슬 온전(한쪽만 실패면 끊긴 것). RunArtifactList도 동일 확인.
(프런트 Ajv 확인은 **일회용 node 스크립트**로 수행 — apps/web 코드 미커밋. Python 시험만 커밋.)

## 프런트 배선 인계 (Gemini 소유)
나는 **공유 fixture를 공유하는 지점까지** 만들었고 프런트가 **읽을 수 있음을 확인**했다(같은 스키마로 Ajv 검증 통과). 남은 프런트 코드는 Gemini가:
1. `apps/web` 계약 시험을 추가해 위 두 fixture를 읽고 `contracts/v1alpha1/core.schema.json#/$defs/RunResultView`·`RunArtifactList`에 Ajv 검증(discovery-candidates 시험과 동형).
2. 수기 타입 `types.ts`의 `RunResultView`/`RunArtifactList`를 그 스키마에서 생성/결속(수기 유지 시 계약과 어긋날 수 있음).
3. `DeveloperStudio` FB-03 시험들의 모의 응답을 이 공유 fixture로 대체해 **모의==계약**이 되게.
프런트 코드는 Gemini 소관이라 나는 수정하지 않았다.

## 소유·조율
**진행판에 기록**: run result/artifacts 계약 결속 = **Claude 담당**(공유 fixture+Python 결속 완료, 프런트 Gemini 인계). Codex가 계약 지도의 다음 항목을 잡을 때 이것과 겹치지 않게 — 사용자가 Codex에 다른 항목 배정. reviewer: Codex(커널 계약 결속 경계 검토), 프런트 배선 owner: Gemini.
