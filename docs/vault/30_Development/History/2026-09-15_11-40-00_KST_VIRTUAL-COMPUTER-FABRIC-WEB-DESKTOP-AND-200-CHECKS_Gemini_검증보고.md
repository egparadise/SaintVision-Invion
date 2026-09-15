---
doc_id: "REPORT-GEMINI-HIST-031"
title: "Virtual Computer Fabric Web Desktop 및 200 Browser Smoke Checks 전수 통과 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-15T11:40:00+09:00"
updated: "2026-09-15T11:40:00+09:00"
source_of_truth: "Git"
---

# Virtual Computer Fabric Web Desktop 및 200 Browser Smoke Checks 전수 통과 검증보고

## 1. 개요 및 배경

- **실행 주체**: Gemini (Antigravity)
- **일시**: 2026-09-15T11:40:00+09:00 (KST)
- **브랜치**: `agent/gemini/virtual-fabric` (Base: `b9752a8`)
- **대상 작업 카드**: `VF-GM-01` ~ `VF-GM-06` (단일 가상 컴퓨터 및 분산 모델 Fabric 보강 트랙)
- **대상 파일**:
  - `apps/web/src/contracts/virtualFabric.ts`
  - `apps/web/src/features/desktop/DesktopShell.tsx`
  - `apps/web/src/features/desktop/DesktopWindow.tsx`
  - `apps/web/src/features/desktop/ResourceExplorer.tsx`
  - `apps/web/src/features/desktop/InvFileExplorer.tsx`
  - `apps/web/src/features/desktop/ModelStudioView.tsx`
  - `apps/web/src/features/desktop/TerminalSessionView.tsx`
  - `apps/web/src/app/App.tsx`
  - `apps/web/src/shared/ui/Header.tsx`
  - `apps/web/tests/virtual-desktop.test.ts`
  - `tools/run_browser_smoke.mjs`
- **목적**:
  - 2026-09-15 승인된 단일 가상 컴퓨터 보강 설계(`ARCH-WEB-FABRIC-001`, `ROADMAP-VIRTUAL-COMPUTER-001`)에 따라, 웹 브라우저에서 다수의 PC를 하나의 가상 컴퓨터처럼 사용할 수 있는 Web Desktop Shell 환경 구축.
  - "사용자가 보는 것은 하나의 가상 컴퓨터지만 UI에는 논리 합계와 Node별 실제 topology를 함께 표시하고, 물리 CPU/GPU/RAM이 하나의 장치로 합쳐진다는 거짓 표현을 쓰지 않는다"는 불변 원칙의 엄격한 구현.
  - E2E 브라우저 스모크 검증을 15개 트랙 **200/200 checks (100%)**로 확장하고, Vitest 스위트를 23개 파일 **143/143 tests (100%)**로 전수 검증.

---

## 2. 카드별 구현 내역

### 2.1 VF-GM-01: Web Desktop Shell과 navigation
- `DesktopShell.tsx`:
  - macOS/현대적 Web Desktop 인터페이스 구현: Top System Menu Bar, Start Menu, System Tray, Desktop Shortcut Grid, Floating Bottom Dock.
  - `DesktopWindowComponent` 윈도우 매니저: 신호등 버튼(🔴 Close, 🟡 Minimize, 🟢 Maximize/Restore), 드래그, Z-Index 포커스 승격, `localStorage` 기반 창 배치 세션 복원.
  - 포털과 데스크톱 간 양방향 전환: 🖥️ Web Desktop <-> 📑 Classic Portal 즉시 스위칭 지원.

### 2.2 VF-GM-02: My Computer / Resource Explorer
- `ResourceExplorer.tsx`:
  - 논리 통합 가상 자원 풀(60 vCPU, 224 GiB RAM, 3 GPU 50GB VRAM, 10TB Storage)과 물리 노드별 실제 토폴로지(Node-01~05)를 나란히 대조 표시.
  - 물리 장치 분산 보존 원칙(ADR-028 / ARCH-WEB-FABRIC-001) 경고 배너 탑재: 물리 장치가 하나로 마법처럼 합쳐진다는 왜곡을 방지하고 실제 격리 실행 경계를 투명하게 명시.
  - 관측 전용 노드(Node-04 192.168.45.225) 스케줄 불가(`schedulable: false`, 가용 코어 0) 안전 가드 실측 반영.

### 2.3 VF-GM-03: inv:// File Explorer
- `InvFileExplorer.tsx`:
  - `inv://` 네임스페이스(`inv://workspaces`, `inv://models`, `inv://datasets`, `inv://artifacts`) 주소창 및 논리 드라이브 탐색.
  - 클라이언트 측 SHA-256 무결성 해시 대조, 분산 복제본(Replicas) 위치 추적.
  - 노드 장애/부분 실패(Partial Failure) 감지: 복제본 중 일부가 비가용 상태일 때 `1/2 Replicas Available (Degraded)` 경고 및 생존 노드 기반 원클릭 복구(Repair) 액션 연동.
  - 실행 증거/영수증 파일의 GC 제외 고정(Pin) 정책 준수.

### 2.4 VF-GM-04: Model Studio와 shard/replica 상태
- `ModelStudioView.tsx`:
  - `ModelManifest` 등록부: SafeTensors, GGUF 등 모델 가중치 불변 해시 관리.
  - Shard & Replica Fabric Matrix: 샤드별 바이트 범위, 레이어, SHA-256, 복제 노드 건강 상태 감시 및 샤드 복구 트리거.
  - Locality & Capability Aware Execution Planner: Single-node, Request Routing, Data Parallel, Pipeline/Tensor Parallel, Offload 모드 선택 및 VRAM/대역폭 타당성 평가.
  - 교차 노드 텐서 병렬 제약 안내(ADR-041): 1Gbps LAN 대기시간 병목 시 명시적 경고 및 파이프라인/단일 노드 배치 권장.

### 2.5 VF-GM-05: Terminal / IDE Session UX
- `TerminalSessionView.tsx`:
  - Windows 노드(Node-01/02/03) 접속 시 PowerShell, Linux 노드(Node-04/05) 접속 시 Bash/Zsh로 자동 정합.
  - 30초 암호학적 1회용 PTY 티켓 인증 및 mTLS 격리 보장.
  - 다중 노드 탭 동시 관리 및 PTY 터미널 <-> Monaco IDE 모드 전환 지원.

### 2.6 VF-GM-06: 외부 HTTPS, browser matrix, rollback
- `tools/run_browser_smoke.mjs` Track 15 신설:
  - 총 15개 트랙, **200/200 checks 100% 무오류 통과**.
  - 단일 Origin Nginx TLS 1.3 리버스 프록시 및 무중단 웹 롤백(rc.2 -> rc.1) 무결성 유지.

---

## 3. 검증 결과 증거 (Evidence)

| 검증 스위트 | 실행 명령 | Exit Code | 검증 결과 |
|---|---|---|---|
| **Vitest 단위/프로토콜 시험** | `npx vitest run` (apps/web) | 0 | **23 test files, 143 tests passed (100%)** |
| **Vite 프로덕션 빌드** | `npm run build` (apps/web) | 0 | 81 modules transformed, 0 errors, 0 warnings (11.73s) |
| **E2E 브라우저 스모크** | `node tools/run_browser_smoke.mjs` | 0 | 15 tracks, **200/200 checks passed (100%)** |
| **2-PC 분산 실행 검증** | `node tools/verify_two_pc_distributed_execution.mjs` | 0 | 5 steps, **67/67 checks passed (100%)** |
| **라우트 커버리지** | `tools/route_coverage.py --served src --served services/control-plane --client apps/web/src` | 0 | 80 distinct routes, 26 client paths, **0 unserved (100%)** |
| **문서 정합성 검사** | `.venv\Scripts\python.exe tools/check_docs.py` | 0 | 288 versioned documents PASS |
| **온톨로지 SHACL 검사** | `.venv\Scripts\python.exe tools/check_ontology.py` | 0 | 48 task mappings PASS |

---

## 4. 결론 및 Claude 독립 검토 인계

1. Gemini 소유 `VF-GM-01` ~ `VF-GM-06` 전 범위의 UI 구현 및 로컬 통합 검증 완료.
2. 독립 검토자 Claude(`CL-01` / `VF-CL-05`)에게 코드 및 실측 결과 정식 인계.
