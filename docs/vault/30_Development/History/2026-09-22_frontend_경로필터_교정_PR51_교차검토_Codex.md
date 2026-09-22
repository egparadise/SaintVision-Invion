---
doc_id: "HIST-CODEX-FRONTEND-PATHS-PR51-REVIEW-001"
title: "Frontend 경로 필터 교정과 PR #51 결정 6a 교차검토"
version: "1.0.0"
status: "active"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-22T19:25:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["ci", "frontend", "github-actions", "model-retry", "postgresql", "review"]
---

# Frontend 경로 필터 교정과 PR #51 결정 6a 교차검토

## Frontend workflow 관측과 교정

Claude hosted CI triage는 Frontend Build가 integration에서 당일 한 번만 실행돼 다섯 workflow의 같은-SHA 증거가 생기지 않는 문제를 기록했다. 기존 push/PR filter는 `apps/web/**`, `contracts/**`, workflow 파일만 보았지만 web source와 시험은 `packages/contracts-ts/src`를 직접 import하므로 package-only 변경을 빠뜨렸다. `contracts/**`는 공유 schema·fixture 입력을 이미 덮었다.

- `main`과 `integration/all-agents-unified` push에서는 `paths`를 제거해 모든 착지 SHA에 Frontend를 생성한다.
- PR은 비용을 제한하면서 `apps/web/**`, `contracts/**`, `packages/contracts-ts/**`, `.github/workflows/frontend.yml` 변경을 검증한다.
- `docs.yml` route-coverage 배선처럼 Frontend 빌드 입력이 아닌 변경은 PR에서 Documentation이 담당한다. integration에 착지하면 push filter가 없으므로 Frontend도 실행되어 같은-SHA 증거를 만든다.

## PR #51 독립 검토

대상은 PR #51 head `ec58e0c174444e46569dc0fa1401274a2c55de71`이다. `tests/integration/test_model_retries_claude.py`는 `TestClient(create_app(...))`로 실제 `POST /v1/projects/{project}/runs/{parent}/model-retries`를 호출해 인증, 요청·응답 계약, DomainError→ProblemDetails 매핑과 `ModelRetryStore`를 함께 지난다. `.env`의 `INV_TEST_ADMIN_DSN`을 사용하고 PowerShell `Start-Process`로 단일 파일만 분리 실행했다.

| 검증 | 결과 |
|---|---|
| 실 PG + 실 ASGI route 단일 파일 | **8 passed / 0 skipped / exit 0 / 17.29s** |
| failed-only | planned/awaiting_approval/scheduled/cancelled → 409 `MODEL-0007`; failed+미해제 lease → 409 `LEASE-0003`; child 0 |
| idempotency | 동일 키·본문은 동일 201 child; 본문 충돌 409 `IDEM-0001`; 키 없음 422 `VAL-0003`; 다른 키 409 `MODEL-0003` |
| authz | `can_request` 없음 → 403 `AUTH-0030`; child 0 |
| 정직성 | `requiresFrozenInputAndApproval=true`, child `planned`, tool claim 없음 |
| 영속·격리 | lineage 1행, 부모·자식 fencing token 교집합 없음, response lease와 DB의 미해제 child lease 일치 |

판정은 **시험·증거 PR 범위 승인**이다. 코멘트: https://github.com/egparadise/SaintVision-Invion/pull/51#issuecomment-5774858320

Finding F1은 타 tenant 요청이 기대 4xx가 아니라 `503 SYS-0001`로 분류되는 현재 backend 결함이다. idempotency ledger INSERT가 run/grant 확인보다 앞서 project FK에서 실패하는 원인이며 child·lineage 유출은 관측되지 않았다. 이 PR은 현 동작을 숨기지 않고 명시 pin하므로 검증 PR에는 비차단으로 두되, backend 후속은 `RES-0004` 또는 `AUTH-0030` 계열 4xx로 고치고 시험 기대값을 함께 뒤집어야 한다. PR은 최신 integration과 conflict 상태이므로 재기반 중 시험 blob이 달라지면 재검토한다.

## 검증 범위

메모리 경보 때문에 전체 Vitest/build/pytest는 실행하지 않았다. workflow YAML 파싱·정책 불변식, `check_docs`, `check_contract_bindings`, `check_ontology`, `git diff --check`만 R1 후보에서 수행하고 종료 코드를 lifecycle에 기록한다.
