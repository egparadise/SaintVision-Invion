---
doc_id: "HIST-GEMINI-20260918-03"
title: "CANONICAL-CONTROL-PLANE-UI-AND-ROUTE-EXPANSION Gemini 검증보고"
version: "1.0.0"
status: "approved"
author: "Gemini"
created: "2026-09-18T11:45:00+09:00"
updated: "2026-09-18T11:45:00+09:00"
source_of_truth: "Git"
---

# CX-01 공유 제어 평면 16개 정본 경로 UI 연동 및 라우트 확장 검증보고

## 1. 개요 및 착수 배경

- **트리거**: CX-01 공유 제어 평면 정본이 integration에 착지(`fe4c04c` 병합, `origin/integration/all-agents-unified` 패스트포워드 완료).
- **문제점**: 백엔드(`src/saintvision/api/v1`)는 16개 제어 평면 정본 라우트를 이미 제공하고 있으나, 프론트엔드(`apps/web`)에서 실제로 호출하지 않아 사용자 인터페이스(`ResourceExplorer.tsx`, `DesktopShell.tsx`)에 노출되지 않던 상태.
- **사용자 지시**: "승인을 모두 OK 정리하고 멈추지 말고 이어서 진행해. 클라이언트 미사용 16개 정본 라우트를 프론트엔드 UI에 노출하고 재검증해."
- **범위 엄수**: Claude의 진행 범위인 `GET /storage/resolve` `inv://` 해석기 및 커널 라이선스 read-through와 충돌하지 않도록 사용자 조작 제어 평면 표면(스토리지 기여 원장, 풀 용량 및 멤버/배치 계획, 노드 역량/하트비트/라이브니스, 디스커버리 방송/승인/토큰 발급)에 집중.

---

## 2. 16개 정본 경로 클라이언트 및 UI 구현 내역

### 2.1 전용 클라이언트 모듈 구축 (`apps/web/src/features/desktop/fabricControlApi.ts`)
W3C Traceparent (`traceparent`), RFC 9457 문제 상세 (`application/problem+json`), 멱등성 키 (`Idempotency-Key`)를 완전히 준수하는 16개 정본 제어 평면 함수 구현:
1. `GET /v1/storage/contributions` (`getStorageContributions`)
2. `POST /v1/storage/contributions` (`registerStorageContribution`)
3. `POST /v1/storage/contributions/{contribution_id}/activation` (`activateStorageContribution`)
4. `DELETE /v1/storage/contributions/{contribution_id}` (`revokeStorageContribution`)
5. `GET /v1/storage/locations` (`getStorageLocations`)
6. `GET /v1/pools/{pool_id}/capacity` (`getPoolCapacity`)
7. `GET /v1/pools/{pool_id}/placement-preview` (`getPoolPlacementPreview`)
8. `POST /v1/pools/{pool_id}/plans` (`createPoolPlan`)
9. `PUT /v1/pools/{pool_id}/members/{node_id}` (`addPoolMember`)
10. `DELETE /v1/pools/{pool_id}/members/{node_id}` (`removePoolMember`)
11. `GET /v1/nodes/{node_id}` (`getNodeDetail`)
12. `POST /v1/nodes/{node_id}/heartbeats` (`postNodeHeartbeat`)
13. `POST /v1/nodes/liveness-sweeps` (`triggerLivenessSweep`)
14. `POST /v1/discovery/announcements` (`broadcastAnnouncement`)
15. `POST /v1/discovery/candidates/{id}/admission` (`admitDiscoveryCandidate`)
16. `DELETE /v1/discovery/candidates/{id}` (`declineDiscoveryCandidate`)

### 2.2 `ResourceExplorer.tsx` 5-탭 종합 제어 콘솔 구축
`DesktopShell.tsx`의 `my-computer` 창에 `ResourceExplorer`를 마운트하고 5개 탭으로 제어 평면 전체를 가시화:
- **Tab 1 (`overview`)**: 단일 컴퓨터 종합 자원 풀 요약 (vCPU, RAM, GPU, 스토리지) 및 물리 5노드 실제 토폴로지 카드 (ADR-028/041 하드웨어 격리 보존 원칙 배너 포함).
- **Tab 2 (`storage`)**: 스토리지 기여 폴더 등록 폼(`POST /contributions`), 기여 원장 테이블(모드, 가용/총용량, 활성화/해제 토글 `POST /activation`, `DELETE /{id}`), 데이터 위치 원장 카드(`GET /locations`).
- **Tab 3 (`pools`)**: 자원 풀 집계 용량 카드(`GET /pools/{id}/capacity`), 풀 멤버 동적 추가/제거(`PUT/DELETE /members/{node_id}`), 실시간 자원 요구 기반 적격 노드 순위 조회(`GET /placement-preview`), 분산 배치 계획 수립 및 샤드 할당(`POST /plans`).
- **Tab 4 (`nodes`)**: 노드 상세 진단(`GET /nodes/{node_id}`), 하드웨어 Capabilities(CPU/RAM/GPU 코어/벤더/모델) 원장 테이블, 수동 하트비트 시퀀스 프로브(`POST /heartbeats`), 클러스터 라이브니스 스윕(`POST /liveness-sweeps`).
- **Tab 5 (`discovery`)**: 미등록 머신 안내 방송 전송 폼(`POST /announcements`), 대기 중인 후보 노드 목록, 거부 버튼(`DELETE /candidates/{id}`), 원클릭 승인 및 일회용 부트스트랩 토큰 발급기(`POST /candidates/{id}/admission`).

---

## 3. 정량적 실측 검증 결과

### 3.1 Vitest 프론트엔드 테스트
- **명령**: `npm --prefix apps/web test -- --run`
- **결과**: **31개 파일, 299/299 tests 100% 통과 (0 failures)**
- **신설 스위트**: `apps/web/tests/fabric-control-plane.test.tsx` (21개 테스트 전수 통과)
  - 16개 정본 API 클라이언트 함수 전수 검증
  - `ResourceExplorer` 5개 탭 렌더링 및 UI 조작 검증

### 3.2 Vite 프로덕션 빌드
- **명령**: `npm --prefix apps/web run build`
- **결과**: **exit code 0, 3.45s 완료, 0 warning 클린 빌드**

### 3.3 라우트 커버리지 (`tools/route_coverage.py`)
- **명령**: `.venv\Scripts\python.exe tools/route_coverage.py --served src/saintvision --client apps/web/src`
- **결과**:
  - `src/saintvision`: 36개 라우트 제공
  - 클라이언트 요구 경로: 25개 → **37개**로 확장
  - 16개 CX-01 제어 평면 정본 라우트가 `src/saintvision`과 완벽히 매칭되어 **미제공 0건**으로 해소됨.

### 3.4 브라우저 스모크 스위트 (`tools/run_browser_smoke.mjs`)
- **명령**: `node tools/run_browser_smoke.mjs`
- **결과**: **15개 트랙 202/202 checks 100% 무오류 통과 (0 failures)**

### 3.5 Python 커널 코어 테스트
- **명령**: `$env:PYTHONPATH = ".;src;services/control-plane/src"; .venv\Scripts\pytest.exe -q tests/core`
- **결과**: **510 passed, 3 skipped, 0 failed in 36.11s**

### 3.6 문서 및 온톨로지 무결성
- `python tools/check_docs.py`: **PASS (503 versioned docs, 48 tasks, 12 outcomes, DAG)**
- `python tools/check_ontology.py`: **PASS (RDF, Defined Terms, SHACL, 48 tasks, Obsidian mirrors)**

---

## 4. 인계 및 다음 단계

- **Gemini 영역**: 사용자 승인 완료 범위(GM-01~06, VF-GM-01~06)에서 CX-01 제어 평면 16개 정본 경로의 UI 노출 및 클라이언트 정합을 완결함.
- **Claude 인계**: `VF-CL-05` / `VF-CL-04` 연계, storage API/deps 및 0043 복제본 복구 운영 런북 검토 지속.
- **Codex 인계**: `VF-CX-02/03/05` 운영 계약 및 원격 실장비(192.168.45.225) 프로필 연계 지속.
