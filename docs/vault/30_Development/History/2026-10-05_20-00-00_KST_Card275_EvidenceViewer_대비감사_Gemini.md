---
doc_id: "HIST-20261005-CARD275-GEMINI"
title: "Card 275 EvidenceViewer 화면 색상 리터럴 전수 토큰화, 증거 상태 계약 무결성 및 접근성 승격"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-05T20:00:00+09:00"
updated: "2026-10-05T20:25:00+09:00"
source_of_truth: "Git"
---

# Card 275 EvidenceViewer 화면 색상 리터럴 전수 토큰화, 증거 상태 계약 무결성 및 접근성 승격

## 1. 작업 개요
- **목표**: ACC-09 불변 증거 뷰어(`apps/web/src/features/evidence/EvidenceViewer.tsx`)의 색상 리터럴 16건 전수(16건→0건) 토큰화 및 디자인 토큰 체계 승격:
  1. `apps/web/src/features/evidence/EvidenceViewer.tsx`: 베이스(`17da19c5`)에 잔존하던 16건의 색상 리터럴(`#10b981`, `#d97706` 3건, `#f87171`, `rgba(16,185,129,0.15)`, `rgba(234,179,8,0.08)`, `rgba(234,179,8,0.15)`, `rgba(234,179,8,0.3)`, `rgba(248,81,73,0.08)`, `rgba(248,81,73,0.1)` 2건, `rgba(248,81,73,0.15)` 2건, `rgba(248,81,73,0.3)`, `rgba(56,139,253,0.15)`)을 전수 제거하고 디자인 토큰 체계로 100% 승격.
  2. **정본 계약 타입 바인딩 및 불변식 보장**:
     - `apps/web/src/contracts/types.ts`에 `INTEGRITY_VERIFICATION_STATUSES = ['PASS', 'FAIL', 'UNVERIFIED', 'RUN_FAILED'] as const` 및 `IntegrityVerificationStatus` 타입을 엄밀 정의 및 export.
     - `EVIDENCE_INTEGRITY_CONFIG` 설정 객체를 `as const satisfies Record<IntegrityVerificationStatus, EvidenceIntegrityConfigItem>`으로 결속하여 계약 외 상태 누락 및 타입 불일치를 컴파일 시점에 fail-closed로 차단.
     - `getEvidenceIntegrityConfig(status: unknown)` 헬퍼에 `Object.hasOwn` 방어를 적용하여 prototype 프로퍼티 주입 공격(`toString`, `constructor`, `__proto__`, `valueOf`) 및 비정상/미확인 상태를 `미확인 무결성 상태 (UNKNOWN: <raw>)`(`var(--color-status-unknown)`, `var(--color-bg-subtle)`)로 안전하게 강등.
  3. **AST 정적 분석기 래칫 및 검증 테이블 바인딩**:
     - `apps/web/tests/acc09-contrast-tokens.test.tsx`의 `checkConfigTables`에 `EVIDENCE_INTEGRITY_CONFIG` 및 `borderVar`를 결속하여 배경/전경 및 배경/테두리 명도 대비 수치를 AST 레벨에서 전수 계산 및 검증.
     - Test 9j-2 `analyzeFile` 스위트에 `features/evidence/EvidenceViewer.tsx`를 등록하고 엄밀 통계 래칫 고정:
       - `totalStyleAttrs: 31`, `checkedObjects: 11`, `checkedPairs: 15`, `unboundColorObjects: 4`, `coveredColorObjects: 15`, `checkedBorderObjects: 12`, `checkedBorderPairs: 12`, `violations: 0`.
  4. **Multiset Baseline 래칫 강제**:
     - `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/evidence/EvidenceViewer.tsx` 허용 인벤토리를 `{}` (0건)으로 전면 래칫 고정.
  5. **DOM 결속 및 Revert-Fail Probes**:
     - Test 9y 신설: PASS, FAIL, RUN_FAILED, UNVERIFIED 4종 상태 배지, SEALED 배지, 알림 배너 3종, 에러 알림 배너, 클립보드 복사 피드백의 DOM 렌더링 및 토큰 바인딩 단언.
     - Revert-Fail Probes 131~135 신설: 베이스의 결함 조합(#d97706 2.90:1, #f87171 2.51:1, PASS border 1.16:1, UNVERIFIED border 1.22:1, copy feedback #10b981 2.54:1)이 WCAG AA 기준을 엄밀히 탈락함을 증명.
  6. **40종 전수 변이 실측 사살 (Receipt A/B)**:
     - `tools/test_c275_mutations.py` W1~W40 40/40 100% 사살 실측 (timeout=120초, 각 변이 후 바이트 일치 복원 확인, 결과 메타데이터 봉인).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스 `17da19c5`의 실제 코드 실측값(라이트 캔버스 `#f8fafc` 위 카드 서피스 `#ffffff`, 서브틀 배경 `#f1f5f9` 및 다크 캔버스 `#090d16` 위 `#111827`, `#1f2937`)을 기준으로 측정되었습니다. 알파 합성은 저장소 정본 모델인 `blendRgba`(sRGB 채널 반올림 표준 공식 `round(alpha * fg + (1 - alpha) * bg)`) 및 실제 조상 underlay를 적용하여 산출하였습니다. 베이스 `17da19c5`에 존재하던 16건의 색상 리터럴이 전수 제거되어 0건으로 정착되었습니다. After 값은 `python tools/reproduce_c275_contrast.py` 실행 결과(21개 전 항목)와 100% 일치합니다.

각 지표의 배경 산출 근거 줄 번호 (베이스 `17da19c5` 기준):
- L109 루트 컨테이너 `<div>`: 캔버스 배경 `var(--color-bg-canvas)` (`#f8fafc` Light / `#090d16` Dark).
- L130 에러 메시지 알림 배너: 조상 캔버스(L109) 위에 렌더링.
- L151 메인 카드 컨테이너: 서피스 배경 `var(--color-bg-surface)` (`#ffffff` Light / `#111827` Dark).
- L173/L189/L205/L221 동적 무결성 배지(PASS/FAIL/RUN_FAILED/UNVERIFIED): 조상 서피스(L151) 위에서 서브틀 배경 `var(--color-bg-subtle)` (`#f1f5f9` Light / `#1f2937` Dark) 적용.
- L222/L223 UNVERIFIED 배지 텍스트/테두리: 배지 자체 배경(베이스 `rgba(234,179,8,0.15)` over surface → 개정 `var(--color-bg-subtle)`) 위에서 렌더링.
- L236 SEALED 배지: 조상 서피스(L151) 위에서 서브틀 배경 `var(--color-bg-subtle)` 적용.
- L248 복사 완료 메시지: 조상 서피스(L151) 위에서 렌더링.
- L275/L277/L279 RUN_FAILED 안내 배너: 조상 서피스(L151) 위에서 `var(--color-risk-l3-bg)` 및 `var(--color-risk-l3-border)` 적용.
- L301 FAIL 안내 배너: 조상 서피스(L151) 위에서 `var(--color-risk-l3-bg)` 및 `var(--color-risk-l3-border)` 적용.
- L326/L328/L330 UNVERIFIED 안내 배너: 조상 서피스(L151) 위에서 `var(--color-bg-subtle)` 및 `var(--color-status-unknown)` 적용.

| ID | UI 요소 | 위치 (코드 줄) | 조상 Underlay | Before 베이스 합성값 (Hex/RGBA on Underlay) | Before 명도비 (Light / Dark) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light) | After 명도비 (Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| IT01 | 에러 배너 배경 | EvidenceViewer.tsx:130 | Canvas L109 | rgba(248,81,73,0.10) on Canvas (#fef0f0 / #21151c) | 1.13:1 (INFO) / 1.09:1 (INFO) | var(--color-risk-l3-bg) on Canvas | 1.17:1 | 1.19:1 | UI 경계 | PASS |
| IT02 | PASS 배지 배경 | EvidenceViewer.tsx:173 | Surface L151 | rgba(16,185,129,0.15) on Surface (#dbf4ec / #113034) | 1.16:1 (INFO) / 1.26:1 (INFO) | var(--color-bg-subtle) on Surface | 1.10:1 | 1.21:1 | UI 경계 | PASS |
| IT03 | FAIL 배지 배경 | EvidenceViewer.tsx:189 | Surface L151 | rgba(248,81,73,0.15) on Surface (#fee5e4 / #2a1920) | 1.20:1 (INFO) / 1.18:1 (INFO) | var(--color-bg-subtle) on Surface | 1.10:1 | 1.21:1 | UI 경계 | PASS |
| IT04 | RUN_FAILED 배지 배경 | EvidenceViewer.tsx:205 | Surface L151 | rgba(248,81,73,0.15) on Surface (#fee5e4 / #2a1920) | 1.20:1 (INFO) / 1.18:1 (INFO) | var(--color-bg-subtle) on Surface | 1.10:1 | 1.21:1 | UI 경계 | PASS |
| IT05 | UNVERIFIED 배지 배경 | EvidenceViewer.tsx:221 | Surface L151 | rgba(234,179,8,0.15) on Surface (#fcf4da / #322f22) | 1.10:1 (INFO) / 1.32:1 (INFO) | var(--color-bg-subtle) on Surface | 1.10:1 | 1.21:1 | UI 경계 | PASS |
| IT06 | UNVERIFIED 배지 텍스트 | EvidenceViewer.tsx:222 | Badge bg L221 | #d97706 on rgba(234,179,8,0.15) composite (#fcf4da / #322f22) | 2.90:1 (FAIL) / 4.21:1 (FAIL) | var(--color-status-unknown) on subtle | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |
| IT07 | UNVERIFIED 배지 테두리 | EvidenceViewer.tsx:223 | Badge bg L221 | #d97706 on Surface/Badge composite | 3.19:1 (PASS) / 5.57:1 (PASS) | var(--color-status-unknown) on subtle | 6.47:1 | 5.82:1 | >= 3.0:1 | PASS |
| IT08 | SEALED 배지 배경 | EvidenceViewer.tsx:236 | Surface L151 | rgba(56,139,253,0.15) on Surface (#e1effe / #162643) | 1.17:1 (INFO) / 1.22:1 (INFO) | var(--color-bg-subtle) on Surface | 1.10:1 | 1.21:1 | UI 경계 | PASS |
| IT09 | 복사 완료 안내 텍스트 | EvidenceViewer.tsx:248 | Surface L151 | #10b981 on Surface (#ffffff / #111827) | 2.54:1 (FAIL) / 6.99:1 (PASS) | var(--color-brand-success) on Surface | 5.02:1 | 7.79:1 | >= 4.5:1 | PASS |
| IT10 | RUN_FAILED 안내 배경 | EvidenceViewer.tsx:275 | Surface L151 | rgba(248,81,73,0.08) on Surface (#fef2f1 / #241920) | 1.10:1 (INFO) / 1.08:1 (INFO) | var(--color-risk-l3-bg) on Surface | 1.22:1 | 1.09:1 | UI 경계 | PASS |
| IT11 | RUN_FAILED 안내 테두리 | EvidenceViewer.tsx:277 | Surface L151 | rgba(248,81,73,0.30) on Surface (#fdcdca / #491f28) | 1.44:1 (FAIL) / 1.48:1 (FAIL) | var(--color-risk-l3-border) on Surface | 6.47:1 | 6.41:1 | >= 3.0:1 | PASS |
| IT12 | RUN_FAILED 안내 텍스트 | EvidenceViewer.tsx:279 | Notice bg L275 | #f87171 on rgba(248,81,73,0.08) composite (#fef2f1 / #241920) | 2.51:1 (FAIL) / 5.93:1 (PASS) | var(--color-risk-l3-text) on risk-l3-bg | 6.80:1 | 11.28:1 | >= 4.5:1 | PASS |
| IT13 | FAIL 안내 배경 | EvidenceViewer.tsx:301 | Surface L151 | rgba(248,81,73,0.10) on Surface (#feeeed / #281e2a) | 1.12:1 (INFO) / 1.11:1 (INFO) | var(--color-risk-l3-bg) on Surface | 1.22:1 | 1.09:1 | UI 경계 | PASS |
| IT14 | UNVERIFIED 안내 배경 | EvidenceViewer.tsx:326 | Surface L151 | rgba(234,179,8,0.08) on Surface (#fdfaf0 / #23221b) | 1.05:1 (INFO) / 1.14:1 (INFO) | var(--color-bg-subtle) on Surface | 1.10:1 | 1.21:1 | UI 경계 | PASS |
| IT15 | UNVERIFIED 안내 테두리 | EvidenceViewer.tsx:328 | Surface L151 | rgba(234,179,8,0.30) on Surface (#fbf0ce / #493f25) | 1.22:1 (FAIL) / 1.90:1 (FAIL) | var(--color-status-unknown) on Surface | 7.09:1 | 7.03:1 | >= 3.0:1 | PASS |
| IT16 | UNVERIFIED 안내 텍스트 | EvidenceViewer.tsx:330 | Notice bg L326 | #d97706 on rgba(234,179,8,0.08) composite (#fdfaf0 / #23221b) | 3.02:1 (FAIL) / 4.89:1 (PASS) | var(--color-status-unknown) on subtle | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |

---

## 3. 설계 결정 및 비자명한 근거 (Design Decisions)

### 3.1 정본 계약 타입 도출 및 Fail-Closed 방어 구조
- `EvidenceViewer`가 표시하는 무결성 검증 결과는 임의의 문자열이 아니며, `apps/web/src/contracts/types.ts`에 정의된 `IntegrityVerificationStatus`(`PASS | FAIL | UNVERIFIED | RUN_FAILED`) 정본 유니언에 종속됩니다.
- 본 작업에서는 `INTEGRITY_VERIFICATION_STATUSES` 상수 배열을 계약 파일에서 직접 export하고, `EVIDENCE_INTEGRITY_CONFIG`가 이를 `as const satisfies Record<IntegrityVerificationStatus, EvidenceIntegrityConfigItem>`으로 엄밀 구현하도록 강제하였습니다.
- `getEvidenceIntegrityConfig(status: unknown)` 헬퍼 함수는 단순 `in` 연산자 대신 `Object.hasOwn(EVIDENCE_INTEGRITY_CONFIG, status)`를 사용하여 `toString`, `constructor`, `__proto__` 등 프로토타입 프로퍼티 주입 공격을 원천 차단하고, 정의되지 않은 모든 입력에 대해 `미확인 무결성 상태 (UNKNOWN: <raw>)` 객체를 안전하게 반환합니다.

### 3.2 16개 색상 리터럴 전수 제거 및 디자인 토큰 승격
- 베이스에 잔존하던 16건의 색상 리터럴은 라이트/다크 테마 환경에서 불투명도 및 명도비 결손을 유발하였습니다 (예: `#d97706` 라이트 배지 2.90:1 결손, `#f87171` 안내 텍스트 2.51:1 결손, 반투명 테두리 1.22~1.44:1 결손).
- 배지 및 안내 배너의 배경을 `var(--color-bg-subtle)` 및 `var(--color-risk-l3-bg)`로 통일하고, 테두리를 `var(--color-status-unknown)`, `var(--color-risk-l3-border)`, `var(--color-brand-success)`, `var(--color-brand-danger)`로 결속함으로써 라이트/다크 양 테마에서 텍스트 >= 4.5:1, 테두리 >= 3.0:1 규격을 100% 충족하도록 개선하였습니다.

### 3.3 AST 정적 분석기 및 포커스 링 보호
- `acc09-contrast-tokens.test.tsx`의 `checkConfigTables` 검증 함수를 확장하여 `EVIDENCE_INTEGRITY_CONFIG`의 전경/배경/테두리 토큰 쌍을 AST 순회 시점에 자동으로 추출하고, `index.css`의 토큰 수치와 결속하여 1:1 충돌 및 명도비 결손을 검출하도록 구성하였습니다.
- 설정 객체 및 인라인 스타일에 `outline: 'none'` 또는 `outline: 0`이 주입될 경우 AST 분석기가 즉시 위반(Violation)을 발생시켜 키보드 포커스 링 접근성을 완벽히 보존합니다.

---

## 4. 변이 테스트 (Mutation Test) 결과 (Receipt A/B)

`tools/test_c275_mutations.py`를 통해 40종(W1~W40)의 변이를 실행하여 100% 사살(KILLED)을 검증하였습니다:

| 변이 ID | 대상 영역 | 변이 내용 | 검출 및 사살 시험 | 결과 |
| :--- | :--- | :--- | :--- | :--- |
| W1 | CONFIG | PASS colorVar==bgVar 1:1 충돌 | Test 9j-2 (checkConfigTables 1:1 충돌 검출) | KILLED |
| W2 | CONFIG | PASS colorVar 저대비 텍스트 변이 (`var(--color-text-inverse)`) | Test 9y (명도비 단언) | KILLED |
| W3 | CONFIG | PASS borderVar==bgVar 충돌 (`var(--color-bg-subtle)`) | Test 9j-2 (1:1 border collision) | KILLED |
| W4 | CONFIG | PASS borderVar border-subtle 강등 | Test 9y (테두리 명도비 단언) | KILLED |
| W5 | CONFIG | FAIL colorVar==bgVar 1:1 충돌 | Test 9j-2 (1:1 color collision) | KILLED |
| W6 | CONFIG | FAIL colorVar 저대비 텍스트 변이 (`var(--color-text-inverse)`) | Test 9y (명도비 단언) | KILLED |
| W7 | CONFIG | FAIL borderVar==bgVar 충돌 | Test 9j-2 (1:1 border collision) | KILLED |
| W8 | CONFIG | RUN_FAILED colorVar==bgVar 1:1 충돌 | Test 9j-2 (1:1 color collision) | KILLED |
| W9 | CONFIG | RUN_FAILED colorVar 저대비 텍스트 변이 | Test 9y (명도비 단언) | KILLED |
| W10 | CONFIG | RUN_FAILED borderVar==bgVar 충돌 | Test 9j-2 (1:1 border collision) | KILLED |
| W11 | CONFIG | UNVERIFIED colorVar==bgVar 1:1 충돌 | Test 9j-2 (1:1 color collision) | KILLED |
| W12 | CONFIG | UNVERIFIED colorVar 저대비 텍스트 변이 | Test 9y (명도비 단언) | KILLED |
| W13 | CONFIG | UNVERIFIED borderVar==bgVar 충돌 | Test 9j-2 (1:1 border collision) | KILLED |
| W14 | CONFIG | UNVERIFIED borderVar border-subtle 강등 | Test 9y (테두리 명도비 단언) | KILLED |
| W15 | Alert | 에러 알림 배너 outline:none 주입 | Test 9j-2 (checkOutlineProp 포커스링 억제 검출) | KILLED |
| W16 | Fallback | Object.hasOwn을 `in` 연산자로 치환 (프로토타입 오염 취약점) | Test 9y (프로토타입 키 UNKNOWN 폴백 단언) | KILLED |
| W17 | Fallback | UNKNOWN fallback colorVar==bgVar 1:1 충돌 | Test 9y (UNKNOWN 대비 단언) | KILLED |
| W18 | Fallback | UNKNOWN fallback colorVar 저대비 변이 | Test 9y (UNKNOWN 대비 단언) | KILLED |
| W19 | Fallback | UNKNOWN fallback borderVar==bgVar 충돌 | Test 9y (UNKNOWN 테두리 대비 단언) | KILLED |
| W20 | Sealed | Sealed 배지 outline:none 주입 | Test 9j-2 (checkOutlineProp 포커스링 억제 검출) | KILLED |
| W21 | DOM | Dynamic badge UNKNOWN testId 폴백 우회 | Test 9y (DOM 렌더링 testid 단언) | KILLED |
| W22 | Sealed | Sealed 배지 배경을 리터럴 `rgba(56,139,253,0.15)`로 회귀 | F2 multiset inventory / Test 9j-2 리터럴 검출 | KILLED |
| W23 | Sealed | Sealed 배지 color==backgroundColor 1:1 충돌 | Test 9j-2 (1:1 color collision) | KILLED |
| W24 | Sealed | Sealed 배지 border==backgroundColor 충돌 | Test 9j-2 (1:1 border collision) | KILLED |
| W25 | Sealed | Sealed 배지 color 저대비 `var(--color-text-inverse)` 변이 | Test 9y (DOM 토큰 바인딩 단언) | KILLED |
| W26 | Copy | 복사 완료 텍스트를 리터럴 `#10b981`로 회귀 | F2 multiset inventory / Test 9j-2 리터럴 검출 | KILLED |
| W27 | Copy | 복사 완료 텍스트를 저대비 `var(--color-text-inverse)`로 변이 | Test 9j-2 (저대비 텍스트 검출) | KILLED |
| W28 | Copy | 복사 완료 텍스트를 서피스 배경 1:1 충돌로 변이 | Test 9j-2 (1:1 color collision) | KILLED |
| W29 | Alert | 에러 알림 배너 배경을 리터럴 `rgba(248,81,73,0.1)`로 회귀 | F2 multiset inventory / Test 9j-2 리터럴 검출 | KILLED |
| W30 | Alert | 에러 알림 배너 테두리를 리터럴 `rgba(248,81,73,0.3)`으로 회귀 | F2 multiset inventory / Test 9j-2 리터럴 검출 | KILLED |
| W31 | Alert | 에러 알림 배너 텍스트를 리터럴 `#f87171`로 회귀 | F2 multiset inventory / Test 9j-2 리터럴 검출 | KILLED |
| W32 | Alert | 에러 알림 배너 color==backgroundColor 1:1 충돌 | Test 9j-2 (1:1 color collision) | KILLED |
| W33 | Notice | RUN_FAILED 배너 배경을 리터럴 `rgba(248,81,73,0.08)`로 회귀 | F2 multiset inventory / Test 9j-2 리터럴 검출 | KILLED |
| W34 | Notice | RUN_FAILED 배너 테두리를 리터럴 `rgba(248,81,73,0.3)`으로 회귀 | F2 multiset inventory / Test 9j-2 리터럴 검출 | KILLED |
| W35 | Notice | RUN_FAILED 배너 텍스트를 리터럴 `#f87171`로 회귀 | F2 multiset inventory / Test 9j-2 리터럴 검출 | KILLED |
| W36 | Notice | FAIL 배너 배경을 리터럴 `rgba(248,81,73,0.1)`로 회귀 | F2 multiset inventory / Test 9j-2 리터럴 검출 | KILLED |
| W37 | Notice | FAIL 배너 텍스트를 저대비 `var(--color-text-inverse)`로 변이 | Test 9y (DOM 토큰 바인딩 단언) | KILLED |
| W38 | Notice | UNVERIFIED 배너 배경을 리터럴 `rgba(234,179,8,0.08)`로 회귀 | F2 multiset inventory / Test 9j-2 리터럴 검출 | KILLED |
| W39 | Notice | UNVERIFIED 배너 테두리를 리터럴 `rgba(234,179,8,0.3)`으로 회귀 | F2 multiset inventory / Test 9j-2 리터럴 검출 | KILLED |
| W40 | Notice | UNVERIFIED 배너 텍스트를 리터럴 `#d97706`으로 회귀 | F2 multiset inventory / Test 9j-2 리터럴 검출 | KILLED |
