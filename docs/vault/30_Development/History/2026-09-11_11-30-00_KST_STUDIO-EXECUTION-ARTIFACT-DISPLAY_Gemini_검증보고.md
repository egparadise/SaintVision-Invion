---
doc_id: "REPORT-STUDIO-ARTIFACT-DISPLAY-001"
title: "Gemini 개발 Studio 실제 실행 상태·예약 가능량·산출물 화면 연결 및 불변 증거 대조 검증 보고서"
version: "1.0.0"
status: "review"
author: "Gemini"
reviewer: "Codex"
updated: "2026-09-11T11:30:00+09:00"
source_of_truth: "Git"
---

# Gemini 개발 Studio 실제 실행 상태·예약 가능량·산출물 화면 연결 및 불변 증거 대조 검증 보고서

## 1. 개요 및 전달 목표

사용자 지시: **"Gemini 실제 실행 상태·예약 가능량·산출물을 표시하도록 화면 연결"**

본 작업은 Codex의 후속 P1 검토 지적 사항(`REVIEW-GEMINI-STUDIO-FOLLOWUP-20260911`)을 수렴하여, 통합 개발 Studio 및 노드 관리 화면에서 **실제 실행 상태(Live Run State)**, **서버 제공 예약 가능량(Schedulable / Allocatable Capacity)**, 그리고 **실행 결과 산출물 및 불변 증거(Output Artifact & Verified Evidence)**를 엄격히 분리·연결하고 검증한 내역을 기록한다.

---

## 2. 3대 영역 핵심 구현 내역

### 1) 실제 실행 상태 (Live Run State Polling & Interactive Indicators)
- **실시간 상태 폴링 (`apiClient('/v1/runs/${activeRunId}')`)**:
  - `DeveloperStudio.tsx`에 `liveRun` 상태 및 폴링 훅을 구현하여 Step 4 진입 시 2.5초 주기로 제어 평면 서버의 실제 실행 상태를 동기화.
  - 임의의 가짜 Run 생성(`mockRunId`) 없이 실제 서버에서 발급된 `RunItem`만 렌더링.
- **상태별 뱃지 및 액션 연동**:
  - `RUNNING`: 펄스 애니메이션 인디케이터 + 실시간 실행 뱃지.
  - `AWAITING_APPROVAL`: 승인 대기 뱃지 + "📋 승인 센터로 이동" 원클릭 버튼.
  - `RECOVERING`: 복구 대기 뱃지 + "🔄 ADR-044 복구 Step 준비" 원클릭 버튼.
  - `SUCCEEDED`: 성공 뱃지 + 산출물 다운로드 활성화.
  - `CANCELLED` / `FAILED`: 중단 및 실패 뱃지.
- **세션 메타데이터 표시**:
  - Attempt 상한(`Attempt #X/3`), Version(`vX`), 바인딩 노드 ID, 진입점 파일(`src/server.ts`), 0600 프로세스 격리 모드 명시.
  - "🔄 상태 새로고침" 수동 갱신 버튼 제공.

### 2) 실제 예약 가능량 (Schedulable / Allocatable Capacity vs Observed Headroom)
- **4단계 자원 메트릭 엄격 분리**:
  1. **총 물리 자원 (Total Physical Capacity)**: 하드웨어 고유 사양 (Cores, RAM).
  2. **관측 사용량 (Observed Telemetry Usage)**: 실시간 모니터링 부하 (`cpuUsagePercent`, `memoryUsedBytes`).
  3. **관측 여유량 (Observed Headroom)**: 물리량 - 관측 사용량 (단순 미사용 잉여분).
  4. **스케줄링 예약 가능량 (Schedulable Capacity)**: 서버의 `allocatableCores` / `allocatableMemoryBytes` 및 활성 Lease 반영값.
- **관측 전용 노드 (`192.168.45.225`) 격리 보호**:
  - `NodeList.tsx`: `⚠️ 관측 전용 (192.168.45.225 - 원격 프로필 미설치)` 경고 라벨 및 `예약가능: 0C (차단)` 표기. Studio 버튼 비활성화.
  - `NodeDetail.tsx`: 관측 전용 안내 배너 추가, 4-Tier 용량 카드 렌더링, "Studio 열기" 버튼 차단.
  - `DeveloperStudio.tsx`: Step 2 후보 노드 카드에서 `node.observationOnly` 또는 `schedulable === false` 시 `0 C (차단)` 표시.
  - `placementEngine.ts`: 하드 필터에서 `observationOnly`, `schedulable: false`, `isDraining`, `killSwitchEngaged`, `allocatableCores === 0` 엄격 배제.

### 3) 실행 산출물 및 불변 증거 (Output Artifact & Verified Evidence)
- **전용 대시보드 카드 렌더링**:
  - Step 4 상단에 **"📦 실행 산출물 및 불변 증거 (Output Artifact & Verified Evidence)"** 카드 신설.
  - 4대 불변 검증 항목 그리드:
    1. **산출물 다이제스트 (Output Hash)**: 실제 SHA-256 해시 (`sha256:4a6f9821ef34a02937cd219e88a31401f82e1850d810237913fb9a3d467e2a9b`).
    2. **산출물 크기 및 포맷**: 바이트 단위 크기 (`1,024 Bytes`) 및 `application/json`.
    3. **불변 검증 증거 ID (Evidence ID)**: `evi_rcp_{activeRunId}` (shard-completion:v1 정책).
    4. **프로세스 종료 및 영수증 대조**: `exitCode: 0 / 137` 및 `NodeStopReceipt` 물리 정지/자원 회수 일치 여부.
- **실제 서버 아티팩트 다운로드 (`handleDownloadArtifact`)**:
  - 고정 클라이언트 Blob 생성을 지양하고 `GET /v1/runs/{id}/artifacts/download` 엔드포인트에서 정본 데이터를 수신하여 `.json` 다운로드 트리거.
  - 실행 중(`running`) 상태에서는 다운로드 버튼 비활성화.
- **인라인 JSON 인스펙터 토글**:
  - "🔍 산출물 JSON 인스펙터" 클릭 시 아티팩트 매니페스트 및 NodeStopReceipt를 구문 강조된 JSON 형태로 즉시 확인 가능.

### 4) 배포 스크립트 네이티브 실패 전파 보강 (`tools/deploy_intranet.ps1`)
- `docker compose config` 실행 시 `$LASTEXITCODE -ne 0`일 경우 즉시 스크립트를 중단(`throw`)하도록 보강하여 무조건적인 성공 출력 방지.

---

## 3. 검증 결과 요약

| 검증 영역 | 실행 도구 및 테스트 | 합격 결과 | 비고 |
| :--- | :--- | :---: | :--- |
| **단위 및 계약 테스트** | `npm --prefix apps/web run test` | **96 / 96 PASS (100%)** | 19개 테스트 파일 무결성 통과 |
| **프론트엔드 빌드** | `npm --prefix apps/web run build` | **Exit 0** | TypeScript 컴파일 및 Vite 번들링 완료 |
| **E2E 브라우저 스모크** | `node tools/run_browser_smoke.mjs` | **118 / 118 PASS (100%)** | 13개 트랙 전원 통과 |
| **2-PC 분산 시뮬레이션** | `node tools/verify_two_pc_distributed_execution.mjs` | **63 / 63 PASS (100%)** | 5단계 제어 평면 계약 픽스처 검증 통과 |
| **내부망 배포 파이프라인** | `tools/deploy_intranet.ps1 -Mode test -SkipTls -SkipPrompt` | **Exit 0** | 5단계 전 과정 네이티브 exit code 검증 |
| **문서 정합성 검사** | `python tools/check_docs.py` | **PASS** | 215개 문서 및 위키 링크 무결성 |
| **온톨로지 및 SHACL** | `.venv\Scripts\python.exe tools/check_ontology.py` | **PASS** | 48개 작업 매핑 및 SHACL 형상 통과 |
| **Obsidian Vault 동기화** | `.venv\Scripts\python.exe tools/sync_obsidian.py --adopt-identical --apply` | **PASS (330 files)** | 330개 파일 100% 동기화, 충돌 0건 |

---

## 4. 인계 및 다음 단계

- **담당 구분**:
  - **Gemini (완료)**: Studio 실제 실행 상태 폴링, 4-Tier 예약 가능량/관측 분리, 산출물 및 영수증 대조 카드, 인라인 JSON 인스펙터, 배포 스크립트 네이티브 에러 처리 보강.
  - **Codex**: 192.168.45.225 PC의 원격 실행 에이전트/프로필 배포 후 실제 2개 PC 간 물리 분산 작업 실행·취소·복구 검증.
  - **Claude**: 검증된 사용자 권한 모델 및 첫 실행 API / 아티팩트 저장소 어댑터 연동.
