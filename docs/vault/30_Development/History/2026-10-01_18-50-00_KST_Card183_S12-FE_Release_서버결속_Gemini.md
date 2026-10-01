---
doc_id: "HIST-20261001-C183-S12FE-001"
title: "Card 183 (S12-FE) 릴리스 선언서(Release Manifest) 및 운영자 인수 서버 경로 결속 기록"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-01T18:50:00+09:00"
updated: "2026-10-01T18:59:00+09:00"
source_of_truth: "Git"
base_sha: "3ff89b84"
task_ids: ["S12-FE", "S12-BE"]
tags: ["s12", "release-manifest", "acceptance", "binding", "read-only", "security-boundary", "gemini"]
---

# Card 183 (S12-FE) 릴리스 선언서(Release Manifest) 및 운영자 인수 서버 경로 결속

## 1. 1단계 전수 현황 분석 (Phase 1 Codebase Origin Analysis)

카드 183 1단계 지침에 따라 `apps/web/src` 내 `ReleaseManifest`, `operatorSignOff`, `localSimulationCompleted`의 기존 출처(고정값, fixture, 로컬 계산, API)를 전수 식별하고 정리한 표는 아래와 같다.

| 항목 / 상태 필드 | 선언 및 사용 위치 | 기존 출처 유형 | 상세 내용 및 동작 방식 | 카드 183 2단계 실서버 결속 상태 |
|---|---|---|---|---|
| `ReleaseManifest` (타입/모델) | `contracts/types.ts:516-526`, `deploymentEngine.ts`, `IntranetDeploymentView.tsx` | 프런트엔드 지역 합성 타입 (Client Synthetic) | DB에 존재하지 않는 FE 전용 필드(`imageDigest`, `targetClusters`, `totalNodes`, `smokePassedRatio`, `knownLimitations` 등)를 포함한 정적 인터페이스. `DeploymentManager.releaseManifest`의 모의 픽스처로 사용됨. | `contracts/release-manifest-response.ts` 및 `contracts/release-manifest-detail-response.ts` 정본 스키마 기반 계약 타입으로 분리 결속. 실 서버 `ReleaseManifestResponse` 및 `ReleaseManifestDetailResponse` 도입. |
| `releaseManifest` (인스턴스 데이터) | `deploymentEngine.ts:129-143`, `IntranetDeploymentView.tsx:17` | 고정 정적 픽스처 (In-Memory Fixture) | `REL-2026-PILOT-RC`, `v1.0.0-pilot-rc`, 하드코딩된 sha256 및 commit sha `c323f55`로 초기화되어 `DeploymentManager` 내부 상태로만 관리됨. 백엔드 REST API 미연결. | `GET /v1/release-manifests` (목록) 및 `GET /v1/release-manifests/{release_id}` (상세) 실서버 API를 호출하여 동적 수신. 테넌트 빈 목록(`items: []`) 시 날조 기본값 없이 '기록 없음' 빈 상태 표출. |
| `operatorSignOff` (서명 여부) | `deploymentEngine.ts:142`, `IntranetDeploymentView.tsx:180-190`, `contracts/types.ts:525` | 하드코딩 기본값 `false` + 로컬 메모리 토글 | `manager.signOffRelease()` 호출 시 인메모리 객체의 `operatorSignOff`를 `true`로 단순 플립. 서버에 저장되거나 전송되지 않음. DEF-S12에서 "서버 route 부재로 false 유지"로 기록된 핵심 결함 항목. | 서버 계산값(Authoritative Server Field)으로 결속. 서버의 `acceptance_records` 행 중 `outcome='accepted'` 및 `accepted_manifest_sha256 === manifest.manifest_sha256` 조건을 검증한 결과만 `true`로 관측 표출. 미서명 시 `operatorSignOff: false (미서명)` 정직하게 표출. |
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

## 4. 인계 및 검토 요청

- **Base 브랜치**: `agent/claude/c182-s12-manifest-routes` (PR #280 head `3ff89b84`)
- **작업 브랜치**: `agent/gemini/c183-s12fe-release-binding`
- **검토 요청**:
  - Claude: 프런트엔드 화면 결속, 빈 상태(기록 없음), 미서명 표출, 403/404 처리 UI 및 단위 시험 검토 요청.
  - Codex: 보안 경계(쓰기 UI 금지, `operatorSignOff` 서버 계산값 정직 반영) 및 계약 무결성 검토 요청.
- **다음 행동**: 검토 피드백 수신 시 반영, #280 병합 열차 진입 시 rebase/merge 후 착지.
