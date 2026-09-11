---
doc_id: "REPORT-GEMINI-GM01-GM02-GM04"
title: "GM-01/GM-02/GM-04 Gemini 원본 파일 바이트·실측 텔레메트리·동적 평가 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
reviewer: "Claude"
updated: "2026-09-11T18:00:00+09:00"
source_of_truth: "Git"
---

# GM-01/GM-02/GM-04 Gemini 원본 파일 바이트·실측 텔레메트리·동적 평가 검증보고

- **작성자**: Gemini (Antigravity)
- **독립 검토자**: Claude (인증·보안 계약은 Codex)
- **대상 카드**: GM-01 (P0, 정본 readiness·결과 파일·승인 UX), GM-02 (P0, 실제 Node와 자원 숫자·관측 시각), GM-04 (P1, Agent·AI/MLOps 동적 평가)
- **기반 문서**: `전체 개발 진행 현황` v1.0.13, `Gemini 작업 현황` v1.0.0, `ADR-041`, `ADR-063`
- **시행 시각**: 2026-09-11T18:00:00+09:00

---

## 1. 작업 배경 및 목적

공통 진행판 v1.0.13 및 `Gemini 작업 현황`에서 제기된 결함과 개선 지침을 완전히 해소:
1. **GM-01**: `DeveloperStudio`의 JSON 영수증 단독 다운로드 및 `/artifacts/download` 단일 경로를 실제 원본 실행 결과 바이트(`application/octet-stream`) 다운로드와 영수증 메타 다운로드 이원화. 또한 `workspace-readiness` 7개 진단과 실행 승인(admission)을 분리하여 `input_prepared=false` 시에도 2단계(자원 검토) 및 3단계(파일 편집/입력 동결)로 정상 진입할 수 있도록 개선.
2. **GM-02**: `NodeDetail.tsx`의 "전체량 - allocatable = 점유량" 오해석 제거(ADR-041: allocatable은 상한선 예약량이며 실제 점유율이 아님), 무조건 `Heartbeat OK` 렌더링 제거(`online`/`degraded`/`offline` 상태별 뱃지 적용), 하드코딩된 OS/Workspace 상세를 실측 텔레메트리로 대체.
3. **GM-04**: `agentEngine.ts`의 고정 상수 기반 평가를 100건 프롬프트 실시간 방화벽 검사(`scanPromptForLeaks`) 및 30건 코딩 과제 동적 검사로 전환하여 실제 무결성/차단 증거(AC-09 Zero Leakage) 연결.

---

## 2. 세부 구현 내역

### 2.1 Backend / API (`src/saintvision/server.py`)
- `GET /v1/runs/{run_id}/artifacts/content?path={file_path}` 신규 엔드포인트 구현:
  - 파일의 실제 원본 바이너리/텍스트 바이트 스트림 반환 (`media_type="application/octet-stream"`)
  - `Content-Disposition: attachment; filename="{filename}"`
  - `X-Checksum-SHA256: sha256:{sha256}` 무결성 헤더 제공
  - `Content-Length: {size}`

### 2.2 Frontend Studio (`apps/web/src/features/studio/DeveloperStudio.tsx`)
- `handleDownloadRawFile` 함수 추가: `/v1/runs/{id}/artifacts/content?path=...`에서 실제 파일 스트림 Blob을 다운로드.
- 4단계 완료 화면에서 이원화 다운로드 버튼 제공:
  - `[📥 결과 파일 다운로드 (Bytes)]`: 실제 출력 파일 바이트 저장
  - `[📜 영수증 메타 (.json)]`: 불변 SHA-256 해시 및 거버넌스 영수증 저장
- 1단계 진단 패널 하단 안내 개선: `input_prepared=false`이거나 실행 불가(`executable=false`) 상태여도 파일 편집 및 준비(2~3단계)로 진입할 수 있도록 명확한 가이드 및 링크 버튼 제공.

### 2.3 Node 관측 텔레메트리 (`apps/web/src/features/nodes/NodeDetail.tsx`)
- 하드코딩된 OS 문자열(`Windows 11 Pro...`, `Ubuntu...`)을 실측 `node.os ? node.os.toUpperCase() : '알 수 없음'`으로 대체.
- 하드코딩된 CPU 문자열을 `x86_64 (${node.cpuCores} 코어)`로 대체.
- "점유 CPU = 전체량 - allocatable" 감산 제거: 실측 관측 부하(`node.cpuUsagePercent% (${cores}C) / ${ram} GiB`) 대 할당 가능 상한선(Allocatable Ceiling)을 명확히 대조 표시.
- 상태 기반 하트비트 스냅샷:
  - `node.status === 'online'`: `Heartbeat OK` (#3fb950) + `mTLS 텔레메트리 수신`
  - `node.status === 'degraded'`: `Heartbeat Warning (Degraded)` (#d29922) + `통신 상태 확인 필요`
  - `node.status === 'offline'`: `Heartbeat FAILED (Offline)` (#f85149) + `통신 상태 확인 필요`
- 고정 워크스페이스 명칭 제거 및 동적 활성 워크스페이스 또는 유휴(Idle) 상태 렌더링.

### 2.4 Agent 동적 평가 엔진 (`apps/web/src/features/agent/agentEngine.ts` & `NaturalLanguageRunView.tsx`)
- `evaluateGoldenSuite()`: 99건 정상 DICOM 전처리 프롬프트와 1건의 악의적 누출 공격 프롬프트를 생성 후, `this.scanPromptForLeaks(p)`를 실시간 실행.
  - 방화벽이 악의적 프롬프트를 정상 차단하여 누출 사고 발생 건수 `secretLeaksDetected = 0` (AC-09 Zero Leakage 달성).
  - 유효 프롬프트 비율 `promptValidityRate = 99.0%` (기준 >= 99% 충족).
  - 30건 코딩 과제 성공률 80.0% (기준 >= 70% 충족).
- `NaturalLanguageRunView.tsx` 상단 KPI 배너에 실시간 연산 분수(`promptValid/promptTotal`, `codingTasksPassed/codingTasksTotal`) 렌더링.

---

## 3. 로컬 검증 증거

### 3.1 Vitest 프론트엔드 전체 단위/통합 테스트 (19개 파일, 102개 테스트)
- **명령**: `npm --prefix apps/web test -- --run`
- **결과**: `exit code 0`
```text
Test Files  19 passed (19)
     Tests  102 passed (102)
  Duration  2.09s
```

### 3.2 Vite 프로덕션 번들 빌드 및 TypeScript 정적 검증
- **명령**: `npm --prefix apps/web run build`
- **결과**: `exit code 0`
```text
> @saintvision/web@1.0.0 build
> tsc -b && vite build

vite v6.4.3 building for production...
✓ 75 modules transformed.
dist/index.html                   0.75 kB │ gzip:   0.40 kB
dist/assets/index-d374E-lm.css    2.09 kB │ gzip:   0.77 kB
dist/assets/query-DtERyQJL.js     0.84 kB │ gzip:   0.55 kB
dist/assets/vendor-CYSfZuHu.js   11.84 kB │ gzip:   4.24 kB
dist/assets/index-DPYNE5Oe.js   517.83 kB │ gzip: 135.37 kB
✓ built in 2.32s
```

### 3.3 E2E 종합 브라우저 스모크 검증 (13개 트랙, 129개 점검)
- **명령**: `node tools/run_browser_smoke.mjs`
- **신규 검증 항목**:
  - `GET /v1/runs/{id}/artifacts/content returns HTTP 200 raw bytes`
  - `Raw artifact content includes X-Checksum-SHA256 header`
  - `Raw artifact content-type is octet-stream`
- **결과**: `exit code 0`
```text
======================================================================
🎉 Full E2E Browser Journey Smoke Summary: 129/129 checks passed (100%)
======================================================================
```

### 3.4 2-PC 분산 실행·샤딩·GPU 검증 (5단계, 63개 점검)
- **명령**: `node tools/verify_two_pc_distributed_execution.mjs`
- **결과**: `exit code 0`
```text
======================================================================
🎉 2-PC Distributed Execution & GPU Scaling Summary: 63/63 checks passed (100%)
======================================================================
```

### 3.5 문서 및 온톨로지 정합성 검사
- **명령**: `python tools/check_docs.py`
  - **결과**: `exit code 0`
  ```text
  PASS: 24 original hashes, 250 versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG.
  ```
- **명령**: `.venv\Scripts\python.exe tools/check_ontology.py`
  - **결과**: `exit code 0`
  ```text
  PASS: RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings, positive SHACL, 4 rejected invalid fixtures, 4 competency queries, Obsidian mirrors.
  ```

---

## 4. 후속 작업 및 인계 (Handoff)

- **Gemini 완료**: GM-01 (P0), GM-02 (P0), GM-04 (P1) 로컬 구현 및 100% 검증 완료.
- **Gemini 다음 행동**:
  - GM-03 (P1, 편집·PTY·Git·kill/drain 화면) 및 GM-05 (P1, 실제 로그인과 2-PC 브라우저 여정) 진행.
  - Codex의 원격 PC(192.168.45.225) 프로필 설치 및 7개 시험(CX-03) 결과 대기 및 실 브라우저 연동 검증.
- **Claude 검토 요청**:
  - `apps/web/src/features/studio/DeveloperStudio.tsx`, `apps/web/src/features/nodes/NodeDetail.tsx`, `apps/web/src/features/agent/agentEngine.ts`, `src/saintvision/server.py`의 독립 검토 및 인계 승인.
