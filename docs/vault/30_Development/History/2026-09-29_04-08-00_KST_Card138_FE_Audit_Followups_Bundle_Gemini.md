---
doc_id: "HIST-GEMINI-CARD138-001"
title: "History: Card 138 프런트엔드 비차단 후속 감사 지적사항 통합 조치 (Items 1-6)"
version: "1.0.0"
status: "approved"
author: "Gemini"
updated: "2026-09-29T04:08:00+09:00"
source_of_truth: "Git"
---

# History: Card 138 프런트엔드 비차단 후속 감사 지적사항 통합 조치 (Items 1-6)

## 1. 개요 및 배경

앞선 검토(PR #219, PR #228, PR #212, PR #178, PR #190)에서 비차단(non-blocking / Low observation)으로 남겨진 6가지 프런트엔드 후속 개선 과제를 단일 PR로 일괄 수렴·해소하고, 모든 항목에 대해 **되돌리면 실패하는 자동화 시험(revert-fails tests)**을 완비하였다.

- **작업 브랜치**: `agent/gemini/card138-fe-bundle` (Base: `agent/gemini/card126-audit-fixes`, Head `27a6e4ca` 위 stacked)
- **담당자**: Gemini (Frontend / UI / 접근성 소유)
- **독립 검토자**: Claude (UI 및 회귀 시험 축), 제어 평면 계약 합의 (계약 축)

---

## 2. 6대 조치 항목별 세부 구현 및 시험

### Item (1) ModelLineageView W2/W4 로딩 해제 소유권 가드 및 입력 변경 취소
- **문제점**: `#219/#228` 계열 `ModelLineageView.tsx`에서 W2(버전 등록) 및 W4(보존 고정) 요청의 `finally` 블록이 이전 요청이 대체된 경우에도 무조건 로딩(`setRegLoading(false)`, `setPinLoading(false)`)을 해제하여, 새 요청이 진행 중임에도 버튼이 조기 활성화되는 잠재적 결함 존재.
- **조치 내용**:
  1. W3/W5와 동일한 소유권 규칙 적용: `finally`에서 `if (regAbortControllerRef.current === ctrl || regGenerationRef.current === currentGen) setRegLoading(false);`, W4도 동일하게 `pinAbortControllerRef.current === ctrl || pinGenerationRef.current === currentGen` 적용.
  2. 폼 입력 변경 핸들러(`handleProjectIdChange`, `handleModelIdChange`, `handleVersionChange`, `handleRegVersionChange`, `handleRegSha256Change`, `handleRegByteSizeChange`, `handlePinUntilChange`)에서 진행 중 요청 abort, ref 초기화, generation 증가 및 loading 즉각 해제.
- **되돌리면 실패하는 시험**:
  - `apps/web/tests/model-registry-business-routes.test.tsx` Test 21 & Test 22: 첫 요청 진행 중 두 번째 요청 제출 시 첫 요청의 `finally`가 로딩을 해제하지 않고, 요청 중 입력값 변경 시 즉각 abort 및 로딩 해제 실측.

### Item (2) SealRecordPanel 봉인 Run 전환 중 늦은 R1/R2 응답 Abort 가드
- **문제점**: `#212` `SealRecordPanel.tsx`에서 활성 `runId`가 변경되었을 때 이전 run의 진행 중이던 비동기 콜백(R1/R2/R3) 응답이 늦게 도달하여 새 run의 상태를 오염시킬 위험.
- **조치 내용**:
  - 모든 비동기 단계 콜백 진입점에 `if (signal.aborted || generationRef.current !== currentGen) return;` 세대 및 중단 가드를 배치하여 stale 응답 즉시 폐기.
- **되돌리면 실패하는 시험**:
  - `apps/web/tests/run-detail-seal-record.test.tsx` Test 25: `runId`가 `run_01`에서 `run_02`로 전환된 후 도착한 이전 run의 R1/R2 응답이 폐기되고 상태 오염이 발생하지 않음을 실측.

### Item (3) DeveloperStudio 취소·Receipt 모달 직접 접근성 시험 (useModalA11y)
- **문제점**: `#178` `DeveloperStudio.tsx`의 워크스페이스 취소 확인 모달 및 영수증(receipt) 모달에 대한 접근성 키보드 트랩 및 트리거 복원 직접 시험 부재.
- **조치 내용**:
  - `apps/web/src/shared/ui/useModalA11y.ts` 공용 접근성 훅 신설: 포커스 트랩(Tab / Shift+Tab 순환), Esc 키 전파 차단 및 닫기, 모달 닫힘 시 트리거 요소 포커스 원복(`triggerRef.current?.focus()`).
  - `DeveloperStudio.tsx`의 Cancel 및 Receipt 모달에 `useModalA11y` 연동.
- **되돌리면 실패하는 시험**:
  - `apps/web/tests/developer-studio-modal-a11y.test.tsx`: 취소 모달 및 영수증 모달의 포커스 트랩 순환, Escape 키 닫기, 이전 트리거 버튼 포커스 복원 전수 검증.

### Item (4) G-07 Eval Runner casesDigest loopCount 포함 (N1) 및 REPAIRING/1 돌연변이 가드 (N2)
- **문제점**: `#190` EVL-05 합성 평가 러너에서 `casesDigest` 해시에 `loopCount`가 포함되지 않아 루프 수 변조가 감지되지 않았고(N1), 코딩 과제에서 1회 복구(`REPAIRING/1`)를 유발하여 `> 0` → `> 1` 돌연변이를 사살하는 태스크가 부재(N2).
- **조치 내용**:
  - `apps/web/src/features/agent/evalRunner.ts`: `digestPayload`에 `${c.loopCount ?? 0}` 추가.
  - `apps/web/src/features/agent/agentEngine.ts`: 비용 및 예산 생성자/메서드(`initialBudgetKrw = 650000`, `setTenantBudget`, `overrideCostKrw`) 정합.
  - 정본 Evidence 파일 생성: `docs/vault/30_Development/Evidence/s09-g07-eval-evidence-fc1c4eb5.json` (130 cases, CasesDigest `0c9a5e19...`, Conformance 100%).
- **되돌리면 실패하는 시험**:
  - `apps/web/tests/agent-mutation-guards.test.ts`:
    - N1: 케이스의 `loopCount`를 변조하면 판정(`verdict`)이 같아도 `casesDigest`가 반드시 변경됨을 실측.
    - N2: 수리 루프 진입 조건을 `> 0`에서 `> 1`로 변조하는 돌연변이를 `REPAIRING / 1` 상태 코딩 과제가 정확히 사살(`killed`)함을 실측.
  - `apps/web/tests/agent-eval-runner.test.ts`: 드리프트 방지 및 130개 케이스 결정론적 실행 검증 (17 passed).

### Item (5) 공용 날짜 검증 가드 (dateTime.ts) 도입 및 무효 타임존 오프셋 차단
- **문제점**: `#219 r3`에서 여러 관측 파일(`modelRegistryObservation.ts`, `modelCommitmentObservation.ts`, `runSealObservation.ts`)에 중복 복제되어 있던 날짜 검증 함수가 `+99:99` 등 비정상 타임존 오프셋을 허용하는 문제.
- **조치 내용**:
  - `apps/web/src/shared/utils/dateTime.ts` 신설: 윤년·일자 유효성뿐 아니라 타임존 오프셋 범위(`tzHour <= 23 && tzMin <= 59`)를 엄격 검증.
  - 각 관측 파일에서 중복 함수를 제거하고 `dateTime.ts`의 정본 가드로 단일화.
- **되돌리면 실패하는 시험**:
  - `apps/web/tests/model-registry-business-routes.test.tsx` Test 23: `+99:99`, `-99:99`, `+24:00` 등 비정상 오프셋 입력 시 클라이언트 가드에서 거부되고 네트워크 요청이 차단됨을 실측.

### Item (6) #228 L-항목 잔여 (식별자 prefix 정합 및 세대 단독 가드)
- **문제점**:
  1. `ModelLineageView.tsx`에서 플레이스홀더 접두사가 서버 규격과 불일치 (`mod_...` 대신 `mdl_...`, `apr_...` 대신 `apv_...`).
  2. W2/W4 늦은 응답 폐기에서 abort가 수반되지 않더라도 세대 카운터(`regGenerationRef.current !== currentGen`) 단독으로 stale 응답을 버릴 수 있는지 격리 검증 필요.
- **조치 내용**:
  - `ModelLineageView.tsx:644` `placeholder="mdl_..."`, `:1564` `placeholder="승인 식별자 입력 (apv_...)"` 정합.
- **되돌리면 실패하는 시험**:
  - `apps/web/tests/model-registry-business-routes.test.tsx`:
    - Test 24: 플레이스홀더 접두사가 서버 규격(`mdl_...`, `apv_...`)과 정확히 일치하는지 실측.
    - Test 25: W2 등록 요청 중 abort 신호와 무관하게 모델 식별자 변경으로 세대만 증가했을 때 늦게 도착한 응답이 UI 상태를 오염시키지 않음을 실측.

---

## 3. 로컬 게이트 실측 검증 결과

| 검증 단계 | 수행 명령 | 결과 요약 | Exit Code |
|---|---|---|---|
| **Vitest 단위/통합** | `npx vitest run` (apps/web) | **84 test files passed (84), 814 tests passed (814)**, 0 failures (26.76s) | `0` |
| **TypeScript 타입 검사** | `npx tsc -b` (apps/web) | **0 errors** | `0` |
| **프로덕션 번들 빌드** | `npm run build` (apps/web) | Vite 프로덕션 빌드 성공 (`dist/assets/index-BLqj7uvO.js` 876.03 kB) | `0` |
| **파이썬 라우트 커버리지** | `pytest tests/test_route_coverage.py` | **40 passed** in 2.91s | `0` |
| **프런트엔드 무결성** | `python tools/check_frontend_integrity.py` | 92 files 0 violations (All 9 integrity rules satisfied) | `0` |
| **계약 바인딩 검사** | `python tools/check_contract_bindings.py` | 55 fixtures / 20 bound types / 14 replay guards PASS | `0` |
| **문서 무결성 검사** | `python tools/check_docs.py` | 24 original hashes, 920 versioned docs, wiki links PASS | `0` |
| **Obsidian 동기화 사전 검사** | `python tools/sync_obsidian.py --check` | 1764 managed files, 0 conflicts PASS | `0` |

---

## 4. 인계 및 다음 단계

- **작업 브랜치**: `agent/gemini/card138-fe-bundle`
- **PR 대상**: Base `agent/gemini/card126-audit-fixes` (PR #243) 위 stacked PR 생성.
- **후속 담당**: Claude (독립 UI 및 시험 축 리뷰) 및 제어 평면 계약 합의 (계약 축 검토).
