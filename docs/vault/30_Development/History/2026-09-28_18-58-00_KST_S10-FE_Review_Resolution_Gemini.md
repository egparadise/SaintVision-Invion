---
doc_id: "HIST-GEMINI-S10-FE-REVIEW-001"
title: "S10-FE 어댑터 conformance 관측 화면 Claude UI 및 Codex 계약 리뷰 전수 조치 (F1~F7, F-R1)"
version: "1.0.0"
status: "active"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-28T18:58:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-FE", "G-03"]
tags: ["s10-fe", "g-03", "conformance", "adapter", "ui", "review-resolution", "claude-f1-f7", "codex-f-r1", "gemini"]
---

# S10-FE 어댑터 conformance 관측 화면 Claude UI 및 Codex 계약 리뷰 전수 조치 (F1~F7, F-R1)

## 1. 개요

PR #208 (head `0d440a8b`)에 대해 접수된 Codex 계약 축(F-R1) 및 Claude UI·시험 축(F1~F7, 변이 M1~M10)의 모든 리뷰 결함 사항을 전수 분석하고 완결 조치하였다.

## 2. 결함 조치 상세 내역

### 2.1 Codex F-R1 & Claude F1 (High): 생성 계약 타입 결속 및 손편집 완전 제거
- **원인**: `packages/contracts-ts/src/index.ts`에 `ConformanceCheckDescriptor`와 `ConformanceStatusResponse`를 수작업으로 추가하고 `apps/web/src/contracts/types.ts`를 통해 re-export하여 사용함으로써, `core.yml`의 `generate_contracts.py` drift 검사 실패 위험 및 타입 결속 단절 가능성이 존재함.
- **조치**:
  - `packages/contracts-ts/src/index.ts`의 수작업 추가 15줄을 base 커밋(`18a59027`) 상태로 온전히 되돌림.
  - `apps/web/src/contracts/types.ts`의 수작업 re-export를 완전 제거.
  - `apps/web/src/shared/api/adapterObservation.ts`와 `apps/web/src/features/mlops/ModelLineageView.tsx`가 생성 모듈 `@/contracts/conformance-status-response`를 직접 import하도록 교체.
  - `model-lineage.test.ts`에 생성 타입 결속 회귀 시험 추가.
  - 닫힘 검증: `git grep -n "ConformanceStatusResponse" -- packages/contracts-ts apps/web/src/contracts/types.ts` 결과 0건, `npm run contracts:check` PASS (17 API response types match schemas).

### 2.2 Claude F2 (Medium-High): PR #200 백엔드 실 응답 정합 및 허위 오류 코드 전면 제거
- **원인**: 테스트 fixture가 실제 백엔드 응답 규격과 불일치(401에 403 코드 `AUTH-0030`, 403에 미존재 `AUTH-0001`, 404에 미존재 `RES-0004` 및 가짜 문구 '프로젝트를 찾을 수 없습니다' 사용, 임의의 체크리스트명 및 대소문자 미구분 PASS 단언).
- **조치**:
  - 403: 실제 RFC 9457 정본(`type: "about:blank"`, `title = code = "AUTH-0030"`, `detail: "This project is not accessible."`) fixture 적용.
  - 401: 실제 InvError 레거시 형태(`type: "https://saintvision.invenio/problems/auth-missing-credential"`, `code: "AUTH-MISSING-CREDENTIAL"`, `detail: "a bearer credential is required"`) 및 FE `client.ts`의 `[NET-0401] (401) Request rejected: a bearer credential is required` 폴백 표출 검증.
  - 404: 미존재 `RES-0004` 및 가짜 문구를 코드/테스트/문서에서 전면 제거. 라우트 미배포 폴백(`NET-0404` / 404 / "Not Found")만 정직하게 검증.
  - 체크리스트 Fixture: `adapters/conformance.py:357-389`의 `CHECKLIST` 정본 15개 명칭(`declares_contract_version` ~ `declared_model_pinning_returns_an_id`), 정본 게이팅(12 Standard / 3 Gated), 실제 어댑터 4종, 실제 reason 문자열로 전면 교체.
  - 대소문자 무관 `/pass/i` 거부 단언 적용.
  - 닫힘 검증: `git grep -n -E "AUTH-0001|RES-0004|프로젝트를 찾을 수 없습니다" apps/web/tests/model-lineage.test.ts` 결과 0건.

### 2.3 Claude F3 (Medium): 500, 네트워크, 502 HTML 프록시 에러 및 성공→403 전이 시험 (M8 변이 사살)
- **원인**: 500, fetch reject(TypeError), 502 HTML 프록시 에러, 성공 후 403 전이 시 stale 데이터 잔존(변이 M8)에 대한 시험 부재.
- **조치**:
  - (a) 성공 → 403 전이 시험 추가: A 프로젝트 성공 후 B 프로젝트가 403 수신 시 이전 체크리스트 컨테이너가 DOM에서 완전히 격리(null)됨을 단언하여 변이 M8(`setConformanceData(null)` 삭제)을 사살.
  - (b) 네트워크 단절(`TypeError: Failed to fetch`) 시험 추가.
  - (c) 정본 500(`SYS-0002`) 시험 추가.
  - (d) 502 HTML 프록시 에러 시험 추가: `ModelLineageView.tsx`에서 비JSON/HTML 마크업 및 5xx NET 에러 수신 시 안전한 한국어 문구(`서버 또는 게이트웨이 오류가 발생했습니다. (잠시 후 다시 시도해 주세요)`)로 변환하여 HTML 마크업 누출을 0건으로 차단.

### 2.4 Claude F4 (Low-Medium): 하드코딩 개수 "15개" 표기 전면 제거
- **조치**:
  - `ModelLineageView.tsx` 소제목(`...정본 체크리스트 규격을 반환합니다`) 및 미측정 안내문(`...체크리스트 규격을 확인하십시오`)에서 하드코딩 "15개" 제거.
  - 동적 체크리스트 테스트에서 패널 `textContent`에 "15개"가 포함되지 않음을 명시적 단언.

### 2.5 Claude F5 (Low): Standard 배지 색상 상향 및 DOM 스타일 직접 실측 대비 계산
- **조치**:
  - Standard 배지 텍스트 색상을 `#8b949e`에서 `#a0a8b2`로 상향하여 `#161b22` 위 15% 알파 블렌딩 배경 대비 5.52:1의 넉넉한 WCAG AA 대비율 확보.
  - `model-lineage.test.ts` 대비율 시험을 상수 계산이 아닌 렌더된 DOM 엘리먼트의 `style.color`와 `backgroundColor`를 직접 읽어 sRGB 상대휘도 및 알파 합성 대비율을 실측 계산하도록 전환.
  - Standard 배지(>= 5.0:1), Gated 배지(>= 4.5:1), Status 배지(>= 4.5:1) 모두 WCAG AA 기준을 상회 통과.

### 2.6 Claude F6 (Low): 문구 정직성 정비 (미수신 literal 배제 및 간결화)
- **조치**:
  - 조회 전: `미측정 (미조회)`, 서브텍스트 `실제 conformance API (G-03 1단계) 연동 대기`.
  - 오류 시: `조회 실패`, 서브텍스트 `어댑터 conformance 조회 실패`.
  - 성공 알림: `조회 완료: 미측정(NOT_OBSERVED)`.
  - 에러 라이브 알림: `❌ 어댑터 Conformance 조회 실패`로 간결화하여 alert 배너와의 중복 낭독 방지.

### 2.7 Claude F7 (Low): 미사용 `initialConformance` prop 및 마운트 `useEffect` 제거
- **조치**:
  - `ModelLineageViewProps`에서 미사용 `initialConformance` 제거.
  - 취소 불가능하고 가드를 우회할 수 있는 마운트 `useEffect` 전면 제거.
  - 모든 API 호출이 명시적이고 취소 가능한 사용자 액션 및 적절한 로딩/상태 가드를 통해 실행되도록 보장.

### 2.8 변이 사살 (M1~M10)
- M6: `isConformanceCheckDescriptor`에 `passed: true` 임의 필드가 포함된 부정 fixture 주입 시 거부 검증으로 사살.
- M8: 성공 후 403 전이 시 stale 데이터 제거 시험으로 사살.
- M9: 네트워크/HTML 에러 시 마크업 누출 차단 및 고정 문구 매핑 시험으로 사살.
- M10: DOM 스타일 직접 실측 대비 시험으로 사살.
- 부가 개선: 체크리스트 테이블 a11y(`<caption>`, `th scope="col"`) 및 고유 key(`${idx}-${check.name}`) 적용.

## 3. 검증 결과

| 검증 항목 | 실행 명령 | 결과 | 비고 |
|---|---|---|---|
| Model Lineage Tests | `npm test -- model-lineage` | **PASS (23 tests passed)** | 결속, 401/403/404, M8/M9/M10 변이 사살 전수 통과 |
| Vitest Full Suite | `npm test` | **PASS (78 files, 707 passed)** | 회귀 없음 (+3 tests 추가) |
| Contract Types Check | `npm run contracts:check` | **PASS** | 17 API response types match schemas |
| TypeScript Typecheck | `npx tsc -b` | **PASS** | 타입 에러 0건 |
| Production Build | `npm run build` | **PASS** | 806.38 kB 번들 생성 성공 |
| Route Coverage | `pytest tests/test_route_coverage.py` | **PASS (40 passed)** | 불변식 및 라우트 검증 통과 |
| Frontend Integrity | `python tools/check_frontend_integrity.py` | **PASS** | 9대 무결성 규칙 위반 0건 |
| Contract Bindings | `python tools/check_contract_bindings.py` | **PASS** | 55 fixtures, 20 bound types, 14 replay guards |
| Documentation Integrity | `python tools/check_docs.py` | **PASS** | 911 versioned docs, DAG 무결성 |
| Obsidian Sync Check | `python tools/sync_obsidian.py --check` | **PASS** | 0 conflicts |
