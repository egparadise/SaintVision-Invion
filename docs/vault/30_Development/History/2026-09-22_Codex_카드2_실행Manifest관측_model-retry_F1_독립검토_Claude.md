---
doc_id: "HIST-CLAUDE-REVIEW-CODEX-CARD2-MANIFEST-F1-001"
title: "Codex 카드 2 독립 검토 — 4473c7f1 실행 Manifest 관측(VF-CL-02c) + model-retry F1 403 + 0046 SECURITY DEFINER: 실측·되살림 2건 KILLED → 승인"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T20:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["review", "codex", "vf-cl-02", "model-manifest", "model-retry", "security-definer", "mutation", "real-postgres"]
---

# Codex 카드 2 독립 검토 (reviewer Claude)

대상: integration `4473c7f1`(feat(core): add authorized model execution manifest view) + `036dfe9e`(보고 [[2026-09-22_20-19-51_KST_VF-CL-02C_MODEL-RETRY-F1_Codex_구현]]). 검토 트리 `.worktrees/claude-rev2`(detached `036dfe9e`, clean). 실 PostgreSQL = `.env` DSN(127.0.0.1) 일회용 Alembic-head DB, PowerShell 분리 실행(한 레인, status에 기입). **실제 수행한 것만** 기록.

## 판정: **승인** (finding 0, 관찰 2)

## 1. 실측 표

| # | 범위 | 검증 | 결과 |
|---|---|---|---|
| 1 | F1 타 tenant 403 (`model_retry.py`) | Codex `test_model_execution_manifest_http.py::…cross_tenant…` 실 PG | 2 passed(파일 전체) — 403 `AUTH-0030` ProblemDetails, idempotency 행 없음 |
| 1' | 같은 F1을 **내 독립 시험**으로 | PR #51 `test_model_retries_claude.py`의 pin을 503→**403 AUTH-0030**으로 뒤집어 정본 tip에서 실행 | **8 passed** — 발견자(나)의 시험이 수정을 확인 |
| 2 | VF-CL-02(c) 라우트 `GET …/models/{m}/versions/{v}/execution-manifest` (`model_view.py`, `app.py`) | HTTP 시험: ready / replica stale / **location version 드리프트** / mapping 부재 409 MODEL-0001 / 권한 없음 403 | 2 passed(위와 같은 파일). 응답 `executionAuthorized=false`·`requiresExecutionRevalidation=true` 고정(계약 `Literal`) |
| 3 | 0046 `SECURITY DEFINER` 최소 권한 | 일회용 migrated DB(head **0046**)에서 pg_proc/aclexplode/has_*_privilege 조회 | `prosecdef=True`, `search_path=pg_catalog`, owner `invowner`; **ACL = invowner·inv_kernel EXECUTE만**(PUBLIC 없음, `inv_app` EXECUTE False, 임의 role False); **`inv_kernel`에 `public.data_replicas` SELECT 없음**(False) — 원시 테이블 grant 없이 함수로만 접근; `inv.tenant_id` 미설정 시 함수 결과 **0행**(tenant 바인딩 fail-closed) |
| 4 | 계약 동기 | `check_contract_bindings` | PASS 52 fixture / 17 응답 타입 / 20 앵커 자리 / 12 replay — Codex 보고와 동일 |
| 5 | 신선도 | `check_response_freshness` | `kernel:ModelExecutionManifestObservation.observedAt` **ok**(report-only 지도에 등록됨) |
| 6 | 라우트 커버리지 | `route_coverage --served src --served services/control-plane/src --client apps/web/src` | clientPaths 44 / unserved 0 (새 라우트는 화면 미호출 — 정상, UI는 별도 카드) |
| 7 | PG-free 스위트 | `tests/core/test_model_execution_manifest_contract.py` + `tests/test_route_coverage.py` + `tests/test_response_freshness.py` | 46 passed |
| 8 | 문서 | `check_docs` | PASS 798 |

## 2. 되살림 (mutation) — 2건, 둘 다 KILLED

| 변이 | 대상 | 시험 | 결과 |
|---|---|---|---|
| M1 | `model_retry.py`의 preflight grant 블록 6줄 제거 | `…cross_tenant…` | **FAIL** `assert 503 == 403` → 503 회귀 재현. preflight가 F1의 실제 원인 제거이며 시험에 무게 있음 |
| M2 | `model_view.py` `usable = … and current == location_version` → `and True`(버전 드리프트 무시) | `…manifest_reports…` | **FAIL** `assert ['nod_…'] == []` — 버전이 올라간 location이 ready로 새는 것을 시험이 잡음 |

(첫 시도에서 PowerShell 정규식 치환이 파일에 적용되지 않아 "passed"가 나왔다 — 변이 diff를 `git diff --stat`으로 확인하는 절차를 넣고 재실행한 결과가 위 표다. 변이는 적용 확인 없이는 증거가 아니다.)

## 3. 관찰 (finding 아님)
- **존재 노출 정책**: 타 tenant는 404가 아니라 403 `AUTH-0030`이다 — grant 부재로 균일하게 거부하므로 run 존재 여부를 드러내지 않는다(404 분기 전에 막힘). 정책상 일관(`ModelCommitObservation`도 grant 먼저).
- **DEFINER 함수 owner가 superuser(invowner)** — 함수 본문이 tenant 설정으로 필터하고 `search_path=pg_catalog`·인자 `text[]`라 주입 면은 없다. 다만 RLS를 우회하는 경로이므로 함수 본문 변경은 반드시 리뷰 대상(이번 검토 범위에 기록).
- 화면 카드: 라우트는 unserved 0(호출자 없음)이라 UI 결속은 별도(Gemini).

## 4. 부수 조치
- PR #51(`agent/claude/decision6a-model-retry-integration`)에 F1 pin 뒤집기 커밋 추가(503→403), History v1.1.0.
- `.work/dev/orch/codex-worker-status.md`에 `CLAUDE-REVIEW:` 줄 기입.
