---
doc_id: "DESIGN-S11-AC11-ACCEPTANCE-001"
title: "S11-BE·S11-DB AC-11 통합 인수 설계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T10:16:34+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tasks: ["S11-BE", "S11-DB"]
acceptance: ["AC-11"]
tags: ["s11", "acceptance", "migration", "rollback", "restore", "slo", "fail-closed"]
---

# S11-BE·S11-DB AC-11 통합 인수 설계

## 0. 결정과 현재 판정

이 문서는 AC-11의 `주요 SLO와 실제값 보고, critical/high 미완화 0, rollback 검증`을 **어떤 증거로 판정할지** 고정한다. 구현·실행·registry 상태 변경은 하지 않는다. 현재 `S11-BE`, `S11-DB`, `AC-11`은 모두 `planned`이며 이 설계만으로 `review` 또는 `done`으로 바꾸지 않는다.

판정 원칙은 다음과 같다.

1. 가역 migration만 실제 `forward → downgrade → forward`를 수행한다.
2. 비가역 migration은 downgrade를 가장하지 않고 `forward → 검증된 사전 스냅샷 복원 → forward`로 검증한다.
3. 실제 PITR, 5노드, 장시간 실장비 결과가 없으면 `NOT_OBSERVED` 또는 `BLOCKED_EXTERNAL`이다. readiness, 설정, 합성 노드, disposable container 결과로 대체하지 않는다.
4. SLO 목표는 측정 artifact를 보기 전에 Git에 고정한다. 사전 등록이 없는 관측값은 수치로 보고하되 합격 판정에는 쓰지 않는다.
5. 누락·불일치·도달 불가·잘못된 SHA를 0 또는 PASS로 보충하지 않는다.

## 1. 증거 봉투와 공통 판정

모든 lane은 다음 필드를 가진 JSON과 JUnit을 같은 artifact에 낸다.

| 필드 | 규칙 |
|---|---|
| `schemaVersion`, `runPurpose` | 알려진 버전·목적만 허용한다. |
| `sourceRunId`, `sourceHeadSha`, `artifactSha256` | GitHub run과 실제 PR head/commit에 도달해야 한다. merge SHA와 dirty tree는 거부한다. |
| `environment` | hosted runner 이미지, PostgreSQL 버전·설정, topology, 실제/합성 여부를 분리한다. |
| `startedAt`, `finishedAt` | UTC RFC 3339. 종료가 시작보다 앞서면 `INVALID_RUN`이다. |
| `observations` | 값, 단위, 표본 수, 성공/실패/skip 분모, SQLSTATE 또는 오류 분류를 함께 기록한다. |
| `targetRef` | 목표가 적힌 문서 SHA와 그 SHA의 run 이전성을 기록한다. 없으면 `NOT_REGISTERED`다. |
| `verdict` | `MEASURED_PASS`, `MEASURED_FAIL`, `NOT_OBSERVED`, `BLOCKED_EXTERNAL`, `NOT_APPLICABLE`, `INVALID_RUN` 중 하나다. |
| `cleanup` | disposable resource 이름·소유 label·정리 결과·잔존 수를 기록한다. 잔존이 있으면 FAIL이다. |

상위 집계기는 `MEASURED_PASS`만 합격 분자에 넣는다. `skip`, `NOT_OBSERVED`, `BLOCKED_EXTERNAL`, `NOT_APPLICABLE`은 PASS가 아니다. 필수 필드 누락, artifact hash 불일치, source SHA 도달 불가, 다른 환경의 수치 합산, 실패가 있는데 오류 합계가 맞지 않는 보고서는 `INVALID_RUN`이다.

## 2. migration forward→rollback→forward 리허설

### 2.1 실행 범위

실행기는 `tools/migration_graph.py`가 산출한 단일 head와 각 revision의 가역성을 먼저 고정한다. 현재 integration 기준 head는 `0046_model_manifest_readiness`이고 이 revision 자체가 비가역이므로 safe downgrade target도 같은 `0046_model_manifest_readiness`다. 따라서 현재 backend workflow의 “reversible tail”은 **0개**다. 이 상태에서 `target == head`를 rollback PASS로 세지 않고 `NOT_APPLICABLE(no reversible tail)`로 낸다.

두 hosted matrix를 분리한다.

| matrix | 대상 | 절차 | 합격 조건 |
|---|---|---|---|
| `reversible-segment` | PR이 추가·변경한 가역 revision과 최신 비가역 revision 위의 연속 가역 tail | 각 case마다 새 DB → `down_revision`까지 upgrade → sentinel seed → 대상 revision forward → downgrade → 같은 revision forward | 세 단계 exit 0, sentinel·권한·sequence 보존, downgrade 뒤 추가 객체 소거, 재-forward 뒤 schema·RLS·DEFINER 불변식 일치 |
| `irreversible-restore` | `check_migration_upgrade.py`의 공개 starting state → 현재 head와, PR이 추가한 비가역 revision | 각 case마다 새 DB → starting state → sentinel·fingerprint → 사전 snapshot → head forward → snapshot을 다른 새 DB에 restore → head forward | downgrade 호출 0, restore 무결성·데이터 보존·최종 head·권한/RLS/DEFINER 불변식, 두 DB 모두 정리 |

매 PR은 변경된 migration case를 필수로 실행한다. scheduled/manual opt-in은 `check_migration_upgrade.py`가 명시적으로 지원하는 curated published-prior matrix 전체를 실행한다. 이 목록은 모든 역사 revision과 같다는 뜻이 아니다. 별도 manifest에서 지원 대상으로 선언한 published prior가 matrix에서 빠지거나, matrix가 graph에 없는 revision을 포함하면 `INVALID_RUN`이며 결과를 본 뒤 prior를 삭제할 수 없다.

### 2.2 데이터 보존 단언

각 case는 migration에 맞는 fixture manifest를 사전 등록한다.

- 공통: tenant, user, project, idempotency key, audit/evidence row의 PK와 content fingerprint.
- 실행·복구: run, attempt, lease, recovery epoch, fencing 값과 참조 무결성.
- 저장·모델: object/model commitment, manifest hash, replica/retention 표식.
- 보안: table owner, role membership, GRANT/REVOKE, RLS enable/force, policy expression, SECURITY DEFINER owner/search_path/EXECUTE 대상.
- sequence와 시간: 복원 뒤 다음 값이 기존 최대값을 덮어쓰지 않고, timestamp precision·timezone이 바뀌지 않는다.

fixture가 revision에 존재하지 않는 열을 요구하거나 owner-only trigger 우회로 운영상 불가능한 orphan을 만들면 실행기는 시작 전에 거부한다. fingerprint 비교는 row count만 보지 않고 key와 canonical JSON/hash를 함께 비교한다.

### 2.3 현재 비가역 inventory와 처리

2026-09-28 integration snapshot에서 `migration_graph.py`가 비가역으로 분류한 revision은 아래와 같다. 정본은 도구 출력이며 예상하지 않은 추가·삭제·복구 문구 소실은 review를 요구하는 `INVALID_RUN`이다.

- `0001_core`, `0002_approvals`, `0003_tool_claims`, `0004_node_receipts`, `0005_node_channels`, `0006_control_api`
- `0007_delivery_queue`, `0008_storage`, `0009_node_snapshots`, `0010_shards`, `0011_results`, `0012_workspace_restore`, `0013_placement_limits`, `0014_reservation_aborts`, `0015_output_ingestions`, `0016_shard_parents`, `0017_workspace_checkouts`, `0018_workspace_resume`, `0019_workspace_api_integration`
- `0020_shard_recovery`, `0021_business_kernel`, `0022_node_containment`, `0023_containment_approvals`, `0024_workspace_bridge`, `0025_workspace_start`, `0026_business_start_merge`, `0027_business_api_guards`, `0028_result_readiness_merge`
- `0030_provisioning_integrity`, `0031_resource_offer_integrity`, `0032_workspace_readiness_merge`, `0033_workspace_bridge_merge`, `0034_terminal_frame_intents`, `0035_credential_registry`, `0036_recovery_target_outcome`, `0037_storage_sample_commit`, `0038_approval_review_snapshot`, `0039_model_manifest`
- `0040_model_run_input`, `0041_model_runtime_input`, `0042_model_retry_lineage`, `0043_replica_retention`, `0044_model_registry_binding`, `0045_discovery_machine_cred`, `0046_model_manifest_readiness`

이 inventory는 SQL downgrade 대상이 아니다. verified snapshot restore와 reviewed forward-fix만 허용한다. 비가역 revision의 `downgrade()`가 성공하거나 recovery note가 사라지는 변이는 FAIL이다.

### 2.4 migration 부정 시험

| 변이 | 기대 판정 |
|---|---|
| branch/cycle/multiple head, 알 수 없는 prior, manifest와 graph 불일치 | `INVALID_RUN` |
| `target == head`를 rollback 성공으로 집계 | 집계기 FAIL |
| 비가역 revision에 downgrade 실행 또는 조용한 schema drop | FAIL |
| sentinel 값·FK·RLS·role membership·DEFINER grant·sequence 훼손 | FAIL |
| restore는 0인데 checksum/fingerprint 불일치 | FAIL |
| 한 DB를 case 간 재사용하거나 residue 존재 | FAIL |
| JUnit은 green인데 JSON에 실패/누락이 존재 | `INVALID_RUN` |

## 3. restore·PITR 증거 경계

### 3.1 재사용하는 hosted restore 증거

[PR #126](https://github.com/egparadise/SaintVision-Invion/pull/126)의 final-head Core run [36355139230](https://github.com/egparadise/SaintVision-Invion/actions/runs/36355139230)은 owned disposable CX01 PostgreSQL의 복구 drill을 실행했다. 기록값은 `cx01-recovery-tests.xml` 20 total / 18 passed / 2 skipped / 0 failed / 0 error, 전체 Core 3253 / 3236 passed / 17 skipped / 0 failed다. 두 skip은 내부망 archiver의 host 비노출이며 **복구 PASS로 승격하지 않는다**. 이 run은 disposable restore와 cleanup 증거이지 실제 운영 PITR, RPO/RTO 또는 off-device media 증거가 아니다.

새 AC-11 집계기는 #126 증거를 가져올 때 run conclusion, head `08ff220b6a5e13ada2268bb143ba152a29bd72bc`, artifact hash, owned resource label, residue 0을 다시 검증한다. PR이 integration에 없으면 외부 candidate evidence로만 표시하고 integration release 판정에 섞지 않는다.

### 3.2 VF-CL-04와 CX-09

[[VF-CL-04 replica 복구와 PITR 운영 runbook]]의 `pitr_readiness`는 설정을 `possible | absent | inconclusive`로 분류할 뿐 실제 복구를 증명하지 않는다. retention dry-run과 7일 정책도 삭제 계획의 안전성을 검증할 뿐 RPO/RTO가 아니다.

실 PITR은 [[2026-09-22_CX-09_PITR_Tier-A_활성여부_결정준비_Claude]] 결정과 사용자 제공 저장소·자격·복구 목표가 필요하다. base backup + WAL로 별도 인스턴스에 목표 시점 복원, checksum/row fingerprint, RPO/RTO, timeline, cleanup까지 얻기 전에는 `BLOCKED_EXTERNAL(CX-09)` 또는 `NOT_OBSERVED`다.

### 3.3 restore 부정 시험

- owner label/name/cid receipt가 없는 container·DB를 삭제하거나 증거로 사용하면 FAIL.
- corrupted/truncated backup, 잘못된 role owner, 누락된 extension, `pg_restore` nonzero, fingerprint mismatch는 FAIL.
- restore 뒤 cleanup 실패·잔존 resource는 FAIL.
- readiness `possible`, archive 설정, retention 계획, logical dump만으로 PITR PASS를 내면 집계기 FAIL.
- #126의 두 archiver skip을 0 또는 pass로 보충하면 `INVALID_RUN`.

## 4. SLO 집계

### 4.1 허용 입력과 비교 경계

| 입력 | 관측값 | AC-11에서의 용도·한계 |
|---|---|---|
| S05 Card46 canonical run [36362386530](https://github.com/egparadise/SaintVision-Invion/actions/runs/36362386530), 측정 head `3a1790ff3431706e81a2ba258eb0b26ea456ed31` | legacy 20/35/50 동시 P95 중앙 411.382 / 705.026 / 990.625ms, timeout 0 | #115 제품 tree(flag off, root-transaction lifecycle 포함)의 hosted 합성-node 결과. integration tree 또는 5노드 AC-05 수치로 쓰지 않는다. |
| S05 clean integration compatibility run [36363327477](https://github.com/egparadise/SaintVision-Invion/actions/runs/36363327477), 측정 head `0892f8e84441d76e2313e2136b003e012f7c2ae1` | 20/35/50 P95 중앙 665.154 / 1109.917 / 1558.406ms, timeout 0, c50 2초 여유 441.594ms | integration tree legacy 호환 측정 1회. canonical decision을 대체하지 않고 서로 직접 합산하지 않는다. |
| CX01 run `36355139230` | 18 pass / 2 honest skip, cleanup success | disposable restore 가용성. 실제 PITR·장시간·5노드 지표 아님. |
| VF-CL-04 readiness·retention | 설정 분류와 dry-run | 운영 준비 관측. 복구 SLO 아님. |

집계기는 `comparableGroup`이 같은 수치만 median/percentile로 합친다. 제품 tree, runner, PostgreSQL 설정, topology, 관측자 유무가 다르면 별도 행이다. 기존 evidence의 목표가 사전 등록되지 않았으면 `MEASURED_NO_TARGET` 성격의 `NOT_REGISTERED`로 보고하고, 결과를 본 뒤 목표를 정해 과거 run을 PASS로 만들지 않는다.

### 4.2 사전 등록할 주요 SLO

구현 카드에서 목표 문서 SHA를 먼저 merge한 뒤 측정한다. 다음 값은 **필드와 판정 방식의 제안**이며 숫자는 아직 승인하지 않는다.

| metric | 집계 | 사전 등록 전 상태 |
|---|---|---|
| migration case 성공률·총시간 | case별 성공/실패와 p50/p95 | `NOT_REGISTERED` |
| rollback/restore RTO, data-loss/RPO | 실제 restore/promotion 시계와 row/hash delta | CX-09 전 `NOT_OBSERVED` |
| 장시간 오류율·resource drift | 고정 시간 window의 요청/실패/누수 | `NOT_OBSERVED` |
| 배치 요청 p95·SQL timeout | topology·동시성별 all-request p95와 SQLSTATE | hosted 합성 값만 관측, 5노드 `NOT_OBSERVED` |
| 장애 감지·복구 성공률 | 반복 횟수·분모·감지/복구 분포 | 5노드 `NOT_OBSERVED` |
| critical/high 미완화 | 스캐너/침투 시나리오 finding ID와 disposition | 완전한 allowlisted report 전 `NOT_OBSERVED` |
| 접근성 | 동일 release SHA의 자동+수동 기준별 결과 | 동일 SHA evidence 전 `NOT_OBSERVED` |

`critical/high 미완화 0`은 보고서가 없다는 뜻이 아니다. allowlisted scanner와 threat scenario가 전부 실행되고, 각 finding이 fixed/accepted-with-expiry/false-positive-with-proof 중 하나이며 만료된 예외가 0일 때만 0이다. 미실행 도구나 누락된 report는 `NOT_OBSERVED`다.

### 4.3 SLO 부정 시험

- target 문서 commit이 run보다 늦음, targetRef 누락, 결과를 보고 임계치 변경 → `INVALID_RUN`.
- P95 all을 P95 success로 바꾸거나 timeout을 분모에서 제거 → FAIL.
- 다른 제품 tree·topology·observer 결과 합산 → `INVALID_RUN`.
- `errorsBySqlState` 합계와 failure count 불일치, unknown failure 누락 → `INVALID_RUN`.
- security report 누락을 critical/high 0으로 변환 → FAIL.
- failed/cancelled hosted run 또는 만료·삭제된 artifact를 재도장 → `INVALID_RUN`.

## 5. hosted 범위와 물리 자원 범위

| 항목 | hosted에서 검증 가능 | 5노드·실장비 필요 |
|---|---|---|
| migration/rollback | disposable PostgreSQL의 가역 segment, 비가역 snapshot restore, 권한/RLS/DEFINER·데이터 보존 | 운영 데이터 크기·실제 유지보수 창·스토리지 장애 |
| restore | #126 방식 disposable CX01, 손상 backup·role·cleanup 부정 시험 | 실제 backup 매체, off-device 복제, 운영 PITR, RPO/RTO |
| 부하 | 고정 runner의 합성 Node·legacy staircase·API/PG 부하 | 등록 Node 5대의 실제 capacity/locality, CP 겸임 Node 제외·표기, 네트워크/디스크 경합 |
| 장시간 | 비용·시간 상한을 사전 등록한 hosted soak, 메모리/FD/DB connection drift | 열·전원·NTP·스위치·WAN/원격 WS를 포함한 장시간 soak |
| security | 계약/RLS/role/DEFINER, dependency/static scan, fail-closed HTTP 부정 시험 | 실제 IdP·CA·mTLS, Node 격리, 네트워크 분할, 운영 비밀 회전 |
| 복구 | 합성 node/container failure와 deterministic replay | 5노드 전원 차단·디스크/네트워크 장애·late write·실 byte 재확보 |
| 접근성/E2E | 동일 SHA의 hosted browser 자동 검사 | 사용자 장비·실제 배포 URL에서 수동 키보드/스크린리더 인수 |

hosted 결과에는 runner 사양과 “로컬/물리 5노드와 직접 비교 불가”를 기록한다. ADR-100에 따른 CP와 같은 호스트의 Node는 timed S05/S07 분모에서 제외하고 별도 smoke/상관 장애로 표시한다.

## 6. 실행 순서와 release gate

1. **설계 승인:** 이 문서의 evidence schema, 가역/비가역 경계, SLO target 사전 등록 규칙을 Claude가 검토한다.
2. **구현 카드 분리:** migration runner, evidence aggregator, security/accessibility importer를 별도 PR로 만든다. 공개 계약과 기존 migration은 바꾸지 않는다.
3. **hosted canary:** 한 가역 fixture와 한 비가역 restore fixture로 fail-closed 부정 시험을 먼저 실행한다.
4. **hosted 전체:** published prior matrix, CX01 restore, allowlisted security/E2E evidence를 같은 release manifest에 수집한다.
5. **물리/외부:** CX-09 실제 PITR, 5노드 부하·복구, 장시간 soak와 사용자 접근성 인수를 별도 실행한다.
6. **최종 판정:** 필수 항목 하나라도 `NOT_OBSERVED`, `BLOCKED_EXTERNAL`, `INVALID_RUN`, `MEASURED_FAIL`이면 AC-11은 `done`이 아니다. 알려진 critical/high 미완화가 1건 이상이면 즉시 FAIL이다.

### release manifest 최소 결과

| 축 | 현재 상태 |
|---|---|
| migration forward/rollback/forward | 설계만 존재; current reversible tail 0, `NOT_APPLICABLE` |
| irreversible restore/forward | 설계만 존재; #126은 후보 restore 증거, integration 판정 미수행 |
| actual PITR | `BLOCKED_EXTERNAL(CX-09)` |
| hosted synthetic load | 기존 수치 존재, 비교군 분리 필요 |
| physical 5-node load/recovery | `NOT_OBSERVED` |
| long soak | `NOT_OBSERVED` |
| security critical/high zero | 완전한 allowlisted report 전 `NOT_OBSERVED` |
| accessibility/E2E | 동일 release SHA 통합 전 `NOT_OBSERVED` |

따라서 현시점 AC-11 판정은 **미완료**다. 다음 구현 카드는 이 표를 자동 생성하되 미측정 값을 보충하지 않아야 한다.

## 7. 롤백

이 PR은 문서만 변경하므로 되돌리기는 문서 commit revert다. 후속 runner는 opt-in workflow/job으로 추가하고 기본 CI를 바꾸지 않는다. runner 결함 시 workflow와 도구만 제거하며 migration·제품 데이터·계약을 건드리지 않는다. 실행 중 disposable resource는 소유 label과 receipt가 모두 맞을 때만 정리한다.
