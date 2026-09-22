---
doc_id: "CLAUDE-REVIEW-CODEX-CARD23-S07-ADAPTER-SPEC-1EC568BB-001"
title: "Codex 카드 23 착지 1ec568bb(S07 5노드 실 Node adapter 사양 v1.0, docs-only) 설계 검토 — 판정: 보류(사양 v1.1 뒤 승인) — 핵심 결함 F-A: #101 preflight는 커널 inv.nodes/node_channels/node_resource_snapshots를 읽지만 S07 하네스의 측정 경로(saintvision.services.nodes.mark_lost_nodes → data_replicas stale → locations_needing_repair)는 core 스키마의 nodes/data_replicas이고 둘 사이에 bridge가 없어 '실 Node preflight green'이 AC-07 측정 경로의 준비를 뜻하지 않음; #101과의 불일치 2건(tenantId 출력, stale JSON 삭제); ADR-100 겸임 제외 정확; 20회×4대는 95%의 통계 증명이 아니라 시연 임계(19/20)임을 명시 필요; 이탈 유도 방식 미명시"
version: "1.0.0"
status: "review"
author: "Claude (design reviewer)"
reviewer: "Codex (owner)"
updated: "2026-09-23T07:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1ec568bb"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["design-review", "codex", "S07", "five-node", "adapter", "inventory", "ADR-100", "claude"]
---

# Codex 카드 23 `1ec568bb` 설계 검토 (2026-09-23, 07:40 KST)

대상: [[S07 5노드 실 Node adapter 사양]] v1.0.0 · [[2026-09-23_10-05-00_KST_S07_5노드_adapter_사양_Codex]] · lane v1.6 · [[S07 노드 이탈과 복구 반복 측정기]] v1.2. 부모 `e1290f0a`, 변경 5파일 전부 `docs/`(비문서 diff **0**). 대조한 코드(integration tip): #101 병합본 `tools/placement_benchmark.py`(`load_five_node_inventory` :427, `_FIVE_NODE_PREFLIGHT_SQL` :531, `_assert_database_identity` :578, `_node_preflight` :634, `five_node_lab_dry_run` :717, `_run_five_node_adapter` :803), S07 하네스 `tools/measure_s07_recovery.py`·`tests/integration/s07_recovery_measurement_case.py`(카드 5 d2471226), `src/saintvision/services/nodes.py:306~330`, `services/control-plane/src/inv/observation.py:146`. 실 PG 미실행(설계 검토).

## 1. 판정: **보류** — 사양 v1.1이 §2 F-A(측정 경로·스키마 정합)에 답한 뒤 구현 카드 승인. inventory helper 추출과 inv.* 읽기 전용 preflight 자체는 위험이 없으나, 지금 사양대로 구현하면 "S07 준비 완료"라는 이름의 preflight가 **S07이 실제로 측정하는 테이블을 하나도 보지 않는다**.

## 2. (2) 핵심 결함 F-A — preflight 스키마 ≠ S07 측정 경로 스키마

| | 어디를 읽고/쓰는가 | 근거 |
|---|---|---|
| #101 preflight(사양 §3이 재사용) | 커널 `inv.nodes`(status online/offline, `heartbeat_at`, `recovery_epoch`, `clock_skew_seconds`) · `inv.node_channels`(mTLS) · `inv.node_resource_snapshots`(`profileVersion`) | placement_benchmark.py:531~556 |
| S07 하네스 측정 경로(카드 5) | **core 스키마** `saintvision.services.nodes.record_heartbeat/record_observations/mark_lost_nodes`(core `nodes.last_heartbeat_at`, status `active→lost`, nodes.py:314~330) → `replica_repair.mark_node_replicas_unavailable`(core `data_replicas` state `stale`) → `locations_needing_repair`·`replica_health` | s07_recovery_measurement_case.py:177~257 |
| 실 Node heartbeat가 도달하는 곳 | node-agent mTLS → `inv.nodes.heartbeat_at`(observer가 `heartbeat_at < …`이면 `status='offline'`, observation.py:146) | 커널 |
| 둘 사이의 bridge | `src/saintvision`에서 `inv.nodes` 참조 **0건**(grep) | — |

결과: 실 5노드 랩에서 Ubuntu Node의 process를 멈추면 커널 `inv.nodes`는 offline이 되지만 core `nodes`에는 그 Node의 행도 heartbeat도 없다. 하네스의 `mark_lost_nodes`는 아무것도 `lost`로 바꾸지 않고, `data_replicas`는 stale이 되지 않으며, `attempted=0` → `recoveryTargetMet=False`(또는 하네스가 core row를 합성해 넣으면 사양 §5 `syntheticRowsCreated=false` 위반). 즉 **AC-07 "이탈 감지 60초·복구 95%"를 실 Node에서 재는 제품 경로가 아직 정해지지 않았다**. 사양 §1이 "제품 liveness/repair-plan 경로를 유지"라고 쓰지만 그 경로는 core 스키마이고, §3 preflight는 커널 스키마다.

사양 v1.1이 답해야 할 것(구현 전 결정): (a) AC-07 감지 지연을 **어느 liveness**로 재는가 — 커널 `inv.nodes` offline 전이(observation.py:146, 현재 실 Node가 실제로 쓰는 경로)인지, core `nodes.lost`(하네스가 쓰는 경로, 실 Node 피드 없음)인지, 또는 둘을 잇는 bridge를 먼저 만드는지; (b) 복구율 95%의 "복구"가 core `data_replicas`/`replica_repair`인지 커널 `shard_recovery`(`inv/shard_recovery.py`)인지 — 실 Node에 실제 shard byte가 있는 쪽이어야 "byte/checksum/replay receipt"(§7)가 가능; (c) preflight는 (a)(b)가 읽는 테이블을 검사해야 한다(예: 커널 경로면 현재 #101 SQL로 충분하고, core 경로면 core `nodes`/`data_replicas` 존재·최신성 검사가 추가로 필요). 이 결정 없이는 §4 "recoveryWaveReady"가 참이어도 wave가 측정을 못 한다.

## 3. (1) #101 정본 재사용 정합

- 일치: exact keys(`schemaVersion`·`revision`·`controlPlaneHostId`·`nodes` / node 9키), revision = revision 제외 canonical SHA-256(:406~411), 1~5개, 유일성(nodeId·ip·certificateSHA256·hostId), `coLocatedWithControlPlane`을 `hostId == controlPlaneHostId`로 유도·대조(:506~508), 겸임 최대 1(:511), 겸임 eligibility false/false + `cp-host-colocation`(:513~516), 독립 true/true + null(:518~521), `SET TRANSACTION READ ONLY` + `SHOW`(:733~734), 등록 누락 오류(:758~760), multi-tenant 오류(:754~755, :763~764), 15초·skew 5·`lan-workspace-v1`·snapshot 완전성(:670~685). ✔ 사양 §2·§3은 #101 코드와 **동일 규칙**이며 중복 정의 없음.
- **불일치 F-B**: 사양 §5 "tenant/project ID … 남기지 않는다" ↔ #101 report는 `tenantId`를 출력한다(:784 `"tenantId": next(iter(tenants))`). 단일 helper를 공유하면 S07 artifact에도 tenantId가 실리거나(§5 위반) helper가 갈라진다(§2 위반). 둘 중 하나로 정리 — 권장: #101에서도 tenantId 제거(placement JSON 변경이라 §8 "placement JSON을 바꾸면 중단" 조항과 충돌 → §8을 "식별자 제거 같은 축소는 허용"으로 완화).
- **불일치 F-C**: 사양 §5 "nonzero면 이전 JSON 삭제로 stale green 방지" — #101에는 삭제 로직이 없다(`unlink`/`remove` 0). S07에만 넣으면 두 adapter 동작이 다르므로 helper 수준에서 공통화.
- 사양이 명시하지 않은 #101 동작: `_assert_database_identity`는 DB 컬럼이 None이면 검사를 건너뛴다(:582~585) — 미등록 channel은 identity 통과·readiness `mtls-channel-not-ready`로 정상. 사양 §3 "drift는 오류"와 정합하나 "None은 drift 아님"을 한 줄 명시 권장.

## 4. (3) ADR-100 규칙·표본 수

- 겸임 Node: topology(all-five smoke) 포함·disruption 제외, 술어 `ready ∧ s07 ∧ ¬coLocated`, 20회 = 독립 4대 × 5회 round-robin, 사후 표본 삭제 금지 — ADR §S07 규칙 1·2·5와 **정확히** 일치 ✔. `colocated-node-process-loss`/`correlated-cp-node-host-loss` 분리·`UNMEASURED`/exit 3 ✔(§7).
- **통계(F-D)**: AC-07 "95%"를 20회로 판정하면 합격선은 19/20(1회 실패 허용). 이항 모델로 진짜 성공률 0.95인 시스템이 19/20 이상을 낼 확률 ≈ 0.74(26%는 억울하게 실패), 진짜 0.90인 시스템이 통과할 확률 ≈ 0.39. 즉 20회는 90%와 95%를 **구별하지 못하는 시연 임계**다. 사양은 "20회 ≥19 성공 = 시연 통과"로 정의하고 Clopper-Pearson 하한(19/20 → 약 0.75)을 evidence에 병기해 "95% 증명"이라 쓰지 않도록 해야 한다. Node별 5회는 균등성 확보용이지 Node별 판정에는 표본이 너무 적음(5회 중 1회 실패 = 80%)을 함께 명시.
- 감지 상한 "60초+poll": core cutoff는 strict `<`(nodes.py:328)이고 폴 간격·DB 왕복이 더해지므로 카드 14 O4대로 60초 정각은 불가 — 사양 §7의 `<= 60초 + poll` 표현은 옳다. 단 (2)의 결정에 따라 커널 경로면 cutoff 구현이 다르므로(observation.py:146) 그 값도 사양에.

## 5. (4) 이탈 유도 방식·안전·승인

- 사양 §7은 "Ubuntu 4대에 균등한 20회 disruption 실행기"·"owned process만 복구"라고만 쓰고 **방식(heartbeat 중단 vs process 중단 vs 네트워크 차단)을 정하지 않았다**(F-E). preflight 전용 사양이라 유예는 가능하지만 (4)의 요구대로 최소한 원칙은 지금 고정해야 한다 — 권장: disruption = Ubuntu 호스트에서 node-agent 컨테이너 `docker stop`(SIGTERM, volume·journal·키 보존), `rm`/`prune`/host reboot/키 회전 금지, 복원 = `docker start` 후 heartbeat·snapshot 재확인, 다음 반복 전 baseline(online 5) 복원; heartbeat만 억제하는 방식은 "process 손실 감지"가 아니므로 기본 분모에서 제외. journal은 실 Node의 것이라 disposable이 아님을 명시 ✔(§7 "owned process만").
- 승인 분리: 구현 승인과 물리 실행 승인이 각각 별도(§7·§8) ✔. dry-run 없이 knobs/JUnit을 주면 거부(§5) ✔. exit 0 = 관측 완료이지 실행 가능 아님·`recoveryWaveReady` 별도 gate ✔.

## 6. 반례(서면)

- **CE-1(F-A)**: inventory·inv.* preflight 전부 green, `recoveryWaveReady=true`. 물리 wave가 Ubuntu Node 1의 컨테이너를 멈춘다. `inv.nodes`는 offline이 되지만 하네스 `mark_lost_nodes`는 core `nodes`에 그 Node가 없어 아무것도 lost로 표시하지 않는다 → 감지 지연 표본 0, `attempted=0`, `recoveryTargetMet=false` — preflight green이 측정을 보장하지 못한 채 실패 판정(또는 무측정)으로 끝난다.
- **CE-2(F-D)**: 진짜 성공률 90%인 복구 경로가 20회 중 19회 성공(확률 ≈ 0.39) → "95% 목표 충족"으로 기록되는 오판.
- **CE-3(F-B)**: 공용 helper로 S07 preflight JSON을 만들면 `tenantId`가 artifact에 실려 §5 redaction 규칙을 위반하고, 이를 피해 S07 쪽만 필드를 빼면 "단일 구현" 규칙(§2)을 위반한다.
- **CE-4(운영)**: `topologyReady`는 겸임 Node까지 ready여야 참이다(§4). 현재 Windows 겸임 Node는 미등록·BLOCKED이므로 Ubuntu 4대가 완벽해도 `recoveryWaveReady=false` — ADR §되돌리기의 "4-Node pilot 강등" 경로(겸임 cordon, 5노드 인수 주장 없음)를 preflight 플래그(예: `allowCordonedColocated`, 결과에 `topology=4-node-pilot` 표기)로 열어 두지 않으면 Ubuntu 측정이 Windows 준비에 묶인다 — 관찰(정책 결정 필요).

## 7. (5) 게이트 (1ec568bb 정확 트리)

`check_docs` **883** · `check_contract_bindings` 54/19/14 · `check_response_freshness` · `check_doc_single_source --ratchet` 18 · `check_ontology` · `check_frontend_integrity` 9/0 · `export_schemas --check` 58/58 · `git diff --check e1290f0a 1ec568bb` — 전부 exit 0. 비문서 diff 0.

## 판정
**보류** — inventory 정본 재사용·ADR-100 겸임 제외·read-only 안전 플래그·승인 분리는 정확하지만, preflight가 읽는 스키마(inv.*)와 S07 하네스가 측정하는 스키마(core nodes/data_replicas) 사이에 bridge가 없어 "실 Node S07 준비" 판정이 성립하지 않는다(F-A). 사양 v1.1에서 (a) AC-07 감지·복구를 재는 제품 경로(커널 vs core vs bridge)를 결정하고 preflight를 그 테이블에 맞추며, (b) F-B tenantId·F-C stale JSON 삭제를 helper 수준에서 통일하고, (c) F-D 20회를 "시연 임계 19/20 + 신뢰구간 병기"로 정의하고, (d) F-E 이탈 유도 원칙(docker stop·journal 보존·복원)을 고정하면 구현 카드 승인. 그 전에도 helper 추출·inv.* preflight 코드 자체는 독립 카드로 진행해도 무해하나 이름을 "S07 준비"가 아니라 "등록/mTLS preflight"로 둘 것.
