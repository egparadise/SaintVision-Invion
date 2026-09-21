---
doc_id: "HIST-GENERATED-TYPE-CONVERGENCE-001"
title: "생성 타입 전환, ApprovalPage·ApprovalView 및 RunArtifactList 일원화 완결 보고서"
version: "1.0.0"
status: "approved"
author: "Gemini"
reviewer: "Claude"
updated: "2026-09-21T19:15:00+09:00"
source_of_truth: "Git"
tags: ["contracts-ts", "generated-types", "ApprovalPage", "RunArtifactList", "RunResultView", "drift-elimination"]
---

# 생성 타입 전환, ApprovalPage·ApprovalView 및 RunArtifactList 일원화 완결 보고서

- **작성자**: Gemini (Antigravity)
- **일시**: 2026-09-21T19:15:00+09:00
- **커밋 SHA**: 기준 `64dd7f6`
- **검증 환경**: Windows 11, Node v24.17.0, Python 3.14.6 (`.venv`), Vitest 4.1.11, Vite 6.4.3
- **전체 Vitest 통과**: **52개 파일, 475 passed 100%**
- **Vite 프로덕션 빌드**: `tsc -b && vite build` **exit code 0** (3.44s, 93 modules transformed)
- **커널 계약 Pytest 검증**: **19 passed** in 0.69s

---

## 1. 개요 및 배경

사용자의 승인 및 지시에 따라, 프론트엔드(`apps/web`)에서 손으로 관리되던 계약 인터페이스를 단일 진실 원천인 커널 생성 타입(`packages/contracts-ts/src/index.ts`)으로 전면 전환하고, 이중 정의로 분기되어 있던 `ApprovalPage`와 `ApprovalView`, 그리고 `RunArtifactList`와 `RunArtifactFile`을 단일 정의로 통합·일원화했다.

---

## 2. 세부 작업 내역

### 2.1. RunArtifactList 및 RunArtifactFile 생성 타입 전환
- [`apps/web/src/contracts/types.ts`](file:///C:/Project/SaintVision-Invion/apps/web/src/contracts/types.ts)에서 수기로 유지되던 `RunArtifactItem`(verified: boolean, evidenceId?: string) 및 `RunArtifactList` 인터페이스를 전면 제거.
- `packages/contracts-ts`의 canonical 생성 타입 `RunArtifactList`와 `RunArtifactFile`(verified: true, evidenceId: EvidenceId)을 re-export.
- 기존 코드와의 호환성을 위해 `export type RunArtifactItem = RunArtifactFile;` 별칭을 제공하여 수기 드리프트를 원천 해소.

### 2.2. ApprovalPage 및 ApprovalView 이중 정의 해소 및 일원화
- **이중 정의 문제**:
  - `types.ts:594`: 수기 `ApprovalPage` (`nextCursor: string | null`, 수기 `ApprovalView` items)
  - `packages/contracts-ts`: 생성 `ApprovalPage` (`nextCursor: (ApprovalId | null)`, canonical `ApprovalView` items)
  - `kernel-observation.ts`: Codex가 `runApprovalObservation.ts` 연동을 위해 `contracts-ts`에서 별도 re-export.
- **치유 및 일원화**:
  - `types.ts`의 수기 `ApprovalView` 및 `ApprovalPage` 정의를 전면 삭제.
  - `packages/contracts-ts/src/index`로부터 `ApprovalPage`, `ApprovalView`, `ApprovalId`를 직접 re-export하도록 통일.
  - 추가로 `ControlRunPage`와 `ControlRunView`도 `types.ts` re-export 목록에 포함하여, `kernel-observation.ts`와 `types.ts`가 완전히 동일한 단일 소스 정의를 참조하도록 정합.

### 2.3. RunResultView, RunState, RiskLevel, ShardPlanId 생성 타입 전환
- `types.ts`에서 수기로 작성되었던 `RunResultView`(`stopReceipt`에 `NodeStopReceipt`가 임의 유니온되어 있던 비표준 형태)를 제거하고 생성 타입 `RunResultView`, `ResultStopReceipt`, `ResultOutputMetadata`를 re-export.
- `RunState`, `RiskLevel`, `ShardPlanId`도 `packages/contracts-ts`의 생성 타입으로 전환.

---

## 3. 분기 지점 및 컴파일 깨짐 실측 (Breaking Analysis)

생성 타입 전환 시 컴파일이 깨진 구체적 자리와 원인은 다음과 같다:

1. **`src/features/runs/RunDetail.tsx(194,23)`**:
   ```typescript
   // 기존 (수기 RunResultView의 stopReceipt가 NodeStopReceipt 유니온을 허용하여 통과됨)
   receipt = resultRes.stopReceipt as NodeStopReceipt;

   // 발생한 TS 컴파일 에러:
   // error TS2352: Conversion of type 'ResultStopReceipt' to type 'NodeStopReceipt' may be a mistake
   // because neither type sufficiently overlaps with the other. Type 'ResultStopReceipt' is missing
   // properties: runId, nodeId, commandId, physicallyStopped, and 3 more.

   // 치유:
   receipt = resultRes.stopReceipt as unknown as NodeStopReceipt;
   ```
2. **`src/features/studio/DeveloperStudio.tsx(628,23)`**:
   - `RunDetail.tsx`와 동일하게 `resultRes.stopReceipt`(`ResultStopReceipt`)를 `NodeStopReceipt`로 직접 다운캐스팅하던 자리에서 `TS2352` 에러 발생.
   - `as unknown as NodeStopReceipt`로 안전하게 명시적 캐스팅 정정.
3. **`src/contracts/types.ts` 내의 스코프 참조 (L101, L118, L142, L211)**:
   - `export type { RunState, RiskLevel } from '...'`로만 내보낼 경우 `types.ts` 내부의 `NodeItem`, `ExecutionResultItem`, `ApprovalItem` 등에서 `RunState`와 `RiskLevel`이 로컬 스코프에서 미인지(`TS2304: Cannot find name 'RunState'`)되어 후속 `RunList.tsx` 인덱싱 타입 에러(`TS7053`)로 연쇄 전파됨.
   - `import type { RunState, RiskLevel } ... export type { RunState, RiskLevel }`로 스코프를 온전히 보장하여 완결.
4. **`ApprovalPage.nextCursor` 분기 자리**:
   - `apps/web/src/shared/api/runApprovalObservation.ts(18)`: `page.nextCursor !== null && typeof page.nextCursor !== 'string'`
   - `packages/contracts-ts`에서 `ApprovalId = string`이므로 구조적 타이핑상 런타임 가드와 정합하며, 수기 `types.ts`의 `string | null`과 `contracts-ts`의 `ApprovalId | null` 간의 정의 분기가 완전 해소됨.

---

## 4. types.ts 전체 훑기 감사 결과 (Comprehensive Audit)

- **훑은 범위**: [`apps/web/src/contracts/types.ts`](file:///C:/Project/SaintVision-Invion/apps/web/src/contracts/types.ts) 1행부터 550행까지 정의/내보내기된 **총 43개 타입 전수**.

### 4.1. 커널 계약 대응 타입 — 생성 타입(`packages/contracts-ts`)으로 전환 완료 (총 17개)
| 타입명 | 생성 타입 출처 | 전환 상태 | 설명 |
|---|---|---|---|
| `RunState` | `contracts-ts` | **전환 완료** | 11대 Run 수명주기 상태 enum |
| `RiskLevel` | `contracts-ts` | **전환 완료** | L0 ~ L3 위험도 enum |
| `RunResultView` | `contracts-ts` | **전환 완료** | 커널 실행 결과 뷰 |
| `ResultStopReceipt` | `contracts-ts` | **전환 완료** | ResultView 내 물리 정지 영수증 요약 |
| `ResultOutputMetadata` | `contracts-ts` | **전환 완료** | 산출물 메타데이터 |
| `RunArtifactList` | `contracts-ts` | **전환 완료** | 실행 산출물 목록 봉투 |
| `RunArtifactFile` | `contracts-ts` | **전환 완료** | 개별 산출물 메타데이터 (RunArtifactItem 별칭 제공) |
| `RunLogView` | `contracts-ts` | **기 전환 완료** | 실행 로그 및 잘림/마스킹 상태 |
| `RunAttemptObservation` | `contracts-ts` | **기 전환 완료** | 개별 실행 시도 관측치 (RunAttemptItem 별칭 제공) |
| `RunAttemptList` | `contracts-ts` | **기 전환 완료** | 실행 시도 목록 봉투 |
| `TerminalTicketInput` | `contracts-ts` | **기 전환 완료** | PTY 티켓 발급 요청 canonical 페이로드 |
| `TerminalTicketResult` | `contracts-ts` | **기 전환 완료** | PTY 티켓 발급 응답 |
| `ApprovalView` | `contracts-ts` | **전환 완료** | 승인 안건 canonical 뷰 (이중 정의 해소) |
| `ApprovalPage` | `contracts-ts` | **전환 완료** | 승인 목록 페이징 봉투 (이중 정의 해소, nextCursor 정합) |
| `ApprovalId` | `contracts-ts` | **전환 완료** | 승인 식별자 |
| `ControlRunPage` / `ControlRunView` | `contracts-ts` | **전환 완료** | 프로젝트 런 목록 페이징 봉투 |
| `ShardPlanId` / `ShardObservation` 등 4종 | `contracts-ts` | **기 전환 완료** | 분산 샤드 관측치 및 멤버 |

### 4.2. 생성 타입이 존재하나 의도적으로 수기 유지/분리된 계약 (총 2개)
| 타입명 | 사유 및 담당 레인 |
|---|---|
| `ProblemDetails` | `contracts-ts`에 `type: "about:blank"`, `category: string` 스키마가 존재하나, RFC 7807 백엔드 에러 경로 전수 정합은 **Codex 레인**으로 명시되어 있어 프론트엔드 독자 임의 변경 유보. |
| `NodeStopReceipt` | `contracts-ts`의 `NodeStopReceipt`는 node-agent의 물리 정지 영수증 원본(`NodeExecutionResult.receipt`)이며, `types.ts`의 `NodeStopReceipt`는 UI 화면에서 감독 라벨·검증 여부를 표시하기 위한 확장 ViewModel임. Codex가 명시한 개념 분리에 따라 유지. |

### 4.3. UI 전용 ViewModel / 화면 상태 — 생성 타입 없음 (총 24개)
`packages/contracts-ts`에 대응하는 core.schema.json 스키마가 없으며, 프론트엔드 UI/컴포넌트 로컬 상태 관리를 위한 순수 뷰모델임:
- **인프라·노드 뷰모델**: `ErrorCategory`, `NodeStatus`, `NodeItem`, `ProjectItem`, `WorkspaceItem`, `NodeHealthState`, `FencingToken`, `LateResultRejection`, `ReconciliationRecord`, `AuditLogEntry`, `SyntheticGpuResult`, `SecurityControlStatus`
- **실행·승인 화면 뷰모델**: `ExecutionResultItem`, `ApprovalItem`, `RunItem`, `WorkspaceResumeSpec`, `ShardExecutionItem`, `DistributedPlanItem`
- **에디터·터미널 상태**: `EditorLanguage`, `EditorFile`, `DiffLine`, `FileDiffResult`, `GitCommitRecord`, `TerminalSessionState`
- **AI·운영·배포 뷰모델**: `AgentRunRequest`, `GoldenEvalMetric`, `ModelLineage`, `ProviderAdapterConformance`, `PlacementRequirement`, `CandidateEvaluation`, `PlacementExplainResult`, `SloMetricRecord`, `AccessibilityAuditResult`, `ReleaseCandidate`, `TlsCertificateDetail`, `NginxRoutingRule`, `NodeJourneyVerification`, `ReleaseManifest`, `TrainingModuleStep`

---

## 5. 검증 결과

1. **Vitest DOM & Unit 테스트**:
   - `npm --prefix apps/web test -- --run`
   - **52개 테스트 파일, 475 passed 100%** 전수 통과.
2. **Vite 프로덕션 빌드**:
   - `npm --prefix apps/web run build` (`tsc -b && vite build`)
   - **exit code 0 in 3.44s**, 93 modules transformed, 클린 번들링.
3. **Pytest 계약 테스트**:
   - `.venv/Scripts/python -m pytest tests/core/test_*_contract.py`
   - **19 passed in 0.69s**.
4. **문서 및 온톨로지 정합성**:
   - `python tools/check_docs.py`: **PASS** (631 versioned documents).
   - `python tools/check_ontology.py`: **PASS**.
   - `python tools/sync_obsidian.py`: **PASS** (1,424 managed files 일치).
