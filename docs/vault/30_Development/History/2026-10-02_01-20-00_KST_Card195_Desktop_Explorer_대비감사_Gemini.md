# 2026-10-02 01:20:00 KST — Card 195: 데스크톱 탐색기 (ResourceExplorer & InvFileExplorer) Light/Dark 명도 대비 전수 감사 및 디자인 토큰 승격 (Gemini)

- **문서 ID**: HIST-GEMINI-CARD195-DESKTOP-EXPLORER-CONTRAST
- **작업 branch**: gent/gemini/c195-desktop-explorer-contrast
- **Base commit**: db37dbc53f2e45ed987b9ed0e0b81ed88f2a7644 (PR #290 HEAD)
- **KST 시각**: 2026-10-02 01:20:00 KST
- **작업자**: Gemini (Frontend / UI / 접근성)
- **독립 검토자 요청**: Claude UI (UI/접근성 축), Codex (계약/디자인 토큰/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 작업 개요 및 감사 목적

ACC-09(접근성 명도 대비 전수 적합화) 트랙의 일환으로, 데스크톱 UI에서 가장 빈번하게 조회 및 조작되는 양대 탐색기 화면의 색상 리터럴을 전수 감사하고 디자인 토큰으로 승격하였습니다.

- **대상 파일**:
  1. pps/web/src/features/desktop/ResourceExplorer.tsx (기존 baseline 리터럴: **390건**)
  2. pps/web/src/features/desktop/InvFileExplorer.tsx (기존 baseline 리터럴: **124건**)
- **감사 및 조치 결과**:
  - 두 파일 모두 하드코딩 색상 리터럴을 **0건**으로 전수 해소 (감소율: **100%**).
  - pps/web/tests/acc09-contrast-tokens.test.tsx의 Fail-Closed COLOR_LITERAL_MULTISET_BASELINE에서 두 파일의 허용 multiset을 {} (0건)으로 전면 갱신하여 순수 감소 래칫을 강제.
  - 전역 ar(--color-border-subtle) 사용 횟수가 141건에서 **232건**(+91건)으로 증가하였으며, 사용 파일 수가 21개에서 **22개**(InvFileExplorer.tsx 신규 편입)로 래칫 단언 갱신.
  - 신규 인덱스 CSS 토큰 정의 추가 없이, 기존 확립된 시맨틱 디자인 토큰 체계(--color-brand-primary, --color-bg-subtle, --color-bg-surface, --color-text-primary, --color-text-muted, --color-text-inverse, --color-status-online, --color-status-offline, --color-status-degraded, --color-border-subtle)만을 활용하여 WCAG 2.2 AA 기준(텍스트 >= 4.5:1, UI 경계 >= 3.0:1)을 Light 및 Dark 양대 테마에서 100% 충족.

---

## 2. 명도 대비 전수 감사 및 개선 결과표

### 2.1 주요 결함 리터럴 실측치 비교 (Before vs After)

| 요소 / 위치 | 이전 리터럴 | 이전 렌더 배경 | 이전 대비율 (Light) | 이전 판정 | 신규 디자인 토큰 | 신규 대비율 (Light) | 신규 대비율 (Dark) | WCAG AA 충족 여부 |
|---|---|---|---|---|---|---|---|---|
| **부차/보조 텍스트 (Muted text)**<br>(ResourceExplorer, InvFileExplorer 전반) | #94a3b8 | #ffffff (surface) | **2.56:1** | **FAIL** (< 4.5:1) | ar(--color-text-muted) | **5.25:1** | **5.78:1** | **PASS (>= 4.5:1)** |
| **보조 텍스트 (Muted on subtle)**<br>(노드 하트비트, 용량 카드 라벨 등) | #94a3b8 | #f1f5f9 (subtle) | **2.32:1** | **FAIL** (< 4.5:1) | ar(--color-text-muted) | **4.76:1** | **4.86:1** | **PASS (>= 4.5:1)** |
| **정상/가용 텍스트 (Success/Online)**<br>(복제본 정상, 온라인 배지 등) | #34d399 | #ffffff (surface) | **1.92:1** | **FAIL** (< 4.5:1) | ar(--color-status-online) | **5.02:1** | **7.79:1** | **PASS (>= 4.5:1)** |
| **정상 배지 텍스트 (Online on subtle)**<br>(복제본 정상 배지, 온라인 카운터) | #34d399 | #f1f5f9 (subtle) | **1.74:1** | **FAIL** (< 4.5:1) | ar(--color-status-online) | **4.58:1** | **6.44:1** | **PASS (>= 4.5:1)** |
| **경고/장애 텍스트 (Offline/Error)**<br>(스토리지/노드 통신 에러 배너) | #f87171 | #ffffff (surface) | **3.44:1** | **FAIL** (< 4.5:1) | ar(--color-status-offline) | **5.86:1** | **4.79:1** | **PASS (>= 4.5:1)** |
| **장애 배너 텍스트 (Offline on subtle)**<br>(ResourceExplorer 에러 배너) | #ef4444 | #f1f5f9 (subtle) | **3.98:1** | **FAIL** (< 4.5:1) | ar(--color-status-offline) | **5.30:1** | **4.79:1** | **PASS (>= 4.5:1)** |
| **강조/링크 텍스트 (Brand/Accent)**<br>(선택 탭, URI 강조, 신선도 고지) | #60a5fa | #ffffff (surface) | **2.53:1** | **FAIL** (< 4.5:1) | ar(--color-brand-primary) | **5.44:1** | **8.23:1** | **PASS (>= 4.5:1)** |
| **강조 텍스트 (Brand on subtle)**<br>(신선도 고지, 활성 필터 버튼) | #60a5fa | #f1f5f9 (subtle) | **2.29:1** | **FAIL** (< 4.5:1) | ar(--color-brand-primary) | **4.93:1** | **6.88:1** | **PASS (>= 4.5:1)** |
| **대화형 테두리 (Border on surface)**<br>(노드 카드, 입력창, 컨테이너) | #334155 / #374151 | #ffffff (surface) | **9.25:1** (다크 1.72:1) | **FAIL** (Dark < 3.0:1) | ar(--color-border-subtle) | **3.53:1** | **3.65:1** | **PASS (>= 3.0:1)** |
| **대화형 테두리 (Border on subtle)**<br>(용량 카드, 주소창, 배지 테두리) | #475569 / #e2e8f0 | #f1f5f9 (subtle) | **1.13:1** (라이트 e2e8f0) | **FAIL** (Light < 3.0:1) | ar(--color-border-subtle) | **3.20:1** | **3.04:1** | **PASS (>= 3.0:1)** |

---

## 3. 세부 파일별 조치 내역

### 3.1 pps/web/src/features/desktop/ResourceExplorer.tsx
- **리터럴 감축**: 390건 $ightarrow$ **0건** (전수 제거).
- **상세 변경 사항**:
  - &#123;node_id&#125; 엔티티가 정규식 헥사코드(#123, #125)로 오인식되던 문제를 {'{node_id}'}로 정정하여 불필요한 리터럴 오탐 제거.
  - 중복 선언되어 있던 4개 버튼의 redundant order: 'none' 속성 정리 (vite/esbuild 빌드 경고 0건 해소).
  - 신선도 고지(
ode-freshness-notice): ar(--color-brand-primary) 텍스트 및 테두리, ar(--color-bg-subtle) 배경 결속.
  - 라이브니스 스윕 버튼(liveness-sweep-btn): ar(--color-bg-subtle) 배경, ar(--color-status-offline) 텍스트 및 테두리 결속 (Light 5.86:1, Dark 4.79:1).
  - 온라인 노드 배지: ar(--color-bg-subtle) 배경, ar(--color-status-online) 텍스트 및 테두리 결속 (Light 4.58:1, Dark 6.44:1).
  - 논리 용량 카드 4종(logical-vcpu-card, logical-ram-card, logical-gpu-card, logical-storage-card): ar(--color-bg-subtle) 배경, ar(--color-border-subtle) 테두리, ar(--color-text-primary) 및 ar(--color-text-muted) 텍스트 결속.
  - 필터 버튼(ilter-all-btn 등): 활성 상태 ar(--color-bg-subtle) 배경, ar(--color-brand-primary) 텍스트 및 테두리 결속.
  - 물리 노드 카드(
ode-card-): 선택 상태 ar(--color-bg-subtle) 배경 + ar(--color-brand-primary) 테두리, 비선택 상태 ar(--color-bg-surface) 배경 + ar(--color-border-subtle) 테두리 결속.
  - 노드 오류 배너(
odes-fetch-error-banner): ar(--color-bg-subtle) 배경, ar(--color-status-offline) 텍스트 및 테두리 결속.

### 3.2 pps/web/src/features/desktop/InvFileExplorer.tsx
- **리터럴 감축**: 124건 $ightarrow$ **0건** (전수 제거).
- **상세 변경 사항**:
  - 주소창(inv-address-bar): ar(--color-bg-subtle) 배경, ar(--color-text-primary) 텍스트, ar(--color-border-subtle) 테두리 결속.
  - 네비게이션 버튼(inv-navigate-btn), 체크아웃 버튼, SHA-256 검증 실행 버튼: ar(--color-brand-primary) 배경, ar(--color-text-inverse) 텍스트 결속 (Light 5.17:1, Dark 7.02:1).
  - 선택 파일 행(ile-row-): ar(--color-brand-subtle) 배경, ar(--color-brand-primary) 테두리 결속 (Light 4.58:1, Dark 5.81:1).
  - 무결성 배지(integrity-badge): 상태별 ar(--color-status-degraded) / ar(--color-status-online) / ar(--color-status-offline) 결속, ar(--color-bg-subtle) 배경.
  - 복제본 건강 배지(
eplica-healthy-badge): ar(--color-bg-subtle) 배경, ar(--color-status-online) 텍스트 및 테두리 결속.
  - 복제본 장애 배지(
eplica-degradation-badge): ar(--color-bg-surface) 배경, ar(--color-status-offline) 텍스트 및 테두리 결속.

### 3.3 pps/web/tests/acc09-contrast-tokens.test.tsx
- **Multiset Baseline 래칫 갱신**:
  - COLOR_LITERAL_MULTISET_BASELINE['features/desktop/ResourceExplorer.tsx'] = {}
  - COLOR_LITERAL_MULTISET_BASELINE['features/desktop/InvFileExplorer.tsx'] = {}
  - ar(--color-border-subtle) 발생 수 232건, 파일 수 22개로 fail-closed 단언 갱신.
- **Card 195 DOM 테스트 블록 신설**:
  - ACC-09 / Card 195: Desktop Explorers (ResourceExplorer & InvFileExplorer) DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification
  - 실제 렌더링된 DOM 요소의 style에서 CSS 변수를 직접 추출(helperExtractVar), 상위 컨테이너 배경과 결합하여 Light 및 Dark 테마에서 동적 명도 대비를 단언.
  - abricObservation.locations spy를 통해 불필요한 네트워크 통신을 차단하고 inally에서 완벽 복원.
- **Revert-Fail Probes (Probes 24 ~ 27) 추가**:
  - Probe 24: 데스크톱 탐색기 과거 muted 텍스트 리터럴 #94a3b8 on Light surface/subtle (2.56:1, 2.32:1) strict fail 단언.
  - Probe 25: 데스크톱 탐색기 과거 online/healthy 리터럴 #34d399 on Light surface/subtle (1.92:1, 1.74:1) strict fail 단언.
  - Probe 26: 데스크톱 탐색기 과거 offline/error 리터럴 #f87171 on Light surface/subtle (3.44:1) strict fail 단언.
  - Probe 27: 데스크톱 탐색기 과거 primary/accent 리터럴 #60a5fa on Light surface/subtle (2.53:1, 2.29:1) strict fail 단언.

---

## 4. 변이 사살 실측 (Mutations M1 ~ M4, 100% Killed)

배경 바꿔치기, 토큰 되돌림 등 4종 변이를 적용하여 cc09-contrast-tokens.test.tsx가 이를 즉시 감지하여 fail하는지 실측하였습니다 (	est_c195_mutations.py).

| 변이 | 변이 내용 | 결과 | 사살 단언 |
|---|---|---|---|
| **H0** | 원본 (Clean HEAD) | **14 passed** | 정상 기준선 |
| **M1** | ResourceExplorer freshnessNotice 배경을 ar(--color-brand-primary)로 치환 (1:1 fg/bg) | **KILLED** (exit 1) | Freshness notice light text contrast >= 4.5:1 및 bg 단언 |
| **M2** | InvFileExplorer 복제본 정상 배지 텍스트를 과거 리터럴 #34d399로 되돌림 | **KILLED** (exit 1) | Replica healthy badge color must bind to var(--color-status-online) 및 multiset 래칫 |
| **M3** | InvFileExplorer 주소창 배경을 ar(--color-text-primary)로 치환 (1:1 fg/bg) | **KILLED** (exit 1) | Address bar light text contrast >= 4.5:1 및 bg 단언 |
| **M4** | ResourceExplorer 노드 하트비트 텍스트를 과거 리터럴 #94a3b8로 되돌림 | **KILLED** (exit 1) | Node heartbeat color must bind to var(--color-text-muted) 및 multiset 래칫 |

---

## 5. 잔여 리터럴 백로그 현황

- ResourceExplorer.tsx: **0건 (완전 해소)**
- InvFileExplorer.tsx: **0건 (완전 해소)**
- 양대 탐색기 화면의 잔여 저대비 리터럴 결함: **0건**.

---

## 6. 종합 검증 게이트 통과 증거 (Full Verification Gates)

| 검증 도구 | 실행 명령 | 결과 | 비고 |
|---|---|---|---|
| Vitest 접근성 스위트 | 
pm test -- tests/acc09-contrast-tokens.test.tsx | **14 passed (14)** (exit 0) | 탐색기 DOM 동적 대비 및 래칫 검증 |
| Vitest 관련 스위트 전체 | 
pm test -- tests/acc09-contrast-tokens.test.tsx tests/resource-explorer-dom.test.tsx tests/inv-file-explorer-dom.test.tsx ... (9개 스위트) | **139 passed (139)** (exit 0) | 탐색기 기능/DOM/상태 회귀 0건 |
| 변이 테스트 하네스 | python test_c195_mutations.py | **4 / 4 killed (100%)** | M1~M4 전원 즉시 사살 |
| TypeScript 컴파일 | cd apps/web && npx tsc -b | **0 errors (exit 0)** | Strict 타입 점검 통과 |
| Vite 프로덕션 빌드 | cd apps/web && npm run build | **built in 7.59s (exit 0)** | 프로덕션 번들 정상 생성 |
| 라우트 커버리지 및 불변식 | pytest tests/test_route_coverage.py | **41 passed (exit 0)** | 라우트/EvidenceViewer 불변식 통과 |
| 프런트엔드 무결성 점검 | python tools/check_frontend_integrity.py | **93 files scanned, 0 violations (exit 0)** | 9대 무결성 규칙 전수 준수 |
| 계약 바인딩 점검 | python tools/check_contract_bindings.py | **55 fixtures, 20 bound types (exit 0)** | 서빙 앵커 및 리플레이 가드 통과 |
| 문서 일관성 점검 | python tools/check_docs.py | **PASS (1072 docs, exit 0)** | 문서 일관성 검사 통과 |
| 문서 경로 인용 래칫 | python tools/check_doc_path_citations.py --ratchet --base-ref c41fe2da | **290 baseline, 0 stale (exit 0)** | 인용 래칫 유지 |
| Git 공백/충돌 검사 | git diff --check | **Clean (exit 0)** | CR 0 바이트, 충돌 마커 0 |

---

## 7. 인계 및 다음 단계

- **상태**: PR 생성 후 Claude UI 및 Codex에 독립 검토 요청 (봇 호출 태그 0건 준수).
- **다음 담당자**: Claude UI (UI/접근성 명도 대비 검토), Codex (계약/디자인 토큰/불변식 검토).
