---
doc_id: "GEMINI-ERR-DESIGN-007-REVISION-PROPOSAL-001"
title: "ERR-DESIGN-007 규격 개정안 및 노드 시각 스큐 알람 활성화 계획"
version: "1.0.0"
status: "proposed"
author: "Gemini"
updated: "2026-09-22T17:15:00+09:00"
source_of_truth: "Git"
tags: ["decision", "clock-skew", "alarm", "governance", "ERR-DESIGN-007"]
---

# ERR-DESIGN-007 규격 개정안 및 노드 시각 스큐 알람 활성화 계획

> **목적**: [[사용자_결정대기_브리프_2026-09-22]] 항목 7(노드 시각 스큐 알람 활성화)의 선행 조건인 [[ERR-DESIGN-007 시각 동기화 요구 부재]]의 규격을 현실에 맞게 개정하고, [[알람 라우팅과 대응 주체]]에 부합하는 운영 알람 활성화 명세 및 실측 검증 계획을 수립한다.

---

## 1. 개요 및 배경

[[ERR-DESIGN-007 시각 동기화 요구 부재]]는 2026-09-09 Claude가 제품의 여러 분산 안전 조건이 노드 시계에 의존함에도 명시적 시각 동기화 규격이 없음을 지적하며 등록한 설계 오류 문서다.

현재 커널(`services/control-plane/src/inv`)은 이미 `inv.nodes.clock_skew_seconds` 컬럼(`0001_core.sql`)을 통해 heartbeat 시 스큐를 기록하고, `scheduler.py`, `placement.py`, `leases.py`, `containment.py`, `dispatch.py`, `tooling.py` 등 모든 실행 적격성 검사에서 `abs(clock_skew_seconds) <= 5` 가드를 운영 코드로 엄격하게 강제하고 있다.

그러나 거버넌스 규격 상으로는 알람 발화 기준, 심각도, 통지 채널, 대응 주체에 대한 공식 채택이 미결로 남아 있어, `tools/alarm_check.py`에서 해당 알람이 `governanceGated` 상태로 격리되어 있다. 본 문서는 현재 규격의 결함을 정밀 분석하고, 실 구현과 일치하는 개정 문안 및 활성화 방안을 제시한다.

---

## 2. 현재 규격(ERR-DESIGN-007)의 결함 분석

현재의 `ERR-DESIGN-007` 원안(v1.0.0)은 다음 4가지 핵심 결함을 안고 있어 그대로 채택할 수 없으며 개정이 필수적이다.

1. **상태 방치 및 커널 기구현 현실 미반영**:
   - 2026-09-09 작성 이후 `status: open`, `검토 지적, owner 판단 대기` 상태로 머물러 있어, 커널 소스에 이미 안착된 런타임 가드(`abs(clock_skew_seconds) <= 5`)를 공식 규격으로 수용하지 못했다.
2. **과도하거나 비현실적인 환경 전제 요구**:
   - 원안 제안 1항은 "NTP 동기화를 Node 등록의 하드 전제조건으로 둔다"고 하였으나, 파일럿 환경인 "기존 Windows/Linux 물리 PC 5대"는 로컬 사용자 권한, 방화벽, 도메인 제약 등으로 인해 Node 등록 시점에 엄격한 NTP 검증을 강제하기 어렵다.
   - 원안 제안 3항은 "Node가 만료를 절대 시각이 아니라 상대 TTL(로컬 monotonic clock)로만 판단해야 한다"고 제안했으나, 실제 Control Plane 커널은 DB의 `clock_timestamp()`와 서버 수신 시각을 기준으로 만료를 통제하므로 Node 측의 단조 시계 강제는 불필요한 아키텍처 복잡성을 초래한다.
3. **부적절한 위협 모델 상정 (실제 발생하지 않는 실패 모드 지적)**:
   - 원안은 "Node의 heartbeat 시각이 미래로 기록되면 이탈 감지가 지연되어 AC-07(60초)을 넘긴다"고 주장했으나, 실제 `inv/observation.py` 구현은 Node의 보고 시각이 아니라 **서버 수신 시각(`clock_timestamp()`)**을 `heartbeat_at`에 기록하므로 해당 지연 위협은 원천적으로 발생하지 않는다 ([[설계 미결 3건 구현 영향 분석]] 확인).
4. **운영 알람 연계의 구체성 결여 (영구 거버넌스 차단 초래)**:
   - 원안 제안 4항은 "스큐를 관찰 지표로 노출하고 한도 근접 시 경고한다"는 정성적 서술에 그쳐, 심각도(P1/P2/P3), 통지 채널, 1차 대응자, 조치 절차가 정의되지 않았다. 이로 인해 `tools/alarm_check.py`는 이를 활성화하지 못하고 `governanceGated` 사유로 묶어두는 원인이 되었다.

---

## 3. ERR-DESIGN-007 개정 문안

기존 `ERR-DESIGN-007`을 다음과 같이 개정하여 확정 채택(Accepted) 규격으로 전환한다.

### [개정 규격서 본문]

#### 제1조 (목적)
본 규격은 SaintVision 클러스터에 참여하는 Node와 Control Plane 간의 시각 편차(Clock Skew) 허용 한계를 규정하고, 시계 이상 노드의 작업 격리 및 운영자 통지 절차를 확립하여 분산 임대(Lease), 스케줄링, 이탈 감지의 무결성을 보장함을 목적으로 한다.

#### 제2조 (스큐 측정 원칙)
1. Control Plane은 Node Agent로부터 heartbeat 프로브를 수신할 때마다 Node가 보고한 로컬 시각과 서버의 `clock_timestamp()` 간의 차이를 계산하여 초 단위의 `inv.nodes.clock_skew_seconds` (Numeric) 값으로 갱신한다.
2. `heartbeat_at` 영속화에는 Node 보고 시각이 아닌 서버의 `clock_timestamp()`를 사용하여 Node 시계 이상에 따른 이탈 감지 지연을 원천 차단한다.

#### 제3조 (런타임 적격성 가드 - 커널 정본)
1. 커널(`inv.scheduler`, `inv.placement`, `inv.leases`, `inv.containment`, `inv.dispatch`, `inv.tooling`)은 다음 중 하나에 해당하는 노드를 모든 스케줄링, 자원 배치(Placement), 임대(Lease) 발급 및 실행 준비 적격 대상에서 즉시 제외한다:
   - `clock_skew_seconds IS NULL` (측정치 부재)
   - `NOT is_finite(clock_skew_seconds)` (비정상 수치)
   - `abs(clock_skew_seconds) > 5.0` (허용 한계 초과)
2. 본 5초 런타임 가드는 운영 안전의 절대 기준으로 상시 유지되며 임의로 완화하거나 우회할 수 없다.

#### 제4조 (운영 알람 규격)
1. **알람명**: `Node 시각 스큐 한도 초과`
2. **심각도**: **P2** (경고 및 계획된 정비 대상; 커널 가드가 이미 자원 배치를 차단하므로 P1 비상 장애 아님)
3. **트리거 조건**: 온라인 상태인 활성 노드 중 `abs(clock_skew_seconds) > 5.0` 또는 스큐 측정이 불가능한 노드가 1대 이상 존재할 때 즉시 발화(`firing = true`).
4. **해제 조건**: 해당 노드의 후속 heartbeat에서 `abs(clock_skew_seconds) <= 5.0`이 실측되면 즉시 자동 해제(`firing = false`).

---

## 4. 알람 라우팅 규정과의 정합

[[알람 라우팅과 대응 주체]]에 본 알람을 다음과 같이 완전히 일치시켜 배선한다.

| 항목 | 규정 값 | 정합 근거 |
|---|---|---|
| **심각도** | **P2** | 커널 안전 필터가 스큐 노드로의 작업 배정을 원천 봉쇄하므로 데이터 오염이나 P1급 즉각적 서비스 다운은 발생하지 않음. 단, 노드 가용 자원 풀이 축소되므로 계획적 대응 필요. |
| **1차 대응 주체** | **인프라** (운영 담당) | 물리 노드의 OS 시간 동기화 서비스(Windows Time, chrony/systemd-timesyncd) 점검 및 하드웨어 RTC 상태 확인 주체임. |
| **백업 대응 주체** | **Backend 운영** | 인프라 부재 시 Control Plane 노드 메트릭 및 DB 관측값 교차 검증. |
| **통지 채널** | **기록 채널** (대시보드 및 알람 로그) | P2 라우팅 규칙에 따라 즉시 호출 채널(전화/SMS)이 아닌 기록 채널로 전달. |
| **자동 조치 여부** | **자동 조치 없음** | 파일럿 규모에서 자동 차단/노드 영구 퇴출은 일시적 NTP 지연 시 오탐 피해가 더 큼. 커널의 배치 제외로 이미 안전함. |
| **대응 시간 정책** | **근무 시간 내 대응 (온콜 없음)** | [[알람 라우팅과 대응 주체]] §4(온콜을 두지 않는다) 원칙에 따라 주간 근무 시간에 인프라 담당자가 시각 동기화 복구 수행. |

---

## 5. 활성화 시 영향 범위 분석

본 규격 개정안 채택 및 알람 활성화 시 변경되는 시스템 영향 범위는 다음과 같다.

1. **`tools/alarm_check.py` 변경**:
   - `GOVERNANCE_GATED` 튜플에서 `Node 시각 스큐 한도 초과`를 제거.
   - `evaluate_alarms()` 쿼리에 `inv.nodes`의 스큐 초과 노드 검사 로직 활성화:
     ```python
     # 활성화 대상 쿼리
     """
     SELECT COUNT(*) FROM inv.nodes
     WHERE status = 'online'
       AND (clock_skew_seconds IS NULL
            OR abs(clock_skew_seconds) > 5.0)
     """
     ```
   - 알람 목록에 `count_alarm("Node 시각 스큐 한도 초과", "P2", "인프라", count, detail)` 추가.
2. **테스트 스위트(`tests/test_alarm_check.py`) 변경**:
   - 기존 `test_clock_skew_is_governance_gated_not_silently_dropped` 테스트를 개정하여, 해당 알람이 gated가 아니라 활성 평가 대상으로서 `firing=True`(스큐 발생 시) 및 `firing=False`(스큐 정상 시) 양방향을 엄격히 검증하도록 수정.
3. **제품 커널 및 런타임 영향**:
   - **영향 없음 (0건)**: 커널은 이미 마이그레이션 0001부터 `abs(clock_skew_seconds) <= 5` 가드를 운영 중이므로 백엔드 런타임이나 SQL 변경이 전혀 없음.
4. **운영 환경 영향**:
   - 운영자가 파일럿 5대 PC 중 시간 동기화가 풀린 장비를 대시보드와 알람을 통해 즉각 인지할 수 있게 되어 "왜 특정 노드에 작업이 할당되지 않는지"에 대한 운영 가시성이 확보됨.

---

## 6. 실측 계획 (실 PostgreSQL 기반 검증 명세)

알람 활성화 전후로 실 PostgreSQL 16(`127.0.0.1:55432/invdev`)에서 실행 가능한 구체적 시험 명세는 다음과 같다.

### 6.1. 테스트 케이스 매트릭스

| 케이스 ID | 대상 노드 상태 및 `clock_skew_seconds` | 기대 알람 상태 | 기대 심각도 / 대응자 |
|---|---|---|---|
| **TC-SKEW-01** | `status='online'`, `clock_skew_seconds = 0.0` | **Quiet (`firing: false`, `count: 0`)** | - |
| **TC-SKEW-02** | `status='online'`, `clock_skew_seconds = 4.9` (경계 내) | **Quiet (`firing: false`, `count: 0`)** | - |
| **TC-SKEW-03** | `status='online'`, `clock_skew_seconds = 6.2` (양수 초과) | **Firing (`firing: true`, `count: 1`)** | P2 / 인프라 |
| **TC-SKEW-04** | `status='online'`, `clock_skew_seconds = -5.5` (음수 초과) | **Firing (`firing: true`, `count: 1`)** | P2 / 인프라 |
| **TC-SKEW-05** | `status='online'`, `clock_skew_seconds = NULL` (미측정) | **Firing (`firing: true`, `count: 1`)** | P2 / 인프라 |
| **TC-SKEW-06** | `status='offline'`, `clock_skew_seconds = 10.0` (오프라인 노드) | **Quiet (`firing: false`, `count: 0`)** | 오프라인 노드는 별도 이탈 알람 관할 |
| **TC-SKEW-07** | 복구 검증: TC-03 노드를 `clock_skew_seconds = 0.2`로 갱신 | **Quiet (`firing: false`, `count: 0`)** | 자동 해제 확인 |

### 6.2. 실측 실행 절차

```powershell
# 1. 테스트 노드 픽스처 삽입 (실 PostgreSQL)
psql -h 127.0.0.1 -p 55432 -U invowner -d invdev -c "
INSERT INTO inv.nodes (tenant_id, node_id, status, recovery_epoch, clock_skew_seconds)
VALUES ('00000000-0000-0000-0000-000000000001', 'node-skew-test-01', 'online', gen_random_uuid(), 6.5);
"

# 2. alarm_check 도구 평가 실행
.venv\Scripts\python.exe -m pytest tests/test_alarm_check.py

# 3. 정리
psql -h 127.0.0.1 -p 55432 -U invowner -d invdev -c "
DELETE FROM inv.nodes WHERE node_id = 'node-skew-test-01';
"
```

---

## 7. 결론 및 코디네이터 결정 요청

본 규격 개정안을 바탕으로 코디네이터는 아래 두 가지 선택지 중 하나를 결정할 수 있다.

- **선택지 A (권고 — 규격 개정 채택 및 알람 즉시 활성화)**:
  - 본 `ERR-DESIGN-007` 개정안을 거버넌스 정본으로 채택하고, `tools/alarm_check.py`에서 `Node 시각 스큐 한도 초과` 알람을 `GOVERNANCE_GATED`에서 해제하여 활성 P2 알람으로 전환한다.
  - **이점**: 커널은 이미 스큐 노드를 배제하고 있으므로 알람을 켜야만 "노드가 왜 스케줄링에서 빠졌는지" 운영자가 즉각 인지할 수 있다. 런타임 위험이 전무하다.
- **선택지 B (보류 — 규격 개정안만 수립하고 알람 활성화는 파일럿 장비 실측 후로 유예)**:
  - 본 규격 개정안은 승인해 두되, 실제 알람 활성화는 파일럿 물리 PC 5대가 실제로 투입되어 현장 NTP 동기화 오차를 관측한 이후로 유예한다 (`governanceGated` 유지).
  - **이점**: 파일럿 PC 환경의 시계가 초기 설정 미비로 5초를 빈번히 넘나들 경우 발생할 수 있는 초기 알람 피로를 방지할 수 있다.
