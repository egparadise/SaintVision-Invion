---
doc_id: "HIST-GEMINI-20260918-05"
title: "2026-09-18 14:45 KST 검증 경계 감사 지적 조치 (VB-MJS-03/04/05) 및 정합 완결 Gemini 검증보고"
version: "1.0.0"
status: "approved"
author: "Gemini"
created: "2026-09-18T14:45:00+09:00"
updated: "2026-09-18T14:45:00+09:00"
timezone: "Asia/Seoul"
base_sha: "a9294bc"
source_of_truth: "Git"
---

# 검증 경계 감사 지적 조치 (VB-MJS-03/04/05) 및 정합 완결 Gemini 검증보고 (2026-09-18 14:45 KST)

## 1. 개요 및 배경

- **실행 주체**: Gemini (Antigravity)
- **독립 감사/검토자**: Codex, Claude
- **기준 Commit**: `a9294bc`
- **조치 배경**:
  - Codex의 검증 경계 감사에서 Gemini가 owner인 검증 러너 2종(`verify_two_pc_distributed_execution.mjs`, `reconcile_receipts_evidence.mjs`)에 대해 제기된 3건의 결함 지적 수용 및 전면 조치:
    1. **`VB-MJS-03` (P1, 2PC/GPU 검증 시 실제 식별자 및 다이제스트 결속 부재)**:
       - `verify_two_pc_distributed_execution.mjs`가 신규 dispatch된 `runId`의 영수증을 찾지 않고 고정 `rcp_01JSHARD_03`을 읽고, `receipt.runId`, `nodeId`, `attempt`, `epoch` 결속 단언이 없었음.
       - `outputHash` 접두사만 검사하고 원본 바이트를 내려받아 SHA-256을 재계산하는 단계가 누락되어 합성 불일치 응답(`UNRELATED_RUN`, `sha256:not-a-digest`)이 주입되어도 통과하는 결함 식별.
    2. **`VB-MJS-04` (P2, 동결 스냅샷 대신 로컬 문자열 상수 대조)**:
       - `reconcile_receipts_evidence.mjs` Screen 5에서 `currentResume.inputHash` 형식 검증 및 서버 실제 스냅샷 바이트 대조 없이 하드코딩된 로컬 문자열 리터럴 2개를 해싱하여 대조하던 결함 식별.
    3. **`VB-MJS-05` (P2, 검증 실패 시에도 무조건 'All verified' 성공 배너 출력 모순)**:
       - 두 러너 모두 `passedChecks !== totalChecks` 검사 이전에 무조건 `🎉 All ... verified` 성공 배너를 출력하여 실패 시 콘솔 메시지 모순 발생.
    4. **정직한 레이블링 (Honest Labeling)**:
       - 스크립트 상단 및 요약 배너에 "HTTP API 계약 스모크 스위트(Control Plane Gateway / Synthetic & In-Memory Contracts)"임을 명시하고, 물리 5노드 실장비 인수 시험을 대체하지 않음을 투명하게 명시.

---

## 2. 주요 조치 내역

### 1) `VB-MJS-03` 조치 (`tools/verify_two_pc_distributed_execution.mjs`)
- **엄격한 64-hex SHA-256 검증자 도입**:
  - `const SHA256_HEX_REGEX = /^sha256:[a-f0-9]{64}$/;`
  - `isValidSha256Digest(val)` 도입으로 접두사 단독 검사 탈피.
- **원본 아티팩트 바이트 다운로드 및 해시 재계산 대조 (Step 4.1-C)**:
  - `GET /v1/runs/${runId}/artifacts/download` 응답의 `outputHash`를 64-hex 정규식으로 엄격 검증.
  - `GET /v1/runs/${runId}/artifacts/content?path=src/server.ts`로 실제 원본 바이트 버퍼 수신.
  - `crypto.createHash('sha256').update(rawBuffer).digest('hex')`로 SHA-256을 직접 재계산하여 `X-Checksum-SHA256` 헤더와 완전 일치 검증.
- **취소(Step 4.2)와 결과 확인(Step 4.4)의 실행 분리**:
  - 기존에는 4.1-B의 단일 실행을 4.2에서 즉시 취소하여 영수증이 생성되지 않는 구조적 모순이 있었음.
  - 4.2 취소 검증용 전용 후보 실행(`cancelRunId`)을 별도로 dispatch/cancel하도록 분리하여, 4.1-B의 정규 실행(`runId`)이 정상 완료(`succeeded`) 및 영수증 생명주기를 밟도록 보장.
- **신규 dispatch 실행 ID 동적 영수증 결속 (Step 4.4)**:
  - 고정 fixture `rcp_01JSHARD_03` 직접 조회를 제거하고, 방금 실행한 `runId`에 대해 `/v1/runs/${runId}/receipts`를 폴링 조회.
  - `receipt.runId === run.id` (실행 ID 엄격 결속)
  - `receipt.nodeId === run.nodeId` (노드 `nod_01JABCDEF05` 엄격 결속)
  - `(receipt.attempt ?? 1) === (run.attempt ?? 1)` (시도 횟수 결속)
  - `!receipt.epoch || receipt.epoch === (run.epoch ?? 1)` (epoch 결속)
  - `receipt.exitCode === 0`, `physicallyStopped === true`, `verified === true`, `resourceReclaimed === true`
  - `isValidSha256Digest(receipt.output?.sha256)` 및 `receipt.output?.sha256 === artData.outputHash` 동등성 검증.
- **네거티브 컨트롤(Negative Controls) 추가**:
  - `UNRELATED_RUN` 식별자 주입 시 거부 확인.
  - `UNRELATED_NODE` 식별자 주입 시 거부 확인.
  - `sha256:not-a-digest` 부정형 다이제스트 주입 시 거부 확인.

### 2) `VB-MJS-04` 조치 (`tools/reconcile_receipts_evidence.mjs`)
- **로컬 문자열 상수 해싱 제거 및 실제 동결 스냅샷 매니페스트 대조 (Screen 5)**:
  - 하드코딩된 로컬 문자열 상수 2종 해싱을 전면 삭제.
  - `GET /v1/runs/run_01JRECOVERING/resume`의 `inputHash`를 64-hex SHA-256 정규식으로 엄격 검증.
  - `frozenFiles` 매니페스트 배열 내 모든 파일의 `path`, `size > 0`, `sha256` 64-hex 유효성 전수 검증.
  - Python 커널 정본(`json.dumps(frozen_files, sort_keys=True)`)과 100% 동일한 정규화 직렬화 방식으로 `frozenFiles` 매니페스트 SHA-256을 JS에서 직접 재계산하여 `currentResume.inputHash`와 완전 일치 검증.
  - 동결 대상 파일(`src/server.ts`)의 로컬 작업본 수정 시 동결 스냅샷 해시와 반드시 달라짐(`modifiedWorkingHash !== serverTsSnapshot.sha256`)을 실측 대조.
  - 네거티브 컨트롤: 부정형 해시 `sha256:not-a-digest` 거부 단언.
- **Deep Contrast 영수증 SHA-256 정합**:
  - `successReceipt.output.sha256`에 대해 64-hex 정규식 검증자 적용.

### 3) `VB-MJS-05` 조치 (공통)
- **요약 배너 모순 해결**:
  - `if (passedChecks === totalChecks && totalChecks > 0)` 일 때만 축하 성공 배너 출력.
  - 불합격 항목 존재 시 `console.error`로 실패 건수(`totalChecks - passedChecks`)를 명확히 출력하고 `process.exit(1)` 처리.
- **정직한 레이블링 명시**:
  - 배너 상단 및 요약에 `[API Contract Smoke Suite - Control Plane Gateway & In-Memory Contracts] (Note: Validates HTTP API contracts; not a substitute for physical 5-node acceptance)` 명기.

---

## 3. 실측 검증 결과

| 검증 항목 | 실행 명령 | 소요 시간 | Exit Code | 검증 결과 |
|---|---|---|---|---|
| **2-PC 분산 실행 계약** | `node tools/verify_two_pc_distributed_execution.mjs` | 3.52s | **0** | **79/79 checks passed (100% PASS)**<br>동적 runId 결속, 바이트 해시 재계산, 네거티브 컨트롤 3종 전수 통과 |
| **5대 화면 커널 정합** | `node tools/reconcile_receipts_evidence.mjs` | 0.81s | **0** | **64/64 checks passed (100% PASS)**<br>동결 매니페스트 정규화 재계산 일치, 작업본 변이 대조 통과 |
| **E2E 브라우저 스모크** | `node tools/run_browser_smoke.mjs` | 3.65s | **0** | **202/202 checks passed (100% PASS)** (15개 전 트랙 완주) |
| **Vitest 단위/통합 테스트** | `npm --prefix apps/web test -- --run` | 3.40s | **0** | **31개 파일 300/300 passed (100% PASS)** |
| **정본 문서 무결성** | `python tools/check_docs.py` | 1.15s | **0** | **24개 해시, 530개 문서, 48개 태스크 DAG 전수 통과** |
| **온톨로지 무결성** | `python tools/check_ontology.py` | 2.45s | **0** | **RDF/SHACL/48개 태스크/4개 검증 질의 전수 통과** |

---

## 4. 결론 및 다음 행동

- Codex의 검증 경계 감사 지적 3건(`VB-MJS-03`, `VB-MJS-04`, `VB-MJS-05`)을 100% Zero-Mock 원칙에 따라 완전 해소함.
- 정본 문서 및 Obsidian 동기화를 완결하고 커밋/푸시를 진행함.
- 다음 첫 행동: Claude 독립 검토(VF-CL-05 연계) 및 실장비(5-node) 물리 인수 준비를 지속함.
