---
doc_id: "HIST-20261001-C183-S12FE-001"
title: "Card 183 (S12-FE) 릴리스 선언서(Release Manifest) 및 운영자 인수 서버 경로 결속 기록"
version: "1.2.0"
status: "proposed"
author: "Gemini"
created: "2026-10-01T18:50:00+09:00"
updated: "2026-10-01T20:20:00+09:00"
source_of_truth: "Git"
base_sha: "4114f8ba"
task_ids: ["S12-FE", "S12-BE"]
tags: ["s12", "release-manifest", "acceptance", "binding", "read-only", "security-boundary", "gemini"]
---

# Card 183 (S12-FE) 릴리스 선언서(Release Manifest) 및 운영자 인수 서버 경로 결속

## 1. 1단계 전수 현황 분석 (Phase 1 Codebase Origin Analysis)

카드 183 1단계 지침에 따라 `apps/web/src` 내 `ReleaseManifest`, `operatorSignOff`, `localSimulationCompleted`의 기존 출처(고정값, fixture, 로컬 계산, API)를 전수 식별하고 정리한 표는 아래와 같다.

| 항목 / 상태 필드 | 선언 및 사용 위치 | 기존 출처 유형 | 상세 내용 및 동작 방식 | 카드 183 2단계 실서버 결속 상태 |
|---|---|---|---|---|
| `ReleaseManifest` (타입/모델) | `apps/web/src/contracts/types.ts:516-526`, `deploymentEngine.ts`, `IntranetDeploymentView.tsx` | 프런트엔드 지역 합성 타입 (Client Synthetic) | DB에 존재하지 않는 FE 전용 필드(`imageDigest`, `targetClusters`, `totalNodes`, `smokePassedRatio`, `knownLimitations` 등)를 포함한 정적 인터페이스. `DeploymentManager.releaseManifest`의 모의 픽스처로 사용됨. | `apps/web/src/contracts/release-manifest-response.ts` 및 `apps/web/src/contracts/release-manifest-detail-response.ts` 정본 스키마 기반 계약 타입으로 분리 결속. 실 서버 `ReleaseManifestResponse` 및 `ReleaseManifestDetailResponse` 도입. |
| `releaseManifest` (인스턴스 데이터) | `deploymentEngine.ts:129-143`, `IntranetDeploymentView.tsx:17` | 고정 정적 픽스처 (In-Memory Fixture) | `REL-2026-PILOT-RC`, `v1.0.0-pilot-rc`, 하드코딩된 sha256 및 commit sha `c323f55`로 초기화되어 `DeploymentManager` 내부 상태로만 관리됨. 백엔드 REST API 미연결. | `GET /v1/release-manifests` (목록) 및 `GET /v1/release-manifests/{release_id}` (상세) 실서버 API를 호출하여 동적 수신. 테넌트 빈 목록(`items: []`) 시 날조 기본값 없이 '기록 없음' 빈 상태 표출. |
| `operatorSignOff` (서명 여부) | `deploymentEngine.ts:142`, `IntranetDeploymentView.tsx:180-190`, `apps/web/src/contracts/types.ts:525` | 하드코딩 기본값 `false` + 로컬 메모리 토글 | `manager.signOffRelease()` 호출 시 인메모리 객체의 `operatorSignOff`를 `true`로 단순 플립. 서버에 저장되거나 전송되지 않음. DEF-S12에서 "서버 route 부재로 false 유지"로 기록된 핵심 결함 항목. | 서버 계산값(Authoritative Server Field)으로 결속. 서버의 `acceptance_records` 행 중 `outcome='accepted'` 및 `accepted_manifest_sha256 === manifest.manifest_sha256` 조건을 검증한 결과만 `true`로 관측 표출. 미서명 시 `operatorSignOff: false (미서명)` 정직하게 표출. |
| `localSimulationCompleted` (모의 완료) | `IntranetDeploymentView.tsx:18, 56, 185, 630` | 로컬 리액트 상태 (React In-Memory State) | `useState(false)`. 운영자 로그인 세션 및 operator/admin 권한 검사 후 `handleSignOff()`를 통해 `true`로 설정되는 브라우저 로컬 시뮬레이션 전용 플래그. | 실서버의 권위적 `operatorSignOff`와 엄격히 분리된 로컬 모의 시뮬레이션 상태로 온전히 유지. 클라이언트에서 실서버 수락을 날조 생성하지 못하도록 보안 경계 고수 (쓰기 UI 원천 차단). |
| 릴리스 후보 및 롤백 (`ReleaseCandidate`) | `ReleaseCandidateView.tsx:15, 35-49`, `releaseEngine.ts` | 인메모리 시뮬레이션 (Local Mock Engine) | `ReleaseCandidateView`는 `ReleaseManifest`나 `operatorSignOff`를 직접 사용하지 않고, 자체 `ReleaseManager`의 `ReleaseCandidate[]` (`REL-2026-09-PROD`, `REL-2026-08-STABLE`) 및 7종 SLO 메트릭 측정과 롤백 절차를 시뮬레이션함. | 본 카드 범위 외. 백엔드 릴리스 제어 API 미노출 고지 배너 유지. |

---

## 2. 2단계 구현 내역 (Implementation Details)

Claude 카드 182(PR #280)에서 생성된 정본 계약 스키마 5종(`contracts/release-*.schema.json`) 및 읽기 전용 REST 라우트(`GET /v1/release-manifests`, `GET /v1/release-manifests/{release_id}`)를 프런트엔드 `apps/web`에 온전히 결속함:

1. **계약 생성 및 검증 자동화 (`apps/web/scripts/api-response-contracts.mjs`)**:
   - `release-manifest-response`, `release-manifest-detail-response`, `release-manifest-page-response`, `release-acceptance-response`, `release-component-response` 5종 계약 등록.
   - `npm run contracts:generate` 및 `npm run contracts:check` 실행 $\rightarrow$ 40개 API 응답 TypeScript 타입과 JSON Schema 일치 확인 (exit 0).

2. **API 관측 계층 구현 (`apps/web/src/shared/api/releaseObservation.ts`)**:
   - `fetchReleaseManifests(options)`: `GET /v1/release-manifests`를 호출하여 테넌트 릴리스 목록(`ReleaseManifestPageResponse`)을 수신하고, shape 검증 수행.
   - `fetchReleaseManifestDetail(releaseId)`: `GET /v1/release-manifests/${encodeURIComponent(releaseId)}`를 호출하여 릴리스 상세 및 수락 결정 목록(`ReleaseManifestDetailResponse`)을 수신.
   - `isValidReleaseManifest`: 런타임 fail-closed 계약 검증기 구현 (`manifestSha256` 64 hex, `operatorSignOff` boolean, `componentCount`, `acceptanceCount` 등).

3. **화면 결속 (`apps/web/src/features/deployment/IntranetDeploymentView.tsx`)**:
   - **Section 3-A [서버 실제 관측] 공식 릴리스 선언서 및 운영자 인수 관측**:
     - 실서버 라우트 결속 배너 표출 (`data-testid="deployment-manifest-server-banner"`).
     - **빈 상태 (기록 없음)**: 테넌트에 등록된 릴리스가 없을 때(`items: []`) 날조 기본값(가짜 릴리스 ID 또는 목 SHA) 없이 명시적 빈 상태(`data-testid="deployment-manifest-empty-state"`) 표출.
     - **미서명 상태**: 수락 행 부재 시 권위적 서버 필드 `operatorSignOff: false`를 `미서명 (operatorSignOff: false)`으로 정직하게 표출.
     - **403 / 404 오류 처리**: 403 Forbidden (`deployment-manifest-error-403`) 및 404 Not Found (`deployment-manifest-error-404`) 발생 시 alert role로 사용자에게 정직하게 안내하고 화면 크래시 방지.
     - **수락 결정 및 컴포넌트 관측**: `server-acceptances-list` 및 `server-components-list`를 통해 각 수락의 `outcome`, `manifestMatches`, `decidedAt`, `knownLimitations` 관측 표출.
     - **쓰기 UI 원천 차단 (보안 경계)**: 임의 수락/서명 등록 쓰기 폼이나 POST 요청을 일체 생성하지 않고, 읽기 전용 관측 표출 전용임을 안내하는 쓰기 경계 공지(`server-write-boundary-notice`) 표출.
   - **Section 3-B [로컬 모의 시뮬레이션] 파일럿 릴리스 선언서 및 운영자 사전 실습**:
     - 기존 AC-12 로컬 시뮬레이션 실습 섹션을 명확히 분리 보존.
     - `localSimulationCompleted`는 브라우저 로컬 인메모리 시뮬레이션 전용 상태로 격리하여, 실서버의 `operatorSignOff`와 혼동되지 않도록 유지.
     - 기존 DEF-S12 결함 수정 시험(`s12-defect-fixes.test.tsx` 23개 전원) 및 배선 무결성 시험(`deployment-release-integrity-wiring.test.tsx` 4개 전원) 100% 무파괴 통과 보존.

4. **단위 및 변이 검증 스위트 (`apps/web/tests/s12-release-manifest-server-binding.test.tsx`)**:
   - 11개 신규 테스트 작성 (Vitest happy-dom):
     - `isValidReleaseManifest` 계약 준수 및 위반 거절.
     - `fetchReleaseManifests` 및 `fetchReleaseManifestDetail` 정상 조회 및 예외 처리.
     - `IntranetDeploymentView` 실서버 메타데이터 및 `operatorSignOff=true` 렌더링.
     - 테넌트 0건 빈 목록 응답 시 날조 기본값 차단 및 `기록 없음` 빈 상태 표출.
     - 수락 부재 시 `미서명 (operatorSignOff: false)` 표출.
     - 403 Forbidden 및 404 Not Found RFC 9457 문제 상세 처리.
     - 로컬 모의 서명 완료 후에도 서버 `operatorSignOff`는 미서명으로 유지되는 분리 불변식 검증.
     - 쓰기 UI 금지 및 `server-write-boundary-notice` 표출 검증.
     - **Revert-Fail 변이 불변식**: 서버 결속을 제거하고 고정 픽스처로 회귀할 경우 동적 서버 속성 단언이 실패함을 고정.

---

## 3. 검증 결과 (Verification Evidence)

| 검증 단계 / 도구 | 명령 및 실행 환경 | 결과 | 상세 내용 |
|---|---|---|---|
| 계약 일치 검사 | `npm run contracts:check` | PASS (exit 0) | 40개 API 응답 TypeScript 타입과 JSON Schema 100% 일치 |
| 신규 단위 테스트 | `npm run test -- s12-release-manifest-server-binding.test.tsx` | PASS (exit 0) | 11 passed (323ms) |
| 기존 S12 회귀 테스트 | `npm run test -- s12-defect-fixes.test.tsx deployment-release-integrity-wiring.test.tsx` | PASS (exit 0) | 27 passed (전원 통과) |
| TypeScript 컴파일 | `npx tsc -b` (apps/web) | PASS (exit 0) | 타입 에러 0건 |
| 프로덕션 번들 빌드 | `npm run build` (apps/web) | PASS (exit 0) | Vite production bundle 정상 생성 |
| 라우트 커버리지 검증 | `pytest tests/test_route_coverage.py` | PASS (exit 0) | 41 passed (exit 0) |
| 프런트엔드 무결성 점검 | `python tools/check_frontend_integrity.py` | PASS (exit 0) | 93개 파일 9대 무결성 규칙 0 위반 (exit 0) |
| 계약 바인딩 점검 | `python tools/check_contract_bindings.py` | PASS (exit 0) | 55개 픽스처 + 20개 커널 응답 타입 앵커 통과 (exit 0) |
| 문서 일관성 검사 | `python tools/check_docs.py` | PASS (exit 0) | 1066개 문서, 24개 원본 해시, 위키 링크 검증 완료 (exit 0) |
| Git 공백/충돌 검사 | `git diff --check` | PASS (exit 0) | 공백 및 충돌 0건 (exit 0) |

---

## 4. Claude UI r1 및 Codex r1 피드백 전수 조치표

| 식별자 | 분류 | 검토 요구사항 | 조치 내용 및 정정 근거 | 상태 |
|---|---|---|---|---|
| **F1 [High]** | 문서 정합성 (CI 차단) | History 문서 내 미존재 경로 4건 인용으로 hosted docs 실패 해소 | • `History` 1절 표의 미존재 인용 4건을 실재하는 레포지토리 경로(`apps/web/src/contracts/...`)로 전수 수정.<br>• `python tools/check_doc_path_citations.py --ratchet --base-ref origin/agent/claude/c182-s12-manifest-routes` 실행 결과 **290 broken citation(s), all in baseline, floor unchanged (PASS, exit 0)** 확인. | **조치 완료** |
| **F2 [Med]** | UI 의미 명확화 | 상단 sign-off 카드가 로컬 상태와 "SIGN-OFF 대기 (백엔드 미연결)" 문구를 유지하여 서버 결속과 모순 | • 상단 KPI 카드 타이틀을 `[로컬 모의] 운영자 인수 서명 (Sign-Off)`으로 명시.<br>• 서브텍스트를 `운영자 확인 대기 중 [로컬 시뮬레이션 전용 — 실서버 연동은 3-A]` 및 `모의 서명자: ... [로컬 모의 — 실서버 서명은 3-A 섹션 관측]`으로 명확히 표기.<br>• 기존 결함 회귀 시험(`s12-defect-fixes.test.tsx` 23 passed)을 100% 보존하면서 실서버 연동(3-A 섹션)과의 혼동을 원천 해소. | **조치 완료** |
| **F3~F5 [Med]** | 시험 결속 및 경계 모의 | 1) 시험이 요청 URL 미단언<br>2) network error / detail 404 미검증<br>3) mock 대신 props 주입<br>4) NODE_ENV=test 시 fetch 끔 분기 제거 | • `IntranetDeploymentView.tsx`에서 테스트 전용 분기(`NODE_ENV === 'test' ? false : true`)를 완전 제거하고 `const shouldFetch = autoFetch ?? true;`로 정규화.<br>• 단위 시험에서 props 주입(`initialManifests`) 대신 `globalThis.fetch` 스파이를 통해 실제 마운트 시의 API 호출을 모의.<br>• 목록 및 상세 엔드포인트의 정확한 호출 URL(`'/v1/release-manifests?cursor=...&limit=...'`, `'/v1/release-manifests/{id}'`), HTTP GET 메서드, 쿼리 파라미터를 직접 단언하여 경로 변경 변이(M2, M3)를 완전 사살. | **조치 완료** |
| **F6 [Low]** | 오류 정직성 | 네트워크 연결 실패 시 500으로 날조 표출 금지 | • `IntranetDeploymentView.tsx` 오류 핸들러에서 problem 없는 네트워크 실패 시 status를 500으로 강제하지 않고 status: 0 / code: 'NET-ERROR'로 기록.<br>• UI에서 `500` 날조 없이 `네트워크 통신 오류`로 정직하게 표출. | **조치 완료** |
| **F7 [Low]** | UI 연속성 | 상세 조회 실패 시 release selector 사라짐 방지 | • 목록에 1개 이상의 릴리스가 조회된 상태라면 상세 조회(detail)가 404 또는 오류로 실패하더라도 `deployment-release-selector`를 상단에 보존 표출.<br>• 운영자가 다른 릴리스를 선택하거나 조회 실패 상태를 인지할 수 있도록 UI 안정성 확보. | **조치 완료** |
| **F8 [Low]** | 페이징 계약 | nextCursor 무시 해소 | • `nextCursor` 상태를 수신 보존하고, 다음 페이지 커서가 존재하는 경우 `deployment-manifest-next-cursor` 엘리먼트에 커서 토큰을 표출. | **조치 완료** |
| **F9 & Codex 차단 1 [High]** | strict wire 계약 검증 | 응답 검증이 strict JSON Schema보다 느슨하고 누락을 성공으로 합성하는 취약점 해소 | • `releaseObservation.ts` 내 5개 계약 스키마에 대해 strict fail-closed 런타임 검증기 구축:<br>  - `componentCount >= 1` (integer) 엄격 검증 (0 거부).<br>  - `additionalProperties: false` (미지 키 전면 거절).<br>  - `components` 각 요소 `{name, kind, digest}` 길이 및 필수 필드 검증.<br>  - `items` 누락 시 빈 배열 합성 금지 (누락 시 즉각 예외 투척).<br>  - `acceptances` 각 요소 `outcome` enum 3종, `manifestMatches` boolean, 64-hex SHA 검증.<br>• Codex 독립 프로브 3종(누락 items 합성, componentCount: 0 + extra, invented outcome) 모두 fail-closed 예외 투척 실측. | **조치 완료** |
| **F10 [Low]** | 접근성 | 빈 상태 role="status" 누락 해소 | • `deployment-manifest-empty-state` 컨테이너에 `role="status"` 및 `aria-live="polite"` 속성 추가. | **조치 완료** |

---

## 5. 변이 검사 전수 실측 결과 (14종 변이 100% 사살)

| ID | 변이 내용 | 검증 가드 및 단언 | 결과 |
|---|---|---|---|
| **M1** | 서버 서명 표시 조건을 항상 `true`로 조작 | `IntranetDeploymentView` 서버 서명 불변식 | **KILLED** |
| **M2** | 목록 경로 `/v1/release-manifests` $
ightarrow$ `/v1/releases` | `fetchSpy` exact list URL assertion | **KILLED** |
| **M3** | 상세 경로 `/v1/release-manifests/` $
ightarrow$ `/v1/release-manifest/` | `fetchSpy` exact detail URL assertion | **KILLED** |
| **M4** | 403 Forbidden 오류 처리 분기 제거 | `deployment-manifest-error-403` alert 단언 | **KILLED** |
| **M5a** | `fetchReleaseManifests`가 fetch 대신 고정 픽스처 반환 | Mock fetch response 단언 | **KILLED** |
| **M5b** | `fetchReleaseManifestDetail`가 고정 서명 픽스처 반환 | Mock fetch response 단언 | **KILLED** |
| **M6** | 네트워크 오류(problem 없음)를 빈 목록으로 삼킴 | Network Error Alert & Empty State Null 단언 | **KILLED** |
| **M7** | 상세 조회 오류 무시 및 상세 렌더 강제 | Detail 404 Alert & Selector Preservation 단언 | **KILLED** |
| **M8** | 서버 서명 표시에 `localSimulationCompleted` OR 결합 | Separation Invariant 단언 | **KILLED** |
| **M9** | 비 test 환경 기본 `autoFetch`를 `false`로 변경 | Default `autoFetch` mount fetch assertion | **KILLED** |
| **M10** | 목록 항목 계약 검증 제거 및 fail-open 허용 | Strict JSON Schema Runtime Guard 단언 | **KILLED** |
| **M11** | 빈 목록일 때 가짜 서명 상세 주입 | Empty State Zero-Fabrication Guard | **KILLED** |
| **M12** | 404 Not Found 오류 처리 분기 제거 | `deployment-manifest-error-404` alert 단언 | **KILLED** |
| **M13** | 미서명 문구를 "서명 완료"로 변조 | Honest Unsigned Label 단언 | **KILLED** |

> **실측 판정**: 14종 변이 중 **14종 전원 사망 (Killed: 14, Survived: 0, 사살율 100%)**.

---

## 6. 부모 #280 Codex F1 계약 변경 후속 조치 (4114f8ba 동기화)

### 6.1 배경 및 계약 변경 사항
PR #280에서 Codex F1 검토 결과, 기존 `acceptance_records`의 `decided_by`가 `users` 테이블 외래키를 참조하나 사람 운영자와 자동화 서비스 주체(예: `svc:release-bot`)를 구분하는 인간 증명(human attestation) 계약이 부재함이 식별됨.
이에 따라 카드 184에서 인간 증명 계약이 정식 도입될 때까지 백엔드 계약에서 `operatorSignOff`는 참이 될 수 없는 불변식(`Literal[False]`, schema `const: false`)으로 고정되고 신규 정족수/차단 사유 필드가 추가됨:
1. `operatorSignOff`: `Literal[False]` (`const: false`, 절대 true 불가)
2. `operatorSignOffBlockedBy`: `"human-attestation-contract-absent"` (`const: "human-attestation-contract-absent"`)
3. `requiredDistinctOperatorCount`: `2` (`const: 2`, 요구 고유 운영자 수 고정 2)
4. `confirmedOperatorCount`: non-negative integer (해시 일치 수락 결정의 고유 사용자 수, 서비스 주체 포함 가능)

### 6.2 프런트엔드 조치 내역
1. **Git 브랜치 동기화**: `origin/agent/claude/c182-s12-manifest-routes` (`4114f8ba`)를 `agent/gemini/c183-s12fe-release-binding`에 no-ff merge (force push 절대 금지).
2. **계약 재생성 및 검증**: `npm run contracts:generate` 및 `npm run contracts:check` 실행 -> 40개 API 응답 TypeScript 타입 동기화 통과 (exit 0).
3. **엄격한 런타임 fail-closed 가드 (`apps/web/src/shared/api/releaseObservation.ts`)**:
   - `isValidReleaseManifest`:
     - `operatorSignOff !== false`인 경우 즉각 `false` 반환 (만약 서버가 true를 반환하면 계약 위반으로 거부).
     - `operatorSignOffBlockedBy !== 'human-attestation-contract-absent'` 검증.
     - `requiredDistinctOperatorCount !== 2` 검증.
     - `confirmedOperatorCount`가 0 이상의 정수인지 엄격 검증.
     - `ALLOWED_MANIFEST_KEYS`에 3개 필드 추가.
4. **UI 정직성 및 표현 정정 (`apps/web/src/features/deployment/IntranetDeploymentView.tsx`)**:
   - 허위 신뢰를 유발하는 `'서버 검증됨'` 및 `'운영자 최종 서명'` 문구를 전면 제거.
   - Section 3-A 카드 타이틀: `운영자 인수 서명 관측 (operatorSignOff)`
   - 상태 라벨: `미서명 (operatorSignOff: false)`
   - 차단 사유 표출: `미서명 — 사람 확인 계약 미구현 (human-attestation-contract-absent)`
   - 정족수 표출: `{confirmedOperatorCount} / {requiredDistinctOperatorCount} 확인 기록 (서명 아님)`
   - 정족수 안내: `해시 일치 수락의 서로 다른 사용자 수 (서비스 주체 포함 가능 — 2명 고유 사람 확인 계약 전 서명 불인정)`
   - 릴리스 선택기 옵션: `{version} ({releaseId}) - 미서명 ({confirmedOperatorCount}/{requiredDistinctOperatorCount} 확인)`
5. **단위 시험 단언 추가 (`apps/web/tests/s12-release-manifest-server-binding.test.tsx`)**:
   - `isValidReleaseManifest refuses operatorSignOff=true as contract violation (Literal[False] guard)`: `operatorSignOff: true` 주입 시 fail-closed 거부 단언.
   - `fetchReleaseManifests throws contract violation if server returns operatorSignOff=true`: 서버 응답에 `operatorSignOff: true`가 올 경우 예외 투척 단언.
   - UI 렌더링 시험에서 `미서명 — 사람 확인 계약 미구현`, `확인 기록 (서명 아님)` 표출 및 `서버 검증됨`/`운영자 최종 서명` 미표출 단언.
   - Vitest 17 passed (전원 통과).

---

## 7. 게이트 및 정적 검증 실측 결과

| 검증 단계 / 도구 | 명령 및 실행 환경 | 결과 | 상세 내용 |
|---|---|---|---|
| **신규 단위/변이 테스트** | `npm run test -- s12-release-manifest-server-binding.test.tsx` | **17 passed** (468ms) | 17개 시험 전원 통과, 14종 변이 100% 사살 |
| **기존 S12 회귀 테스트** | `npm run test -- s12-defect-fixes.test.tsx deployment-release-integrity-wiring.test.tsx` | **27 passed** (전원 통과) | 27개 시험 전원 통과, AC-12 로컬 모의 회귀 0건 |
| **TypeScript 컴파일** | `npx tsc -b` (apps/web) | **에러 0건** | 타입 검사 클린 통과 |
| **프로덕션 번들 빌드** | `npm run build` (apps/web) | **빌드 성공** (9.25s) | Vite production bundle 정상 생성 |
| **화면-백엔드 라우트 커버리지** | `pytest tests/test_route_coverage.py` | **41 passed** (4.09s) | 41개 라우트/화면 검증 전원 통과 |
| **프런트엔드 무결성 점검** | `python tools/check_frontend_integrity.py` | **0 violations** | 93개 파일 9대 무결성 규칙 클린 통과 |
| **계약 바인딩 점검** | `python tools/check_contract_bindings.py` | **PASS** (exit 0) | 55개 픽스처 + 20개 커널 응답 타입 앵커 통과 |
| **문서 일관성 검사** | `python tools/check_docs.py` | **PASS** (exit 0) | 1066개 문서, 24개 원본 해시 통과 |
| **문서 경로 인용 래칫 검사** | `python tools/check_doc_path_citations.py --ratchet --base-ref origin/agent/claude/c182-s12-manifest-routes` | **PASS** (exit 0) | 290 broken citations in baseline, 0 new broken citations (F1 완전 해소) |
| **공백/서식 무결성 검사** | `git diff --check 4114f8ba` | **출력 없음 (PASS)** | 공백/개행 오류 0건 |
| **금지 문자열 검사** | 봇 호출 방지 태그 검사 | **0건 검출 확인** | 커밋, 문서, PR 코멘트 대상 |

---

## 8. 인계 및 검토 요청

- **Base 브랜치**: `agent/claude/c182-s12-manifest-routes` (PR #280 head `4114f8ba`)
- **작업 브랜치**: `agent/gemini/c183-s12fe-release-binding`
- **조치 커밋**: Claude UI r1/r2 및 Codex r1/r2 피드백 전수 조치 완료
- **검토 요청**:
  - Claude: UI/사용자 경험, 404/403 ProblemDetails 해석, 계약 위반 분리 표출, 셀렉터 변경 인터랙션, 단위 시험 21 passed 검토 요청.
  - Codex: strict wire 스키마 계약 검증(Blocker 1 & 2), canonical 5개 스키마 1:1 결속 검증, ProblemDetails 정본 코드(RES-0004, AUTH-0030) 검토 요청.

---

## 9. Claude UI r2 및 Codex r2 피드백 전수 조치표

| 식별자 | 분류 | 검토 요구사항 | 조치 내용 및 정정 근거 | 상태 |
|---|---|---|---|---|
| **Claude UI r2 차단 1 & Codex r2 차단 3** | 테스트 정합성 / CI 게이트 | `s12-release-manifest-server-binding.test.tsx:373` 404 픽스처가 `code: 'RES-RELEASE-NOT-FOUND'`를 사용하여 `fixture-problem-codes-integrity.test.ts`(/^[A-Z]+-[0-9]{4}$/) 거부로 CI 실패 | • 404 fixture `code`를 표준 백엔드 RFC 9457 코드인 `RES-0004`로 교체.<br>• 403 fixture `code`를 정본 인가 코드인 `AUTH-0030`으로 교체.<br>• UI 및 시험에서 `RES-0004`, `AUTH-0030` 코드와 ProblemDetails `detail` 메시지('요청한 릴리스 선언서를 찾을 수 없습니다.', '접근 권한이 부족하여...')를 직접 단언.<br>• `npm run test -- fixture-problem-codes-integrity.test.ts` 실행 결과 **1 passed (0 violations, exit 0)** 확인. | **조치 완료** |
| **R2-2 [Med]** | 계약 위반 상태 분리 | 서버가 `operatorSignOff=true`를 반환하거나 스키마 계약 위반 시 `네트워크 통신 오류` 대신 별도의 계약 위반 상태 표출 | • `releaseObservation.ts`에 `ContractViolationError` 클래스(`isContractViolation = true`, `code = 'CONTRACT-VIOLATION'`) 정의 및 검증 실패 시 투척.<br>• `IntranetDeploymentView.tsx` 에러 상태에 `CONTRACT-VIOLATION` 분기 추가.<br>• UI 에러 알림 컨테이너에 `data-testid="deployment-manifest-error-contract"`, 라벨 `🛑 계약 위반 응답: 잘못된 서버 응답 규격`으로 독립 렌더링.<br>• 목록 및 상세 계약 위반 변이 사살 시험 2종 추가(목록 operatorSignOff=true, 상세 corrupt-sha regex 위반). | **조치 완료** |
| **Low 1** | 잔여 문구 정비 | 상단 KPI 카드 `IntranetDeploymentView.tsx:318`에 잔존하던 'SIGN-OFF 대기 (백엔드 미연결)' 문구 정비 | • 'SIGN-OFF 대기 (백엔드 미연결)' 문구를 'SIGN-OFF 대기 (로컬 모의)'로 교체하여 오래된 "미연결" 문구를 완전히 제거.<br>• `s12-defect-fixes.test.tsx` line 54 단언을 'SIGN-OFF 대기 (로컬 모의)'로 갱신하여 23 passed 유지. | **조치 완료** |
| **Low 2** | UI 상호작용 검증 | 릴리스 선택기(`<select data-testid="deployment-release-selector">`) 변경 시 상세 쿼리 재호출 및 화면 갱신 시험 부재 | • `deployment-release-selector`에서 다른 릴리스(`rel-2026-s12-002`)를 선택하는 사용자 동작을 모의하는 테스트 추가.<br>• `/v1/release-manifests/rel-2026-s12-002` 엔드포인트 호출 및 화면의 수락 결정 이력이 두 번째 릴리스의 0건(`server-acceptances-empty`, '기록된 수락 결정 없음')으로 갱신됨을 단언. | **조치 완료** |
| **Codex r2 차단 1 & 2 선제 대비** | 계약 스키마 1:1 결속 검증 | `contracts/release-*.schema.json` 5개 스키마와 `releaseObservation.ts`의 허용 키셋 및 필수 필드 1:1 일치 시험 부재 | • 5개 스키마 파일(`release-component-response`, `release-manifest-response`, `release-acceptance-response`, `release-manifest-page-response`, `release-manifest-detail-response`)을 직접 로드하여 `additionalProperties === false` 불변식 검증.<br>• `releaseObservation.ts`의 `ALLOWED_*_KEYS` 5개 셋이 스키마의 `properties` 키셋과 1:1 정확히 일치함을 단언.<br>• 스키마의 모든 `required` 속성이 런타임 가드에서 검증됨을 단언. | **조치 완료** |
