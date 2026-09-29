---
doc_id: "GEMINI-S07-FE-SCENARIO-MATRIX-20260928"
title: "S07-FE 분산 복구·Node 이탈·Heartbeat 60s Stale 전이·Fencing Token·Zombie Late Write 차단 UX 시나리오 매트릭스 (Gemini)"
version: "1.0.3"
status: "review"
author: "Gemini"
reviewer: "Codex, Claude"
updated: "2026-09-28T06:15:00+09:00"
source_of_truth: "Git"
tags: ["s07-fe", "acceptance-matrix", "distributed-recovery", "fencing-token", "zombie-rejection", "split-brain", "heartbeat", "gemini"]
---

# S07-FE 분산 복구·Node 이탈·Heartbeat 60s Stale 전이·Fencing Token·Zombie Late Write 차단 UX 시나리오 매트릭스 (Gemini)

> **관련 계약 및 선행 문서**:
> - [[전체 개발 진행 현황]]
> - [[Gemini 작업 현황]]
> - [[S07 분산 복구]] (OUT-07 / AC-07)
> - [[Frontend 최종 개발 계획]]
> - [[설계 충돌 정정 및 ADR]] (ADR-006, ADR-043, ADR-100)
> - `apps/web/src/features/recovery/DistributedRecoveryView.tsx`
> - `apps/web/src/features/recovery/recoveryEngine.ts`
> - `apps/web/tests/distributed-recovery.test.ts`
> - `apps/web/tests/defect-recovery-admin-recovery-editor.test.tsx`
> - `tools/measure_s07_recovery.py`
> - `tests/core/test_s07_recovery_measurement.py`
> - `tests/integration/test_shard_recovery.py` (lines 371-383)
> - `services/control-plane/src/inv/workspace_recovery.py`
> - `services/control-plane/src/inv/observation.py` (lines 138-150)
> - `services/control-plane/src/inv/dispatch.py` (lines 79-85)
> - `services/control-plane/src/inv/leases.py` (lines 253-263)

---

## 1. 개요 및 수용 목표 (OUT-07 / AC-07)

본 문서는 SaintVision 분산 클러스터 탄력성 및 제어 평면의 **S07-FE (분산 복구·Node 이탈·Heartbeat 60s Stale 전이·단조 Fencing Token·Zombie Late Write 차단 UX)** 트랙을 완결하기 위해, 코디네이터 지시 및 Codex 계약 검토(F-C1, F-C2, F-C3)와 **Claude UI 경로 독립 검토(issuecomment-5859655979 8대 수정 요청 및 관찰사항 전수)**를 반영하여 수립한 **시나리오 매트릭스 정본 개정안(v1.0.3)**이다.

본 문서는 `DistributedRecoveryView` 및 `recoveryEngine` 화면/엔진의 사용자 여정별 기대를 **실제 프런트엔드 컴포넌트 셀렉터(`data-testid`, `button:has-text`, `role`, 배너 텍스트)**와 1:1로 엄격히 대응시키며, 클라이언트 인메모리 시뮬레이션 결과와 백엔드 DB 커널 계약의 경계를 철저히 분리한다.

### 1.1 핵심 합격 기준 (AC-07) 및 클라이언트 시뮬레이션 vs 커널 계약 경계 분리

1. **Heartbeat 지연 감지 시간 및 노드 상태 경계 (F-C1 및 Claude r1 반영)**:
   - **클라이언트 인메모리 시뮬레이션 계약 (UI Simulation Contract)**:
     - `recoveryEngine.ts`의 `ResilientNodeState`는 하트비트 경과 시간에 따라 60초 초과 시 `stale`, 120초 초과 시 `offline`, 네트워크 분할 시 `fenced` 상태로 전이한다.
     - `DistributedRecoveryView:71-78`의 버튼(`⏱️ Simulate Heartbeat Delay (75s > 60s Stale Threshold)`)을 통해 75초 지연 인입 시 UI 카드 배지(`STALE`) 및 알림 배너 전이를 검증한다. (참고: 120초 초과 `offline` 전이는 UI 버튼/트리거 경로가 없으며 엔진 단위 시험 `distributed-recovery.test.ts:31-32`에서만 실행됨).
     - 상단 KPI 배너의 `≤ 60 초 (실측 통과)`는 **정적 JSX 리터럴(측정값이나 동적 계산값이 아닌 고정 문자열)**이며, 실제 커널 AC-07 감지 한계는 timeout + poll (설정 의존: measure_s07_recovery 도구 기본 60.1s, 단위시험 fixture 60.5s)로 숫자도 차이가 있다. 제품 문구의 동적 실측 연동은 향후 FE 개선 과제로 분리하며, 실제 물리/PG 클러스터 감지 지연은 **`UNMEASURED`**이다.
     - **실제 Node에 합성 상태를 덧씌우는 구조 고지**: `DistributedRecoveryView:13-17`은 실제 백엔드에서 전달된 Node 목록(`App.tsx:264-267` `/v1/nodes` 등)의 `id`, `hostname`만 취하고, 실제 백엔드 헬스(`NodeItem.status`, `heartbeatAt`)를 무시한 채 모두 `healthState: 'online'`, `heartbeatAgeSeconds: 2`로 강제 초기화(`recoveryEngine.ts:49-51`)한다. 따라서 백엔드 상에서 실제 offline인 노드도 UI상에서는 초록 ONLINE으로 렌더된다.
   - **백엔드 DB 커널 정본 계약 (Kernel Authority Boundary)**:
     - DB 정본 `inv.nodes.status` enum 규격(`0001_core.sql:17`)은 `'online' | 'offline' | 'draining' | 'quarantined'` 4종만을 허용하며, `stale`이나 `fenced`는 DB 상태가 아닌 프런트엔드 전용 합성 상태이다.
     - 백엔드 관측기(`services/control-plane/src/inv/observation.py:138-150`)는 60초 초과(`heartbeat_at < clock_timestamp() - interval '60 seconds'`) 미수신 시 `online` 노드를 곧바로 `offline`으로 일괄 갱신한다.
     - 백엔드 작업 디스패치 및 리스 점유(`dispatch.py:79-85`, `leases.py:253-256`)는 별도로 **15초 신선도(`heartbeat_at >= clock_timestamp() - interval '15 seconds'`)**를 엄격히 요구하며, 신선도 미달 시 `ready=False` 또는 `RES-0006` 에러를 반환한다.
2. **단조 Fencing Token 및 Split-Brain 분할 격리 (ADR-006 & ERR-DESIGN-006)**:
   - **클라이언트 정수 단조 Fencing 추상화 (`isTokenNewer`, `isTokenValidAndCurrent`)**:
     - 상위 `epoch`은 하위 `epoch`의 모든 시퀀스를 무조건 무효화한다 (`epoch: 2, seq: 1` > `epoch: 1, seq: 9999`).
     - 동일 `epoch` 내에서는 상위 `sequence`가 우선한다.
     - 활성 쓰기는 현재 발급된 유효 임차 토큰과 정확히 일치(`attempted === current`)해야 하며, 과거 토큰(stale)과 미발행 미래 토큰(future)은 모두 엄격히 거절된다.
     - 네트워크 분할 모의(`DistributedRecoveryView:81-88`, `⚡ Simulate Network Partition & Split-Brain Fencing`) 시 노드를 `fenced` 상태로 격리하고 클러스터 `epoch`을 전진(+1)시키며 `sequence`를 1로 재설정한다. (새로 마운트 후 첫 노드 대상 1회 실행 전제; 반복 클릭 시 epoch 누적).
3. **오래된 토큰(Zombie) 쓰기 거절 및 물리 영속 격리 (F-C2 및 Claude r1 반영)**:
   - **UI 인메모리 합성 거절 시나리오 (50/50 Rejections)**:
     - 분할된 좀비 워커가 과거 토큰으로 쓰기를 시도(`attemptWrite`)할 때 `STALE_FENCING_TOKEN` 에러로 즉각 거절된다.
     - `DistributedRecoveryView:93-96`의 과거 토큰 계산식은 `epoch: Math.max(1, curToken.epoch - 1)`, `sequence: Math.max(1, curToken.sequence - 5)`이다. FNC-01(네트워크 분할) 직후 `current = (2, 1)`인 경우 clamp 수식에 의해 과거 시도 토큰은 **`attempted = (1, 1)`**이 되며, 거절 사유는 `STALE_FENCING_TOKEN: attempted (1, 1) < current (2, 1)`이 된다.
     - `distributed-recovery.test.ts:76`의 50회 시험은 **동시(concurrent)가 아닌 순차(sequential for-loop)** 루프로 수행된다.
     - `staleTokenWritesAllowed`는 `recoveryEngine.ts:41`에서 0으로 초기화된 후 증가 경로가 없는 인메모리 카운터이며, 시험은 거절된 호출만 반복한다. 상단 KPI 배너 `0 건 (완전 차단)`은 UI 컴포넌트 프레젠테이션 정합성을 나타낸다.
   - **운영 AC-07 물리 불변식**: 클러스터 전체에 걸친 실제 영속 쓰기 완전 차단(Zero stale persisted writes across cluster)은 **`UNMEASURED ('실 5노드 분산 랩 배선 후')`**로 엄격히 유지한다.
4. **노드 대피(Drain) 및 Reconciliation 복구 (F-C2 및 Claude r1 반영)**:
   - **UI 인메모리 모의 복구 시나리오 (20/20 Recovery)**:
     - 장애 노드 복구(`reconcileNode`) 시 활성 작업을 대피(`activeWorkspacesCount = 0`)시키고, 신규 Epoch을 발급(+1)한 뒤 노드 헬스를 `recovering` ➔ `online`으로 복원한다. 엔진 내부에서 동기 전이(`recoveryEngine.ts:180` ➔ `:190`)되므로 UI에는 `recovering` 배지가 노출되지 않고 곧바로 `ONLINE`으로 렌더된다.
     - `reconcileNode()`는 인메모리 결정론적 로직으로 항상 `{ recoverySuccess: true }`를 반환하므로 20/20은 UI 시뮬레이션 결과이다.
     - 상단 KPI 배너 `100% (목표: ≥95%)`는 **정적 JSX 리터럴(복구 0건 빈 상태에서도 마운트 즉시 100% 고정 렌더)**이다. 제품 문구의 동적 연동은 FE 개선 과제로 분리한다.
     - `distributed-recovery.test.ts:96`의 20회 반복 복구 시험은 5개 fixture 노드를 `i % 5`로 순차 4회씩 실행한 것이며, **ADR-100:51의 물리 AC-07 벤치마크 규격(Ubuntu 4대 × 5회, CP 겸임 노드 분모 제외 및 합산 금지)**과 형태가 다르다.
   - **운영 AC-07 물리 복구율**: 물리 바이트 전송, 실행 샤드 재생, 프로세스 페일오버를 포함한 운영 복구율(≥95% physical recovery)은 **`UNMEASURED ('실 5노드 분산 랩 배선 후')`**로 엄격히 유지한다.
5. **ADR-043 Writable Generations & Workspace Checkouts 모의 고지**:
   - 백엔드 파일시스템 및 제어 평면 미노출 엔드포인트(`/v1/recovery/*`)에 대해 `recovery-unexposed-notice`(`role="status"`)를 상단에 영구 렌더링한다.
   - 새 작업 사본 체크아웃 생성 시 실제 파일시스템에 기록된 양 속이지 않고 `ℹ️ [모의 시뮬레이션] ADR-043 Writable Generation 생성 ... — 백엔드 파일시스템에는 기록되지 않습니다.`로 정직하게 고지한다 (`defect-recovery-admin-recovery-editor.test.tsx:162-179`).
6. **5노드 물리 환경 및 커널 측정 경계 (ADR-100 UNMEASURED)**:
   - ADR-100 토폴로지 B에 따라 Control Plane 겸임 Node 1대와 독립 Ubuntu Node 4대의 경계를 분리 기록한다 (`registeredNodeCount=5`, `cpIndependentWorkerHostCount=4`, `cpColocatedNodeCount=1`).
   - 실제 멀티 물리 머신 환경의 네트워크 단절 및 하드웨어 페일오버는 **UNMEASURED ('실 5노드 분산 랩 배선 후')**로 정직하게 격리 표기한다.

---

## 2. 5대 핵심 영역 매트릭스 구성 체계

| 영역 코드 | 핵심 테마 | 대상 컴포넌트 / 모듈 | 핵심 방어 기제 및 백엔드 계약 규격 |
|:---:|---|---|---|
| **HBD** | **Heartbeat 지연 감지 및 노드 헬스 수명주기**<br>(Heartbeat & Node Lifecycle) | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | • **UI 시뮬레이션 계약**: `age <= 60s` ➔ `online`, `age > 60s` ➔ `stale`, `age > 120s` ➔ `offline` (단, `offline`은 DOM 트리거 없음, 엔진 전용)<br>• **백엔드 커널 정본**: `inv.nodes.status`는 4종(`online\|offline\|draining\|quarantined`)만 허용. `>60s` 시 즉시 `offline` 전이(`observation.py:138-150`). 실행 경로는 별도 `15s freshness` 요구(`dispatch.py:79-85`, `leases.py:253-256`)<br>• 상단 KPI 배너 `≤ 60 초 (실측 통과)`는 정적 JSX 리터럴(고정 문자열)로 표기 |
| **FNC** | **단조 Fencing Token 및 Split-Brain 분할**<br>(Monotonic Fencing & Partition) | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | • ADR-006 & ERR-DESIGN-006: `(epoch, sequence)` 사전식 단조성 보증 (클라이언트 펜싱 추상화)<br>• 상위 Epoch 전진 우선 정책 (과거 Epoch 무조건 무효화)<br>• 네트워크 분할 시뮬레이션 시 노드 `fenced` 격리 및 `epoch += 1`, `sequence = 1` 재설정<br>• 현재 활성 토큰 외 미래/과거 토큰 일체 거절 (`isTokenValidAndCurrent`) |
| **ZMB** | **Zombie Late Write 차단 및 Stale 쓰기 0건**<br>(Zombie Write Rejection & Zero Leak) | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | • 과거 토큰(`Math.max(1, epoch-1)`, `Math.max(1, seq-5)`) 쓰기 시 `STALE_FENCING_TOKEN` 에러 반환<br>• FNC-01 직후 분할 노드 쓰기 시도 토큰은 clamp에 의해 `(1, 1)`로 계산됨<br>• UI 인메모리 합성 거절 50회 순차 for 루프 검증 (`staleTokenWritesAllowed === 0`)<br>• 에러 알림 배너 `🛡️ AC-07 Zombie Write Blocked: ...`<br>• `Late Result Rejections` 감사 목록에 거부 이력 즉각 렌더링<br>• 운영 AC-07 zero stale persisted writes는 **UNMEASURED** 유지 |
| **REC** | **노드 Drain 및 Reconciliation 복구**<br>(Drain & Reconciliation Consensus) | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | • `reconcileNode`: 태스크 대피(`evacuatedWorkspacesCount`), Epoch 전진, `online` 복구 (동기 전이로 화면 `recovering` 미노출)<br>• UI 인메모리 모의 복구 시뮬레이션 20회 순차 성공 (20/20; ADR-100 물리 5노드 벤치마크와 형태 상이)<br>• 상단 KPI 배너 `100% (목표: ≥95%)`는 정적 JSX 리터럴<br>• `Cluster Reconciliation Audit Trail` 이력 테이블에 RECOVERED 기록<br>• 물리 AC-07 ≥95% 복구율(바이트 전송/샤드 재생)은 **UNMEASURED** 유지 |
| **CHK** | **ADR-043 작업 세대 및 미노출 API 고지**<br>(Working Generations & Notice) | `DistributedRecoveryView.tsx`<br>`defect-recovery-admin-recovery-editor.test.tsx` | • 상단 `recovery-unexposed-notice`(`role="status"`)로 백엔드 API 부재 정직 고지<br>• `create-checkout-btn` 클릭 시 `sim_chk_*` 모의 세대 생성 고지 표출<br>• 빈 상태 고지 `recovery-no-checkouts`<br>• Case B(대상 노드 부재)는 UI에서 도달 불가한 방어 코드(알 수 없는 id는 resilientNodes[0] 대체, nodes=[] 시 line 309 렌더 예외 발생 버그 존재) |

---

## 3. 세부 시나리오 매트릭스 (15대 시나리오)

### 3.1 Heartbeat 지연 감지 및 노드 헬스 수명주기 (HBD-01 ~ HBD-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **HBD-01** | **정상 Heartbeat 수신 및 Healthy 노드 렌더링** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | 초기 클러스터 노드 마운트 완료 (엔진 fixture는 5대, DOM 테스트는 1대 `node-win-01` 마운트) | 화면 마운트 완료 시점 | • KPI 배너: `div:has-text("AC-07 이탈 감지 시간")`<br>• KPI 값: `div:has-text("≤ 60 초 (실측 통과)")` (정적 JSX 리터럴)<br>• 상태 배지: `span:has-text("ONLINE")`<br>• 경과 시간: `span:has-text("2s ago")` | • 초기 노드 `healthState === 'online'` 및 녹색 배지(`#3fb950`) 표출 확인.<br>• Heartbeat 경과 시간이 60초 이내(기본 2s)로 렌더링됨.<br>• 상단 KPI 배너에 `≤ 60 초 (실측 통과)` 고정 JSX 리터럴 표출 확인 (동적 측정값 아님; 물리 클러스터 감지 시간은 UNMEASURED).<br>• **(합성 상태 고지)** 백엔드 실제 노드 상태와 무관하게 UI 인메모리에서 무조건 online/2s로 초기화됨. (인용 시험은 엔진 단언 전용이며 DOM 셀렉터 단언은 아님). | `apps/web/tests/distributed-recovery.test.ts:22-26`<br>*(순수 엔진 단위시험)* |
| **HBD-02** | **Heartbeat 지연(75초 > 60초) 시뮬레이션 및 STALE 자동 전이** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | **비분할(Non-partitioned) Node**(`nod_01JABCDEF01`) 선택 상태 | 지연 버튼 클릭: `button:has-text("⏱️ Simulate Heartbeat Delay (75s > 60s Stale Threshold)")` | • 버튼: `Button variant="secondary"`<br>• 알림 배너: `actionNotice.type === 'info'` (border/color `#58a6ff`; 별도 role/testid 없음)<br>• 알림 문구: `Heartbeat age for Node-01-WinMain set to 75s (>60s). Health transitioned to STALE (AC-07 verified).` (정적 고정 문구)<br>• 상태 배지: `span:has-text("STALE")` (color: `#e3b341`)<br>• 경과 시간 텍스트: `span:has-text("75s ago")` (color: `#f85149`) | • `recoveryManager.simulateHeartbeatDelay(nodeId, 75)` 호출 완료.<br>• 클라이언트 엔진 상에서 노드 헬스가 즉시 `online`에서 `stale`로 전이됨을 실측.<br>• (경계 고지) `stale`은 UI 인메모리 시뮬레이션 상태이며, 백엔드 DB observer는 60s 초과 시 `offline`으로 직접 전이함(`observation.py:146`). 분할 노드는 엔진이 `fenced`를 유지하므로 비분할 노드에서만 배지가 STALE로 변경됨. (참고: `Node-01-WinMain`은 엔진 시험 fixture 값이며 실제 화면에서는 백엔드 API가 전달한 노드의 hostname이 동적 렌더링됨). | `apps/web/tests/distributed-recovery.test.ts:28-29`<br>*(순수 엔진 단위시험)* |
| **HBD-03** | **Heartbeat 120초 초과 시 OFFLINE 전이 (엔진 전용; DOM 경로 부재)** | `recoveryEngine.ts` | 특정 노드 선택 상태 | `evaluateNodeHealth(nodeId, 125)` 직접 호출 | • 엔진 상태: `healthState: 'offline'`<br>• 상태 배지: `span:has-text("OFFLINE")` (color: `#f85149`)<br>• **[DOM 경로 부재]**: UI 버튼(`view:72`)은 75초만 전달하므로 UI 화면상에서 >120s 지연을 인입하는 DOM 트리거 버튼은 없음 | • 120초 초과 지연 발생 시 클라이언트 엔진에서 `stale`에서 `offline`으로 전이됨을 엔진 시험으로만 단언.<br>• (경계 고지) 백엔드 스케줄러의 영구 제외 연동은 별도 커널 디스패치 계약(`dispatch.py:79-85`, `leases.py:253-256`) 영역이며 **스케줄러 연동은 UNMEASURED**로 분리함. | `apps/web/tests/distributed-recovery.test.ts:31-32`<br>*(순수 엔진 단위시험)* |

---

### 3.2 단조 Fencing Token 및 Split-Brain 분할 격리 (FNC-01 ~ FNC-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **FNC-01** | **네트워크 분할(Split-Brain) 시뮬레이션 및 FENCED 격리·Epoch 전진** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | **새로 마운트 후 첫 번째 노드 선택 상태** (초기 `Epoch 1 : Seq 10`; 1회 실행 전제) | 분할 버튼 클릭: `button:has-text("⚡ Simulate Network Partition & Split-Brain Fencing")` | • 버튼: `Button variant="secondary"` (style: `#a371f7`)<br>• 알림 배너: `actionNotice.type === 'error'` (border/color `#f85149`)<br>• 알림 문구: `Network partition simulated for Node-01-WinMain. Node isolated & FENCED; Epoch advanced to 2.`<br>• 상태 배지: `span:has-text("FENCED")` (color: `#a371f7`)<br>• 토큰 텍스트: `code:has-text("Epoch 2 : Seq 1")` | • `recoveryManager.simulateNetworkPartition(nodeId)` 호출 완료.<br>• `isPartitioned === true`, `healthState === 'fenced'` 전이.<br>• 이전 Epoch(1)의 모든 토큰을 무효화하기 위해 노드 Fencing Lease의 `epoch`이 +1(2)로 전진하고 `sequence`가 1로 재설정됨 (클라이언트 ADR-006 추상화). (참고: 버튼을 반복 클릭하면 epoch이 계속 누적됨). | `apps/web/tests/distributed-recovery.test.ts:69-72`<br>*(순수 엔진 단위시험)* |
| **FNC-02** | **상위 Epoch 우선순위 사전식 순서 단조성 단언 (ADR-006)** | `recoveryEngine.ts` | 두 개의 Fencing Token 비교 (`isTokenNewer`) | 함수 호출: `isTokenNewer({ epoch: 2, sequence: 1 }, { epoch: 1, sequence: 9999 })` | • 순수 로직 검증: ADR-006 & ERR-DESIGN-006 단조 펜싱 토큰 불변식 | • 시퀀스 크기와 상관없이 상위 Epoch(2)가 이전 Epoch(1)의 거대 시퀀스(9999)를 무조건 압도(`true`).<br>• 역방향 비교 시 엄격하게 `false` 반환. | `apps/web/tests/distributed-recovery.test.ts:37-41`<br>*(순수 로직 단위시험)* |
| **FNC-03** | **동일 Epoch 내 시퀀스 단조성 및 미발행/과거 토큰 거절 (ERR-DESIGN-006)** | `recoveryEngine.ts` | 현재 활성 토큰 `{ epoch: 1, sequence: 100 }` | 토큰 유효성 검증 (`isTokenValidAndCurrent`) | • 함수 호출: `isTokenValidAndCurrent(attempted, current)` | • 정확한 일치(`epoch: 1, seq: 100`)만 `true` 허용.<br>• 미발행 미래 토큰(`epoch: 99` 또는 `seq: 999`) 전면 거부 (`false`).<br>• 과거 만료 토큰(`epoch: 0` 또는 `seq: 99`) 전면 거부 (`false`). | `apps/web/tests/distributed-recovery.test.ts:43-57`<br>*(순수 로직 단위시험)* |

---

### 3.3 Zombie Late Write 차단 및 Stale 쓰기 0건 보증 (ZMB-01 ~ ZMB-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **ZMB-01** | **고립 Zombie 워커의 오래된 토큰 쓰기 시도 차단 (STALE_FENCING_TOKEN)** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | FNC-01 실행 직후 첫 Node 선택 상태 (`current: Epoch 2 : Seq 1`) | 좀비 쓰기 버튼 클릭: `button:has-text("🚫 Attempt Stale Token Write (Simulate Zombie Worker)")` | • 버튼: `Button variant="secondary"` (style: `#f85149`)<br>• 알림 배너: `actionNotice.type === 'error'`<br>• 알림 문구: `🛡️ AC-07 Zombie Write Blocked: STALE_FENCING_TOKEN: attempted (1, 1) < current (2, 1). Stale writes allowed: 0 (ZERO LEAK).`<br>• 엔진 반환: `{ success: false, error: 'STALE_FENCING_TOKEN: attempted (1, 1) < current (2, 1)' }` | • 과거 토큰 계산식(`Math.max(1, 2-1)=1`, `Math.max(1, 1-5)=1`)에 의해 시도 토큰은 **`(1, 1)`**이 됨.<br>• `isTokenValidAndCurrent` 불일치로 쓰기 즉시 거부.<br>• 거부 사유에 `STALE_FENCING_TOKEN: attempted (1, 1) < current (2, 1)` 명시.<br>• (주의: 단위시험 :75는 `currentSeq + 10`을 사용하여 view 수식과 다른 시퀀스를 검증함). | `apps/web/tests/distributed-recovery.test.ts:77-80`<br>*(순수 엔진 단위시험)* |
| **ZMB-02** | **UI 합성 거절 50회 순차 루프 차단 및 0건 불변식 (F-C2 및 Claude r1 반영)** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | 순차 50회(sequential for-loop) 좀비 워커의 지연 쓰기 시도 주입 (`distributed-recovery.test.ts:76`) | 반복 호출 루프 완료 시점 | • KPI 배너: `div:has-text("오래된 토큰(Zombie) 쓰기 수")`<br>• KPI 값: `div:has-text("0 건 (완전 차단)")`<br>• 엔진 카운터: `mgr.getStaleWritesAllowed()` | • 50회 순차 지연 쓰기 시도 중 단 1건도 쓰기가 인가되지 않음 (`staleTokenWritesAllowed === 0`).<br>• 상단 KPI 배너에 `0 건 (완전 차단)` 유지.<br>• (경계 고지) 이는 UI 인메모리 합성 거절 검증이며, 운영 클러스터 전체의 물리 영속 쓰기 완전 차단(Zero stale persisted writes)은 **UNMEASURED**임. | `apps/web/tests/distributed-recovery.test.ts:81-85`<br>*(순수 엔진 단위시험)* |
| **ZMB-03** | **실시간 Late Result Rejections 감사 목록 렌더링** | `DistributedRecoveryView.tsx` | FNC-01 ➔ ZMB-01 거절 1건 발생 상태 | 거절 수신 후 컴포넌트 재렌더링 | • 헤더: `h4:has-text("Late Result Rejections (AC-07 Zero Stale Writes)")`<br>• 카운트: `span:has-text("Total Rejections: 1")`<br>• 거부 카드: `div:has-text("BLOCKED: req_")`<br>• 상세 내용: `code:has-text("Epoch 1 : Seq 1")` vs `code:has-text("Epoch 2 : Seq 1")`<br>• 에러 사유: `div:has-text("STALE_FENCING_TOKEN: attempted (1, 1) < current (2, 1)")` | • `lateResultRejections` 배열에 거절 레코드가 unshift로 즉시 추가됨.<br>• 각 거절 항목에 고유 요청 ID(`req_*`), 거부 시각, 시도 토큰(`Epoch 1 : Seq 1`) 대 현재 토큰(`Epoch 2 : Seq 1`) 비교가 상세 렌더링됨.<br>• 거절 목록 0건일 때 `No late result rejections yet...` 안내 표출.<br>• (인용 시험 :84는 엔진 배열 길이 단언이며 DOM 셀렉터 단언은 아님). | `apps/web/tests/distributed-recovery.test.ts:84`<br>*(순수 엔진 단위시험)* |

---

### 3.4 노드 Drain 및 Reconciliation 복구 Consensus (REC-01 ~ REC-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **REC-01** | **노드 태스크 대피(Drain) 및 Epoch 전진 복구 재개** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | FNC-01 실행된 첫 노드 (`activeWorkspacesCount > 0`, `isPartitioned === true`) | 복구 버튼 클릭: `button:has-text("🛡️ Drain & Reconcile Node (Restore & Advance Epoch)")` | • 버튼: `Button variant="primary"`<br>• 알림 배너: `actionNotice.type === 'success'` (border/color `#3fb950`)<br>• 알림 문구: `✔ Node Node-01-WinMain reconciled! Evacuated 1 tasks. Advanced to Epoch 3. Status restored to ONLINE.`<br>• 상태 배지: `span:has-text("ONLINE")`<br>• 활성 태스크: `span:has-text("0")` (단, 경과시간 0s ago와 혼동 주의) | • `recoveryManager.reconcileNode(nodeId)` 실행 완료.<br>• 활성 작업 대피(`evacuatedWorkspacesCount`) 후 `activeWorkspacesCount = 0` 초기화.<br>• 네트워크 분할 해제(`isPartitioned = false`) 및 Epoch 전진(+1) 발급.<br>• 엔진 내부에서 `recovering` ➔ `online` 동기 전이되므로 화면에는 recovering이 노출되지 않고 곧바로 ONLINE으로 복구됨.<br>• **[주의]** 인용 시험 `:101-106`은 `record.recoverySuccess && healthState==='online'`만 확인하며, 대피·분할해제·Epoch 전진에 대한 expect 단언이 0개임 (단언 보강 필요). | `apps/web/tests/distributed-recovery.test.ts:101-106`<br>*(단언 미흡 / 보강 필요)* |
| **REC-02** | **UI 인메모리 복구 시뮬레이션 20회 반복 성공 (F-C2 및 Claude r1 반영)** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | 5개 fixture 노드 대상 20회 순차 분할 및 Reconcile 루프 (`i % 5`) | 테스트 스위트 또는 모의 하네스 완료 시점 | • KPI 배너: `div:has-text("분산 복구 성공률 목표")`<br>• KPI 값: `div:has-text("100% (목표: ≥95%)")` (정적 JSX 리터럴)<br>• 부제: `div:has-text("Drain 및 Epoch 전진 Consensus")` | • 20회 반복 복구 시뮬레이션에서 20회 전수 복구 성공 (`successfulReconciliations === 20`).<br>• 상단 KPI 배너에 `100% (목표: ≥95%)` 정적 JSX 리터럴 표출 확인.<br>• **[거버넌스 고지]**: 이 20회 시험은 fixture 노드 대상 4회씩 순차 실행한 것이며, **ADR-100:51의 물리 5노드 벤치마크 규격(Ubuntu 4대 × 5회, 겸임 노드 분모 제외 및 합산 금지)**과 형태가 다름.<br>• 물리 바이트 전송 및 실행 샤드 재생을 수반하는 운영 AC-07 복구율(≥95%)은 **UNMEASURED**임. | `apps/web/tests/distributed-recovery.test.ts:89-113`<br>*(순수 엔진 단위시험)* |
| **REC-03** | **Cluster Reconciliation 이력 감사 원장 표출** | `DistributedRecoveryView.tsx` | 복구 1회 이상 완료 상태 | 이력 렌더링 시점 | • 헤더: `h4:has-text("Cluster Reconciliation Audit Trail (AC-07 Recovery KPI)")`<br>• 테이블 헤더: `th:has-text("Reconciliation ID")`, `th:has-text("Node ID")`, `th:has-text("Evacuated Tasks")`, `th:has-text("New Epoch")`, `th:has-text("Status")`, `th:has-text("Timestamp")`<br>• 상태 셀: `td:has-text("RECOVERED")` (color: `#3fb950`) | • `reconciliationHistory` 배열의 감사 레코드가 테이블 행으로 즉시 표출됨.<br>• `rec_*` 식별자, 대피된 태스크 수, 신규 Epoch 번호 및 `RECOVERED` 성공 상태 확인.<br>• 이력 0건일 때 `No recovery reconciliations recorded yet...` 안내 표출. | `apps/web/src/features/recovery/DistributedRecoveryView.tsx:401-432`<br>*(컴포넌트 렌더링 검증)* |

---

### 3.5 ADR-043 작업 세대 및 미노출 API 고지 (CHK-01 ~ CHK-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **CHK-01** | **분산 장애 복구 및 펜싱 시뮬레이션 제어기 (API 미노출) 정직 고지 배너** | `DistributedRecoveryView.tsx` | 분산 복구 화면 진입 시점 | 화면 마운트 | • 배너 셀렉터: `div[role="status"][aria-live="polite"][data-testid="recovery-unexposed-notice"]`<br>• 고지 문구: `ℹ️ 분산 장애 복구 및 펜싱 시뮬레이션 제어기 (API 미노출): 현재 SaintVision 백엔드에는 분산 펜싱 토큰 갱신 및 파일시스템 체크아웃 생성 엔드포인트(/v1/recovery/*)가 배선되어 있지 않습니다. 아래의 노드 격리, Fencing Epoch 전이 및 체크아웃 목록은 장애 복구 프로토콜(ADR-043)을 검증하기 위한 클라이언트 인메모리 시뮬레이션입니다.` | • 상단에 `role="status"` 및 `aria-live="polite"` 속성을 가진 파란색 안내 배너 영구 렌더링.<br>• 백엔드 제어 평면에 `/v1/recovery/*` 실 API가 미배선 상태임을 정직하게 사용자에게 고지.<br>• 브라우저 및 사용자 착오 방지. (실제 DOM 셀렉터 검증 시험). | `apps/web/tests/defect-recovery-admin-recovery-editor.test.tsx:150-160`<br>*(실제 DOM 테스트)* |
| **CHK-02** | **ADR-043 Working Generation 수정 가능 작업 사본 체크아웃 생성 및 모의 고지** | `DistributedRecoveryView.tsx` | 유효한 노드 선택 상태 | 체크아웃 버튼 클릭: `button[data-testid="create-checkout-btn"]` | • 버튼: `button[data-testid="create-checkout-btn"]`<br>• 알림 배너: `actionNotice.type === 'info'`<br>• 알림 문구: `ℹ️ [모의 시뮬레이션] ADR-043 Writable Generation 생성: sim_chk_1 (모의 inode: sim_ino_49152, 권한: 0600, Epoch: 1) — 백엔드 파일시스템에는 기록되지 않습니다.`<br>• 테이블 행: `td:has-text("sim_chk_1")`, `span:has-text("0600 (read/write)")`, `td:has-text("✓ ACTIVE (WRITABLE)")` | • 모의 Writable Generation 체크아웃 행이 테이블에 추가됨.<br>• 과거 허위 완료 배너(`✓ ADR-043 Writable Generation 생성 완료`)를 완전 배제하고, `백엔드 파일시스템에는 기록되지 않습니다`는 모의 시뮬레이션임을 정직하게 명시.<br>• POSIX 권한 `0600 (read/write)` 및 격리 사본(0400 readonly)과의 분리 표기. (실제 DOM 셀렉터 검증 시험). | `apps/web/tests/defect-recovery-admin-recovery-editor.test.tsx:162-179`<br>*(실제 DOM 테스트)* |
| **CHK-03** | **체크아웃 부재 빈 상태 고지 및 대상 부재 방어 코드 (UI 도달 불가 분석)** | `DistributedRecoveryView.tsx` | Case A: 체크아웃 목록 0건<br>Case B: `selectedNode === undefined` | Case A: 화면 초기 마운트<br>Case B: 체크아웃 생성 시도 | • Case A 빈 상태: `div[data-testid="recovery-no-checkouts"]`<br>• Case A 문구: `활성화된 수정 가능 세대(Working Generation) 체크아웃이 없습니다.`<br>• Case B 에러: `actionNotice.type === 'error'`<br>• Case B 문구: `❌ 체크아웃 생성 실패: 선택된 유효 대상 노드가 없습니다. (위조 노드 합성 방지)` | • Case A: 활성 체크아웃이 없을 때 `recovery-no-checkouts` 안내 박스 정상 마운트.<br>• **[Case B 도달 불가 분석]**: `view:37`에서 `selectedNodeId`가 없거나 알 수 없으면 `|| resilientNodes[0]`으로 대체되어 첫 노드로 생성됨. 노드가 없으면 버튼이 disabled됨(`view:458`). 만약 `nodes=[]`이면 line 309 `selectedNode.hostname`에서 **렌더 예외(Crash)**가 먼저 발생하므로 `view:43` 에러 문구는 정상 UI 경로에서 도달할 수 없는 방어 코드임 (위조 노드 식별자 차단 미동작; FE 결함 과제로 분리). | `apps/web/src/features/recovery/DistributedRecoveryView.tsx:37-46, 458-479`<br>*(코드 정독 대조)* |

---

## 4. 돌연변이(Mutation) 사살 계획 및 불변식 단언 (MUT 5종) (F-C3 및 Claude r1 반영)

본 매트릭스의 검증력과 견고성을 보장하기 위해, 프로덕션 코드 심볼을 의도적으로 변조했을 때 테스트 스위트가 이를 즉각 검출(KILLED)할 수 있는지 확인하는 5대 돌연변이 사살 계획을 수립한다. 실제 실행 증거(provenance)가 확보되기 전까지 상태는 **`PLANNED / NOT_RUN`**으로 정직하게 기록하며, 단언이 부재한 변이는 미측정으로 보존한다.

| 돌연변이 ID | 대상 파일 및 대상 로직 | 의도적 결함 주입 (Mutation) | 사살 검증 시험 및 단언 위치 (파일:행) | 판정 상태 (Claude r1 정정) |
|:---:|---|---|---|:---:|
| **MUT-01** | `recoveryEngine.ts:97`<br>`evaluateNodeHealth` | `if (currentAgeSeconds > 60)` ➔ `if (currentAgeSeconds > 100)` 으로 임계치 완화 | `apps/web/tests/distributed-recovery.test.ts:28-29`<br>`expect(mgr.evaluateNodeHealth(target, 61)).toBe('stale')` 단언 실패 유도 (코드 추론상 사살 예상) | **PLANNED / NOT_RUN** |
| **MUT-02** | `recoveryEngine.ts:32`<br>`isTokenNewer` | `if (candidate.epoch > baseline.epoch) return true;` 누락 (시퀀스만 비교) | `apps/web/tests/distributed-recovery.test.ts:37-41`<br>`expect(isTokenNewer({ epoch: 2, sequence: 1 }, { epoch: 1, sequence: 9999 })).toBe(true)` 단언 실패 유도 (코드 추론상 사살 예상) | **PLANNED / NOT_RUN** |
| **MUT-03** | `recoveryEngine.ts:144`<br>`attemptWrite` | `const isValid = isTokenValidAndCurrent(...)` 검증을 무시하고 무조건 `{ success: true }` 반환 | `apps/web/tests/distributed-recovery.test.ts:78-79, 84`<br>`expect(res.success).toBe(false)`, `expect(res.error).toContain('STALE_FENCING_TOKEN')`, `expect(mgr.getLateRejections()).toHaveLength(50)` 단언 실패 유도.<br>*(주의: :83 getStaleWritesAllowed()===0은 엔진에 증가 경로가 없어 변이 후에도 통과하므로 사살 단언이 아님)* | **PLANNED / NOT_RUN** |
| **MUT-04** | `recoveryEngine.ts:185`<br>`reconcileNode` | 노드 Reconcile 시 `node.fencingToken.epoch += 1`을 누락하여 Epoch 미전진 | `apps/web/tests/distributed-recovery.test.ts:89-113`<br>※ **(Codex F-C3 & Claude r1 공통 검증)** 현재 시험은 `record.newEpoch`를 단언하지 않고 `record.recoverySuccess && healthState==='online'`만 확인하므로 본 변이 주입 시 시험이 통과함. 따라서 **프로덕션 단언 보강 전까지 SURVIVED (미측정)** 상태임. | **SURVIVED (미측정)<br>[단언 보강 필요]** |
| **MUT-05** | `DistributedRecoveryView.tsx:133`<br>`Notice Banner` | `data-testid="recovery-unexposed-notice"` 배너를 제거하거나 고지 문구를 변조 | `apps/web/tests/defect-recovery-admin-recovery-editor.test.tsx:155-160`<br>`expect(notice).not.toBeNull()`, `expect(notice?.textContent).toContain('분산 장애 복구 및 펜싱 시뮬레이션 제어기 (API 미노출)')` 단언 실패 유도.<br>*(주의: defect:176의 '백엔드 파일시스템에는 기록되지 않습니다'는 체크아웃 알림 문구이므로 배너 사살 단언이 아님)* | **PLANNED / NOT_RUN** |

---

## 5. 백엔드 커널 계약 및 5노드 물리 환경 UNMEASURED 경계

### 5.1 백엔드 커널 분산 복구 계약 및 측정 도구 (F-C1, F-C3 반영)
- **PostgreSQL 노드 복구 에포크 (`inv.nodes.recovery_epoch`) 및 stale UUID 거절 경계**:
  - `tests/integration/test_shard_recovery.py:371-383` (`test_stale_epoch_and_cross_project_requests_do_not_create_recovery`):
    ```python
    stale = ShardRecovery(Database(a.e.runtime, recovery_epoch=str(uuid4())), a.recovery.targets)
    with pytest.raises(DomainError, match="LEASE-0004"):
        stale.prepare(...)
    ```
  - **정본 계약 불변식**: 백엔드 커널의 `recovery_epoch`(`0001_core.sql:19`)은 단조 증가 정수 카운터가 아니라 `UUID` 타입이다. 백엔드 샤드 복구에서 과거 에포크 거부 불변식은 **현재 유효 에포크와의 일치 검증 및 stale UUID 거절(`LEASE-0004`) 경계**로 작동한다. 정수 `(epoch, sequence)` 사전식 단조 순서는 ADR-006 클라이언트 펜싱 추상화이다.
- **백엔드 노드 헬스 및 신선도 계약**:
  - `0001_core.sql:17`: `inv.nodes.status` enum은 `'online' | 'offline' | 'draining' | 'quarantined'` 4종만 유효하며, `stale`/`fenced`는 DB 상태가 아님.
  - `services/control-plane/src/inv/observation.py:138-150`: 60초 초과 미수신 노드는 observer에 의해 즉시 `offline`으로 전환됨.
  - `services/control-plane/src/inv/dispatch.py:79-85` 및 `leases.py:253-263`: 실행/리스 점유 경로는 15초 신선도(`heartbeat_at >= clock_timestamp() - interval '15 seconds'`)를 강제하며 미달 시 `RES-0006` 에러 발생.
- **S07 노드 이탈·복구 측정 하네스 (`tools/measure_s07_recovery.py`)**:
  - `tests/core/test_s07_recovery_measurement.py:37-77`:
  - `operationalAcceptanceAssessed: false` (측정 하네스는 운영 수용을 자의적으로 단언하지 않음).
  - 커널 경계 발견 사항 (`findings`):
    - `F-S07-01` (kernel-boundary): 15초 커널 관측 윈도우는 60초 이탈 대기 중 독립 갱신되어야 하며, 이탈 시점 스냅샷 재사용 금지.
    - `F-S07-02` (acceptance-boundary): 레플리카 복구 코드는 계획 및 상태 마킹만 수행하며, 물리 바이트 전송이나 샤드 리플레이를 입증하지 않음.
    - `F-S07-03` (slo-boundary): 엄격한 `last_seen < now - timeout` 술어 유지. AC-07 감지 한계는 `timeout + 1 poll interval`로 정의됨.

### 5.2 ADR-100 5노드 랩 측정 경계 및 UNMEASURED 격리
- **ADR-100 토폴로지 B 수량 표기 불변식**:
  - `registeredNodeCount`: 5
  - `cpIndependentWorkerHostCount`: 4 (독립 Ubuntu 물리 호스트 4대)
  - `cpColocatedNodeCount`: 1 (Windows CP 호스트 겸임 Docker Linux VM Node 1대)
- **UNMEASURED 격리 항목**:
  - 실 5대 물리 머신 간의 네트워크 케이블 단절, 스위치 파티션 및 실제 호스트 전원 차단에 따른 복구 지연 실측은 **`UNMEASURED ('실 5노드 분산 랩 배선 후')`**로 엄격히 분류한다.
  - UI 엔진 시험의 20회 반복 복구(`distributed-recovery.test.ts:96`)는 ADR-100의 물리 5노드 벤치마크 규격(Ubuntu 4대 × 5회, 겸임 노드 분모 제외 및 합산 금지)과 형태가 다르며, 물리 복구율은 **`UNMEASURED`**이다.
  - 현재 브라우저·빌드·전체 suite 금지(메모리 경보 ~0.86GB) 하에 인메모리 및 단위 시험 검증 완료 상태를 유지한다.

---

## 6. Claude UI 독립 검토 관찰사항 및 FE 개선 과제 등록

Claude UI 경로 독립 검토(issuecomment-5859655979)에서 식별된 비차단 관찰사항을 투명하게 기록하고 향후 프런트엔드 개선 카드로 등록한다:

1. **FE-DEFECT-S07-01 (빈 노드 렌더 예외 방어)**:
   - `App.tsx:58` 초기 상태 또는 노드 fetch 실패(`nodes=[]`) 상태에서 `DistributedRecoveryView` 마운트 시 line 309 `selectedNode.hostname`에서 `TypeError: Cannot read properties of undefined` 렌더 크래시가 발생함.
   - 조치 계획: `selectedNode?.hostname ?? 'N/A'` 옵셔널 체이닝 및 빈 노드 가드 추가.
2. **FE-DEFECT-S07-02 (액션 알림 DOM 접근성 및 testid 결여)**:
   - 액션 알림 div(`DistributedRecoveryView.tsx:202-231`)에 `data-testid` 및 `role="alert"`(또는 `role="status"`)가 결여되어 있어 테스트가 React 상태(`actionNotice.type`)에 의존함.
   - 조치 계획: `data-testid="recovery-action-notice"`, `role="alert"` 속성 부여.
3. **FE-DEFECT-S07-03 (상단 KPI 정적 리터럴 동적 바인딩)**:
   - 상단 KPI 배너 2종(`≤ 60 초 (실측 통과)`, `100% (목표: ≥95%)`)이 고정 JSX 리터럴로 하드코딩되어 있어 초기 0건 상태에서도 100%로 표출됨.
   - 조치 계획: `reconciliationHistory`의 실제 성공률 및 관측 감지 시간과 동적 연동.
4. **FE-A11Y-S07-04 (Node 카드 키보드 접근성)**:
   - 노드 선택 카드가 단순 `div onClick`(`DistributedRecoveryView.tsx:250-252`)으로 구현되어 있어 `role="button"`, `tabIndex={0}`, 키보드 엔터/스페이스 이벤트가 부재함.
   - 조치 계획: 웹 접근성 WCAG 2.1 AA 준수를 위한 대화형 요소 속성 보강.
5. **FE-STATE-S07-05 (Node 목록 props 갱신 반영)**:
   - `useState(recoveryManager.getNodes())`(`view:11-21`)가 컴포넌트 마운트 시점에만 1회 초기화되어 부모(`App.tsx`)로부터 전달되는 `nodes` props의 동적 변경이 재렌더링에 반영되지 않음.
   - 조치 계획: `useEffect`를 통한 nodes props 동기화 처리.

---

## 7. 검토 인계 및 다음 단계

- **문서 상태**: `status: "review"` (S07-FE 시나리오 매트릭스 v1.0.3 - Codex 계약 검토 및 Claude UI 경로 독립 검토 8대 수정 요청 및 관찰사항 전수 반영 완결)
- **독립 리뷰어**: Codex (S07 정본 계약, 단조 Fencing Token, DB recovery_epoch, 커널 15s 윈도우 대조), Claude (UI 셀렉터, 거버넌스 불변식, 돌연변이 단언 대조)
- **다음 단계**:
  1. Claude UI 검토 반영 commit & push (`agent/gemini/s07-fe-matrix`).
  2. PR #116에 v1.0.2 조치 보고 코멘트 작성.
  3. S08-FE 시나리오 매트릭스 v1.0.0 작성 계속 진행.
