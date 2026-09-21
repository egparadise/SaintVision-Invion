---
doc_id: "VF-GM04-MODEL-STUDIO-SHARDS-ADR041-GEMINI-001"
title: "VF-GM-04 Model Studio 샤드·복제본 매트릭스, ADR-041 네트워크 제약 경고 및 노드 적격성 실행 계획기 실증 보고"
version: "1.0.0"
status: "verified"
author: "Gemini"
reviewer: "Codex"
updated: "2026-09-21T18:05:00+09:00"
code_ref_tip: "integration/all-agents-unified"
source_of_truth: "Git"
tags: ["vf-gm-04", "model-studio", "shard-matrix", "adr-041", "execution-planner", "tensor-parallel-lan-warning", "observation-node-exclusion", "mutation-testing"]
---

# VF-GM-04 Model Studio 샤드·복제본 매트릭스, ADR-041 네트워크 제약 경고 및 노드 적격성 실행 계획기 실증 보고

## 1. 개요 및 목적

사용자 기승인 트랙 지침에 따라 `VF-GM-03` (`inv://` File Explorer) 및 Claude `RunResultView` 계약 결속 완결 직후 차기 준비 완료 카드인 **`VF-GM-04` (Model Studio)**로 즉시 전환하여 구현 및 실증을 완결하였다.

본 작업의 핵심 목표:
1. **모델 Manifest 쿼리 및 메타데이터 정합성**: `projectId`, `modelId`, `version` 3개 필드 기반 매니페스트 조회, 포맷(`safetensors`), 바이트 크기, 해시(`sha256:...`), 라이선스 정책 및 정적 마크업 불변식(`'정확한 모델 ID'`, 초기 빈 마운트 시 허위 샘플 모델 배제) 준수.
2. **샤드 및 복제본 패브릭 매트릭스 (Shard & Replica Fabric Matrix)**: 샤드별 byteRange, 레이어 매핑, 노드별 복제본 상태(정상/누락), 저하 상태 감지 시 `replica-degraded-badge` (`role="alert"`) 표출, 생존 적격 노드(surviving eligible nodes) 계산.
3. **샤드 복구(Repair) 방어 및 부분 저하 감지**:
   - 생존 적격 노드가 0개일 때 복구 버튼 비활성화 및 `no-surviving-repair-nodes` (`role="alert"`) 고지.
   - 복구 실패 시 거짓 성공 은폐 방지 및 `shard-repair-error-alert` (`role="alert"`) 표출.
   - 복구 후에도 복제본이 1/2로 저하된 경우 `shard-repair-warning-alert` (`role="alert"`) 표출.
   - 2/2 정상 복제본 복원 시에만 `shard-repair-success-banner` 표출.
4. **ADR-041 분산 패브릭 제약 및 노드 적격성 실행 계획기 (Execution Planner)**:
   - 5대 실행 모드 지원: `single_node`, `request_routing`, `data_parallel`, `tensor_pipeline_parallel`, `cpu_gpu_offload`.
   - **ADR-041 1Gbps LAN 제약 방어**: `tensor_pipeline_parallel` 선택 및 복수 노드(selectedNodeIds > 1) 할당 시, All-Reduce 레이턴시 병목 경고 배너(`data-testid="tensor-parallel-lan-warning"`, `role="alert"`) 강제 표출.
   - **관측 전용 노드(Node-04) 연산 할당 절대 배제**: `observationOnly: true` 또는 `schedulable: false`인 노드는 체크박스를 엄격히 `disabled` 처리하고 `data-testid="node-ineligible-badge"` (`role="alert"`) 표출.
   - **VRAM 수용성(Feasibility) 엄격 판정**: 할당된 적격 노드들의 가용 VRAM 합산이 모델 총 크기에 미달할 경우 `data-testid="plan-infeasible-alert"` (`role="alert"`) 표출 및 거절 사유 고지.

---

## 2. 세 가지 구분 원칙에 입각한 실측 현황 분석

| 구분 범주 | 구체적 검증 내용 및 실측 결과 |
|---|---|
| **1. 돌연변이로 실측해 깨진 것 (Measured Mutation Failures)** | • **Mutation 1 (ADR-041 LAN 경고 가드 우회 및 false 강제 변조)**: `showTensorLanWarning`을 `false`로 강제했을 때, `[VF-GM-04-ADR041-LAN-WARNING]` 시험에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected null not to be null`<br>&nbsp;&nbsp;`at tests/model-studio-dom.test.tsx:404:28` (`expect(lanWarning).not.toBeNull()`)<br>• **Mutation 2 (Node-04 관측 전용 노드 체크박스 비활성화 가드 우회)**: `isObservation = false`로 강제했을 때, `[VF-GM-04-ADR041-OBSERVATION-GUARD]` 시험에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected false to be true // Object.is equality`<br>&nbsp;&nbsp;`- Expected: true, + Received: false`<br>&nbsp;&nbsp;`at tests/model-studio-dom.test.tsx:426:32` (`expect(checkbox?.disabled).toBe(true)`)<br>• **Mutation 3 (VRAM 부족 상태를 실행 가능으로 허위 판정 변조)**: `isFeasible = true`로 강제했을 때, `[VF-GM-04-FEASIBILITY-REJECTION]` 시험에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected null not to be null`<br>&nbsp;&nbsp;`at tests/model-studio-dom.test.tsx:453:33` (`expect(infeasibleBadge).not.toBeNull()`)<br>• **Mutation 4 (샤드 복구 실패 시 오류 알림 은폐 및 무시 변조)**: `handleRepairShard`에서 `if (!res.success)` 검사를 `if (false)`로 우회했을 때, `[VF-GM-04-REPAIR-FAIL]` 시험에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected null not to be null`<br>&nbsp;&nbsp;`at tests/model-studio-dom.test.tsx:303:29` (`expect(repairError).not.toBeNull()`) |
| **2. 소스를 읽어 판단한 것 (Source-Read Analysis)** | • `DesktopShell.tsx`에서 클러스터 상태 노드 목록(`nodes`)을 `<ModelStudioView clusterNodes={nodes} />`로 주입하도록 결속하여 데스크톱 쉘 통합을 완성함.<br>• `fabric-observation.test.tsx` 정적 마크업 테스트 계약을 소스 수준에서 점검하여 초기 렌더링 시 하드코딩된 샘플 모델명(/llama\|qwen\|복구 완료\|SAMPLE_/i)이 배제되고 `'정확한 모델 ID'` 안내 문구가 표출됨을 확인.<br>• TypeScript 컴파일러(`tsc -b`) 린트 규칙(`noUnusedLocals`)을 위해 미사용 타입 임포트(`ExecutionPlanNodeAssignment`)와 루프 로컬 변수(`vram`)를 정리하여 프로덕션 빌드를 무결하게 만듦. |
| **3. 아직 확인 못 한 것 (Unverified / Deferred Invariants)** | • 물리적 GPU 노드 간 실제 PCIe/NVLink 또는 이더넷 NIC을 통한 텐서 분할 가중치 데이터 패킷 송수신 속도.<br>• 백엔드 실제 vLLM / ONNX Runtime 분산 컨테이너 워커 프로세스의 실제 메모리 점유 및 연산 동기화.<br>• 상기 분산 가속기 물리 하드웨어 동작은 백엔드 오케스트레이터 및 실제 GPU 클러스터 통합 E2E 레인으로 이관함. |

---

## 3. 검증 결과 및 회귀 시험 지표

### 3.1 테스트 카운트 증가 보고 (기준선 명시)
- **`apps/web/tests/model-studio-dom.test.tsx` 신규 생성**: **10 tests 100% PASS**
  1. `[VF-GM-04-QUERY] queries model and renders manifest metadata`
  2. `[VF-GM-04-SHARD-MATRIX] renders shards matrix and surfaces degradation badge on missing replica`
  3. `[VF-GM-04-REPAIR-GUARD] disables repair and displays alert when 0 surviving eligible nodes exist`
  4. `[VF-GM-04-REPAIR-FAIL] surfaces honest error alert when shard repair fails (Catches Mutation 4)`
  5. `[VF-GM-04-REPAIR-PARTIAL] surfaces warning alert when repaired shard remains degraded`
  6. `[VF-GM-04-REPAIR-SUCCESS] surfaces success banner when shard is restored to 2/2 healthy`
  7. `[VF-GM-04-ADR041-LAN-WARNING] displays ADR-041 LAN constraint warning when tensor_pipeline_parallel is selected across multi-node (Catches Mutation 1)`
  8. `[VF-GM-04-ADR041-OBSERVATION-GUARD] strictly prevents observation-only Node-04 from being assigned execution (Catches Mutation 2)`
  9. `[VF-GM-04-FEASIBILITY-REJECTION] rejects placement with role="alert" when allocated VRAM is insufficient (Catches Mutation 3)`
  10. `[VF-GM-04-FEASIBILITY-SUCCESS] renders feasible badge when allocated VRAM is sufficient`
- **전체 Vitest 스위트**: 직전 보고 기준 **42개 파일 389 passed**에서 **43개 파일 399 passed**로 순증 (**from 389 to 399, net +10 tests**, 43개 테스트 파일 100% 합격).

### 3.2 빌드 및 거버넌스 도구 전수 합격 증거
- **웹 프로덕션 빌드 (`tsc -b && vite build`)**: Exit Code `0`, 90개 모듈 번들링 완료.
- **문서 무결성 검증 (`python tools/check_docs.py`)**: Exit Code `0` (PASS: 24 original hashes, 618 versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG).
- **온톨로지 검증 (`python tools/check_ontology.py`)**: Exit Code `0` (PASS: RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings, positive SHACL, 4 rejected invalid fixtures, 4 competency queries, Obsidian mirrors).
- **옵시디언 동기화 검사 (`python tools/sync_obsidian.py --check`)**: Exit Code `0` (CHECK: 1410 managed files, 0 pending exports, 0 conflicts. No writes).

---

## 4. 이어서 할 다음 작업 (Next Action)

- **다음 담당**: Gemini (Antigravity)
- **다음 작업 카드**: **`VF-GM-05` (Terminal & Virtual IDE Web Session UX)**
  - 가상 단말(Terminal) PTY 스트림 연결, 세션 복원, 접속 불능/재연결 상태 처리.
  - 가상 IDE 웹 에디터 탭 전환, 실시간 린트 피드백, 저장 시 무결성 검증, 접근성 및 부분 실패 방어.
