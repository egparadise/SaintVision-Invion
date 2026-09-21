---
doc_id: "CLAUDE-INDEP-REVIEW-RUN-APPROVAL-PAGE-001"
title: "독립 검토 — Codex run/approval 페이지 계약 결속 (고정 SHA 3052038)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex(피검토)"
updated: "2026-09-21T18:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["independent-review", "contract-binding", "codex", "fixed-sha"]
---

# 독립 검토 — run/approval 페이지 계약 결속

## 검토 트리 못 박기 (움직이는 브랜치 ref 금지)
- **피검토 SHA**: `agent/codex/run-approval-observation-contract` tip = `3052038e03640b20cacd861388dc48a97d1ac65c` (로컬=origin 동일 확인).
- 실질 코드 커밋: `7a9b5002f495007d2b117b470fc76a9763de5259`. integration(그 시점 `7ab955b`) 대비 4 ahead / 1 behind(1 behind = 내 인계 커밋 `8c12449`, Codex 미수신).
- **오염 방지**: Codex worktree `.worktrees/codex-run-approval-observation-contract`는 HEAD=3052038이나 **clean 아님**(Codex가 pool/placement WIP 62파일 진행 중). 내 검토 대상 13파일 + 시험 import/read 폐포가 dirty 집합과 **교집합 없음**을 실측 확인한 뒤에만 실행함(placement/pool fixture·test_pool_placement 는 폐포 밖).
- 인터프리터: `.venv/Scripts/python.exe` (Python 3.14.6). Python 실행 시 `PYTHONPATH=<worktree>/services/control-plane/src`로 `inv`가 **worktree(3052038)** 로 해석됨을 확인(`inv.__file__` 검증). `ControlRunPage`가 main(7ab955b)엔 없고 worktree에만 있으므로 필수 조건.

## 확인한 것 (전부 실행 증거)
1. **스키마 정합**: `ControlRunPage`는 신규 $def, `ApprovalPage`는 기존 $def. 둘 다 `required:[items,nextCursor]`, `nextCursor: anyOf[<Id>, null]`, `items` maxItems 200.
2. **4개 wire 사본 일관성**: `ControlRunPage` 블록이 `contracts/v1alpha1`·`services/control-plane/src/inv/generated`·`services/node-agent/internal/wire` 3개 JSON에서 **바이트 동일**(sha256 앞16 `797881e4f01c21af`). 생성 타입도 정합: `generated/models.py`(ControlRunPage L679·ApprovalPage L1331)·`packages/contracts-ts`(interface)·`packages/contracts-go`(struct).
3. **Python 계약 시험** `tests/core/test_run_approval_observation_contract.py`: **7 passed**(fixture↔`validate_contract`+pydantic roundtrip 2 · nextCursor 제거 음성대조 2 · provider가 공유 fixture 반환 2 · view 동일투영 1). 단언 도달 확인(음성대조는 `pytest.raises(ValidationError)`, provider는 `result==expected`로 `validate_contract` 경유).
4. **schema-level 돌연변이 직접 확증**(시험이 pydantic만 보므로 내가 보강): `validate_contract("ControlRunPage"/"ApprovalPage", nextCursor 제거)` → 양쪽 **DomainError**. 즉 스키마가 nextCursor를 실제 강제.
5. **프런트 Ajv/vitest** `apps/web/tests/run-approval-observation-contract.test.ts`: **6 passed**(두 fixture 스키마 유효 · nextCursor 제거 Ajv 거부 2 · 매핑+project-scoped 라우트 2 · 런타임 가드 오형 `17`/`false` 거부 1).
6. **control.py 결속**: `list_runs`/`list_approvals`가 결과를 `validate_contract("ControlRunPage"/"ApprovalPage", result)` 후 반환. 커서 계산 `rows[limit-1][id]`(limit+1 fetch, rows[:limit] 반환)는 마지막 반환행 id로 정확.

## 판정
사용자 확인 요청("nextCursor 제거 시 프런트·Python 양쪽이 깨진다")을 **고정 SHA 3052038에서 실행으로 확증**: pydantic model 거부 · schema `validate_contract` 거부 · Ajv 스키마 거부 · 런타임 가드 오형 거부가 모두 재현됨. 4개 wire 사본·생성 타입 정합. **결함 없음. sound — 병합 진행 무방.**

## 관찰(결함 아님)
- 어댑터 런타임 가드는 `nextCursor`를 `null` 또는 `typeof string`만 확인(Id 패턴 미검사) — 스키마보다 의도적으로 느슨. 엄격 shape는 계약 시험이 담당하므로 계층 분담 타당. (nextCursor **부재**도 `undefined !== null && typeof !== 'string'`으로 런타임 거부됨 — 코드상 확인.)

관련: [[2026-09-21_이어가기_상태와규칙_Claude]] · `pass-report-provenance-rule` · `judge-integration-files-from-origin-not-worktree`
