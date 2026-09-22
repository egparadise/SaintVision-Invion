---
doc_id: "HIST-CLAUDE-PR57-MODEL-RETRY-UI-REVIEW-001"
title: "PR #57 RunDetail 모델 재시도 UI(결정 #6 6a, 계약 563c54ce) 독립 검토 — 게이트 GREEN이나 입력 사양 합성·비안정 Idempotency-Key·배너 과장 → 수정 요청"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T21:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["review", "pr-57", "model-retry", "decision-6", "frontend", "zero-mock", "idempotency"]
---

# PR #57 독립 검토 — RunDetail 모델 재시도 UI

대상 `agent/gemini/model-retry-ui` head **`f156d21b`**(Antigravity/Gemini). 검토 트리 `.worktrees/claude-pr36`(detached f156d21b, clean). 계약 기준 `563c54ce`(`ModelRetryPrepareInput/Result`), 서버 동작 기준은 내 통합 검증 [[2026-09-22_결정6a_model-retries_통합검증_실PG_실HTTP_Claude]]. 보안 관점은 Codex 위임(한 줄).

## 판정: **수정 요청** (3건 + 경미 1)

## 1. 실측
| 검증 | 결과 |
|---|---|
| `tsc -b --force` | exit 0 |
| `vitest run tests/model-retry-action.test.tsx` | 8 passed |
| `check_frontend_integrity` | 9 rules, 0 violations |
| `route_coverage`(tip 서빙 트리) | clientPaths 45 / unserved 0 — `/v1/projects/{}/runs/{}/model-retries` 서빙됨 |
| delta | 웹 4(types·RunDetail·modelRetry.ts·시험) + 문서 4; tip 겹침 진행판 1 |
| 계약 대조 | Input 8 필수+2 선택 전부 송신; Result 6 필드 배너·lineage에 사용; tri-state(로딩 disabled·`role=alert`·`role=status`) 존재 |

## 2. 발견
- **F1 입력 사양 합성(Zero-Mock 위반, 실질)** — `run.resourceRequest`(types.ts 신설 선택 필드)를 채우는 producer가 화면 어디에도 없다(`ControlRunView`에도 자원 필드 없음). 실제 화면은 항상 어댑터 기본값 500 millicores / 1 GiB / maxHostLoad 0.8 / requiredBytes 0으로 **커널 배치 예약을 체결**한다 — 부모 Run의 실제 요구와 무관. 시험은 fixture에 `resourceRequest`를 넣어 통과. 요구: 실제 producer(부모 workload 관측)가 있을 때만 활성, 없으면 버튼 비활성 + "입력 사양 미관측" 정직 고지, `?? 500` 류 기본값 제거.
- **F2 Idempotency-Key `Date.now()`** — 클릭마다 새 키 → 재요청이 같은 child를 못 받고(멱등 의미 소실) 두 번째 클릭은 409 MODEL-0003. 부모 Run당 안정 키로.
- **F3 성공 배너 과장** — "입력 파일·체크포인트·환경 설정이 **동결되었으며** 예약이 **체결**"은 사실과 반대. `requiresFrozenInputAndApproval=true`는 "동결·승인이 아직 필요"이고 커널은 child를 `planned`로만 둔다(실 PG 관측). 문구 정정.
- 경미: `formatModelRetryProblem`이 status로 분기 — 400 분기는 죽음(서버는 422 `VAL-000x`), 422는 일반 문구. `problem.code`로 분기 권고.
- **보안(Codex 위임)**: Idempotency-Key 예측 가능성, 클라이언트 제공 자원 사양의 서버측 상한 강제 위치 확인.

## 3. 조건
F1~F3 반영 + 케이스 갱신 후 승인. 병합 자체의 회귀 위험은 낮음(게이트 GREEN). PR 코멘트: https://github.com/egparadise/SaintVision-Invion/pull/57#issuecomment-5775824377
