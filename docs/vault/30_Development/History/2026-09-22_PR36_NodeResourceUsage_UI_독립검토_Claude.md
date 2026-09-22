---
doc_id: "HIST-CLAUDE-PR36-NODE-RESOURCE-USAGE-REVIEW-001"
title: "PR #36 NodeResourceUsage UI 연결 — 독립 검토 (Gemini→Claude 교차): 게이트 GREEN이나 서빙 라우트 0·제품 배선 0·스캐너 사각"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T18:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["review", "pr-36", "node-resource-usage", "zero-mock", "route-coverage", "frontend", "handoff"]
---

# PR #36 독립 검토 — NodeResourceUsage UI 연결

대상: PR #36 `agent/claude/node-usage-ui` head **`96fa3ec6`**(Antigravity 작성, 화면 레인). 검토 규칙: Gemini→Claude 교차, **실제 수행한 검증만** 기록. 검토 트리 `.worktrees/claude-pr36`(detached 96fa3ec6, `git status --porcelain` 0줄, node_modules는 메인 junction). 비교 기준: 병합 base `c5042322`, 현재 integration `7b251bd6`.

## 판정 요약

**게이트는 전부 GREEN이고 Zero-Mock 프로젝터는 되살림으로 무게를 확인했다. 그러나 "UI 연결"이라는 제목과 달리 (1) 어댑터가 부르는 라우트를 서빙하는 백엔드가 없고, (2) 어댑터를 부르는 화면이 없으며, (3) 그 둘을 잡아야 할 route_coverage 스캐너가 이 어댑터 모양(변수에 조립한 URL)을 못 본다.** 병합 자체는 안전(배선이 안 돼 사용자에게 아무 것도 안 보임)하지만, "연결됨"으로 기록하면 축 1(배선≠통과)·축 5(계약 있으나 서빙 미강제)의 반복이다. 병합 조건과 후속 카드를 아래에 둔다.

## 1. 실측 (실제 수행)

| # | 검증 | 명령/방법 | 결과 |
|---|---|---|---|
| G1 | 타입 | `npx tsc -b --force` | exit 0 |
| G2 | 회귀 시험(PR 파일) | `npx vitest run tests/node-resource-usage-contract.test.tsx` | 4 passed |
| G3 | 회귀 시험(전체) | `npx vitest run` | **76 files / 659 passed**, exit 0 (integration 기준선 75/655 + 이 파일 4) |
| G4 | 빌드 | `npm run build` | exit 0 (9.11s) |
| G5 | 정직성 스캐너 | `PYTHONUTF8=1 python tools/check_frontend_integrity.py` | 9 rules, 0 violations, exit 0 |
| G6 | 라우트 커버리지 | `python tools/route_coverage.py --served . --client apps/web/src --json` | clientPaths 30 / unserved **0** / exit 0 — **아래 F3 참조(거짓 초록)** |
| M1 | **되살림(Zero-Mock 무게)** | 프로젝터의 `reserved`를 `measured`와 무관하게 `… : 0`으로 변이 → 같은 시험 | **1 failed**(`expect(gpu.reserved).toBeNull()`) → 되돌림. 시험이 실제로 합성 0을 막는다 |
| C1 | 계약 정합 | `packages/contracts-ts` `NodeResourceUsageResponse`(eceac8cf) ↔ `observedNodeResourceUsage` 필드 대조 | source/nodeId/stateAsOf/resources[].{resourceId,kind,unit,capacity,offered,reserved,spare,measured,observedAt} 1:1. `kind`·`unit` 리터럴 집합 동일 |
| C2 | 서빙 라우트 존재 | `grep -rn "resource-usage\|NodeResourceUsage" src services/control-plane/src tests`(generated 제외) + `route_coverage.scan_served('.')` | **서빙 0**. `/v1/nodes/{}` 계열 서빙 = `nodes, liveness-sweeps, {}, {}/control, {}/drain, {}/heartbeats, {}/offers, {}/resume, {}/undrain, projects/{}/nodes`뿐. 커널 응답 타입·fixture·negative 시험만 존재(Codex 결정 문서 그대로: "실제 route/service는 계약 다음 카드로 분리") |
| C3 | 제품 배선 | `grep getNodeResourceUsage apps/web/src` / `App.tsx`의 `<NodeDetail …>` | 호출자 **0**. `App.tsx:426`은 `resourceUsage`를 안 넘긴다 → 패널은 시험의 fixture로만 렌더된다 |
| C4 | 스캐너 사각 재현 | `route_coverage.client_paths()`에 (a) PR의 어댑터 본문, (b) `apiClient(\`/v1/nodes/${id}/resource-usage\`)` 직접 리터럴 | (a) **∅**(못 잡음) / (b) `{'/v1/nodes/{}/resource-usage'}`(잡음). 원인: URL을 `const url = cond ? \`…\` : \`…\``로 조립한 뒤 `apiClient(url)` — 스캐너는 호출 인자의 리터럴/템플릿만 본다 |
| S1 | PR delta 범위 | `git diff c5042322 96fa3ec6 --name-only` / `git diff origin/integration 96fa3ec6 --stat` | 웹 6파일 외에 `InvFileExplorer.tsx`(+151, 카탈로그 탐색기 — `db05daee`·`d45435be` 등 **미병합 gemini/S02-FE·codex 커밋**이 8c504682 merge로 딸려옴), `tests/core/test_credential_provision_cli.py`(BOM 1자만 다름), 나머지 비-웹 파일은 현재 integration과 내용 동일(이미 착지) |

## 2. 발견 (원인 단위, 소유 명시)

- **F1 — 서빙 라우트 없음 (Backend 카드 미착수; 소유 Claude 레인, 계약 소유 Codex)**: `getNodeResourceUsage`는 `/v1/nodes/{n}/resource-usage`·`/v1/projects/{p}/nodes/{n}/resource-usage`를 부르지만 어느 트리도 서빙하지 않는다(C2). 결정 #2 A는 계약만 착지했고 라우트는 "다음 카드"다. **호출되면 404**. PR 설명 "Bind getNodeResourceUsage adapter"는 사실이나 "연결"은 아니다.
- **F2 — 제품 배선 없음 (Gemini/화면)**: 어댑터·패널·버튼은 있으나 `App.tsx`가 자원 사용량을 조회해 `NodeDetail`에 넘기는 코드가 없다(C3). 사용자는 이 PR 후에도 아무 변화를 못 본다. 축 1 "배선≠통과"의 앞 단계(배선 자체가 없음).
- **F3 — route_coverage 스캐너 사각 (도구 소유 Claude; Rule 8 부류)**: 변수에 조립한 URL을 못 본다(C4). 그래서 G6이 30/0으로 초록이면서 F1을 놓쳤다 = **"검사는 했으나 대상 밖"**(오늘 밤 부류: 스캐너 모양지정). 스캐너 docstring이 "static path shapes only"라 자기 한계는 선언했으나, 이 모양(어댑터 함수 안 `const url = …; apiClient(url)`)은 코드베이스에 흔하다 → 지정 확장 필요. **내 레인 후속**: `client_paths`가 `apiClient(<식별자>)`의 정의를 같은 파일에서 역추적(또는 어댑터에서 리터럴을 직접 넘기는 관례 강제).
- **F4 — 프로젝터의 조용한 강등 1곳 (Gemini, 경미)**: `capacity`/`offered`가 유한수가 아니면 `0`으로 대체(`kernel-observation.ts`). 계약이 정수를 보장하므로 도달 불가이나, Zero-Mock 함수 안에 "미지값→0" 분기가 있는 건 자기모순이며 계약이 깨졌을 때 조용히 0을 그린다. 권고: 던지거나 `measured=false`로 강등을 **드러내라**.
- **F5 — PR 범위에 남의 미병합 작업이 섞임 (프로세스)**: `InvFileExplorer.tsx` +151(카탈로그 탐색기)은 이 PR 주제가 아니고 미병합 브랜치에서 딸려왔다(S1). 이대로 병합하면 그 작업의 소유·검토가 흐려진다(공유워크트리 규칙 R5의 브랜치판). 권고: integration 위로 **rebase해 웹 6파일+문서만** 남기거나, 포함을 명시하고 소유자(Gemini) 검토를 받는다.
- **F6 — locale 의존 표시 (Gemini, 정보)**: `NodeDetail`의 `toLocaleString()`·`toLocaleTimeString()`은 locale 미지정(기존 코드). PR #40이 시험 쪽 locale을 고정했고 화면은 `ko-KR` 고정이 관례(`ApprovalCenter`) — 이 파일도 맞추면 C6 부류 재발을 막는다. 시험이 이 값을 단언하지 않아 지금은 red 아님.
- **F7 — 시험 입력의 합성 0 (정보)**: `NodeItem` 타입이 `cpuUsagePercent: number`라 미관측 fixture도 `0`을 넣는다. 이 PR이 만든 게 아니라 `contracts/types.ts`의 기존 모양(미관측을 표현 못 함) — 별도 카드(노드 관측 타입의 null 허용).

## 3. 병합 판정

- **병합 가능(조건부)**: G1~G5·M1·C1 통과, 사용자 가시 변화 없음(F2)이라 회귀 위험 낮음. 조건: (a) F5 처리(rebase 또는 명시), (b) PR 제목/설명과 History 문서를 "어댑터·뷰모델·패널 **준비**; 서빙 라우트(백엔드 카드)와 App 배선은 후속"으로 정정 — "연결 완결"로 기록하지 않는다(규칙 "있다≠작동한다").
- **완료 아님**: 결정 #2의 화면 노출은 F1(라우트)+F2(배선)이 착지하고 실 PG·실 HTTP로 한 번 통과해야 닫힌다.

## 4. 후속 카드 (소유)

1. **Backend 라우트** `GET /v1/projects/{p}/nodes/{n}/resource-usage`(+ 비-프로젝트 경로 여부 결정) — 커널 `inv.resources`·최근 heartbeat `usedQuantity`로 `NodeResourceUsageResponse` 조립, `validate_contract` 앵커, 서빙앵커 시험, 실 PG. **Claude**(중간 난도 서비스) / 계약 앵커 검토 Codex.
2. **App 배선** — 노드 선택 시 조회, 404/미서빙을 "미제공"으로 정직 표시(모의 금지). **Gemini**.
3. **스캐너 확장** — 변수 조립 URL 추적 + 이 PR 어댑터를 회귀 fixture로. **Claude**.
4. F4·F6 정리 — **Gemini**(작음).

관련: PR #36의 검토요청 문서(`2026-09-22_NodeResourceUsage_UI_PR36_Gemini검토요청.md`, PR 브랜치에만 존재) · [[2026-09-22_노드_자원_사용량_HTTP_계약_결정제안_Codex]] · [[검증규칙과_세축_canon]] · [[2026-09-22_되돌아오는결함_구조가막나_주의에기대나_Claude]]
