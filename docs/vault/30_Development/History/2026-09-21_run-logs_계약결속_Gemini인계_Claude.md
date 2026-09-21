---
doc_id: "CLAUDE-RUN-LOGS-CONTRACT-GEMINI-HANDOFF-001"
title: "run-logs(RunLogView) 계약 결속 — Gemini 프런트 배선 인계"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
frontend_owner: "Gemini"
updated: "2026-09-21T18:15:00+09:00"
timezone: "Asia/Seoul"
integration_tip_at_write: "7ab955b"
source_of_truth: "Git"
tags: ["contract-binding", "run-logs", "gemini-handoff", "drift"]
---

# run-logs(RunLogView) 계약 결속 — 내가 한 것 + Gemini 인계

run-result와 **동일 패턴·동일 커널 시스템**. 보수적 규칙대로 계약+fixture+Python 검증까지 내가 만들고 **프런트 배선은 Gemini**.

## 내가 결속한 것 (integration tip 7ab955b 위)
- 공유 fixture: `contracts/fixtures/run-log-view.json` — 커널 `logs()`의 "출력 있음" 케이스에 충실(7필드 전부 required).
- Python 계약 시험: `tests/core/test_run_log_contract.py` — **3 passed**:
  - fixture↔커널 계약(`validate_contract("RunLogView")`; 커널 `result_view.logs()`가 `_checked("RunLogView")`로 도는 바로 그 검증).
  - 7필드 전부 load-bearing(각 필드 제거 → `DomainError VAL-0002`).
  - `source` const 위반(`"execution-kernel"` 아님) → `DomainError VAL-0002`.
- 변형 **양방향** 확증: Python `validate_contract`(VAL-0002) + **일회용 Ajv**(`contracts/v1alpha1/core.schema.json#/$defs/RunLogView`) 둘 다 필수필드 제거·source const 위반 거부.
- 검증 환경: `.venv/Scripts/python.exe`(3.14.6), inv 패키지 폐포 clean 확인.

## 실측 드리프트 (Gemini가 프런트에서 고쳐야 할 것)
`apps/web/src/contracts/types.ts:563` 의 수기 `RunLogView`가 계약보다 **느슨**하다:
| 필드 | 스키마(계약) | 프런트 수기 타입 | 문제 |
|---|---|---|---|
| `source` | const `"execution-kernel"` | `'execution-kernel' \| string` | `\| string`이 const를 무력화 — 아무 문자열 허용 |
| `truncated` | **required** (`boolean\|null`) | `truncated?:` (optional) | 계약은 항상 존재, 타입은 없어도 됨 |
| `absentReason` | **required** (`string\|null`) | `absentReason?:` (optional) | 동상 |

→ 프런트 모의가 `truncated`/`absentReason` 없이도 TS 통과하지만 백엔드 계약은 거부. 공유 fixture에 결속하면 이 드리프트가 드러난다.

## Gemini 인계 (프런트 배선 — run-result와 동일)
1. `types.ts`의 `RunLogView`를 계약과 일치시킨다(`source` const, `truncated`/`absentReason` required). 또는 `@/contracts/kernel-observation`처럼 생성 타입(`packages/contracts-ts`)을 re-export.
2. logs 엔드포인트 소비 어댑터(RunDetail/DeveloperStudio 로그 패널) 배선 — **현재 apps/web에 logs fetch 어댑터 부재**(dormant 타입). run-result 어댑터와 동일 형태로 신설.
3. 프런트 Ajv 계약 시험 추가: `contracts/fixtures/run-log-view.json`을 `#/$defs/RunLogView`에 대조 + 필수필드 제거 음성대조(Codex의 `run-approval-observation-contract.test.ts` 형태 재사용).

## 겹침/담당
- Codex는 pool/placement/distributed-plan WIP 중(worktree dirty 실측) — run-logs 비겹침.
- 공유 진행판(`전체 개발 진행 현황.md`) 담당 기록은 현재 Gemini가 편집 중(dirty)이라 미기입 — **run-logs=Claude(계약) / 프런트=Gemini** 항목을 Gemini 편집 착지 후 반영 요.

관련: [[2026-09-21_이어가기_상태와규칙_Claude]] · [[2026-09-21_run결과_artifacts_계약결속_Claude]]
