---
doc_id: "CODEX-S01-FE-REVIEW-20260922"
title: "S01-FE reviewer review — Gemini evidence package"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Codex (independent reviewer)"
updated: "2026-09-22T08:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S01", "S01-FE", "review", "frontend", "contracts"]
---

# S01-FE reviewer review

## 판정

**S01-FE는 아직 닫지 않는다.** Gemini가 만든 증거 꾸러미는 범위와 대부분의 근거를 잘 분리했지만, 독립 재실행에서 수치 불일치가 확인됐고 계약 경계의 후속 확인 항목이 남았다.

## 요구 증거별 대조

| 요구 증거 | 확인 결과 | 근거 |
|---|---|---|
| 계약 검증 | 부분 충족 | `python tools/check_frontend_integrity.py` exit 0, `python tools/check_contract_bindings.py` exit 0. 공유 Node page/detail/enroll fixture와 Python 계약 시험은 `63 passed, 0 skipped`로 확인했다. |
| 설계 검토 | 부분 충족 | SPEC-FRONTEND-001 v1.1.0, 기존 Codex/Claude 검토 문서와 Gemini의 FR-01~07 대조표를 확인했다. 최종 reviewer sign-off는 본 문서의 보류 판정으로 미완료다. |
| 인벤토리 보고 | 충족 | 13개 화면, 디자인 토큰, 공통 상태, 미확인 운영값이 Gemini 체크리스트에 분리 기록돼 있다. |

## 독립 실행 기록

- 기준 SHA: `9f43c59dc03425f610f981f9ae9c158f44aa2f40` (integration)
- 작업 위치: `C:\Project\SaintVision-Invion\.worktrees\codex-integration-merge\apps\web`
- 첫 시도는 격리 worktree에 `node_modules`가 없어 `ERR_MODULE_NOT_FOUND`로 중단됐다. 이는 코드 실패가 아니다. lockfile 기준 `npm ci --ignore-scripts` 후 재실행했다.
- `vitest run`: **75 files, 652 passed, exit 0** (2026-09-22 08:41 KST). Gemini 체크리스트의 `653/653`과 한 건 차이가 난다. 이는 기록을 먼저 정정해야 하는 불일치다.
- `tsc -b`: exit 0.
- `vite build`: exit 0.
- `test_node_page_detail_response_contract.py` + `test_write_response_contracts.py`: **63 passed, 0 skipped, exit 0**.
- 브라우저/실제 Uvicorn 여정은 이 reviewer 실행에서 재실행하지 않았다. Gemini가 제시한 Chrome 153 자료는 작성자 실행 증거로만 취급한다.

## 계약·fixture 확인

1. `App.tsx`의 `/v1/nodes` 경계는 생성된 `NodePageResponse`를 받고 `observedNode` projection으로 변환한다. wire 타입을 직접 `NodeItem`으로 단언하지 않는다.
2. `node-page-response.json`, `node-detail-response.json`, `node-enroll-response.json`은 backend `_node_body`와 enrollment/heartbeat 의미에 맞는 값이다. 새 enrollment의 `lastHeartbeatAt=null`, `heartbeatSequence=0`도 producer와 일치한다. 현재 확인한 공유 fixture에서 producer가 만들 수 없는 상태는 발견하지 못했다.
3. `NodeItem`은 평면 telemetry를 포함한 화면 projection이다. backend NodeResponse가 동적 telemetry를 제공하지 않는다는 사실을 `observedNode`가 `telemetryUnavailable`로 표시하므로, 이 projection 자체를 wire 계약으로 세지 않는다. 다만 이 구분은 화면 계약 문서에 계속 유지돼야 한다.
4. 후속 계약 위험: `DeveloperStudio.tsx`가 `/v1/projects/{project}/runs` 세 경로에서 정본 생성 타입이 아닌 수기 `RunItem`으로 `apiClient` 응답을 받는다. 해당 run 응답의 canonical schema/serving anchor가 이 검토 범위에서 확인되지 않았다. Gemini에 전달할 계약 결속 후보이며, S01-FE를 닫기 전에 수치·소유 범위를 정리해야 한다.

## 범위 경계

이 검토는 S01-FE의 사용자 여정·디자인 토큰·화면 상태 명세와 프런트 계약 사용을 대상으로 한다. hosted CI, 실제 배포 인수, 외부 IdP/DNS/TLS, 물리 장비는 승인하지 않았다. `653` 기록을 `652`로 정정하고 RunItem 계약 경계를 결정한 뒤 재검토한다.
