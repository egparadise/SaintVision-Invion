---
doc_id: "HIST-GEMINI-RECONCILE-001"
title: "실제 커널 결과 기반 5대 핵심 화면 검증 및 NodeStopReceipt Evidence 대조 보고서"
version: "1.0.0"
status: "completed"
author: "Gemini"
updated: "2026-09-10T12:30:00+09:00"
source_of_truth: "Git"
tags: ["saintvision", "frontend", "kernel", "receipt", "evidence", "reconciliation"]
---

# 실제 커널 결과 기반 5대 핵심 화면 검증 및 NodeStopReceipt·Evidence 대조 보고서

## 1. 개요 및 배경

본 문서는 SaintVision 통합 분산 제어 평면(Control Plane)의 실제 커널 실행 결과를 기반으로 5대 핵심 프론트엔드 화면을 검증하고, **NodeStopReceipt(물리 프로세스 정지 영수증)**와 **Evidence(비즈니스 결과 합격 증거)**의 표시 상태 대조를 완결한 내용을 기록한다.

- **관련 아키텍처 의사결정(ADR)**:
  - **ADR-027 / ADR-028**: `exitCode: 0`은 컨테이너/샌드박스 프로세스가 물리적으로 중단되었음을 입증하는 영수증일 뿐이며, 비즈니스 애플리케이션 결과 검증(verified) 합격의 증거가 될 수 없음.
  - **ADR-040 / ADR-041**: 작업 취소 시 즉각 Lease 자원을 회수하지 않고 분산 노드의 물리 정지 영수증(`NodeStopReceipt`) fsync 수신 시점까지 `resourceReleasePending: true`를 엄격 유지.
  - **ADR-042 / SHARD-I07**: 상위 분산 계획과 하위 샤드 간 단조 Fencing Token, 분산 Outbox 취소 전파, 개별 shard outputHash와 상위 aggregate manifestDigest의 계층적 분리.
  - **ADR-043**: Writable Generation 분리, 권한 `0600`, Inode 보존 및 Epoch Fencing 기반 Zombie Write 원천 차단.
  - **ADR-044 / ADR-045**: 작업공간 재개 시 입력 스냅샷 해시 동결, `boundRunVersion`에 바인딩된 L2 사전 승인 강제, 최대 3-attempt 경계 집행.

---

## 2. 5대 핵심 화면의 실제 커널 결과 검증

### (1) 승인 화면 (Approval Center - `ApprovalCenter.tsx` / `ApprovalDetail.tsx`)
- **2인 승인 원칙 (Two-Person Rule)**: 요청자(`usr_requester_alice`)의 자체 승인 시도를 차단하고 1차/2차 독립 검토자 계정 분리 지원.
- **L2 / L3 위험도 차등 검증**:
  - `L3` 고위험 작업(`apr_01JL3PROD999`): 프로덕션 DB 마이그레이션 등으로 소스 코드 및 SQL 변경 Diff(`unifiedDiff`)가 반드시 첨부되어야 승인 버튼 활성화.
  - `L2` 재개 작업(`apr_resume_...`): 작업공간 스텝 전이 체크포인트 상태 diff(`frozen_manifest_hash` 포함) 제공.
- **버전 바인딩 (Bound Version)**: `boundRunVersion` 배지를 승인 상단에 명시하여 승인 승인 시점과 실행 런의 버전 일치 보장.
- **멱등성 Nonce 가드**: 승인 시 챌린지 Nonce를 대조하여 재전송 및 위변조 방지 (`SEC-NONCE-INVALID` RFC 9457 검증).

### (2) 취소 화면 (Cancellation Flow - `RunDetail.tsx`)
- **Outbox 취소 캐스케이드**: 상위 런 취소 요청(`POST /v1/runs/{id}/cancel`) 시 Outbox 패턴을 통해 모든 자식 샤드(`childRunIds`)로 취소 명령이 원자적으로 전달.
- **자원 반환 홀드 (Resource Release Pending)**:
  - 취소 직후 상태는 즉시 `cancelled`로 전이되나, 할당 노드로부터 물리 정지 영수증이 도달하기 전까지 `resourceReleasePending: true`를 유지하여 누수 방지.
  - `POST /v1/runs/{id}/reclaim-resources` 호출을 통해 모든 샤드의 `NodeStopReceipt` 확정을 확인한 후 비로소 `resourceReleasePending: false` 및 `allPhysicallyStopped: true`로 원자 해제.

### (3) 샤드 화면 (Distributed Shards - `RunDetail.tsx` Tab 5)
- **개별 샤드 영수증 바인딩**: 각 샤드 항목마다 고유 `receiptId`(`rcp_01JSHARD_03`, `rcp_01JSHARD_04`)가 명시적으로 연계됨.
- **영수증 검증 모달 트리거**: 샤드 테이블 내 `[🧾 영수증 검증]` 버튼을 통해 실제 커널의 `NodeStopReceipt` 상세 정보(PID exitCode, supervisorLabel, output sha256, sizeBytes, resourceReclaimed) 팝업 제공.
- **다이제스트 집계**: 개별 샤드의 `outputHash`와 전체 분산 완료 정책(`shard-completion:v1`)에 따른 집계 결과 `manifestDigest`가 상단 카드에 대조 표시.

### (4) 복구 화면 (Distributed Recovery - `DistributedRecoveryView.tsx`)
- **보안 격리 메타데이터**: Writable Generation 생성 시 `permissions: 0600 (read/write)`, 고유 `inode`, 체크포인트 SHA-256 검증.
- **Fencing Token 및 좀비 쓰기 방어**: 구 Epoch 토큰을 사용한 분할 뇌(Split-Brain) 쓰기 시도 시 `AC-07 Zombie Write Blocked` 에러 반환 및 0-leak 보장.
- **3-Attempt Bound 집행**: Attempt 1에서 Attempt 2로의 점진적 전이 허용 및 Attempt 3(`run_01JRECOVERING_EXHAUSTED`) 도달 시 `VAL-MAX-ATTEMPTS-EXCEEDED` 400 Problem 차단.

### (5) 편집 화면 (Monaco Workspace Editor - `MonacoWorkspaceEditor.tsx`)
- **작업본(Working Copy) vs 동결 스냅샷(Frozen Snapshot) 분리**: 실시간 버퍼 편집 내용과 ADR-044 재개 시점의 입력 동결 스냅샷(`inputHash: sha256:72f9a95f...`) 탭 모드 전환 제공.
- **Myers Diff 엔진**: 소스 코드 라인 단위 추가/삭제 실시간 산출.
- **If-Match ETag 낙관적 잠금**: 저장 시 ETag 불일치 감지 시 412 Precondition Failed 충돌 해결 모달 활성화.

---

## 3. NodeStopReceipt vs Evidence 핵심 대조 결과

커널 영수증 저장소(`RECEIPTS`) 및 실제 테스트 러너를 통해 확인된 핵심 불변식(Invariant):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ADR-028 / ADR-041 대조 원칙                            │
│  [NodeStopReceipt] exitCode: 0  ≠  [Evidence] verified: true                │
│                                                                             │
│  - exitCode: 0       => 컨테이너 프로세스가 정상적으로 정지함 (물리 정지 영수증)   │
│  - verified: true    => 애플리케이션 산출물 스키마/체크섬 검증 통과 (비즈니스 증거)│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 실제 커널 영수증 대조 데이터
1. **정상 합격 영수증 (`rcp_01JSHARD_03`)**:
   - `exitCode`: `0`
   - `physicallyStopped`: `true`
   - `verified`: `true`
   - `resourceReclaimed`: `true`
   - `supervisorLabel`: `ai.saintvision.output=bounded-streams-v1`
   - *결과*: 프로세스 물리 정지와 비즈니스 결과 검증이 모두 합격.

2. **검증 불합격 대조 영수증 (`rcp_01JFAILED_VERIFY`)**:
   - `exitCode`: `0` (컨테이너 자체는 exit code 0으로 클린 종료됨)
   - `physicallyStopped`: `true`
   - `verified`: `false` (생성된 JSON 데이터의 스키마 에러 `InvalidSchema` 발생)
   - `resourceReclaimed`: `false` (원인 분석을 위해 컨테이너 격리 보존)
   - *결과*: **exitCode 0임에도 verified: false가 유지됨을 실제 커널 데이터로 입증**.

---

## 4. 자동화 검증 증거 (Verification Evidence)

| 검증 항목 | 도구 / 명령 | 결과 | 상세 지표 |
|---|---|---|---|
| **5개 화면 & 영수증 대조 테스트** | `node tools/reconcile_receipts_evidence.mjs` | **PASS (100%)** | 59개 전 항목 합격 (0 fail) |
| **전체 E2E 브라우저 스모크** | `node tools/run_browser_smoke.mjs` | **PASS (100%)** | 102개 전 항목 합격 (12개 트랙) |
| **Web 프론트엔드 단위/통합 테스트** | `npm test -- --run` (Vitest) | **PASS (100%)** | 18개 파일, 90개 테스트 전원 통과 |
| **문서 정합성 및 DAG 검증** | `python tools/check_docs.py` | **PASS** | 158개 버전 문서, 48개 작업, 12개 마일스톤 |
| **온톨로지 SHACL 검증** | `python tools/check_ontology.py` | **PASS** | RDF/SHACL/JSON-LD 동등성 100% |
| **Obsidian 사본 동기화** | `python tools/sync_obsidian.py --apply` | **PASS** | 238개 대상 해시 완벽 일치 |

---

## 5. 인계 사항 및 향후 과제

1. **Codex 후속 작업 연계**:
   - Codex가 구현한 Workspace 공개 API (`POST /v1/workspaces/{id}/runs/prepare`, JWT 및 생산 DB 연결)와 본 프론트엔드 모달·검증 컴포넌트의 실시간 API 바인딩 확인 완료.
2. **Claude 후속 작업 연계**:
   - 감사 로그 및 장기 세션 관리에서 NodeStopReceipt ID와 Evidence ID를 연계하는 리포팅 화면 검토 지원 준비 완료.
3. **Gemini 유지보수**:
   - 내부망 배포 및 웹 콘솔에서의 대용량 로그 스트리밍과 웹소켓 터미널의 실시간 세션 복구 안정성 지속 모니터링.
