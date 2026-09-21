---
doc_id: "HIST-2026-09-22-NARROWED-NOTICES-AND-NODE-STATUS"
title: "산출물 다운로드 전송 검증 문구 좁힘 및 노드 lost/unknown 조용한 합류 둔갑 차단 실제 Chrome 153 실측"
version: "1.0.0"
status: "completed"
author: "Gemini"
reviewer: "Codex"
created: "2026-09-22T03:41:30+09:00"
updated: "2026-09-22T03:41:30+09:00"
source_of_truth: "Git"
branch: "integration/all-agents-unified"
---

# 산출물 다운로드 전송 검증 문구 좁힘 및 노드 lost/unknown 조용한 합류 둔갑 차단 실제 Chrome 153 실측

## 1. 작업 배경 및 사실 기반 요구사항

### 1.1 산출물 다운로드 무결성 표시 문구 좁히기 (전송 확인 및 저장소 미대조 고지)
- **발견된 사실 (Codex 실측)**:
  - Codex가 실제 PostgreSQL 16과 Uvicorn 0.52.4 환경에서 `/artifacts/content` 다운로드 엔드포인트를 실측한 결과, 다운로드 응답은 저장된 디스크 파일이 아닌 DB의 `stop_receipt` 불변 영수증 바이트로 본문과 `X-Content-SHA256` 헤더를 함께 생성함.
  - 저장 디스크의 스냅샷 파일을 임의로 변조하더라도 HTTP 응답은 여전히 200과 함께 DB 영수증 원본 바이트를 반환하므로, 프런트엔드가 수신한 해시와 헤더가 일치하는 것은 **"서버가 보낸 바이트가 네트워크 전송 중에 손상/변조되지 않았음"**만을 증명함.
  - 따라서 기존 화면에 표출되던 `[무결성 검증 완료]` 문구는 사용자로 하여금 "저장소에 보관된 산출물 원본까지 대조 검증되었다"는 오해를 불러일으키는 과장 주장이었음.
- **조치 내용**:
  - 구조는 유지하되 화면의 말을 사실대로 좁힘:
    - 정상 일치 시: `[전송 확인 완료] 산출물 파일 '...' (... Bytes, 수신 바이트와 서버 헤더 일치 · 저장소 원본 대조 아님) 다운로드 완료.` (`role="status"`)
    - 불일치 시: `[전송 불일치 · 저장 차단] 산출물 파일 '...'의 수신 바이트 체크섬이 서버 전송 헤더와 다릅니다. 전송 중 손상 위험으로 파일 저장을 차단했습니다.` (`role="alert"`)
    - 필수 헤더 부재 시: `[전송 헤더 누락 · 저장 차단] 서버 응답에 전송 검증용 필수 헤더(X-Content-SHA256)가 없습니다. 전송 검증 생략 및 조용한 강등 위험을 방지하기 위해 파일 저장을 차단했습니다.` (`role="alert"`)

### 1.2 노드 상태 어휘 불일치 선제 조치 (죽은 노드 lost 단절 고지 & 모르는 값 unknown 명시)
- **발견된 결함**:
  - 백엔드 DB CHECK 어휘(`enrolling`, `active`, `draining`, `lost`, `retired`)와 화면 어휘(`online`, `degraded`, `offline` 등) 간 어휘 통일은 사용자 결정 대기 중임.
  - 그러나 기존 `nodeObservation.ts`는 해석할 수 없는 모든 상태(죽은 노드인 `lost` 및 백엔드 상태인 `active` 등)를 전부 조용히 `enrolling`(합류 중)으로 강등/둔갑시켜 렌더링하고 있었음.
  - ① 죽은 노드(`lost`)가 합류 중(`enrolling`)으로 표시되는 것은 운영자에게 치명적인 허위 보고임. 확실하게 통신 두절된 죽은 노드로 분리해야 함.
  - ② 모르는 상태 어휘를 만났을 때 그럴듯한 정상/준비 상태(`enrolling`)로 조용히 둔갑시키는 것은 silent fallback 결함임. `unknown`(미확인 상태)으로 명시하여 운영자에게 상황을 정직하게 전달해야 함.
- **조치 내용**:
  - `apps/web/src/contracts/types.ts`: `NodeStatus` 유니온에 `'lost' | 'unknown'` 추가.
  - `apps/web/src/shared/api/nodeObservation.ts`: `rawStatus === 'lost'`이면 `mappedStatus = 'lost'`, 매핑되지 않는 모르는 값이면 조용히 `enrolling`으로 바꾸지 않고 `mappedStatus = 'unknown'`으로 명시.
  - `apps/web/src/features/nodes/NodeList.tsx`:
    - `lost` 노드: `role="alert"` 컨테이너, 빨간색 `LOST (단절)` 뱃지, "🔴 노드와의 통신이 두절되어 상태가 유실(Lost)되었습니다..." 경고 표출.
    - `unknown` 노드: `role="status"` 컨테이너, 주황색 `UNKNOWN (미확인)` 뱃지, "⚠️ 서버에서 관측된 노드 상태를 화면에서 해석할 수 없습니다 (미확인 상태 · 조용한 합류 둔갑 차단)" 안내 표출.
  - `NodeDetail.tsx`, `ClusterOverview.tsx`, `ResourceExplorer.tsx`: `lost` 및 `unknown` 뱃지 및 색상 분기 일관 적용.

---

## 2. 변경 파일 목록

1. `apps/web/src/contracts/types.ts`: `NodeStatus`에 `'lost'`, `'unknown'` 상태 타입 추가.
2. `apps/web/src/shared/api/nodeObservation.ts`: `lost` 매핑 및 모르는 어휘를 `enrolling`으로 강등하지 않고 `unknown`으로 매핑.
3. `apps/web/src/features/nodes/NodeList.tsx`: `lost` alert 배너 및 `unknown` status 배너, 상태 뱃지 렌더링 추가.
4. `apps/web/src/features/nodes/NodeDetail.tsx`: `lost`, `unknown` 뱃지 분기 반영.
5. `apps/web/src/features/dashboard/ClusterOverview.tsx`: `lost`, `unknown` 뱃지 분기 반영.
6. `apps/web/src/features/desktop/ResourceExplorer.tsx`: `lost`, `unknown` 뱃지 분기 반영.
7. `apps/web/src/features/studio/DeveloperStudio.tsx`:
   - 산출물 다운로드 문구 좁힘 (`[전송 확인 완료]` 및 저장소 원본 미대조 명시).
   - 비동기 `runs` 도착 시 `activeRunId` 자동 동기화 보강.
8. `apps/web/tests/artifact-content-download-integrity.test.tsx`: 좁혀진 전송 확인 문구 6개 단언 반영.
9. `apps/web/tests/node-status-lost-unknown-guard.test.tsx`: 신규 작성. `lost`가 `enrolling`으로 둔갑하지 않고 `lost`로 유지되는지, 모르는 어휘가 `unknown`으로 유지되는지 검증 (6 passed).
10. `scratch/verify_narrowed_notices_and_node_status_chrome.py`: Google Chrome 153 실제 브라우저 E2E 검증 스크립트.

---

## 3. 검증 결과 및 증거 (Evidence)

### 3.1 실제 Google Chrome 153.0.7070.0 (Blink) 실측 수용
- **실행 명령**: `.venv\Scripts\python.exe scratch/verify_narrowed_notices_and_node_status_chrome.py`
- **결과**: `Exit Code 0`, 전 항목 통과.
- **실측 항목**:
  1. `lost` 노드가 Chrome DOM에서 `role="alert"`와 함께 `LOST (단절)` 뱃지로 렌더링되며 합류 중(`enrolling`)으로 둔갑하지 않음 확인 (`PASSED`).
  2. 모르는 백엔드 어휘(`active`)가 Chrome DOM에서 `role="status"`와 함께 `UNKNOWN (미확인)` 뱃지 및 "조용한 합류 둔갑 차단" 고지로 렌더링됨 확인 (`PASSED`).
  3. `DeveloperStudio`에서 결과 파일 다운로드 클릭 시 `[전송 확인 완료]` 및 "수신 바이트와 서버 헤더 일치 · 저장소 원본 대조 아님" 고지가 렌더링되고 과거 과장 문구 `[무결성 검증 완료]`가 완전히 제거되었음 확인 (`PASSED`).
  4. 서버 응답 헤더 부재 시 `[전송 헤더 누락 · 저장 차단]` 고지 및 파일 저장 차단 확인 (`PASSED`).
- **생성된 산출물**:
  - `scratch/chrome_narrowed_notices_and_node_status_acceptance_result.json`
  - `scratch/real_chrome_node_status_lost_unknown.png`
  - `scratch/real_chrome_narrowed_transmission_notice.png`
  - *(주의: 부트스트랩 일회용 토큰 등 민감 화면은 스크린샷 캡처에서 철저히 배제됨)*

### 3.2 단위/통합 테스트 (Vitest 73개 파일 642개 테스트 전수 통과)
- **실행 명령**: `npm test` (apps/web)
- **결과**: `73 passed (73)`, `642 passed (642)`, `Duration: 12.97s`.
- 돌연변이 사살 검증:
  - `nodeObservation.ts`에서 `mappedStatus = 'enrolling'`으로 돌연변이 주입 시 `node-status-lost-unknown-guard.test.tsx` 2 failed로 돌연변이 완벽 사살(KILLED) 확인 후 원복.

### 3.3 게이트 검사 도구 전수 통과
- `python tools/check_frontend_integrity.py`: `Scanning 82 frontend production source files under apps/web/src ... All 7 integrity rules satisfied (0 violations)` (EXIT 0).
- `python tools/check_contract_bindings.py`: `PASS check_contract_bindings: 39 fixtures each referenced by a test; 12 bound kernel responses each have a serving-anchor test` (EXIT 0).
- `python tools/check_docs.py`: `PASS: 24 original hashes, 710 versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG` (EXIT 0).
