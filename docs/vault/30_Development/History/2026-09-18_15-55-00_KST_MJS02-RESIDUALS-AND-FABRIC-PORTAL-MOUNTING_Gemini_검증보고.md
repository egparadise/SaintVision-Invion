---
doc_id: "HIST-GEMINI-20260918-08"
title: "2026-09-18 15:55 KST MJS02 잔여(R1/R2) 조치 및 제어 평면 포털 마운팅 Gemini 검증보고"
version: "1.0.0"
status: "approved"
author: "Gemini"
created: "2026-09-18T15:55:00+09:00"
updated: "2026-09-18T15:55:00+09:00"
timezone: "Asia/Seoul"
base_sha: "04863a3"
source_of_truth: "Git"
---

# MJS02 잔여(R1/R2) 조치 및 제어 평면 포털 마운팅 Gemini 검증보고 (2026-09-18 15:55 KST)

## 1. 개요 및 배경

- **실행 주체**: Gemini (Antigravity)
- **독립 감사/검토자**: Codex, Claude
- **기준 Commit**: `04863a3`
- **Codex 재검토(`HIST-CODEX-PITR-MJS02-REVIEW-001`, `ccdc41f`) 수용 및 잔여 2건 완전 조치**:
  1. **MJS02-R2 (P2, 인접 상수 UI 단언 잔여)**:
     - `tools/run_browser_smoke.mjs` 914~915행에 `const hasDesktopShell = true; assert('Web Desktop Shell provides bidirectional switcher (Desktop <-> Portal)', hasDesktopShell);`가 잔존하여 관측되지 않은 UI 동작이 PASS 카운트에 포함되던 문제.
     - 조치: `recordUnverified`로 전면 전환하고 `[PASS]` 카운트에서 제외. 이제 Track 15의 4대 UI 불변식(양방향 전환기, 창 관리자, 키보드 A11y, 레이아웃 영속성)이 전수 `[UNVERIFIED]`로 투명하게 로깅되고 별도 대화형 브라우저 레인으로 이관됨.
     - 요약 배너의 `total === 0`일 때 `NaN%` 발생 가능성을 `${total > 0 ? Math.round((passed / total) * 100) : 0}%`로 원천 방어.
     - 최종 스모크: **198/198 observed checks passed (100%) | 4 unverified UI invariants deferred to browser lane**.
  2. **MJS02-R1 (P2, 신규 회귀 시험의 실행 환경 경계)**:
     - `tests/test_browser_smoke_boundary.py`가 백엔드 없는 환경(예: port 0, 오프라인)에서 전체 스모크 서브프로세스를 호출하여 네트워크 연결 오류로 실패하던 결함.
     - 조치:
       - **오프라인 격리 요약 하네스 신설 (`test_isolated_summary_harness_verifies_exit_codes_and_unverified_exclusion`)**: Codex의 리뷰 하네스 검증 방식을 정규 채택하여, Node.js VM 내에서 `recordUnverified` 헬퍼와 Track 15 UI 슬라이스, 요약 연산만을 네트워크 및 백엔드 의존성 없이 100% 격리 검증. 시드 `[2, 2, 0]`, `[1, 2, 1]`, `[0, 0, 1]` 전수에서 exit code 및 4개 unverified 집계, NaN% 미출력 검증.
       - **라이브 스모크 통합 경계 분리 (`test_smoke_runner_reports_four_unverified_and_observed_checks_in_integration`)**: `http://127.0.0.1:8080/v1/health` 사전 프로브를 통해 백엔드 미기동 시 `pytest.skip`으로 처리하여 오프라인 기본 테스트 스위트의 결정론적 100% 합격을 보장.
  3. **CX-01 제어 평면 16개 정본 경로 포털 및 시뮬레이터 전면 연동**:
     - `apps/web/src/shared/ui/Header.tsx`: 네비게이션 탭에 `fabric` (`가상 패브릭 (CX-01)`) 추가.
     - `apps/web/src/app/App.tsx`: Classic Portal 모드에서도 `ResourceExplorer`가 마운트되도록 렌더링 연결 (Web Desktop 및 Classic Portal 양쪽에서 16개 제어 평면 경로 즉시 접근 가능).
     - `apps/web/src/features/placement/PlacementSimulator.tsx`: 백엔드와 불일치하던 POST 방식을 정본 `GET /v1/pools/{selectedPoolId}/placement-preview?cpuMillicores=...&ramBytes=...&gpuDevices=...` 쿼리로 완전 정합하고, 샤드 배치 상태 테이블에 적격 후보 바인딩.
     - `apps/web/tests/desktop-layout.test.tsx`: Header의 `fabric` 탭 렌더링 단위 테스트 추가 (Vitest 31개 스위트 **301/301 tests 100% 통과**).

---

## 2. 실측 검증 결과

| 검증 항목 | 실행 명령 | Exit Code | 실측 결과 |
|---|---|---|---|
| **스모크 경계 회귀 시험 (MJS02-R1/R2)** | `.venv\Scripts\python -m pytest tests/test_browser_smoke_boundary.py -v` | **0** | **3 passed in 3.31s** (상수 부재, 오프라인 격리 하네스 3시드, 4 unverified 검증) |
| **배포 런처 회귀 시험 (VB-LAUNCH-01)** | `.venv\Scripts\python -m pytest tests/test_deploy_intranet_preflight.py -v` | **0** | **10 passed in 5.56s** |
| **프론트엔드 Vitest 전체** | `npm --prefix apps/web test -- --run` | **0** | **31개 파일 301 passed / 0 failed in 3.82s** |
| **Vite 프로덕션 번들 빌드** | `npm --prefix apps/web run build` | **0** | `tsc -b && vite build` 클린 생성 (4.83s, 0 error/0 warning) |
| **스모크 러너 실실행** | `node tools/run_browser_smoke.mjs` | **0** | **198/198 observed checks passed (100%)**, 4 unverified UI invariants deferred |
| **문서 정합성 검증** | `.venv\Scripts\python tools/check_docs.py` | **0** | **PASS**: 24 original hashes, 552 versioned docs, wiki links, 48 tasks |
| **온톨로지 정합성 검증** | `.venv\Scripts\python tools/check_ontology.py` | **0** | **PASS**: RDF parsing, TTL/JSON-LD, 48 task mappings, positive SHACL |

---

## 3. 미노출 제어 평면 16개 정본 경로 최종 현황

사용자가 요청한 16개 제어 평면 경로의 프론트엔드 실장 상태:

1. `GET /v1/storage/contributions` — **실장 완료** (`fabricControlApi.ts:getStorageContributions`, `ResourceExplorer.tsx:loadStorage`)
2. `POST /v1/storage/contributions` — **실장 완료** (`fabricControlApi.ts:registerStorageContribution`, `ResourceExplorer.tsx:handleRegisterContribution`)
3. `DELETE /v1/storage/contributions/{id}` — **실장 완료** (`fabricControlApi.ts:revokeStorageContribution`, `ResourceExplorer.tsx:handleRevokeContribution`)
4. `POST /v1/storage/contributions/{id}/activation` — **실장 완료** (`fabricControlApi.ts:activateStorageContribution`, `ResourceExplorer.tsx:handleActivateContribution`)
5. `GET /v1/storage/locations` — **실장 완료** (`fabricControlApi.ts:getStorageLocations`, `ResourceExplorer.tsx:loadStorage`)
6. `GET /v1/pools/{id}/capacity` — **실장 완료** (`fabricControlApi.ts:getPoolCapacity`, `ResourceExplorer.tsx:loadPoolData`)
7. `GET /v1/pools/{id}/placement-preview` — **실장 완료** (`fabricControlApi.ts:getPoolPlacementPreview`, `ResourceExplorer.tsx:handlePlacementPreview`, `PlacementSimulator.tsx`)
8. `POST /v1/pools/{id}/plans` — **실장 완료** (`fabricControlApi.ts:createPoolPlan`, `ResourceExplorer.tsx:handleCreatePlan`)
9. `PUT /v1/pools/{id}/members/{node_id}` — **실장 완료** (`fabricControlApi.ts:addPoolMember`, `ResourceExplorer.tsx:handleAddMember`)
10. `DELETE /v1/pools/{id}/members/{node_id}` — **실장 완료** (`fabricControlApi.ts:removePoolMember`, `ResourceExplorer.tsx:handleRemoveMember`)
11. `GET /v1/nodes/{node_id}` — **실장 완료** (`fabricControlApi.ts:getNodeDetail`, `ResourceExplorer.tsx:loadNodeDetailData`)
12. `POST /v1/nodes/{node_id}/heartbeats` — **실장 완료** (`fabricControlApi.ts:postNodeHeartbeat`, `ResourceExplorer.tsx:handleHeartbeat`)
13. `POST /v1/nodes/liveness-sweeps` — **실장 완료** (`fabricControlApi.ts:triggerLivenessSweep`, `ResourceExplorer.tsx:handleLivenessSweep`)
14. `POST /v1/discovery/announcements` — **실장 완료** (`fabricControlApi.ts:broadcastAnnouncement`, `ResourceExplorer.tsx:handleBroadcastAnnouncement`)
15. `POST /v1/discovery/candidates/{id}/admission` — **실장 완료** (`fabricControlApi.ts:admitDiscoveryCandidate`, `ResourceExplorer.tsx:handleAdmitCandidate`)
16. `DELETE /v1/discovery/candidates/{id}` — **실장 완료** (`fabricControlApi.ts:declineDiscoveryCandidate`, `ResourceExplorer.tsx:handleDeclineCandidate`)

**결과: 16개 전 경로가 클라이언트 호출 및 UI 인터랙션(Web Desktop Shell 및 Classic Portal)으로 100% 완전 노출됨.**
