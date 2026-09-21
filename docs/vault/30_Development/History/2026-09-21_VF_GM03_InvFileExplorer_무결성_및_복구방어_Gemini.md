---
doc_id: "VF-GM03-INV-FILE-EXPLORER-INTEGRITY-REPAIR-GEMINI-001"
title: "VF-GM-03 inv:// File Explorer 네임스페이스 탐색, 실측 SHA-256 무결성 검증 및 복제본 저하·복구 방어 실증 보고"
version: "1.0.0"
status: "verified"
author: "Gemini"
reviewer: "Codex"
updated: "2026-09-21T17:40:00+09:00"
code_ref_tip: "integration/all-agents-unified"
source_of_truth: "Git"
tags: ["vf-gm-03", "inv-file-explorer", "sha256-integrity", "tri-state-verification", "replica-degradation", "repair-guard", "mutation-testing"]
---

# VF-GM-03 inv:// File Explorer 네임스페이스 탐색, 실측 SHA-256 무결성 검증 및 복제본 저하·복구 방어 실증 보고

## 1. 개요 및 목적

사용자 기승인 트랙 지침에 따라 `VF-GM-02` (My Computer / Resource Explorer) 완결 직후 차기 준비 완료 카드인 **`VF-GM-03` (`inv://` File Explorer)**로 즉시 전환하여 구현 및 실증을 완결하였다.

본 작업의 핵심 목표:
1. **`inv://` 가상 분산 파일 네임스페이스 탐색**: `inv://models`, `inv://datasets`, `inv://workspaces`, `inv://artifacts` 4대 네임스페이스 주소 표시줄 내비게이션, 주소 직접 입력 이동, 퀵 네비게이션 버튼, 빈 상태(`등록된 파일이 없습니다.`) 무결 렌더링.
2. **클라이언트 실측 SHA-256 무결성 검증 (Requirement 1)**: Web Crypto API `crypto.subtle.digest('SHA-256')`를 기반으로 한 실측 해시 계산 및 카탈로그 기대 체크섬과의 엄밀한 대조. 해시 불일치 시 `role="alert"`와 `data-testid="integrity-mismatch-banner"`를 통한 `TAMPERED / MISMATCH` 경고 표출.
3. **엄밀한 삼태(Tri-State) 무결성 상태 구분 (Requirement 2)**: `UNVERIFIED` vs `VERIFIED` vs `MISMATCH / TAMPERED`의 엄밀한 분리. 카탈로그 체크섬이 부재하거나 빈 문자열인 파일은 절대로 `VERIFIED`로 처리되지 않으며 정직하게 `UNVERIFIED`로 유지.
4. **신규 실패 은폐 방지 (Requirement 3)**: 이전에 `VERIFIED` 상태였더라도 재검증 시 네트워크/503 오류가 발생하면 낡은 `VERIFIED` 상태를 즉시 파기하고 `status: 'error'` 및 `role="alert"` 경고 박스를 표면화.
5. **정직한 복제본 저하 감지 및 복구 가드 (Requirement 4)**:
   - `healthyReplicas < requiredReplicas`일 때 `replica-degradation-badge` (`role="alert"`) 표출 (예: `1/2 Replicas Available (Degraded)`).
   - 관측 전용 노드(`observationOnly: true`, `schedulable: false`)를 생존 노드에서 배제. 생존 가능 노드가 0개인 경우 복구 버튼을 비활성화하고 `no-surviving-nodes-notice` (`role="alert"`) 고지.
   - 복구 요청 실패 시 `repair-action-error` (`role="alert"`) 표출.
   - 복구 완료 후에도 여전히 복제본이 저하 상태(1/2)인 경우 거짓 성공 배너 대신 `repair-action-warning` (`role="alert"`) 표출.
   - 모든 필수 복제본이 정상 복구(2/2)된 경우에만 `repair-action-success` 배너 및 `replica-healthy-badge` 복원.

---

## 2. 세 가지 구분 원칙에 입각한 실측 현황 분석

| 구분 범주 | 구체적 검증 내용 및 실측 결과 |
|---|---|
| **1. 돌연변이로 실측해 깨진 것 (Measured Mutation Failures)** | • **Mutation 1 (해시 일치 여부 비교 생략 및 무조건 참 변조)**: `InvFileExplorer.tsx` 검증 분기에서 `isMatch = true`로 강제했을 때, 변조 해시 검증 시험에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected '검증 통과 (VERIFIED)' to contain '검증 실패 (해시 불일치 / TAMPERED)'`<br>&nbsp;&nbsp;`Expected: "검증 실패 (해시 불일치 / TAMPERED)"`<br>&nbsp;&nbsp;`Received: "검증 통과 (VERIFIED)"` (at `tests/inv-file-explorer-dom.test.tsx:269:32`)<br>• **Mutation 2 (체크섬 부재 시 미검증 대신 검증 완료로 합치 변조)**: `contentHash` 부재 시 `status = 'verified'`로 강제했을 때, 삼태 분리 시험에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected '검증 통과 (VERIFIED)' to be '미검증 (UNVERIFIED)' // Object.is equality`<br>&nbsp;&nbsp;`Expected: "미검증 (UNVERIFIED)"`<br>&nbsp;&nbsp;`Received: "검증 통과 (VERIFIED)"` (at `tests/inv-file-explorer-dom.test.tsx:349:32`)<br>• **Mutation 3 (재검증 실패 시 이전 성공 상태 은폐 보존 변조)**: `catch` 블록에서 이전 `status`를 덮어쓰지 않고 보존하게 했을 때, 신규 실패 은폐 방지 시험에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected '계산 중... (VERIFYING)' to be '검증 오류 (ERROR)' // Object.is equality`<br>&nbsp;&nbsp;`Expected: "검증 오류 (ERROR)"`<br>&nbsp;&nbsp;`Received: "계산 중... (VERIFYING)"` (at `tests/inv-file-explorer-dom.test.tsx:396:32`)<br>• **Mutation 4 (복구 실패 시 성공 배너로 은폐 변조)**: 서버 복구 거절 시 성공 메시지를 노출하게 했을 때, 정직한 복구 실패 시험에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected null not to be null` (at `tests/inv-file-explorer-dom.test.tsx:482:29`)<br>• **Mutation 4b (부분 복구 1/2 상태를 완전 복구 성공으로 취급 변조)**: 부분 복구 시 저하 검사를 우회(`if (false)`)하게 했을 때, 저하 경고 단언에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected null not to be null` (at `tests/inv-file-explorer-dom.test.tsx:532:25`) |
| **2. 소스를 읽어 판단한 것 (Source-Read Analysis)** | • `InvFileExplorer.tsx`의 `calculateSha256` 함수에서 TypeScript DOM 타입 호환성(`data as unknown as BufferSource`)을 교정하여 `tsc -b` 타입 검사를 100% 통과하도록 조치함.<br>• 파일 목록 행 더블클릭 시 `onOpenFile?.(file)`을 트리거하도록 결합하여 미사용 프로퍼티 린트 경고(`TS6133`)를 해소하고 에디터 연결성을 확보함.<br>• 기존 `fabric-observation.test.tsx`의 `renderToStaticMarkup`이 빈 상태 문구 `'등록된 파일이 없습니다'`를 기대하고 허위 복구 문구(/복구 완료/)를 금지하는 정적 마크업 계약을 준수하도록 초기 상태를 무결하게 유지함. |
| **3. 아직 확인 못 한 것 (Unverified / Deferred Invariants)** | • 수 기가바이트(GB) 대용량 모델 가중치 파일에 대한 실시간 청크 스트리밍 해싱 시 메인 스레드 블로킹 방지를 위한 Web Worker 백그라운드 연산 분리.<br>• 원격 물리 노드 간 물리 이더넷/Infiniband 패킷 단절 시 TCP 소켓 타임아웃 지연과 UI 스피너 연동.<br>• 상기 분산 스토리지 물리 계층 검증은 백엔드 스토리지 데몬 및 브라우저 E2E 인수 레인으로 이관함. |

---

## 3. 검증 결과 및 회귀 시험 지표

### 3.1 테스트 카운트 증가 보고 (기준선 명시)
- **`apps/web/tests/inv-file-explorer-dom.test.tsx` 신규 생성**: **10 tests 100% PASS**
  1. `[VF-GM-03-EXPLORE] handles inv:// namespace navigation, address bar input, and empty state`
  2. `[VF-GM-03-HASH-COMPARE] executes genuine hash comparison and surfaces TAMPERED alert on mismatch (Catches Mutation 1)`
  3. `[VF-GM-03-HASH-COMPARE] displays VERIFIED badge and suppresses mismatch banner when hashes strictly match`
  4. `[VF-GM-03-TRISTATE] strictly treats missing catalog checksum as UNVERIFIED, never VERIFIED (Catches Mutation 2)`
  5. `[VF-GM-03-NO-STALE-MASKING] immediately wipes prior VERIFIED state when a fresh re-verification fails (Catches Mutation 3)`
  6. `[VF-GM-03-REPLICA-DEGRADED] accurately surfaces replica degradation badge when healthy < required`
  7. `[VF-GM-03-REPAIR-GUARD] disables repair button and displays warning alert when 0 surviving nodes exist`
  8. `[VF-GM-03-REPAIR-FAIL] surfaces honest error alert when repair request fails (Catches Mutation 4)`
  9. `[VF-GM-03-REPAIR-PARTIAL] accurately reports partial restoration warning when replicas are still degraded (Catches Mutation 4b)`
  10. `[VF-GM-03-REPAIR-SUCCESS] displays success banner and restores healthy badge when all required replicas become healthy`
- **전체 Vitest 스위트**: 직전 보고 기준 **40개 파일 375 passed**에서 **41개 파일 385 passed**로 순증 (**from 375 to 385, net +10 tests**, 41개 테스트 파일 100% 합격).

### 3.2 빌드 및 거버넌스 도구 전수 합격 증거
1. **TypeScript & Vite 프로덕션 빌드 (`tsc -b && vite build`)**:
   `✓ built in 3.23s` (dist/index.html, dist/assets/index-Bn_O2ir3.js 631.00 kB 클린 빌드).
2. **Pytest 클라이언트 라우트 커버리지 (`test_route_coverage.py`)**:
   30 passed in 0.88s (100% 통과).
3. **문서 정합성 (`tools/check_docs.py`)**:
   PASS: 24 original hashes, 614 versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG.
4. **온톨로지 무결성 (`tools/check_ontology.py`)**:
   PASS: RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings, positive SHACL, 4 rejected invalid fixtures, 4 competency queries, Obsidian mirrors.

---

## 4. 결론 및 인계

`VF-GM-03` (`inv://` File Explorer)의 4대 네임스페이스 탐색, 실측 SHA-256 무결성 대조, 삼태 검증 분리, 신규 실패 은폐 방지, 복제본 저하 감지 및 생존 노드 기반 정직한 복구 가드를 완결하였다.

- **Outcome**: VF-GM-03 완료 (`inv://` File Explorer 무결성 및 복구 방어선 고정)
- **Code Reference Tip**: `integration/all-agents-unified`
- **Next Ready Action**: `VF-GM-04` (Model Studio: 단일 가상 GPU/vCPU 연산 뷰 & 다중 노드 실물 분산 매핑)
