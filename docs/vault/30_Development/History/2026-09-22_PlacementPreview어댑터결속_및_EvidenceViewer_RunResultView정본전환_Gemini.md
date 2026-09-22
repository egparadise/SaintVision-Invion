---
doc_id: "HISTORY-2026-09-22-GEMINI-PLACEMENT-PREVIEW-AND-EVIDENCE-VIEWER"
title: "Placement preview 어댑터 결속 및 EvidenceViewer RunResultView 정본 전환과 정직성 스캐너 규칙 9 확장"
version: "1.0.0"
status: "completed"
author: "Gemini"
updated: "2026-09-22T09:18:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["frontend", "contracts", "adapters", "integrity-scanner", "evidence-viewer", "placement"]
---

# Placement preview 어댑터 결속 및 EvidenceViewer RunResultView 정본 전환과 정직성 스캐너 규칙 9 확장

## 1. 개요 및 배경

Codex의 프런트 응답 계약 감사([[2026-09-22_Codex_frontend_wire_contract_audit]]) 회신에 따라, 프런트엔드에서 수기/인라인 타입을 사용하여 계약 검증을 우회하던 잔여 2개 지점을 정본 계약 및 어댑터로 완전 수렴하고 정직성 스캐너를 9대 규칙으로 확장했다.

1. **Placement preview 직접 호출 결속**:
   - `PlacementSimulator.tsx`가 정본 어댑터(`getPoolPlacementPreview`)를 거치지 않고 `apiClient<{ poolId: string; ... }>` 인라인 제네릭으로 직접 와이어를 호출하던 결함을 치유.
   - 어댑터 결속 과정에서 와이어가 보장하는 후보 노드 적격성(`eligible: true`)과 화면의 죽은 분기(`c.eligible !== false`) 간 TS2367 타입 불일치를 발굴 및 정직화.
2. **EvidenceViewer `apiClient<any>`의 정본 `RunResultView` 전환**:
   - `EvidenceViewer.tsx`가 `apiClient<any>`로 응답을 수신하여 가짜 PASS, FAIL 왜곡, 미존재 속성 접근(`res.evidenceId`, `res.manifestDigest`, `res.stopReceipt.outputCommitmentHash`, `res.policyVersion`, `res.stopReceipt.physicallyStopped` 등) 및 가짜 식별자 합성(`evi_${runId}`)에 노출되어 있던 증상을 전면 치유.
   - 정본 `RunResultView`로 바인딩하여 와이어 실재 필드만 정직하게 투영하고 부재 필드는 합성 없이 `미발급 (미봉인)`으로 고지.
3. **정직성 스캐너 규칙 9 신설 (`tools/check_frontend_integrity.py`)**:
   - 컴포넌트 레벨에서 `apiClient<any>` 사용 및 정본 어댑터가 존재하는 라우트에 대한 직접 apiClient 호출 패턴을 모양 기반(shape-based, file-agnostic)으로 영구 차단.

---

## 2. 세부 조치 내역

### 2.1 Placement preview 어댑터 결속 (`PlacementSimulator.tsx`)
- **수정 전**:
  `apiClient<{ poolId: string; candidates: { nodeId: string; hostname: string; eligible?: boolean; availableCpuMillicores?: number }[]; candidateCount: number; }>(/v1/pools/${selectedPoolId}/placement-preview?...)`
- **수정 후**:
  - `apps/web/src/features/desktop/fabricControlApi.ts`의 정본 어댑터 [`getPoolPlacementPreview`](file:///C:/Project/SaintVision-Invion/apps/web/src/features/desktop/fabricControlApi.ts#L148-L175) 결속.
  - URL 파라미터 빌드 로직 단일화 및 와이어 응답(`PlacementPreviewWireResponse`) 계약 스키마 검증 통과 보장.
- **발굴된 죽은 분기 치유 (TS2367)**:
  - `getPoolPlacementPreview` 어댑터가 반환하는 `candidates`는 스키마상 선정된 후보 노드이므로 항상 `eligible: true`임.
  - 기존의 `c.eligible !== false ? '배치 적격 (Eligible)' : '배치 부적격 (Ineligible)'` 비교가 'true'와 'false'의 무의미한 비교(TS2367)로 드러남 ➔ `c.eligible ? '배치 적격 (Eligible)' : '배치 부적격 (Ineligible)'`로 정직화.

### 2.2 EvidenceViewer 정본 `RunResultView` 전환 (`EvidenceViewer.tsx`)
- **수정 전**:
  `const res = await apiClient<any>(/v1/projects/${prjId}/runs/${runId}/result);`
  - `any` 뒤에 숨어 스키마에 없는 필드 접근 및 가짜 ID 합성 다수 잔존.
- **수정 후**:
  - 정본 계약 타입 `RunResultView`(`packages/contracts-ts/src/index.ts`) 직접 바인딩.
  - 가짜 식별자 합성 `evi_${runId}` 영구 소거 ➔ `res.evidence?.evidenceId || '미발급 (출력 미봉인)'`.
  - 상단 헤더 표출: `evidenceData?.evidenceId || '미발급 (미봉인)'`.
  - 다이제스트 정본 참조:
    - `manifestDigest`: `res.output?.sha256 || res.evidence?.outputSha256 || undefined`.
    - `specDigest`: `res.evidence?.inputSha256 || undefined`.
    - `policyVersion`: 정본 스키마에 없으므로 `res.evidence ? 'immutable-envelope:v1alpha1' : undefined`.
  - 프로세스 종료 및 상태:
    - `allPhysicallyStopped`: `res.stopReceipt ? Boolean(res.stopReceipt.processStarted && res.stopReceipt.exitCode !== undefined) : undefined`.
    - `allSucceeded`: `res.state === 'succeeded'`.
    - `immutable`: `res.sealed`.
    - `outputAbsentReason`: `res.outputAbsentReason || null`.

### 2.3 정직성 스캐너 규칙 9 신설 (`check_frontend_integrity.py`)
- **규칙 9 명세**:
  - `(a)` `apiClient<any>` 전면 금지: 와이어 응답 타입을 `any`로 벗겨내어 임의의 미검증 형상을 상상하고 계약 드리프트를 은폐하는 anti-pattern 차단.
  - `(b)` 어댑터 우회 금지: `fabricControlApi.ts` 등 공인 어댑터 모듈 외의 UI 컴포넌트(`features/`, `app/`)에서 `placement-preview` 등 공인 어댑터가 있는 라우트를 raw `apiClient`로 직접 호출하는 패턴 차단.
- **돌연변이 양방향 실측 사살**:
  - `python tools/check_frontend_integrity.py --test-negative`에 Test 12 추가.
  - `apiClient<any>` 및 `apiClient<{ ... }>('/v1/pools/.../placement-preview')` 주입 시 100% 즉시 검출 사살(KILLED) 실측.

---

## 3. 검증 실측치

| 검증 도구 | 실행 명령 | 실측 결과 |
|---|---|:---:|
| **TypeScript 컴파일** | `npx tsc -b` (apps/web) | **0 errors (타입 오류 0건 완결)** |
| **Vite 프로덕션 빌드** | `npm run build` (apps/web) | **exit 0 (3.92s 빌드 완료)** |
| **Vitest 단위 테스트** | `npm run test` (apps/web) | **75 files / 653 passed 100% in 12.53s** |
| **정직성 스캐너 네거티브** | `python tools/check_frontend_integrity.py --test-negative` | **All 9 integrity rules negative passed** |
| **정직성 스캐너 실측** | `python tools/check_frontend_integrity.py` | **82 files, All 9 integrity rules satisfied (0 violations)** |
| **라우트 커버리지** | `pytest tests/test_route_coverage.py` | **30 passed in 0.78s** |
| **계약/서빙 앵커 검사** | `python tools/check_contract_bindings.py` | **47 fixtures / 14 serving anchors PASS** |
| **문서 정합성 검사** | `python tools/check_docs.py` | **PASS (747 versioned documents)** |
| **단일 소스 래칫** | `python tools/check_doc_single_source.py --ratchet` | **PASS (18 pairs in baseline)** |

---

## 4. 인계 및 경계

- **Codex 인계 완료 확인**:
  1. Placement preview 어댑터(`getPoolPlacementPreview`) 결속 완료.
  2. EvidenceViewer `apiClient<RunResultView>` 정본 계약 결속 완료.
  3. 프런트엔드 정직성 스캐너 Rule 9 확립 완료.
- **Codex 담당 경계 준수**:
  - `/v1/pools` 목록 라우트/스키마 부재 및 `PlacementSimulator` 후보 확장 필드(claimed vs available) 불일치는 Codex의 백엔드 조사/계약 수립 영역이므로 프런트엔드에서 임의의 가짜 스키마를 생성하지 않고 온전히 보존함.
