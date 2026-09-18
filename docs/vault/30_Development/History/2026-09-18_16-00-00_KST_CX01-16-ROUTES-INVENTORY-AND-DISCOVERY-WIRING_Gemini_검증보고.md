---
doc_id: "HIST-GEMINI-20260918-09"
title: "2026-09-18 16:00 KST CX-01 제어 평면 16개 정본 경로 전수 실장 현황 및 디스커버리 동기화 Gemini 검증보고"
version: "1.0.0"
status: "approved"
author: "Gemini"
created: "2026-09-18T16:00:00+09:00"
updated: "2026-09-18T16:00:00+09:00"
timezone: "Asia/Seoul"
base_sha: "8de61a6"
source_of_truth: "Git"
---

# CX-01 제어 평면 16개 정본 경로 전수 실장 현황 및 디스커버리 동기화 Gemini 검증보고 (2026-09-18 16:00 KST)

## 1. 개요 및 실장 현황

CX-01 제어 평면 착지 이후 클라이언트에서 미호출되던 16개 정본 엔드포인트에 대해 프론트엔드 API 클라이언트(`fabricControlApi.ts`), UI 화면(`ResourceExplorer.tsx`, `PlacementSimulator.tsx`, `App.tsx`), 및 단위/통합 테스트 스위트 전수 실장 및 검증을 완료하였다.

### CX-01 16대 제어 평면 라우트 전수 실장 현황표

| 번호 | 범주 | 정본 라우트 (HTTP + Path) | 클라이언트 API 함수 | UI 노출 위치 | 검증 상태 |
|:---:|:---|:---|:---|:---|:---:|
| 1 | Storage | `GET /v1/storage/contributions` | `getStorageContributions(nodeId?)` | `ResourceExplorer` 스토리지 탭 (기여 목록) | **PASS** (단위/통합) |
| 2 | Storage | `POST /v1/storage/contributions` | `registerStorageContribution(data, idempKey)` | `ResourceExplorer` 스토리지 탭 (신규 등록 폼) | **PASS** (단위/통합) |
| 3 | Storage | `POST /v1/storage/contributions/{id}/activation` | `activateStorageContribution(id)` | `ResourceExplorer` 스토리지 탭 (활성화 버튼) | **PASS** (단위/통합) |
| 4 | Storage | `DELETE /v1/storage/contributions/{id}` | `revokeStorageContribution(id)` | `ResourceExplorer` 스토리지 탭 (기여 해제 버튼) | **PASS** (단위/통합) |
| 5 | Storage | `GET /v1/storage/locations` | `getStorageLocations(options)` | `ResourceExplorer` 스토리지 탭 (위치 원장) | **PASS** (단위/통합) |
| 6 | Pools | `GET /v1/pools/{id}/capacity` | `getPoolCapacity(poolId)` | `ResourceExplorer` 풀 탭 (집계 용량 카드) | **PASS** (단위/통합) |
| 7 | Pools | `GET /v1/pools/{id}/placement-preview` | `getPoolPlacementPreview(poolId, cpu, ram, gpu)` | `ResourceExplorer` 풀 탭 & `PlacementSimulator` | **PASS** (단위/통합) |
| 8 | Pools | `POST /v1/pools/{id}/plans` | `createPoolPlan(poolId, planData)` | `ResourceExplorer` 풀 탭 (분산 배치 계획 수립) | **PASS** (단위/통합) |
| 9 | Pools | `PUT /v1/pools/{id}/members/{node_id}` | `addPoolMember(poolId, nodeId)` | `ResourceExplorer` 풀 탭 (멤버 노드 추가) | **PASS** (단위/통합) |
| 10 | Pools | `DELETE /v1/pools/{id}/members/{node_id}` | `removePoolMember(poolId, nodeId)` | `ResourceExplorer` 풀 탭 (멤버 노드 제외) | **PASS** (단위/통합) |
| 11 | Nodes | `GET /v1/nodes/{node_id}` | `getNodeDetail(nodeId)` | `ResourceExplorer` 노드 탭 (상세 & Capabilities) | **PASS** (단위/통합) |
| 12 | Nodes | `POST /v1/nodes/liveness-sweeps` | `triggerLivenessSweep()` | `ResourceExplorer` 노드 탭 (스윕 트리거 버튼) | **PASS** (단위/통합) |
| 13 | Nodes | `POST /v1/nodes/{node_id}/heartbeats` | `postNodeHeartbeat(nodeId, data)` | `ResourceExplorer` 노드 탭 (하트비트 전송) | **PASS** (단위/통합) |
| 14 | Discovery | `GET /v1/discovery/candidates` | `getDiscoveryCandidates(includeStale?)` | `ResourceExplorer` 디스커버리 탭 (후보 목록) | **PASS** (단위/통합) |
| 15 | Discovery | `POST /v1/discovery/candidates/{id}/admission` | `admitDiscoveryCandidate(id)` | `ResourceExplorer` 디스커버리 탭 (후보 승인 & 토큰) | **PASS** (단위/통합) |
| 16 | Discovery | `DELETE /v1/discovery/candidates/{id}` | `declineDiscoveryCandidate(id, reason?)` | `ResourceExplorer` 디스커버리 탭 (후보 거절 버튼) | **PASS** (단위/통합) |
| + | Discovery | `POST /v1/discovery/announcements` | `broadcastAnnouncement(data, tenantId)` | `ResourceExplorer` 디스커버리 탭 (안내 방송 브로드캐스트) | **PASS** (단위/통합) |

---

## 2. 세부 보강 및 동기화 조치

1. **`getDiscoveryCandidates` 클라이언트 함수 신설 및 스키마 확장**:
   - `apps/web/src/features/desktop/fabricControlApi.ts`에 `getDiscoveryCandidates(includeStale: boolean = false)` 정식 추가.
   - `DiscoveryCandidate` 인터페이스를 확장하여 백엔드 모델(`NodeAnnouncement`)의 `state: 'candidate'`, `firstSeenAt`, `lastSeenAt`, `announceCount` 필드를 온전히 수용.
2. **ResourceExplorer 디스커버리 탭 자동 동기화**:
   - `activeTab === 'discovery'` 전환 시 `loadDiscoveryCandidates()`가 자동으로 백엔드 실시간 후보 목록을 호출.
   - 미등록 머신 안내 방송(`POST /v1/discovery/announcements`) 성공 즉시 `loadDiscoveryCandidates()`를 연쇄 호출하여 신규 후보를 화면에 반영.
   - 백엔드의 초기 등록 상태인 `state === 'candidate'` 및 프론트엔드 폴백 `state === 'pending'` 모두에 대해 승인(Admission) 및 거절(Decline) 액션 버튼이 정상 활성화되도록 분기 정합.
3. **단위 테스트 스위트 확장**:
   - `apps/web/tests/fabric-control-plane.test.tsx`에 `getDiscoveryCandidates` 단위 테스트 추가 (`includeStale` 파라미터 분기 검증).
   - Vitest 전체 스위트가 **31개 파일 302/302 tests 100% 통과**로 증가.

---

## 3. 실측 검증 결과

### 1) 프론트엔드 단위 테스트 (Vitest)
```powershell
$ npm --prefix apps/web test -- --run
Test Files  31 passed (31)
     Tests  302 passed (302)
  Duration  3.20s
```

### 2) 배포 런처 & 스모크 경계 회귀 스위트 (Pytest)
```powershell
$ .venv\Scripts\python.exe -m pytest tests/test_browser_smoke_boundary.py tests/test_deploy_intranet_preflight.py -v
============================= 13 passed in 7.79s ==============================
```

### 3) API Contract Smoke Runner (`tools/run_browser_smoke.mjs`)
```powershell
$ node tools/run_browser_smoke.mjs
🎉 API Contract Smoke Summary: 198/198 observed checks passed (100%) | 4 unverified UI invariants deferred to browser lane
```
- Track 15 4대 UI 불변식(양방향 전환기, 창 관리자, 키보드 A11y, 레이아웃 영속성) 미검증 이관 유지.
- 관측된 198개 HTTP API 계약 전수 무오류 통과 (exit code 0).

### 4) 프로덕션 웹 빌드
```powershell
$ npm --prefix apps/web run build
✓ built in 3.36s (dist/index.html 0.75 kB, assets cleanly bundled)
```

### 5) 문서 및 온톨로지 무결성
```powershell
$ python tools/check_docs.py && python tools/check_ontology.py
PASS: 24 original hashes, 553 versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG.
PASS: RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings, positive SHACL, 4 rejected invalid fixtures, 4 competency queries, Obsidian mirrors.
```

---

## 4. 인계 및 다음 권장 작업

- **수신 대상**: Codex, Claude
- **완결 사항**:
  - CX-01 16대 제어 평면 라우트의 클라이언트 API/UI/테스트 전수 매핑 완결.
  - 디스커버리 후보 목록 조회(`GET /v1/discovery/candidates`) 및 상태 동기화 완결.
  - MJS02-R1/R2 조치 무결성 유지 (오프라인 격리 3시드 VM 하네스 및 live smoke 분리).
- **다음 첫 행동**:
  - Claude/Codex의 16개 라우트 UI 매핑 및 MJS02-R1/R2 조치 최종 검토 수신.
  - 대화형 브라우저 레인(Playwright/대화형 E2E) 확충을 통한 4대 미검증 UI 불변식의 증거 확보.
