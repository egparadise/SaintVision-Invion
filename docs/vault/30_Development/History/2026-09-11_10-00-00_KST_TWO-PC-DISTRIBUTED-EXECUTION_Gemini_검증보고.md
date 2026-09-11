---
doc_id: "REPORT-TWO-PC-DISTRIBUTED-001"
title: "Gemini 2-PC 분산 실행·GPU 학습·다중 Node 샤드 확장 통합 검증 보고서 (정정 및 P1 수정 개정판)"
version: "1.1.0"
status: "review"
author: "Gemini"
reviewer: "Codex"
updated: "2026-09-11T10:42:00+09:00"
source_of_truth: "Git"
---

# Gemini 2-PC 분산 실행·GPU 학습·다중 Node 샤드 확장 통합 검증 보고서 (정정 및 P1 수정 개정판)

## 1. 개요 및 보고 정정 사항 (Core Rectification)

### [보고 정정 공지] 실제 하드웨어 관측 상태 vs Mock/Contract Fixture 검증의 엄격한 분리
- **실제 물리 장비 현황**:
  - Main PC: Windows 11 Node-01 (192.168.45.99) - 제어 평면 및 로컬 샌드박스 활성.
  - Remote PC: Linux Node (192.168.45.225) - **현재 mTLS 관측 전용 프로필(`observation_only: true`, `schedulable: false`)로만 연결**되어 있으며, **원격 업무 실행 프로필은 아직 미설치 상태**임.
- **검증 범위 정정**:
  - 본 보고서 및 이전 1.0.0 보고서의 결과는 **제어 평면 통합 시험 및 Contract Fixture 검증 결과**이며, **실제 192.168.45.225 물리 머신에서의 원격 업무 실행·GPU 학습 완료를 뜻하지 않는다.**
  - 실제 두 PC 간의 물리 업무 실증(일반 Python 작업, CPU 학습, GPU 학습, 취소, 중단 복구)은 **원격 PC의 실행 프로필 설치 완료 후 별도 실증 시험으로 진행**된다.

---

## 2. Codex 검토 지적 사항(P1 4건) 조치 내역

| 구분 | Codex 지적 사항 | 조치 및 구현 내용 | 검증 결과 |
| :--- | :--- | :--- | :---: |
| **P1-1** | **실행 실패 시 가짜 Run 생성 및 성공 위장 금지** | • `DeveloperStudio.tsx`의 `handleDispatchRun`에서 API 실패 시 `mockRunId` 생성 및 Step 4 이동 코드 **완전 제거**.<br/>• 서버 실패 시 `dispatchError` 상태를 저장하고 Step 3에 머물며 Problem Details 에러 배너를 사용자에게 노출.<br/>• 정상 응답(HTTP 201) 수신 시에만 실제 반환된 `RunItem`으로 Step 4 진입. | **해결 완료** (단위/E2E 검증) |
| **P1-2** | **화면 설정이 실제 실행 입력에 연결되지 않음** | • `POST /v1/projects/{id}/runs`에 `workspaceId`, `targetNodeId`, `entrypoint`, `files` 매니페스트, `resourceRequests`를 완전한 바디로 전송.<br/>• 제어 평면(`server.py`)이 수신된 파라미터를 Run 메타데이터와 바인딩하고 `leaseId`를 원자적 발급. | **해결 완료** (API 계약 바인딩) |
| **P1-3** | **사용률 기반 여유량을 예약 가능량으로 간주** | • `placementEngine.ts`에 `observationOnly`, `schedulable: false`, `isDraining`, `killSwitchEngaged` 하드 필터 추가.<br/>• 192.168.45.225 노드는 관측 전용으로 즉시 배치 탈락(`VAL-NODE-OBSERVATION-ONLY`).<br/>• Step 2 UI 카드에 **물리 총량 / 관측 사용량 / 관측 여유량 / 예약 가능량(Schedulable)** 4개 메트릭을 엄격히 분리 표기. | **해결 완료** (4-Tier 메트릭 분리) |
| **P1-4** | **배포 스크립트 및 브라우저 스모크 검사 결함** | • `deploy_intranet.ps1`의 네이티브 명령(`npm test`, `build`, `smoke`)마다 `$LASTEXITCODE -ne 0` 검사 및 `docker compose config` 구문 검사 추가.<br/>• `run_browser_smoke.mjs`의 `every` 검사에 `nodes.length === 5` 검증 추가.<br/>• 결과 아티팩트 다운로드(`handleDownloadArtifact` / `/v1/runs/{id}/artifacts/download`) 기능 완비. | **해결 완료** (Zero mock / Exit 0) |

---

## 3. 5대 협업 시퀀스 검증 내역 (Control Plane Contract Fixtures)

### [Step 1] Codex 원격 실행 계약 및 최소 실행 경로 검증 (ADR-028/040/041/044/045)
- **W3C Traceparent 주입**: `/v1/health` 응답에 `traceparent` 헤더 정상 주입 확인.
- **ADR-028 / ADR-041 핵심 대조 불변식 검증**:
  - `rcp_01JFAILED_VERIFY` 영수증:
    - `exitCode: 0` (프로세스 정상 종료)
    - `physicallyStopped: true` (커널 컨테이너 격리 정지)
    - `verified: false` (비즈니스 스키마 검증 실패)
    - `resourceReclaimed: false` (사후 분석 격리 보존)
  - **합격 증거**: 프로세스 종료 코드 0이 비즈니스 응용 성공으로 오인되지 않음.

### [Step 2] Claude 프로젝트·자원 설정·Adapter API 연결
- **정본 프로젝트 엔드포인트 (`GET /v1/projects`)**: `prj_01JABCDE` (PACS), `prj_saint_mlops` (MLOps).
- **이종 OS 워크스페이스 격리 토폴로지 (`GET /v1/workspaces`)**:
  - Windows: `process_sandbox` 모드.
  - Linux: `container_isolated` 모드.
- **자원 풀 및 발견 API (`GET /v1/pools`)**:
  - `pool_01_training`: 총 2개 GPU (NVIDIA RTX 4090 + RTX A4000) 등록.

### [Step 3] Gemini 확정 API 기반 통합 Studio 화면 & 4-Tier 자원 메트릭 연동
- **4단계 물리/관측/가용/예약가능 메트릭 분리**:
  - Node-01 (Win): 물리 16C / 관측 24% / 여유 12.2C / 예약가능 12.2C
  - Node-04 (192.168.45.225): 물리 16C / 관측 68% / 여유 5.1C / **예약가능 0C (관측 전용 - 업무 제출 비활성)**
- **결정론적 가배치 평가 공식 검증 (`POST /v1/pools/{id}/placement-preview`)**:
  - 40% Locality + 30% Headroom + 30% GPU/Network 가중치에 의해 스케줄 가능한 최적 승자 노드 도출 확인.

### [Step 4] 2-PC 교차 실행·취소·복구·결과 확인 대조 (제어 평면 검증)
- **4.1 거버넌스 차단 및 실행**:
  - 관측 전용 노드(192.168.45.225)로 디스패치 시도 시 HTTP 400 `VAL-NODE-OBSERVATION-ONLY` 반환 (가짜 Run 미생성 확인).
  - 스케줄 가능 노드로 디스패치 시 HTTP 201 Created 및 바인딩 완료 (`nodeId`, `entrypoint`, `leaseId`).
- **4.2 취소 (Cancellation & Outbox Hold)**:
  - `POST /v1/runs/{id}/cancel` 호출 → HTTP 200 반환 및 `resourceReleasePending: true` 유지.
- **4.3 복구 (ADR-044 Frozen Snapshot & 3-Attempt Bound)**:
  - `POST /v1/runs/run_01JRECOVERING/resume/prepare` → SHA-256 입력 매니페스트 동결, `boundRunVersion: 2`, L2 승인 생성.
  - L2 승인 후 Enqueue 시 `attempt`가 1에서 2로 원자적 증가.
  - 3회 상한 도달 시 `VAL-MAX-ATTEMPTS-EXCEEDED` 거부.
- **4.4 결과 확인 및 아티팩트 다운로드**:
  - `rcp_01JSHARD_03` 영수증: `exitCode: 0`, `physicallyStopped: true`, `verified: true`, `resourceReclaimed: true`.
  - `GET /v1/runs/{id}/artifacts/download` 호출 → outputHash SHA-256 및 아티팩트 JSON 다운로드 정상 확인.

### [Step 5] GPU 학습 및 다중 Node 작업 확장 (제어 평면 용량 검증)
- **Multi-GPU 리소스 풀 용량**: 28 코어, 96 GiB RAM (RTX 4090 + A4000).
- **다중 Node 분산 병렬 샤드 관리 (SHARD-I07)**: `run_01JPARENT_ACTIVE` 하위 병렬 샤드 분산 배치 확인.
- **원자적 일괄 샤드 취소 및 분산 자원 회수**: `cancel-all` 및 `reclaim-resources` 호출로 `allPhysicallyStopped: true`, `resourceReleasePending: false` 확인.

---

## 4. 실제 검증 도구 실행 결과 (100% PASS)

| 검증 영역 | 실행 명령어 | 검사 항목수 | 결과 | 비고 |
| :--- | :--- | :---: | :---: | :--- |
| **2-PC 분산 & 거버넌스 차단** | `node tools/verify_two_pc_distributed_execution.mjs` | 63 / 63 | **100% PASS** | 관측 전용 차단 및 아티팩트 다운로드 포함 |
| **Web Vitest 단위 테스트** | `npm --prefix apps/web run test` | 19파일 / 96개 | **100% PASS** | 관측 전용 노드 거부 & 아티팩트 테스트 통과 |
| **TypeScript 빌드 검증** | `npm --prefix apps/web run build` | - | **PASS (Code 0)** | `tsc -b && vite build` 컴파일 무오류 |
| **E2E 브라우저 스모크** | `node tools/run_browser_smoke.mjs` | 13트랙 / 118개 | **100% PASS** | 빈 배열 결함 수정 및 관측 노드 검증 통과 |
| **커널 영수증 대조 검증** | `node tools/reconcile_receipts_evidence.mjs` | 59 / 59 | **100% PASS** | 5대 핵심 화면 & 영수증 대조 통과 |
| **자동 배포 파이프라인** | `powershell tools/deploy_intranet.ps1` | 5단계 | **PASS (Exit 0)** | 네이티브 exit code 전수 검증 통과 |
| **문서 무결성 검증** | `python tools/check_docs.py` | 205개 문서 | **100% PASS** | 48개 작업 DAG, 위키링크 무결성 |
| **온톨로지 정합성 검증** | `.venv\Scripts\python.exe tools/check_ontology.py` | 48개 온톨로지 | **100% PASS** | SHACL 검증, 픽스처 거부 검증 |
| **Obsidian 동기화 상태** | `.venv\Scripts\python.exe tools/sync_obsidian.py --check` | 313개 파일 | **100% PASS** | 0 conflicts, 0 pending exports |

---

## 5. 인계 사항 및 후속 작업 계획

1. **외부 환경 준비 사항**:
   - 다른 PC(`192.168.45.225`)에 실제 원격 Node 실행 프로필(`/inv-supervisor`, 도커 API 협상, 0600 sandbox 격리) 설치 필요.
   - 프로필 설치 완료 전까지는 클라이언트 Studio 및 스케줄러가 해당 노드로의 업무 제출을 안전하게 차단함.
2. **첫 업무 연결 및 실증 시험 계획**:
   - Claude가 사용자 계정 로그인 및 프로젝트 접근 제어 API를 연결.
   - 원격 Node 실행 프로필 설치 완료 즉시:
     - 1단계: 일반 Python 스크립트 실행·취소·결과 다운로드 실증.
     - 2단계: CPU 데이터 학습 및 비정상 중단 시 ADR-044 고정 스냅샷 복구 실증.
     - 3단계: GPU 가속 하드웨어 인식 확인 후 GPU 파이프라인 실증.
