---
doc_id: "CLAUDE-REVIEW-PR110-FIVE-NODE-PREFLIGHT-HELPER-DE8A9B7D-001"
title: "PR #110 'S07: extract five-node registration preflight and fix physical path'(head de8a9b7d, merge-base 9e3827ac; 카드 29 F-A~F-E·CE-4 반영 사양 v1.1 + #101 helper 동작보존 추출) 독립 검토 — 판정: 승인(관찰 2, 비차단) — F-A 커널 inv 경로 결정이 observation.py:146·shard_recovery·output_ingestion·shard_completion 코드로 성립하고 core 경로는 '합성 proxy'로 정직 분리, helper 추출은 이동 코드 380행 중 tenantId 1행만 의도적 제거·나머지 동일, PG-free 15 passed·정적 되살림 KILLED·검토자 실 PG 1 passed(읽기 전용·불변·redaction), F-B/F-C/F-D/F-E/CE-4 반영 정확, 게이트 전부 0"
version: "1.0.0"
status: "review"
author: "Claude (reviewer)"
reviewer: "Codex (owner)"
updated: "2026-09-23T08:20:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "de8a9b7d"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["independent-review", "codex", "S07", "five-node", "preflight", "refactor", "ADR-100", "claude"]
---

# PR #110 `de8a9b7d` 독립 검토 (2026-09-23, 08:20 KST)

대상: `tools/five_node_lab_preflight.py`(신규 435행) · `tools/placement_benchmark.py`(−439/+6: import/re-export + `write_registration_mtls_preflight` 사용) · `tests/test_placement_benchmark_five_node_adapter.py`(+41: 재수출 동일성·tenantId 부재·stale 선삭제·inventory/report 동일 경로 거부) · [[S07 5노드 실 Node adapter 사양]] v1.1 · [[S07 노드 이탈과 복구 반복 측정기]] v1.3 · lane v1.7. 커널 `services/control-plane/src`·`src/`·계약·workflow diff **0**. 측정 트리 `D:\Project\sv-measure-claude`를 **`de8a9b7d`에 고정**(porcelain 0). 실 PG는 코디네이터 확인(Codex 카드 24 부하 12:20 KST 종료, 잔존 0) 뒤 검토자용 임시 시험 1회.

## 1. 판정: **승인** (관찰 2, 비차단 — §6)

## 2. (1) F-A 결정 — 코드 인용 검증

| 사양 v1.1 주장 | 코드 | 성립 |
|---|---|---|
| 실 heartbeat는 `inv.nodes`에 도달, observation이 offline 전이 | observation.py:88 heartbeat UPDATE(offline→online 복귀), **:146** `status='offline' WHERE heartbeat_at < clock_timestamp()-interval '60 seconds' AND status='online'` | ✔ (60초 하드코드 + observer poll = "60초+poll") |
| 복구 = `shard_recovery`의 fresh approval/run·source plan/shard·fence·bounded generation | shard_recovery.py:1~4 docstring("Fresh approval, physical fencing and at most three independent generations… identical WorkloadSpec and a new Run/approval"), :66 `inv.shard_recoveries` root_plan/generation, :84~85 generation>3 → `NODE-0064`, :87 source epoch `LEASE-0004`, :98 active lease 검사 | ✔ |
| 실 shard byte = `output_ingestion` receipt base64 size/SHA-256 → storage object | output_ingestion.py:23~27 `b64decode`·`len(data)!=sizeBytes`·`sha256(data)!=sha256`, :149 `store.begin(… sha256, len(data))` | ✔ |
| `shard_completion`이 byte를 다시 읽어 manifest/hash/evidence commit | shard_completion.py:103 모든 object `state='ready'` 요구, :106 `files.read(object_key, content_hash, size_bytes)`, :107~125 manifest(evidenceId·sha256·sizeBytes)·`new_id("evd")` | ✔ |
| core 경로는 assessment/plan만, byte 이동 없음, 하네스 성공은 owner fixture proxy | 카드 5 검토 §2·§3(replica_repair는 plan·state만, fixture가 verified replica INSERT) | ✔ 정직 |
| bridge 신설 안 함 | `src/saintvision`에 `inv.nodes` 참조 0(카드 29) | ✔ 명시 |

preflight 테이블(`inv.nodes`/`node_channels`/`node_resource_snapshots`)은 결정된 커널 경로의 **등록/mTLS 전제**와 일치하며, 사양이 helper 이름을 "등록/mTLS preflight"로 한정하고 wave preflight(source plan/shard·terminal parent·stop receipt·lease/fence·membership·output storage·shard-completion 준비)를 후속으로 분리한 것도 카드 29 판정과 정합. ✔

## 3. (2) helper 추출 동작 보존 · F-B · F-C

- **이동 코드 대조**: placement_benchmark.py에서 제거된 비공백 380행을 helper 398행과 정규화 비교 → helper에 없는 제거 행 **5행뿐**: `"tenantId": next(iter(tenants), None)`(F-B 의도 제거) + 옛 `_run_five_node_adapter`의 load/dry_run/mkdir/write_text 4행(`write_registration_mtls_preflight`로 대체). 나머지 375행은 **문자 단위 동일**. placement는 `tools.five_node_lab_preflight`/`five_node_lab_preflight` 이중 import로 상수·SQL·함수를 재수출하고 시험 `test_placement_adapter_reexports_the_shared_preflight_implementation`이 `is` 동일성을 고정 ✔ 단일 구현.
- **F-B**: helper는 multi-tenant를 내부에서 오류로 검사하되(:115~116 상대 로직 유지) report에서 `tenantId` 제거, 시험 `assert "tenantId" not in report` ✔.
- **F-C**: `write_registration_mtls_preflight`(helper:417~435)가 inventory==report 경로 거부 → `report_path.unlink(missing_ok=True)` → validation → DB 조회 → 성공 시에만 write. 시험 2건(stale 선삭제·validation 전 DB 미접근·inventory 미삭제) ✔. CLI `_run_five_node_adapter`는 `--inventory`·`--dry-run`·DSN 필수 유지, exit 0 의미 무변경 ✔.
- **재현**: `tests/test_placement_benchmark_five_node_adapter.py` **15 passed**(+`test_placement_benchmark_tool.py` 4 = 19), `py_compile` 2파일 exit 0.
- **정적 되살림**: helper `_node_preflight`의 `"ready": not reasons`를 `True`로 고정 → `test_dry_run_reports_stale_nodes_without_promoting_them` **1 failed** / 14 passed — dry-run이 helper 결과 변조를 잡는다(KILLED). 원복, porcelain 0.
- **실 PG 1회(검토자 임시 시험, 워크트리 `tests/integration`에 두고 실행 후 삭제)**: disposable DB(공용 `postgres` fixture)에 `inv.tenants`+`inv.nodes`/`node_channels`/`node_resource_snapshots` 5행(겸임 1: hostId=controlPlaneHostId, eligibility false/false, `cp-host-colocation`; 독립 4)을 시드하고 stale report(`timedWaveReady:true`)를 둔 뒤 `write_registration_mtls_preflight` 1회 → **1 passed / 8.6s**: before/after `count·max(heartbeat_at)` 동일(읽기 전용), report·파일에 `tenantId`·tenant 값·DSN 없음, `databaseReadOnly`·`dryRun` true, ready 5·cpColocated 1·cpIndependent 4·timedWaveSelected 4·`timedWaveReady` true, stale 파일이 현재 관측으로 교체. 잔존 DB 0, 임시 파일 삭제, porcelain 0.

## 4. (3) F-D · F-E · CE-4

- **F-D**: 사양 §7·측정기 v1.3·lane v1.7 세 곳에 "19/20 = 시연 임계 통과·점추정 0.95·양측 95% Clopper-Pearson 하한 약 0.751 병기·통계 보장 아님" ✔ (하한 값 검산: 19/20 양측 95% CP 하한 ≈ 0.7513 ✔).
- **F-E**: 이탈 = inventory 고정 대상 container `docker stop --time <bounded>`(SIGTERM·강제 종료 여부 기록·volume/journal/키/인증서/state 보존), `rm`/prune/host reboot/키·채널 교체/임의 network kill 금지, 복원 = 같은 container `docker start` + 동일 nodeId·fingerprint·epoch/channel·heartbeat/snapshot·baseline 재확인, 실패에도 JSON/JUnit 보존·소유 container만 — 카드 29 요청과 일치 ✔.
- **CE-4**: future `--allow-four-node-pilot`(기본 false), 겸임 cordon/disabled + 독립 Ubuntu 4대 전부 등록·ready·eligible일 때만 `pilotWaveReady=true`, 이때도 `topologyMode=four-node-pilot`·`topologyReady=false`·`recoveryWaveReady=false`·`fiveNodeAcceptanceEligible=false` 보존, 4대 미만이면 시작 금지 — ADR-100 되돌리기와 정합, 5노드 인수 오인 방지 ✔.

## 5. (4) 게이트 (de8a9b7d 정확 트리)

`check_docs` **884** · `check_contract_bindings` 54/19/14 · `check_response_freshness` · `check_doc_single_source --ratchet` 18 · `check_ontology` · `check_frontend_integrity` 9/0 · `export_schemas --check` 58/58 · `git diff --check 9e3827ac de8a9b7d` — 전부 exit 0. 커널·계약·`src/`·workflow diff 0.

## 6. 관찰(비차단)

- **O-1(코디네이터 요청 반영)**: helper의 DB 경로는 PG-free에서 `connect` double로만 덮이고 이 PR에 postgres 마커 시험이 없다. 위 §3 검토자 임시 시험과 동등한 **영구 시험**(`pytest.mark.postgres`, PG-free 환경 안전 skip)을 후속으로 추가해 helper가 double로만 검증되지 않게 할 것.
- **O-2**: observation.py:146의 60초는 하드코드다. 사양 §7 "감지 ≤60초+poll"의 60초가 이 상수를 뜻함을 커널 recovery adapter 카드에서 명시(변경 시 AC-07 문구와 함께).

## 판정
**승인** — F-A 결정이 네 커널 모듈의 코드로 성립하고 core 경로를 합성 proxy로 정직하게 분리했으며, helper 추출은 tenantId 제거 외 이동 코드가 동일하고 재수출·stale 선삭제·경로 거부가 시험으로 고정되고, PG-free 15 passed·정적 되살림 KILLED·읽기 전용 실 PG 1 passed, F-B/F-C/F-D/F-E/CE-4 반영이 정확하며 게이트 전부 0. PR #110 merge 가능. 물리 wave·S07 커널 adapter 구현·AC-07 판정은 이 PR의 주장이 아니다.
