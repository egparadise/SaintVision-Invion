---
doc_id: "VF-GM02-RESOURCE-EXPLORER-FABRIC-TOPOLOGY-GEMINI-001"
title: "VF-GM-02 ResourceExplorer 논리-물리 토폴로지 대조 및 3대 결함 패턴(Unwired/Dead/Masking) 방어 실증 보고"
version: "1.0.0"
status: "verified"
author: "Gemini"
reviewer: "Codex"
updated: "2026-09-21T17:30:00+09:00"
code_ref_tip: "integration/all-agents-unified"
source_of_truth: "Git"
tags: ["vf-gm-02", "resource-explorer", "hardware-isolation", "adr-028", "adr-041", "observation-only", "mutation-testing", "defect-pattern-guards"]
---

# VF-GM-02 ResourceExplorer 논리-물리 토폴로지 대조 및 3대 결함 패턴(Unwired/Dead/Masking) 방어 실증 보고

## 1. 개요 및 목적

사용자 기승인 트랙 지침에 따라 `UI-FB-03` 완결 직후 차기 준비 완료 카드인 **`VF-GM-02` (My Computer / Resource Explorer)**로 즉시 전환하여 구현 및 실증을 완결하였다.

본 작업의 핵심 목표:
1. **논리 통합 가상 자원 vs 물리 토폴로지 대조 렌더링**: 논리 총합(60 vCPU, 224 GiB RAM, 3 GPU 50GB VRAM, 10TB Storage)과 Node-01~05 물리적 독립 노드를 나란히 배치하고, 하드웨어 버스 마법 병합 왜곡을 방지하는 ADR-028/041 격리 보존 원칙 배너(`role="alert"`) 명시.
2. **관측 전용 노드(Node-04, 192.168.45.225) 경계 가드**: `schedulable: false`, 가용 코어 0, 가용 메모리 0, `관측 전용` 및 `스케줄 불가` 배지 표출 및 필터링 검증.
3. **UI 3대 결함 패턴(Defect Patterns 1~3) 사전 원천 차단**:
   - *패턴 1 (방어가 정의되었으나 컴포넌트에 미연결)*: 모든 액션 실패 시 붉은색 경고 박스(`role="alert"`, `data-testid="<tab>-action-error"`)를 렌더링하도록 4대 탭 피드백 핸들러 전수 연결.
   - *패턴 2 (상위 가드에 막혀 방어선이 죽어있음)*: 관측 전용 노드에 대한 연산 풀 편입 시도 차단(`handleAddMember`에 `observationOnly || !schedulable` 선행 가드 실장 및 드롭다운 비활성화).
   - *패턴 3 (캐시/폴백 경로가 실패를 은폐함)*: 노드 상세 조회 실패(`initialNodeDetailError`) 시 `useEffect`가 무단으로 에러를 덮어쓰고 재조회하던 결함을 정정(`!initialNodeDetail && !initialNodeDetailError`), 실패 시 하드웨어 원장을 완전 은폐하고 정직한 에러 표면화 및 재시도 제공.

---

## 2. 세 가지 구분 원칙에 입각한 실측 현황 분석

| 구분 범주 | 구체적 검증 내용 및 실측 결과 |
|---|---|
| **1. 돌연변이로 실측해 깨진 것 (Measured Mutation Failures)** | • **Mutation 1 (연산 풀 멤버 관측 전용 가드 해제)**: `ResourceExplorer.tsx:352` 가드를 주석 처리했을 때, Node-04 편입 시 `addPoolMember`가 1회 호출되어 즉시 실패 포착 (`AssertionError: expected "addPoolMember" to not be called at all, but actually been called 1 times`).<br>• **Mutation 2 (아키텍처 고지 배너 role="status" 변조)**: `fabric-disclaimer-banner`의 `role="alert"`를 `role="status"`로 변조했을 때 즉시 실패 포착 (`AssertionError: expected 'status' to be 'alert'`).<br>• **Mutation 3 (스토리지 실패 시 성공 배너로 은폐 변조)**: 실패 시 `storage-action-success`를 표출하도록 변조했을 때 즉시 실패 포착 (`AssertionError: expected null not to be null: storageActionError`). |
| **2. 소스를 읽어 판단한 것 (Source-Read Analysis)** | • `ResourceExplorer.tsx:262`의 `useEffect`에서 `initialNodeDetailError`가 주입되어도 `if (!initialNodeDetail)`만 검사하여 에러를 즉시 null로 초기화하고 재조회하던 비동기 결함을 소스 분석으로 규명하고, `if (!initialNodeDetail && !initialNodeDetailError)`로 정정함.<br>• 글로벌 라이브니스 스윕 버튼이 헤더에 위치함에도 피드백 메시지가 `nodes` 탭에만 국한되던 패턴 1 결함을 발견하여 `(activeTab === 'nodes' || activeTab === 'overview')`로 확장함. |
| **3. 아직 확인 못 한 것 (Unverified / Deferred Invariants)** | • 물리적 전원 단절 및 물리 PC 분리 시 실제 BMC/IPMI 하드웨어 센서 텔레메트리 단절 시각 동기화.<br>• 수십 기가바이트 스토리지 복제본의 실제 이기종 물리 디스크 I/O 전송 지연시간.<br>• 상기 물리 계층 검증은 브라우저/실장비 및 백엔드 하드웨어 인수 레인으로 이관함. |

---

## 3. 물리 노드 토폴로지 vs 논리 가상 자원 대조 명세

### 3.1 5대 노드 클러스터 실측 토폴로지
- **Node-01 (WinMain, `nod_01JABCDEF01`)**: Windows 11, 16C (12C 가용), 64 GiB RAM (36 GiB 가용), 1 GPU (NVIDIA RTX 4090 24GB), 2 TB Storage (2048 GiB), `schedulable: true`, `observationOnly: false`.
- **Node-02 (WinWork, `nod_01JABCDEF02`)**: Windows 11, 8C (4C 가용), 32 GiB RAM (12 GiB 가용), 1 GPU (NVIDIA RTX 3080 10GB), 1 TB Storage (1024 GiB), `schedulable: true`, `observationOnly: false`.
- **Node-03 (WinDev, `nod_01JABCDEF03`)**: Windows 11, 8C (6C 가용), 32 GiB RAM (20 GiB 가용), 0 GPU, 1 TB Storage (1024 GiB), `schedulable: true`, `observationOnly: false`.
- **Node-04 (LinuxBuild, `nod_01JABCDEF04`, 192.168.45.225)**: Ubuntu 24.04, 16C (**0C 가용**), 64 GiB RAM (**0 GiB 가용**), 0 GPU, 4 TB Storage (4096 GiB), **`schedulable: false`**, **`observationOnly: true`**.
- **Node-05 (LinuxTrain, `nod_01JABCDEF05`)**: Ubuntu 24.04, 12C (10C 가용), 32 GiB RAM (24 GiB 가용), 1 GPU (NVIDIA A4000 16GB), 2 TB Storage (2048 GiB), `schedulable: true`, `observationOnly: false`.

### 3.2 논리 통합 패브릭 합산 수치
- **논리 vCPU**: 총 **60 Cores** (스케줄 가용: **32 Cores**)
- **논리 RAM**: 총 **224 GB** (스케줄 가용: **92 GB**)
- **논리 가속기 (GPU)**: 총 **3 장 (독립)**, 총 VRAM **50 GB**
- **논리 스토리지**: 총 **10 TB** (`10240 * 1024^3` 바이트)
- **물리 격리 보존 원칙 (ADR-028 / ARCH-WEB-FABRIC-001)**:
  `"논리 통합 자원은 INV 클러스터 제어 평면이 관측·합산한 전체 용량 스냅샷입니다. 서로 다른 물리 PC의 CPU 코어나 GPU VRAM이 단일 하드웨어 버스로 마법처럼 병합된 것이 아니며, 모든 실제 연산과 VRAM 배치는 작업의 데이터 근접성(Locality)과 스케줄러 정책에 따라 각 독립 물리 노드에 분산 격리 실행됩니다."` (고지 배너 `role="alert"` 상시 표출)

---

## 4. 검증 결과 및 회귀 시험 지표

### 4.1 테스트 카운트 증가 보고 (기준선 명시)
- **`apps/web/tests/resource-explorer-dom.test.tsx`**: 기존 8 tests에서 **14 tests**로 순증 (**net +6 tests**).
  1. `proves side-by-side comparison: renders 60 vCPU, 224 GB RAM, 3 GPU 50GB VRAM, 10TB Storage against 5 physical nodes`
  2. `proves ADR-041 observation-only isolation boundary: Node-04 displays observation badge, unschedulable badge, 0 allocatable cores and filters accurately`
  3. `proves Defect Pattern 1 & 2 guard: strictly rejects observation-only node (Node-04) from compute pool enrollment`
  4. `proves Defect Pattern 1 & 3 guard: storage registration failure renders honest role="alert" error banner`
  5. `proves Defect Pattern 1 & 3 guard: cluster sweep failure renders honest role="alert" error banner on overview`
  6. `proves Defect Pattern 3 guard: node detail error suppresses hardware capabilities and allows retry`
- **전체 Vitest 스위트**: 직전 보고 기준 **354 passed**에서 **375 passed**로 순증 (**net +21 tests**, 40개 테스트 파일 100% 합격).

### 4.2 빌드 및 거버넌스 도구 전수 합격 증거
1. **TypeScript & Vite 프로덕션 빌드**:
   `tsc -b && vite build` ➔ 3.23s 클린 빌드 완료 (0 error, 0 warning).
2. **Pytest 클라이언트 라우트 커버리지 (`test_route_coverage.py`)**:
   30 passed in 0.67s (100% 통과).
3. **문서 정합성 (`tools/check_docs.py`)**:
   PASS: 24 original hashes, 613 versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG.
4. **온톨로지 무결성 (`tools/check_ontology.py`)**:
   PASS: RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings, positive SHACL, 4 rejected invalid fixtures, 4 competency queries, Obsidian mirrors.
5. **Obsidian 동기화 사전 검사 (`tools/sync_obsidian.py --check`)**:
   CHECK: 1405 managed files, 0 pending exports, 0 conflicts. No writes.

---

## 5. 결론 및 인계

`VF-GM-02` (My Computer / Resource Explorer)의 논리-물리 자원 대조, ADR-028/041 하드웨어 격리 보존 원칙 고지, 관측 전용 노드(Node-04) 격리 가드, 그리고 3대 결함 패턴(미연결/사장 방어/캐시 은폐)을 원천 차단하는 회귀 방어선 구축을 완결하였다.

- **Outcome**: VF-GM-02 완료 (My Computer / Resource Explorer 하드웨어 대조 및 방어선 고정)
- **Code Reference Tip**: `integration/all-agents-unified`
- **다음 준비 완료 카드 (Next Ready Card)**: **`VF-GM-03` (`inv://` File Explorer)**
  - 주소창 탐색, 클라이언트 SHA-256 무결성, 1/2 복제본 저하 감지 및 원클릭 복구 UX를 동일한 무결성 원칙하에 연속 추진한다.
