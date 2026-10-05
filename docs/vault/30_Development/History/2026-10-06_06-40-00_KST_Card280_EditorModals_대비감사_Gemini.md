---
doc_id: "HIST-20261006-CARD280-GEMINI"
title: "Card 280 Editor Modals 화면 색상 리터럴 전수 토큰화 및 접근성 승격"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-06T06:40:00+09:00"
updated: "2026-10-06T06:40:00+09:00"
source_of_truth: "Git"
---

# Card 280 Editor Modals 화면 색상 리터럴 전수 토큰화 및 접근성 승격

## 1. 작업 개요
- **목표**: ACC-09 에디터 모달 컴포넌트 묶음 3종(`ConflictResolutionModal.tsx`, `DiffViewer.tsx`, `GitCommitModal.tsx`)에 잔존하던 60 occurrences 색상 리터럴 전수 토큰화(60건→0건), 상태 계약 무결성 및 디자인 토큰 체계 승격:
  1. `apps/web/src/features/editor/ConflictResolutionModal.tsx`: 베이스(`94c99c72`, Card 279 Commit D + coordinator stamp)에 잔존하던 16 occurrences / 9 distinct 색상 리터럴 (`#0d1117`, `#161b22`, `#30363d`×2, `#58a6ff`, `#8b949e`×2, `#f85149`×5, `#fff`, `rgba(0,0,0,0.5)`, `rgba(0,0,0,0.75)`, `rgba(248,81,73,0.1)`) 전수 제거 및 토큰 승격 (16건→0건).
  2. `apps/web/src/features/editor/DiffViewer.tsx`: 베이스에 잔존하던 18 occurrences / 10 distinct 색상 리터럴 (`#0d1117`, `#161b22`, `#30363d`×2, `#3fb950`×3, `#484f58`×2, `#8b949e`, `#c9d1d9`×2, `#f0f6fc`, `#f85149`×3, `rgba(248,81,73,0.15)`, `rgba(46,160,67,0.15)`) 전수 제거 및 토큰 승격 (18건→0건).
  3. `apps/web/src/features/editor/GitCommitModal.tsx`: 베이스에 잔존하던 26 occurrences / 10 distinct 색상 리터럴 (`#0d1117`×3, `#161b22`, `#30363d`×6, `#58a6ff`, `#8b949e`×5, `#c9d1d9`×3, `#e3b341`×2, `#f0f6fc`, `#f85149`, `rgba(0,0,0,0.5)`, `rgba(0,0,0,0.75)`, `rgba(56,139,253,0.1)`) 전수 제거 및 토큰 승격 (26건→0건).
  4. **Diff 라인 전용 시맨틱 토큰 신설 및 동적 명도 대비 강제**:
     - `apps/web/src/index.css` 라이트/다크 양 테마에 diff 전용 시맨틱 토큰 6종 정의:
       - `--color-diff-added-bg`: `#dcfce7` (Light) / `#052e16` (Dark)
       - `--color-diff-added-text`: `#166534` (Light) / `#4ade80` (Dark) (양 테마 배경 위 6.49:1 / 8.55:1 >= 4.5:1 준수)
       - `--color-diff-added-border`: `#16a34a` (Light) / `#22c55e` (Dark) (3.15:1 / 8.53:1 >= 3.0:1 준수)
       - `--color-diff-removed-bg`: `#fee2e2` (Light) / `#3b1219` (Dark)
       - `--color-diff-removed-text`: `#991b1b` (Light) / `#fca5a5` (Dark) (양 테마 배경 위 6.80:1 / 8.60:1 >= 4.5:1 준수)
       - `--color-diff-removed-border`: `#b91c1c` (Light) / `#f87171` (Dark) (6.18:1 / 7.02:1 >= 3.0:1 준수)
  5. **Fail-Closed 상태 계약 체계 확립**:
     - `ConflictResolutionModal`: `UiConflictStatus` ('etag_mismatch' | 'concurrency_conflict') 및 `UiConflictResolutionAction` ('accept_remote' | 'keep_mine' | 'merge') 설정 표 구축 + `Object.hasOwn` 기반 `getConflictStatusConfig`, `getConflictResolutionActionConfig` fail-closed 헬퍼.
     - `DiffViewer`: `UiDiffLineType` (DiffLine['type']: 'added' | 'removed' | 'unchanged') 설정 표 `DIFF_LINE_TYPE_CONFIG` 구축 + `getDiffLineTypeConfig` fail-closed 헬퍼.
     - `GitCommitModal`: `UiGitFileStatus` ('clean' | 'modified') 및 `UiGitStageState` ('staged' | 'unstaged') 설정 표 구축 + `getGitFileStatusConfig`, `getGitStageStateConfig` fail-closed 헬퍼.
  6. **AST 정적 분석기 래칫 및 검증 테이블 바인딩**:
     - Test 9j-2 `analyzeFile` 스위트에 3개 파일 등록:
       - `ConflictResolutionModal.tsx`: 18 style attrs, 2 checked objects, 5 checked pairs, 3 unbound, 5 covered, 4 border objects, 4 border pairs, 0 violations.
       - `DiffViewer.tsx`: 17 style attrs, 4 checked objects, 8 checked pairs, 4 unbound, 8 covered, 3 border objects, 3 border pairs, 0 violations.
       - `GitCommitModal.tsx`: 25 style attrs, 4 checked objects, 12 checked pairs, 8 unbound, 12 covered, 6 border objects, 6 border pairs, 0 violations.
  7. **Multiset Baseline 래칫 강제**:
     - `COLOR_LITERAL_MULTISET_BASELINE`에서 3개 파일 전수 `{}` (0건)으로 전면 래칫 고정.
     - `var(--color-border-subtle)` 정확히 471건, 34개 파일 보존 (Test 10 통과).
  8. **DOM 결속 및 Revert-Fail Probes**:
     - Test 9ad 신설: 3개 모달 컴포넌트 렌더링, 색상 토큰 바인딩, 동적 명도 대비 계산, 프로토타입 오염 격리 전수 단언.
     - Revert-Fail Probes 156~160 신설: 베이스의 결함 조합이 WCAG AA 기준을 엄밀히 탈락함을 증명.
  9. **40종 전수 변이 실측 사살 (Receipt A/B)**:
     - `tools/test_c280_mutations.py` M1~M40 40/40 100% 사살 실측 (clean commit A `f1c898ce` 기반, Commit B `b6ba31fb` 봉인, 바이너리 read_bytes/write_bytes 복원 및 fail-closed clean-tree 무결성 검증 통과).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스 `94c99c72`(Card 279 Commit D + coordinator stamp)의 실제 코드 실측값(라이트 캔버스 `#f8fafc` 위 카드 서피스 `#ffffff` 및 다크 캔버스 `#090d16` 위 `#111827`, `#1f2937`)을 기준으로 측정되었습니다. 알파 합성은 저장소 정본 모델인 `blendRgba` 및 실제 조상 underlay를 적용하여 산출하였습니다. After 값은 `python tools/reproduce_c280_contrast.py` 실행 결과(32개 전 항목)와 100% 일치합니다.

각 지표의 배경 산출 근거 줄 번호 (베이스 `94c99c72` 기준):
- `ConflictResolutionModal.tsx:32`: 모달 백드롭 배경 `rgba(0, 0, 0, 0.75)`.
- `ConflictResolutionModal.tsx:44`: 다이얼로그 본체 배경 `#161b22`.
- `ConflictResolutionModal.tsx:55`: 경고 배너 배경 `rgba(248, 81, 73, 0.1)` on surface.
- `ConflictResolutionModal.tsx:88`: 하단 액션 영역 배경 `#0d1117` on surface.
- `DiffViewer.tsx:20`: 코드 뷰어 본체 배경 `#0d1117` on surface.
- `DiffViewer.tsx:30`: 헤더 바 배경 `#161b22` on canvas.
- `DiffViewer.tsx:81`: 추가 코드 줄 배경 `rgba(46, 160, 67, 0.15)` on canvas.
- `DiffViewer.tsx:85`: 삭제 코드 줄 배경 `rgba(248, 81, 73, 0.15)` on canvas.
- `GitCommitModal.tsx:112`: 커밋 다이얼로그 배경 `#161b22` on canvas.
- `GitCommitModal.tsx:128`: 작성자 및 커밋 메시지 입력 필드 배경 `#0d1117` on surface.
- `GitCommitModal.tsx:192`: 스테이징 파일 목록 배경 `#0d1117` on surface.

| ID | 항목 명칭 | 코드 위치 | 언더레이 | Before 규격 | Before 실측 (L/D) | After 토큰 규격 | After 실측 (L/D) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EM-1 | 모달 백드롭 스크림 (scrim on canvas) | ConflictResolutionModal:131 | Canvas | rgba(0,0,0,0.75) on canvas | N/A | var(--color-bg-backdrop) on canvas | N/A | N/A | INFO (스크림) |
| EM-2 | 다이얼로그 본체 배경 (surface on canvas) | ConflictResolutionModal:145 | Canvas | #161b22 on canvas | N/A | var(--color-bg-surface) on canvas | N/A | N/A | INFO (표면) |
| EM-3 | 다이얼로그 외곽선 (offline status border on surface) | ConflictResolutionModal:146 | Surface | #f85149 on surface | 3.35:1 / 5.29:1 | var(--color-status-offline) on surface | 6.47:1 / 6.41:1 | >= 3.0:1 | PASS |
| EM-4 | 경고 배너 배경 (risk-l3 fill on surface) | ConflictResolutionModal:159 | Surface | rgba(248,81,73,0.1) on surface | N/A | var(--color-risk-l3-bg) on surface | N/A | N/A | INFO (배경) |
| EM-5 | 경고 제목 텍스트 (offline status on risk-l3-bg) | ConflictResolutionModal:168 | risk-l3-bg | #f85149 on risk-l3-bg | 2.74:1 / 4.87:1 | var(--color-status-offline) on risk-l3-bg | 5.30:1 / 5.90:1 | >= 4.5:1 | PASS (결손수리) |
| EM-6 | 경고 부제목 안내 문구 (text-muted on risk-l3-bg) | ConflictResolutionModal:184 | risk-l3-bg | #8b949e on risk-l3-bg | 2.52:1 / 5.31:1 | var(--color-text-muted) on risk-l3-bg | 4.71:1 / 6.43:1 | >= 4.5:1 | PASS (결손수리) |
| EM-7 | 경고 파일 경로 코드 텍스트 (brand-hover on risk-l3-bg) | ConflictResolutionModal:185 | risk-l3-bg | #58a6ff on risk-l3-bg | 2.07:1 / 6.46:1 | var(--color-brand-hover) on risk-l3-bg | 5.49:1 / 9.05:1 | >= 4.5:1 | PASS (결손수리) |
| EM-8 | 하단 액션 영역 배경 (canvas on surface) | ConflictResolutionModal:204 | Surface | #0d1117 on surface | N/A | var(--color-bg-canvas) on surface | N/A | N/A | INFO (배경) |
| EM-9 | 하단 액션 영역 상단 경계선 (border-subtle on canvas) | ConflictResolutionModal:203 | Canvas | #30363d on canvas | 11.66:1 / 1.59:1 | var(--color-border-subtle) on canvas | 3.33:1 / 4.08:1 | >= 3.0:1 | PASS (결손수리) |
| EM-10 | 하단 액션 안내 텍스트 (text-muted on canvas) | ConflictResolutionModal:210 | Canvas | #8b949e on canvas | 2.94:1 / 6.32:1 | var(--color-text-muted) on canvas | 5.50:1 / 7.65:1 | >= 4.5:1 | PASS (결손수리) |
| EM-11 | 강제 덮어쓰기 버튼 텍스트 (offline status on canvas) | ConflictResolutionModal:222 | Canvas | #f85149 on canvas | 3.20:1 / 5.80:1 | var(--color-status-offline) on canvas | 6.18:1 / 7.02:1 | >= 4.5:1 | PASS (결손수리) |
| EM-12 | Diff 뷰어 본체 배경 (canvas on surface) | DiffViewer:75 | Surface | #0d1117 on surface | N/A | var(--color-bg-canvas) on surface | N/A | N/A | INFO (배경) |
| EM-13 | Diff 헤더 바 배경 (surface on canvas) | DiffViewer:89 | Canvas | #161b22 on canvas | N/A | var(--color-bg-surface) on canvas | N/A | N/A | INFO (배경) |
| EM-14 | Diff 헤더 하단 경계선 (border-subtle on surface) | DiffViewer:88 | Surface | #30363d on surface | 12.20:1 / 1.45:1 | var(--color-border-subtle) on surface | 3.48:1 / 3.73:1 | >= 3.0:1 | PASS (결손수리) |
| EM-15 | Diff 파일 경로 텍스트 (text-primary on surface) | DiffViewer:93 | Surface | #f0f6fc on surface | 1.09:1 / 16.30:1 | var(--color-text-primary) on surface | 17.85:1 / 16.98:1 | >= 4.5:1 | PASS (결손수리) |
| EM-16 | Diff 추가 줄 수 텍스트 (diff-added-text on surface) | DiffViewer:94 | Surface | #3fb950 on surface | 2.54:1 / 6.98:1 | var(--color-diff-added-text) on surface | 7.13:1 / 10.18:1 | >= 4.5:1 | PASS (결손수리) |
| EM-17 | Diff 삭제 줄 수 텍스트 (diff-removed-text on surface) | DiffViewer:95 | Surface | #f85149 on surface | 3.35:1 / 5.29:1 | var(--color-diff-removed-text) on surface | 8.31:1 / 9.35:1 | >= 4.5:1 | PASS (결손수리) |
| EM-18 | Diff 추가 코드 줄 배경 (added-bg on canvas) | DiffViewer:143 | Canvas | rgba(46,160,67,0.15) on canvas | N/A | var(--color-diff-added-bg) on canvas | N/A | N/A | INFO (배경) |
| EM-19 | Diff 추가 줄 코드 텍스트 (added-text on added-bg) | DiffViewer:178 | diff-added-bg | #3fb950 on diff-added-bg | 2.31:1 / 5.87:1 | var(--color-diff-added-text) on diff-added-bg | 6.49:1 / 8.55:1 | >= 4.5:1 | PASS (결손수리) |
| EM-20 | Diff 추가 줄 좌측 인디케이터 (added-border on canvas) | DiffViewer:144 | Canvas | #3fb950 on canvas | 2.43:1 / 7.65:1 | var(--color-diff-added-border) on canvas | 3.15:1 / 8.53:1 | >= 3.0:1 | PASS (결손수리) |
| EM-21 | Diff 삭제 코드 줄 배경 (removed-bg on canvas) | DiffViewer:143 | Canvas | rgba(248,81,73,0.15) on canvas | N/A | var(--color-diff-removed-bg) on canvas | N/A | N/A | INFO (배경) |
| EM-22 | Diff 삭제 줄 코드 텍스트 (removed-text on removed-bg) | DiffViewer:178 | diff-removed-bg | #f85149 on diff-removed-bg | 2.74:1 / 4.87:1 | var(--color-diff-removed-text) on diff-removed-bg | 6.80:1 / 8.60:1 | >= 4.5:1 | PASS (결손수리) |
| EM-23 | Diff 삭제 줄 좌측 인디케이터 (removed-border on canvas) | DiffViewer:144 | Canvas | #f85149 on canvas | 3.20:1 / 5.80:1 | var(--color-diff-removed-border) on canvas | 6.18:1 / 7.02:1 | >= 3.0:1 | PASS |
| EM-24 | Diff 거터 줄 번호 텍스트 (text-muted on canvas) | DiffViewer:152 | Canvas | #484f58 on canvas | 7.92:1 / 2.35:1 | var(--color-text-muted) on canvas | 5.50:1 / 7.65:1 | >= 4.5:1 | PASS (결손수리) |
| EM-25 | 커밋 입력 필드 배경 (canvas on surface) | GitCommitModal:198 | Surface | #0d1117 on surface | N/A | var(--color-bg-canvas) on surface | N/A | N/A | INFO (배경) |
| EM-26 | 커밋 입력 필드 테두리 (border-subtle on surface) | GitCommitModal:199 | Surface | #30363d on surface | 12.20:1 / 1.45:1 | var(--color-border-subtle) on surface | 3.48:1 / 3.73:1 | >= 3.0:1 | PASS (결손수리) |
| EM-27 | 커밋 입력 필드 내용 텍스트 (text-primary on canvas) | GitCommitModal:201 | Canvas | #c9d1d9 on canvas | 1.48:1 / 12.59:1 | var(--color-text-primary) on canvas | 17.06:1 / 18.59:1 | >= 4.5:1 | PASS (결손수리) |
| EM-28 | 필수 입력 별표 인디케이터 (offline status on surface) | GitCommitModal:210 | Surface | #f85149 on surface | 3.35:1 / 5.29:1 | var(--color-status-offline) on surface | 6.47:1 / 6.41:1 | >= 4.5:1 | PASS |
| EM-29 | 전체 스테이징 버튼 텍스트 (brand-hover on surface) | GitCommitModal:243 | Surface | #58a6ff on surface | 2.53:1 / 7.02:1 | var(--color-brand-hover) on surface | 6.70:1 / 9.84:1 | >= 4.5:1 | PASS (결손수리) |
| EM-30 | 스테이징 파일 목록 테두리 (border-subtle on surface) | GitCommitModal:264 | Surface | #30363d on surface | 12.20:1 / 1.45:1 | var(--color-border-subtle) on surface | 3.48:1 / 3.73:1 | >= 3.0:1 | PASS (결손수리) |
| EM-31 | 수정된 파일명 상태 텍스트 (status-degraded on canvas) | GitCommitModal:294 | Canvas | #e3b341 on canvas | 1.86:1 / 9.98:1 | var(--color-status-degraded) on canvas | 4.80:1 / 9.05:1 | >= 4.5:1 | PASS (결손수리) |
| EM-32 | 미수정 파일명 상태 텍스트 (text-secondary on canvas) | GitCommitModal:294 | Canvas | #c9d1d9 on canvas | 1.48:1 / 12.59:1 | var(--color-text-secondary) on canvas | 7.24:1 / 15.69:1 | >= 4.5:1 | PASS (결손수리) |

---

## 2.2 독립 재현 검증 스크립트 실행 결과 (`reproduce_c280_contrast.py`)

```text
Machine verification: All 26 token declarations match apps/web/src/index.css exactly.
========================================================================================
CARD 280 (EditorModals) WCAG 2.2 AA DYNAMIC CONTRAST AUDIT REPORT
========================================================================================
ID     | Target     | Before (L/D)   | After (L/D)    | Status | Item Name
----------------------------------------------------------------------------------------
EM-1   | INFO       | N/A            | N/A            | INFO   | Modal backdrop overlay (scrim on canvas)
EM-2   | INFO       | N/A            | N/A            | INFO   | Dialog container (surface on canvas)
EM-3   | >= 3.0:1   | 3.35 / 5.29    | 6.47 / 6.41    | PASS   | Dialog boundary (offline status border on surface)
EM-4   | INFO       | N/A            | N/A            | INFO   | Warning banner (risk-l3 fill on surface)
EM-5   | >= 4.5:1   | 2.74 / 4.87    | 5.30 / 5.90    | PASS   | Warning title text (offline status on risk-l3-bg)
EM-6   | >= 4.5:1   | 2.52 / 5.31    | 4.71 / 6.43    | PASS   | Warning description (text-muted on risk-l3-bg)
EM-7   | >= 4.5:1   | 2.07 / 6.46    | 5.49 / 9.05    | PASS   | Warning code text (brand-hover on risk-l3-bg)
EM-8   | INFO       | N/A            | N/A            | INFO   | Action footer background (canvas on surface)
EM-9   | >= 3.0:1   | 11.66 / 1.59   | 3.33 / 4.08    | PASS   | Action footer borderTop (border-subtle on canvas)
EM-10  | >= 4.5:1   | 2.94 / 6.32    | 5.50 / 7.65    | PASS   | Action footer guidance text (text-muted on canvas)
EM-11  | >= 4.5:1   | 3.20 / 5.80    | 6.18 / 7.02    | PASS   | Force overwrite button text (offline status on canvas)
EM-12  | INFO       | N/A            | N/A            | INFO   | Diff container background (canvas on surface)
EM-13  | INFO       | N/A            | N/A            | INFO   | Diff header background (surface on canvas)
EM-14  | >= 3.0:1   | 12.20 / 1.45   | 3.48 / 3.73    | PASS   | Diff header borderBottom (border-subtle on surface)
EM-15  | >= 4.5:1   | 1.09 / 16.30   | 17.85 / 16.98  | PASS   | Diff file path text (text-primary on surface)
EM-16  | >= 4.5:1   | 2.54 / 6.98    | 7.13 / 10.18   | PASS   | Diff additions count (diff-added-text on surface)
EM-17  | >= 4.5:1   | 3.35 / 5.29    | 8.31 / 9.35    | PASS   | Diff deletions count (diff-removed-text on surface)
EM-18  | INFO       | N/A            | N/A            | INFO   | Diff added line background (added-bg on canvas)
EM-19  | >= 4.5:1   | 2.31 / 5.87    | 6.49 / 8.55    | PASS   | Diff added line text (added-text on added-bg)
EM-20  | >= 3.0:1   | 2.43 / 7.65    | 3.15 / 8.53    | PASS   | Diff added line border (added-border on canvas)
EM-21  | INFO       | N/A            | N/A            | INFO   | Diff removed line background (removed-bg on canvas)
EM-22  | >= 4.5:1   | 2.74 / 4.87    | 6.80 / 8.60    | PASS   | Diff removed line text (removed-text on removed-bg)
EM-23  | >= 3.0:1   | 3.20 / 5.80    | 6.18 / 7.02    | PASS   | Diff removed line border (removed-border on canvas)
EM-24  | >= 4.5:1   | 7.92 / 2.35    | 5.50 / 7.65    | PASS   | Diff line numbers gutter (text-muted on canvas)
EM-25  | INFO       | N/A            | N/A            | INFO   | Commit input background (canvas on surface)
EM-26  | >= 3.0:1   | 12.20 / 1.45   | 3.48 / 3.73    | PASS   | Commit input border (border-subtle on surface)
EM-27  | >= 4.5:1   | 1.48 / 12.59   | 17.06 / 18.59  | PASS   | Commit input text (text-primary on canvas)
EM-28  | >= 4.5:1   | 3.35 / 5.29    | 6.47 / 6.41    | PASS   | Required asterisk indicator (offline status on surface)
EM-29  | >= 4.5:1   | 2.53 / 7.02    | 6.70 / 9.84    | PASS   | Stage all action button (brand-hover on surface)
EM-30  | >= 3.0:1   | 12.20 / 1.45   | 3.48 / 3.73    | PASS   | Staged files list border (border-subtle on surface)
EM-31  | >= 4.5:1   | 1.86 / 9.98    | 4.80 / 9.05    | PASS   | Modified file status text (status-degraded on canvas)
EM-32  | >= 4.5:1   | 1.48 / 12.59   | 7.24 / 15.69   | PASS   | Clean file status text (text-secondary on canvas)
----------------------------------------------------------------------------------------
Total Audit Items: 32, Failures: 0
ALL AUDIT ITEMS COMPLIANT WITH WCAG 2.2 AA SPECIFICATIONS.
```

---

## 3. 기술적 판단 및 설계 정합성

### 3.1 모달 백드롭 스크림 (Modal Backdrop Scrim)의 대비 규격 제외 근거
- 모달 대화상자 배후의 `backgroundColor: var(--color-bg-backdrop)` (`rgba(0, 0, 0, 0.75)`)는 배경 페이지 콘텐츠를 어둡게 조광(dimming)하여 모달 포커스를 유도하는 비텍스트 시각 스크림(scrim overlay)입니다.
- WCAG 2.2 SC 1.4.11(Non-text Contrast)은 사용자가 상호작용하는 UI 컨트롤의 경계선(boundary) 및 상태(state)에 적용되며, 장식적/화면 감광 목적의 반투명 오버레이 레이어는 컨트롤 본체가 아니므로 SC 1.4.11 및 SC 1.4.3(Text Contrast) 적용 대상에서 명백히 제외(INFO)됩니다.

### 3.2 Diff 라인 배경 위 코드 텍스트 4.5:1 대비 보장
- 베이스 `DiffViewer.tsx`는 추가/삭제 줄에 각각 `rgba(46, 160, 67, 0.15)` 및 `rgba(248, 81, 73, 0.15)` 배경을 고정하고, 그 위에 `#3fb950`, `#f85149`를 배치하여 라이트 모드에서 심각한 대비 결손(2.31:1, 2.74:1)을 유발하고 있었습니다.
- 신설된 `--color-diff-added-text` (`#166534` / `#4ade80`) 및 `--color-diff-removed-text` (`#991b1b` / `#fca5a5`)는 추가/삭제 배경색 위에서 라이트 6.49:1 / 6.80:1, 다크 8.55:1 / 8.60:1로 WCAG SC 1.4.3의 4.5:1 기준을 넉넉히 상회하도록 설계되었습니다.

### 3.3 Fail-Closed 프로젝션 설정 테이블 및 프로토타입 주입 차단
- 각 에디터 모달의 상태 룩업 헬퍼(`getConflictStatusConfig`, `getConflictResolutionActionConfig`, `getDiffLineTypeConfig`, `getGitFileStatusConfig`, `getGitStageStateConfig`)는 단순 `in` 연산자 대신 `Object.hasOwn`을 강제하여 `toString`, `constructor`, `__proto__`, `valueOf` 등 프로토타입 오염 공격 및 계약 외 미등록 키를 `UNKNOWN (<key>)` 및 `var(--color-status-unknown)` 토큰으로 안전 강등하도록 봉인되었습니다 (변이 M7, M25, M33, M36 100% 사살).

---

## 4. 증거 및 검증 결과 (Evidence & Verification)
- `python tools/reproduce_c280_contrast.py` -> 32/32 PASS/INFO (0 failures).
- `cd apps/web && npx tsc -b` -> exit code 0, 0 errors.
- `npm run build` -> exit code 0, production bundle generated.
- `npx vitest run tests/acc09-contrast-tokens.test.tsx` -> 44/44 PASS.
- `pytest tests/test_route_coverage.py` -> 41/41 PASS.
- `python tools/check_frontend_integrity.py` -> PASS (9대 무결성 규칙 위반 0건).
- `python tools/check_contract_bindings.py` -> PASS.
- `python tools/check_docs.py` -> PASS.
- `python tools/check_doc_path_citations.py --ratchet --base-ref 94c99c72` -> PASS.
- `python tools/sync_obsidian.py --check` -> PASS (0 conflicts).
- `tools/test_c280_mutations.py` -> 40/40 KILLED on clean commit A (`f1c898ce`), sealed in Commit B (`b6ba31fb`) with byte-clean restore verification.
