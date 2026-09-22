---
doc_id: "CLAUDE-CX09-PITR-TIER-A-DECISION-PREP-001"
title: "CX-09 PITR Tier-A 활성 여부 결정 준비 — runbook v1.2.0 실측 근거로 활성화(A) vs 유예(B) 비교 1쪽 + 코디네이터 결정 요청"
version: "1.1.0"
status: "decided"
author: "Claude"
reviewer: "Codex"
audience: "coordinator"
updated: "2026-09-22T22:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["pitr", "cx-09", "ac-12", "decision", "tier-a", "operations"]
---

# CX-09 PITR Tier-A 활성 여부 — 결정 준비

**결정할 것**: 이 PC의 개발/파일럿 PostgreSQL(`saintvision-invion-dev-pg`, 향후 Control Plane DB)에 `docker-compose.pitr.yml`(Tier-A 로컬 WAL 아카이브)을 **지금 적용(A)** 할지, **CX-09 릴리스 통합 시점까지 유예(B)** 할지. 근거 실측은 [[2026-09-22_17-14-47_KST_PITR-RUNBOOK_Claude_실측]]과 [[VF-CL-04 replica 복구와 PITR 운영 runbook]] v1.2.0 §4, 변경안은 [[2026-09-19_Claude_PITR_변경안과영향]].

## 1. 실측으로 확정된 사실 (2026-09-22, 새 PC)

| 사실 | 근거 |
|---|---|
| 이 PC dev PG는 **PITR absent** — `archive_mode=off`, `archive_command` disabled, `wal_level=replica`. `pitr_readiness --require-pitr` exit 1(인수 차단) | 실측 §1 (비파괴 probe DB) |
| Tier-A 절차 자체는 성립 — `tools/pitr_rehearsal.sh` 정상 1회 **PASS**(base backup → INSERT → 별도 클러스터 복원 → 목표 시각 승격), 결함 주입 5종은 **각기 다른 게이트로 FAIL**, 잔재 컨테이너 0 | 실측 §2 (옛 PC와 같은 매트릭스·같은 판정) |
| 보관 주기 **7일**(파일럿 값; 운영 전환 시 재결정) 결정됨 | runbook §4, 코디네이터 회신 |
| 활성화는 **postgres 재시작 수반** + **외부 `wal_archive` 볼륨 사전 준비(uid 70, 0700)** 없이는 WAL이 `pg_wal`에 쌓여 디스크를 채운다 | `docker-compose.pitr.yml` 헤더 |
| **설정은 필요조건이지 RPO 증거가 아니다** — AC-12(RPO ≤15분·RTO ≤1시간)는 활성 후 **실제 복구 드릴 측정**으로만 인수 | 변경안 원칙, `recovery_drill.rpo_bound_from` |
| Tier-A는 **같은 호스트 아카이브**(별도 장애 도메인 아님) → 디스크 손실엔 무력; 내구성은 Tier-B(off-host, wal-g/minio) | 변경안 §Tier A 한계·§Tier B |

## 2. A vs B

| | **A. 지금 활성화(Tier-A, 7일)** | **B. CX-09까지 유예(absent 유지)** |
|---|---|---|
| 얻는 것 | 파일럿 기간 동안 **논리 dump 시점이 아닌 시점 복구**가 가능해지고, `pitr_readiness`가 `possible`로 바뀌어 **AC-12 드릴을 실제로 돌릴 수 있다**(RPO 실측의 전제). 운영 절차(7일 정리·볼륨·모니터링)를 파일럿에서 먼저 익힌다 | 재시작·볼륨 준비 없이 지금 상태 유지. 이 PC의 dev DB 재시작 금지 조건(다른 에이전트가 동시에 사용) 유지 |
| 비용/위험 | (1) **postgres 재시작 1회** — 다른 에이전트의 실 PG 시험·개발 서버(8080) 중단 → **조율 창 필요**. (2) 외부 볼륨 미준비 시 디스크 포화 위험(사전 검증 명령 있음). (3) 같은 호스트라 디스크 장애엔 무력(Tier-B 아님) — "PITR 있음"으로 과대 기록 금지. (4) 7일 정리 자동화 미실측 → 운영자 수동 or 후속 카드 | (1) 파일럿 중 데이터 손실 시 복구점은 마지막 논리 dump. (2) AC-12는 계속 **미달성**이며 CX-09에서 활성+드릴을 한꺼번에 해야 해 릴리스 시점 위험 집중. (3) `pitr_readiness --require-pitr`가 계속 exit 1 |
| 되돌림 | override를 빼고 재시작하면 원복(아카이브 볼륨은 남음) | 해당 없음 |
| AC-12에 미치는 영향 | 필요조건 충족 → **드릴 카드 착수 가능**(RPO/RTO 실측 = 인수 증거) | 필요조건 미충족 → 드릴 불가 |

## 3. 권고 (reviewer 의견, 결정은 코디네이터)

**A를 권고하되 두 전제 아래**: (i) **재시작 창을 코디네이터가 잡는다**(다른 레인의 실 PG 시험·8080 dev 서버가 없는 시간; 통보 후 5분), (ii) 적용 전 **사전 검증 3단계**를 통과한다 — `docker volume create wal_archive` + 소유자 uid 70/0700 확인, `docker compose -f docker-compose.prod.yml -f docker-compose.pitr.yml config --quiet` exit 0, 적용 후 `pitr_readiness --require-pitr`가 `possible`로 전환. 그 뒤 **AC-12 드릴 카드**(base backup → 결함 → 복구 → RPO/RTO 측정)를 별도로 연다. 이유: 실측이 절차의 성립을 이미 증명했고, 파일럿에서 활성해야 릴리스(CX-09)에서 "처음 켜고 처음 드릴"하는 위험을 피한다. B를 고르면 CX-09 계획에 "활성+드릴+7일 정리"를 한 묶음으로 넣어야 한다.

**A를 골라도 기록 규칙**: `pitr_readiness=possible`은 "복구 가능"이 아니다. 드릴 측정 전까지 AC-12는 **미달성**으로 둔다.

## 4. 코디네이터 결정 요청

- [ ] **A** 활성화 — 재시작 창(일시)과 담당(Claude가 적용·검증, Codex 검토)을 지정
- [x] **B 유예 — 결정됨 (2026-09-22, 코디네이터, 사용자 위임)**. 근거: A는 dev PG 재시작(다른 레인 실 PG 시험·8080 dev 서버 중단)과 외부 `wal_archive` 볼륨 준비가 필요한데, 오늘은 5개 에이전트가 실 PG를 동시 사용 중이고 메모리 여유가 2GB 수준이라 조율 창을 잡기 어렵다.

### 결정 B에 따른 조치 (CX-09 카드 첫 항목으로 추가 — [[Codex 작업 현황]] CX-09 절)
1. **PITR 활성(Tier-A, 보관 7일)** — `docker-compose.pitr.yml` override 적용(postgres 재시작 수반).
2. **외부 볼륨 사전 검증 3단계** — `docker volume create wal_archive` + uid 70/0700 확인 → `docker compose -f docker-compose.prod.yml -f docker-compose.pitr.yml config --quiet` exit 0 → 적용 후 `pitr_readiness --require-pitr` = `possible`.
3. **실제 복구 드릴** — base backup → 결함 → 복구 → **AC-12 RPO/RTO 측정**(설정만으로 인수 금지).
4. **정리 도구** — `tools/pitr_archive_retention.py`(7일 초과 세그먼트/베이스백업 정리, 착지 예정).
- **재시작 창**: 에이전트 무활동 시간(예: 다음 작업일 시작 전)에 코디네이터가 지정.
- 이 문서가 그 카드의 근거 문서다. AC-12는 드릴 측정 전까지 미달성으로 둔다.

결정 후: A면 적용 절차 History + `readiness possible` 증거 + 드릴 카드 착수; B면 CX-09 카드 갱신(Codex owner). 둘 다 이 문서 status를 `decided`로 바꾼다.
