---
doc_id: "PORTAL-REFRESH-POLLING-R2-GEMINI"
title: "포털 폴링 고갈 방지 및 게이트웨이 상태 식별 보강 (R2)"
version: "1.0.0"
status: "active"
author: "Gemini"
updated: "2026-11-06T21:45:00+09:00"
source_of_truth: "Git"
---

# 포털 폴링 고갈 방지 및 게이트웨이 상태 식별 보강 (R2)

## 1. 개요 및 배경

- **Task**: `PORTAL-REFRESH-POLLING-R2-20261106` (Task ID: `task_9d814a8270e1`, Dispatch ID: `ctx_d855f1849f6b`)
- **담당 및 역할**: Gemini via Antigravity (프런트엔드 바운디드 구현 및 단위/CI 검증 전담; Root 배포 및 인프라 소유).
- **작업 환경**: Worktree `D:/Project/SaintVisionI-Invion/portal-refresh-fleet-ui-20261106`, branch `agent/gemini/portal-refresh-polling-r2-20261106`.
- **기준 베이스**: `854a8eab0b6e236b62878f49ee941c700e458af0` (이전 R1 완료 커밋).
- **R2 동결 후보 커밋**: `22c20a838fe0ab82a772641163ef553494c5bea3`
- **배경**: Claude의 1차 독립 검토(`ab7f768db22c0b6f2f4ac812f63a1b605cd26d19/review.json`) 결과 제기된 `UI-854-M1`(Medium) 및 `UI-854-L1` ~ `UI-854-L4`(Low) 지적 사항을 해결하고 실측 검증을 완료함.

---

## 2. 검토 지적 사항별 해결 내역

### 1) UI-854-M1 (Medium): 지연 응답 고갈 방지 및 행 걸린 요청의 유한 타임아웃
- **원인 분석**:
  - R1에서는 `request === nodeRequest.current` 방식의 엄격한 최신 요청 동일성 검사를 수행함.
  - 응답 지연이 5초 폴링 주기보다 길 경우(예: 6초 지연, Reviewer Probe P6), 매 5초마다 `nodeRequest.current`가 증가하여 이전 응답의 성공/실패가 매번 버려지는 기아(starvation) 현상이 발생함.
  - 또한 요청이 백엔드/프록시에서 무한 대기할 경우(Reviewer Probe P7), `nodesState`가 영구히 이전 'success' 상태로 유지되어 stale 경고가 표출되지 않고 0대 정상을 계속 주장함.
- **해결 조치**:
  1. **단조 증가 적용 펜스(`appliedRef`) 도입**: `request > nodeAppliedRef.current` 검사를 통해, 이전에 적용된 관측보다 최신인 응답은 중간에 새 요청이 발송되었더라도 버려지지 않고 즉시 UI에 반영됨 (`nodeAppliedRef.current = request`).
  2. **10초 유한 타임아웃(`AbortController`)**: 각 폴링 요청에 10초 타임아웃을 적용하여, 응답이 지연되거나 무응답인 경우 명시적 `error` 및 `cluster-stale-warning`(`role="alert"`)을 표출하고 과거 스냅샷 시점을 투명하게 고지함.
  3. `fetchRuns`, `fetchApprovals`, `fetchWorkspaces`에도 동일한 단조 증가 펜스 및 10초 타임아웃을 전면 적용함.

### 2) UI-854-L1 (Low): 게이트웨이 실패 상태 레이블 세분화
- **원인 분석**:
  - R1에서는 네트워크 실패와 수신된 비정상 응답(HTML 200 SPA fallback, JSON 404/503, status!=ok)이 모두 `Gateway: Offline`으로 축약됨.
- **해결 조치**:
  - `Header.tsx`의 게이트웨이 상태를 판별 유니온(`{ kind: 'unknown' | 'healthy' | 'degraded' | 'offline' }`)으로 세분화:
    - `healthy`: HTTP 200 + application/json + status==='ok' → `${rttMs}ms` (녹색 도트)
    - `degraded`: 서버 응답 수신 성공했으나 규약 불일치(HTML 200, 404, 503, down) → `비정상 응답` (적색 도트)
    - `offline`: 네트워크 연결 실패(Failed to fetch) 또는 4초 타임아웃 초과 → `Offline` (적색 도트)
    - `unknown`: 초기 미관측 상태 → `확인 중...` (회색 도트)
  - `tests/acc09-contrast-tokens.test.tsx`의 AST 스타일 속성 수(20개) 및 evaluated pair(정확히 11개) 래칫을 100% 준수함.

### 3) UI-854-L2 (Low): 게이트웨이 헬스체크 순서 역전 방지
- **해결 조치**:
  - `Header.tsx`에 `reqSeqRef` 시퀀스 카운터 및 4,000ms `AbortController` 타임아웃을 적용.
  - 이전의 느린 성공 응답이 나중에 도착하더라도, 더 최근의 실패 관측을 덮어쓰지 못하도록 `reqId === reqSeqRef.current` 검사를 통해 폐기(Probe H2 검증).

### 4) UI-854-L3 (Low): ResourceExplorer 재시도 이벤트 전달 방지
- **원인 분석**:
  - `ResourceExplorer.tsx`의 `<button onClick={onRetryNodes}>`에서 React의 `SyntheticMouseEvent`가 전달되어, `isBackground` 매개변수가 truthy로 평가되는 결함.
- **해결 조치**:
  - `ResourceExplorer.tsx`: `onClick={() => onRetryNodes?.()}`로 래핑하여 이벤트 객체 전파를 차단.
  - `App.tsx`: `const isBg = isBackground === true;`로 불리언 타입을 엄격히 비교하고, `handleManualRetryNodes`, `handleManualRetryRuns`, `handleManualRetryApprovals` 콜백을 명시적으로 선언하여 수동 재시도시 항상 `isBackground=false`로 실행되도록 보장.

### 5) UI-854-L4 (Low): App 수준의 종합 검증 테스트 통합
- **해결 조치**:
  - `apps/web/tests/portal-refresh-fleet-ui.test.tsx`에 Section 10(Reviewer Probes P1~P9, H1~H2)을 통합하여 총 35개 테스트로 확장.
  - P1: 빈 스냅샷 주기적 폴링 중 패널 언마운트/플리커 방지
  - P2: 빈 스냅샷 이후 백그라운드 실패 시 `role="alert"` stale 경고 표출 및 복구 시 해제
  - P3: 비어있지 않은 노드 스냅샷 유지 및 stale 경고 표출
  - P4: 최신 우선 펜스(순서 역전 시 과거 응답 폐기)
  - P5: 프로젝트 전환 시 이전 프로젝트 지연 응답 폐기 및 미관측 상태 리셋
  - P6: 5초 주기보다 긴 6초 지연 응답이 정상적으로 수신되어 새 노드가 표출됨
  - P7: 10초 초과 행 걸린 요청의 명시적 타임아웃 및 stale 경고 표출
  - P8: 승인 목록 실패(`approvalsState === 'error'`) 시 안건 결재/반려 API 호출 완전 차단
  - P9: ResourceExplorer 재시도 버튼 클릭 시 수동 재시도(`isBackground=false`) 트리거
  - H1: Header 실패 레이블 식별(비정상 응답 vs Offline)
  - H2: Header 시퀀스 펜스로 이전 성공이 최신 실패를 덮어쓰지 못함

---

## 3. 로컬 검증 실측 결과

모든 검증은 명령어 실행 직후 `$LASTEXITCODE`를 확인하여 0을 실측함.

| 검증 항목 | 실행 명령어 | Exit Code | 실측 결과 요약 |
|---|---|---|---|
| 포털 리프레시 단위 시험 | `cd apps/web && npx vitest run tests/portal-refresh-fleet-ui.test.tsx` | 0 | 35 passed (100% 성공) |
| 대비 토큰 및 AST 래칫 | `cd apps/web && npx vitest run tests/acc09-contrast-tokens.test.tsx` | 0 | 46 passed (evaluated pair 11개 준수) |
| 인증서 신선도 및 폴링 | `cd apps/web && npx vitest run tests/app-node-certificate-freshness.test.tsx` | 0 | 9 passed (폴링 횟수 및 스케줄링 검증) |
| 관측 계약 픽스처 | `cd apps/web && npx vitest run tests/run-approval-observation-contract.test.ts` | 0 | 6 passed (공유 픽스처 및 라우트 검증) |
| 실시간 관측 단위 시험 | `cd apps/web && npx vitest run tests/live-observation.test.tsx` | 0 | 27 passed |
| TypeScript 타입 검사 | `cd apps/web && npx tsc -b` | 0 | 0 errors |
| 프로덕션 번들 빌드 | `cd apps/web && npm run build` | 0 | built in 5.06s (`dist/assets/index-CvDvyizV.js`) |
| 프런트엔드 무결성 게이트 | `python tools/check_frontend_integrity.py` | 0 | 94 files scanned, 9 rules satisfied (0 violations) |
| 계약 바인딩 게이트 | `python tools/check_contract_bindings.py` | 0 | 57 fixtures, 21 bound types, 14 replay guards PASS |
| 라우트 커버리지 게이트 | `pytest tests/test_route_coverage.py` | 0 | 41 passed in 1.34s |
| 문서 정합성 게이트 | `python tools/check_docs.py` | 0 | 24 original hashes, 1260 versioned documents PASS |
| Obsidian 동기화 점검 | `python tools/sync_obsidian.py --check --state ...` | 0 | 2828 managed files, 0 conflicts, no writes |
| 동기화 상태 해시 불변 | `Get-FileHash .../obsidian-sync-state.json` | 0 | `58E776629B8945B7A1D7B196C7AC751A10C01B874FE989D1953D22EF2BB0358D` (일치) |

---

## 4. 원격 GitHub Actions CI 검증 결과

- **대상 브랜치**: `agent/gemini/portal-refresh-polling-r2-20261106`
- **동결 후보 커밋 SHA**: `22c20a838fe0ab82a772641163ef553494c5bea3`

| 워크플로 명 | Run ID | Job ID(s) | 소요 시간 | 상태 | 결론 | 비고 |
|---|---|---|---|---|---|---|
| Documentation Build | `42219586479` | `127898008985` | 23s | completed | **success** | docs, check_docs, contract_bindings, frontend_integrity 전원 통과 |
| Frontend Build & Test | `42219574051` | `127897973932`<br>`127897974300` | 1m 41s<br>1m 22s | completed | **success** | frontend (ESLint, Vitest, tsc, build), Portal Container Hardened Smoke 전원 통과 |

### 생성된 빌드 아티팩트 (`42219574051`)
1. `saintvision-web-dist`:
   - Artifact ID: `13502802678`
   - 크기: 1,119,071 bytes
   - SHA256 Digest: `sha256:8ab34e777e6169da9d6ffbb4fb9e6010e1c482277b701548c3ecda1f8c022388`
2. `saintvision-portal-release`:
   - Artifact ID: `13501724534`
   - 크기: 25,984,356 bytes
   - SHA256 Digest: `sha256:583b1303eeda2401bb6951f1830904d7d451770ab63c64161be09c54af9a0d15`

---

## 5. 범위 제한 및 인계 상태

- **불가침 경계 준수**:
  - 라이브 서비스(3100, 8080, 8443, r5)에 대한 임의 재시작 또는 간섭 없음.
  - 호스트 Chrome Computer Use / CDP 브라우저 접근 완전 배제 (헤드리스 Vitest 및 CI 컨테이너 검증 사용).
  - 데모 LAN pilot DB 0대 노드 상태 준수 및 5대 허위 데이터 위조 일체 없음.
  - 공유 레지스트리, 공통 진행판, ADR, 타 Agent 문서를 수정하지 않음.
- **인계 상태**:
  - Independent Review: **PENDING** (Claude R2 재검토 대기)
  - Deployment: **NOTRUN** (Root 배포 대기)
