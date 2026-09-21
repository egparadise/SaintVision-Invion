---
doc_id: "REVIEW-CONTRACT-SHARED-FIXTURE-CLAUDE-001"
title: "Codex 계약 검증(8532f70·eb4366d) 독립 검토 — 공유 fixture가 프런트를 묶는가. 소스+변형"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T20:00:00+09:00"
branch_reviewed: "agent/codex/discovery-candidates-contract (eb4366d)"
source_of_truth: "Git"
tags: ["saintvision", "independent-review", "contract", "shared-fixture", "frontend", "mutation-testing"]
---

# Codex 계약 검증 독립 검토 — 공유 fixture가 프런트를 묶는가

내가 앞서 지적한 mock–계약 gap(프런트 adapter 시험이 임의 shape를 mock)에 대한 Codex의 답 `8532f70`·`eb4366d`(브랜치 `agent/codex/discovery-candidates-contract`, 통합 미반영)을 독립 검토했다. **범위: 프런트 쪽**(사용자는 Python 검증 완료). **핵심 질문: 공유 fixture가 정말 backend·frontend 양쪽을 묶는가.** apps/web 미수정 — 임시 worktree에서 변형·확인·원복, worktree 제거. `[소스]`/`[변형]` 구분.

## 사슬 구조 (schema.json = 단일 정본)
- **Backend**: Pydantic 모델 → `export_schemas.py --check`(model↔schema 게이트) → `contracts/discovery-candidates-response.schema.json`. Python 시험은 공유 fixture를 모델로 검증.
- **Frontend**: schema.json → `discovery-contracts.mjs --check`(schema↔생성 TS타입 게이트) → `apps/web/src/contracts/discovery-candidates-response.ts`("Do not edit by hand", json-schema-to-typescript 생성). 프런트 계약 시험은 공유 fixture를 공유 schema에 **Ajv 검증**(+음성대조).
- **공유 파일**: `contracts/fixtures/discovery-candidates-response.json`(fixture)과 `contracts/...schema.json`(schema)을 양쪽이 읽는다.

## 고리별 검증 (소스+변형)
1. **프런트가 공유 fixture를 읽는가 — 예** `[소스]`. `apps/web/tests/fixtures/discovery-candidates.ts`가 **복사본이 아니라** `readFileSync('../../../../contracts/fixtures/discovery-candidates-response.json')`로 공유 JSON을 읽는다. 복사본 드리프트 여지 없음.
2. **fixture 변형 → 프런트 깨지는가 — 예** `[변형]`. 공유 fixture의 `claimedCpuCores: 8`을 `"eight"`(타입 위반)로 바꾸니 프런트 계약 시험이 **FAIL**(Ajv). 즉 프런트가 공유 fixture+schema에 실제로 묶여 있다. 원복.
3. **schema 타입 변경 → 생성 TS타입 게이트 — 잡음** `[변형]`. schema의 `claimedCpuCores` type을 number→string으로 바꾸니 `npm run contracts:check`가 **FAIL exit 1**(생성 타입 stale). 원복.
4. **schema required-only 변경 → 상보 커버** `[변형]`. schema `required`에 property 정의 없는 필드를 추가하면 `contracts:check`는 **PASS**(생성 타입은 `properties`에서 나오므로 불변)이나, **프런트 Ajv fixture-검증은 FAIL**(required 강제). → 두 프런트 게이트가 **상보적**(contracts:check=타입 구조, Ajv=required/제약). 조용히 어긋나는 구멍 아님.
5. **게이트 CI 강제 — 예** `[소스]`. `.github/workflows/backend.yml:75 export_schemas.py --check`, `frontend.yml:43 npm run contracts:check`. 수동 스크립트가 아니라 CI에서 강제.

## 판정 — 끊긴 고리 없음
**프런트는 공유 계약에 진짜 묶인다**(변형으로 확증). 절반만 묶인 상태가 아니다. 모델→schema(export_schemas), schema→생성타입(contracts:check), fixture↔schema(Ajv, 양쪽), 모두 CI 게이트로 연결. 두 프런트 게이트가 상보적이라 타입 구조·required/제약을 함께 덮는다. **내가 앞서 지적한 mock–계약 gap을 이 구현이 닫는다** — 프런트가 더 이상 임의 shape를 쓰지 않고 공유 schema에 검증된다.

## 관찰 (구멍 아님, 참고)
- `contracts:check`(생성 타입)만으로는 property 정의 없는 required-only 변경을 못 잡지만 Ajv fixture-검증이 잡는다. 둘이 함께 있어야 완전하며 지금 둘 다 있다.
- 이 구현은 **discovery-candidates 응답 하나**에 대한 것이다. 다른 엔드포인트로 같은 패턴을 확장할 때 각 계약마다 (schema, fixture, 생성타입, 양쪽 검증)을 갖춰야 동일 보장이 선다 — 범위 확장 시 유의(정보).

## 인계
브랜치 `agent/codex/discovery-candidates-contract`는 sound, 끊긴 고리 없음 — 통합 반영 권고. apps/web은 Gemini 소유이나 이 계약 사슬은 Codex 구현이며 나는 수정하지 않았다(변형 원복·worktree 제거). 다음: Codex/Gemini 조율로 landing.
