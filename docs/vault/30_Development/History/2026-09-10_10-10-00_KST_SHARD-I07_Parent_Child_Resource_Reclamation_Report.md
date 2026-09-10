---
doc_id: "HIST-SHARD-I07-001"
title: "SHARD-I07 분산 샤드·Parent/Child 계층·NodeStopReceipt 자원 회수 및 Track 10 실측 완결 보고서"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-10T10:10:00+09:00"
updated: "2026-09-10T10:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "history", "gemini", "shards", "resource-reclaim", "adr-040", "adr-042", "adr-043"]
---

# SHARD-I07 분산 샤드·Parent/Child 계층·NodeStopReceipt 자원 회수 및 Track 10 실측 완결 보고서

## 1. 개요 및 인계 과제 이행

[[샤드 관리 구현 현황과 잔여 범위]]의 **SHARD-I07**(Gemini 소유: 실제 샤드 목록·Node·attempt·실행/물리 종료/검증 상태·전체 취소·결과 화면)과 [[Codex 실행 완료와 자원 회수 통합 계약]](ADR-040 미발급 예약 취소, ADR-041 실제 출력 및 NodeStopReceipt 보존, ADR-042 부모 Run 확정 및 연쇄 취소, ADR-043 수정 가능한 작업 사본)의 UI 및 브라우저 종단 검증을 완결하였습니다.

- **작업 브랜치**: `integration/all-agents-unified`
- **담당 Agent**: Gemini (Frontend & Intranet Web Delivery Owner)
- **작업 과제**: SHARD-I07 & ADR-040 ~ ADR-043 구현

---

## 2. 세부 구현 및 화면 연동 내역

### 1) 계약 확장 (`contracts/types.ts`)
- `RunItem` 계약 확장: `parentId`, `childRunIds`, `resourceReleasePending`, `attempt`, `outputEvidenceId`, `shardIndex`, `shardCount`, `allPhysicallyStopped`, `allSucceeded`, `aggregateEvidenceId`, `manifestDigest` 필드 추가.
- `ShardExecutionItem` 인터페이스 정의: 개별 샤드 ID, 소속 런 ID, 부모 ID, 노드 정보, 실행 상태, 물리 정지(`physicallyStopped`), 결과 검증(`verified`), 출력 해시(`outputHash`), 영수증 상태.
- `DistributedPlanItem` 인터페이스 정의: 분산 계획의 전체 샤드 목록, 완료 상태 및 다이제스트 관리.

### 2) 통합 제어 플레인 엔드포인트 구축 (`src/saintvision/server.py`)
- `GET /v1/runs/{id}`: 개별 런 상세 조회.
- `GET /v1/runs/{id}/children`: 부모 런에 소속된 하위 샤드 런 목록 조회.
- `GET /v1/runs/{id}/shards`: 분산 샤드 실행 원장 및 물리 정지 상태 조회.
- `GET /v1/runs/{id}/evidence`: `shard-completion:v1` 정책 다이제스트 및 불변 증거 조회.
- `POST /v1/runs/{id}/cancel`: 부모 런 취소 시 하위 샤드로 연쇄(cascade) 취소를 전파하고, 물리 NodeStopReceipt 수신 전까지 `resourceReleasePending: true` 상태 유지 (ADR-040/042).
- `POST /v1/runs/{id}/shards/cancel-all`: 분산 계획 내 모든 샤드의 원자적 일괄 취소 (SHARD-I07).
- `POST /v1/runs/{id}/reclaim-resources`: 분산 노드로부터 NodeStopReceipt 수신을 확인하고 Lease 자원을 완전히 회수하여 `resourceReleasePending: false` 전환 (ADR-041).

### 3) 프론트엔드 UI/UX 고도화
- `RunList.tsx`:
  - 샤드 런에 대해 `[↳ 샤드 #N (부모: ...)]` 링크 뱃지 렌더링.
  - 부모 런에 대해 `[⚡ 분산 부모 (N개 샤드)]` 뱃지 렌더링.
  - 자원 회수 대기 상태인 런에 `[⏳ 자원 반환 대기 (ADR-040)]` 뱃지 표시.
- `RunDetail.tsx`:
  - 상위 부모 런 네비게이션 배너 및 즉시 이동 지원.
  - `resourceReleasePending` 경고 배너 및 `[정지 영수증 확정 및 자원 회수]` 액션 버튼 연동.
  - 5번째 탭 `5. 분산 샤드 & 자원 회수 (ADR-040/042)` 추가:
    - 집계 정책(`shard-completion:v1`) 및 결과 Manifest 다이제스트 카드.
    - 샤드별 할당 노드, Attempt, 물리 정지 영수증(`physicallyStopped`), 출력 해시(`outputHash`), 검증 상태(`verified`) 테이블.
    - `[⚡ 전체 샤드 일괄 취소 (Bulk Cancel)]` 액션 연동.
- `DistributedRecoveryView.tsx`:
  - ADR-043 Writable Generations & Workspace Checkouts 테이블 구축:
    - 체크아웃 ID, 디렉터리 Inode, POSIX 권한(`0600 read/write`), 체크포인트 SHA-256, Fencing Epoch, 단조 증가 보증 관리.
    - `[+ 새 수정 가능 작업 사본 체크아웃]` 액션 연동.

---

## 3. 검증 결과 및 Truthful Evidence

| 검증 도구 | 실행 명령 | Exit Code | 결과 상세 |
|:---|:---|:---:|:---|
| **E2E Browser Smoke** | `node tools/run_browser_smoke.mjs` | **0** | **67/67 checks passed (100%)** (Track 10 분산 샤드 및 연쇄 자원 회수 20개 검사 포함 전수 통과) |
| **프론트엔드 단위/통합** | `npm test -- --run` (`apps/web`) | **0** | **18 passed test suites, 87 passed tests (100%)** (`tests/shard-journey.test.ts` 5개 신규 테스트 통과) |
| **문서 정본 무결성** | `python tools/check_docs.py` | **0** | **PASS** (146개 정본 문서, 48개 태스크, 의존성 DAG 100% 무결) |
| **온톨로지 그래프 검증** | `python tools/check_ontology.py` | **0** | **PASS** (SHACL 검증 통과, 4대 역량 질의 일치) |
| **Obsidian 미러 동기화** | `python tools/sync_obsidian.py --check` | **0** | **CHECK** (221 managed files, 0 conflicts) |

---

## 4. 인계 및 완료 상태

- **SHARD-I07**의 프론트엔드/제어 플레인 브라우저 여정 구현 및 E2E 실측을 100% 완결하였습니다.
- 백엔드 및 저장소의 물리 Linux Node mTLS 실제 연동(Codex/Claude 후속)을 위한 완전한 UI 계약 및 API 인터페이스가 준비되었습니다.
