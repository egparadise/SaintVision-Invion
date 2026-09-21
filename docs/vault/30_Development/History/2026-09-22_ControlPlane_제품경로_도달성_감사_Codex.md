---
doc_id: "AUDIT-CONTROL-PLANE-REACHABILITY-CODEX-20260922"
title: "Control-plane 제품 경로 도달성 감사"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-22T03:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["control-plane", "reachability", "static-audit"]
---

# Control-plane 제품 경로 도달성 감사

## 판정 기준

다음을 모두 충족할 때만 “구현·시험은 있지만 제품에서 호출되지 않는 기능 후보”로 센다.

1. 테스트나 정적 타입만이 아니라 동작하는 구현이 있다.
2. 현재 제품 동작으로 기대되는 계약·업무 흐름이 문서나 API 표면에 있다.
3. 선언된 서버/worker entrypoint에서 라우트, 조립, 설정, 등록, 큐·이벤트 소비 경로를 따라가도 구현으로 도달하지 않는다.
4. 별도의 의도적 단계 분리나 미완료 인계가 확인되면 결함으로 단정하지 않고 계획/결정 대기로 분류한다.

테스트 호출만으로 3번을 충족하지 않는다. 반대로 단순 유틸리티·생성 타입·외부 adapter primitive는 그 자체로 제품 기능이라고 보지 않는다.

## 범위와 방법

- 감사 고정 기준: `0d5b82591286975c226097f14cb4f309ca306629`; 격리 worktree `C:/Users/egpar/AppData/Local/Temp/sv-codex-contract-land-20260922`, branch `agent/codex/contribution-lifecycle-contracts`; private worktree clean at start. 정적 조사 KST 2026-09-22 03:44–03:52. 최종 문서 게이트는 integration `5bb87e7ed504da61df2155573024ca3595372a79` 위 audit candidate `1dfd519a`에서 실행했다.
- `services/control-plane/src/inv`의 69개 비-`__init__` Python 모듈을 읽고, 선언된 세 entrypoint `inv.app:main`, `inv-delivery-worker`, `inv-observer-worker`에서 AST 기반 로컬 import 폐포를 계산했다. 61개 모듈은 정적 import 폐포에 도달했고 8개는 별도 수동 확인 대상으로 나왔다.
- `app.py`의 FastAPI route/composition/lifespan, `workspace_config.py`, worker entrypoint와 `pyproject.toml` scripts를 대조했다. `WorkspaceRecovery`, `ModelRetryStore`, `PlacementStore`, `NodeTransfer`, `PostgresCredentialRegistry`, `Outbox`의 제품/시험 참조를 저장소 전체에서 분리해 조사하고, migrations와 해당 architecture/history 문서를 확인했다.
- 조사 명령군: `rg --files services/control-plane/src/inv`; `rg -n`으로 route, lifespan, registration, 각 대상 symbol을 product source/tools/tests에서 대조; `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` (Python 3.14.6) AST import-closure scan. 문서 검증 `python tools/check_docs.py`, `python tools/check_ontology.py`, `python tools/sync_obsidian.py --check`, `git diff --check`는 모두 exit 0. 최신 SHA에서 `check_docs`: 24 original hashes/715 versioned documents; `sync_obsidian --check`: 1516 managed/7 pending/0 conflicts, no writes. 제품시험·Docker·PostgreSQL·HTTP 실행은 하지 않았다. 이는 소스/구성 연결 감사이며 런타임 부재를 외부 배포 wrapper까지 일반화하지 않는다.

## 판정

### 현재 제품 소비자가 없는 복구 구현 — 기존 사용자 결정 대기 재확인

`WorkspaceRecovery.restore`와 `.checkout`은 실제 파일을 읽고 generation을 만들며, integration 시험에서 호출된다. 하지만 `configured_workspace`는 `WorkspaceAPI`만 만든다. 앱에는 start/resume와 checkout 파일·Git 라우트가 있으나 `WorkspaceRecovery` 생성이나 restore/checkout 라우트가 없고 queue/event 등록에서도 호출을 찾지 못했다. resume prepare가 요구하는 checkout row의 writer도 이 미연결 클래스다. 따라서 시험에서는 동작하지만 저장소의 제품 조립에서는 접근할 수 없다. 이는 새 finding이 아니라 기존에 사용자 결정으로 올린 복구 연결/보존 대기 건을 재확인한 것이다. 연결하거나 저장 정책을 바꾸지 않았다.

근거와 검색 경계: [[2026-09-22_workspace_snapshot_reader_inventory_Codex]] 및 `services/control-plane/src/inv/app.py`, `workspace_config.py`, `workspace_resume.py`, `workspace_recovery.py`.

### 모델 재시도/측정 배치 — 구현·DB 시험은 있으나 제품 호출 경로 미착지

`ModelRetryStore.prepare`는 failed Run의 lease 해제·승인·동일 모델 입력 검증 후 child Run, `PlacementStore.reserve`, lineage와 outbox를 한 트랜잭션에서 만든다. 별도 `model_retry_lineage` migration이 있고 integration 시험은 예산, 권한, rollback, 동시성 경로를 직접 호출한다. 그러나 앱 route에는 model retry/placement 요청이 없고, API 또는 worker composition에서 `ModelRetryStore`를 생성·호출하지 않는다. `PlacementStore`와 순수 `scheduler.place`의 유일한 제품 소스 caller는 이 미연결 retry 구현이다. Architecture 문서도 service endpoint와 업무 권한 binding을 후속으로 남긴다.

판정: 기능 구현의 우발 누락이라고 단정할 수 없다. 기존 문서가 후속 endpoint/auth binding을 명시하므로 “계획된 server-internal capability, 제품 진입점 미착지”가 정확하다. 사용자/업무 소유자가 이 retry 흐름을 현재 제품에 노출할지와 호출 owner를 결정해야 한다. 이번 감사에서는 route나 worker를 추가하지 않았다.

근거: `services/control-plane/src/inv/model_retry.py`, `placement.py`, `scheduler.py`, `app.py`; `tests/integration/test_model_retry.py`, `test_placement.py`, `test_model_node.py`; [[모델 실행 입력과 대체 Node 복구 계약]], [[모델 locality 예약과 실행 입력 경계]].

## 제품 기능으로 오인하지 않은 정적 미도달 항목

| 항목 | 미도달 사실 | 분류 |
|---|---|---|
| `NodeTransfer.fetch` | integration 시험에서 호출되며 `inv.node_chunk` 검증을 쓴다. 앱/worker 및 도구의 제품 조립은 호출하지 않는다. | Node executor와 외부 Node adapter 부재가 README에 명시되고 runtime/provider 연결이 후속 문서에 남아 있다. 의도된 integration gate이지 독립 결함으로 승격하지 않는다. |
| `PostgresCredentialRegistry.lookup` | 현재 참조는 integration 시험뿐이다. operator provisioning CLI는 자격증명 파일을 만들지만 이 runtime lookup registry를 제품 서버에 조립하지 않는다. | 동일하게 Node executor/runtime adapter 통합 대기. README의 명시된 제한과 일치한다. |
| `Outbox.publish_batch` / `.consume` | DB 통합 시험은 callback으로 직접 호출한다. publisher/consumer worker나 broker 설정·등록은 없다. | outbox row를 쓰고 `/events` route가 DB event를 읽는 기존 제품 경로는 연결돼 있다. 미도달인 것은 선택적 외부 broker adapter helper이며, 현재 요구된 제품 consumer가 없으므로 기능 결함으로 세지 않는다. |
| `inv.generated.models` | runtime import 폐포에서는 사용하지 않고 계약 시험이 생성 Pydantic 타입을 읽는다. | 의도적이다. 생성 파일 주석과 contract runtime은 JSON Schema를 authoritative validator로 사용한다고 명시한다. |

## 결론과 다음 행동

이 범위에서 구현과 시험만으로 제품 도달성을 증명할 수 없는 것은 두 기능군이다. WorkspaceRecovery는 이미 사용자 결정 대기다. ModelRetry/Placement는 문서상 endpoint/auth binding을 남긴 계획 기능이며, 노출할지 결정 전까지 연결하지 않는다. 나머지 미도달 adapter/helper는 명시된 Node 통합 전제 또는 선택적 broker 경계와 일치한다. 발견 없음으로 잘못 닫지 않는다.

다음 행동: 집계 담당/사용자는 `ModelRetryStore` 제품 진입점을 지금 제공할지와 담당자를 정한다. 복구 경로는 기존 결정 대기 목록에서 보존·연결 방침을 선택한다. Claude나 다른 담당의 검토는 이 감사에서 수행하지 않았으며 미요청이다.

## 경계

이는 고정 SHA의 정적 소스/설정 감사다. 앱/worker를 구동하거나 동적 plugin/외부 배포 wrapper를 조사하지 않았다. 따라서 “저장소에 선언된 entrypoint에서 연결되지 않음”을 넘어 배포된 외부 조립물에도 없다고 주장하지 않는다. 제품 코드, 설정, route, worker 연결은 바꾸지 않았다.
