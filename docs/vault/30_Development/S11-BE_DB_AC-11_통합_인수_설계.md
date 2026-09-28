---
doc_id: "DESIGN-S11-AC11-ACCEPTANCE-001"
title: "S11-BE·S11-DB AC-11 통합 인수 설계"
version: "1.2.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-29T00:08:48+09:00"
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
| `sourceRunId`, `sourceHeadSha`, `checkoutTreeSha`, `artifactSha256` | GitHub run과 실제 PR head/commit에 도달해야 한다. `checkoutTreeSha == sourceHeadSha^{tree}`여야 하고 merge ref checkout은 거부한다. |
| `cleanCheckout` | `true`만 허용한다. `git status --porcelain`이 비었음을 producer가 기록하고 aggregator가 workflow log와 함께 확인한다. |
| `environment` | hosted runner 이미지, PostgreSQL 버전·설정, topology, 실제/합성 여부를 분리한다. |
| `startedAt`, `finishedAt` | UTC RFC 3339. 종료가 시작보다 앞서면 `INVALID_RUN`이다. |
| `observations` | 값, 단위, 표본 수, 성공/실패/skip 분모, SQLSTATE 또는 오류 분류를 함께 기록한다. |
| `targetRef` | 목표 문서의 commit·path·blob SHA를 기록한다. target commit은 `sourceHeadSha`의 조상이고, 측정 tree의 같은 path blob이 target blob과 동일해야 한다. 없으면 `NOT_REGISTERED`다. |
| `verdict` | 닫힌 enum `MEASURED_PASS`, `MEASURED_FAIL`, `NOT_OBSERVED`, `BLOCKED_EXTERNAL`, `NOT_APPLICABLE`, `NOT_REGISTERED`, `INVALID_RUN` 중 하나다. 모르는 문자열은 `INVALID_RUN`이다. |
| `cleanup` | disposable resource 이름·소유 label·정리 결과·잔존 수를 기록한다. 잔존이 있으면 FAIL이다. |

상위 집계기는 producer의 `verdict`를 신뢰하지 않고 observation·targetRef·분모로 다시 계산한다. `MEASURED_PASS`인데 관측값이 비었거나 `n=0`이거나 목표를 위반하면 `INVALID_RUN`이다. `skip`, `NOT_OBSERVED`, `BLOCKED_EXTERNAL`, `NOT_APPLICABLE`, `NOT_REGISTERED`는 PASS가 아니다. 필수 필드나 필수 축 누락, artifact hash 불일치, source SHA/tree 도달 불가, 다른 환경 수치 합산, 실패가 있는데 오류 합계가 맞지 않는 보고서도 `INVALID_RUN`이다. `MEASURED_NO_TARGET`과 일반 문자열 `PASS`는 허용하지 않는다.

## 2. migration forward→rollback→forward 리허설

### 2.1 실행 범위

실행기는 `tools/migration_graph.py`가 산출한 단일 head와 각 revision의 가역성을 먼저 고정한다. 현재 integration 기준 head는 `0046_model_manifest_readiness`이고 이 revision 자체가 비가역이므로 safe downgrade target도 같은 `0046_model_manifest_readiness`다. 따라서 현재 backend workflow의 “reversible tail”은 **0개**다. 이 상태에서 `target == head`를 rollback PASS로 세지 않고 `NOT_APPLICABLE(no reversible tail)`로 낸다.

두 hosted matrix를 분리한다.

| matrix | 대상 | 절차 | 합격 조건 |
|---|---|---|---|
| `reversible-segment` | PR이 추가·변경한 가역 revision과 최신 비가역 revision 위의 연속 가역 tail | 각 case마다 새 DB → `down_revision`까지 upgrade → sentinel seed → 대상 revision forward → downgrade → 같은 revision forward | 세 단계 exit 0, sentinel·권한·sequence 보존, downgrade 뒤 §2.2 기준 DB catalog fingerprint 동등, 재-forward 뒤 schema·RLS·DEFINER 불변식 일치 |
| `irreversible-restore` | `check_migration_upgrade.py`의 공개 starting state → 현재 head와, PR이 추가한 비가역 revision | 각 case마다 새 DB → starting state → sentinel·fingerprint → 사전 snapshot → head forward → snapshot을 다른 새 DB에 restore → head forward | downgrade 호출 0, restore 무결성·데이터 보존·최종 head·권한/RLS/DEFINER 불변식, 두 DB 모두 정리 |

매 PR은 변경된 migration case를 필수로 실행한다. scheduled/manual opt-in은 `check_migration_upgrade.py`가 명시적으로 지원하는 curated published-prior matrix 전체를 실행한다. 이 목록은 모든 역사 revision과 같다는 뜻이 아니다. 별도 manifest에서 지원 대상으로 선언한 published prior가 matrix에서 빠지거나, matrix가 graph에 없는 revision을 포함하면 `INVALID_RUN`이며 결과를 본 뒤 prior를 삭제할 수 없다.

### 2.2 데이터 보존 단언

각 case는 migration에 맞는 fixture manifest를 사전 등록한다.

- 공통: tenant, user, project, idempotency key, audit/evidence row의 PK와 content fingerprint.
- 실행·복구: run, attempt, lease, recovery epoch, fencing 값과 참조 무결성.
- 저장·모델: object/model commitment, manifest hash, replica/retention 표식.
- 보안: table owner, role membership, GRANT/REVOKE, RLS enable/force, policy expression, SECURITY DEFINER owner/search_path/EXECUTE 대상.
- sequence와 시간: 복원 뒤 다음 값이 기존 최대값을 덮어쓰지 않고, timestamp precision·timezone이 바뀌지 않는다.

sentinel은 **forward 전과 forward 후에 각각** 넣는다. forward 후 sentinel은 downgrade가 새 열·새 객체의 데이터를 버리는지 드러내며, revision manifest는 각 sentinel을 `PRESERVED` 또는 `DECLARED_LOSS_REQUIRES_RESTORE` 중 하나로 미리 분류한다. 결과를 본 뒤 등급을 바꿀 수 없다.

`reversible`은 두 등급으로 나눈다.

| 등급 | 의미 | 현재 고정 fixture |
|---|---|---|
| `lossless-reversible` | forward 후 데이터까지 downgrade→re-forward 뒤 보존 | 일반 additive/constraint migration |
| `lossy-reversible` | 코드상 downgrade는 있으나 데이터·의미 손실 가능; SQL downgrade PASS로 release gate를 충족하지 못하고 snapshot restore가 필요 | base `0001_s02_baseline`~`0007_locality_replicas`의 `DROP TABLE ... CASCADE`, `0009_idempotency_and_inbox_scope`, `0010_canonical_resource_units`, `0025_workspace_tool_choice` |

downgrade 뒤 catalog는 단순 “추가 객체 없음”이 아니라 **새 DB를 같은 `down_revision`까지 upgrade한 기준 DB**와 fingerprint가 같아야 한다. fingerprint 범위는 table·column·constraint·index·function signature/body hash·owner·GRANT·role membership·RLS enable/force·policy expression이다. 이 비교는 `0026`/`0028`처럼 같은 함수 이름을 다루는 revision이 기존 객체를 조용히 지우는 회귀도 잡는다.

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
| `downgrade(): pass`를 가역 성공으로 분류 | `INVALID_RUN` |
| 기존 객체를 삭제했는데 “추가 객체 없음”만 확인 | catalog fingerprint 불일치로 FAIL |
| `0009`처럼 forward 후 project별 동일 key가 생긴 뒤 downgrade가 실패하거나 데이터를 접음 | `lossy-reversible`; SQL rollback PASS 금지, restore 요구 |
| sentinel 값·FK·RLS·role membership·DEFINER grant·sequence 훼손 | FAIL |
| restore는 0인데 checksum/fingerprint 불일치 | FAIL |
| 한 DB를 case 간 재사용하거나 residue 존재 | FAIL |
| JUnit은 green인데 JSON에 실패/누락이 존재 | `INVALID_RUN` |

정적 사전 검사가 `downgrade(): pass`를 먼저 `INVALID_RUN`으로 거부한다. 이 검사가 빠진 변이는 실행 단계의 기준 DB catalog fingerprint에서 다시 FAIL해야 한다. 둘 중 하나라도 없는 구현은 승인하지 않는다.

## 3. restore·PITR 증거 경계

### 3.1 재사용하는 hosted restore 증거

[PR #126](https://github.com/egparadise/SaintVision-Invion/pull/126)의 Core run [36355139230](https://github.com/egparadise/SaintVision-Invion/actions/runs/36355139230)은 owned disposable CX01 PostgreSQL의 복구 drill을 실행했다. 2026-09-28 10:51 KST 확인 시 PR은 **OPEN**이며 head는 `08ff220b6a5e13ada2268bb143ba152a29bd72bc`다. 기록값은 `cx01-recovery-tests.xml` 20 total / 18 passed / 2 skipped / 0 failed / 0 error, 전체 Core 3253 / 3236 passed / 17 skipped / 0 failed다. 두 skip은 내부망 archiver의 host 비노출이며 **복구 PASS로 승격하지 않는다**. 이 run은 disposable restore와 cleanup 증거이지 실제 운영 PITR, RPO/RTO 또는 off-device media 증거가 아니다.

새 AC-11 집계기는 #126 증거를 가져올 때 run conclusion, head, artifact digest `sha256:3b38ef2a…0262c`, 만료 `2026-10-27T22:43:03Z`, owned resource label, residue 0을 다시 검증한다. PR이 integration에 없으면 외부 candidate evidence로만 표시하고 integration release 판정에 섞지 않는다. run-specific JSON은 아직 Git에 없으므로 artifact 만료 전에 커밋되지 않으면 이후 판정은 `INVALID_RUN`이다. 현재 출처 스냅샷은 `Evidence/s11-ac11-source-baseline.json`에 고정한다.

### 3.2 VF-CL-04와 CX-09

[[VF-CL-04 replica 복구와 PITR 운영 runbook]]의 `pitr_readiness`는 설정을 `possible | absent | inconclusive`로 분류할 뿐 실제 복구를 증명하지 않는다. retention dry-run과 7일 정책도 삭제 계획의 안전성을 검증할 뿐 RPO/RTO가 아니다.

실 PITR은 [[2026-09-22_CX-09_PITR_Tier-A_활성여부_결정준비_Claude]] 결정과 사용자 제공 저장소·자격·복구 목표가 필요하다. `tools/pitr_rehearsal.sh`는 같은 호스트의 별도 cluster에서 base backup+WAL promotion을 확인하는 **메커니즘 증거**이고 운영 장애 영역·지속 archive·RPO/RTO를 증명하지 않는다. 별도 장애 영역 인스턴스에 목표 시점 복원, checksum/row fingerprint, RPO/RTO, timeline, cleanup까지 얻기 전에는 `BLOCKED_EXTERNAL(CX-09)` 또는 `NOT_OBSERVED`다.

### 3.3 restore 부정 시험

- owner label/name/cid receipt가 없는 container·DB를 삭제하거나 증거로 사용하면 FAIL.
- corrupted/truncated backup, 잘못된 role owner, 누락된 extension, `pg_restore` nonzero, fingerprint mismatch는 FAIL.
- restore 뒤 cleanup 실패·잔존 resource는 FAIL.
- readiness `possible`, archive 설정, retention 계획, logical dump만으로 PITR PASS를 내면 집계기 FAIL.
- 같은 호스트 disposable `pitr_rehearsal.sh` PASS를 운영 PITR 또는 RPO/RTO PASS로 승격하면 FAIL.
- #126의 두 archiver skip을 0 또는 pass로 보충하면 `INVALID_RUN`.

## 4. SLO 집계

### 4.1 허용 입력과 비교 경계

| 입력 | 출처·상태·확인 시각 | artifact digest·만료·Git 기준점 | 관측값과 AC-11 경계 |
|---|---|---|---|
| S05 Card46 run [36362386530](https://github.com/egparadise/SaintVision-Invion/actions/runs/36362386530), 측정 head `3a1790ff3431706e81a2ba258eb0b26ea456ed31` | PR #148 **OPEN**, 2026-09-28 10:51 KST | `sha256:44be1e7a…2a10`, `2026-10-12T00:30:21Z`; #151 candidate blob `ff6af431…b374` | legacy 20/35/50 P95 411.382/705.026/990.625ms, timeout 0. #115 제품 tree의 hosted 합성-node 참고값이며 integration/물리 5노드 AC-05 판정값이 아니다. |
| S05 clean-base run [36363327477](https://github.com/egparadise/SaintVision-Invion/actions/runs/36363327477), 측정 head `0892f8e84441d76e2313e2136b003e012f7c2ae1` | PR #151 **OPEN**, 2026-09-28 10:51 KST | `sha256:e4994e4e…767`, `2026-10-12T00:46:10Z`; #151 candidate blob `904b9030…517d` | 20/35/50 P95 665.154/1109.917/1558.406ms, timeout 0, c50 여유 441.594ms. clean-base 호환 1회이며 canonical decision이나 AC-05 판정을 대체하지 않는다. |
| CX01 run [36355139230](https://github.com/egparadise/SaintVision-Invion/actions/runs/36355139230) | PR #126 **OPEN**, 2026-09-28 10:51 KST | `sha256:3b38ef2a…0262c`, `2026-10-27T22:43:03Z`; run-specific committed JSON 없음 | 18 pass / 2 honest skip, cleanup success. disposable restore 메커니즘이며 실제 PITR·장시간·5노드 지표가 아니다. |
| VF-CL-04 readiness·retention | Git 문서·도구, candidate | 설정 분류와 dry-run | 운영 준비 관측. 복구 SLO가 아니다. |

집계기는 `comparableGroup`이 같은 수치만 median/percentile로 합친다. 제품 tree, runner, PostgreSQL 설정, topology, 관측자 유무가 다르면 별도 행이다. 기존 evidence의 목표가 사전 등록되지 않았으면 `NOT_REGISTERED`로 보고하고, 결과를 본 뒤 목표를 정해 과거 run을 PASS로 만들지 않는다. 위 artifact metadata의 오래 남는 기준점은 `Evidence/s11-ac11-source-baseline.json`이다. 단, OPEN PR의 blob은 integration 증거가 아니며 CX01 run-specific JSON 부재도 그대로 gap이다.

#126·#148·#151의 기존 schema에는 `checkoutTreeSha`·`cleanCheckout`이 없고 #126은 merge ref checkout이었다. 따라서 세 run은 모두 **참고 전용**이며 AC-11 PASS 분자에 들어가지 않는다. 새 schema로 sourceHead tree·clean checkout을 다시 증명한 run만 판정 입력이 된다.

### 4.2 사전 등록된 목표와 신규 목표 규칙

이미 측정보다 앞서 Git에 등록된 목표는 아래와 같다. 둘 다 commit `d74e82ec5d0dda0b9f379e56fea2aad2a9b714f3`(2026-09-09)의 blob을 `targetRef`로 쓴다.

| metric | targetRef | 목표 | 이 설계의 판정 |
|---|---|---|---|
| AC-05 50동시 배치 | `docs/vault/30_Development/Sprints/S05 자원 배치.md` at `d74e82ec` | 초과 예약 0, all-request P95 ≤ 2초 | hosted 합성-node rung은 **참고값**이다. 물리 5노드·정본 topology가 아니므로 목표와 숫자 비교는 보고하되 AC-05 PASS로 세지 않는다. |
| 복구 RPO/RTO·보존 | `docs/vault/30_Development/DB 최종 개발 계획.md` at `d74e82ec` | RPO ≤15분, RTO ≤1시간, 35일 보존, 매주 restore smoke | 실제 별도 장애 영역 복구와 운영 archive·주간 반복 증거가 없으므로 `NOT_OBSERVED`/`BLOCKED_EXTERNAL`; readiness·same-host rehearsal로 PASS 금지. |

VF-CL-04 파일럿 retention 기본값 **7일**과 정본 DB 계획의 **35일**은 불일치다. 7일 dry-run은 운영 35일 목표의 합격 증거가 아니며, 운영 결정이 35일을 바꾸려면 새 목표 문서를 **측정 전에** merge해야 한다. 그 전까지 보존 축은 미충족이다.

그 밖의 신규 목표는 target 문서를 먼저 merge하고 나서만 측정한다. commit timestamp가 빠른지만 보지 않고 targetRef가 sourceHeadSha의 조상이며 source tree의 해당 blob과 동일한지 확인한다.

| metric | 집계 | 현재 상태 |
|---|---|---|
| migration case 성공률·총시간 | case별 성공/실패와 p50/p95 | 신규 목표 merge 전 `NOT_REGISTERED` |
| 장시간 오류율·resource drift | 고정 시간 window의 요청/실패/누수 | `NOT_OBSERVED` |
| 장애 감지·복구 성공률 | 반복 횟수·분모·감지/복구 분포 | 5노드 `NOT_OBSERVED` |
| critical/high 미완화 | allowlist v0 + dependency/SAST v1 finding ID와 disposition | 네 report 전부 결속 전 `NOT_OBSERVED` |
| 접근성 | 동일 release SHA의 자동+수동 기준별 결과 | 동일 SHA evidence 전 `NOT_OBSERVED` |

`critical/high 미완화 0`은 보고서가 없다는 뜻이 아니다. allowlisted scanner와 threat scenario가 전부 실행되고, 각 finding이 fixed/accepted-with-expiry/false-positive-with-proof 중 하나이며 만료된 예외가 0일 때만 0이다. 미실행 도구나 누락된 report는 `NOT_OBSERVED`다.

### 4.3 security allowlist v0

dependency/static scanner는 opt-in hosted lane의 `pip-audit 2.10.1`과 `bandit 1.9.4` 두 개를 등록한다. 등록 자체는 측정이 아니며, exact source head에서 네 report가 모두 결속되기 전 판정은 계속 `NOT_OBSERVED`다. 아래 repo-native 보안 evidence도 “scanner 전체”로 부풀리지 않고 각 threat ID 범위만 덮는다.

| threat ID | 도구·고정 버전(blob) | 범위 | severity 규칙 |
|---|---|---|---|
| `SEC-DEF-001` | `tools/check_definer_functions.py` `5831f8d8…3952` + `definer-policy.json` `c1581f1f…70e` | SECURITY DEFINER owner/search_path/EXECUTE 정책 drift | 미등록 definer·PUBLIC EXECUTE·비고정 search_path = high |
| `SEC-RLS-001` | `tools/collect_rls_evidence.py` `329da31a…932` + `rls-boundary-baseline.json` `698a5b55…404` | tenant isolation·RLS boundary evidence | reachable cross-tenant read/write 또는 fail-open provenance = critical; 미측정 = NOT_OBSERVED |
| `SEC-VF-001` | `Evidence/s11-security-allowlist-v0.json`이 runner/workflow/test 3파일 blob과 required node ID 5개를 고정 | 승인 중복·회수, catalogue owner scope, current permission, login/approval/logout 경계 | policy bypass/credential disclosure = critical, 다른 강제 경계 회귀 = high |
| `SEC-SCAN-001` | `pip-audit 2.10.1` + `bandit 1.9.4`; `Evidence/s11-security-dependency-sast-allowlist-v1.json`이 producer/workflow blob·scope·severity policy를 고정 | `requirements-core.txt` 의존성 취약점, `services/control-plane/src`·`src/saintvision` Python SAST | pip-audit finding은 안정 severity 부재 때문에 전부 high로 보수 분류, Bandit HIGH만 high; allowlist 밖 1건 이상 = `MEASURED_FAIL` |

`SEC-VF-001`의 정본 invocation은 `tools/run_vf_security_tests.py tests/integration/test_desktop_browser.py tests/integration/test_approval_browser.py tests/integration/test_studio_browser.py`이고, workflow가 요구하는 node ID 집합이 manifest와 exact match해야 한다. argv로 다른 파일을 넘기거나 node ID가 빠지면 `INVALID_RUN`이다.

`rls-boundary-baseline.json`의 기존 accepted 3건은 manifest에서 측정 전에 disposition을 정한다. `inv_app/public.tenants` E2~E5는 cross-tenant registry 관찰이 남아 있어 `accepted-with-expiry(2026-10-31T23:59:59+09:00)`, discovery issuer의 tenant-id-only grant와 NOLOGIN budget guard는 migration/grant proof가 있는 `false-positive-with-proof`다. baseline 항목이 manifest와 exact match하지 않거나 expiry가 지나면 각각 `INVALID_RUN` 또는 `MEASURED_FAIL`이다.

#### 도구 결과 → severity/verdict 매핑

| 도구 결과 | severity | AC-11 verdict |
|---|---|---|
| definer `unrecognized_privileged_function`, `runtime_role_bypasses_rls`, `runtime_can_create_in_trusted_schema`, `runtime_can_assume_function_owner` | critical | `MEASURED_FAIL` |
| definer `definition_differs_from_policy`, `execute_grants_differ_from_policy`, `expected_privileged_function_missing` | high | `MEASURED_FAIL` |
| definer `migration_revision_mismatch` | provenance 불일치 | `INVALID_RUN` |
| definer `runtime_role_missing` | 관측 분모 불완전 | `NOT_OBSERVED` |
| definer exit 0 / 1 / 2 | tool-scope pass / 위 problem별 판정 / 관측 불가 | `MEASURED_PASS` / 위 표 / `NOT_OBSERVED` |
| RLS E1(role SUPERUSER/BYPASSRLS), E2(RLS enable+force), E3(unset 노출), E4(cross-tenant/identity mismatch), E5(unknown-tenant 노출), E6(PUBLIC definer EXECUTE) | critical | baseline disposition으로 제거되지 않은 1건이라도 `MEASURED_FAIL` |
| RLS exit 0 / 1 / 2 / 3 | tool-scope pass / 위반 / 관측 불가 / identity unmeasured | `MEASURED_PASS` / `MEASURED_FAIL` / `NOT_OBSERVED` / `NOT_OBSERVED` |
| pip-audit vulnerability 1건 이상 | high(보수 분류) | exact finding ID가 사유·만료와 함께 allowlist에 없으면 `MEASURED_FAIL` |
| Bandit HIGH 1건 이상 | high | exact `test_id:path:line` finding ID가 사유·만료와 함께 allowlist에 없으면 `MEASURED_FAIL` |
| `SEC-SCAN-001` report 누락·scanner exit 2+·payload SHA 불일치 | 관측 불완전 | `NOT_OBSERVED` |
| scanner 버전·scope Git object·producer/workflow blob drift | provenance 불일치 | `INVALID_RUN` |

도구·blob·범위·severity mapping·threat ID 중 하나라도 문서 갱신 없이 바뀌면 `INVALID_RUN`이다. allowlist 도구 report 누락은 `NOT_OBSERVED`, accepted-with-expiry가 만료되면 `MEASURED_FAIL`이다. `SEC-SCAN-001`은 이 v1.2 표와 고정 allowlist가 merge된 source head에서만 분모에 들어간다. `check_definer_functions.py`에는 검토에서 열거한 8개 외에도 실제 code `expected_privileged_function_missing`이 있으므로 위 표가 함께 fail-closed로 포함한다.

### 4.4 SLO 부정 시험

- target 문서 commit이 run보다 늦음, targetRef 누락, 결과를 보고 임계치 변경 → `INVALID_RUN`.
- P95 all을 P95 success로 바꾸거나 timeout을 분모에서 제거 → FAIL.
- 다른 제품 tree·topology·observer 결과 합산 → `INVALID_RUN`.
- `errorsBySqlState` 합계와 failure count 불일치, unknown failure 누락 → `INVALID_RUN`.
- security report 누락을 critical/high 0으로 변환 → FAIL.
- allowlist 도구 report 누락 → `NOT_OBSERVED`; 문서 변경 없는 도구/blob 교체 → `INVALID_RUN`; 만료된 accepted-with-expiry → `MEASURED_FAIL`.
- producer가 관측값 없음·`n=0`·목표 위반인데 `MEASURED_PASS` 제출 → 집계기 재계산으로 `INVALID_RUN`.
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

hosted 결과에는 runner 사양과 “로컬/물리 5노드와 직접 비교 불가”를 기록한다. GitHub-hosted job의 6시간 상한을 넘는 soak는 hosted 가능 범위가 아니라 외부 자원 범위다. ADR-100에 따른 CP와 같은 호스트의 Node는 timed S05/S07 분모에서 제외하고 별도 smoke/상관 장애로 표시한다. 접근성/E2E producer는 S11-FE(owner Gemini)이며, 동일 release SHA·artifact를 이 집계기에 인계한다.

## 6. 실행 순서와 release gate

1. **설계 승인:** 이 문서의 evidence schema, 가역/비가역 경계, SLO target 사전 등록 규칙을 Claude가 검토한다.
2. **구현 카드 분리:** migration runner, evidence aggregator, security/accessibility importer를 별도 PR로 만든다. 공개 계약과 기존 migration은 바꾸지 않는다.
3. **hosted canary:** 한 가역 fixture와 한 비가역 restore fixture로 fail-closed 부정 시험을 먼저 실행한다.
4. **hosted 전체:** published prior matrix, CX01 restore, allowlisted security/E2E evidence를 같은 release manifest에 수집한다.
5. **물리/외부:** CX-09 실제 PITR, 5노드 부하·복구, 장시간 soak와 사용자 접근성 인수를 별도 실행한다.
6. **최종 판정:** 아래 필수 축은 모두 집계기가 재계산한 `MEASURED_PASS`여야 AC-11이 `done`이다. 알려진 critical/high 미완화가 1건 이상이면 즉시 FAIL이다. 차단 verdict를 나열하는 방식은 쓰지 않는다.

필수 축은 `(1) migration reversible-segment, (2) irreversible restore/forward, (3) actual PITR·RPO/RTO·retention, (4) physical 5-node AC-05 placement load SLO, (5) physical 5-node failure detection/recovery SLO, (6) long soak, (7) security critical/high zero, (8) accessibility/E2E`다. hosted synthetic load는 별도 참고행이며 필수 PASS 축이 아니다. 축 누락은 `INVALID_RUN`이다.

유일한 구조 예외는 `reversible-segment`다. `sourceHeadSha`의 graph가 reversible tail 0을 증명한 경우에만 미리 선언한 `NOT_APPLICABLE(no reversible tail)`을 허용하고, 짝인 `irreversible restore/forward`가 `MEASURED_PASS`여야 한다. 이때 reversible 축은 필수 집합에서 조건부 제외될 뿐 PASS 분자에 들어가지 않는다. 다른 축의 `NOT_APPLICABLE`, 모든 축의 `NOT_APPLICABLE`, `NOT_REGISTERED`, `NOT_OBSERVED`, `BLOCKED_EXTERNAL`, `MEASURED_FAIL`, `INVALID_RUN`은 모두 `done`을 막는다.

집계기 부정 시험은 최소 세 건을 고정한다: 모든 축 `NOT_APPLICABLE` → not done, verdict 문자열 `"PASS"` → `INVALID_RUN`, 필수 축 하나 누락 → `INVALID_RUN` + not done.

### release manifest 최소 결과

| 축 | 현재 상태 |
|---|---|
| migration forward/rollback/forward | 설계만 존재; current reversible tail 0, 조건부 `NOT_APPLICABLE`이지만 짝인 restore PASS 전에는 gate 미충족 |
| irreversible restore/forward | 설계만 존재; #126은 후보 restore 증거, integration 판정 미수행 |
| actual PITR | `BLOCKED_EXTERNAL(CX-09)` |
| hosted synthetic load (non-gate reference) | 기존 참고 수치 존재; PASS 분자·물리 5노드 AC-05 판정 아님 |
| physical 5-node AC-05 placement load | `NOT_OBSERVED` |
| physical 5-node failure detection/recovery | `NOT_OBSERVED` |
| long soak | `NOT_OBSERVED` |
| security critical/high zero | 완전한 allowlisted report 전 `NOT_OBSERVED` |
| accessibility/E2E | 동일 release SHA 통합 전 `NOT_OBSERVED` |

따라서 현시점 AC-11 판정은 **미완료**다. 다음 구현 카드는 이 표를 자동 생성하되 미측정 값을 보충하지 않아야 한다.

## 7. 롤백

이 PR은 문서만 변경하므로 되돌리기는 문서 commit revert다. 후속 runner는 opt-in workflow/job으로 추가하고 기본 CI를 바꾸지 않는다. runner 결함 시 workflow와 도구만 제거하며 migration·제품 데이터·계약을 건드리지 않는다. 실행 중 disposable resource는 소유 label과 receipt가 모두 맞을 때만 정리한다.
