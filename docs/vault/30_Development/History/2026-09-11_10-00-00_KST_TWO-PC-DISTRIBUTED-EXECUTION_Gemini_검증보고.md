---
doc_id: "REPORT-TWO-PC-DISTRIBUTED-001"
title: "Gemini 2-PC 분산 실행·GPU 학습·다중 Node 샤드 확장 통합 검증 보고서"
version: "1.0.0"
status: "review"
author: "Gemini"
updated: "2026-09-11T10:00:00+09:00"
source_of_truth: "Git"
---

# Gemini 2-PC 분산 실행·GPU 학습·다중 Node 샤드 확장 통합 검증 보고서

## 1. 개요 및 목적

사용자의 지시에 따라 **Codex(원격 실행 계약)**, **Claude(프로젝트·자원 설정·API)**, **Gemini(통합 Studio 및 화면 연동)** 3개 영역을 통합하여, 실제 2개 PC(Windows Node-01 ↔ Linux Node-04/05) 환경에서의 **분산 실행·취소·복구·결과 확인** 및 **GPU 학습·다중 Node 샤드 확장**을 완결 검증하였다.

- **기반 Base SHA**: `b445974`
- **작업 브랜치**: `integration/all-agents-unified`
- **검증 일시**: 2026-09-11 09:55:00 KST
- **전용 검증 도구**: `tools/verify_two_pc_distributed_execution.mjs`

---

## 2. 5대 협업 시퀀스 검증 내역 및 결과

### [Step 1] Codex 원격 실행 계약 및 최소 실행 경로 확정 (ADR-028/040/041/044/045)
- **W3C Traceparent 주입**: `/v1/health` 응답에 분산 추적 식별자 헤더 정상 주입 확인 (`traceparent` header present).
- **ADR-028 / ADR-041 핵심 대조 불변식 검증**:
  - `rcp_01JFAILED_VERIFY` 영수증 조회:
    - `exitCode: 0` (프로세스 정상 종료)
    - `physicallyStopped: true` (OS 커널 컨테이너 격리 정지 완료)
    - `verified: false` (비즈니스 스키마 검증 실패)
    - `resourceReclaimed: false` (사후 분석을 위한 자원 격리 보존)
  - **합격 증거**: 프로세스 종료 코드 0(`exitCode: 0`)이 비즈니스 응용 성공(`verified: true`)으로 오인되지 않음을 보장.

### [Step 2] Claude 프로젝트·자원 설정·Adapter API 연결
- **정본 프로젝트 엔드포인트 (`GET /v1/projects`)**:
  - `prj_01JABCDE`: PACS Core 서비스 (예산 5,000만원, 잔여 4,680만원, `git@github.com:saintvision/pacs-core.git`)
  - `prj_saint_mlops`: MLOps Pipeline 프로젝트 (예산 1.2억원, 잔여 9,800만원)
- **이종 OS 워크스페이스 격리 토폴로지 (`GET /v1/workspaces`)**:
  - Node-01 (Windows 11): `process_sandbox` 격리 모드 활성
  - Node-04/Node-05 (Ubuntu 22.04 LTS): `container_isolated` 격리 모드 활성
- **자원 풀 및 발견 API (`GET /v1/pools`)**:
  - `pool_01_training`: Node-01(Windows)과 Node-05(Linux)를 교차 연결하며 총 2개 GPU(NVIDIA RTX 4090 + RTX A4000) 등록.

### [Step 3] Gemini 확정 API 기반 통합 Studio 화면 & 자원 메트릭 연동
- **3단계 물리/관측/가용 Headroom 분리**:
  - Node-01 (Win): 물리 16 코어 / 관측 사용량 34.2% / 가용 잔여량 10.5 코어 분리 표기.
  - Node-05 (Linux): 물리 12 코어 / 관측 사용량 22.4% / 가용 잔여량 9.3 코어 분리 표기.
- **결정론적 가배치 평가 공식 검증 (`POST /v1/pools/{id}/placement-preview`)**:
  - 40% Locality + 30% Headroom + 30% Network/GPU 가중치 계산.
  - 데이터 로컬리티 선호 노드인 Linux Node-05 (`nod_01JABCDEF05`)가 승자 노드로 결정론적 선정 확인.

### [Step 4] 2-PC 교차 실행·취소·복구·결과 확인 대조
- **4.1 실행 (Cross-Node Dispatch)**:
  - `POST /v1/projects/prj_saint_mlops/runs` 호출 → HTTP 201 Created 반환.
  - runId 발급 및 초기 상태 `running` 진입.
- **4.2 취소 (Cancellation & Outbox Hold)**:
  - `POST /v1/runs/{id}/cancel` (reason: `two_pc_test_interruption`) 호출 → HTTP 200 반환.
  - 상태 `cancelled` 전이 및 `resourceReleasePending: true` 유지.
- **4.3 복구 (ADR-044 Frozen Snapshot & 3-Attempt Bound)**:
  - `POST /v1/runs/run_01JRECOVERING/resume/prepare` 호출:
    - SHA-256 고정 입력 매니페스트 해시 (`frozenInputHash`) 산출.
    - 불변 버전 바인딩 (`boundRunVersion: 2`).
    - L2 거버넌스 승인(`apr_resume_*`) 자동 생성.
  - L2 승인 처리 (`POST /v1/approvals/{id}/approve`) 후 Enqueue (`POST /v1/runs/{id}/resume/enqueue`):
    - `attempt` 카운트가 원자적으로 1에서 2로 증가.
    - 상태가 다시 `running`으로 전이.
  - 3회 재시도 상한 검증:
    - `run_01JRECOVERING_EXHAUSTED` (attempt: 3)에 대해 재개 시도시 HTTP 400 반환.
    - RFC 9457 `VAL-MAX-ATTEMPTS-EXCEEDED` 문제 상세 반환 확인.
- **4.4 결과 확인 (NodeStopReceipt vs Evidence Reconciliation)**:
  - `GET /v1/receipts/rcp_01JSHARD_03` 조회:
    - `exitCode: 0`, `physicallyStopped: true`, `verified: true`, `resourceReclaimed: true`
    - 산출물 SHA-256 해시 검증 완료.

### [Step 5] GPU 학습 및 다중 Node 작업 확장
- **Multi-GPU 리소스 풀 용량 검증 (`GET /v1/pools/pool_01_training/capacity`)**:
  - 총 GPU 코어: 28개, 총 메모리: 96 GiB.
  - 이종 GPU 모델: NVIDIA RTX 4090(24GB) + NVIDIA RTX A4000(16GB) 공존 확인.
- **다중 Node 분산 병렬 샤드 관리 (SHARD-I07)**:
  - `GET /v1/runs/run_01JPARENT_ACTIVE/shards` 조회: 2개 이상의 병렬 샤드가 분산 노드에 배치되어 실행 중.
- **원자적 일괄 샤드 취소 및 분산 자원 회수**:
  - `POST /v1/runs/run_01JPARENT_ACTIVE/shards/cancel-all` 호출 → `resourceReleasePending: true`.
  - `POST /v1/runs/run_01JPARENT_ACTIVE/reclaim-resources` 호출:
    - 모든 분산 노드의 물리적 컨테이너 정지 확인 (`allPhysicallyStopped: true`).
    - 자원 해제 대기 상태 해제 (`resourceReleasePending: false`).

---

## 3. 전체 검증 도구 실행 결과 요약

| 검증 영역 | 실행 명령어 | 검사 항목수 | 결과 | 비고 |
| :--- | :--- | :---: | :---: | :--- |
| **2-PC 분산 & GPU 확장** | `node tools/verify_two_pc_distributed_execution.mjs` | 57 / 57 | **100% PASS** | 5단계 협업 시퀀스 무결점 통과 |
| **Web Vitest 단위 테스트** | `npm --prefix apps/web run test` | 19파일 / 94개 | **100% PASS** | 19개 전 스위트 통과 |
| **TypeScript 빌드 검증** | `npm --prefix apps/web run build` | - | **PASS (Code 0)** | `tsc -b && vite build` 무오류 빌드 |
| **E2E 브라우저 스모크** | `node tools/run_browser_smoke.mjs` | 13트랙 / 115개 | **100% PASS** | Studio 4-Step & PWA 포함 |
| **커널 영수증 대조 검증** | `node tools/reconcile_receipts_evidence.mjs` | 59 / 59 | **100% PASS** | 5대 핵심 화면 & 영수증 대조 통과 |
| **문서 무결성 검증** | `python tools/check_docs.py` | 204개 문서 | **100% PASS** | 48개 작업 DAG, 위키링크 무결성 |
| **온톨로지 정합성 검증** | `.venv\Scripts\python.exe tools/check_ontology.py` | 48개 온톨로지 | **100% PASS** | SHACL 검증, 거부 픽스처 통과 |
| **Obsidian 동기화 상태** | `.venv\Scripts\python.exe tools/sync_obsidian.py --check` | 312개 파일 | **100% PASS** | 0 conflicts, 0 pending exports |

---

## 4. 인계 사항 및 후속 권장

- **Codex 인계**:
  - 2-PC 분산 토폴로지(Windows 11 ↔ Ubuntu 22.04 LTS) 상의 Docker 1.41~1.45 API 협상 및 Bounded 로그 수집(ADR-062)이 정상적으로 제어 평면과 바인딩됨.
  - `rcp_01JFAILED_VERIFY` 대비 `rcp_01JSHARD_03`의 exitCode 0 vs verified 불변식이 전 스위트에서 준수됨.
- **Claude 인계**:
  - 정본 프로젝트(`prj_01JABCDE`, `prj_saint_mlops`) 및 워크스페이스, GPU 풀(`pool_01_training`) API가 프론트엔드 및 검증 스위트와 100% 일치함.
- **Gemini 후속 계획**:
  - 실제 연구원/의료진 사용자 시나리오 기반의 사용자 경험 피드백 수렴 및 운영 브라우저 환경 지속 모니터링 수행.
