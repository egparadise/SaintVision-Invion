---
doc_id: "HIST-20261005-CARD276-GEMINI"
title: "Card 276 ApprovalDetail 및 Header 화면 색상 리터럴 전수 토큰화, 승인 상태 계약 결속 및 접근성 승격"
version: "1.0.1"
status: "proposed"
author: "Gemini"
created: "2026-10-05T21:00:00+09:00"
updated: "2026-10-05T23:45:00+09:00"
source_of_truth: "Git"
---

# Card 276 ApprovalDetail 및 Header 화면 색상 리터럴 전수 토큰화, 승인 상태 계약 결속 및 접근성 승격

## 1. 작업 개요
- **목표**: ACC-09 승인 상세(`ApprovalDetail.tsx`) 및 공통 헤더(`Header.tsx`) 화면에 잔존하던 색상 리터럴 18 occurrences / 16 distinct(ApprovalDetail 7 occurrences / 7 distinct, Header 11 occurrences / 9 distinct → 0건) 전수 토큰화 및 디자인 토큰 체계 승격:
  1. `apps/web/src/features/approvals/ApprovalDetail.tsx`: 베이스(`c0519605`)에 잔존하던 7 occurrences / 7 distinct의 색상 리터럴(`#0d1117`, `#30363d`, `#58a6ff`, `#c9d1d9`, `rgba(0,0,0,0.5)`, `rgba(220,38,38,0.1)`, `rgba(56,139,253,0.15)`)을 전수 제거하고 디자인 토큰 체계로 100% 승격.
  2. `apps/web/src/shared/ui/Header.tsx`: 베이스(`c0519605`)에 잔존하던 11 occurrences / 9 distinct의 색상 리터럴(`#58a6ff`, `#60a5fa`, `#79c0ff`, `#f85149` 3회, `rgba(56,139,253,0.12)`, `rgba(56,139,253,0.25)`, `rgba(56,139,253,0.3)`, `rgba(59,130,246,0.2)`, `rgba(59,130,246,0.4)`)을 전수 제거하고 디자인 토큰 체계로 100% 승격.
  3. **정본 계약 타입 바인딩 및 승인 상태 설정 테이블 재사용 (F2)**:
     - `apps/web/src/features/approvals/ApprovalCenter.tsx`에서 wire 계약 `ApprovalItem['status']`를 단일 소스로 하여 `ApprovalStatus` 타입 및 `APPROVAL_STATUSES` 상수를 도출 및 export하여 `apps/web/src/contracts/types.ts` 와이어 계약 오염을 원천 방지 (Codex F-R1 원칙 준수).
     - `ApprovalCenter.tsx`의 `APPROVAL_STATUS_CONFIG`를 정본 단일 소스로 유지하고, `as const satisfies Record<ApprovalStatus, ApprovalStatusConfigItem>`으로 결속 (중복 테이블 생성 원천 차단).
     - Test 9z에서 `contracts/v1alpha1/core.schema.json`의 `$defs.ApprovalView.properties.status.enum`을 직접 읽어 expected key set을 생성하고 `APPROVAL_STATUS_CONFIG` key set 및 `APPROVAL_STATUSES`와 exact equality 단언 (Card 273 F-R3 패턴 준수, 스키마 변이 시 시험 즉각 실패 강제).
     - `ApprovalDetail.tsx`에 `getApprovalStatusConfig(approval.status)`를 결속하여 상단 배너에 승인 상태 배지를 명시 표출 (`data-testid="approval-detail-status-${approval.status}"`).
     - `getApprovalStatusConfig(status: unknown)` 헬퍼에 `Object.hasOwn` 방어를 적용하여 prototype 프로퍼티 주입 공격(`toString`, `constructor`, `__proto__`, `valueOf`) 및 비정상/미확인 상태를 `UNKNOWN (<safeStatus>)`(`var(--color-status-unknown)`, `var(--color-bg-subtle)`)로 안전하게 강등.
  4. **AST 정적 분석기 래칫 및 검증 테이블 바인딩**:
     - Test 9j-2 `analyzeFile` 스위트에 `ApprovalDetail.tsx` 및 `Header.tsx`를 등록하고 엄밀 통계 래칫 고정:
       - `ApprovalDetail.tsx`: `totalStyleAttrs: 35`, `checkedObjects: 3`, `checkedPairs: 14`, `unboundColorObjects: 10`, `coveredColorObjects: 13`, `checkedBorderObjects: 5`, `checkedBorderPairs: 6`, `violations: 0`.
       - `Header.tsx`: `totalStyleAttrs: 20`, `checkedObjects: 3`, `checkedPairs: 11`, `unboundColorObjects: 7`, `coveredColorObjects: 10`, `checkedBorderObjects: 4`, `checkedBorderPairs: 4`, `violations: 0`.
  5. **Multiset Baseline 래칫 강제**:
     - `COLOR_LITERAL_MULTISET_BASELINE`에서 `ApprovalDetail.tsx` 및 `Header.tsx` 양 파일 허용 인벤토리를 `{}` (0건)으로 전면 래칫 고정.
  6. **DOM 결속 및 Revert-Fail Probes**:
     - Test 9z 신설: canonical schema `core.schema.json` 결속 검증, `APPROVAL_STATUS_CONFIG` 5개 상태 명도 대비 계산(텍스트 >= 4.5:1, 테두리 >= 3.0:1), `Object.hasOwn` fail-closed UNKNOWN 방어, `ApprovalDetail` 및 `Header` 컴포넌트 실제 DOM 렌더링 검증, `index.css` 미정의 토큰 부재 전수 단언.
     - Revert-Fail Probes 136~140 신설: 베이스의 결함 조합(ApprovalDetail bound version 1.97:1, Header pill border 1.40:1, Header user name 2.22:1, Header role badge 1.47:1, Header Web Desktop button 2.02:1)이 WCAG AA 기준을 엄밀히 탈락함을 증명.
  7. **40종 전수 변이 실측 사살 (Receipt A'/B')**:
     - `tools/test_c276_mutations.py` M1~M40 40/40 100% 사살 실측 (timeout=120초, 각 변이 후 바이트 일치 복원 확인, 결과 메타데이터 봉인).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스 `c0519605`(PR #372 B')의 실제 코드 실측값(라이트 캔버스 `#f8fafc` 위 카드 서피스 `#ffffff`, 서브틀 배경 `#f1f5f9` 및 다크 캔버스 `#090d16` 위 `#111827`, `#1f2937`)을 기준으로 측정되었습니다. 알파 합성은 저장소 정본 모델인 `blendRgba`(sRGB 채널 반올림 표준 공식 `round(alpha * fg + (1 - alpha) * bg)`) 및 실제 조상 underlay를 적용하여 산출하였습니다. 베이스 `c0519605`에 존재하던 18 occurrences / 16 distinct의 색상 리터럴이 전수 제거되어 0건으로 정착되었습니다. After 값은 `python tools/reproduce_c276_contrast.py` 실행 결과(21개 전 항목)와 100% 일치합니다.

각 지표의 배경 산출 근거 줄 번호 (베이스 `c0519605` 기준):
- `ApprovalDetail.tsx:109`: 상단 배너 서브틀 배경 `var(--color-bg-subtle)` (`#f1f5f9` Light / `#1f2937` Dark).
- `ApprovalDetail.tsx:125`: Bound Version 배지 자체 배경(베이스 `rgba(56, 139, 253, 0.15)` over subtle → 개정 `var(--color-bg-surface)`).
- `ApprovalDetail.tsx:186`: 실행 메타데이터 그리드 캔버스 배경 `var(--color-bg-canvas)` (`#f8fafc` Light / `#090d16` Dark).
- `ApprovalDetail.tsx:202`: 롤백 경고 배너 배경(베이스 `rgba(220, 38, 38, 0.1)` over surface → 개정 `var(--color-risk-l3-bg)`).
- `ApprovalDetail.tsx:233`: Unified Diff `<pre>` 배경(베이스 `#0d1117` → 개정 `var(--color-bg-canvas)`).
- `ApprovalDetail.tsx:313`: 반려 확인 모달 백드롭 오버레이(베이스 `rgba(0, 0, 0, 0.5)` → 개정 `var(--color-bg-backdrop)` = `rgba(0, 0, 0, 0.75)`).
- `Header.tsx:88`: 헤더 루트 서피스 배경 `var(--color-bg-surface)` (`#ffffff` Light / `#111827` Dark).
- `Header.tsx:150/175`: 게이트웨이 및 클러스터 상태 서브틀 배경 `var(--color-bg-subtle)`.
- `Header.tsx:201`: 사용자 정보 컨테이너 배경(베이스 `rgba(56, 139, 253, 0.12)` over surface → 개정 `var(--color-bg-subtle)`).
- `Header.tsx:213`: 역할 배지 자체 배경(베이스 `rgba(56, 139, 253, 0.25)` over container underlay → 개정 `var(--color-bg-surface)` over subtle).
- `Header.tsx:243`: Web Desktop 버튼 배경(베이스 `rgba(59, 130, 246, 0.2)` over surface → 개정 `var(--color-bg-subtle)`).

| ID | UI 요소 | 위치 (코드 줄) | 조상 Underlay | Before 베이스 합성값 (Hex/RGBA on Underlay) | Before 명도비 (Light / Dark) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light / Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| AD-1 | Bound Version 배지 배경 | ApprovalDetail:125 | Subtle L109 | rgba(56,139,253,0.15) on subtle | 1.17:1 / 1.24:1 | var(--color-bg-surface) on subtle | 1.10:1 / 1.21:1 | INFO (UI Boundary) | PASS |
| AD-2 | Bound Version 배지 텍스트 | ApprovalDetail:126 | Badge bg L125 | #58a6ff on rgba(56,139,253,0.15) composite | 1.97:1 / 4.70:1 | var(--color-brand-primary) on subtle | 4.72:1 / 5.77:1 | >= 4.5:1 | PASS |
| AD-3 | Bound Version 배지 테두리 | ApprovalDetail:120 | Subtle L109 | none on subtle | 1.00:1 / 1.00:1 | var(--color-brand-primary) on subtle | 4.72:1 / 5.77:1 | >= 3.0:1 | PASS |
| AD-4 | 롤백 경고 배너 배경 | ApprovalDetail:202 | Surface L88 | rgba(220,38,38,0.1) on surface | 1.17:1 / 1.05:1 | var(--color-risk-l3-bg) on surface | 1.22:1 / 1.09:1 | INFO (UI Boundary) | PASS |
| AD-5 | 롤백 경고 배너 테두리 | ApprovalDetail:203 | Surface L88 | --color-status-offline on surface | 6.47:1 / 6.41:1 | var(--color-risk-l3-border) on surface | 6.47:1 / 6.41:1 | >= 3.0:1 | PASS |
| AD-6 | 롤백 경고 배너 텍스트 | ApprovalDetail:205 | Banner bg L202 | --color-status-offline on rgba(220,38,38,0.1) | 5.54:1 / 6.09:1 | var(--color-risk-l3-text) on risk-l3-bg | 6.80:1 / 11.28:1 | >= 4.5:1 | PASS |
| AD-7 | Unified Diff <pre> 배경 | ApprovalDetail:233 | Surface L88 | #0d1117 on surface | 18.92:1 / 1.07:1 | var(--color-bg-canvas) on surface | 1.05:1 / 1.10:1 | INFO (UI Boundary) | PASS |
| AD-8 | Unified Diff <pre> 텍스트 | ApprovalDetail:234 | Pre bg L233 | #c9d1d9 on #0d1117 | 12.26:1 / 12.26:1 | var(--color-text-primary) on bg-canvas | 17.06:1 / 18.59:1 | >= 4.5:1 | PASS |
| AD-9 | Unified Diff <pre> 테두리 | ApprovalDetail:241 | Surface L88 | #30363d on surface | 12.20:1 / 1.45:1 | var(--color-border-strong) on surface | 7.58:1 / 6.99:1 | >= 3.0:1 | PASS |
| AD-10 | 반려 모달 백드롭 오버레이 | ApprovalDetail:313 | Canvas L186 | rgba(0, 0, 0, 0.5) on Canvas | N/A (Focus Overlay) | var(--color-bg-backdrop) | 100% Non-text overlay | focus overlay | PASS |
| HD-1 | 게이트웨이 오프라인 표시 점 | Header:185 | Subtle L175 | #f85149 on subtle | 3.06:1 / 4.38:1 | var(--color-status-offline) on subtle | 5.91:1 / 5.31:1 | >= 3.0:1 | PASS |
| HD-2 | 게이트웨이 오프라인 텍스트 | Header:190 | Subtle L175 | #f85149 on subtle | 3.06:1 / 4.38:1 | var(--color-status-offline) on subtle | 5.91:1 / 5.31:1 | >= 4.5:1 | PASS |
| HD-3 | 사용자 정보 컨테이너 배경 | Header:201 | Surface L88 | rgba(56,139,253,0.12) on surface | 1.14:1 / 1.17:1 | var(--color-bg-subtle) on surface | 1.10:1 / 1.21:1 | INFO (UI Boundary) | PASS |
| HD-4 | 사용자 정보 컨테이너 테두리 | Header:202 | Surface L88 | rgba(56,139,253,0.3) on surface | 1.40:1 / 1.57:1 | var(--color-border-strong) on surface | 7.58:1 / 6.99:1 | >= 3.0:1 | PASS |
| HD-5 | 사용자 이름 텍스트 | Header:207 | Container bg L201 | #58a6ff on rgba(56,139,253,0.12) | 2.22:1 / 5.99:1 | var(--color-brand-primary) on subtle | 4.72:1 / 5.77:1 | >= 4.5:1 | PASS |
| HD-6 | 역할 배지 배경 | Header:213 | Container underlay L201 | rgba(56,139,253,0.25) on container composite | 1.28:1 / 1.44:1 | var(--color-bg-surface) on subtle | 1.10:1 / 1.21:1 | INFO (UI Boundary) | PASS |
| HD-7 | 역할 배지 텍스트 | Header:216 | Role bg L213 | #79c0ff on surface->container->badge composite | 1.33:1 / 5.40:1 | var(--color-text-secondary) on surface | 7.58:1 / 14.33:1 | >= 4.5:1 | PASS |
| HD-8 | 로그아웃 버튼 텍스트 | Header:222 | Container bg L201 | #f85149 on rgba(56,139,253,0.12) | 2.94:1 / 4.51:1 | var(--color-status-offline) on subtle | 5.91:1 / 5.31:1 | >= 4.5:1 | PASS |
| HD-9 | Web Desktop 버튼 배경 | Header:243 | Surface L88 | rgba(59,130,246,0.2) on surface | 1.26:1 / 1.29:1 | var(--color-bg-subtle) on surface | 1.10:1 / 1.21:1 | INFO (UI Boundary) | PASS |
| HD-10 | Web Desktop 버튼 테두리 | Header:244 | Surface L88 | rgba(59,130,246,0.4) on surface | 1.62:1 / 1.80:1 | var(--color-brand-primary) on surface | 5.17:1 / 6.98:1 | >= 3.0:1 | PASS |
| HD-11 | Web Desktop 버튼 텍스트 | Header:245 | Desktop bg L243 | #60a5fa on rgba(59,130,246,0.2) | 2.02:1 / 5.39:1 | var(--color-brand-primary) on subtle | 4.72:1 / 5.77:1 | >= 4.5:1 | PASS |

### 2.2 독립 재현 스크립트 실행 콘솔 (`tools/reproduce_c276_contrast.py`)

```text
================================================================================
Card 276: ACC-09 ApprovalDetail & Header WCAG 2.2 AA Contrast Reproduction
================================================================================
[AD-1] Bound Version badge background (UI Boundary): PASS (Light: 1.10:1, Dark: 1.21:1, Target: INFO)
[AD-2] Bound Version badge text (text): PASS (Light: 4.72:1, Dark: 5.77:1, Min: 4.5:1)
[AD-3] Bound Version badge border (border): PASS (Light: 4.72:1, Dark: 5.77:1, Min: 3.0:1)
[AD-4] Rollback warning banner background (UI Boundary): PASS (Light: 1.22:1, Dark: 1.09:1, Target: INFO)
[AD-5] Rollback warning banner border (border): PASS (Light: 6.47:1, Dark: 6.41:1, Min: 3.0:1)
[AD-6] Rollback warning banner text (text): PASS (Light: 6.80:1, Dark: 11.28:1, Min: 4.5:1)
[AD-7] Unified Diff <pre> background (UI Boundary): PASS (Light: 1.05:1, Dark: 1.10:1, Target: INFO)
[AD-8] Unified Diff <pre> text (text): PASS (Light: 17.06:1, Dark: 18.59:1, Min: 4.5:1)
[AD-9] Unified Diff <pre> border (border): PASS (Light: 7.58:1, Dark: 6.99:1, Min: 3.0:1)
[AD-10] Reject modal backdrop overlay (Focus Dimming Overlay): PASS (Non-text overlay tokenized)
[HD-1] Gateway offline indicator dot (border): PASS (Light: 5.91:1, Dark: 5.31:1, Min: 3.0:1)
[HD-2] Gateway offline text (text): PASS (Light: 5.91:1, Dark: 5.31:1, Min: 4.5:1)
[HD-3] User badge container background (UI Boundary): PASS (Light: 1.10:1, Dark: 1.21:1, Target: INFO)
[HD-4] User badge container border (border): PASS (Light: 7.58:1, Dark: 6.99:1, Min: 3.0:1)
[HD-5] User name text (text): PASS (Light: 4.72:1, Dark: 5.77:1, Min: 4.5:1)
[HD-6] User role badge background (UI Boundary): PASS (Light: 1.10:1, Dark: 1.21:1, Target: INFO)
[HD-7] User role badge text (text): PASS (Light: 7.58:1, Dark: 14.33:1, Min: 4.5:1)
[HD-8] Logout button text (text): PASS (Light: 5.91:1, Dark: 5.31:1, Min: 4.5:1)
[HD-9] Web Desktop button background (UI Boundary): PASS (Light: 1.10:1, Dark: 1.21:1, Target: INFO)
[HD-10] Web Desktop button border (border): PASS (Light: 5.17:1, Dark: 6.98:1, Min: 3.0:1)
[HD-11] Web Desktop button text (text): PASS (Light: 4.72:1, Dark: 5.77:1, Min: 4.5:1)
--------------------------------------------------------------------------------
Result: 21/21 items passed WCAG 2.2 AA requirements.
================================================================================
```

---

## 3. 설계 결정 및 비자명한 근거 (Design Decisions)

### 3.1 승인 상태 테이블 단일 소스 원칙 및 계약 결속
- 승인 상태 설정 객체는 이미 Card 245에서 `ApprovalCenter.tsx`에 `APPROVAL_STATUS_CONFIG`로 구축되어 있었습니다.
- 본 Card 276에서는 중복 테이블을 생성하지 않고, `ApprovalCenter.tsx`의 설정을 `ApprovalStatusConfigItem` 및 `as const satisfies Record<ApprovalStatus, ApprovalStatusConfigItem>`으로 엄밀 타이핑하여 `ApprovalDetail.tsx`가 직접 import하여 사용하도록 결속하였습니다.
- `ApprovalDetail.tsx` 상단 배너에 승인 상태 배지를 추가하여 상태(`pending`, `approved`, `rejected`, `expired`, `dispatched`)를 시각적·의미론적으로 명확히 전달하도록 개선하였습니다.
- Test 9z에서는 canonical JSON schema `core.schema.json`의 `$defs.ApprovalView.properties.status.enum`을 직접 파싱하여 `APPROVAL_STATUS_CONFIG` 및 `APPROVAL_STATUSES` 키 셋과의 완전 일치를 강제함으로써, 스키마 레벨의 변경이나 누락이 발생할 경우 CI 시험이 즉시 fail-closed 차단되도록 설계하였습니다.

### 3.2 반려 모달 백드롭 `var(--color-bg-backdrop)` 토큰화
- `ApprovalDetail.tsx`의 반려 확인 모달 백드롭 `rgba(0, 0, 0, 0.5)`는 텍스트를 담지 않는 비텍스트 포커스 딤 오버레이(Focus-dimming overlay)입니다.
- 이를 `var(--color-bg-backdrop)` 디자인 토큰으로 승격하여 모달 뒤편 콘텐츠를 반투명하게 감추고 포커스 트랩에 집중시키는 디자인 일관성을 확보하였습니다.
- 또한 베이스 `rgba(0, 0, 0, 0.5)`에서 `--color-bg-backdrop` = `rgba(0, 0, 0, 0.75)`로 전환됨에 따라 모달 딤이 50% 강화되어(Card 273 0.65→0.75의 일관성 연장) 배경과의 초점 분리도가 추가 향상되었습니다.

### 3.3 헤더 공통 컴포넌트 안전성 보존 및 회귀 차단
- `Header.tsx`는 대시보드뿐만 아니라 데스크톱 환경 전체에 상시 마운트되는 최상위 공통 컴포넌트입니다 (`desktop-layout.test.tsx`, `s11-defect-fixes.test.tsx` 등 다수 테스트 참조).
- 내부 탭 식별자(`data-testid`), 텍스트 라벨, `aria-current="page"` 불변식을 100% 보존하고, 오직 인라인 색상 리터럴 11개 출현만을 디자인 토큰으로 대체하여 다른 화면이나 기존 스위트에 단 1건의 회귀도 발생하지 않도록 조치하였습니다.

---

## 4. 변이 테스트 (Mutation Test) 결과 (Receipt A'/B')

`tools/test_c276_mutations.py`를 통해 40종(M1~M40)의 변이를 실행하여 100% 사살(KILLED)을 검증하였습니다:

| 변이 ID | 대상 영역 | 변이 내용 | 검출 및 사살 시험 | 결과 |
| :--- | :--- | :--- | :--- | :--- |
| M1 | ApprovalDetail | Bound version badge color==bg 1:1 충돌 | Test 9j-2 (1:1 color collision) | KILLED |
| M2 | ApprovalDetail | Bound version badge border collision | Test 9j-2 (1:1 border collision) | KILLED |
| M3 | ApprovalDetail | Bound version badge 저대비 텍스트 변이 (`var(--color-text-inverse)`) | Test 9j-2 (명도비 단언) | KILLED |
| M4 | ApprovalDetail | Bound version badge inline outline:none 포커스 억제 | Test 9j-2 (focus ring suppression) | KILLED |
| M5 | ApprovalDetail | Bound version badge color 리터럴 회귀 (`#58a6ff`) | Multiset Baseline + Test 9j-2 | KILLED |
| M6 | ApprovalDetail | Bound version badge bg 리터럴 회귀 (`rgba(56, 139, 253, 0.15)`) | Multiset Baseline + Test 9j-2 | KILLED |
| M7 | ApprovalDetail | Rollback banner color==bg 1:1 충돌 | Test 9j-2 (1:1 color collision) | KILLED |
| M8 | ApprovalDetail | Rollback banner border collision | Test 9j-2 (1:1 border collision) | KILLED |
| M9 | ApprovalDetail | Rollback banner 저대비 텍스트 변이 (`var(--color-text-inverse)`) | Test 9j-2 (명도비 단언) | KILLED |
| M10 | ApprovalDetail | Rollback banner bg 리터럴 회귀 (`rgba(220, 38, 38, 0.1)`) | Multiset Baseline + Test 9j-2 | KILLED |
| M11 | ApprovalDetail | Rollback banner border 리터럴 회귀 (`#dc2626`) | Multiset Baseline + Test 9j-2 | KILLED |
| M12 | ApprovalDetail | Rollback banner inline outline:none 포커스 억제 | Test 9j-2 (focus ring suppression) | KILLED |
| M13 | ApprovalDetail | Unified Diff pre color==bg 1:1 충돌 | Test 9j-2 (1:1 color collision) | KILLED |
| M14 | ApprovalDetail | Unified Diff pre border collision | Test 9j-2 (1:1 border collision) | KILLED |
| M15 | ApprovalDetail | Unified Diff pre 저대비 텍스트 변이 (`var(--color-text-inverse)`) | Test 9j-2 (명도비 단언) | KILLED |
| M16 | ApprovalDetail | Unified Diff pre bg 리터럴 회귀 (`#0d1117`) | Multiset Baseline + Test 9j-2 | KILLED |
| M17 | ApprovalDetail | Unified Diff pre border 리터럴 회귀 (`#30363d`) | Multiset Baseline + Test 9j-2 | KILLED |
| M18 | ApprovalDetail | Unified Diff pre text 리터럴 회귀 (`#c9d1d9`) | Multiset Baseline + Test 9j-2 | KILLED |
| M19 | ApprovalDetail | Unified Diff pre inline outline:none 포커스 억제 | Test 9j-2 (focus ring suppression) | KILLED |
| M20 | ApprovalDetail | Reject modal backdrop 리터럴 회귀 (`rgba(0, 0, 0, 0.5)`) | Multiset Baseline + Test 9j-2 | KILLED |
| M21 | Header | Gateway dot offline 리터럴 회귀 (`#f85149`) | Multiset Baseline + Test 9j-2 | KILLED |
| M22 | Header | Gateway offline text 리터럴 회귀 (`#f85149`) | Multiset Baseline + Test 9j-2 | KILLED |
| M23 | Header | Gateway offline text 저대비 텍스트 변이 (`var(--color-text-inverse)`) | Test 9j-2 (명도비 단언) | KILLED |
| M24 | Header | Gateway offline text color==bg 충돌 | Test 9j-2 (1:1 color collision) | KILLED |
| M25 | Header | User pill container bg 리터럴 회귀 (`rgba(56, 139, 253, 0.12)`) | Multiset Baseline + Test 9j-2 | KILLED |
| M26 | Header | User pill container border 리터럴 회귀 (`rgba(56, 139, 253, 0.3)`) | Multiset Baseline + Test 9j-2 | KILLED |
| M27 | Header | User pill container border 충돌 (`border: 1px solid var(--color-bg-subtle)`) | Test 9j-2 (1:1 border collision) | KILLED |
| M28 | Header | User pill container inline outline:none 포커스 억제 | Test 9j-2 (focus ring suppression) | KILLED |
| M29 | Header | User name text 리터럴 회귀 (`#58a6ff`) | Multiset Baseline + Test 9j-2 | KILLED |
| M30 | Header | User name color==bg 1:1 충돌 | Test 9j-2 (1:1 color collision) | KILLED |
| M31 | Header | User name 저대비 텍스트 변이 (`var(--color-text-inverse)`) | Test 9j-2 (명도비 단언) | KILLED |
| M32 | Header | Role badge bg 리터럴 회귀 (`rgba(56, 139, 253, 0.25)`) | Multiset Baseline + Test 9j-2 | KILLED |
| M33 | Header | Role badge text 리터럴 회귀 (`#79c0ff`) | Multiset Baseline + Test 9j-2 | KILLED |
| M34 | Header | Role badge color==bg 1:1 충돌 | Test 9j-2 (1:1 color collision) | KILLED |
| M35 | Header | Role badge 저대비 텍스트 변이 (`var(--color-text-inverse)`) | Test 9j-2 (명도비 단언) | KILLED |
| M36 | Header | Logout button text 리터럴 회귀 (`#f85149`) | Multiset Baseline + Test 9j-2 | KILLED |
| M37 | Header | Logout button inline outline:none 포커스 억제 | Test 9j-2 (focus ring suppression) | KILLED |
| M38 | Header | Web Desktop button bg 리터럴 회귀 (`rgba(59, 130, 246, 0.2)`) | Multiset Baseline + Test 9j-2 | KILLED |
| M39 | Header | Web Desktop button border 리터럴 회귀 (`rgba(59, 130, 246, 0.4)`) | Multiset Baseline + Test 9j-2 | KILLED |
| M40 | Header | Web Desktop button text 리터럴 회귀 (`#60a5fa`) | Multiset Baseline + Test 9j-2 | KILLED |

---

## 5. 최종 검증 결과 요약
- **Vitest 전체 스위트**: 40/40 passed (`acc09-contrast-tokens.test.tsx`), 전체 단위 테스트 전원 통과.
- **TypeScript 무오류**: `cd apps/web && npx tsc -b` -> exit code 0, 타입 에러 0건.
- **파이썬 백엔드 라우트 게이트**: `pytest tests/test_route_coverage.py` -> 41 passed (100%).
- **프런트엔드 9대 무결성 가드**: `python tools/check_frontend_integrity.py` -> 0 violations.
- **계약 바인딩 검증**: `python tools/check_contract_bindings.py` -> PASS (55 fixtures, 20 types, 14 replay guards).
- **문서 무결성**: `python tools/check_docs.py` -> PASS.
- **문서 경로 인용 래칫**: `python tools/check_doc_path_citations.py --ratchet --base-ref c0519605` -> PASS.
- **Obsidian 동기화**: `python tools/sync_obsidian.py --check` -> 0 conflicts.
