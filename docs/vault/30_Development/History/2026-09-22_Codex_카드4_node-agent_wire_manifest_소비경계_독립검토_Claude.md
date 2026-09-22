---
doc_id: "HIST-CLAUDE-REVIEW-CODEX-CARD4-NODE-WIRE-001"
title: "Codex 카드 4 독립 검토 — 9c519774 node-agent wire ModelExecutionManifestObservation 소비 경계(VF-CL-02e) + 카드 3 F1 판별 시험 반영: Go 시험·vet, 실 PG M1 KILLED 확인, Go 되살림 2건(1 KILLED·1 SURVIVED=schema const 중복 방어) → 승인"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T23:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["review", "codex", "vf-cl-02", "node-agent", "wire-contract", "contracts-go", "mutation", "real-postgres"]
---

# Codex 카드 4 독립 검토 (reviewer Claude)

대상: integration `9c519774`(feat(node-agent): bind resolver manifest wire contract) + 보고 `e2ebadda`([[2026-09-22_21-58-06_KST_VF-CL-02E_NODE-WIRE_Codex_구현]]). 검토 트리 `.worktrees/claude-rev4`(detached tip `e2ebadda`, 종료 시 clean). Go 1.27.0(`C:\Program Files\Go`, 이번 PC에서 첫 로컬 Go 실행), 실 PG = `.env` DSN 일회용 DB(PowerShell 분리 1레인). **실제 수행한 것만** 기록. 앞 검토: [[2026-09-22_Codex_카드3_inv_URI_resolver_kernel_manifest_결속_독립검토_Claude]].

## 판정: **승인** (finding 0, 관찰 3)

## 1. 실측 표

| # | 범위 | 검증 | 결과 |
|---|---|---|---|
| 1 | 카드 3 F1 반영 | `tests/integration/test_model_uri_resolver_http.py` +34줄: `stale` 뒤 replica ready 복원 + `storage_contributions.status='revoked'` → 커널 `/execution-manifest` `readyNodes [node]` 유지, `/models/resolve` `readyNodes []`·`materialisable false` | 내 §5 제안과 동일 구조. 실 PG **1 passed** |
| 2 | M1 KILL 확인 | 같은 파일에 M1(`model_uri_resolver.py` 교집합 재검증 2줄 제거, `git diff --stat` 1 file +1 −2 확인) | **1 failed** `assert ['nod_…'] == []` → **KILLED**(카드 3에서 SURVIVED였던 변이) |
| 3 | schema mirror 동기 | `cmp contracts/v1alpha1/core.schema.json` ↔ `services/node-agent/internal/wire/core.schema.json` ↔ `control-plane/.../generated/core.schema.json` | 바이트 동일 |
| 4 | 생성 Go 타입 | `packages/contracts-go/contracts.go` `ModelExecutionManifestObservation` 필드(`ManifestHash`·`ShardLocations`·`Materialisable`·`ExecutionAuthorized`·`RequiresExecutionRevalidation`) 존재 | 일치 |
| 5 | Go 소비 경계 | `go test ./internal/wire/` · `go vet ./internal/wire/` | **ok**(2 시험 포함) · vet 0 |
| 6 | 계약 재생성 drift | `tools/generate_contracts.py` 실행 후 `git status` | node-agent mirror·Go 0 변경; `generated/models.py`만 CRLF 줄끝 변경(내용 diff 0) → 되돌림 |
| 7 | 게이트 | `check_contract_bindings` PASS 52/17 · `check_response_freshness` MISSING 0 · `route_coverage` 45/unserved 0 · `check_docs` PASS 816 · PG-free contract+route 45 passed | 전부 GREEN |
| 8 | 문서 | 권한 경계 정본 1.11.0 §"node-agent wire 소비 경계" | 코드와 일치(identity/hash 대조 → `NODE-0070`, 권한 플래그 고정, M1 경로 서술) |

## 2. 되살림 — Go 디코더 2건 + Python 1건(위 #2)

| 변이 | 대상 | 시험 | 결과 |
|---|---|---|---|
| M-G1 | `DecodeModelExecutionManifest`에서 `result.ManifestHash != manifestHash` 대조 제거 | `TestDecodeModelExecutionManifestRejectsScopeAndAuthorityDrift` | **FAIL "manifest hash drift was accepted"** → KILLED |
| M-G2 | 같은 함수에서 `!result.RequiresExecutionRevalidation` 검사 제거 | 전체 wire 시험 | **ok → SURVIVED**. 이유: canonical schema가 `requiresExecutionRevalidation`을 `const: true`로 고정해 `Validate()`가 먼저 거부하므로 디코더 검사는 **중복 방어**다. fail-closed는 유지되나 Go 시험에 `requiresExecutionRevalidation=false` 케이스가 없어 그 층의 무게는 0 |

## 3. 관찰 (finding 아님)
- **M-G2**: 디코더 권한 플래그 검사는 schema `const`와 이중이다. 이중 방어 자체는 바람직하나, Go 시험에 `requiresExecutionRevalidation=false` 입력(schema가 잡음)을 추가하면 어느 층이 막았는지 로그로 남는다. 후속 선택.
- **`generate_contracts.py` Windows CRLF**: `generated/models.py`가 줄끝만 바뀌어 dirty로 보인다(내용 동일). 생성기에 `newline="\n"` 고정 또는 `.gitattributes`가 없으면 Windows 작업자마다 가짜 drift가 난다. 별도 카드.
- **검토 절차 기록**: Go 변이와 실 PG 레인을 같은 트리(`claude-rev4`)에서 동시에 돌렸다. 두 레인이 만지는 파일이 서로 다르고(`model_manifest.go` vs `model_uri_resolver.py`) 각자 자기 파일만 되돌려 결과 간섭은 없었으나, 다음부터는 트리를 분리한다.

## 4. 부수 조치
- `.work/dev/orch/codex-worker-status.md`에 `CLAUDE-REVIEW:` 줄 기입. 코드 변경 없음(docs-only PR).
