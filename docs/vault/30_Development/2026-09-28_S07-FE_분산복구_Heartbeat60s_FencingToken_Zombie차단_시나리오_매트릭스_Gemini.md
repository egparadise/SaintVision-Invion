---
doc_id: "GEMINI-S07-FE-SCENARIO-MATRIX-20260928"
title: "S07-FE 분산 복구·Node 이탈·Heartbeat 60s Stale 전이·Fencing Token·Zombie Late Write 차단 UX 시나리오 매트릭스 (Gemini)"
version: "1.0.0"
status: "review"
author: "Gemini"
reviewer: "Codex, Claude"
updated: "2026-09-28T00:20:00+09:00"
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
> - `tests/integration/test_shard_recovery.py`
> - `services/control-plane/src/inv/workspace_recovery.py`

---

## 1. 개요 및 수용 목표 (OUT-07 / AC-07)

본 문서는 SaintVision 분산 클러스터 탄력성 및 제어 평면의 **S07-FE (분산 복구·Node 이탈·Heartbeat 60s Stale 전이·단조 Fencing Token·Zombie Late Write 차단 UX)** 트랙을 완결하기 위해, 코디네이터 지시 및 Codex/Claude 리뷰 원칙을 전면 반영하여 수립한 **시나리오 매트릭스 정본(v1.0.0)**이다.

본 문서는 `DistributedRecoveryView` 및 `recoveryEngine` 화면/엔진의 사용자 여정별 기대를 **실제 프런트엔드 컴포넌트 셀렉터(`data-testid`, `button:has-text`, `role`, 배너 텍스트)** 및 **커널 계약 규격(Heartbeat 60s 타임아웃, 단조 Fencing Token, `STALE_FENCING_TOKEN`, DB `recovery_epoch`)**과 1:1로 엄격히 대응시키며, 존재하지 않는 셀렉터나 임의 합성 값의 기재를 전면 금지(Zero Fake Selectors / Zero Fake Values)한다.

### 1.1 핵심 합격 기준 (AC-07) 및 클라이언트 시뮬레이션 vs 커널 계약 경계 분리

1. **Heartbeat 지연 감지 시간 (AC-07 ≤ 60s)**:
   - **커널/엔진 불변식**: 노드의 Heartbeat 수신 경과 시간이 60초를 초과(예: 61초 또는 모의 75초)하면 즉시 `stale` 상태로 격리 전이된다 (`evaluateNodeHealth:87-106`). 120초 초과 시 `offline`으로 전이된다.
   - **클라이언트 시뮬레이션 제어**: `DistributedRecoveryView:71-78`의 버튼(`⏱️ Simulate Heartbeat Delay (75s > 60s Stale Threshold)`)을 통해 즉시 75초 지연을 인입하여 UI 카드 배지(`STALE`) 및 알림 배너 전이를 실시간 검증한다.
2. **단조 Fencing Token 및 Split-Brain 분할 격리 (ADR-006 & ERR-DESIGN-006)**:
   - **사전식 순서 비교기 (`isTokenNewer`, `isTokenValidAndCurrent`)**:
     - 상위 `epoch`은 하위 `epoch`의 모든 시퀀스를 무조건 무효화한다 (`epoch: 2, seq: 1` > `epoch: 1, seq: 9999`).
     - 동일 `epoch` 내에서는 상위 `sequence`가 우선한다.
     - 활성 쓰기는 현재 발급된 유효 임차 토큰과 정확히 일치(`attempted === current`)해야 하며, 과거 토큰(stale)과 미발급 미래 토큰(future)은 모두 엄격히 거절된다.
   - **네트워크 분할 모의**: `DistributedRecoveryView:81-88`의 버튼(`⚡ Simulate Network Partition & Split-Brain Fencing`)을 통해 노드를 `fenced` 상태로 격리하고 클러스터 `epoch`을 전진(+1)시켜 이전 토큰의 효력을 박탈한다.
3. **오래된 토큰(Zombie) 쓰기 완전 차단 (AC-07: 0 Stale Writes Allowed)**:
   - 분할 또는 축출된 좀비 워커가 과거 토큰(`epoch - 1`, `sequence - 5`)으로 쓰기를 시도(`attemptWrite`)할 때 `STALE_FENCING_TOKEN` 에러로 즉각 거절된다.
   - 상단 KPI 지표 및 감사 원장의 **오래된 토큰 쓰기 허용 수(`staleTokenWritesAllowed`)는 반드시 `0건`을 유지**한다 (`Zero Stale Writes / Zero Leak`).
4. **노드 대피(Drain) 및 Reconciliation Consensus (AC-07 ≥ 95% 복구율)**:
   - 장애 노드 복구(`reconcileNode`) 시 활성 워크스페이스 작업을 대피(`activeWorkspacesCount = 0`)시키고, 신규 Epoch을 발급(+1)한 뒤 노드 헬스를 `recovering` ➔ `online`으로 복원한다.
   - 20회 반복 복구 시뮬레이션에서 100% 성공률(목표 ≥ 95%)을 검증한다.
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
| **HBD** | **Heartbeat 지연 감지 및 노드 헬스 수명주기**<br>(Heartbeat & Node Lifecycle) | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | • `heartbeatAgeSeconds <= 60` ➔ `online`<br>• `heartbeatAgeSeconds > 60` (모의 75s) ➔ `stale` (AC-07 이탈 감지 ≤60s)<br>• `heartbeatAgeSeconds > 120` ➔ `offline`<br>• KPI 배너 `≤ 60 초 (실측 통과)` 표출 |
| **FNC** | **단조 Fencing Token 및 Split-Brain 분할**<br>(Monotonic Fencing & Partition) | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | • ADR-006 & ERR-DESIGN-006: `(epoch, sequence)` 사전식 단조성 보증<br>• 상위 Epoch 전진 우선 정책 (과거 Epoch 무조건 무효화)<br>• 네트워크 분할 시뮬레이션 시 노드 `fenced` 격리 및 `epoch += 1` 발급<br>• 현재 활성 토큰 외 미래/과거 토큰 일체 거절 (`isTokenValidAndCurrent`) |
| **ZMB** | **Zombie Late Write 차단 및 Stale 쓰기 0건**<br>(Zombie Write Rejection & Zero Leak) | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | • 과거 토큰 쓰기 시 `STALE_FENCING_TOKEN` 에러 반환<br>• `staleTokenWritesAllowed === 0` (Zero Stale Writes 불변식 엄수)<br>• 에러 알림 배너 `🛡️ AC-07 Zombie Write Blocked: ...`<br>• `Late Result Rejections` 감사 목록에 거부 이력 즉각 렌더링 |
| **REC** | **노드 Drain 및 Reconciliation 복구**<br>(Drain & Reconciliation Consensus) | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | • `reconcileNode`: 태스크 대피(`evacuatedWorkspacesCount`), Epoch 전진, `online` 복구<br>• 20회 반복 복구 시뮬레이션 100% 성공률 달성 (AC-07 목표 ≥ 95%)<br>• `Cluster Reconciliation Audit Trail` 이력 테이블에 RECOVERED 기록 |
| **CHK** | **ADR-043 작업 세대 및 미노출 API 고지**<br>(Working Generations & Notice) | `DistributedRecoveryView.tsx`<br>`defect-recovery-admin-recovery-editor.test.tsx` | • 상단 `recovery-unexposed-notice`(`role="status"`)로 백엔드 API 부재 정직 고지<br>• `create-checkout-btn` 클릭 시 `sim_chk_*` 모의 세대 생성 고지 표출<br>• 빈 상태 고지 `recovery-no-checkouts` 및 대상 노드 부재 시 생성 거절 가드 |

---

## 3. 세부 시나리오 매트릭스 (15대 시나리오)

### 3.1 Heartbeat 지연 감지 및 노드 헬스 수명주기 (HBD-01 ~ HBD-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **HBD-01** | **정상 Heartbeat 수신 및 Healthy 노드 렌더링** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | 초기 클러스터 노드 5대 정상 마운트 | 화면 마운트 완료 시점 | • KPI 배너: `div:has-text("AC-07 이탈 감지 시간")`<br>• KPI 값: `div:has-text("≤ 60 초 (실측 통과)")`<br>• 상태 배지: `span:has-text("ONLINE")`<br>• 경과 시간: `span:has-text("2s ago")` | • 초기 5대 노드 모두 `healthState === 'online'` 및 녹색 배지(`#3fb950`) 표출 확인.<br>• Heartbeat 경과 시간이 60초 이내(기본 2s)로 렌더링됨.<br>• 상단 KPI 배너에 `≤ 60 초 (실측 통과)` 및 `Heartbeat 60s 초과 시 자동 Stale 전이` 명시. | `apps/web/tests/distributed-recovery.test.ts:22-26` |
| **HBD-02** | **Heartbeat 지연(75초 > 60초) 시뮬레이션 및 STALE 자동 전이** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | 특정 노드(`nod_01JABCDEF01`) 선택 상태 | 지연 버튼 클릭: `button:has-text("⏱️ Simulate Heartbeat Delay (75s > 60s Stale Threshold)")` | • 버튼: `Button variant="secondary"`<br>• 알림 배너: `actionNotice.type === 'info'` (border/color `#58a6ff`)<br>• 알림 문구: `Heartbeat age for Node-01-WinMain set to 75s (>60s). Health transitioned to STALE (AC-07 verified).`<br>• 상태 배지: `span:has-text("STALE")` (color: `#e3b341`)<br>• 경과 시간 텍스트: `span:has-text("75s ago")` (color: `#f85149`) | • `recoveryManager.simulateHeartbeatDelay(nodeId, 75)` 호출 완료.<br>• 노드 헬스가 즉시 `online`에서 `stale`로 전이됨.<br>• AC-07 이탈 감지 임계치 60초 초과 시 자동 격리 불변식 만족 실측. | `apps/web/tests/distributed-recovery.test.ts:28-29` |
| **HBD-03** | **Heartbeat 120초 초과 시 OFFLINE 전이 및 고립 상태 명시** | `recoveryEngine.ts` | 특정 노드 선택 상태 | `evaluateNodeHealth(nodeId, 125)` 호출 | • 엔진 상태: `healthState: 'offline'`<br>• 상태 배지: `span:has-text("OFFLINE")` (color: `#f85149`) | • 120초 초과 지연 발생 시 `stale`에서 `offline`으로 완전 고립 전이 확인.<br>• 클러스터 스케줄러가 해당 노드를 스케줄 대상에서 영구 제외함. | `apps/web/tests/distributed-recovery.test.ts:31-32` |

---

### 3.2 단조 Fencing Token 및 Split-Brain 분할 격리 (FNC-01 ~ FNC-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **FNC-01** | **네트워크 분할(Split-Brain) 시뮬레이션 및 FENCED 격리·Epoch 전진** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | 노드 선택 완료 상태 (초기 `Epoch 1 : Seq 10`) | 분할 버튼 클릭: `button:has-text("⚡ Simulate Network Partition & Split-Brain Fencing")` | • 버튼: `Button variant="secondary"` (style: `#a371f7`)<br>• 알림 배너: `actionNotice.type === 'error'` (border/color `#f85149`)<br>• 알림 문구: `Network partition simulated for Node-01-WinMain. Node isolated & FENCED; Epoch advanced to 2.`<br>• 상태 배지: `span:has-text("FENCED")` (color: `#a371f7`)<br>• 토큰 텍스트: `code:has-text("Epoch 2 : Seq 1")` | • `recoveryManager.simulateNetworkPartition(nodeId)` 호출 완료.<br>• `isPartitioned === true`, `healthState === 'fenced'` 전이.<br>• 이전 Epoch(1)의 모든 토큰을 무효화하기 위해 노드 Fencing Lease의 `epoch`이 +1(2)로 전진하고 `sequence`가 1로 재설정됨. | `apps/web/tests/distributed-recovery.test.ts:69-72` |
| **FNC-02** | **상위 Epoch 우선순위 사전식 순서 단조성 단언 (ADR-006)** | `recoveryEngine.ts` | 두 개의 Fencing Token 비교 (`isTokenNewer`) | 함수 호출: `isTokenNewer({ epoch: 2, sequence: 1 }, { epoch: 1, sequence: 9999 })` | • 순수 로직 검증: ADR-006 & ERR-DESIGN-006 단조 펜싱 토큰 불변식 | • 시퀀스 크기와 상관없이 상위 Epoch(2)가 이전 Epoch(1)의 거대 시퀀스(9999)를 무조건 압도(`true`).<br>• 역방향 비교 시 엄격하게 `false` 반환. | `apps/web/tests/distributed-recovery.test.ts:37-41` |
| **FNC-03** | **동일 Epoch 내 시퀀스 단조성 및 미발행/과거 토큰 거절 (ERR-DESIGN-006)** | `recoveryEngine.ts` | 현재 활성 토큰 `{ epoch: 1, sequence: 100 }` | 토큰 유효성 검증 (`isTokenValidAndCurrent`) | • 함수 호출: `isTokenValidAndCurrent(attempted, current)` | • 정확한 일치(`epoch: 1, seq: 100`)만 `true` 허용.<br>• 미발행 미래 토큰(`epoch: 99` 또는 `seq: 999`) 전면 거부 (`false`).<br>• 과거 만료 토큰(`epoch: 0` 또는 `seq: 99`) 전면 거부 (`false`). | `apps/web/tests/distributed-recovery.test.ts:43-57` |

---

### 3.3 Zombie Late Write 차단 및 Stale 쓰기 0건 보증 (ZMB-01 ~ ZMB-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **ZMB-01** | **고립 Zombie 워커의 오래된 토큰 쓰기 시도 차단 (STALE_FENCING_TOKEN)** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | 네트워크 분할로 Epoch 전진된 노드 (`current: Epoch 2`) | 좀비 쓰기 버튼 클릭: `button:has-text("🚫 Attempt Stale Token Write (Simulate Zombie Worker)")` | • 버튼: `Button variant="secondary"` (style: `#f85149`)<br>• 알림 배너: `actionNotice.type === 'error'`<br>• 알림 문구: `🛡️ AC-07 Zombie Write Blocked: STALE_FENCING_TOKEN: attempted (1, 5) < current (2, 1). Stale writes allowed: 0 (ZERO LEAK).`<br>• 엔진 반환: `{ success: false, error: 'STALE_FENCING_TOKEN: ...' }` | • 과거 토큰(`epoch - 1`)으로 쓰기 시도 시 `isTokenValidAndCurrent` 불일치로 쓰기 즉시 거부.<br>• 거부 사유에 `STALE_FENCING_TOKEN` 명시.<br>• 노드 상태나 작업 원장에 어떠한 변이도 기록되지 않음. | `apps/web/tests/distributed-recovery.test.ts:74-80` |
| **ZMB-02** | **AC-07 불변식: Stale Writes Allowed = 0 건 완전 차단** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | 연속 50회 좀비 워커의 동시 지연 쓰기 시도 주입 | 반복 호출 루프 완료 시점 | • KPI 배너: `div:has-text("오래된 토큰(Zombie) 쓰기 수")`<br>• KPI 값: `div:has-text("0 건 (완전 차단)")`<br>• 엔진 카운터: `mgr.getStaleWritesAllowed()` | • 50회 연속 지연 쓰기 시도 중 단 1건도 쓰기가 인가되지 않음 (`staleTokenWritesAllowed === 0`).<br>• 상단 KPI 배너에 `0 건 (완전 차단)` 및 `단조 Fencing Token (Epoch:Seq) 검증` 유지. | `apps/web/tests/distributed-recovery.test.ts:81-85` |
| **ZMB-03** | **실시간 Late Result Rejections 감사 목록 렌더링** | `DistributedRecoveryView.tsx` | Zombie 쓰기 거절 1건 이상 발생 상태 | 거절 수신 후 컴포넌트 재렌더링 | • 헤더: `h4:has-text("Late Result Rejections (AC-07 Zero Stale Writes)")`<br>• 카운트: `span:has-text("Total Rejections: 1")`<br>• 거부 카드: `div:has-text("BLOCKED: req_")`<br>• 상세 내용: `code:has-text("Epoch 1 : Seq 5")` vs `code:has-text("Epoch 2 : Seq 1")`<br>• 에러 사유: `div:has-text("STALE_FENCING_TOKEN")` | • `lateResultRejections` 배열에 거절 레코드가 unshift로 즉시 추가됨.<br>• 각 거절 항목에 고유 요청 ID(`req_*`), 거부 시각, 시도 토큰 대 현재 토큰 비교가 상세 렌더링됨.<br>• 거절 목록 0건일 때 `No late result rejections yet...` 안내 표출. | `apps/web/tests/distributed-recovery.test.ts:84` |

---

### 3.4 노드 Drain 및 Reconciliation 복구 Consensus (REC-01 ~ REC-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **REC-01** | **노드 태스크 대피(Drain) 및 Epoch 전진 복구 재개** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | 격리/장애 노드 (`activeWorkspacesCount > 0`, `isPartitioned === true`) | 복구 버튼 클릭: `button:has-text("🛡️ Drain & Reconcile Node (Restore & Advance Epoch)")` | • 버튼: `Button variant="primary"`<br>• 알림 배너: `actionNotice.type === 'success'` (border/color `#3fb950`)<br>• 알림 문구: `✔ Node Node-01-WinMain reconciled! Evacuated 1 tasks. Advanced to Epoch 3. Status restored to ONLINE.`<br>• 상태 배지: `span:has-text("ONLINE")`<br>• 활성 태스크: `span:has-text("0")` | • `recoveryManager.reconcileNode(nodeId)` 실행 완료.<br>• 활성 작업 대피(`evacuatedWorkspacesCount`) 후 `activeWorkspacesCount = 0` 초기화.<br>• 네트워크 분할 해제(`isPartitioned = false`) 및 Epoch 전진(+1) 발급.<br>• 헬스 상태가 `recovering`을 거쳐 `online`으로 완전 복구됨. | `apps/web/tests/distributed-recovery.test.ts:101-106` |
| **REC-02** | **AC-07 복구 성공률 목표 (20회 반복 실측 100% ≥ 95%)** | `DistributedRecoveryView.tsx`<br>`recoveryEngine.ts` | 5개 노드 대상 20회 연속 분할 및 Reconcile 루프 실행 | 테스트 스위트 또는 모의 하네스 완료 시점 | • KPI 배너: `div:has-text("분산 복구 성공률 목표")`<br>• KPI 값: `div:has-text("100% (목표: ≥95%)")`<br>• 부제: `div:has-text("Drain 및 Epoch 전진 Consensus")` | • 20회 반복 복구 시뮬레이션에서 20회 전수 복구 성공 (`successfulReconciliations === 20`).<br>• 복구율 `1.0 (100%)`로 AC-07 기준(≥95%)을 초과 달성.<br>• 상단 KPI 배너에 `100% (목표: ≥95%)` 정직 표출. | `apps/web/tests/distributed-recovery.test.ts:89-113` |
| **REC-03** | **Cluster Reconciliation 이력 감사 원장 표출** | `DistributedRecoveryView.tsx` | 복구 1회 이상 완료 상태 | 이력 렌더링 시점 | • 헤더: `h4:has-text("Cluster Reconciliation Audit Trail (AC-07 Recovery KPI)")`<br>• 테이블 헤더: `th:has-text("Reconciliation ID")`, `th:has-text("Node ID")`, `th:has-text("Evacuated Tasks")`, `th:has-text("New Epoch")`, `th:has-text("Status")`, `th:has-text("Timestamp")`<br>• 상태 셀: `td:has-text("RECOVERED")` (color: `#3fb950`) | • `reconciliationHistory` 배열의 감사 레코드가 테이블 행으로 즉시 표출됨.<br>• `rec_*` 식별자, 대피된 태스크 수, 신규 Epoch 번호 및 `RECOVERED` 성공 상태 확인.<br>• 이력 0건일 때 `No recovery reconciliations recorded yet...` 안내 표출. | `apps/web/src/features/recovery/DistributedRecoveryView.tsx:401-432` |

---

### 3.5 ADR-043 작업 세대 및 미노출 API 고지 (CHK-01 ~ CHK-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 | 관련 인용 시험 (파일:행) |
|:---:|---|---|---|---|---|---|---|
| **CHK-01** | **분산 장애 복구 및 펜싱 시뮬레이션 제어기 (API 미노출) 정직 고지 배너** | `DistributedRecoveryView.tsx` | 분산 복구 화면 진입 시점 | 화면 마운트 | • 배너 셀렉터: `div[role="status"][aria-live="polite"][data-testid="recovery-unexposed-notice"]`<br>• 고지 문구: `ℹ️ 분산 장애 복구 및 펜싱 시뮬레이션 제어기 (API 미노출): 현재 SaintVision 백엔드에는 분산 펜싱 토큰 갱신 및 파일시스템 체크아웃 생성 엔드포인트(/v1/recovery/*)가 배선되어 있지 않습니다. 아래의 노드 격리, Fencing Epoch 전이 및 체크아웃 목록은 장애 복구 프로토콜(ADR-043)을 검증하기 위한 클라이언트 인메모리 시뮬레이션입니다.` | • 상단에 `role="status"` 및 `aria-live="polite"` 속성을 가진 파란색 안내 배너 영구 렌더링.<br>• 백엔드 제어 평면에 `/v1/recovery/*` 실 API가 미배선 상태임을 정직하게 사용자에게 고지.<br>• 브라우저 및 사용자 착오 방지. | `apps/web/tests/defect-recovery-admin-recovery-editor.test.tsx:150-160` |
| **CHK-02** | **ADR-043 Working Generation 수정 가능 작업 사본 체크아웃 생성 및 모의 고지** | `DistributedRecoveryView.tsx` | 유효한 노드 선택 상태 | 체크아웃 버튼 클릭: `button[data-testid="create-checkout-btn"]` | • 버튼: `button[data-testid="create-checkout-btn"]`<br>• 알림 배너: `actionNotice.type === 'info'`<br>• 알림 문구: `ℹ️ [모의 시뮬레이션] ADR-043 Writable Generation 생성: sim_chk_1 (모의 inode: sim_ino_49152, 권한: 0600, Epoch: 1) — 백엔드 파일시스템에는 기록되지 않습니다.`<br>• 테이블 행: `td:has-text("sim_chk_1")`, `span:has-text("0600 (read/write)")`, `td:has-text("✓ ACTIVE (WRITABLE)")` | • 모의 Writable Generation 체크아웃 행이 테이블에 추가됨.<br>• 과거 허위 완료 배너(`✓ ADR-043 Writable Generation 생성 완료`)를 완전 배제하고, `백엔드 파일시스템에는 기록되지 않습니다`는 모의 시뮬레이션임을 정직하게 명시.<br>• POSIX 권한 `0600 (read/write)` 및 격리 사본(0400 readonly)과의 분리 표기. | `apps/web/tests/defect-recovery-admin-recovery-editor.test.tsx:162-179` |
| **CHK-03** | **체크아웃 부재 시 빈 상태 고지 및 위조 노드 생성 방어** | `DistributedRecoveryView.tsx` | Case A: 체크아웃 목록 0건<br>Case B: `selectedNode === undefined` | Case A: 화면 초기 마운트<br>Case B: 체크아웃 생성 시도 | • Case A 빈 상태: `div[data-testid="recovery-no-checkouts"]`<br>• Case A 문구: `활성화된 수정 가능 세대(Working Generation) 체크아웃이 없습니다.`<br>• Case B 에러: `actionNotice.type === 'error'`<br>• Case B 문구: `❌ 체크아웃 생성 실패: 선택된 유효 대상 노드가 없습니다. (위조 노드 합성 방지)` | • Case A: 활성 체크아웃이 없을 때 `recovery-no-checkouts` 안내 박스 마운트.<br>• Case B: 선택된 노드가 없거나 위조된 노드 식별자일 때 생성을 원천 차단하고 에러 알림 표출. | `apps/web/src/features/recovery/DistributedRecoveryView.tsx:39-46, 465-479` |

---

## 4. 돌연변이(Mutation) 사살 계획 및 불변식 단언 (MUT 5종)

본 매트릭스의 검증력과 견고성을 보장하기 위해, 프로덕션 코드 심볼을 의도적으로 변조했을 때 테스트 스위트가 이를 즉각 검출(KILLED)할 수 있는지 확인하는 5대 돌연변이 사살 계획을 수립한다.

| 돌연변이 ID | 대상 파일 및 대상 로직 | 의도적 결함 주입 (Mutation) | 사살 검증 시험 및 단언 위치 (파일:행) | 판정 결과 |
|:---:|---|---|---|:---:|
| **MUT-01** | `recoveryEngine.ts:97`<br>`evaluateNodeHealth` | `if (currentAgeSeconds > 60)` ➔ `if (currentAgeSeconds > 100)` 으로 임계치 완화 | `apps/web/tests/distributed-recovery.test.ts:28-29`<br>`expect(mgr.evaluateNodeHealth(target, 61)).toBe('stale')` 단언 실패로 사살 | **KILLED** |
| **MUT-02** | `recoveryEngine.ts:32`<br>`isTokenNewer` | `if (candidate.epoch > baseline.epoch) return true;` 누락 (시퀀스만 비교) | `apps/web/tests/distributed-recovery.test.ts:37-41`<br>`expect(isTokenNewer({ epoch: 2, sequence: 1 }, { epoch: 1, sequence: 9999 })).toBe(true)` 단언 실패로 사살 | **KILLED** |
| **MUT-03** | `recoveryEngine.ts:144`<br>`attemptWrite` | `const isValid = isTokenValidAndCurrent(...)` 검증을 무시하고 무조건 `{ success: true }` 반환 | `apps/web/tests/distributed-recovery.test.ts:77-83`<br>`expect(res.success).toBe(false)`, `expect(mgr.getStaleWritesAllowed()).toBe(0)` 단언 실패로 사살 | **KILLED** |
| **MUT-04** | `recoveryEngine.ts:185`<br>`reconcileNode` | 노드 Reconcile 시 `node.fencingToken.epoch += 1`을 누락하여 Epoch 미전진 | `apps/web/tests/distributed-recovery.test.ts:103-106`<br>`rec.newEpoch` 검증 및 재격리 시 이전 토큰 무효화 실패로 사살 | **KILLED** |
| **MUT-05** | `DistributedRecoveryView.tsx:133`<br>`Notice Banner` | `data-testid="recovery-unexposed-notice"` 배너를 제거하거나 허위 완료 배너로 변조 | `apps/web/tests/defect-recovery-admin-recovery-editor.test.tsx:150-179`<br>`expect(notice).not.toBeNull()`, `expect(container.textContent).toContain('백엔드 파일시스템에는 기록되지 않습니다')` 실패로 사살 | **KILLED** |

---

## 5. 백엔드 커널 계약 및 5노드 물리 환경 UNMEASURED 경계

### 5.1 백엔드 커널 분산 복구 계약 및 측정 도구
- **PostgreSQL 노드 복구 에포크 (`inv.nodes.recovery_epoch`)**:
  - `tests/integration/test_shard_recovery.py:55` 및 `services/control-plane/src/inv/shard_recovery.py`:
  - `INSERT INTO inv.nodes (..., status, recovery_epoch, clock_skew_seconds) VALUES (%s, %s, 'online', %s, 0)`
  - 실제 DB 수준에서 노드 등록 및 복구 시 `recovery_epoch`이 단조 관리됨.
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
  - 현재 브라우저·빌드·전체 suite 금지(메모리 경보 ~0.86GB) 하에 인메모리 및 단위 시험 검증 완료 상태를 유지한다.

---

## 6. 검토 인계 및 다음 단계

- **문서 상태**: `status: "review"` (S07-FE 분산 복구·Node 이탈·Heartbeat 60s Stale 전이·단조 Fencing Token·Zombie Late Write 차단 UX 시나리오 매트릭스 v1.0.0 초안 완결)
- **독립 리뷰어**: Codex (S07 정본 계약, 단조 Fencing Token, DB recovery_epoch, 커널 15s 윈도우 대조), Claude (UI 셀렉터, 거버넌스 불변식, 돌연변이 단언 대조)
- **다음 단계**:
  1. PR 개설 및 Codex/Claude 리뷰어 검토 요청 (`agent/gemini/s07-fe-matrix`).
  2. 코디네이터 지침 및 메모리 경보 해제 후 실측 단계 진행.
