---
doc_id: "PORTAL-REFRESH-POLLING-R3-GEMINI"
title: "포털 폴링 인증서 구간 타임아웃 및 요청 취소 판정 보강 (R3)"
version: "1.0.0"
status: "active"
author: "Gemini"
updated: "2026-11-07T02:40:00+09:00"
source_of_truth: "Git"
---

# 포털 폴링 인증서 구간 타임아웃 및 요청 취소 판정 보강 (R3)

## 1. 개요 및 배경

- **Task**: `PORTAL-REFRESH-POLLING-R3-20261106` (Task ID: `task_8dfd2a5d01a2`, Dispatch ID: `ctx_c8a99a3645b0`)
- **담당 및 역할**: Gemini via Antigravity (프런트엔드 바운디드 구현 및 단위/로컬 검증 소유; 배포 및 런타임 제어는 Root 소유).
- **작업 브랜치**: `agent/gemini/portal-refresh-polling-r3-20261106`
- **기준 베이스**: `9c25f3c9cab162f424744d79f9a4e21729c40404` (R2 최종 동결 커밋).
- **1차 소스 커밋**: `9cd017abf26a145d15a5c1b0d915662c3c71a724`
- **최종 정정 소스 커밋**: `b48c2c4492f8aea4b55c33161733a9a6fb9eed8c`
- **배경**: Claude의 2차 독립 검토(`71f26dbfc648a8140ac688df3fa89d6952d81d0d/review.json`) 결과 제기된 `UI-R2-M1`(Medium) 및 `UI-R2-L1` ~ `UI-R2-L3`(Low) 지적 사항을 해소하고 엄밀한 실측 검증을 완료함.
- **독립 소스 검토 현황**: 불변 소스 `b48c2c44`에 대한 Claude 3차 독립 검토 결과 `SOURCE_AXIS_ACCEPT:626ab0eda10c22e8539546db8d9639092d88f7e7` 확정 (Docs CI Run `42263763156`, job `128050178761`, 19개 전 스텝 통과; 이전 M1/L1/L2/L3 전원 CLOSED, 블로킹 이슈 0건, 소스 수정 불요 판정). 정적 독립 리뷰 및 Root 실측 CI/가드 증빙 기반이며, 6건의 INFO 한계(R2b 늦은 거절 no-op 경계 등)가 유지됨. 본 리포트 및 최종 Docs 동결/비문서 바이트 동등성은 실제 배포 전 통과해야 할 Root 게이트임.

---

## 2. 검토 지적 사항별 해결 내역

### 1) UI-R2-M1 (Medium): 노드 인증서 관측 2차 leg 타임아웃 결속
- **원인 분석**:
  - `apps/web/src/app/App.tsx`의 `fetchNodes` 내부에서 1차 `/nodes` 호출에는 `controller.signal`을 전달했으나, 2차 leg인 `fetchProjectNodeCertificates(targetPrj)` 호출 시그널 인자가 누락되어 있었음.
  - `/node-certificates` 엔드포인트가 무한 행에 걸리거나 60초 504 지연이 발생할 경우 10초 타이머의 abort가 도달하지 않아 10초 한도를 초과하여도 에러/stale 상태로 전환되지 않고 이전의 0대 정상 상태를 무기한 유지하는 결함이 존재함.
- **조치 내용**:
  - `certObs = await fetchProjectNodeCertificates(targetPrj, controller.signal);` 형태로 동일 `controller.signal` 전달을 결속함.
  - 내부 `catch (err: any)` 블록에서 `controller.signal.aborted`인 경우 예외를 재던져 외곽 catch에서 타임아웃/오류 처리를 일관되게 수행하도록 함 (단, 단순 통신 오류는 graceful fallback 유지).
  - 단위 시험 R1(인증서 행 시 10초 한도 내 stale/alert 전환), R1b(60초 504 시 stale 전환), T1(실제 transport wrapper에서 AbortSignal 전달 및 10초 abort) 검증 완료.

### 2) UI-R2-L1 (Low): 요청 취소(Supersede)와 타이머 만료(Timeout)의 판정 엄밀화
- **원인 분석**:
  - 이전 R2 catch 블록에서는 `err?.name === 'AbortError'`를 타임아웃으로 단순 분류하여, 사용자가 새로고침 버튼을 누르거나 프로젝트 전환 시 진행 중이던 백그라운드 요청이 정상 취소(0ms 경과)되었음에도 `10s Timeout` 에러 메시지와 경고 배너가 깜빡이는 결함이 있었음.
  - 또한 거절 에러의 메시지만으로 판정할 경우 취소된 이전 요청의 늦은 응답이 잘못 타임아웃으로 취급될 위험이 있었음.
- **조치 내용**:
  - 4대 리소스(`fetchNodes`, `fetchRuns`, `fetchApprovals`, `fetchWorkspaces`) 전체 catch 블록에서 `controller.signal.reason`의 메시지가 `'REQUEST_TIMEOUT'`인 경우에만 타임아웃으로 판정하도록 결속함.
  - 사용자의 수동 재시도, 프로젝트 전환, 언마운트 등으로 인한 취소는 `controller.signal.aborted && !isTimeout` 조건에 의해 즉시 `return` 처리하여 화면 깜빡임과 거짓 타임아웃 배너를 원천 차단함.
  - 단위 시험 R2(수동 갱신 시 0ms 취소 에러 배너 없음), R2b(늦은 타임아웃 에러 거절에도 소유 reason 기반 취소 방어), R5(프로젝트 전환 격리), R6(로그아웃 격리) 검증 완료.

### 3) UI-R2-L2 (Low): Header 4초 타임아웃 데드라인의 응답 바디 확장 및 비정상 응답 유지
- **원인 분석**:
  - `Header.tsx`에서 헤더 도착 직후 `clearTimeout(timeoutId)`를 호출하여, 헤더 이후 JSON 바디 전송이 행에 걸릴 경우 4초 한도가 작동하지 않는 결함이 있었음.
  - 또한 단순 파싱 실패(SyntaxError) 시 무조건 Offline으로 강등하면 `UI854-L1` 합의(비정상 응답 degraded)에 위배됨.
- **조치 내용**:
  - 헤더 도착 직후의 조기 `clearTimeout`을 제거하고 타이머 정리를 `finally` 블록으로 일원화하여 바디 수신까지 4초 데드라인을 보장함.
  - 바디 파싱 시 non-abort SyntaxError는 degraded('비정상 응답')으로 안전 강등하고, 4초 초과로 컨트롤러가 abort된 경우에만 outer catch로 재던져 offline('Offline')으로 정직하게 표출하도록 정합함.
  - 단위 시험 H3(바디 행 시 4초 만료 후 Offline 전환), H3b(비정상 JSON 바디 degraded 유지 및 정상 복구), H4(fetch 행 시 Offline 전환), H5(상태 전이 순서) 검증 완료.

### 4) UI-R2-L3 (Low): 표면적 시험의 실제 DOM 인터랙션 격상
- **조치 내용**:
  - P8: 단순 spy 미호출 단언에서 벗어나, `approvalsState === 'error'` 상태에서 실제 안건 클릭, 반려 버튼 클릭, 확인 모달 '반려 확인' 클릭까지 완전한 사용자 인터랙션을 실행하고 `decideApproval` API가 절대 호출되지 않음(0 calls)을 실측함. `ApprovalDetail` 재던짐 unhandledRejection 핸들러를 테스트 하니스에 장착하여 안전하게 검증함.
  - R8c (대조군): 정상 상태에서 동일한 전체 클릭 플로우를 거칠 때 `decideApproval`이 정확히 1회 호출됨을 대조 실측함.
  - R9: 자원 탐색기 Fabric 탭에서 `nodes-retry-btn` 클릭 시 에러 배너가 즉시 제거되고 `nodes-loading-state`에 진입함을 실측함.

### 5) 린트 결함 정정 (b48c2c44)
- 1차 소스 커밋 `9cd017ab`의 Hosted Frontend CI에서 발생한 ESLint `@typescript-eslint/no-unused-vars`(`App.tsx:487` `fetchApprovals` catch의 미사용 `err`) 지적에 대해, Root 지침에 따라 바인딩을 생략한 `catch {` 형태로 최소 1줄 정정을 적용하여 커밋 `b48c2c44`를 확정함.

---

## 3. 시험 및 가드 변이 검증 실측

### 1) 시험 귀속 및 범위 고지
- `apps/web/tests/portal-refresh-fleet-ui.test.tsx` 내의 R1, R1b, R2, R2b, R6, R8, R8c, R9, H3, H3b, H4, H5, T1 시험은 진단용 리뷰어 형상을 작성자 하니스에 이식한 **작성자 자체 시험(OWNER reproduction)**임. 실제 독립 Claude 소스 검토는 불변 `b48c2c44`에 대해 `SOURCE_AXIS_ACCEPT:626ab0eda10c22e8539546db8d9639092d88f7e7`로 완료됨 (정적 리뷰 및 Root 실측 CI/가드 증빙 기반, 6 INFO 한계 유지).
- T1 시험은 모의 fetch 환경 하에서 실제 클라이언트 래퍼 계약 및 시그널 전달을 검증하는 시험이며, 실제 물리적 네트워크, 브라우저, SSO, TLS 환경 검증이 아님.

### 2) 가드 변이(Guard Mutant) 검증 실측 (ROOT OPERATOR 대행 실행)
- **증빙 영수증**: `D:/Project/SaintVisionI-Invion/fleet-five-orchestration-20261105/.work/uir3-pc3-guard-root-proof.json` (SHA256: `98f6949affbaac61186e32732e228d699738a3c6129e58a0a9e8a08dbd953ac7`).
- **실행 환경**: 물리 PC3, Git `b48c2c44` 독립 비공개 소스 export 환경, 고정 `node@sha256:01d566e8...` / Node v24.22.2, 격리 컨테이너 (2 CPU, memory 2 GiB, memory+swap TOTAL 2 GiB [extra swap 0; dockerMemoryBytes 2147483648, dockerMemorySwapBytes 2147483648], pids 128, read-only rootfs, cap-drop ALL, no-new-privileges, UID 1000, network NONE). 직접 cgroup 측정은 dependency 컨테이너 대상이며 모든 테스트 HostConfig를 개별 점검함.
- **시험 대상**: `apps/web/tests/portal-refresh-fleet-ui.test.tsx` 46개 실제-App 시험군 (단일 워커 직렬 실행 3회).
- **실측 결과**:
  1. `control_baseline` (변이 없음): **46 PASS / 0 FAIL (exit 0)**
  2. `MD_noApprovalsErrorGuard` (`App.tsx` 내 `approvalsState === 'error'` 가드 2개소 제거): **45 PASS / 1 expected FAIL (exit 1)**
     - 실패 시험: **R8** (가드 제거로 인해 에러 상태에서 `decideApproval`이 호출되어 단언 실패).
     - 대조군: R8c 정상 클릭 단언은 양호하게 통과하여 인과적 탐지 확인.
  3. `ME_L3EventAsBackground` (이벤트 객체를 background 인자로 전달하는 회귀 복원): **45 PASS / 1 expected FAIL (exit 1)**
     - 실패 시험: **R9** (포그라운드 재시도 시 loading 상태 진입 실패로 단언 실패).
     - 대조군: R8c 정상 클릭 단언은 양호하게 통과하여 인과적 탐지 확인.
- **입력 폐포 무결성**: 281개 apps/web + 165개 contracts 파일의 복원 후 해시 전수 일치 확인 (저장소 원본 변형 0건).
- **미실행 초안 보존**: 작성자가 최초 작성한 `tools/run_uir3_mutants.py` 초안은 미실행 상태로 안전하게 `.work/run_uir3_mutants.py.draft`로 격리 보존함.

---

## 4. 검증 실측 기록

### 1) 로컬 검증
- **로컬 검증 귀속 및 한계 고지 (localVerificationAttribution)**: 아래 로컬 CLI 실행 결과는 작성자 자체 관측 기록(OWNER_REPORTED_EARLIER)이며, 모든 초기 항목에 대해 완전한 source/WIP/KST/raw-log 결속이 제공되지는 않고 Root가 개별 항목을 독립 검증한 것은 아님. 불변 동결 소스 `b48c2c44`의 정식 게이트는 호스팅 CI 1,264건 통과 및 Root PC3 3회 직렬 가드 변이 검증임.
- **단위 시험 (Vitest)**:
  - `cd apps/web; npx vitest run tests/portal-refresh-fleet-ui.test.tsx`: **46/46 passed** (exit 0, 835ms/980ms)
  - `cd apps/web; npx vitest run tests/acc09-contrast-tokens.test.tsx`: **46/46 passed** (exit 0, 2121ms)
- **타입 검사 (Non-writing TypeScript checks)**:
  - `cd apps/web; node node_modules/typescript/bin/tsc -p tsconfig.app.json --noEmit`: exit 0
  - `cd apps/web; node node_modules/typescript/bin/tsc -p tsconfig.node.json --noEmit`: exit 0
- **프로덕션 번들 빌드 (Vite)**:
  - `cd apps/web; node node_modules/vite/bin/vite.js build`: exit 0 (`dist/assets/index-DEIKEmX_.js` 1,299.68 kB 번들 정상 생성)
- **게이트 검사 (Python)**:
  - `python tools/check_frontend_integrity.py`: PASS (9개 규칙 0건 위반, exit 0)
  - `python tools/check_contract_bindings.py`: PASS (57 fixtures, 21 bound response types, 14 replay guards, exit 0)
  - `pytest tests/test_route_coverage.py`: PASS (41 passed, exit 0, 1.43s)
  - `python tools/check_docs.py`: PASS (24 original hashes, 1262 versioned documents, exit 0)
  - `python tools/sync_obsidian.py --check --state "D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json"`: CHECK (2829 managed files, 0 conflicts, 상태 해시 `6367D282E9029B1BFC531D4145A4FB4890A010481E48EEE0E66ED2B7540FFEDD` 전후 불변 실측, exit 0)
- **로컬 린트 환경 상태**:
  - `apps/web/node_modules/eslint/bin/eslint.js`가 공유 정션에 존재하지 않아 로컬 린트는 `NOT_RUN_ENVIRONMENT_missing_shared_eslint`로 기록함 (exit 1, `MODULE_NOT_FOUND`). 정식 린트는 호스팅 CI 환경에서 완벽히 통과함.

### 2) 원격 CI 검증 (Root Operator 대행 실행)
- **1차 소스 `9cd017ab`**:
  - Frontend Run `42247974625`: failure (frontend job 127995132127 ESLint unused catch err 실패, container job 127995132761 성공)
- **정정 소스 `b48c2c44`**:
  - Frontend Run `42254157322` (workflow_dispatch, attempt 1): **SUCCESS**
  - Job `128016761183` (frontend, 12 steps): **SUCCESS** (Full ESLint, Vitest 103 test files/1264 tests passed, API contract check, TypeScript build, Artifact upload 전 스텝 통과)
  - Job `128016761717` (hardened-container, 14 steps): **SUCCESS**
  - 산출물:
    - `saintvision-web-dist`: ID `13520599988` (1,119,300 bytes, `sha256:7212b4870e3a142b8c44dc2629d5e6643401ae9e1d187d6234ecdf4059fd671d`) — Root가 직접 다운로드하여 13개 압축 파일 및 ZIP 해시 완벽 일치 실측 완료.
    - `container-release`: ID `13521388864` (25,985,266 bytes, `sha256:09e3b81e4034bcdbfff46eae89af6e34ffe0aac59382a95a10fe127f1e1baa3f`)

---

## 5. 소스 범위 및 불변식 준수

- **수정 허용 파일 3건 엄수**:
  - `apps/web/src/app/App.tsx`
  - `apps/web/src/shared/ui/Header.tsx`
  - `apps/web/tests/portal-refresh-fleet-ui.test.tsx`
- **비문서 바이트 동등성**:
  - 최종 리포트 패킷 커밋 시 비문서(Non-Docs) 파일 바이트는 소스 커밋 `b48c2c4492f8aea4b55c33161733a9a6fb9eed8c`와 100% 동일함 (`git diff b48c2c44 -- . ':!docs'` 결과 clean).
- **운영/배포 경계 준수**:
  - 라이브 서비스(3100, 8080, 8443, r5) 무접촉 유지.
  - 가상 데이터 조작(5/5 조작 금지, 실제 0대 빈 스냅샷 정직 반영) 100% 준수.
  - 독립 소스 검토 판정(`SOURCE_AXIS_ACCEPT:626ab0eda10c22e8539546db8d9639092d88f7e7`)은 소스 축에 한정되며, 전체 프로그램 인수, 프로덕션 배포, 5-PC 하드웨어 제공을 주장하지 않음. 실제 배포는 최종 리포트 Docs/동등성/배포 게이트에 대한 Root 운영 승인 후 수행됨.
