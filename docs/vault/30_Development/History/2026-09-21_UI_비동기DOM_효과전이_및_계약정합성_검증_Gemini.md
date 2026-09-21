---
doc_id: "UI-EFFECT-DOM-REPORT-20260921-GEMINI"
title: "UI 비동기 DOM 효과 전이 검증 하네스 및 백엔드 계약 정합성 완결 보고"
version: "1.0.0"
status: "review"
author: "Gemini"
reviewer: "Codex"
base_commit: "47c9f73"
updated: "2026-09-21T11:30:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["UI-DOM", "happy-dom", "frontend", "verification-boundary", "mock-contract", "history"]
---

# UI 비동기 DOM 효과 전이 검증 하네스 및 백엔드 계약 정합성 완결 보고

## 1. 개요 및 배경

- **목적**:
  1. **비동기 DOM 효과 전이 검증 (`useEffect` 실행 누락 해소)**: Claude의 독립 검토([[2026-09-21_UI_static_markup감사_Claude독립검토]])에서 증명된 바와 같이, SSR `renderToStaticMarkup` 기반 테스트는 `useEffect`를 실행하지 않아 `setCandidates([])` 변형 회귀(후보 버림 버그)를 전혀 잡아내지 못하는 한계를 지니고 있었다.
  2. **브라우저 하네스 확장 (Gap a)**: `apps/web/tests/browser/desktop.tsx`가 기존에 `files`와 `model` 뷰만 마운트하고 `ResourceExplorer`를 배제하던 문제를 해결하여 브라우저 레인에서 패브릭 컴포넌트를 마운트할 수 있도록 확장했다.
  3. **Mock-계약 정합성 격차 해소 (Gap b)**: 프론트엔드 모의 데이터와 백엔드 원천 스키마(`src/saintvision/services/discovery.py`, `src/saintvision/api/v1/pools.py`) 간 1:1 일치를 보장하고, 양방향 계약 불변식 테스트를 Python 회귀 스위트에 영구 편입했다.
- **배정 Owner**: Gemini (디자인 / Frontend / 웹 배포)
- **독립 Reviewer**: Codex

---

## 2. 작업 내용 상세

### 2.1 DOM 환경 하네스 도입 및 비동기 상태 전이 테스트 구축 (`apps/web/tests/resource-explorer-dom.test.tsx`)
- `happy-dom` 패키지를 설치하여 Vitest 환경에서 실제 DOM 렌더링 및 `useEffect` 비동기 효과 실행 환경을 활성화했다 (`IS_REACT_ACT_ENVIRONMENT = true`).
- `createRoot`와 React `act()` 비동기 전이 추적기를 사용하여 지연된 Promise(`deferred()`)를 통해 5가지 핵심 수명주기 전이를 실제 DOM 관측으로 입증했다:
  1. **Pending 전이**: `loadDiscoveryCandidates()` 비동기 호출 중 `discovery-loading` 인디케이터 렌더링 확인, 유령 센티널 노드 및 어드미션 버튼 완전 부재 단언.
  2. **Success-with-data 전이 (`setCandidates([])` 변형 방어)**: 어댑터 응답 도착 시 `Node-99-LiveDiscovered`, `192.168.1.199`, `ann_live_99`가 DOM에 실제 렌더링되고 어드미션 제어 버튼이 활성화됨을 확인. Claude가 제기한 `setCandidates([])` 변형 주입 시 즉시 FAIL로 포착됨을 보증.
  3. **Success-empty 전이**: 빈 목록(`items: []`) 응답 시 `discovery-empty-state`가 표시되고 불필요한 액션 버튼이 비활성화됨을 확인.
  4. **Error 전이**: API 500/503 에러 발생 시 `discovery-error-banner`가 표출되고 모든 후보 카드 및 mutation 버튼이 즉각 차단됨을 확인.
  5. **Storage Error 전이**: 스토리지 API 오류 시 `storage-error-banner`가 표출되고 정상적인 빈 목록으로 오인되지 않음을 확인.

### 2.2 브라우저 하네스 확장 (`apps/web/tests/browser/desktop.tsx`)
- `DesktopBrowserView` 타입에 `'fabric' | 'resource'`를 추가.
- `(window as any).mountDesktopTest` 진입점에서 `input.view === 'fabric' || input.view === 'resource'` 분기를 추가하여 `<ResourceExplorer nodes={[]} initialTab={input.initialTab || 'discovery'} />`를 마운트할 수 있도록 확장.
- TypeScript 컴파일(`tsc -b`) 및 Vite 프로덕션 빌드 통과 확인.

### 2.3 백엔드-프론트엔드 모의 스키마 계약 불변식 수립 (`tests/test_route_coverage.py` & `fabricControlApi.ts`)
- 백엔드 `src/saintvision/services/discovery.py:list_candidates`의 반환 필드:
  - `announcementId`, `instanceId`, `sourceIp`, `claimedHostname`, `claimedOsType`, `claimedCpuCores`, `claimedRamBytes`, `claimedGpuCount`, `firstSeenAt`, `lastSeenAt`, `announceCount`, `stale`, `verified` (항상 `False`)
- 프론트엔드 `fabricControlApi.ts`의 `DiscoveryCandidate` 인터페이스에 누락되어 있던 `stale?: boolean`을 추가하여 백엔드 스키마와 완전 일치시킴.
- 프론트엔드 모의 데이터(`fabric-control-plane.test.tsx`, `resource-explorer-dom.test.tsx`)에 `instanceId`, `announceCount`, `stale`을 포함시켜 임의 모의 형태 제거.
- `tests/test_route_coverage.py`에 `test_discovery_candidate_schema_contract_invariants()` 함수를 추가하여:
  - 백엔드 딕셔너리 필수 키 13개 검증
  - 백엔드 `verified: False` 하드코딩 불변식 검증
  - `/v1/discovery/candidates` 엔드포인트의 미검증 주의 문구 포함 여부 검증
  - 프론트엔드 인터페이스 필수 필드 매핑 검증

---

## 3. 검증 결과 및 증거 (Evidence)

| 검증 항목 | 실행 명령 | 결과 | 상세 비고 |
| :--- | :--- | :--- | :--- |
| **비동기 DOM 테스트** | `npm --prefix apps/web test -- tests/resource-explorer-dom.test.tsx` | **PASS** (5/5 tests passed) | `act()` 비동기 전이 완전 포착, 0 warnings |
| **프론트엔드 전체 단위/컴포넌트** | `npm --prefix apps/web test -- --run` | **PASS** (33/33 files, 327 passed) | 0 failures |
| **프론트엔드 번들 빌드** | `npm --prefix apps/web run build` | **PASS** (exit code 0) | `tsc -b && vite build` 3.32s 완료 |
| **라우트 및 계약 불변식 테스트** | `.venv\Scripts\pytest.exe tests/test_route_coverage.py` | **PASS** (29/29 passed) | 신규 스키마 계약 불변식 포함 |
| **인트라넷 배포 사전검사 테스트** | `.venv\Scripts\pytest.exe tests/test_deploy_intranet_preflight.py` | **PASS** (17/17 passed) | 20.32s 통과 |
| **문서 무결성 검증** | `.venv\Scripts\python.exe tools/check_docs.py` | **PASS** | 24 hashes, 589 docs, 48 tasks |
| **온톨로지 정합성 검증** | `.venv\Scripts\python.exe tools/check_ontology.py` | **PASS** | RDF, SHACL, 4 queries pass |

---

## 4. 인계 및 다음 단계

- **작업한 것**:
  1. `apps/web/tests/resource-explorer-dom.test.tsx` 신설 (DOM 환경에서 4-상태 전이 및 `setCandidates([])` 돌연변이 회귀 완벽 방어).
  2. `apps/web/tests/browser/desktop.tsx`에 `fabric`/`resource` 뷰 마운트 지원 추가.
  3. `apps/web/src/features/desktop/fabricControlApi.ts`의 `DiscoveryCandidate`에 `stale` 필드 보강 및 모의 데이터 스키마 1:1 일치.
  4. `tests/test_route_coverage.py`에 `test_discovery_candidate_schema_contract_invariants` 영구 불변식 추가.
- **확인한 것**:
  - Vitest 33개 파일 327개 테스트 통과, Pytest 46개 테스트 통과, `check_docs` 및 `check_ontology` 통과, 프론트엔드 빌드 통과.
- **다음 담당 및 첫 행동**:
  - **Codex**: UI 비동기 DOM 전이 하네스 및 스키마 계약 불변식 독립 경계 검토.
  - **Gemini**: 이어서 VF-GM 잔여 카드 및 외부 HTTPS 브라우저 인수 준비.
