---
doc_id: "API-RESPONSE-CONTRACT-STORAGE-001"
title: "Storage 목록 응답 계약 확장 Codex 기록"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude (pending)"
updated: "2026-09-21T15:06:00+09:00"
source_of_truth: "Git"
---

# Storage 목록 응답 계약 확장

## 작업 경계

- Task: API mock ↔ backend response contract 확장, 1차 범위
- Owner: Codex; 독립 reviewer: Claude 대기
- Base SHA: `3f83e3fe271c5d95d3aceed499dcbd74ee4765f9`
- 작업 위치: `integration/all-agents-unified`, `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`
- 선택 경로: `GET /v1/storage/contributions`, `GET /v1/storage/locations`. ResourceExplorer 및 storage observation adapter가 보여주는 목록이다. 화면 영향도와 discovery 계약 첫 조각의 패턴 재사용 가능성을 기준으로 선택했다.

## 구현

두 페이지 응답에 strict Pydantic 모델을 추가해 `items`가 기존 `ContributionResponse`/`DataLocationResponse`로 구성되고 `nextCursor`가 필수 nullable 필드가 되게 했다. FastAPI routes에 `response_model`을 결속했다. 모델에서 JSON Schema를 내보내고 JSON Schema에서 TypeScript 타입을 생성하는 기존 계약 생성 사슬을 확장했다. Provider serialization 시험과 Vitest/Ajv 계약 시험은 backend를 띄우지 않고 동일한 `contracts/fixtures` JSON 파일을 읽는다. Main adapter와 alternate `fabricObservation` adapter가 generated wire types를 사용하고, 관련 frontend mocks도 shared fixture를 재사용한다. Nullable capacity가 허용될 때 ResourceExplorer는 용량을 `미확인`으로 표시한다.

`route_coverage`와는 역할이 다르다. Route scanner는 정적 path shape와 endpoint 존재를 찾고, 여기서는 endpoint의 JSON response shape와 mock/provider 일치를 검사한다. 어느 쪽도 live HTTP 실행을 증명하지 않는다.

## 작성자 검증과 provenance

양방향 mutation 대조와 최초 긍정 확인은 base SHA `3f83e3fe271c5d95d3aceed499dcbd74ee4765f9`의 dirty worktree에서 2026-09-21 KST 15:04에 했다. Commit 후 최종 긍정 재검증은 SHA `9ff829859b6771fbccac58c2d0089bf6738edb53`의 clean worktree에서 15:07에 했다. Branch `integration/all-agents-unified`, worktree `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`, Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` (3.14.6), Node `C:/Program Files/nodejs/node.exe` (v24.17.0)다. Provenance 도구는 각 명령을 직접 실행해 exit code를 수집했다. 실행자는 Codex, 독립 검토자는 아직 없다.

| 검사 | 명령(저장소 또는 `apps/web` cwd) | 결과 |
|---|---|---|
| provider/model contract | `.venv/Scripts/python.exe -m pytest -q tests/core/test_storage_list_response_contract.py` | exit 0, 12 passed, 2 warnings |
| model→JSON Schema drift | `.venv/Scripts/python.exe tools/export_schemas.py --check` | exit 0, 24 schemas match |
| JSON Schema→TypeScript drift | `node scripts/api-response-contracts.mjs --check` | exit 0, 3 response types match |
| UI suite | `node node_modules/vitest/vitest.mjs run` | exit 0, 35 files / 336 passed |
| TypeScript project build | `node node_modules/typescript/bin/tsc -b` | exit 0 |
| production bundle | `node node_modules/vite/bin/vite.js build` | 최초 dirty-tree 실행 exit 0, Vite build completed; clean commit-SHA 재실행은 미수행 |

PostgreSQL DSN gate는 absent였다. 따라서 DSN을 요구하는 DB integration 경로는 실행하지 않았으며 성공이나 실패로 세지 않는다. CI, live HTTP, 브라우저/운영 인수도 수행하지 않았다.

## 양방향 mutation 대조

1. Pydantic page contract에 required `contractProbe`를 추가하고 generator drift check를 실행했다. Provider가 shared fixture를 직렬화하는 테스트는 실패했고 `tools/export_schemas.py --check`도 schema drift로 exit 1을 냈다. 변형을 원복한 뒤 정상 검사는 통과했다.
2. 반대 방향으로 shared contribution fixture에서 required `nodeId`를 제거했다. Python shared-fixture 검증과 Vitest/Ajv schema 검증이 실패했다. 변형을 원복하고 전체 Vitest와 Python focused suite를 재실행해 통과시켰다.

두 대조는 contract definition 변경과 mock/fixture 변경을 각각 독립적으로 검출한다. 임시 변형 파일은 원복했고 검사 후 제품 코드에 남아 있지 않다. 최종 clean-SHA 확인에서 Python focused suite, export schema, TypeScript contract generator, Vitest, `tsc -b`, `check_docs.py`가 다시 통과했다. Vite build는 최초 구현 상태에서만 확인했다.

원격 통합의 Claude commit `5f42c31`을 merge한 뒤, merged SHA `f3ca36ca1be26f874c1ead64a23dc18bc9fab840`에서도 clean tree로 동일 핵심 검증을 2026-09-21 KST 15:09에 재실행했다. Response pytest 12 passed; Vitest 35 files/336 passed; schema export (24 schemas), frontend type generator (3 contracts), `tsc -b`, Vite build, `check_docs.py`, `check_ontology.py`, `sync_obsidian.py --check` 모두 exit 0. Obsidian check 당시 1400 managed/0 pending/0 conflicts였다. 이 SHA에서 원격 통합 ref는 local last-fetch 기준 `AHEAD 2`였으며, push 후 원격 대조는 별도 확인한다.

## 상태와 다음 행동

작성자 로컬 검증 완료. 독립 리뷰, CI 및 live acceptance는 pending이므로 이 작업은 완료/운영 인수가 아니다. 다음 행동: Claude가 fixed-SHA diff와 계약/시험을 독립 검토한다. 이후 화면에서 영향이 큰 API adapter 하나씩을 선택해 같은 shared response-contract chain으로 넓히되 모든 adapter를 한 번에 묶지 않는다.

처음 provenance 호출은 worktree-relative `.venv` 및 `apps/web` cwd에서 root의 `tools/provenance.py`를 찾으려는 invocation error로 실패했다. 프로젝트 `.venv`와 provenance script의 절대 경로를 지정해 다시 실행했으며, 그 잘못된 wrapper 호출은 제품 검사 결과로 집계하지 않았다.
