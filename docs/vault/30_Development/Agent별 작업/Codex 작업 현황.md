---
doc_id: "WORKBOARD-CODEX-001"
title: "Codex 작업 현황"
version: "1.0.207"
status: "review"
author: "Codex"
updated: "2026-09-23T15:27:00+09:00"
source_of_truth: "Git"
---

# Codex 작업 현황

## 2026-09-23 S05 Card26 bounded semaphore 구현 — R2 검토 준비

- 카드 번호 `26`, branch `agent/codex/s05-bounded-semaphore`, base `1e8baf04`, owner Codex, reviewer Claude다. `S05-DB` registry를 `in_progress`로 전환했다.
- 사양 §4~§8의 canonical tenant+project process-local permit, 논리적 wait 0ms, root transaction finalizer, replay-before-permit, 기존 `RES-0007`/503/retryable 표면과 flag 기본 off를 구현했다. benchmark schema 1.8은 semaphore reject를 SQL timeout과 분리하되 외부 실패 합계에 포함한다.
- PG-free focused 시험은 응답 계약 회귀를 포함해 101 passed/exit 0이고 docs·contract bindings·ontology·single-source ratchet·frontend integrity·Black·diff 게이트도 exit 0이다. 실 PostgreSQL·20동시 wave는 실행하지 않았고 코디네이터 별도 승인 전 실행하지 않는다. R2 PR의 reviewer는 Claude다. [[S05 project별 bounded semaphore 사양]], [[2026-09-23_15-27-00_KST_S05_Card26_bounded_semaphore_구현_Codex]].

## 2026-09-23 S05 Card32 측정 provenance 보강 — 착지 요청

- Card24 local 실행 head `4c8a7363…`와 Card25 local 실행 head `6c389a1d…`가 origin integration 조상이 아님을 확인했다. 실행 위치는 evidence `executionHeadAtRun`에 보존하고 재현 anchor로는 쓰지 않는다.
- 두 실행 head와 도달 가능한 `c042b3fce80cd246ba5aeb77a6a28d2ca4cdb5ff`의 `placement.py`, `db.py`, benchmark/short-commit 시험, benchmark 도구 blob OID가 모두 같음을 확인했다. 두 evidence의 `codeSHA`를 이 reachable commit으로 보정하고 blob OID를 evidence·사양·History에 기록했다.
- 제품 코드·수치·판정은 불변이고 새 wave는 실행하지 않았다. JSON parse, docs·bindings·ontology·ratchet·frontend·diff 게이트는 모두 exit 0이며 Card32 sampler-off 재현 wave 조건은 그대로 유지한다. [[2026-09-23_15-10-00_KST_S05_Card32_provenance_보강_Codex]], [[s05-card25-sampler-off-6c389a1d.json]], [[s05-bprime-card24-4c8a7363.json]].

## 2026-09-23 S05 Card25 bounded semaphore 사양 — 착지 요청

- 옵션 B를 canonical tenant+project별 process-local non-blocking permit으로 사양화했다. 상한 초과는 기존 `RES-0007`/503/retryable이며 exact replay·changed-body 409, fencing/epoch, RLS, no-overbooking과 root transaction 종료 뒤 release를 유지한다.
- sampler-off candidate 1500×1은 20/20·timeout0, request P95 2014.409ms, hold p50/p95/max 55.469/155.873/234.974ms, DB 잔존0·기존 `inv_app_*` role 2 유지·신규 role 0이다. F-1 관측자 효과는 확인됐고 767.708ms는 observer 포함 상한이다. 보수적 max에서 N=4의 최장 469.948ms는 500ms 안, N=5는 704.922ms라 첫 실험값을 4로 정했다. permit wait budget은 0ms다.
- process P개에서 최악 `P×N`이라 전역 FIFO·multi-CP 상한은 비보장이다. legacy/candidate-B(N=4) 20동시 각 3회 계획은 semaphore reject까지 외부 실패에 포함하는 기존 3조건을 사용한다. 구현·시험·추가 부하는 미수행, flag off·S05 `review`; Claude 카드 32의 sampler-off 재현 wave 1회 조건 검토와 코디네이터 승인 대기다. [[S05 project별 bounded semaphore 사양]], [[2026-09-23_13-28-00_KST_S05_bounded_semaphore_사양_Codex]], [[s05-card25-sampler-off-6c389a1d.json]].

## 2026-09-23 S05 Card24 B′ 구현·h 교정 실험 — 착지 요청

- candidate limits `FOR UPDATE` statement에만 private budget(기본 500, 유효 1~1900ms)을 적용하고 성공 시 caller의 `current_setting('lock_timeout')` 값으로 복원한다. savepoint 실패·stale rollback, BoundDatabase 700ms 복원, 기존 `RES-0007`/503/retryable·replay·fencing·RLS·no-overbooking을 고정했으며 production flag는 off, 공개 계약·migration은 불변이다.
- SHA `4c8a7363` PG-free 15 passed, 실 PG focused 17 passed. legacy 20동시 3회는 60/60·timeout0, candidate B=1500은 11/60·`55P03`49다. 중앙 request P95(all) 1785.486→2315.099ms, 성공 request P95 2402.481ms, hold P95 141.932→767.708ms로 3조건 전부 실패했다.
- candidate depth19의 observer-on hold 767.708ms와 예상 실패17 대 실제16/16/17은 evidence 내부에서 정합하지만, sampler interval 증가와 `pg_blocking_pids` 비용 때문에 제품 h 교정값 주장은 철회했다. B′는 승격 실패로 닫고 1900 arm·50동시·5노드는 미실행, S05 `review` 유지. 다음은 B 사양과 sampler-off 대조다. [[S05 B-prime candidate limits 잠금 예산 구현 사양]], [[2026-09-23_12-20-00_KST_S05_Bprime_구현_교정실험_Codex]], [[s05-bprime-card24-4c8a7363.json]].

## 2026-09-23 Backend S05 lock-wait opt-in 수집 hotfix

- 일반 Backend pytest 수집은 `test_placement_lock_wait_diagnostic.py`를 전용 도구 환경이 없으면 fixture 생성 전에 정확한 사유 `run only through tools/placement_lock_wait_diagnostic.py`로 1건 skip한다. 전용 도구의 opt-in 실행은 불변이다.
- `backend.yml` skip 분포에 같은 사유 1건을 등록해 drift를 감시한다. R1 `41f899b3`으로 카드 24와 분리 착지했으며 일반 수집 1 skipped, check_docs 884, YAML/diff가 exit 0이다.

## 2026-09-23 S07 Card17 커널 경로·등록 mTLS helper

- 물리 AC-07은 실 heartbeat의 `inv.nodes` offline 전이와 `inv.shard_recovery`, receipt-bound output storage, `inv.shard_completion`을 잇는 커널 경로로 권고했다. core replica 하네스는 byte를 옮기지 않는 합성 개발 proxy이고 bridge는 측정을 위해 신설하지 않는다.
- #101 strict inventory와 등록/mTLS read-only preflight를 `tools/five_node_lab_preflight.py`로 동작 보존 추출했다. report `tenantId` 제거, stale JSON 선삭제, inventory/report 동일 경로 fail-closed를 추가했다. PG-free 16 passed, disposable 실 PG 1 passed(read-only·before/after 동일·정리), docs/bindings/frontend/ontology/ratchet/route/freshness 게이트가 exit 0이다.
- `19/20`은 시연 점추정 0.95와 양측 95% exact 하한 약 0.751로 보고한다. 물리 이탈은 bounded `docker stop`/동일 container `docker start`만 허용하고 rm/prune/reboot를 금지한다. `--allow-four-node-pilot`은 future opt-in이며 5노드 인수로 승격하지 않는다.
- 구현 `de8a9b7d` + 실 PG 경계시험 `58ad1cb0`, PR #110, reviewer Claude. 실제 Node·Docker·물리 wave는 미실행이고 S07-DB `review`, AC-07 미측정 유지. [[S07 5노드 실 Node adapter 사양]], [[2026-09-23_11-50-00_KST_S07_커널경로_등록mTLS_helper_Codex]].

## 2026-09-23 S07 Card23 5노드 실 Node adapter 사양

- `measure_s07_recovery.py`의 미래 `--adapter five-node-lab --inventory ... --dry-run`을 사양화했다. #101 canonical inventory/read-only DB 분류를 단일 정본으로 재사용하고 등록 Node·heartbeat/snapshot·mTLS identity·`lan-workspace-v1`을 조회만 한다.
- topology에는 CP 겸임 Node를 포함하되 disruption target은 ready·`measurementEligible.s07=true`·CP 독립 Ubuntu 4대로 제한한다. 20회 미래 계획은 4대 각 5회지만 이 카드에서 Node 중단·repair·JUnit·5노드 실행은 모두 미실행이다.
- 기존 S07 synthetic 기본 동작과 공개 계약·registry·ontology는 불변이다. S07-DB `review`, AC-07 미측정을 유지하며 구현은 Claude 검토와 코디네이터 별도 승인 뒤다. [[S07 5노드 실 Node adapter 사양]], [[2026-09-23_10-05-00_KST_S07_5노드_adapter_사양_Codex]].

## 2026-09-23 S05 Card22 B′ 구현 사양

- Card21 기전과 결정 v1.4를 바탕으로 candidate limits `FOR UPDATE` 한 statement에만 기본 500ms·실험 1500ms를 적용하고 획득 직후 공통 500ms로 복원하는 사양을 작성했다. legacy/direct lease/후속 resource lock과 production config는 바꾸지 않는다.
- 한 lock segment 1500ms 초과의 `55P03`과 같은 statement 누적 2초의 `57014`를 구분하되 공개 표면은 기존 `RES-0007`/503/retryable로 유지한다. SQLSTATE는 evidence 전용이고 계약 변경은 0이다.
- 승인 뒤 판정은 legacy/candidate 20동시 각 3회에서 외부 timeout 합계 비증가, request P95 중앙값 비악화, post-acquire hold P95 중앙값 비악화 3조건을 모두 요구한다. 현재는 docs-only이며 코드·시험·부하 미실행, flag off·S05 `review`; Claude Card24와 코디네이터 별도 승인 대기다. [[S05 B-prime candidate limits 잠금 예산 구현 사양]], [[2026-09-23_09-20-00_KST_S05_Bprime_구현사양_Codex]].

## 2026-09-23 LAN pilot CP 겸임 철회 증거·재활성 경계

- 철회 뒤 `init --allow-server-node-colocation`을 재실행해도 disabled/channel을 자동 재활성하지 않으며 private-state 편집·certificate 재등록·대체 Node 우회를 금지한다고 README에 명시했다. 재활성에는 identity 재검증·channel version CAS·audit·disabled 해제를 묶은 별도 검토 command가 필요하며 현재 미구현이다.
- 겸임 Node 없이 철회 명령을 실행하면 flag false와 빈 disabled/channel 목록만 남기는 무해한 idempotent opt-out이고 독립 Node는 불변이다. 이는 과거 겸임 identity 존재 증거가 아니다.
- final `6230b06f`의 disposable 실 PG 단일 시험은 CP channel version 1→2/enabled false, provision v1+revoke v2 audit, 독립 channel v1/enabled true, Node 2행·key/journal/cert bytes 보존을 확인해 1 passed/8.77s/exit 0이다. PG-free 47 passed와 표준 게이트도 exit 0. PR #105, reviewer Claude. [[2026-09-23_09-15-00_KST_LAN-PILOT-CP-철회증거_Codex]].
- 실 파일럿은 변경하지 않았고 Docker API 1.41·WSL Ubuntu blocker와 `review`를 유지한다.

## 2026-09-23 S05 Card21 lock-wait 기전 확인

- Claude 카드 23의 D1~D3를 반영한 opt-in 하네스를 `40b24329`에 고정하고 PostgreSQL 16 disposable DB 두 개에서 legacy 원본/FK-DROP 대조를 각각 20동시×1로 실행했다. 둘 다 단일 파일 1 passed/exit 0, DB/role 잔존 0이다.
- 원본은 20/20, depth 1, transaction acquired segment 190, tuple 0, `pgrowlocks` Key Share+For No Key Update, timeout 0. FK-DROP은 2/20, depth 19, tuple segment 최대 499.957ms, `55P03` 18로 **HYPOTHESIS_SUPPORTED**다.
- F-S05-02를 RI KEY SHARE→tuple FIFO 우회→holder xid 직접 대기→holder 교체별 lock_timeout 재시작 기전으로 승격했다. candidate limits는 선행 FK 잠금이 없어 FIFO `55P03` cascade가 난다. 정책은 B′→B 우선 v1.4 초안, A는 기전 확인용이며 구현은 Claude 카드 24 뒤 별도 결정이다.
- 20동시 초과·candidate·50동시·5노드는 실행하지 않았고 P95는 진단 부수값이라 AC-05 판정에 쓰지 않는다. flag off·S05 `review` 유지. [[2026-09-23_08-45-00_KST_S05_Card21_lock_wait_기전확인_Codex]], [[s05-lock-wait-card21-40b24329.json]].

## 2026-09-23 LAN pilot CP 겸임 관찰 보강

- O1 `revoke-server-node-colocation`은 기존 CP 겸임 identity/files/key/journal/DB row를 보존하고 private state disabled marker를 먼저 저장한 뒤 등록 channel만 monotonic revoke한다. disabled Node는 status에는 남되 bundle/enroll/source-IP serve의 active 집합에서 제외한다.
- O2는 schema-v3 script와 옛 v2 bundle 혼용을 fail closed하고 기존 Ubuntu 3대 재설치 불필요를 명시했다. O4는 loopback/WSL NAT source의 bundle/cert 요청이 HTTP 403인 정상 경계와 allowlist/portproxy 우회 금지를, O5는 API 1.45 = Engine 25+ / Docker Desktop 4.27+ `BLOCKED` 메시지를 고정했다.
- 구현 `791c7332`, focused 47 passed, py_compile/bash parse/CLI help와 docs/bindings/frontend/ontology/ratchet/freshness가 exit 0이다. 실제 CP Node·철회 실행은 미수행이며 Docker API 1.41·WSL Ubuntu 부재 blocker와 `review`를 유지한다. [[2026-09-23_08-10-00_KST_LAN-PILOT-CP-관찰보강_Codex]].
- 다음 담당은 Claude 독립 검토다. Docker prerequisite가 준비되기 전 운영 등록이나 철회를 대신 실행하지 않는다.

## 2026-09-23 5노드 물리 adapter read-only preflight

- `placement_benchmark.py`에 기존 synthetic 기본 경로를 유지한 `--adapter five-node-lab --inventory <path> --dry-run`을 추가했다. revision-fixed inventory의 node/IP/cert/profile/host/failure-domain과 ADR-100 eligibility를 strict 검증하고 PostgreSQL의 실제 heartbeat/resource snapshot/mTLS identity를 read-only transaction으로만 읽는다.
- CP 겸임 Node는 all-five smoke 후보에는 남기되 timed wave에서 사전 제외한다. 합성 row·resource 생성, heartbeat 갱신, 물리 load 실행은 0이며 공유 계약/HTTP/DB schema 변경도 없다. PG-free 12 passed와 docs/bindings/frontend/ontology/ratchet/freshness 게이트가 exit 0이다.
- 현재 파일럿 online Node 2개의 read-only dry-run은 registered 2, ready 0, all-five/timed false다. 두 Node 모두 실제 `lan-observe-v1`이라 workspace profile로 승격하지 않았고 AC-05·5노드 준비를 주장하지 않는다. 구현 `ec254775`(rebase 전과 코드 blob 동일), PR #101, reviewer Claude. [[2026-09-23_07-25-00_KST_5노드_물리_adapter_read-only_preflight_Codex]].
- 다음은 Claude 독립 검토와 코디네이터의 실제 revision-fixed inventory 재실행이다. 별도 카드 15는 LAN pilot O1/O2/O4/O5 관찰 보강 PR로 진행한다.

## 2026-09-23 PR #96 S05-FE 시나리오 매트릭스 계약 검토

- head `90991423`를 실제 pool route/service/schema, generated contract, frontend adapter/DOM, ProblemDetails와 대조해 수정 요청했다. 코멘트: <https://github.com/egparadise/SaintVision-Invion/pull/96#issuecomment-5783083226>.
- 차단: 미존재 pool 실제 409를 404로 기재, preview 후보를 `shd_*`로 합성해 Zero Fake Shards와 모순, UI `spread|binpack`과 서버 enum 불일치로 plan 201 불가, 관측 전용 편입의 server-side 거부 부재. 문서/계약·어댑터 정정을 분리했다.
- focused route/contract 검증 63 passed/exit 0. Gemini PR branch는 수정하지 않았다.

## 2026-09-23 S05 log_lock_waits 재실행 설계

- Card19의 waiter 19/depth 1/timeout 0과 Claude 카드 21의 idempotency FK→project KEY SHARE→tuple FIFO 우회 probe 가설을 연결했다. 제품 인과는 미확정이며 `log_lock_waits=on` server segment와 `pgrowlocks('inv.projects')`를 같은 legacy 20×1 wave에서 확인하는 설계다.
- 5ms sampler는 명목값(실측 약 17ms), 0.793ms arrival은 client barrier 기준(DB 첫 Lock 표본 515ms), 다른 role/DB blocker는 depth가 끊긴다는 O-a/O-b/O-c를 판정 경계에 넣었다. disposable DB session default만 쓰며 `ALTER SYSTEM`·config reload/restart·운영 DSN은 금지한다.
- 후속 옵션은 (A) limits 최종 lock까지 `FOR NO KEY UPDATE`로 낮추는 선행 약한 잠금 변형과 (B) FIFO queue 깊이 상한이다. KEY SHARE+기존 `FOR UPDATE`는 교착 가능성 때문에 제외하고, 기아·thundering herd·fail-fast 상충과 rollback을 명시했다.
- 별도 Environment 승인형 `workflow_dispatch`를 제안했지만 workflow/runner/parser는 미구현이고 실행하지 않았다. Claude의 실수 50동시 1회 수치는 사용하지 않는다. coordinator exact-SHA 승인 전 실행 금지, flag off·S05 `review`·candidate/50/5노드 미승격. [[S05 log_lock_waits opt-in 재실행 설계]], [[2026-09-23_06-15-00_KST_S05_log_lock_waits_재실행설계_Codex]].

## 2026-09-23 LAN pilot Windows CP 겸임 Node

- branch `agent/codex/lan-pilot-cp-colocated`, original base `ed200c33`, final base `4143f375`, implementation `8007ae12`, reviewer Claude. server==node 기본 거부를 유지하고 `--allow-server-node-colocation`과 protected state 승인이 함께 있을 때만 CP 겸임 identity를 추가한다.
- schema-v3 manifest·worker_config·prepare/finish·Start-Worker가 `coLocatedWithControlPlane=true`, S05/S07 false, `cp-host-colocation`을 fail closed한다. PG-free 13+30 passed, PowerShell/bash parse와 CLI help exit 0이다.
- 실제 state에는 Ubuntu identity 3개가 있고 image digest·host IP·18443 free는 확인했다. Docker Engine 20.10.22/API 1.41과 WSL Ubuntu 부재 때문에 실제 Windows 등록은 `BLOCKED`; 코디네이터가 Engine 25+/API1.45+·Ubuntu integration 뒤 수행한다. 5 Node·운영 인수·S05/S07 완료를 주장하지 않는다. [[2026-09-23_06-15-00_KST_LAN-PILOT-CP-COLOCATED_Codex_구현]].

## 2026-09-23 S05 legacy 큐 깊이 실측

- report schema 1.6에 barrier 기준 request arrival/completion과 opt-in `pg_stat_activity`/`pg_blocking_pids` queue observer를 추가했다. raw PID·SQL parameter는 보존하지 않고 공개 계약·migration은 변경하지 않았다.
- 개발 PC·합성 Node legacy 20동시 1회는 20/20 성공, timeout 0, request/acquire/hold P95 2142.809/1588.193/151.225ms, arrival spread 0.793ms였다. 98표본에서 max active 20, project-lock waiter 19, blocking chain depth 1이었다.
- `log_lock_waits=off`라 55P03 부재 원인은 미확정이다. holder 교체별 wait segment에서 timeout이 다시 시작된다는 가설만 남기고 `log_lock_waits=on` 재실행은 별도 제안으로 둔다. O2 BoundDatabase attempt1 hold 누락과 O3 legacy 운영 metric sink 부재도 유지한다. flag off·S05 `review`·50동시/5노드 미승격. [[2026-09-23_05-55-00_KST_S05_legacy_큐깊이_실측_Codex]].
- PG-free 4 passed, 실 PG 단일 파일 1 passed(20동시 wave 포함), 문서·계약·ontology·ratchet·freshness·frontend·schema·diff 게이트는 모두 exit 0이다.

## 2026-09-23 S05 5노드 lane v1.4

- ADR-100 topology B를 실행 계획에 고정했다. 등록 Node 5개 중 Windows CP 겸임 Docker Node 1개는 all-five smoke만 수행하고, S05 timed candidate와 P95 분모는 CP 독립 Ubuntu 4대만 사용한다. co-location은 inventory 선언과 host/machine identity·Docker parent 유도값을 대조하며 mismatch/unmeasured면 차단한다.
- 카드 18 결정 (b)에 따라 현재 물리 실행 권한은 inventory-bound legacy 20동시 × 3회 계획까지다. `placementShortCommit=false`, candidate와 50동시는 별도 승인 SHA 없이는 `UNAUTHORIZED/NOT_RUN`, S05-DB는 `review`를 유지한다.
- Claude 카드 20은 대칭 계측과 결정 (b)를 승인했다. holder chain별 `lock_timeout` 재적용으로 얕은 legacy 큐와 깊은 candidate limits 큐의 차이를 설명할 수 있지만, candidate 재검토 전 도착 timeline·wait_event·queue depth 실측이 필요하며 이 승인을 실행 권한으로 승격하지 않는다.
- evidence를 schema 1.5 `lockHold`·`lockAcquireWait`·mode별 wait·parameter-free `sqlDiagnostics`로 갱신했다. workflow/adapter는 미구현이고 메모리 경보에 따라 시험·빌드·브라우저·부하는 실행하지 않았다. [[2026-09-23_04-20-00_KST_S05_5노드_lane_v1_4_Codex]].

## 2026-09-23 S05 P1/P2 대칭 계측 · 결정 (b)

- legacy hold phase를 limits 획득 뒤로 옮기고 획득 client elapsed를 별도 metric으로 분리했다. SQL observer는 parameter-free statement template·phase·elapsed·SQLSTATE를 남기며 report schema는 1.5다. 공개 계약·migration 변경은 없다.
- 실 PG 20동시 각 1회: legacy 20/20·요청/hold/acquire P95 1885.489/289.365/1453.658ms, candidate 8/20·1054.907/170.766/528.705ms. candidate 실패 12건은 전부 limits `FOR UPDATE`의 `55P03`; 57014는 0건이다. real-PG 단일 파일 14 passed/exit 0, PG-free 4 passed/exit 0.
- 코디네이터 결정 (b)에 따라 legacy·flag off·S05 `review`를 유지한다. legacy acquire 1454ms에 55P03이 없는 이유는 client elapsed에 scheduling이 포함되고 server wait_event가 없어 미확정이다. 다음 후보 lock-timeout 예산/queue 깊이 상한은 Claude 카드 20 뒤 별도 결정한다. [[2026-09-23_03-45-00_KST_S05_P1_P2_대칭계측_Codex]].

## 2026-09-23 ADR-100 CP 호스트 Node 겸임

- 사용자 결정 토폴로지 B를 accepted ADR로 기록했다: Windows 물리 호스트의 Control Plane + Docker Desktop Linux Node 1개, 별도 Ubuntu Node 4개다. 등록 Node는 5개지만 CP 독립 worker host는 4개이며 registry/ontology는 바꾸지 않았다.
- S05에서는 겸임 Node를 all-five smoke에만 포함하고 20/50 동시 timed candidate·P95 분모에서 사전 제외한다. S07 기본 20회는 Ubuntu 4대에 균등 배분하고, 겸임 process loss와 CP+Node host loss는 별도 상관 장애 scenario로 분리한다.
- docs-only gate는 check_docs·contract bindings·ontology·single-source ratchet·response freshness·frontend integrity·diff check 모두 exit 0이다. 제품 시험·빌드·브라우저·부하는 실행하지 않았다. 실제 5노드 등록·inventory-bound wrapper/workflow·물리 부하/복구는 미실행·미측정이고 S05/S07은 `review` 유지, reviewer Claude. [[2026-09-23_03-10-00_KST_CP호스트_Node겸임_ADR100_Codex]].

## 2026-09-23 S05 fail-fast · F-R1/F-R2 보강

- database contention 내부 retry를 제거해 limit-row `55P03`을 기존 `RES-0007`/503/retryable로 즉시 반환한다. stale speculative decision 재계획은 유지하고 flag는 기본 off다. 공개 계약 변경 0이다.
- tight-fit active_total 재계산과 BoundDatabase 실제 `55P03` savepoint 시험을 추가했다. 실 PG 13 passed/exit 0, 두 mutation은 각각 exit 1로 KILLED이며 model-retry 회귀 1 passed/exit 0이다. flag-off는 내부 shared primitive 리팩터를 포함한 동작 동등 경로라고 문서를 정정했다.
- a60313a7 20동시×3에서 hold P95 중앙 1526.365→116.848ms, 요청 P95(all) 1817.763→922.915ms였으나 외부 timeout 2→27로 증가해 단계 3은 미통과다. flag off·S05 `review`·50/5노드 미승격을 유지하며 decision v1.3의 limit-row 입도 변경 대 legacy 유지·5노드 후 재판단을 코디네이터에게 요청한다. [[2026-09-23_02-50-00_KST_S05_fail-fast_F-R1_F-R2_Codex]].

## 2026-09-23 LAN pilot 다중 Node state·번들·등록 경계

- 기존 단일 Node private state의 top-level identity를 호환 primary로 유지하면서 `nodes[]`, 반복 `init --node-ip`, Node별 manifest/worker.zip/peer policy/certificate를 추가했다. 신규 Node ID를 side effect 전에 저장해 partial retry에서도 기존 Node·key·channel·CA·epoch를 교체하지 않는다.
- CSR CN으로 대상 Node를 선택하고 HTTP bootstrap은 source IP 허용 목록에서 그 Node의 bundle/certificate만 반환한다. hash는 HTTP로 내지 않고 별도 operator 채널로 유지하며, status/observe와 방화벽 안내는 Node별 행/IP 목록이다.
- implementation `e7a37b0a`, Ubuntu F1 hotfix `10b0fc03`: 실제 Ubuntu 24.04 Node 1대가 mTLS online·observed true다. Claude 조건 보강 `619a45db`는 secondary legacy fallback과 peer-policy node/epoch/fingerprint mismatch를 고정하고 M1 1-fail·M3 3-fail로 KILLED, 복원 10 passed다. Node 2/3 CSR·Ubuntu 4대 전체·CP 겸임 Windows Node와 최종 Claude 전환 전 `review`다. 상세: [[2026-09-23_03-16-00_KST_LAN-PILOT-MULTINODE_Codex_구현]].

## 2026-09-23 S05-DB 5노드 lane 실행 계획

- 기존 5노드 opt-in lane 정의를 v1.1로 갱신해 legacy/candidate, 20→50동시, mode별 3회, hold·limit-row wait·retry/SQLSTATE artifact와 단계별 승격 조건을 고정했다.
- node 5대·resource·NTP·CA/control cert·node cert·network·disposable PG·checkout/images·evidence root·승인/직렬화를 input/secret 이름, preflight evidence, 차단 기준으로 대조했다. 비밀 값은 기록하지 않았다.
- inventory-bound S05 adapter/workflow와 물리 실행은 미구현·미측정이며 카드 18/F-S05-03 후속 결정 전 50동시를 실행하지 않는다. registry/ontology 불변, reviewer Claude. 상세: [[2026-09-23_02-06-00_KST_S05_5노드_lane_실행계획_Codex]].

## 2026-09-23 S05 옵션 1 구현 · F-S05-03 경합 재배치

- 기본 off `placementShortCommit`으로 speculative read → 선택 Node/Resource final commit, canonical admission/prepared primitive, active fit 재계산, stale savepoint 재계획, 안전한 hold/limit-wait metric을 구현했다. 공개 응답·오류 계약은 불변이며 실 PG 불변식 10 passed와 model-retry outer transaction 1 passed/exit 0이다.
- 실 PG 20동시 legacy/candidate 각 3회 모두 20/20·exit 0이었다. hold P95 중앙값은 1399.883→122.126ms로 줄었지만 요청 P95 중앙값은 1771.763→1697.737ms(약 4.2%)에 그쳤고, 내부 timeout은 0/0/0→limit-row `55P03` 14/10/11로 늘었다.
- 단계 3 timeout 감소 조건 미충족을 F-S05-03으로 기록했다. flag off·S05-DB `review`·50동시/5노드 미실행을 유지하며, 다음은 Claude 카드 18 구현 검토 뒤 limit-row 입도/배치 갱신 또는 fail-fast 위임을 결정한다. 상세: [[2026-09-23_01-40-00_KST_S05_short-commit_구현과_F-S05-03_Codex]].

## 2026-09-23 S08-DB recovery·PITR opt-in dry-run

- 결정 B(Tier-A 유예)를 유지한 채 read-only `pitr_readiness`와 filesystem-only retention plan을 한 JSON으로 묶는 `pitr_opt_in_dry_run.py`를 `50d5ebc4`로 착지했다. 보고서는 restart/settings/compose/apply mutation과 PITR/AC-12 인수를 모두 false로 고정한다.
- 실 PG dry-run은 현재 dev 설정을 `absent`(`archive_mode=off`, `wal_level=replica`)로 관측했고 삭제 후보·DB write·compose apply 0건이다. landed SHA focused는 실 PG 포함 23 passed, compose config/docs/bindings/frontend/ontology/ratchet/freshness/route/diff/sync-check가 exit 0이다.
- 외부 volume uid70/0700→compose config→적용 후 readiness possible 3단계와 AC-12 RPO/RTO·fencing·권한 복구 드릴 초안을 문서화했다. 실제 재시작/WAL/restore/off-device/5노드는 미실행이며 S08-DB `review`를 유지하고 Claude에게 독립 검토를 인계한다. 상세: [[2026-09-23_01-38-00_KST_S08-DB_PITR-opt-in-dry-run_Codex]].

## 2026-09-23 F-S05-02 57014 원인 분리

- a1470435 실 PG disposable DB에서 runtime transaction의 `lock_timeout=500ms`, `statement_timeout=2s`, 난수 login role·tenant GUC 적용을 직접 `SHOW` 상당으로 확인했다. `Database.transaction`은 호출마다 새 connection을 열며 pool 재사용은 없다.
- project row holder 1 + waiter 1은 `wait_event_type=Lock/transactionid` 뒤 557.919ms에 `55P03 LockNotAvailable`; 비-Lock `pg_sleep(2.5)`는 `Timeout/PgSleep` 뒤 2,092.747ms에 `57014 QueryCanceled`였고 둘 다 기존 `RES-0007`/503/retryable 표면이다. 진단은 2 passed/18.33s/exit 0이다.
- 과거 20동시 57014는 statement 이름만 남고 wait-event가 없어 project row Lock으로 귀속할 수 없다. 정확한 실행 원인은 미확정이며 legacy/candidate 20동시 비교 카드에서 PID별 query/wait-event와 lock hold p95를 함께 계측한다. 제품·계약 수정과 AC-05 판정은 하지 않았다. 상세: [[2026-09-23_01-05-00_KST_F-S05-02_57014_원인분리_Codex]].

## 2026-09-22 S06-DB snapshot reader 제품 결속

- strict restore/checkout 입력·응답 계약, fixture, Python/TS/Go/node schema와 product route/composition을 구현 `a4bf2cee`로 착지했다. fresh/replay 모두 계약 anchor와 현재 `can_request`를 재검증하며 기존 resume·commitment API는 불변이다.
- 실 PG 단일 파일은 1 passed/0 skipped: 실제 object bytes read, restore replay, writable checkout, 권한 회수 replay 403, 타 project/tenant 404, 난수 `inv_app` 직접 접근 거부, tenant 미설정 `inv_kernel` 0행을 확인했다.
- 관련 56 passed/23 Windows Linux-only skip/0 failed, bindings 54 fixtures·19 types·25 sites·14 replay guards, 생성 drift 0, Go/docs/frontend/ontology/ratchet/freshness가 exit 0이다. hosted 5 run은 생성됐으나 보고 시점 진행 중이라 통과로 세지 않는다.
- 원격 WS/PTY·실 Git·CP/Node 재시작 복원은 미측정이며 S06-DB `review`와 AC-06 차단을 유지한다. 다음 담당은 Claude 독립 검토다. 상세: [[2026-09-22_23-47-00_KST_S06-DB_snapshot-reader_결속_Codex_구현]].

## 2026-09-23 F-S05-01 timeout 실측과 결정 초안 v1.1

- 단일 project lock 주입 실 PG 시험은 `55P03 LockNotAvailable`을 기존 `RES-0007`/503/retryable로 고정했고 1 passed/exit 0, Lease·idempotency 잔존 0이었다. 따라서 v1.0의 freshness→`RES-0003` 인과와 PR #74의 미매핑·계약변경 전제를 함께 정정했다.
- 개발 PC·합성 Node의 3동시 3/3×2 P95 861.651ms, 10동시 10/10×2 P95 1,738.762ms에 이어 20동시 한 라운드는 **17/20 성공, 성공 P95 2,417.912ms, 실패 3건 모두 `57014 QueryCanceled` statement timeout → `RES-0007`**이었다. 50동시·물리 5노드·20동시 peak는 미측정이다.
- 코디네이터 결정 C(조건부 보류)에 따라 옵션 1·2 구현은 시작하지 않았다. 옵션 1 v1.1은 final lock 아래 active_total/fit 재계산, stale winner 재계획, Node/Resource 병목, `leases.py:176` 중복 project lock, 네 `require_*` 순서 통일과 transaction별 lock hold p50/p95/max를 필수로 한다.
- benchmark JSON/JUnit은 요청별 지연·완료 순서·오류 status/retryable·cause·SQLSTATE·timeoutKind와 1/2 라운드 미측정 경계를 기록한다. 단위 4 passed, 단일 주입 1 passed, 20동시는 finding을 JUnit failure/exit 1로 정직 노출했다.
- PR #68 head `ef5b6587`은 E4를 ctid 또는 tenant_id+전체 PK로 고치고 불가 시 UNMEASURED/exit3으로 닫아 [승인](https://github.com/egparadise/SaintVision-Invion/pull/68#issuecomment-5778940562)했다. PR #73 head `1b21e8d1`의 evidence cleanup 라벨도 [승인 유지](https://github.com/egparadise/SaintVision-Invion/pull/73#issuecomment-5778941058)했다.
- Claude v1.1 재검토와 코디네이터 후속 A/B/C 결정 전 커널 구현·50동시 재실행·AC 판정을 하지 않는다. 상세: [[2026-09-22_S05_배치잠금_입도_결정제안_Codex]], [[2026-09-23_00-18-00_KST_S05_timeout_실측과_결정초안_v1_1_Codex]].

## 2026-09-22 S07-DB 노드 이탈·복구 반복 측정 — F-S07-03

- 실 PostgreSQL disposable DB·난수 login role에서 합성 measured-node N대 중 한 node만 heartbeat를 끊고, 생존 node는 제품 heartbeat/observation을 계속 갱신한다. 실제 lost 판정·replica stale·repair plan·15초 fresh candidate·health 경로를 R회 측정해 JSON 분포와 JUnit을 남기는 opt-in 하네스를 구현 SHA `d2471226`로 착지했다.
- 착지 SHA N=3/R=3 축약 예비값은 감지 min/p50/p95/max `1.034432/1.103582/1.112639/1.112639s`, stale 3/3, fresh target 3/3, 합성 shard proxy 3/3(1.0), JUnit exit 0이다. 이는 물리 5-node·bytes transfer·execution shard replay 판정이 아니며 `operationalAcceptanceAssessed=false`다.
- 실제 60초 경계 N=3/R=1의 `60.066591s` red는 역사 증거로 보존한다. PR #72 독립 검토 후 코디네이터 결정은 strict `< cutoff` 커널을 유지하고 AC-07 상한을 `liveness timeout + poll interval`로 정의하는 것이다. 측정기의 최대 감지 기본값도 timeout+poll이며, JSON은 하네스 wall-clock과 `codeSha`/provenance를 명시한다. fresh candidate 0은 F-S07-01 fail-closed, 물리 복구 미검증은 F-S07-02다.
- 전용 5-node lane은 물리 lab 수동 workflow에서 명시적 DSN·topology로만 opt-in 실행하고 기본 Backend/Core 수집에서는 제외한다. 합성 하네스만으로 물리 bytes transfer 판정을 하지 않는다.
- 단위 3, 관련 실 PG 회귀 14, route coverage 38, docs/bindings/frontend/ontology/ratchet/freshness가 exit 0이다. 같은 SHA hosted Docs·Frontend·Browser는 success, Core·Backend는 후속 push로 job 0 cancelled라 통과로 세지 않는다. reviewer Claude이며 self-close하지 않는다. 상세: [[2026-09-22_23-00-04_KST_S07-DB_노드이탈_복구반복측정_Codex]].

## 2026-09-22 S05-DB benchmark 교정 — F-S05-01

- exact landing `3f0fab3d`는 snapshot 계약 위반과 report TypeError가 있어 기존 78.15초/61.69초 `RES-0003` 수치를 철회했다. R1 `7569c418`로 13필드 계약+fixture validation과 summarize 호출을 교정했다.
- 실 PG에서 3동시 P95 861.651ms, 10동시 1,738.762ms, 각 두 라운드 전부 성공·오류 0·결정성/replay/fencing/no-overbooking true, disposable DB 잔존 0을 확인했다.
- 후속 20동시 실측이 현 실패를 2초 statement timeout(`57014` → `RES-0007`)으로 고정해 15초 freshness 인과를 철회했다. 50동시와 물리 5노드는 미측정이며 S05-DB는 `review`를 유지한다. 상세: [[2026-09-23_00-18-00_KST_S05_timeout_실측과_결정초안_v1_1_Codex]].

## 2026-09-22 VF-CL-02(e) node-agent wire 계약 소비 + 카드 3 M1 보강

- PR #64 조건부 승인에서 생존한 reader-scope M1을 실 PG HTTP 시험에 추가했다. kernel ready 관측 뒤 business reader scope만 폐기하면 kernel은 ready node를 유지하지만 resolver는 빈 `readyNodes`와 false로 강등한다. 원본 1 passed, 교집합 두 줄 제거 변이 1 failed, 복원본 1 passed로 M1 KILLED다.
- node-agent는 canonical fixture를 embedded `core.schema.json`으로 검증하고 생성 `contracts-go.ModelExecutionManifestObservation`으로 소비한다. project/model/version/manifest hash와 비권한 플래그를 대조하며 drift는 `NODE-0070`으로 전체 거부한다. generator exit 0, node mirror/Go 타입 drift 0이다.
- 구현 `9c519774`(부모 `80d4e748`)는 origin integration에 fast-forward 착지했다. node-agent build/vet/test, contracts-go, focused pytest 45, 실 PG 1, bindings 52/17/21/12, freshness 10/10, frontend/docs/ontology/ratchet가 모두 exit 0이다.
- hosted 같은 SHA는 Docs `35730310514`, Frontend `35730310623`, Desktop `35730310535`, Core `35730310519`가 success다. Backend `35730310466`은 후속 push로 job 0 cancelled된 최초 시도를 통과로 세지 않고 같은 run/head SHA로 rerun해 Python matrix 두 job과 최종 conclusion success를 확인했다.
- 상세: [[2026-09-22_21-58-06_KST_VF-CL-02E_NODE-WIRE_Codex_구현]]. 다음 담당은 Claude 독립 검토이며 작성자가 self-close하지 않는다.

## 2026-09-22 review→done 차단 지도

- registry의 `review` 18건과 `in_progress` 2건을 각각 우리 몫·U1~U6 사용자 입력·물리 자원으로 분해했다. S02~S12는 직전 스프린트 FE/BE/DB/ST 네 base 카드의 done에도 연쇄 종속하므로, 자체 증거만 채워 자동 done 처리하지 않는다.
- 사용자 입력 없이 다음 배정 가능한 우선순위는 Codex의 S05-DB benchmark/S07-DB 장애 측정기, Claude의 S02/S03-DB Evidence collector, Gemini의 S09-FE eval runner와 S02/S04-FE browser matrix다. registry·ontology는 변경하지 않았다.
- 정확한 R1 candidate에서 docs 813, ontology 48, generation 4, ratchet 18, diff 모두 exit 0이며 표 20행·planned 26/26 미충족 선행을 기계 대조했다. content commit은 `20a777a8`; Orca Obsidian check는 두 진행판 `both-diverged`로 exit 3이라 apply하지 않았다. 상세: [[2026-09-22_21-55-00_KST_review_done_차단지도_Codex]].

## 2026-09-22 S01-BE·S01-ST 증거 기록 갱신

- PR [#62](https://github.com/egparadise/SaintVision-Invion/pull/62) head `d97a6d7e`의 Claude 인계 R1~R6을 대조해 stale migration head `0045`를 실제 `0046_model_manifest_readiness`로 고쳤다. 계약/hosted CI와 독립 peer review 완료, 물리 노드 인벤토리 **표 양식** 착지를 증거 표에 연결했다.
- registry의 `S01-BE.next_handoff`는 `user-input:U2/U3/U4`, `S01-ST.next_handoff`는 `user-input:U1/U5/U6`으로 바꿨다. 두 task의 `status: in_progress`와 scope는 유지했으며, 값 없는 표 양식이나 소프트웨어 peer review를 실운영 완료로 올리지 않았다.
- 정확한 R1 후보에서 docs 812, ontology 48, generation 4, ratchet 18, diff 게이트가 모두 exit 0이었다. R1 content commit은 `fed529e0`이며 상세 provenance는 [[2026-09-22_21-31-00_KST_S01_증거기록갱신_Codex]]에 고정한다. 다음 담당은 사용자가 U1~U6의 비밀 제외 값을 제공하고, Codex가 해당 운영 성공 신호를 실제 측정하는 것이다.
- Orca worktree Obsidian check는 baseline 차이(3 both-diverged·1 no-baseline)로 exit 3이어서 apply하지 않았다. 착지 뒤 코디네이터가 정본 checkout에서 sync한다.

## 2026-09-22 VF-CL-02(d) inv URI resolver 운영 바인딩

- project-scoped `GET /v1/projects/{project}/models/resolve?uri=inv://...`를 추가하고 카드 2의 strict `ModelExecutionManifestObservation`을 실제 `resolve_model` 주입 reader에 연결했다. restricted `inv_app`이 kernel 관측의 location/version/ready node를 RLS로 재확인하며 최종 node 집합은 교집합만 허용한다.
- R1 구현 `b06fc199`(부모 `e31ce3f3`)은 origin integration에 fast-forward 착지했다. focused 53 passed, 실 PG 단일 파일 1 passed/0 skipped, bindings 52 fixtures/17 types/21 sites/12 replay guards, 새 anchor 1 rejection-tested/0 gap, freshness 10/10, 생성 drift 0, TS/Go·docs/frontend/ontology/ratchet exit 0이다.
- 실 PG에서 난수 `inv_app` login의 kernel table 직접 접근 거부, tenant 미설정 0행, 타 project 403, 미존재 404, stale false/empty, 성공 후 membership 폐기 동일 GET 403을 확인했다. hosted CI는 Backend `35726028276`, Docs `35726028423`, Frontend `35726028287`, Desktop `35726028426` success, Core `35726028397`는 후속 push로 cancelled되어 통과로 세지 않는다.
- 상세: [[2026-09-22_21-18-16_KST_VF-CL-02D_INV-URI-RESOLVER_Codex_구현]]. 다음 담당은 Claude 독립 검토이며 작성자가 self-close하지 않는다.

## 2026-09-22 S06-DB·S08-DB owner 판정

- 실제 PostgreSQL/Linux와 hosted Core 증거를 AC-06/08에 다시 대조해 S06-DB·S08-DB를 `planned`에서 `review`로 전환했다. 이는 reviewer 인계이며 outcome/acceptance `done`이나 진행률 상승이 아니다.
- hosted Core `35706465645` artifact에서 Workspace explicit 22, workspace recovery 12, snapshots 15, permission observation 11, readiness 10, pilot 35, containment 28, audit 41이 모두 0 failure임을 직접 확인했다. hosted recovery drill 19 skip과 물리 GPU 미실행도 함께 기록했다.
- S06은 S05 선행·실 원격 WS/PTY/Git 재시작·제품 snapshot reader 결속, S08은 S07 선행·실 GPU·승인 우회 종단·off-device/PITR/독립 역할 복원을 done 차단 조건으로 유지한다.
- registry 2줄과 ontology 4산출물을 재생성했고 docs 804·ontology 48 mappings·generation 4 artifacts·ratchet 18 pairs·diff 게이트가 모두 exit 0이었다. 상세: [[2026-09-22_21-13-00_KST_S06-DB_S08-DB_Codex_owner판정]].
- R1 적용 commit `6d095d5c`는 최신 integration `b06fc199`을 부모로 하며 8개 Codex 소유 파일만 담는다.
- Orca worktree의 Obsidian check는 baseline 없는 4개 `both-diverged`로 exit 3이어서 apply하지 않았다. 착지 뒤 코디네이터가 정본 checkout에서 sync한다.

- **hosted Core 컨테이너 opt-in**: PR [#59](https://github.com/egparadise/SaintVision-Invion/pull/59), exact head `0d02f343`, run [35720205341](https://github.com/egparadise/SaintVision-Invion/actions/runs/35720205341) success — role guard 13 + server 8 + config 2를 실행 전환해 JUnit **3065 passed / 35 skipped / 0 failed**; Claude review pending. 상세: [[2026-09-22_hosted_Core_컨테이너_opt-in_검증_Codex]].

## 2026-09-22 VF-CL-02(c) 실행 Manifest 관측 + model-retry F1

- 타 tenant model-retry가 `503 SYS-0001`을 내던 idempotency 선행 순서를 기존 `can_request` 경계 앞에서 차단하도록 고쳐 `403 AUTH-0030` ProblemDetails로 만들었다. 본 트랜잭션 재검사는 유지했다.
- project-scoped `GET /v1/projects/{project}/models/{modelId}/versions/{version}/execution-manifest`와 strict `ModelExecutionManifestObservation`을 추가했다. missing shard/mapping은 `409 MODEL-0001` 전체 실패, stale·location-version mismatch·ready replica 없음은 `readyNodes=[]`/`materialisable=false`다. 기존 commitment API는 불변이다.
- R1 구현 SHA `4473c7f1`(부모 `b877c601`)은 origin integration에 fast-forward 착지했다. focused 68 passed, 실 PG HTTP 2 passed/0 skipped, 생성 drift 0, bindings 52 fixtures/17 types/20 sites/12 replay guards, model_view anchor 1 rejection-tested/1 called-only/0 gap, docs·frontend·ontology·ratchet exit 0이다.
- 후속 정책 등록 hotfix `57f3afb9`에서 Docs `35723211550`, Frontend `35723211574`, Desktop `35723211494`, Core `35723211545`가 success했다. Backend `35723211526`은 후속 integration push로 cancelled되어 success로 세지 않는다. Claude는 PR #58에서 finding 0으로 독립 승인했고, 운영 인수 전에는 self-close하지 않는다.
- 상세: [[2026-09-22_20-19-51_KST_VF-CL-02C_MODEL-RETRY-F1_Codex_구현]].

## 2026-09-22 S04-DB·S05-DB·S07-DB owner 판정 + PR #53 교차검토

- Claude 인계 패키지 `04d88d58`의 실 PG·hosted Core 증거를 AC-04/05/07과 대조해 세 카드의 `planned` → `review` 진입을 수용했다. acceptance/outcome `done`은 건드리지 않았고, S04 물리 전송 재개, S05 5노드 결정성·P95 2초, S07 이탈 60초·복구 95%·CX01 및 각 선행 카드가 완료 차단 조건이다.
- Core run `35706465645`의 실제 파일별 수치는 node delivery 18, output ingestion 5, placement 12, shard recovery 21, containment 28, workspace recovery 12다. 인계 문서의 shard 15·containment 21 표기는 집계 오기로 보정해 기록했다.
- registry 3줄과 ontology mirror를 재생성한 뒤 착지 후보에서 `check_docs` 796 documents, `check_ontology` 48 task mappings, single-source ratchet 18 pairs가 모두 exit 0이었다. 메모리 경보 지침에 따라 시험 suite는 재실행하지 않았다.
- PR #53 HEAD `9a7a3651`은 잔여 충돌 표식, 스크린샷 수·병합 head SHA 불일치, 제어문자성 손상, 미래 갱신 시각 때문에 수정 요청했다. 코멘트: https://github.com/egparadise/SaintVision-Invion/pull/53#issuecomment-5775051728
- 상세: [[2026-09-22_19-45-00_KST_S04-DB_S05-DB_S07-DB_Codex_owner판정]].

## 2026-09-22 Frontend 경로 필터 교정 + PR #51 교차검토

- Claude hosted triage의 integration Frontend 1회 관측을 재검토했다. push의 `paths`를 제거해 main/integration에서는 모든 SHA에 Frontend가 실행되게 했고, PR filter에는 실제 import 뿌리 `packages/contracts-ts/**`를 추가했다. 기존 `contracts/**`는 공유 schema·fixture를 이미 덮으며, docs route-coverage 배선은 PR에서 Documentation 소유이고 integration에서는 path filter 제거로 Frontend도 실행된다.
- PR #51 head `ec58e0c1`은 실제 `.env` PostgreSQL + `TestClient(create_app(...))` 단일 파일에서 **8 passed / 0 skipped / exit 0 / 17.29s**였다. 제품 POST route, idempotency, 409/403, failed-only, `requiresFrozenInputAndApproval`, lineage·lease 영속을 확인해 시험·증거 PR로 승인했다. 코멘트: https://github.com/egparadise/SaintVision-Invion/pull/51#issuecomment-5774858320
- PR #51 F1은 타 tenant가 기대 4xx 대신 `503 SYS-0001`을 받는 현재 backend 분류 오류다. child·lineage 유출은 없고 PR이 명시 pin해 숨기지 않으므로 검증 PR에는 비차단이지만, backend 후속에서 `RES-0004`/`AUTH-0030` 계열로 고쳐야 한다. 현재 PR conflict 재기반 중 시험 blob 변경 시 재검토한다.
- 상세: [[2026-09-22_frontend_경로필터_교정_PR51_교차검토_Codex]].

## 2026-09-22 task_84d2b7804299 — 커널·계약·CI와 후속 reviewer 판정

- 기준선 `d01c931a`; owner Codex, 독립 검토 Claude. 코드 착지: `881f2911`, `1312e295`, `eceac8cf`, `dcf2b94`, `51d53b7f`, `2aa80899`, `2e803cd6`, `4b2204d7`, `7509f667`, `33283867`, `9f1c0fcc`, `563c54ce`. reviewer 착지: `3882496d`.
- 완료한 것: 5-workflow 실제 실행·red 귀속, Codex CI/harness 보정, EvidenceEnvelope 실PG 5-site 서빙 거부, docs 계약·프런트 게이트/UTF-8, 결정 #2/#5 계약, fixture reachability report-only, 결정 #6a 실패 model Run 재시도 HTTP 계약. F-A/F-B는 `33283867`에 반영했다.
- 검증: 6a clean tree focused 68 passed, 실PG HTTP 1 passed, bindings 51 fixtures/16 response types/19 sites, app anchor 3 rejection-tested/0 gaps, Go build·vet·test, TS strict, docs/frontend/ontology/ratchet 모두 exit 0. Core [35706465645](https://github.com/egparadise/SaintVision-Invion/actions/runs/35706465645)는 전체 단계 success, Browser [35710556600](https://github.com/egparadise/SaintVision-Invion/actions/runs/35710556600)도 success다.
- 교차검토: Node resource usage의 grant·신선도·`released_at IS NULL` lease 집계·RES-0010/0011에 finding 없음. 당시 Frontend filter가 실제 의존 뿌리를 모두 덮는다고 판단했으나 `packages/contracts-ts/**` 직접 import와 integration all-5-same-SHA 요구를 누락했다. 위 경로 필터 교정 카드가 이 결론을 대체한다.
- reviewer 판정: S02-DB/S03-DB는 review 진입만 수용했다. 실 IdP·물리 Node·실 컨테이너 금지 명령/출력·선행 카드가 남아 있어 done/self-close 금지다. registry·ontology 및 판정 History는 `3882496d`.
- 동일 SHA hosted CI: `f2aa2b14`에서 Backend [35714785554](https://github.com/egparadise/SaintVision-Invion/actions/runs/35714785554), Core [35714470445](https://github.com/egparadise/SaintVision-Invion/actions/runs/35714470445), Browser [35712413553](https://github.com/egparadise/SaintVision-Invion/actions/runs/35712413553), Docs [35712413561](https://github.com/egparadise/SaintVision-Invion/actions/runs/35712413561), Frontend [35712428159](https://github.com/egparadise/SaintVision-Invion/actions/runs/35712428159)가 모두 success했다. 최초 Core의 Docker isolation 단일 failure는 같은 코드 후속 Core `35713565774`와 고정 SHA 재실행이 모두 전체 success해 runner transient로 분류했다.
- 다음 첫 행동: 다음 fresh dispatch에서 model-retries 타 tenant 503 `SYS-0001` F1을 정직한 4xx로 먼저 보정하고 VF-CL-02(c) project-scoped 커널 라우트를 구현한다. 이 카드는 self-close하지 않고 Claude 독립 검토·운영 인수를 기다린다.
- Evidence: [[2026-09-22_18-37-00_KST_CODEX-KERNEL-CI-CONTRACT_Codex_최종보고]], [[2026-09-22_18-27-37_KST_S02-DB_S03-DB_Codex_독립검토]].

## 2026-09-22 hosted CI 러너 기아 방지

- 카드 `THREAD-2026-09-22-CI-RUNNER-STARVATION`; owner Codex. integration `3d1892c0` Core가 PR Core 네 곳의 러너 점유 때문에 20분 이상 jobs 0 pending이었던 관측을 원인으로 삼았다.
- 5 workflow를 `workflow + ref` group으로 고정하고 main/integration만 `cancel-in-progress=false`, PR/수동 Agent branch는 true로 명시했다. Core는 label 없는 PR에서 job을 skip하고 `run-core` label·workflow_dispatch·main/integration push에서만 실행한다. Backend/Docs/Frontend/Desktop Browser PR 실행은 유지한다.
- repository `run-core` label을 생성했다. 로컬 actionlint는 PATH에 없어 실행하지 않았고, PyYAML 정책 validator·check_docs·check_ontology·diff check는 모두 exit 0이다. 상세: [[2026-09-22_hosted_CI_러너기아_방지_브랜치별_concurrency_Codex]].
- 카드 중 선처리 검토: PR #41 재검토 승인, PR #46 report-only docs 배선 승인·선병합 후 재기반, PR #44 보안 헤더·실 browser/container 증거 승인(rebase 필요).
- 정책 본체는 integration `a7f2ecf2`에 착지했다. 다음 push `f2aa2b14`의 Core run [35712413499](https://github.com/egparadise/SaintVision-Invion/actions/runs/35712413499)은 선행 integration Core가 끝난 3초 뒤 `09:57:57Z`에 실제 job을 시작해 PR Core 기아 해소와 in-progress 보호를 입증했다. run은 이후 Docker isolation의 `NODE-0027`로 failure였으며 scheduling acceptance와 분리해 후속 Core triage 대상으로 남겼다.

## 2026-09-22 PR #41 결정 #7 시각 스큐 알람 교차검토

- 대상 PR #41 최신 head `35fb2859`를 Claude→Codex 규칙으로 독립 검토했다. `.env` `INV_TEST_ADMIN_DSN` 실 PostgreSQL에서 PowerShell `Start-Process` 분리·폴링으로 `tests/test_alarm_check.py`를 실행해 **35 passed / exit 0**, `check_docs.py`도 773 documents / exit 0을 확인했다.
- 현재 알람 술어(`None`·비유한·`abs > 5`, online만), P2·인프라 1차·기록 채널·자동 조치 없음은 커널과 규격에 맞다. 그러나 accepted ERR-DESIGN-007이 커널과 알람을 "동일 함수가 제어해 어긋날 수 없음"으로 단언한 것은 실제 독립 Python/SQL 술어와 모순이라 **수정 요청**했다. 코멘트: https://github.com/egparadise/SaintVision-Invion/pull/41#issuecomment-5773731159
- PR #38의 미연결 능력 문서는 exact blob이고 시각 스큐 제안서는 채택 frontmatter/callout만 갱신한 내용상 superset이므로, finding 수정 뒤 #41이 #38을 supersede할 수 있다. 상세: [[2026-09-22_PR41_시각스큐알람_교차검토_Codex]].
- 다음: Claude가 규격 보장 표현과 docstring 조항 번호를 고친 새 head를 올리면 단일 시험 파일과 docs만 재검증한다. 병합은 코디네이터 소관이다.

## 2026-09-22 최초 hosted CI 실패 교정

- 카드 `THREAD-2026-09-22-FIRST-HOSTED-CI-RECOVERY`; owner Codex, reviewer Claude pending. 초기 base `d01c931a`, R1 착지 base `2aa80899`, integration landing `36d3ee9b`, branch `agent/codex/continuation-20260922`.
- Backend schema drift, Core ontology 의존성·credential fail-closed/portable fixture, Browser catalogue·business-project·model availability 회귀를 교정했다. 통합에서 누락된 `origin/codex/ontology-regeneration` 9커밋도 merge `23235bbb`로 복원했다.
- 작성자 검증: Linux credential 61 passed, storage PG 24 passed/0 skip, 실 브라우저 6 passed/0 failed/0 skipped, Vitest 655 passed, frontend contracts 16, schema 58. 정확 착지 후보에서는 docs 764, bindings 50 fixtures / 14 response types / 17 sites / 12 replay guards, ontology 48 tasks가 exit 0이고 core 단일 파일 29 passed였다. 기존 69 Docker volume은 건드리지 않았다.
- R1 착지: 최초 후보 `8dc73ff9`는 origin이 `2aa80899`로 이동해 push 전에 차단했다. 최신 tip에 같은 24개 작성 경로만 다시 얹은 `36d3ee9b`를 non-force push했고, 부모·rev-range·origin tip을 대조했다.
- 아직 `done` 아님: integration landing은 완료했지만 hosted Documentation·Backend 3.12/3.14·Core·Frontend·Desktop Browser와 Claude 독립 검토가 pending이다. Evidence: [[2026-09-22_최초_호스티드_CI_실패_교정_Codex]].

## 2026-09-22 최종 정지 기준선 — `70234d2e`

- 마지막 착지: Claude `check_anchor_weight` 범위·타입/위치 독립 검토(`1c7c6ef5`), WorkloadSpec 입력 앵커 무게 시험(`cdfab100`), R2-b push exit hard-stop 절차(`ff926916`, `c74855d7`), GOV-GIT-001·AGENTS·이전 절차서의 게이트 예시 교정(`70234d2e`).
- 확인: `check_docs.py` exit 0, `check_ontology.py` exit 0, 의도적 red gate 변형에서 `throw` 후 push marker 미생성, 작업 트리 clean.
- 남은 것: `shard_completion` Linux 실행, WorkloadSpec 전체 PostgreSQL 통합, Go T1-3/교차언어, 물리 worker 5대 인수, 다운로드 정본 사용자 결정. 이 호스트에서 새로 시작하지 않는다.
- 다음 담당: 새 PC 또는 CI에서 기준선 이후 전수 검증. 독립 검토·외부 실행·사용자 결정은 각 담당 경계를 유지한다.

## 2026-09-22 GOV-ALERT-001 ???? ?? ??

- `tools/alarm_check.py`? ?? `coverage`? ?? 20? ?? ??? ??? ??? ??? ??? ??? ?? `4 of 16`?? ???? ?? ????. ?? ??? ?? ????? ??? ? ??, ?? ????? ?? ???governance-gated ??? ??? ????? ????.
- `tests/test_alarm_check.py`? ?? ?? ??? ????. `.venv\Scripts\python.exe -m pytest -q tests/test_alarm_check.py`? ?? ? 12 passed/exit 0, ?? ?? ??? 1 failed/11 passed/exit 1, ?? ? 12 passed/exit 0??. `git diff --check`? exit 0??.
- ?? ?? ????????? governance ??? ???? ???. PostgreSQL ??, ?? ??, CI ? Claude ?? ??? ???/pending??. Evidence: [[2026-09-22_alarm_coverage_summary_Codex]].

## 2026-09-22 strict response producer-shape self-audit

- **Closed (Codex author work):** source-audited the 19 response models added/narrowed tonight; no producer shape was found that the strict models reject. Corrected the impossible Node enrollment fixture and added branch-shape coverage for project kernel-link outputs, cleared/unassigned workspace tools, and contribution status ? nullable-capacity combinations. Named the broader class `schema-valid but producer-unreachable fixture state`; examples are Claude's impossible Node `online` fixture and this audit's enrollment heartbeat sequence/timestamp mismatch. The current binding checker validates fixture references and serving anchors, not producer reachability. See [[2026-09-22_response_model_shape_self_audit_Codex]].
- **Verified:** integration SHA `9dbf9915` is the recorded clean test tip. Focused suite: 101 passed, 2 PostgreSQL-gated skips because `INV_TEST_ADMIN_DSN` is absent; DB-backed producer output therefore remains unverified. `check_docs` passed. Obsidian read-only check had pending exports and was not applied.
- **Independent review pending:** Claude review of this audit and its added tests.
- **Decision pending:** whether to add a generic producer-reachability check for fixtures. No implementation or further fixture scan was started; this requires a design decision.

## 2026-09-22 CI 개방 전 조건부 수동 교차 검증 절차 제안

- 작업 `THREAD-2026-09-22-PRECI-CROSS-LANE-PROPOSAL`; owner Codex, governance owner/reviewer Claude (수용 대기). 기준 integration SHA `2867ddbb78af0efdc46288b3c26a316e41ad719e`.
- 변경 범위에 따라 Vitest/Python UI guard, schema/fixture/backend contract, PostgreSQL API, Chromium/proxy를 선택하는 제안을 History에 작성했다. 문서-only, 화면, 계약, route/DB/security, browser/proxy, 누적 integration/handoff별 trigger와 정확한 최종 SHA·provenance·skip 분포 요구를 적었고 모든 suite를 매번 돌리지는 않도록 했다.
- 임시 절차 종료는 결제 복구만으로 하지 않는다. 같은 integration SHA에서 `docs/backend/core/frontend/desktop-browser` 다섯 hosted workflow가 실제 완료되고, 기대 테스트가 실행되고, 금지 skip/error/failure가 없으며 evidence를 남긴 뒤 수동 전체 교차 절차를 해제하도록 제안했다. workflow 누락/비활성 시 해당 lane 수동 실행 재개 조건도 포함했다.
- 이 내용은 **제안**이며 Claude 소유 정본을 편집하지 않았다. Claude 수용 전 효력 없음. Evidence: [[2026-09-22_CI개방전_조건부_수동검증절차_제안_Codex]].
- 이 카드 닫힘: 교차 레인 목록 완료; 최초 Python guard red 및 Gemini fix 후 Python guard green을 각각 기록; latest Gemini DOM 3-case는 소스 확인만 했고 Codex Vitest 재실행/독립 승인 없음. Hosted CI 미실행.
- 대기: (1) Claude의 절차 제안/작업판 수용, (2) Claude independent review of Codex contract/guard work as assigned. 사용자 결정 대기: capability별 동적 node usage 계약; artifact GET의 receipt/file 정본; WorkspaceRecovery 제품 연결·보존 정책; 시계 skew alarm threshold/owner/routing; discovery credential 안전 전달 경로; Node `active` 상태 의미/표시 정책. 외부/환경 대기: GitHub Actions 결제, Go toolchain 및 실 Node 인수. 상세 범위는 해당 History와 기존 결정 대기 목록에서 확인한다.
- 다음 담당: Claude가 제안 문서를 검토해 정본에 반영하거나 수정 요청/기각한다. CI 복구 후 최초 동일-SHA 5-workflow 실행 evidence를 집계한다. 문서 검사 외 제품·DB·Vitest·browser 시험은 실행하지 않았다.

## 2026-09-22 프런트·백엔드 검증 레인 교차 가드 목록

- 작업 `THREAD-2026-09-22-CROSS-LANE-TEST-INVENTORY`; owner Codex, reviewer pending. 기준 integration SHA `8f4d9194736037e31404de9b00d520efb23e1da8`; 격리 worktree `C:/Project/SaintVision-Invion/.worktrees/codex-cross-lane-test-inventory`.
- 소스/workflow 정적 조사에서 프런트 규칙을 직접 검사하는 Python source-policy는 `tests/test_route_coverage.py` 한 파일(세 UI/source guard)이며, 실제 client path 대조는 `tests/integration/test_vf_canonical.py`에 있다. Browser/HTTP/PG 연동은 desktop-browser workflow 전용 lane에 분리돼 있다. Vitest의 17개 canonical schema/fixture 검사와 mock 기반 UI 시험을 backend runtime 검증으로 혼동하지 않도록 구분했다.
- 고정-SHA `8f4d919`에서 사용자 보고 EvidenceViewer false PASS를 focused 시험으로 실행: `python -m pytest -q tests/test_route_coverage.py::test_evidence_viewer_integrity_contract_invariants` → exit 1 / 1 failed. 그 트리의 `sealed && sha256` PASS가 Python 가드에 실제 검출됐다. 후속 integration `0b7d51e`에서 Gemini의 UI 수정과 3-case DOM guard를 소스에서 확인했다. 착지 SHA `e83b79bd`의 clean tree에서 동일 Python guard는 provenance wrapper로 1 passed/exit 0 (C:\Python314\python.exe 3.14.6, 04:47:29 KST); Vitest/전체 pytest/browser/CI는 실행하지 않았다.
- Workflow 소스상 backend/core full pytest가 Python guards를 수집하고, frontend workflow가 Vitest/contracts/build를 수행한다. GitHub Actions는 결제 대기로 미실행이므로 현재 임시 통제는 각 레인을 수동 실행하고 같은 SHA·skip 분포·결과를 기록하는 것이다. CI 성공은 아직 주장하지 않는다.
- History: [[2026-09-22_프런트백엔드_검증레인_교차가드_목록_Codex]]. 코드·시험 및 다른 Agent 작업판 수정 없음. 다음: CI 결제 후 integration 동일 SHA에서 backend/core/frontend/desktop-browser 각 lane 실행 결과를 확인한다. 독립 검토 pending.

## 2026-09-22 부재 주장 회귀 가드

- 작업 `THREAD-2026-09-22-NEGATIVE-CLAIM-GUARDS`; owner Codex, reviewer Claude pending. 기준 integration `23f76b9172c7a5e85527a4ef1d692e66299e3ebd`; code/test SHA `2679f0c76b81f078b40e21d1461f7af4dac95050`; branch `agent/codex/negative-claim-regression-guards`; 격리 worktree 사용.
- `failed`가 terminal이며 재시도 간선이 없다는 상태기계 불변식을 `test_failed_run_is_terminal_and_cannot_enter_a_retry_transition`로 명시했다. capability kind·Node OS·placement strategy는 현재 지원값과 외부 미지원 sentinel을 각각 시험해 새 값을 무심코 열거나 현재값을 제거하지 못하게 했다. 제품 코드는 바꾸지 않았다.
- 지원값과 미지원 sentinel을 request 및 대응 response 모델 양쪽에서 고정했다. 여섯 변형을 각각 주입해 guard가 죽는 것을 확인했다: failed→scheduled 허용, request의 `npu` capability 허용, response kind의 `npu` 허용, `freebsd` OS 허용, request의 `automatic` strategy 허용, response strategy의 `automatic` 허용. 각 변형에서 해당 시험이 exit 1로 실패했고 원복했다. 기준 focused suite는 99 passed, 2 deprecation warnings.
- History `[[2026-09-22_부재주장_회귀가드_Codex]]`에 명령·환경·돌연변이·남은 범위를 기록했다. 이번 카드의 작성자 검증 완료, 독립 검토 대기. PostgreSQL·CI·실 Node 실행은 하지 않았다.
- 다음: Claude가 integration SHA의 새 guard와 돌연변이 근거를 독립 검토한다. 사용자 결정 대기 항목은 capability별 동적 사용량 모델, artifact GET의 영수증/저장파일 정본, WorkspaceRecovery 운영 연결 및 보존 정책, 시계 스큐 알람 기준·대응 경로, discovery credential의 승인된 비밀 전달 경로다. Hosted CI는 결제 복구 대기이며 실제 Go/장비 인수는 툴체인·장비 조건 대기다. 각 상세 상태는 아래 기존 카드 및 공통 진행판을 기준으로 다시 확인한다.

## 2026-09-22 좁은 계약의 외부·확장 도메인 역검토

- 작업 `THREAD-2026-09-22-ENUM-OPEN-DOMAIN-REVIEW`; owner Codex, reviewer Claude. 기준 integration SHA `640d0119eb3276dd4873ac8f1a7bebea25eef316`; branch `agent/codex/enum-contract-exception-review`; 격리 worktree 사용.
- 오늘 좁힌 세 status 계약은 제외하고 기존 API의 열거/패턴 도메인을 소스·DB 제약·생성 타입·소비 경로로 대조했다. 현재 잘못 닫힌 값은 찾지 못했다. capability kind와 placement strategy는 외부/사용자 입력 및 확장 후보지만 모르는 값으로 동작할 수 없어 fail-closed 유지가 맞다. OS type도 경로 안전성 때문에 현재 지원 OS만 허용해야 한다.
- Node의 좁은 wire status를 화면 projection으로 전달할 때 현재 `active`가 `unknown`이 되는 잔여 불일치를 확인해 Gemini 재검증 대상으로 남겼다. Claude가 후속 `447a65e9`에서 규칙 7에 내부 폐쇄/외부 확장 구분과 DB CHECK의 현재성 조건을 반영했다. control input은 미지원 시 명시적으로 거부되어야 하며 capability kind/strategy를 넓힐 근거는 없다는 해석을 기록했다. 공통 정본은 수정하지 않았다.
- `.venv/Scripts/python.exe` (Python 3.14.6)에서 workspace/node/write response 계약시험 74 passed, export_schemas 56/56 통과. DB·CI·실 Node·브라우저는 미실행. 전체 범위와 근거: [[2026-09-22_좁은계약_외부확장도메인_역검토_Codex]]. 리뷰와 reviewer 상태는 pending.

## 2026-09-22 Run retry 경로 감사와 저위험 쓰기 응답 결속

- 제품 소스 정적 조사에서 일반 failed Run을 재실행하는 경로는 발견되지 않았다. DeliveryQueue는 기존 command 전달/receipt 관찰을, OutputIngestion은 같은 결과 receipt 수집을 재시도한다. Run-list의 재시도 버튼은 조회만 새로 한다. WorkspaceResume는 recovering workspace Run의 frozen checkout·새 step·approval에 한정된 continuation이고, ShardRecovery는 새 child Run/approval을 만드는 별도 capability지만 현재 app/worker 진입점이 없다. ModelRetryStore도 server-internal 구현이며 제품 route/worker에서 호출되지 않는다. 어떤 retry도 연결하지 않았다.
- 사용자 저위험으로 분류된 일곱 raw-dict write를 strict response_model/fixture/schema로 결속했다: heartbeat, liveness sweep, discovery announce/decline, member removal, user status, project status. Discovery announce는 existing candidate/admitted/declined/expired의 기존 상태를 보존한다. 각 route anchor 제거 대조 7/7 감지. 코드 commit `d901a0d1`, 검증 tree SHA `f2d86db5`; 관련 core 계약 시험 77 passed, schema 56/56, binding 46 fixture/12 serving test, docs/ontology 통과. Obsidian read-only check는 1518 managed/4 pending/0 conflicts이며 apply하지 않았다.
- History: [[2026-09-22_Run_retry_path_and_low_risk_write_contracts_Codex]]. 정적 감사 base `044c343a`; 구현은 최신 integration `1212f8b6` 위에서 검증 후 fast-forward로 착지했다. Origin/local integration 모두 `a8ad24d4`이고 clean. 작성자 검증은 완료, Claude 독립 검토와 PG·CI·제품 런타임 검증은 미실시/pending이다.

## 2026-09-22 Control-plane 제품 경로 도달성 감사

- 기준 `0d5b82591286975c226097f14cb4f309ca306629`, owner Codex; 정적 조사만 수행하고 제품 경로를 연결하지 않았다.
- WorkspaceRecovery의 제품 미연결은 기존 사용자 결정 대기로 재확인했다. 새 후보는 ModelRetryStore/Placement/scheduler: 구현과 DB 시험은 있으나 app/worker entrypoint에서 호출되지 않고, architecture 문서도 endpoint/auth binding을 후속으로 남긴다. 사용자/업무 owner의 노출 결정이 필요하다.
- NodeTransfer와 PostgresCredentialRegistry는 Node executor/runtime adapter 미구현으로 문서상 의도된 integration gate다. Outbox broker helper는 호출되지 않지만 DB outbox→`/events` 제품 경로는 연결돼 있다. generated Pydantic models 미사용은 JSON Schema 정본 규칙상 의도적이다.
- 69개 비-`__init__` 모듈의 AST import 폐포는 61개 도달/8개 수동 확인 후보였다. 최신 integration SHA `5bb87e7e` 위 문서 게이트: check_docs / ontology / git diff 0, Obsidian read-only 1516 managed/7 pending/0 conflicts. 상세 판정과 범위: [[2026-09-22_ControlPlane_제품경로_도달성_감사_Codex]]. 제품시험/DB/HTTP/CI를 실행하지 않았고 외부 wrapper는 미확인이다.
- 다음: 사용자/집계 담당이 모델 재시도 진입점을 제품에 노출할지/owner를 결정. Claude 독립 검토 요청은 이번 감사에서 보내지 않았다.

## 2026-09-22 Workspace snapshot reader 감사

- 요청: 저장된 `inv.workspace-output` snapshot 파일을 실제로 읽는 경로가 있는지 확인. Owner Codex; SHA `993cfaf068f3da1df09f402399e75ea3aa55711d`.
- 판정: 후속 읽기 구현은 있지만 현재 tracked product tree의 운영 경로에는 연결되지 않았다. `configured_workspace`는 `WorkspaceAPI`만 조립하고 restore/checkout route가 없다. resume prepare는 `workspace_checkouts` 행을 요구하는데 그 row writer인 `WorkspaceRecovery.checkout`은 제품 composition에서 생성·호출되지 않는다. queue/event 소비자도 찾지 못했다. 따라서 completion 시 receipt와 대조하는 읽기 외에 저장 workspace-output의 운영 consumer는 현재 없다.
- 근거/경계: tests를 제외한 `git grep`와 설정→route→필수 checkout row→writer 흐름을 정적으로 대조했다. `SnapshotStore.restore`/WorkspaceRecovery 복구는 integration tests와 격리 acceptance 도구에서만 호출된다. 제품 운영 연결 부재는 tracked tree 기준 확인이며 미추적 외부 wrapper는 미확인이다. 이 작업에서 실행 시험은 하지 않았다.
- 변경/안전: 제품 코드·provider wiring 변경 없음, 사용자 결정 선점 없음, `.work` 잔여 삭제 없음. 근거와 검색 범위: [[2026-09-22_workspace_snapshot_reader_inventory_Codex]].
- 문서 게이트: SHA `993cfaf068f3da1df09f402399e75ea3aa55711d`, `C:\Python314\python.exe tools/check_docs.py` exit 0; `sync_obsidian.py --check` exit 0, 1508 managed/4 pending/0 conflicts (read-only). Pending를 apply하지 않았다.
- 다음: 제품/운영 owner 결정 필요 — recovery wiring을 제품 route/worker에 연결하거나, 연결 전 저장·pin을 유지할 근거와 용량 정책을 정한다. artifact GET 정본 선택도 별도 사용자 결정이다. 제품 코드·provider wiring 변경과 `.work` 정리는 없었다.

## 2026-09-22 contribution lifecycle·workspace-tool 응답 결속

- `register_contribution`·`activate_contribution`·`revoke_contribution`의 반환 shape가 동일한 `{contribution: ContributionResponse}`임을 확인하고 activation/revoke에 registration과 같은 strict response_model을 연결했다. 각각의 response_model 제거 변형에서 invalid-response 시험이 1 failed로 깨졌다.
- 남은 raw-dict 쓰기 중 가장 풍부한 workspace-tool 응답을 별도 `WorkspaceToolResultResponse`로 결속했다. 모델/fixture/route 시험과 JSON Schema 생성이 추가됐고, readiness 필드의 extra 주입은 500으로 거부된다. route 앵커 제거 대조도 시험을 실패시켰다.
- Provenance 고정 SHA `1381e2c2147d3f0846aef44277745d21bbb5d0ed`; 당시 `integration/all-agents-unified`는 fetch된 origin보다 1 커밋 뒤, 공유 워킹 트리는 다른 작업자의 프런트 변경 등으로 dirty였다. `.venv/Scripts/python.exe`로 두 계약 시험 파일 65 passed, `export_schemas.py --check` 49 schemas, `check_contract_bindings.py` 39 fixtures/12 kernel anchors 통과, `git diff --check` 통과. 03:34:47 KST 재실행은 service 시험 포함 65 passed/1 skipped; 유일한 skip은 `INV_TEST_ADMIN_DSN` 부재다.
- 미결속 저위험 raw-dict 쓰기는 heartbeat, liveness sweep, announcement/decline, member removal, user/project status 7개다. 새 handle을 만들지 않는 수령증/상태 응답이다. 완료 처리하지 않고 다음 Codex 카드로 남긴다. CI·독립 검토·실 PostgreSQL workspace-tool 검증도 pending.
- Evidence: [[2026-09-22_Contribution_lifecycle_and_workspace_tool_response_contract_Codex]].
- 후속 문서 게이트(최신 base 재검사): `check_docs.py`·`check_ontology.py` exit 0; `sync_obsidian.py --check` exit 0 (1512 managed, 4 pending, 0 conflicts; no writes). 상세 KST/provenance는 History에 기록.

## 2026-09-22 Artifact download SHA-256 header 경로 감사

- 작업 카드 `THREAD-2026-09-22-ARTIFACT-CONTENT-HEADER-AUDIT`; owner Codex, 독립 reviewer pending. Base SHA `3ebbe960f8136318a16427c248d8345172805a12`; implementation SHA `b9f8212a2124a852aeaaf95a8e435e475d803cdb`; branch `agent/codex/artifact-content-header-audit`, fast-forwarded to integration. Final test worktree had one unrelated `apps/web/src/shared/ui/Header.tsx` modification by another worker; it was left untouched.
- 제품 control-plane에서 `/artifacts/content` 라우트 두 개를 전수 확인했다. 프로젝트 경로와 run 경로는 같은 `run_file` handler이며, 둘 다 materialized bytes를 `artifact_content_response`에 전달한다. 이 함수는 바이트 길이와 SHA-256을 먼저 확인한 뒤 항상 `X-Content-SHA256`을 붙인다. 다운로드 서비스는 검증된 workspace output을 반환하고 스트리밍·오브젝트 스토리지 우회·Range/조건부 응답 분기를 쓰지 않는다. Boundary의 `no-store`도 유지된다.
- `tests/core/test_artifact_content_contract.py`를 확장해 두 라우트 별칭의 일반 요청과 Range+If-None-Match 요청을 검증하고, 제품의 모든 `/artifacts/content` 경로가 정확히 이 두 alias이며 동일 handler인지 고정했다. Range/조건부 헤더는 현재 전부 200 full-body 응답이며 Content-Range/ETag는 없다. `artifact_content_response`에서 SHA 헤더를 제거한 변형은 네 성공 케이스 전부를 실패시켰고 복원 후 13 passed다.
- 별도 격리 레거시 fixture `tests/fixtures/legacy_control.py`에도 같은 URL 모양의 두 route가 있지만, 그것은 `X-Checksum-SHA256`을 내며 production control-plane이 아니다. `rg`로 확인한 import자는 quarantined `tests/test_server_project_api.py`와 `tests/test_server_auth_integrity.py`뿐이다. 실제 배포가 이 fixture 서버를 대상으로 하는지는 이 감사에서 확인하지 않았으므로 제품 근거로 섞지 않는다. Gemini UI 파일은 수정하지 않았다.
- 세부 소스 범위·명령·provenance·검증 한계는 [[2026-09-22_artifact_content_header_path_audit_Codex]].
- Uvicorn 0.52.4를 ephemeral localhost 포트에 띄우고 실제 `urllib` HTTP로 두 alias를 확인했다. 두 응답 모두 200, 본문 34바이트, `x-content-sha256`의 값이 받은 본문 해시와 일치했고 서버 종료를 확인했다. 앱의 `ResultView.download`는 합성 fixture로 대체했으므로 DB/파일 읽기와 배포 프록시는 범위 밖이다. 상세 provenance: History 참조.
- 다음 담당: Claude가 고정 integration SHA에서 독립 검토. 이 근거는 local Uvicorn/HTTP까지이며 실제 배포 프록시와 브라우저 인수는 아니다.

### 후속: 실제 PostgreSQL·저장 파일·Uvicorn HTTP

- 앞선 34-byte synthetic Uvicorn 증거는 이번 실제 경로 시험으로 대체된다. 현재 integration `a0839b4a2aa3f22bd6872bfbe50d339bfccd1d92`에서 실제 PostgreSQL 16과 synthetic Node 실행·output ingestion·Linux LocalObjects 저장을 거쳐 Uvicorn 0.52.4 실제 TCP 요청을 보냈다. 임시 통합 시험 JUnit은 1 passed, 0 failed/errors/skipped다.
- 응답 파일 바이트는 실제 저장 snapshot에서 독립적으로 읽은 `outputs/metrics.json` 및 manifest SHA와 같고, wire `x-content-sha256`도 해당 바이트와 같다.
- 부정 대조에서 저장 snapshot 파일을 변조하자 실제 디스크 해시가 DB metadata와 어긋났지만 HTTP는 여전히 200으로 DB stop receipt의 원본 바이트를 반환했다. 따라서 현재 라우트는 파일을 읽지 않고 receipt 바이트로 내용을 구성한다. DB 기록 해시 UPDATE 대조는 불변성 trigger가 거부했다. 파일 변조를 감지하는 HTTP 보장이나 파일 기반 다운로드는 검증/승인되지 않았다.
- 실행은 임시 disposable PostgreSQL과 owned Linux runner에서 했고 둘 다 제거 후 label 조회 0이다. 보호 컨테이너 세 개가 계속 실행 중임을 확인했다. 전체 소스·명령·환경·정확한 경계는 [[2026-09-22_artifact_download_real_pg_uvicorn_source_boundary_Codex]]. JUnit: `docs/vault/30_Development/Evidence/artifact-download-real-pg-uvicorn.xml`.
- 문서 사후 검사: ontology exit 0. 최초 `check_docs.py`는 별도 Claude 인계 문서의 memory link 6건에서 exit 1이었고, Claude 소유 변경 후 재실행은 24 hashes/706 documents로 exit 0이다. 최종 `sync_obsidian.py --check`는 1507 files, 3 pending, 0 conflicts (read-only), `git diff --check`와 시험 파일 원복 대조도 exit 0이다. Pending exports는 적용하지 않았다.
- 다음 행동: Codex가 receipt-authoritative와 physical-file-authoritative 중 artifact GET의 정본을 결과/복구 계약에 맞춰 정리한다. 파일 원본이 요구되면 output provider/공유 저장 경로 구성과 변조 시 HTTP 거부를 구현·시험한다. 브라우저·배포 proxy/TLS/CDN 인수는 별도다.
---

## 2026-09-22 후속 요청 핸들 쓰기 응답 결속

- 작업 카드 `THREAD-2026-09-22-WRITE-RESPONSE-FOLLOWUPS`; owner Codex, reviewer pending. Base `aa67de8c6f6a79798cebe58f685456939d70cdf7`, code SHA `f0a96dc81dae0bcb7741ea76c8a2c254f2a566fe`, branch `agent/codex/write-response-followup-contracts`.
- `POST /nodes`의 NodeEnrollResponse route anchor와 `POST /storage/contributions`의 ContributionRegistrationResponse wrapper/schema/route anchor를 추가했다. 후자는 raw idempotency replay도 응답 계약 검증 아래 둔다. 다음 요청의 대상을 만드는 후속 핸들 응답은 이 두 건을 추가 결속해 상위 잔여가 없다고 판정했다. 하위 status/receipt와 usability 응답은 새 대상을 발급하지 않아 유지한다.
- pinned code SHA에서 `tests/core/test_write_response_contracts.py` 33 passed, `export_schemas.py --check` 47 schema pass. 두 response_model 제거 변형은 각각 invalid response를 201으로 반환해 해당 시험 실패. 최초 실 PG 시도는 DSN 부재로 3 skip이었으나 후속에서 disposable PostgreSQL 16을 사용해 세 기존 DB API 사례와 두 DB-backed response-anchor 대조를 실행: 5 passed/0 skipped/0 failed. 두 anchor 제거 시 각 해당 DB 대조가 1 failed로 검출했다. 상세 자원 소유·정리와 provenance는 History 참조.
- 상세 목록·provenance·변형 대조·범위: [[2026-09-22_write_response_followups_Codex]]. 이전 `response-freshness` 이력불일치 ref는 integration 내용 확인 후 삭제됐으며 local/remote refs와 worktree가 없다. 다른 Agent 자원은 정리하지 않았다.
- 다음 담당: Claude 고정-SHA 독립 검토 및 현재 최종 구현 SHA에서 재실행. Hosted CI와 운영 HTTP 인수는 별도다.
---

## 2026-09-22 Artifact content response contract

- 작업 카드 `THREAD-2026-09-22-ARTIFACT-CONTENT-CONTRACT`; owner Codex, reviewer/독립 검토 pending. 구현 branch `agent/codex/artifact-content-contract`, 기준 `8cb1251572de743ef14c6c8ec85dde3d7de65676`, 코드 SHA `65aec0ccbd276e35bd4707b93965b0b1b786debe`.
- Raw artifact body bytes의 content type/length/SHA-256/disposition/nosniff와 manifest `RunArtifactFile` 메타데이터를 canonical 계약·공유 fixture·backend serving validator·frontend 계약 검사에 결속했다. 변형 시험에서 serving validator 제거 시 실패, canonical schema 변형 시 frontend 및 생성 후 backend 검사 실패를 확인했다.
- 코드 SHA clean worktree에서 Python core 13 passed, 계약 바인딩 검사 36 fixture/12 serving anchors, Vitest 6 passed, contracts:check 16 type/schema 통과, web build exit 0. PostgreSQL integration 1건은 `INV_TEST_ADMIN_DSN` 부재로 명시적 skip이며 DB-backed 경로는 미검증. 상세 provenance, 명령, 되돌림 대조: [[2026-09-22_artifact_content_contract_Codex]].
- `agent/codex/response-freshness`는 커밋 내용이 이미 integration에 보존된 것을 확인하고, 이력 불일치 원격 ref를 삭제한 뒤 clean worktree/local ref를 정리했다. 강제 갱신은 하지 않았다.
- 다음: integration 결과를 기준으로 독립 검토, disposable PostgreSQL integration 실행. node usage 모델 결정과 Go T1-3는 이 카드 범위 밖의 대기 항목.
---

## 2026-09-22 Run / shard / artifact / log 신선도 계약

- 작업 카드 `THREAD-2026-09-22-RESP-FRESHNESS`, owner Codex, reviewer pending. 작업 기준 SHA `94fbf7e8fc6d35e87731ec4d52e6509fccaf6f1a`; 최종 검증은 integration `bbfb42b6c898a9bb5e25909eb5baa716f21f26a9`에 fast-forward한 dirty worktree에서 수행.
- 출처 감사 결과: 라이브 Run 상태의 진실 시각은 이미 갱신되는 `inv.runs.updated_at`이고 응답이 이를 누락했다. `ShardObservation`은 parent/member Runs의 `updated_at`을 저장하고 쿼리 가능하지만 서빙하지 않았다. `RunArtifactList`와 `RunLogView`에는 독립적인 artifact/log capture 시각이 없고, 둘 다 읽고 있던 `result_completions.completed_at`만 출력 가능한 영속 시각이다. 따라서 각각 `stateUpdatedAt`, nullable `stateAsOf`(parent/member 최대값이며 단일 DB snapshot 아님), nullable `completedAt`을 계약과 응답에 연결했다. HTTP/query 시각을 데이터 진실 시각으로 사용하지 않는다.
- disposable PostgreSQL 16 실측: 실 자원 등록 시 `appliedToKernel=true`, resource ID/capacity 및 DB `offered=8000`을 HTTP 응답과 대조했고, 등록되지 않은 제어 경로의 `false/resource_not_registered`도 함께 확인했다. `ShardObservation.stateAsOf`와 `RunResultView.stateUpdatedAt`을 DB 저장 `updated_at`과 비교했다. 결과 4 passed, 0 skip, 0 failed/errors. 상세 소유/정리/명령은 [[2026-09-22_response_freshness_asof_Codex]].
- 현재 확인: 전체 Vitest 67 files/607 passed; focused core 18 passed; schema exporter 46, freshness pinned map 9/9, bindings 35 fixture / 11 serving anchor; docs/ontology 통과. 재검증 시각, 명령, 환경 및 제한은 History에 기록. PostgreSQL은 실행 가능한 disposable 환경에서 직접 돌렸고 Go compile, production HTTP, browser acceptance는 주장하지 않는다. Gemini UI 연결은 integration `597ef148`에 있으나 이 작성자 검증은 독립 UI review가 아니다.
- 착지/재검증: `f1d95466ac6b46fad4f110f94ca9fb0bf5354414`를 작업 브랜치와 integration에 push했다. 이 exact SHA에서 clean-tree provenance로 실 PostgreSQL 16 focused 4 passed/0 skipped, core 18 passed, Vitest 607/607, build, 16 web contracts, schema 46, freshness 9/9, bindings 35/11, docs 686/ontology, Obsidian 1483/0/0을 확인했다. 별도 reviewer는 아직 pending이다.
- 후속 독립 분기 재실행: 현재 integration `2158f03011da99037fce92a31c4567ebea5f6da0`에서 parameter `[True]`만 실 PostgreSQL 16으로 실행해 1 passed/0 skipped. HTTP `appliedToKernel=true`, kernel resource ID/capacity, refusal 미발생과 DB `inv.resources.offered=8000`을 확인했고 자체 컨테이너 제거도 재확인했다. 명령/provenance는 History에 추가했다. 기능 결함 수정은 필요하지 않았다. 별도 reviewer pending.
- 다음 행동: 고정 integration SHA에서 별도 reviewer가 backend response semantics와 실 PG 증거를 확인한다. Gemini/운영은 `stateAsOf`가 서로 다른 Run row의 최신 시각이지 공통 snapshot 시각이 아님을 보존하고, artifact/log의 `completedAt`을 실제 capture 시각처럼 표시하지 않아야 한다.

## 2026-09-22 고위험 쓰기 응답 결속 및 시각 스큐 규격 현실화

- Claude 위험도 목록 `7d75f810`의 HIGH 네 경로에 `ProjectCreateResponse`, `DiscoveryAdmissionResponse`, `MemberRoleResultResponse`, `ResourceOfferResultResponse`를 정의하고 POST/PUT 라우트에 strict FastAPI `response_model`을 붙였다. 조건부 `kernelNote`/`kernelReason`, nullable 필드와 실제 service 타입을 반영했다. 네 응답의 nullable/타입 경계 및 malformed service body HTTP 500을 TestClient로 고정하고, 네 선언을 제거한 대조에서는 네 negative test가 실패했다.
- 새 Claude 위험 재판정 `9454962`에 따라 `PUT /workspaces/{id}/status`도 HIGH로 올려 `WorkspaceStatusResponse`를 추가했다. status와 `allowedNext` 원소는 workspace lifecycle Literal로 제한하고, 독립 core 시험은 전체 전이 그래프와 상태 집합을 비교한다. `provisioning → ready` 실 PG 전이에서 다음 전이 집합 `deleting/suspended`도 고정했다.
- 프로젝트 생성과 제공량 변경은 추가 서비스 없이 disposable PostgreSQL fixtures로 실측 가능했다. PostgreSQL 16에서 기존 네 HIGH 응답과 workspace status 응답 전부를 실제 HTTP route/service/DB 왕복으로 확인했다: admission, project create, member role change, resource offer, workspace transition 합계 5 passed/0 skipped/0 failed/errors. 제공량 경로는 실제 `apply_capability_offer`를 불렀으나 inv kernel resource가 없는 케이스여서 `appliedToKernel=false/resource_not_registered`를 확인했다. 적용 성공(등록 kernel resource 존재) 분기는 별도 미검증이다. 명령/provenance/컨테이너 소유·정리: [[2026-09-22_write_response_real_pg_Codex]].
- 스큐 드리프트는 커널의 5초 런타임 적격성 필터를 유지하고 GOV-ALERT-001 라우팅 알람을 계속 governance-gated로 분리했다. ±5초 실측 보정, 통지 채널과 응답 담당이 미정이라 ERR-DESIGN-007 전체 채택으로 취급하지 않는다. 상세 근거/다음 후보: [[2026-09-22_write_route_response_binding_Codex]].
- 다음 행동: 통합에 착지된 response schemas, 5개 PG-backed route 시험, workspace transition graph를 별도 reviewer가 고정 SHA로 검토. 이번 slice에서 프로젝트 생성·자원 제공량 변경은 mock-only가 아니라 실 PG로 확인했다. 남은 근거는 제공량의 kernel-apply 성공 분기, hosted CI, 운영 HTTP/browser 인수다. 장비 시계 보정과 알람 라우팅 결정은 운영 인수 이후.

## 2026-09-21 미병합 branch의 회귀 가드 5건 재평가·회수

- Claude의 미병합 감사 `0979fe6`을 기준으로 `test_definer_rules.py`, `test_recovery_capability.py`, `test_recovery_drill_record.py`, `test_role_shape.py`, `test_alarm_check.py`를 현재 통합 구현과 각각 대조했다. 무조건 cherry-pick하지 않았다. 기존의 더 현재적인 guard로 대체된 3건은 옮기지 않았고, recovery recording의 현재 빠진 실패 무결성 속성 1건만 통합 DB 시험으로 다시 작성했다. alarm guard는 evaluator 함수가 없는 상태라 적용 불가로 남겼고 알람 기능 자체를 완료로 세지 않았다.
- 실측 중 definer 정책이 revision 0044에 남아 있고 migration 0045의 `consume_discovery_issue_budget(uuid)`가 빠져 있어 실제 audit baseline이 실패함을 확인했다. 정책을 현 head/digest/grant로 갱신했다. `test_migration_role_guard.py`의 0037 하드코딩도 Alembic current head 비교로 바꿨다.
- 새 recovery-record 시험은 integrity 실패인데 plausible RPO/RTO 값이 있는 경우 ledger outcome=`failed`, measured RPO/RTO=NULL을 확인한다. 측정치 유무만으로 record하도록 가드를 약화시킨 변형에서 1 failed/exit 1, 복구 후 exact merged SHA `7779d8cf8126f6a17ba41e34bf9ef97282ab3d68`에서 선택 suite 89 passed/0 skipped/0 failed, 1 warning (28.47s). 프로젝트 Python 3.14.6; disposable PostgreSQL 16, owner label 확인·정리 확인. 상세 명령과 분류는 [[2026-09-21_회귀가드회수_Codex]].
- 현재 CI 미실행. Independent review pending. 다음 별도 기능 카드는 GOV-ALERT-001 evaluator 구현/시험 설계이며, `test_alarm_check.py`만 이식하지 않는다.

## 2026-09-21 시험·워크플로·도구 변경연동 하드코딩 감사

- 시작 기준 local integration `938ea1b1d797e7c2ed4a81e9920cdab0cb9f620b`; 조사 중 integration이 `a451d69`, `a342f88`, `8da7791`, `7d75f81`로 전진해 매번 rebase했다. 최종 branch `agent/codex/hardcoded-value-audit`, worktree `C:/Project/SaintVision-Invion/.worktrees/codex-hardcoded-value-audit`. 감사 조사 당시 220 tests/66 tools/workflows 5개를 검색했고, helper 자체 시험 1개를 추가했다. 주 checkout의 타 agent 미커밋 변경은 수정하지 않았다.
- ontology ownership query의 48행은 task registry의 outcome edge 수에서 유도하고 task별 edge를 비교하게 했다. Workspace-upgrade 3, Node Docker compatibility 4, remote-workspace 7의 evidence 검사는 count 대신 독립적인 정확한 case/mode 집합, 누락·추가·중복 검사가 되게 했다.
- 고정 baseline(48 task/12 outcome), browser canonical journey, 11 run states, curated 역사적 migration priors, semantic query fixture cardinalities는 목적이 독립 수용 기준 또는 역사적 fixture라 고정 유지하고 바뀌는 시점을 기록했다. migration current head는 이미 Alembic graph에서 유도된다.
- Final provenance-wrapped checks at `2ee96ecca1cf82b953bda6aec3c2ca77b81e937d` passed: focused evidence inventory 4 passed; `check_docs.py` 24 source hashes/668 docs; `check_ontology.py`; related checker `py_compile` all exit 0. Python was `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6 on Windows 11; executor Codex; clean worktree; KST 2026-09-21 23:49:28. At measurement the branch was 3 commits ahead of integration `7d75f81033c0601364c76e47cacb3de11bd96b13`. Obsidian sync receipt is in History. Hosted CI was not run; independent review remains pending. Detailed scope, triggers, and limits: [[2026-09-21_하드코딩_변경연동값_감사_Codex]].
- `05c250e23c674a5a6ca72f83aaa848962323934f`를 integration에 fast-forward push했고, 후속 fetch에서 local HEAD와 원격 tip의 exact SHA 일치를 확인했다. 같은 SHA에서 focused 4 passed, docs 668, ontology, py_compile, Obsidian 1461/0/0이다. hosted CI 실행과 별도 reviewer의 고정 SHA 검토는 아직 pending이며, 작업 완료로 처리하지 않는다.
- 다음 첫 행동: 별도 reviewer가 integration SHA `05c250e23c674a5a6ca72f83aaa848962323934f`에서 후보 분류 및 변형 가드를 독립 검토한다. CI가 열리면 docs 및 관련 제품 workflow 실행. 새 migration revision이 외부 upgrade prior로 지원되는 시점마다 curated prior matrix를 확인한다.

## 2026-09-21 CI 검사 배선, issuer 쿼터 경계, Node 응답 계약

- `.github/workflows/docs.yml`에서 `check_contract_bindings.py`와 `check_frontend_integrity.py`를 자동 실행하게 했다. PostgreSQL CI 설정 소스상 backend `invowner`와 core `postgres`는 공식 서비스 이미지의 bootstrap superuser이며 통합 fixture가 요구하는 DB/role 생성 권한이 있다. hosted runner 실실행은 결제 대기다.
- ADR-097 및 0045 migration 주석에 쿼터 범위를 명시했다: `inv_discovery_issuer`와 `SET ROLE` 직접 SQL 경로는 10회/tenant/24h 제한을 받으며 PostgreSQL superuser와 credential 테이블 소유자는 해당 역할 바깥이라 쿼터 밖이다. 그 특권 계정은 별도로 제한·감사해야 한다.
- 12 worker barrier 동시 발급 시험을 추가했다. disposable PostgreSQL 16 실측에서 10 성공·2 안정 거부, credential/audit/budget timestamp 각 10개를 확인했다. `.venv/Scripts/python.exe -m pytest -q tests/integration/test_discovery_machine_credentials.py`: 5 passed, 0 skipped, 0 failed/errors; 소유 라벨 확인 후 시험 컨테이너 제거 및 잔존 0 확인. 사유·명령·환경은 History 참조.
- Node list/detail를 strict FastAPI response model, 공유 fixture, JSON Schema/생성 TS, Python provider와 frontend conformance 시험으로 묶었다. DB-free provider route 9 passed. fixtures에 telemetry를 합성하지 않았고 기존 `nodeObservation`에서 unavailable semantics를 유지한다. 합성 `nextCursor` 이름 변형은 Python과 Vitest 양쪽에서 실패해 원복했다.
- 로컬 검증: 전체 Core 778 passed/4 선행조건 skip/0 fail(errors 포함), Vitest 58 files/545 passed, TypeScript/Vite build 성공, schema 41, TS API contracts 16, bindings 29 fixtures/11 anchors, frontend integrity 0 violations, docs/ontology 통과. 엄격 nested capability schema 반영 후에는 focused node contract 9 passed와 schema/type generation check를 재실행했다. 전체 provenance/경계는 `[[2026-09-21_web_response_contract_map_workspace_Codex]]`.
- 다음 담당/행동: Claude fixed-SHA 독립 검토는 integration 착지 SHA 대상으로 대기. hosted Actions는 결제 복구 후 `docs`, `backend`, `core` 순으로 실행해 신규 게이트와 실제 PG role 권한을 확인한다. Gemini는 이 Node API slice에서 화면 변경을 하지 않았으며 브라우저 인수는 별도다.
- Fixed SHA candidate `6f638e30dc8087b81eddf58c6019c314b5f3dac5`는 Claude 최신 integration review `9ed6df9`와 Codex 구현을 병합한 clean tree에서 Core 778/4 skips/0 fail, Vitest 545, build 및 docs/schema/binding/frontend checks를 통과했다. PostgreSQL 동시성 대조는 별도 소유 PG16 컨테이너에서 5 integration tests passed. 상세 provenance/skip 분포는 History; hosted CI billing과 browser/device acceptance는 미완.
- **Node telemetry 층위 정정 (integration `775ff825`, 2026-09-21 22:41:59 KST, 소스 판독):** list는 heartbeat/identity만, detail의 `capabilities`는 정적 선언(capacity/unit/device metadata)이다. 인증 heartbeat로 수집한 동적 `ResourceSnapshot.used_quantity`는 placement 내부에서 읽지만 현재 이를 반환하는 HTTP read route는 없다. 따라서 기존 “telemetry가 capabilities로 노출된다”는 해석은 바로잡는다. 현재 strict node detail 계약은 정적 capability 용도로 유지하고, UI가 사용량을 원하면 인증·신선도·부재 의미를 갖는 별도 read contract가 필요하다. 평면 metrics 또는 capability 관측 중 어느 모델로 수렴할지는 사용자 결정이며 여기서 선점하지 않는다. 화면 의미는 Gemini 소관. 상세 근거는 History의 node telemetry clarification 부록.

## 2026-09-21 통합 migration-head 회귀 및 응답 계약 결정

- Claude fixed-SHA 보고에서 통합 Core의 단일 실패를 확인: `test_integrated_migration_keeps_both_published_histories`의 기대 head가 0044에 고정되어 0045에서 실패했다. 0045는 정상 head다. 시험은 Alembic `ScriptDirectory.get_current_head()`와 migration_graph AST head를 비교하고, rollback target은 현재 irreversible/merge 경계에서 유도한다. 메모리상 synthetic future reversible migration도 추가해 새 tip을 따라가며 rollback target을 보존하는지 검사한다.
- 수정 전 0044 literal 변형은 1 failed/exit 1 (`0045_discovery_machine_cred != 0044_model_registry_binding`), 수정 후 integration exact tip `a1833e3`에서 Core 전체는 769 passed / 4 reasoned skips / 0 failed / 0 errors다. Claude 기준선 770 passed/1 failed/4 skipped와 pass 하나 차이는 제거된 legacy project provider fixture 케이스다. Python은 `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6. 최종 provenance와 skip 이유는 History에 기록했다.
- LegacyProjectCatalogResponse는 `/v1/projects` 외 별도 producer·운영 호환 구성이 검색되지 않아 dead server contract로 판정해 API schema/fixture/test/generated types와 프런트 fallback을 제거했다. 이전 envelope를 허위 프로젝트 메타데이터로 바꾸지 않고 거부하는 DOM 없는 adapter 회귀를 고정했다.
- `GET /v1/nodes`와 `GET /v1/nodes/{node_id}`의 미계약 응답은 다음 Codex 작업으로 지정됐으며, 이번 후속에서 strict page/detail/capability response model, generated schema/type, shared fixture, DB-free provider/frontend conformance 시험으로 묶었다. telemetry는 계속 wire contract 밖에 있고 Gemini 소유의 화면 동작 변경은 하지 않았다.
- 상세 근거와 검증 경계: `[[2026-09-21_web_response_contract_map_workspace_Codex]]`. Integration landing 완료. 다음 Codex 작업: node list/detail response-contract slice; strict route response model과 fixture/provider test부터 추가하되 화면 변화는 Gemini 소유로 둔다.

## 2026-09-21 ADR-097 issuer quota follow-up

- User's interim operator-CLI issuance decision and Claude review of commit `a533b4b` are integrated. The DB quota hardening is commit `8b8ed81`; integration SHA `6dcd09dd69729e7651aae62b54bb6fd2d3858636` includes it and the intervening Gemini screen-state commit.
- Decision: the trusted issuer can still use distinct installation IDs to cause up to 500 open candidates. DBA-granted membership and audit reduce the actor set but do not prevent repeated operator error or a compromised issuer login. Adopt DB-enforced tenant limit 10 issuer-role issues per rolling 24h. It slows burst exhaustion but a persistent authorized issuer can still reach the cap over multiple days.
- Final rolling-window SQL was exercised on a newly owned PostgreSQL 16 container at integration base SHA `c08967c...`: full integration file 4 passed/7 warnings, exit 0, including ten issues, CLI refusal on issue 11, direct SQL refusal, and credential/audit/budget cardinality all 10. A threshold 10→100 mutation caused the quota test to fail at the expected issue-11 refusal assertion (1 failed/exit 1); source restored byte-for-byte and clean-threshold rerun passed. Containers were owned by exact name+label and removed; Docker returned to 48 containers. The quota patch was then pushed with the merge at integration `6dcd09d...`.
- Project interpreter: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` (3.14.6). Core/migration/response-contract tests: 39 passed/2 warnings. `check_docs.py`, `check_ontology.py`, and `git diff --check` exit 0. The final SQL test is a local PostgreSQL result, not CI or physical Node acceptance.
- At integration `6dcd09dd69729e7651aae62b54bb6fd2d3858636`, the provenance-wrapped focused unit/migration/response-contract run passed 39 tests/2 warnings, exit 0; docs and ontology checks passed at the same tree. Exact header and command are recorded in the ADR-097 History page. Obsidian export/check is current at 1450 managed/0 pending/0 conflicts.
- Next: obtain a separate fixed-SHA independent review of the quota migration/test commit `8b8ed81`. Go binary/physical-node onboarding and the organization's protected delivery channel remain operationally unverified. The long-term protected issuer API remains an open decision.

## 2026-09-21 ADR-097 운영자 CLI 임시 발급 경로

- 사용자 결정으로 ADR-097을 Accepted로 올려, 운영자 CLI가 tenant+installation 결속 `discovery:announce` 자격증명을 임시 발급하도록 구현했다. `inv_discovery_issuer`는 NOLOGIN 최소 권한 DB role이며, 지정된 운영자 로그인만 DBA가 멤버로 부여한다. 원문은 commit 뒤 interactive stdout에서 한 번만 보이고 DB/audit에는 SHA-256 digest와 비밀 아닌 메타데이터만 남긴다. 15분 만료, 30초 공지 간격, 재발급 회전 폐기, 명시 폐기와 승인/거절 시 자동 폐기를 구현했다. 승인된 보호 전달 채널의 실제 이름/설정은 저장소에서 확인되지 않아 운영 전제다.
- 발급 권한이 있는 운영자의 실수/계정 탈취도 tenant 후보 500건 한도를 소진할 수 있으므로, DB 트리거에서 tenant별 rolling 24시간 최대 10회로 제한했다. 동시 issuer 세션과 직접 SQL도 DB 경계에서 제한되고 감사된다. 이 제한은 burst 억제이지 장기 악용 방지는 아니므로 500 후보 한도는 여전히 별도 hard stop이며 발급자 수를 좁게 유지하고 후보 큐를 감시해야 한다.
- PostgreSQL 16 임시 Docker 컨테이너(768 MiB 제한, tmpfs DB, 고유 Codex 라벨)로 CLI 발급→실제 FastAPI 공지 및 linked-candidate 갱신→admission 자동 폐기→명시적 폐기와 403을 실행 확인했다. 일반 후보 조회 API에 동일 discovery bearer를 보내면 403이며, 타 tenant·잘못된 설치 ID·만료·폐기는 HTTP 403/no candidate였다. issuer 멤버십이 없는 실제 PostgreSQL login은 거부됐고 자격증명 row는 생성되지 않았다. tenant/expiry/revocation 각 가드를 단독 제거한 변형은 각각 targeted unit test를 실패시킨 뒤 복구했다.
- quota의 초기 DB 구현은 PostgreSQL에서 4 integration tests 통과(10건 허용, 11번째 CLI와 직접 issuer-role SQL 거부, counts=10)했다. 이후 코드를 더 엄격한 rolling 24h timestamp 배열 및 멤버 없는 NOLOGIN guard function owner로 강화했다. 이 최신 migration은 아직 DB에서 실행하지 않았다. 마지막 RAM은 918,116 KiB(<1 GiB 안전 바닥)라 컨테이너를 띄우지 않았고, 최신 소스 기반 focused/migration 39 tests는 통과했다. 따라서 현재 quota migration의 DB runtime은 미검증으로 분리한다. 실제 `inv-discover` 바이너리/물리 Node 발급-공지-enrollment-mTLS는 Go compiler 부재로 미실행이고 승인된 조직 전달 채널도 확인되지 않았다.
- Node runbook을 operator role grant, DSN 환경주입, dry-run/issue, one-time secret protected handoff, Node env injection, 후보 수동 확인, admission 자동 폐기, 긴급 revoke까지 이어지게 고쳤다. 장기 protected issuer API는 열린 결정이다. 상세: `[[2026-09-21_Discovery_기계자격증명_최소권한_계약제안_Codex]]` 및 `[[2026-09-21_discovery_machine_credential_ADR097_Codex]]`.
- 최종 export에서 Obsidian `sync_obsidian.py --apply`를 수행하고 뒤이은 `--check`는 1439 managed/0 pending/0 conflicts, exit 0이었다. 보호 전달 채널 미지정, 실제 Go Node 바이너리 미빌드/미실행, quota hardening의 DB runtime 재검증은 남는다.
- 보안 정정: 첫 실패 테스트의 assertion 출력에 disposable DB 합성 bearer 원문이 노출됐다. 해당 컨테이너 삭제 및 15분 TTL 종료 후, 테스트 코드는 값 없는 실패 메시지를 사용하도록 수정했다. 21:04 KST RAM 645,764 KiB preflight에서는 DB를 띄우지 않았으나, 이후 21:12 KST 1,607,300 KiB에서 출력 보호 변경을 포함한 통합시험을 disposable PostgreSQL로 재실행해 3 passed/7 warnings, exit 0을 확인했다. 고유 컨테이너는 소유 라벨 확인 후 제거 및 inspect 부재까지 확인했다. 자세한 경계 기록은 `[[2026-09-21_discovery_machine_credential_ADR097_Codex]]`.

## 2026-09-21 Codex 계약 서빙 앵커 버킷 감사

- 기준 SHA `6403611e1ffdb64e313b9ef5c9eabef56fcee11b`에서 ControlRunPage/ApprovalPage/ApprovalReviewView/ApprovalChallenge/TerminalTicketResult의 수동 앵커 5개가 유효 결과 시험만으로는 보호되지 않음을 확인했다. invalid serving output 시험을 추가했고 각 `validate_contract` 제거 변형이 targeted test를 실패시켜 현재 Bucket 2 5개 → Bucket 1 5개다. pool/capacity/placement/mutation/plan의 FastAPI response_model 6개도 metadata 및 5개 실제 malformed route response 거부 시험으로 검사했다. 이 Codex 범위의 확인되지 않은 Bucket 2는 11개에서 0개가 됐다. Claude 전체 7개 커널 결속 등은 별도 미결이다. 실행·변형 결과와 경계: `[[2026-09-21_Codex_계약서빙앵커_버킷감사]]`.

## 2026-09-21 ShardObservation 앵커 및 모델 관측 노출 판정

- `ShardRuntime._status`가 응답을 반환하기 전에 `validate_contract("ShardObservation", result)`를 실행하도록 앵커를 추가했다. invalid shard state를 fake DB에서 반환하는 회귀시험으로 서빙 경계 호출과 거부를 고정했다. focused 결과는 6 passed이며 앵커 제거 변형은 이 시험 하나가 `DID NOT RAISE DomainError`로 실패했다. 상세 판정과 검증 경계는 `[[2026-09-21_ShardObservation_앵커와_검증정보_노출판정_Codex]]` 참조.
- 모델 verify HTTP 관측과 온디맨드 재검증은 현재 미노출로 결정했다. DB에는 immutable commit만 있고 마지막 검증 결과/카운트 receipt가 저장되지 않으며 locality 검증은 요청·주체·epoch에 결합된 임시 결과다. 이를 현재 무결성으로 노출하지 않는다. 별도 lineage route도 아직 만들지 않는다. SaintVision `trace_model`은 실데이터를 갖지만 HTTP auth/tenant scope 및 공개 필드 계약이 미정이다. 화면은 합성 lineage/eval 점수 대신 명시적 미노출 상태를 유지한다.
- 검증은 Windows 주 checkout의 프로젝트 Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`로 이 worktree의 소스를 대상으로 한다. worktree-local venv는 없어 provenance wrapper의 첫 실행은 launch exit 127이었고, 이를 시험 실패로 집계하지 않았다. PostgreSQL-backed test, live route 및 browser acceptance는 실행하지 않았다. reviewer pending.
- Claude `85868a7`의 discovery tenant 최고위험 finding을 소스에서 확인했다. 기존 announcement route는 principal 없이 caller `X-Inv-Tenant`를 RLS scope에 사용했고 Node Agent 시험은 bearer가 없음을 기대했다. 후보 row만 쓰더라도 타 tenant 후보 주입 및 후보 500 한도 소진이 가능했다. route가 이제 `get_principal`을 요구하고 header mismatch를 DB 접근 전에 `AUTH-TENANT-SCOPE` 403으로 거부한다. Node Agent `inv-discover`는 `INV_DISCOVERY_BEARER_TOKEN` 환경 자격증명을 보내도록 수정했고 runbook을 갱신했다. FastAPI TestClient에서 다른 tenant 403/no DB call, 무인증 401을 확인했고 tenant compare 제거 변형은 mismatch 시험을 실패시켰다. discovery+shard suite 8 passed; check_docs 639 versioned documents 통과.
- 과거 상태 기록(20:18 snapshot, 아래 ADR-097 Accepted 항목으로 대체): 당시 `ResourceExplorer.tsx`의 tenant UUID는 Gemini가 session principal tenant로 교체해야 했고 bearer issuer 및 PostgreSQL 저장/운영 HTTP는 아직 구현 전이었다. 이후 operator CLI 발급부터 FastAPI 공지까지 실제 PostgreSQL로 검증했다. Go compiler 부재에 따른 `inv-discover` 바이너리/Node 시험 미실행과 보호 전달 채널 미확인은 여전히 남는다. model verify 및 lineage endpoint 미노출 판단은 유지한다.
- 과거의 Proposed ADR-097 및 “user decision pending” 문구는 20:18 시점 상태로 보존한다. 사용자가 같은 날 운영자 CLI 임시 경로를 승인했고 아래 20:49 항목에서 발급/폐기/만료 구현과 검증을 기록했으므로 현재 상태로 읽지 않는다. 장기 protected API만 열린 결정이다.

## 2026-09-21 PTY 티켓 wire 계약 및 인계

- `TerminalTicketInput`/`TerminalTicketResult` 기존 정본을 프런트가 따르도록 공유 요청·응답 fixture와 contract-only `terminalTicket` adapter를 추가했다. `TerminalTicketAuthFrame`을 JSON Schema에 명시하고 WebSocket 입구에서 검증하며, 응답 `websocketPath`는 workspace/session 경로 형식으로 제한한다. 어댑터는 티켓을 URL에 넣지 않고 `inv-terminal-v1` 첫 인증 프레임으로만 내보낸다. `WebTerminal` 화면이나 사용자 흐름은 Codex가 수정하지 않았다.
- `agent/codex/terminal-pty-contract` 후보를 integration에 fast-forward 반영했다. PTY no-row 회귀시험 `4ee1085`와 integration의 WorkspaceEditView 변화 및 Claude 보고서를 병합한 현재 Codex 후보는 `3412694`다. Claude의 `65f7b9a` 보고서는 ProblemDetails/NodeStopReceiptView 등 지정 계약은 sound로 판정했지만 PTY는 명시적으로 검토 범위 밖에 두었다. 따라서 PTY 독립 검토는 아직 없고, Gemini 화면 소유 경계도 Codex 승인으로 바뀌지 않는다.
- Gemini 전달 대기(사용자 릴레이): 빈 노드에서는 ticket 발급을 시작하지 말 것. 현재 API는 workspace/session만으로 발급하지 않고 명시적 `commandId`가 필요하다. UI는 선택된 실행의 commandId로 새 adapter를 호출하고, 반환된 `websocketPath` 및 subprotocol을 사용해 query string 없는 연결을 열며 첫 frame으로 adapter auth frame을 보내야 한다. 이 화면 통합은 Codex 범위가 아니다.
- focused Python/Vitest/schema/build/docs 결과와 명령은 `[[2026-09-21_terminal_ticket_contract_Codex]]` 참조. 실제 DB-backed PTY, live WebSocket/browser, CI, Claude 독립 검토는 별도 미확인이다.
- 최신 화면 코드는 Gemini 소유로 두고 소스 경계에서만 인계 finding을 남겼다: `TerminalSessionView`가 고정 placeholder `commandId`를 전달하고, `WebTerminal`은 응답 타입을 인라인 정의하며 잘못된/누락 `websocketPath`를 합성 경로로 대체하고 ticket 앞 12자를 로그에 남긴다. 계약 전용 `terminalTicket` adapter를 화면이 아직 사용하지 않는다. 이는 Codex의 소스 검토이며, Gemini의 UI 테스트·독립 DOM/browser 승인이 아니다. 화면 소유자는 선택된 실행 commandId 사용, adapter wiring, 경로 fallback 제거, ticket 전체/부분 로그 제거를 검토한다.
- 보안 경계 후속 확인: placeholder UUID는 형식만 유효하며 권한을 만들지 않는다. `TerminalService._current`에서 requester가 소유한 기존 승인 실행/현재 attempt/실행 상태/node/lease/terminal capability/project membership/workspace를 확인한 뒤에만 ticket insert가 가능하다. 없는 command row는 `403 AUTH-0070` ProblemDetails다. UUID가 실제 권한 있는 실행 row와 일치해야만 발급 가능하므로 화면은 합성 ID를 보내면 안 된다. 이 no-row 경로를 fake DB로 고정했고 focused 시험은 14 passed다. live DB 경로는 PostgreSQL DSN absent로 미확인이다. Gemini의 오류/사용 불가 UI 합격 기준은 History에 기록했다.
- Latest-source provenance (`3412694`, 2026-09-21 19:31:41 KST, clean worktree `C:/Project/SaintVision-Invion/.worktrees/codex-terminal-pty-contract`, project Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6, Node 24.17.0): terminal-ticket authority + terminal contract + ProblemDetails tests 14 passed, full Vitest 55 files/497 passed, check_docs 636 versioned documents all exit 0. DSN absent; no live ticket/HTTP/WebSocket test.

## 2026-09-21 ProblemDetails anchor와 receipt 이름 공간

- Claude drift sweep의 `ProblemDetails`는 backend 공통 오류 직렬화 경로와 동시성 overload 응답이 Codex의 공통 계약 소유 범위이므로 이쪽에서 처리했다. `problem()`이 정본 validator를 부르고 공유 fixture와 frontend 생성 타입 결속을 추가했다. `NodeStopReceipt` wire 정의는 변경하지 않고 화면 projection 타입을 `NodeStopReceiptView`로 이름 분리했다. Governance에 wire/view 접미사 규칙을 추가했다.
- Final tested source SHA `450971485eb2075b924e3e5b53ad3ed9c6d272c6`, branch `agent/codex/problem-details-contract`, worktree `.worktrees/codex-run-approval-observation-contract`, clean at execution. Project venv `.venv/Scripts/python.exe` 3.14.6, Node 24.17.0. Core 720 passed / 4 reasoned skips / 0 failures; full Vitest 52 files / 470 passed; schema 41 and API type 15 checks, docs 630, ontology, `tsc -b` and Vite build exit 0. PostgreSQL DSN absent; no live HTTP, hosted CI, browser acceptance or independent review.
- Evidence/provenance and skip reasons: [[2026-09-21_problem_details_contract_codex]]. Branch is pushed as `origin/agent/codex/problem-details-contract`; integration merge remains pending independent Claude fixed-SHA review. Obsidian paired sync at documentation snapshot `1ca5da0`: 1423/7/0 → export 7 → 1423/0/0; the follow-up report edit will be synced separately.

## 2026-09-21 재개: integration 선행 병합, UI-FB-03, 응답 계약 slice

- Gemini VF-GM-05 `39af7ca`를 먼저 포함하도록 최신 integration을 Codex 작업 브랜치에 병합한 뒤 `d438db8`로 fast-forward push했다. Claude run-log 계약 `c192cdc`도 포함한다. 병합 중 공통 진행판 충돌은 양쪽 기록을 보존해 합쳤다. 통합 tip은 `d438db89c18abc0fa5ab58215364871b8418301f`; 그 SHA를 detached clean worktree에서 직접 검증했다.
- UI-FB-03: `apps/web/tests/developer-studio-dom.test.tsx`의 이전 성공 로드 후 다운로드 401 시나리오를 직접 실행했다. 전체 DOM 파일 18 passed. `handleDownloadArtifact`에서 오류를 삼키고 `serverPayload || artifactData`로 낡은 캐시를 재사용하는 변형을 넣으면 해당 시험이 실패했다. 캐시 fallback만 복원하고 오류 즉시 반환을 유지한 단일 변형은 통과했으므로 그 시험은 결함을 막는 두 조건의 조합을 검증한다. 변형은 원복했다. 근거는 컴포넌트 DOM 경계이며 실제 브라우저/HTTP 인수는 아니다.
- Codex 응답 계약 slice는 run/approval 관찰, pool capacity, placement preview, pool create/member mutations와 distributed plan 응답을 canonical schema·생성 타입·공유 fixture·backend 및 frontend conformance test에 연결했다. 프런트 표시/요청 의미의 변경은 Gemini 소관이다. PlacementSimulator의 `binpack`/`spread`와 backend strategy enum 간 매핑은 추측하지 않고 Gemini 인계에 남겼다.
- Codex가 만든 프런트 계약 경로를 Gemini에 인계한다: `apps/web/src/contracts/kernel-observation.ts`, `apps/web/src/shared/api/runApprovalObservation.ts`, `apps/web/tests/run-approval-observation.test.tsx`, `apps/web/tests/run-approval-observation-contract.test.ts`. 이들은 adapter/type/conformance 범위이며 화면 렌더링을 바꾸지 않는다.
- 통합 SHA `d438db8` provenance, 명령, exit code, runtime, 실행 시각 및 남은 경계는 History `2026-09-21_web_response_contract_map_workspace_Codex.md`에 기록했다. Claude의 fixed-SHA 독립 검토는 대기 중이며, CI/실제 DB·HTTP/browser/장비 검증으로 과장하지 않는다.

## 2026-09-21 Integration 확인, UI-FB-03 review, run/approval contract follow-up

- 역할 경계를 `Agent 역할과 인계 계약`에 명시했다: Codex는 canonical 응답 스키마·생성 타입·backend validation·공유 fixture/적합성 시험을 소유하고, Gemini는 화면/UI 동작·접근성·브라우저를 소유한다. Codex의 `apps/web` 변경은 계약 전용 adapter/type/conformance tests에 한정되며, 표시·상태 동작은 Gemini 인계 대상이다.
- Gemini-first order is satisfied: remote integration has RunResult/Artifact frontend fixture binding `7ab955b` before Gemini Model Studio `3e9903f`. Both are now merged into Codex branch; merge SHA `5c6c3b6eeea6ce54e7142352eded3dea7563a3fa` is clean. On that fixed SHA at 18:07:37–18:07:39 KST, provenance-wrapped pool pytest passed 17 (2 deprecation warnings), full Vitest 45 files/413 passed, `tsc -b`, Vite build, schema export 41, API TS type check 15, `check_docs.py` (619 docs), `check_ontology.py`, and Obsidian read-only check 1412/4/0 all exited 0. Python `.venv` 3.14.6; Node 24.17.0; DSN absent, Docker present, Go absent. Codex branch is ahead of integration by six commits and not pushed to integration yet; next: push the branch, advance integration fast-forward, then verify integration SHA directly.
- Already-committed Codex contract-only frontend paths to hand off to Gemini: `apps/web/src/contracts/kernel-observation.ts`, `apps/web/src/shared/api/runApprovalObservation.ts`, `apps/web/tests/run-approval-observation.test.tsx`, `apps/web/tests/run-approval-observation-contract.test.ts`. These are wire adapter/types/conformance tests and contain no screen rendering change.
- The next response slice now binds pool capacity, placement-preview wire output, plan response, and pool create/member add/member remove responses. A pre-existing wire mismatch was found: backend preview candidate has `spare`/`headroom`, while ResourceExplorer expected `available*`/`eligible`; the contract adapter translates the backend wire shape to that view. `PlacementSimulator` remains a direct, self-shaped preview consumer and still sends visible `binpack`/`spread` request values while the backend accepts `single_node`/`data_parallel`/`sharded`. Do not guess a UI mapping; hand this decision and generated-type wiring to Gemini.
- Obsidian delivery for this evidence update: `--apply` at 18:09:05 KST exported 5 files with all 1412 destination hashes matching; paired `--check` at 18:09:17 returned 1412 managed / 0 pending / 0 conflicts. No writes to unmanaged files.

- 요청 순서대로 `agent/codex/workspace-response-contract-map`을 integration에 fast-forward하고 push했다: `beff6c1` → `614501a`; integration은 이후 `686eecf`와 Claude `5914f04`로 전진했다. 기존 통합 worktree의 uncommitted `ResourceExplorer.tsx` 변경은 건드리지 않았다. `core.yml` ignore 6개는 `686eecf`에서 확인했다. Schema 32, app response type 9, provider group 27 checks도 integration-derived content에서 통과했다.
- UI-FB-03: Gemini `beff6c1`에서 click-time 401이 캐시 성공을 재사용하지 않고 alert 후 중단되는지 소스와 DOM 시험으로 검토했다. 정상 로드 후 클릭 401 상주 test가 no `/artifacts`, alert, no `createObjectURL`을 단언한다. `developer-studio-dom.test.tsx`: 18 passed. Codex가 확인한 범위는 happy-dom/소스이며 browser/live HTTP/실제 파일 쓰기는 아님. Gemini가 기록한 mutation 결과는 확인했지만 Codex가 변형을 직접 재실행하지 않았다.
- 다음 계약 지도 slice는 `runApprovalObservation.ts`의 run/approval pages. API list는 App의 작업/승인 큐를 그리며, 누락/rename이 화면에서 빈 큐나 사라진 승인 행처럼 조용히 보일 수 있었다. 기존 `ApprovalPage`를 재사용하고 `ControlRunPage`를 canonical core schema에 추가했다. Provider는 `validate_contract`로 반환 전에 strict 검증하고 frontend adapter는 생성된 core schema TS type 및 동일 fixture를 사용한다. Route coverage path-only 검사는 변경하지 않았다.
- Base `686eecff924a5527e537c26228e2db87c00106ff`, branch `agent/codex/run-approval-observation-contract`, worktree `.worktrees/codex-run-approval-observation-contract`; project Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6, Node 24.17.0, Windows 11, PostgreSQL DSN absent, Docker present, Go absent. At 17:36:06 KST provenance-wrapped provider pytest passed 7; schema check passed 32; app API response type check passed 9; core contract generation, check_docs (614 versioned documents), ontology/SHACL and read-only Obsidian check (1407 managed/5 pending/0 conflicts) exited 0. At 17:36:35 KST, from `apps/web`, provenance-wrapped full Vitest passed 41 files/381 tests, `tsc -b` and Vite build exited 0. Core YAML structural parse found six ignore arguments and verified both image-lane files remain separately wired. These ran on dirty implementation/docs source based on integration 686, not on a final commit SHA.
- Negative control: removing `nextCursor` from shared run fixture made provider test exit 1 and frontend Ajv fixture test exit 1; restored afterward. Removing `ControlRunPage.required.nextCursor` and regenerating changed generated Pydantic, TypeScript, Go, and packaged schema outputs; snapshots were restored and generator rerun. This proves fixture and schema drift are visible; it is not a live DB or live HTTP check. The first full Vitest attempt exposed three old mocks missing the now-required `nextCursor`; mock fixtures were updated, and the full suite then passed 381.
- Remaining: PostgreSQL/live endpoint integration unavailable (DSN absent); Go tests unavailable (Go absent); Claude fixed-SHA review pending; Actions billing blocker; browser/physical operational acceptance separate. Next first action: commit/push this contract slice and hand off for Claude fixed-SHA review. Run/result/artifact wire responses remain the next top screen-level contract gap.

## 2026-09-21 Core CI red-green correction and project-list contract

- `core.yml` general pytest now excludes `tests/integration/test_workspace_upgrade.py` and `tests/integration/test_lan_storage_install.py`, matching their dedicated image-provisioned Core lane. Before correction, both files ran 15 tests, all skipped for absent opt-in owned Docker storage image; the Core no-skip JUnit gate exited 1. After correction, directory-level `--collect-only` over `tests` with the Core ignore set collected 2666/2668 and explicitly contained neither module. A positive control JUnit of six passed cases was accepted by the same no-skip gate. This proves the local collection/gate wiring, not full Core green or hosted CI.
- Bound the P1 `projectObservation.ts` project chooser: canonical business `projects/count` and compatibility-only historical `items` envelopes have separate strict Pydantic contracts, JSON Schemas, generated TS types and shared fixtures. `/v1/projects` now declares its strict response model. Provider tests and frontend adapter/schema tests consume the shared fixture. Failure if unbound: project choices can disappear or show IDs as display names.
- Provenance red/green: base `6cff94dca899a130fc733841e4fed765a5524708`, branch `agent/codex/workspace-response-contract-map`, checkout `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`, dirty source during measurement; Python absolute project venv 3.14.6, Node v24.17.0, Windows 11, PostgreSQL DSN absent/Docker present. Before JUnit: 15 skipped/0 failure/0 error and exact no-skip check exit 1. After exclusion: 2666/2668 collected, both image modules absent. Positive-control JUnit: 6 passed/0 skipped/failure/error, exact evidence check exit 0. Provenance artifacts are in `.work/core-image-optin-before.xml`, `.work/core-after-positive-control.xml`, and `.work/core-after-collect.txt` (ignored local evidence). These are local targeted checks, not Actions.
- Response tests: provider `tests/core/test_workspace_response_contract.py` 18 passed. Focused Vitest after final edits: 30 passed. Temporary required model-field mutation failed two provider assertions and made schema export check exit 1; removing `displayName` from the fixture failed three provider cases and two frontend cases. Both mutations were restored. See [[2026-09-21_web_response_contract_map_workspace_Codex]] for command timestamps and exact commit provenance.
- Remaining contract map: screen-local run/result/artifact, run/approval queue, placement/pool/mutation, storage resolve/replica/model, shard and node response shapes. UI-FB-03 independent approval and actual browser acceptance remain separate. CI remains billing-blocked; no full Core Actions execution claimed.

## 2026-09-21 fixed-SHA completion

- Final code+integration merge SHA `6573e57f61522a9c4d39e422a5c5a639200ccdba`, branch `agent/codex/workspace-response-contract-map`, clean checkout `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`. At 17:16:42–17:17:30 KST, project Python venv `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6 and Node 24.17.0 were used; Windows 11, DSN absent, Docker present. Provider contract 18 passed; all Vitest 40 files/369 tests passed; TS build and Vite build exit 0; 32 Pydantic JSON Schemas and 9 generated TS API response contracts match. `check_docs.py`, `check_ontology.py`, Core YAML parse/order/structure, and tests-directory collect-only assertions exited 0. Core collection: 2666/2668; both LAN image modules were asserted absent from general collection. A six-pass positive JUnit control had zero skip/failure/error and passed the same Core evidence assertion. The 15-skip pre-edit module JUnit failed that gate (red control). See History for exact prior/final SHAs and mutation evidence.
- Obsidian paired check/apply is recorded after the final History update. GitHub Actions was not executed (billing blocker); LAN Docker acceptance itself needs the Ubuntu/Linux image lane and remains unexecuted here. No PostgreSQL integration, deployed live HTTP, browser acceptance, or independent review is claimed. Branch is local-ahead of latest observed integration; push follows after final records and checks.

## 2026-09-21 CI image-lane preflight preparation

- Claude preflight's actionable setting failures were prepared: backend no longer collects three opt-in image suites without prerequisites; Core builds a checkout-derived `inv-node` agent image and supplies workspace-upgrade/storage image IDs and a temporary source root; desktop-browser builds the web proxy image from the completed Vite assets and executes its container/TLS tests. The static test-count literals were removed from browser and docker-host proof checks.
- Node-runtime prerequisites are already built in `core.yml`: checked-out Go `inv-node`, repository-built isolated runtime image, `INV_NODE_BINARY`, immutable `INV_NODE_IMAGE`, `INV_RUN_NODE_TESTS=1`, and PostgreSQL 16. This does not use a private prebuilt artifact. The Python test workload and web proxy use public `python:3.12-slim` and `nginx:1.27-alpine`; npm/Playwright and Docker image pulls require hosted-runner network access.
- Three workflow YAMLs parse and the structural check confirms provisioning/order/ownership. GitHub Actions was not run (billing blocked), so workflow runtime remains unverified. No additional workflow changes are justified until the first actual run supplies evidence.

## 2026-09-21 kernel approval mutation response contract

- `ApprovalChallenge`와 `ApprovalView` 응답을 canonical core schema, 생성 Pydantic/TypeScript 모델, 공유 fixture에 결속했다. backend challenge 및 fresh/idempotent decision 반환도 runtime validation한다. `kernelMutations.ts`는 생성 request/response 타입을 쓰고 adapter test는 실제 저장소 fixture를 사용한다. run GET/version 및 cancellation response는 아직 미계약이다.
- Provenance at dirty base `41fe0cb6695a15954a39db1ab6ad977a046ca21e`; branch `agent/codex/workspace-response-contract-map`; worktree `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`; Python `.venv/Scripts/python.exe` 3.14.6; Node `C:/Program Files/nodejs/node.exe` v24.17.0; Codex executor; DSN absent. Python focused tests: 19 passed/25 skipped, all skips require disposable PostgreSQL. Full Vitest: 38 files/346 passed. `tsc -b`, Vite build, API TS contract check (7) and canonical contract generation exited 0. Valid missing-`expiresAt` fixture mutation failed both provider pytest and Vitest; restored fixture passed. First mutation attempt was malformed JSON (trailing comma) and is not counted as schema rejection evidence.
- Integration DB bodies (25) were not executed, no CI/live HTTP/browser acceptance, no independent review. Next: Codex handles direct run/result/artifact contract with Gemini coordination for UI-FB-03; Claude fixed-SHA review remains pending. Detailed commands and caveats: [[2026-09-21_web_response_contract_map_workspace_Codex]].

## CI Node-runtime preparation status

Source inspection confirmed `core.yml` already compiles the checked-in Go `inv-node`, builds the isolated runtime image from repository sources, sets `INV_NODE_BINARY`, `INV_NODE_IMAGE` and `INV_RUN_NODE_TESTS=1`, and provides PostgreSQL 16. Thus no additional workflow change is needed to prepare this lane. This is configuration evidence only; Actions remains billing-blocked and was not executed. JavaScript Node.js is distinct from the Go node-agent.

## 2026-09-21 approval-review 계약 slice 및 CI 준비 판독

- 응답 계약 지도는 8개 functional adapter 모듈이며 화면 직접 호출 endpoint는 별도 scope다. workspace list/readiness, discovery candidates, storage contributions/locations에 이어 `approvalReview.ts`의 `ApprovalReviewView`를 묶었다. 실제 P1 영향은 사람이 승인하기 전에 보는 immutable workload/action/policy binding이다. shared synthetic fixture 하나를 생성 Pydantic model/Ajv schema test/adapter mock이 함께 사용하고 adapter 반환형은 생성 TS 타입을 쓴다. kernel challenge/decision mutations가 다음 P1; 전체 계약 지도가 완료된 것은 아니다.
- Initial tests were on dirty base `71bdb078c25056dc7fc675378825c40a739cd9a7`; final source is committed as `d22cc8c2490db2395d07db368688a541c0daaf8b`, branch `agent/codex/workspace-response-contract-map`, worktree `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`. At 16:20–16:20:56 KST, the exact commit had a clean tree. Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6; Node `C:/Program Files/nodejs/node.exe` v24.17.0; DSN absent; Codex executor. `tests/core/test_approval_review_response_contract.py` 3 passed; full Vitest 37 files/342 passed; schema export 28 match; `tsc -b`, Vite build, docs and ontology checks exited 0. No DB-backed API/CI/live HTTP/browser acceptance or independent review.
- CI source review: Claude's three CI-fail gate paths (two PG gates and `test_node_runtime.py`) align with source. All five workflows use Ubuntu per user report and checked files. `core.yml` builds Go `inv-node` and an isolated local image from repository sources, sets `INV_NODE_BINARY`, inspected immutable image ID `INV_NODE_IMAGE`, and `INV_RUN_NODE_TESTS=1` before pytest; PG16 service/DSN is configured. The browser workflow likewise provisions Chromium and asserts six journeys. This is source-configured, not GitHub Actions execution; Billing still blocks proof. Image/installer opt-ins not supplied by workflows remain web container, workspace upgrade, and LAN storage. Detailed scope/limitations: [[2026-09-21_web_response_contract_map_workspace_Codex]].
- Next: (1) Claude fixed-SHA review of approval contract binding; (2) Codex next P1 slice is `kernelMutations.ts`, keeping challenge/decision groups distinct; (3) coordinate screen-local run/artifact contract with Gemini UI-FB-03; then dual project-list envelopes, run/approval queues and lower-impact observation endpoints. CI can be confirmed only when billing unblocks; actual DB and browser evidence remain separate gates.

## 2026-09-21 response contract inventory and workspace slice

- Added an eight-module adapter inventory ranked by visible failure impact. It marks partial versus absent contract bindings and names the quiet failure each unbound shape can cause. Screen-local endpoints remain separately counted; discovery and storage are partial, and workspace list/readiness are now bound. This does not claim full adapter coverage.
- Bound project workspace listing and execution-readiness through strict provider models, generated JSON Schema and TypeScript, shared repository fixtures, FastAPI serialization tests, and frontend Ajv/consumer tests. The dual-envelope project list remains explicitly unbound.
- Rollback evidence: adding a required provider field caused the provider fixture test and schema drift check to fail; removing `allowedNext` from the shared fixture caused Python fixture validation and frontend Vitest to exit nonzero. Restored both mutations.
- Provenance at dirty base `4384bf7d7a29f988f06a7e21b2a97b7a6d559c65`, worktree `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`, branch `integration/all-agents-unified`: Python 3.14.6 via `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`; Node v24.17.0 via `C:/Program Files/nodejs/node.exe`; KST 15:59:54–15:59:55; DSN absent. Provenance-wrapped commands: workspace pytest 12 passed; focused Vitest 29 passed; schema export check 28 match; TS response generator 7 match; `tsc -b` exit 0. CI, live HTTP, browser acceptance, DB integration, and independent review remain pending. Full mutation/test detail is in [[2026-09-21_web_response_contract_map_workspace_Codex]].
- Latest check set after fast-forwarding to base `512daf7924e4...` (branch/worktree unchanged; dirty source slice), provenance-wrapped from 16:03:39 KST: Python contract 12 passed; full Vitest 36 files/340 passed; schema export 28 match; TypeScript response contract generator 7 match; `tsc -b`, `check_docs.py`, `check_ontology.py`, and Vite build exit 0. Python DSN absent. Prior source mutation checks and sync apply/check are itemized in the History record. No DB-backed integration, CI, live HTTP, browser acceptance, or independent review was run.
- Fixed-source handoff: `e460296eaa4cc6da7349fe50cd0cf452ddaa31d3` is pushed on `agent/codex/workspace-response-contract-map`. Provenance-wrapped post-commit checks on the clean exact SHA at 16:07 KST: provider 12 passed, full Vitest 36 files/340 passed, JSON schemas 28 match, TS contracts 7 match, `tsc -b`, docs/ontology and Vite build exit 0; Obsidian 1402 managed/0 pending/0 conflicts. DSN absent. Claude fixed-SHA review remains next; CI and DB/browser operational evidence are not claimed.
- Next: Claude fixed-SHA independent contract review; then rank and bind approval review/kernel mutation responses. Coordinate run-result/artifact contracts with Gemini's pending UI-FB-03 work. Do not treat route coverage as response-shape coverage.

## 2026-09-21 storage response contracts 확장

- `GET /v1/storage/contributions`와 `GET /v1/storage/locations`의 페이지 envelope를 strict Pydantic 응답 모델로 고정했다. JSON Schema와 TypeScript 타입을 생성하고 provider 직렬화 시험 및 frontend adapter/mock가 같은 저장소 fixture를 읽도록 연결했다. ResourceExplorer에서 nullable 용량 표시도 반영했다.
- 계약/fixture mutation 대조는 base `3f83e3fe271c5d95d3aceed499dcbd74ee4765f9`의 dirty worktree에서 15:04 KST에 실행했다. 최종 긍정 검증은 commit `9ff829859b6771fbccac58c2d0089bf6738edb53`의 clean worktree에서 15:07 KST에 다시 실행했다. Branch `integration/all-agents-unified`, worktree `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`, Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6, Node 24.17.0이다. 그 SHA에서 response contract pytest 12 passed; schema export check 24 schemas match; frontend contract generator 3/3 match; Vitest 35 files/336 passed; TypeScript `tsc -b` exit 0이다. Vite build는 같은 구현의 최초 dirty-tree run에서 exit 0이며, final clean-SHA rerun 전이다. 명령별 provenance는 [[2026-09-21_storage_list_response_contract_Codex]]에 있다.
- 양방향 mutation: 페이지 모델에 필수 필드를 추가하면 provider shared-fixture 테스트가 실패하고 `export_schemas.py --check`가 stale schema로 실패했다. 반대로 shared fixture 필드를 제거하면 Python 모델 검증과 Vitest/Ajv fixture 검증이 실패했다. 각 변형은 검증 뒤 원복했다.
- 한계: DB DSN은 absent라 DB 의존 storage integration 시험은 이 결과에 포함되지 않았고, CI·live HTTP·브라우저 인수·독립 리뷰도 아직 없다. 구현은 local verified/review pending이며 done이 아니다. 다음 owner는 Claude 독립 계약 검토; 다음 contract 후보는 화면 영향도에 따라 선정한다. 전체 route coverage는 endpoint 발견 검사이며 응답 shape 계약의 대체물이 아니다.

## 2026-09-21 최종 마감 상태

- Current integration tip before this documentation update: `03e0c6117ae90d16bee94514345312eb7f4afecc`; original product-suite verification ran at `cb505f6697beffe78a1cbdaee027f415003c55d3` in `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`. Claude's later commits added `tools/provenance.py`, its reporting rule, and the reference-only main-checkout sync convention; the tool was directly exercised at 5c1e9ef and document gates are rerun at 03e0c61. Do not attribute the old full suite to 03e0c61.
- Direct Python regression: `1338 passed / 1315 skipped / 2 deselected / 0 failed`; JUnit SHA and skip-reason distribution are in the integration audit. Claude independently reran the same code SHA in another clean worktree with identical results. Route coverage CLI exit 1 is the known `/v1/workspaces` static configuration-string false positive; route coverage regression tests 28 passed.
- Pending owner order: Codex route scanner false-positive fix; Gemini UI-FB-03 component transition tests and fixed-SHA handoff; CI only after Billing/`gh` auth; PostgreSQL/Linux/browser lanes when their prerequisites exist; approved AC-12 and physical-device acceptance separately. Public DSN credential validity/rotation remains with its owner. Anonymous Docker volumes remain user-decided preserve; do not reopen without explicit direction.
- Governance reporting policy is now v1.1.0 and requires SHA, branch, checkout, clean/dirty status, exact command/cwd, absolute interpreter/runtime and version, KST start/end, direct exit code, pass/fail/error/skip/deselected distribution, artifacts and executor/reviewer identities.
- `ROUTE-COV-FP-01` is resolved in the current integration worktree at `b234315`: the bare `/v1/workspaces` false positive came directly from `_CLIENT_HEAD` truncating actual workspace child-route templates before `${...}`; Nginx `location` metadata was a separate false-candidate form, not the direct cause of that bare path. Provenance-wrapped route tests: 30 passed; CLI: 31 static client shapes / 0 unserved, exit 0. Both exclusion rules have rollback mutants that fail their paired tests; a synthetic genuinely unserved path remains detected. Static-only, not live HTTP acceptance. Full-suite skip distribution from `cb505f6` remains: PostgreSQL DSN 1046, Linux 225, Docker/image 34, browser 7, other host/tool 3; 2 docker_host tests were deselected.
- Final correction register and Codex collaboration perspective: [[2026-09-21_하루정정대장과_감사잔여_Codex]]. Independent Claude view: [[2026-09-21_통합tip검사_독립대조_Claude]]. Detailed direct check evidence: [[2026-09-21_integration-tip-verification_Codex]].

Integration DSN landing and check_docs correction: `5c7ce9d` carried the merge without conflicts; integration is pushed. On the checked integration source, `proposal-3.txt` has 22 tracked files/28 URI occurrences/0 unmasked passwords and the guard/preflight tests passed 22. A follow-up found the link string corruption introduced in `b569318` by non-ASCII text through a Windows PowerShell native pipe; the filename itself was intact. Claude memory slugs were external references, not vault pages; these are now visibly marked `memory:<slug>`. Current full `check_docs.py` passes. Earlier checker evidence is corrected in the linked history.

2026-09-21 완료·push: 공개 `proposal-3.txt` 노출 14개(28개 비밀번호)를 `***`로 가리고, JUnit 증거 2회와 운영 절차 1회도 마스킹했다. `.venv\Scripts\python.exe -m pytest -q tests/test_check_docs_secret_guard.py` 3 passed, `tools/check_docs.py`와 `tools/check_ontology.py` PASS. 안전한 tracked scan상 마스크 후 문서 0건, 나머지 24개 URI는 테스트/임시 CI/로컬 개발 기본값으로 target 비밀번호와 일치하지 않는다. `sync_obsidian --apply`는 20개+2개, 최종 `--check`는 1390/0/0. 코드·문서 변경은 `5b6bfca`로 원격 push했다. 상세: [[2026-09-21_공개제안DSN_마스킹_Codex]]. 다음: DB 소유자 자격증명 유효성·회전 판단; 과거 public Git 이력 노출은 남는다.

2026-09-21 최신 결과: Obsidian은 사용자가 두 checkout을 같은 `b5ea2a5`로 맞춰 실행한 paired `--check`에서 각각 1373 managed/6 pending/0 conflicts(exit 0)였다. 사용자 `--apply`는 6 files export 및 1373 destination hash 일치를 보고했고 사후 check는 1373/0/0, 당시 vault 1384 files다. 이후 remote `a39fc13`에서 온 14개 regression evidence와 Codex 문서를 합친 18 files를 추가 동기화했고 1388 managed hash 일치, 사후 check 1388/0/0이다. 별도 recursive vault file count는 1399로 managed count와 다른 범위다. 이전 6/5는 snapshot이 다른 중간 측정이다. Codex는 사용자 실행과 본인 실행을 구분한다. `GET /v1/discovery/candidates` 계약 first slice는 `8532f705ecd2a53b0688f6bada6895b1efe403d5`로 구현·커밋했고 `agent/codex/discovery-candidates-contract`에 push했다. Python contract+route 36 passed, Vitest 전체 34 files/332 passed, schema/type checks, Vite build, check_docs/ontology 통과. Claude 독립 리뷰 대기. UI-FB-03은 Gemini 구현 대기이며 브라우저 인수 아님. 상세: [[2026-09-21_discovery_candidates_response_contract_Codex]].

2026-09-21 공용 sync state migration 완료: `default_state_path()`는 `git-common-dir` 사용. main/C:\vw가 같은 `.git/obsidian-sync-state.json`을 읽는다. 기존 1370-entry state는 이전 전 1372/10/0으로 검사한 뒤 이동했다. 최신 read-only check: main 1373/6/0, C:\vw 1373/3/0 (둘 다 exit 0, HEAD 각각 b5ea2a5/507a486). 문서 snapshot이 달라 pending 수를 같은 기준으로 비교하지 않는다. 두 쪽 모두 conflict 0, vault write 없음. `tools/test_sync.py` 14 passed/5 subtests; `--git-path` 되돌림에서 신규 linked-worktree test 실패. UI-FB-01/02 component boundary는 승인; FB-03은 all-errors-to-artifact mutant가 기존 13 helper test에서 살아남아 Gemini component-level test 대기. [[2026-09-21_sync_common_state_UI_FB_boundary_Codex]]

2026-09-21 sync explicit resolver(구현 당시 상태): `tools/sync_obsidian.py --apply --resolve-conflicts-from PATHS_FILE`은 UTF-8 경로 목록에 있는 **현재 충돌만** 저장소 바이트로 교체한다. 오래된/non-conflict 경로는 쓰기 전에 거부한다. 임시 저장소 시험 13 passed, stale guard 제거 mutation은 전용 시험을 실패시켰다. 당시 공유 vault 미적용 상태였고, 사용자 완료 실행은 아래에 따로 기록한다. 상세: [[2026-09-21_sync_obsidian_explicit_conflict_resolution_Codex]].

2026-09-21 UI-FB-01 새 DOM 시험 계약: 사용자 변형 실측상 `84f26ca` 단일 fetch 시험은 `items.length > 0` 회귀를 잡지 못했다. Gemini 인계 요구는 후보 있음→두 번째 빈 응답, 후보 있음→두 번째 오류 응답, error 상태+후보 데이터 3개 DOM scenario와 각 해당 mutant failure다. `apps/web` 코드는 수정하지 않았고 독립 검토 pending. mock response shape/backend drift에는 OpenAPI/Pydantic 단일 계약 생성 및 consumer/provider 양쪽 검증을 제안했다. [[2026-09-21_UI_FB_contract_readiness_review_Codex]].

2026-09-21 sync 사용자 실행: backup 뒤 14 explicit conflict paths 적용 exit 0, 당시 C:\\vw 후속 check 1370/0/0. 뒤이어 주 checkout에서 관측한 7 no-baseline은 실제 vault 충돌이 아니라 worktree별 state 위치 결함이었다. 기존 1370-entry를 migration 전 1372/10/0으로 검증해 common-dir에 옮겼다. 최종 main b5ea2a5 check는 1373/6/0, C:\\vw 507a486 check는 1373/3/0, 둘 다 exit 0/conflicts 0이다. 문서 snapshot 차이로 pending 수를 동일조건 비교로 쓰지 않는다. `--apply`하지 않았다. [[2026-09-21_sync_common_state_UI_FB_boundary_Codex]] [[2026-09-21_하루정정대장과_감사잔여_Codex]].

2026-09-21 response contract first slice 완료: `/v1/discovery/candidates`만 대상으로 strict Pydantic response model, generated JSON Schema/TypeScript type, shared JSON fixture, DB 없는 FastAPI provider serialization과 Ajv/Pydantic fixture 검증을 추가했다. Adapter와 frontend mock은 generated wire type 및 shared fixture를 사용한다. `route_coverage`는 path shape 전용이다. 35 Python tests, 28 Vitest tests, schema/type checks 및 production build 통과. 독립 reviewer Claude 대기. 상세: [[2026-09-21_discovery_candidates_response_contract_Codex]].

2026-09-21 sync EOL: LF/CRLF만 정규화하는 SHA 비교를 추가했다. 실제 바이트를 보존하고 683 fixture에서 667 EOL-only false conflict를 제거했으며 정규화 rollback 시험은 683 대 16 차이로 실패한다. 원격 `7404a6a`의 사용자 index 흡수 후 공유 vault `--check`는 14 no-baseline(Claude는 SAFE old residue 10 + whitespace 4 판정), 0 both-diverged다. Claude의 SAFE 근거는 Codex가 재실행하지 않았고 apply도 하지 않았다. 상세: [[2026-09-21_sync_obsidian_state_and_static_markup_audit_Codex]].

2026-09-21 Obsidian state 및 SSR 감사: `sync_obsidian.py`는 `--adopt-identical` 해시를 conflict exit 전 metadata에 원자 저장하고 기본 state를 현재 worktree Git metadata에 둔다. `.venv\\Scripts\\python.exe -m pytest -q tools/test_sync.py` 초기 5 passed, 이후 EOL 회귀 추가 후 8 passed; 두 rollback 대조 모두 회귀 시험을 실패시켰다. `apps/web/tests`에 static SSR 사용 7파일/27호출을 목록화했다. 두 UI 상태 스위트의 “query/fetch” 이름은 state props 주입일 뿐 effect 실행이 아님을 기록했다. UI tests 코드는 수정하지 않음. **정정:** 당시 state가 worktree별 `--git-path`에 있어 공유 vault 하나의 baseline으로는 부적절했다. 현재 기본은 common-dir이며 migration은 별도 이력 참조. [[2026-09-21_sync_obsidian_state_and_static_markup_audit_Codex]] [[2026-09-21_sync_common_state_UI_FB_boundary_Codex]].

2026-09-21 UI-FB fixed-SHA 경계 재검토: Gemini 구현 `c6dc915`에 대해 Vitest 322 및 route coverage 28 통과를 확인하고 네 가지 FB-01 되돌림 대조를 수행했다. 유령 초기값 복원은 기존 idle 시험을 실패시켰지만 catch에서 목록 비우기 제거, 빈 응답 회귀 복원, error 상태 guard 제거는 26/26 통과했다. 이 공백과 FB-02 local eligible 문구, FB-03 Output Verified 표시, 오류 배너 접근성 및 실제 component fetch 분기 시험 부족을 finding으로 기록했다. 구현 owner Gemini; Codex 승인 대기. 상세 및 실행 범위: [[2026-09-21_UI_FB_contract_readiness_review_Codex]].

2026-09-21 이어서 실행: tip `08f2a4d`에서 `.venv\\Scripts\\python.exe -m pytest -q tests/ --ignore=tests/integration -m "not docker_host"` 결과 **1324 passed / 489 skipped / 2 deselected / 0 failed**, 105.48초, exit 0. 별도 PostgreSQL DSN은 없고 Docker 사전관측 가용 RAM 788MB라 이번에는 disposable DB를 띄우지 않았다. 두 integration 파일의 66개 환경 skip은 미실행 유지. 다음: 격리 DB와 충분한 자원 조건에서만 해당 통합군 재개. 상세: [[2026-09-19_pytest_skip_baseexception_assertion_boundary_Codex]].

2026-09-19 skip-as-failure 경계 후속: 공용 `raises_without_skip`이 직접 및 `BaseExceptionGroup` 내부 pytest skip을 예상 오류를 대체하는 실패로 만든다. 일곱 파일의 원래 `pytest.raises` 35곳 중 실제 skip 기대 7곳은 보존하고 실패 기대 28곳을 보호했으며, helper 자체를 검사하는 두 개 회귀를 추가했다. pure four modules reject any module-level skip; integration modules retain Linux/PG skips and guard only error expectations. Seven named files were run/injection-checked; exact scope and KST evidence: [[2026-09-19_pytest_skip_baseexception_assertion_boundary_Codex]].

2026-09-19 recovery/JUnit 후속: Claude checkout `40e921b`의 5개 배치 JUnit 산술 합 2628/2192/1/0/435이며 단일 실행 아님. Full collect 177개 시험 파일과 batch manifest union 187개가 누락 0/중복 0으로 대조됐다. 이전 432/386/0는 manifest 없는 선택 배치 집계로 철회됐고, 421/386/18은 해당 과거 JUnit의 실제 값으로만 보존한다. `aeec9b3`는 18 setup errors를 이유 있는 skips로 전환했다. Codex는 archiver `/bin/true`와 `/bin/false`를 실제 PG16/Docker로 재실행해 running+ready+no host port 상태에서 각각 skip, 별도 exited/FATAL PG negative control에서 failure를 확인했다. `.venv\\Scripts\\python.exe -m pytest -q tests/test_recovery_drill_prerequisites.py`: 19 passed. [[2026-09-19_archiver_readiness_boundary_Codex]]

최종 착지 재검토: [[2026-09-18_Claude8b49981_최종착지와routecoverage_재검토_Codex]]. Claude `8b49981` 문서 정정과 PITR cleanup hold를 integration merge `0955202`로 반영했다. 최신 사용자 회귀는 `a04c17c`에서 1263/489/2/0(74초)이며 증가분 기원은 미대조다. 감사 12개 ID는 수정·검증 기록을 보유하고 route 실제 계약 불일치는 현재 0건이다. live HTTP 인수는 별도다.


고정SHA 후속 재검토: [[2026-09-18_PITR63fb71c와MJS02_bfb225e_재검토_Codex]]. PITR63fb71c cleanup 코드 hold 해제(대역13체크+보강5시나리오); 전체branch는 기존 문서 정정 잔여. MJS02 지정3항목 해소(격리집계3시나리오), Gemini 잔여는 backend의존 기본시험과 hasDesktopShell 상수 단언. 실Docker/PG/전체smoke 인수 없음.


## 오늘 감사 사이클 종료

MJS-02 인계 구체화(기준8a8e3db): Gemini owner/Codex reviewer. 상수 UI 3건은 API smoke PASS에서 제외·미검증 표기가 최소 수정이며, 실제 browser 관측을 선택하면 항목별 음성 대조가 필요하다. [[2026-09-18_Codex_감사사이클종료와다음세션인계]]의 처리 계획 참조. owner 수신·착수는 미확인. PITR/해당 수정본 대기, 새 감사 없음.


[[2026-09-18_Codex_감사사이클종료와다음세션인계]]: 사용자6feccd8 회귀1254/489skip/2제외/0failed(80초),1074대비180증가. 지도v1.5.0. FIX02검토·착지완료/PITR은Claude cleanup잔여수정대기. Gemini summary2건은bcec3e0 소스재검토·Codex10passed로해소. 별도MJS02/기존review/부분감사6영역/외부5조건을다음세션으로인계. 새감사·운영재실행없이종료.

## 최신 상태 지도 (기준 d7e7d13)

[[Codex 검증 상태 지도와 재개 조건]]이 현재 검증완료/미검증/외부대기와 재시도조건 정본이다. e2908a5 Claude sound 수신, 11e9f44 설정연결은 로컬46통과/Claude7e3de2a 독립소스검토 sound(수신). 기본회귀1eaf285 사용자1179/489skip/2제외/0failed. 최신image는f4b3f73에서4통과/2daemon-timeout실패/2operation-timeout skip, business-kernel-role미검증. VF운영인수0/5·formal0/48 유지. 외부4건과 AC-12 운영PITR 적용은 별도대기. 아래 고정SHA별 과거의 완료/차단 표현을 현재상태로 자동승계하지 않는다.

## CX-01 공유 개발 정본 착지 (2026-09-18)

- 사용자 우선 지시에 따라 `agent/codex/cx-01-canonical-landing`에서 최신 보안 제어 평면과 공유 integration 47a423e/810ab3b를 병합했다. PR34로 원격 integration에 병합 완료(fe4c04c). 검증·착지 SHA는 [[2026-09-18_CX-01_정본착지_Codex]]에 기록한다.
- 다음 작업의 계약/branch/필수 migration/Agent별 첫 행동: [[CX-01 제어 평면 정본과 Agent 재개 계약]]. 개별 storage API 파일 복사 대신 deps·0043·서비스가 일치하는 통합 SHA를 사용한다.
- 사용자 진행 승인은 유효하다. 공유 개발 정본 착지와 main 릴리스/운영 배포/CI/독립검토/5대 인수는 별도 상태다. 다른 Agent 수신은 미확인이다.
- 아래 과거 항목의 'CX-01 정본 미병합'은 당시 상태다. 최신 착지 결과는 위 History가 우선하며 전체 완료율은 재평가하지 않는다.


## Codex 승인과 연속 진행

- 사용자 Codex 담당영역 후속작업 승인 OK. 구현·검증·통합·인계를 반복확인 없이 진행한다. 승인과 실제CI/독립검토/운영인수 결과는 별도다.
- 로그인·프로젝트조회·승인상태 보강 누락을 실제browser실패로 확인하고 통합,273시험/build 및 실제HTTP browser6/6 통과. [[2026-09-18_VF-BROWSER-AUTH_Codex]].
- 다음ready 운영복원리허설 진행: source0023→복사본0043 업그레이드·기존row보존통과, 원본변경없음. 원격.225:18443은3회timeout,실장비인수대기.


## 2026-09-18 현재 확인

- 2026-09-18 재채점: **2800/4800 = 58.33%, 잔여41.67%**. 기존 48 task 동일가중 산식을 유지하고 S11-DB만 50→75로 갱신했다(물리 PITR 양·음성 게이트). formal 0/48과 VF 운영인수 0/5는 별도 분모이며 CI·전체 독립검토·운영 PITR 적용이 남아 있다. [[2026-09-18_Codex_진척률재채점]]
- PR30 실제Desktop→HTTP→PG: 관련57/브라우저2 통과. 이후 신규 검토commit 없음. 이번 Desktop 저장배치 crash2건 재현·수정, 프런트엔드256시험/build통과. [[2026-09-18_VF-DESKTOP-LAYOUT_Codex]].
- 다음: Gemini·Claude 이번변경 독립검토, 운영owner CI billing·SSO/PITR·5대 인수. 아래 이전 기록은 당시 상태이며 최신 합격 증거와 구분한다.


- 최신배포registry: Claude검토2commit수신, 승인시간/ORM캐시/동시등록4실패재현·수정, 최종82시험통과/실제image8통과. [[2026-09-15_VF-DEPLOYMENT-GUARD_Codex]]. 기존DB중복거부유지,새수정독립검토/CI/운영미완.


- 2026-09-15T16:13:30+09:00 배포레지스트리검토착수 base0db07c8. [[2026-09-15_VF-DEPLOYMENT-GUARD_Codex]].


- 최신 모델커밋관측: 현재project권한·저장manifest무결성검사·최소요약GET, 최종141시험(실제image포함)통과. [[2026-09-15_VF-MODEL-OBSERVATION_Codex]]. Claude독립검토/Gemini화면/CI·운영은미완.


- 2026-09-15T15:24:19+09:00 모델관측 착수: basec74ce2e/agent/codex/vf-model-observation. [[2026-09-15_VF-MODEL-OBSERVATION_Codex]].


- 최신 replica 관측: 소유자·활성폴더/단일SQL/현재가용성unknown, 관련137·실제image8통과. [[2026-09-15_VF-REPLICA-OBSERVATION_Codex]]. Claude독립검토·Gemini화면연결·CI/운영은미완.


- 2026-09-15T15:16:03+09:00 VF replica 관측 착수: base1f71d89/agent/codex/vf-replica-observation. [[2026-09-15_VF-REPLICA-OBSERVATION_Codex]].


- 2026-09-15T15:11:55+09:00 Codex VF-CX-02 검토 finding 판정 착수, base116e6e5/agent/codex/vf-model-review. [[2026-09-15_VF-MODEL-REVIEW_Codex]].


- [[2026-09-15_VF-CX-02_Codex_검증보고]]: ModelManifest/DataLocation FK·전체 bytes hash·lease/fence commit, Windows66/Linux49 통과. 독립 검토·CI·실장비 미완료. 다음 Codex VF-CX-03 locality 결속.


- 2026-09-15T11:54:32+09:00 VF-CX-02 착수: base 3efa507, 별도 agent/codex/vf-cx-02. [[2026-09-15_VF-CX-02_Codex_착수]]. owner Codex/reviewer Claude 미수신.


- [[2026-09-15_VF-CX-01_Codex_검증보고]]: canonical factory·fixture 격리·실제 인증/DB 보강, Linux 복원/definer/tenant 41 및 factory/account 5 통과. CI/독립 검토/운영 인수 미완료. 다음 Codex VF-CX-02; [[Codex VF 작업 현황]].


- VF-CX-01 착수 (2026-09-15T11:34:04+09:00): 원격 b9752a8 기반 별도 agent/codex/vf-cx-01, canonical factory 통합·fixture 격리 후 보안/PG 검증 중. owner Codex, reviewer Claude 미수신; [[2026-09-15_VF-CX-01_Codex_착수]]. 기존 57.81%와 VF 인수율은 별도.


- [[2026-09-14_APPROVAL-REVIEW-UI_Codex_검증보고]]:ab8b645 검토 snapshot화면·표시digest결정결속·미관측거부,210시험/build통과. 서버024a817과단일통합/배포미완료. 다음Codex격리통합/브라우저,Gemini UI,Claude독립검토. 전체57.81%유지.

- [[2026-09-14_APPROVAL-REVIEW-SNAPSHOT_Codex_검증보고]]:024a817 immutable 승인 검토snapshot/GET·approve/dispatch 결속 검사. 격리PG/HTTP48·계약10통과,운영DB/UI미반영. 다음Codex review화면연결,Claude독립검토,Gemini브라우저. 전체57.81%유지.

- [[2026-09-14_RUN-APPROVAL-OBSERVATION_Codex_검증보고]]: b0ecb5e Run/승인 정본 변환·임의 명령/예산/검토자 제거,182시험/build통과. 내용 미관측 요청 승인 보류; 다음 Codex digest결속 검토view, Gemini 통합/브라우저, Claude 독립검토. 전체57.81%유지.

- [[2026-09-14_LIVE-PROJECT-OBSERVATION_Codex_검증보고]]: 7b50ae2 실제 프로젝트 선택·Workspace 계약·미관측 Node 제외, 163시험/build 통과. 공유 통합/운영 배포/브라우저/peer 미완료. 다음 Codex Run/Approval 매핑, Gemini 통합/브라우저, Claude 독립 검토. 전체57.81% 유지.


- [[2026-09-14_SHARD-OBSERVATION-FIX_Codex_검증보고]]:ea42657 Gemini최신43640ee통합후샤드관측/새로고침정본화·미확인receipt성공표시제거·초기fixture제거. 최종140시험/build통과,공유integration/운영배포전. 다음응답unknown/project선택·브라우저/peer인수,전체57.81%유지.


- [[2026-09-14_FRONTEND-MUTATION-FIX_Codex_검증보고]]:별도frontend후보8037166 승인challenge/digest·일반취소version/실패상태보존,Vitest127/최종build통과. 공유App/RunDetail편집보존,아직통합/브라우저/peer미완료. Gemini후보병합·샤드연결/Codex재검토. Claude c5c014e는기존재현시험만독립확인. 전체57.81%유지.


- [[2026-09-14_FRONTEND-MUTATION-REVIEW_Codex_검증보고]]:frontend70ea3fb 독립검토 changes requested(FE-M01~05). 승인nonce/digest·취소version누락,취소실패성공표시,flat회수/fallback·임의관측·로딩오류. 실제격리PG/HTTP6개통과로현body422/상태보존·정본200확인(b95ab27). 다음Gemini수정/Codex재검토,전체57.81%유지.

- 최신 [[2026-09-14_CLI-OUTPUT-BOUNDARY_Codex_검증보고]]:dcd5f79 Agent CLI 수집 중 메모리 상한·timeout/incomplete·stderr 잘림 판정 보완. 실제 로컬 subprocess Windows24/Linux24 통과(동일24개). 실제 Provider/원격 인수·독립검토 미완료,전체57.81% 유지.

- 최신 [[2026-09-14_BACKUP-OPEN-GUARD_Codex_검증보고]]:3eced3b 보관 백업을 기존 ReadRoot로 읽도록 통합, Windows 관련42개 및 clean SHA 독립 PostgreSQL 복원130테이블/0037/tenant격리 통과. .225 TCP 불가·CI billing 차단·독립검토 pending, 전체57.81% 유지.

- 최신 [[2026-09-14_LEGACY-ROLE-REPAIR_Codex_검증보고]]:공용LOGIN재발관측,구Codex상주코드경로의위험fixture를4da131f로backport수정·격리PG21개통과. 실제재활성화주체는불명. 기존승인으로17:54:35 재폐기·권한보존. [[2026-09-14_INDEPENDENT-RESTORE_Codex_검증보고]]:33785f2 보관백업130테이블독립cluster복원/0037·replay/definer9·tenant격리통과. 원격/CI/운영인수미완료,전체57.81% 유지.

- 최신 [[2026-09-14_ROUTE-SURFACE_Codex_검증보고]]:8ef06eb Claude fef3292 경로도구통합·configured factory 측정/BusinessDispatch 선택범위·미등록fixture제외. 관련24개통과,추가lazyWS unit23개통과(중복합산안함). 다음Gemini 실제정본API/브라우저·Claude 독립검토·Codex 원격준비후7개. CI/운영인수미완료,전체57.81% 유지.

- 최신 [[2026-09-14_PROJECT-OBSERVATION_Codex_검증보고]]:4f518ea project 승인목록/상세·샤드조회·생성계약 연결. PG/HTTP16+승인계약10+실제후보컨테이너8 통과. 부모전체취소는 기존cancel,회수는receipt자동처리 정본. .225 접속불가·CI결제차단,전체57.81% 유지. 다음Gemini 정본계약 화면연결/Claude 독립검토/Codex 원격재연결 후7개시험.

- 최신 [[2026-09-14_MIGRATION-GUARD_Codex_검증보고]]:3742f11 Alembic 실제 진입점 그룹검사/별도PG13개 통과,221d253 CI opt-in 연결. 운영inv_app LOGIN 재발을 기존승인으로13:45:50 재폐기·권한/schema보존. 재활성화 원인 미확인. .225 offline/stale/observe,DB0023·kill switch유지. CI결제차단·독립검토/운영인수 미완료,전체57.81% 유지.

- 최신 [[2026-09-12_OFFER-SNAPSHOT_Codex_독립확인]]:51f4004 실제 offer중간 release는 기존Node/Resource잠금으로 차단·재시도성공, 관련12개통과. F1의 lease행만 잠근다는 전제는 실제호출과 달라 Claude재확인 요청. 새migration없음/0037유지. 업무·영속설정27개검증과 운영전환입력 준비 완료,실제OIDC/critical전환/원격7개/CI남음. 전체57.81% 유지.

- 최신 [[2026-09-12_BUSINESS-WORKSPACE_Codex_검증보고]]:14de71d 업무DSN/401정합·Windows설정volume·영속Workspace overlay, 실제컨테이너/DB/재시작/설정경계27개 통과. 운영 .225 fresh/observe·kill switch=true·DB0023 유지. 다음Codex role독립검토/운영전환계획,Claude 운영OIDC·계정/검토,Gemini 정본연결. CI차단,전체57.81% 유지.

- 최신 [[2026-09-12_SERVER-CONTAINER_Codex_검증보고]]:2bfd5fa 후보 backend 실제 image build/UID65532·DB·Workspace 설정/권한거부5개 통과. 일반 PostgreSQL16 head0037 적용. 원격 실행·운영SSO·Windows bind·영속Workspace 인수 미완료. 다음Codex business 활성화/영속volume·설정전달 검증,Claude 독립 검토. CI 결제 차단,전체57.81% 유지.

- 최신 [[2026-09-12_CONFIGURED-SERVER_Codex_검증보고]]:510ced4 정본 factory 필수 설정·readonly mount·/readyz 연결, 격리 PostgreSQL/실제 HTTP/Compose 경계14개 통과. 운영 SSO·후보 컨테이너·Workspace 활성화/원격 시험 미완료. 다음Codex 후보 backend build/비root mount/DB 확장 검증,Claude 독립 검토. CI 결제 차단,전체57.81% 유지.

- 최신 [[2026-09-12_DB-ROLE-REVOKE_Codex_운영적용보고]]:사용자 승인 후20:47:51 KST 운영inv_app NOLOGIN/password폐기 완료. 기존credential 인증거부·runtimeDB 접근·변경후Node fresh 확인,grant/RLS/membership 보존. **운영 로그인 폐기 승인대기 해소**. 다음Codex 정본server candidate/인증·DB 연결,각Agent 구fixture 갱신. 전체57.81% 유지.

- 최신 [[2026-09-12_DB-TEST-ROLE_Codex_검증보고]]:4ec4c5d 공용inv_app LOGIN/password 변경 제거·시험별 난수login/정리·배포 기본credential 제거. 별도PostgreSQL/Compose51개 통과,remediation SQL 별도컨테이너 거부/적용/replay 확인. **기존 운영credential 폐기는 critical 승인 대기**. 다음Codex 승인 후 서비스 의존 재확인/조치,각Agent 구fixture 갱신. 전체57.81% 유지.

- 최신 [[2026-09-12_LAN-RETAINED-BACKUP_Codex_검증보고]]:7a0a25b private 로컬 보관 파일 재검증→실제130테이블/조회행합계28726 복원·0037 upgrade/replay 통과,경계11 통과. 18100은 SQLite 로컬 작업대임을 확인. 다음Codex 별도 정본 server candidate/설정·인증·DB 검증,Claude 독립 검토. off-device/운영 인수 미완료,전체57.81% 유지.

- 최신 [[2026-09-12_LAN-RESTORE-UPGRADE_Codex_검증보고]]:04bd617 실제snapshot130테이블/조회행합계28165 복원,0037upgrade/전체replay/기존열보존·definer9·runtimeDBtransaction 통과,경계5통과. 원본0023/Node fresh 유지·폐기DB정리. 영속백업/독립클러스터/HTTP·운영인수미완료. 다음Codex 서비스호환성·실제배포계획,Claude독립검토. 전체57.81% 유지.

- 최신 [[2026-09-12_LAN-MIGRATION-PLAN_Codex_검증보고]]: b5493d7 운영0023→코드0037 미적용20개 계획, 열별SELECT/schema USAGE 판정 보완. 실제PG 포함15개/폐기용0023 upgrade·replay 통과. 운영 변경 없음. 다음Codex 복원 사본 리허설/호환성, Claude 독립 검토. 전체57.81% 유지.

- 최신 [[2026-09-12_LAN-STORAGE-READINESS_Codex_검증보고]]: f2a7fbc 읽기 전용 실제 운영 점검/경계6 통과. .225 online/fresh이나 observe 전용·kill switch 활성, storage 증명 관계2개 없음, 관측 역할 조회 제한, 공개 묶음 구형. 다음 Codex 실제 서비스 migration/역할/등록 연결 검토 후 후보 묶음, Claude 독립 검토. CI 결제 차단, 전체57.81% 유지.

- 최신 [[2026-09-12_STORAGE-WINDOWS_Codex_검증보고]]:e512b60 Windows 진입점/WSL request hash 준비·교체·재개 연결. 경계121(실제 PowerShell+모사WSL10 포함), 실제 Linux bridge1 통과. 본 서버 Ubuntu 없음, 실제 원격 경로·mTLS/Evidence 인수/CI/독립 검토 미완료. 다음 Codex 실제 PC 경로와 receipt 확인,전체57.81% 유지.

- 최신 [[2026-09-12_STORAGE-REPLACE_Codex_검증보고]]: f766146 보존 컨테이너/durable 교체/forward 재개, 실제 Docker11·경계111 통과. Windows/WSL 진입점·원격 .225·서버 인수/CI/Claude 검토 미완료. 다음 Codex wrapper/실제 mTLS·Evidence 연결, 전체57.81% 유지.

- 최신 [[2026-09-12_STORAGE-REPLACE-PREFLIGHT_Codex_검증보고]]:823b4b8 교체 전 읽기 점검·상태 해시·stale 재검사. 경계90/실제 Docker3 통과. **교체 실행기/forward 재개는 후속**이며 운영 Node 변경 없음. CI 결제 제한/Claude 검토 pending,전체57.81% 유지.

- 최신 [[2026-09-12_STORAGE-BUNDLE_Codex_검증보고]]: 9848afb 새 LAN 컨테이너 readonly mount·policy/Go receipt 대조, 실제 Docker2/경계62 통과. 기존 Node 교체·Windows WSL/원격 설치·서버 인수 미완료, CI 결제 제한/Claude 검토 pending. 다음 Codex 통제된 교체·forward 재개, 전체57.81% 유지.

[[전체 개발 진행 현황]] → 이 페이지 → [[Agent 지속 개발 운영 규칙]] 순서로 확인한다. 이 페이지는 현재 후속 카드 목록이며 이전 장문 보고서는 SHA별 근거다.

- 배정 owner: Codex. 독립 reviewer: Claude. 현재 착수/검토 기록은 아래 실제 SHA와 History로 확인한다. 작성자 보고를 독립 승인으로 바꾸지 않는다.
- 공통 Skill: agent-delivery v1.1.0, 역할 Skill core-reliability v1.0.0. 계획: [[Backend 최종 개발 계획]], [[DB 최종 개발 계획]], [[Storage 최종 개발 계획]].
- 계약: GUIDE-001, GOV-AGENT-001, GOV-GIT-001, ADR-INDEX-001 v1.29.0, [[Codex Workspace 편집과 PTY 및 원격 Git 계약]] v1.1.0, [[Codex 실제 실행 결과 조회 계약]]. 계약 변경 시 버전 갱신.
- 확인 기준: 2026-09-11T17:07:33+09:00. 준비됨(ready)은 아직 착수했다는 뜻이 아니다. 차단 카드 대신 선행 없이 가능한 ready 카드를 진행한다.

## 최근 확인한 진척

- [[2026-09-12_STORAGE-POLICY_Codex_검증보고]]:f9d69a8 기존 Node journal에 폴더/channel 독립 최소 버전·hash 영속화, 역행/같은 버전 변경 거부 및 로컬 시작 receipt. 실제 재시작 포함 Linux85 통과. 다음 LAN bundle 읽기 mount·policy 전달/교체·receipt 대조 연결. CI/독립 검토/운영 인수 미완료, 전체57.81% 유지.

- [[2026-09-12_STORAGE-VIEW_Codex_검증보고]]:9d7559e 인증 GET/현재 권한·소유자/저장 서명·Evidence 재검증, pending·expired·recorded와 currentHealth unknown 분리. Linux153/Windows25 통과. 다음 폴더-root policy 설치·교체/receipt 계약, Claude 독립 검토·Gemini 화면 연결. 전체57.81% 유지, CI/물리 원격 인수 미완료.

- [[2026-09-12_STORAGE-COMMIT_Codex_검증보고]]:fd0c081/0037 현재 프로젝트 요청 권한+등록 소유자·durable challenge/nonce·기존 Evidence/StorageCheck 원자 기록. Linux156/Windows DB22 통과. Studio 시작 바로가기 복구/로그인 세션 생성 확인. 다음 조회·운영 설치 연결, CI/Claude 독립 검토/원격 인수 pending. 전체57.81% 유지.

- [[2026-09-12_STORAGE-NODE-TRANSPORT_Codex_검증보고]]:688678d Go opt-in 폴더 설정/mTLS/실제 서명 sample과 Python 검증 연결. Linux 실제 통합130, Windows98 및 Go 경계 시험 통과. durable challenge/nonce 소비·기존 StorageCheck/Evidence 원자 쓰기는 다음 작업. 운영 .225/Windows native 수집/CI/독립 검토 미완료, 전체57.81% 유지.

- [[2026-09-12_STORAGE-SIGNED-SAMPLE_Codex_검증보고]]:124fe97 실제 ReadRoot sample·불변 Run/ChannelProof/root/catalog/nonce challenge·Ed25519 서명 검증, Windows124/Linux129 통과. 내부 Python 수집/검증 모듈이며 Go 배포·durable nonce·StorageCheck/inv.evidence 원자 기록은 아직 남음. CI 계정 제한/독립 검토/물리 장비 인수 별도, 전체57.81% 유지.

- [[2026-09-12_NODE-AUTH-COMMIT_Codex_검증보고]]:2830887 ASGI 인증서 오류 거부·proxy fallback 우회 차단·heartbeat 기록 transaction에서 현재 certificate/node row lock. 원본3개 오류 재현, Windows89/Linux89 통과. storage challenge/Evidence 쓰기 자체는 아직 미구현이며 다음 기존 Go nonce/ChannelProof/epoch와 Run-bound inv.evidence 연결 계약을 진행한다. 전체57.81% 유지, CI/peer/운영 인수 pending.

- [[2026-09-12_STORAGE-CHECK_Codex_검증보고]]:8c6805f/a7d0f5e 실제 local sample/READ ONLY·ReadRoot·hash/size 검증, Linux138/Windows105 통과. 입력 Node 이름은 신원 증명이 아니므로 운영 기록0. zero sample/과거 잘못된 healthy 판정을 보완했다. 다음 기존 Node 인증·epoch·challenge·root 버전/Evidence 원자 연결, Claude 독립 검토. S12-ST25→50, 전체57.81%/잔여42.19%, CI/원격 인수 미완료.

- [[2026-09-12_BACKUP-ROOT_Codex_검증보고]]:6a72b9d에서 허용 root·링크/교체 차단·시간 정보가 같을 때도 bounded 재읽기 hash 비교를 구현했다. 최종 Linux103/Windows80 통과. 다음71cf2c0 storage_check 실제 node binding·root 조율/독립 검토, 이후 durable 관측/Evidence. PR19 draft/CI 계정 차단/reviewer pending/실장비 인수 미완료. 전체57.29% 유지.

- 최신 복구 목표 판정: [[2026-09-12_RPO-CAPABILITY_Codex_검증보고]]. b49ecd3 Linux69 / core53 / upgrade23 통과. 설정만으로 운영 RPO를 확정하지 않고 실패/중단의 목표 달성 오기록을 서비스·0036 DB 제약으로 차단. 운영 PITR·CI·peer 인수는 별도.


- 최신 자격증명 등록·회전·회수: [[2026-09-12_CREDENTIAL-PROVISION_Codex_검증보고]], [[Codex 자격증명 등록 회전 회수 운영 절차]]. 76ba5ba Linux90/CLI4 통과. 운영 적용·Provider·CI·독립 인수 별도.


- 최신 자격증명 backend·Context/readiness 통합: [[2026-09-12_CREDENTIAL-BACKEND_Codex_검증보고]]. 제품0f5f4e8 Linux154/core53, migration22(74012b3) 통과. 실제 Linux/DB backend 확보, 외부 Provider·CI·peer·물리 원격 인수는 남음.


제품 c5f2154: 편집/PTY/Git와 최신 account/tenant/offer kernel 통합. 로컬 통합 402개·기본 301개·Linux Go 고유 43개·20개 migration 경로 확인. 전달 02e6188, PR19 draft. CI/독립 검토/물리 원격 인수는 남는다.

## 작업 카드

각 카드의 sprint/area/outcome/acceptance는 부모 task에서 상속한다. 원래 task owner를 바꾸지 않는다. CL-01은 독립 검토 업무다. 카드 상태와 원래 48개 task의 최종 done은 별개다. 각 카드의 base/branch와 실제 검증값은 착수 시 담당자가 고정한다.

| 카드 | 우선순위 | 상태 | 부모 task | 범위 |
|---|---|---|---|---|
| CX-01 | P0 | in_progress | S01-DB S04-DB S08-DB | 최신 3 Agent 변경 통합과 보안 검토 |
| CX-02 | P0 | in_progress | S01-BE S01-ST S08-ST | 운영·credential·Storage 공통 계약 확정 |
| CX-03 | P0 | blocked | S03-BE S04-BE S12-BE | 실제 원격 Node 실행 프로필과 7개 시험 |
| CX-04 | P1 | planned | S06-BE S06-DB S06-ST | 원격 개발 작업공간과 실제 Git 인수 |
| CX-05 | P1 | planned | S05-BE S05-DB S05-ST S07-BE S07-DB S07-ST | 5대 배치·지역성·샤드 통신·복구 |
| CX-06 | P1 | planned | S08-BE | Windows·GPU·BuildKit 실행과 격리 |
| CX-07 | P1 | planned | S04-ST S08-ST S11-ST | 제품 Storage 규모와 복구 무결성 |
| CX-08 | P1 | planned | S09-BE | 제한 Agent·Reverse-Ontology 실행 루프 |
| CX-09 | P1 | planned | S11-BE S11-DB S12-BE | 릴리스 통합·5대 부하/장애·최종 인수 |

### CX-01 — 최신 3 Agent 변경 통합과 보안 검토

- owner / reviewer: Codex / Claude; status: in_progress; priority: P0.
- 원래 목표/합격 조건: OUT-01, OUT-04, OUT-08 / AC-01, AC-04, AC-08.
- 다음 첫 행동: F1 잠금29c810f/F2 intent1460634 이후 Claude Context/readiness를 0f5f4e8에 통합했다. 새 backend/0035/ADR-077/078 독립 검토를 받고 CX-02 후속을 진행한다. Gemini 858763c의 정본 API/운영 인수 finding도 추적한다.
- 필요한 합격 증거: review finding별 해결 SHA/독립 검토, 현재 적용 DB 함수의 실제 다른 tenant 거부, 계약·migration 이력 보존. CI와 main 상태 별도.
- 선행/차단과 해소 담당: 검토할 코드 확보됨. 독립 승인자는 CL-01.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-02 — 운영·credential·Storage 공통 계약 확정

- owner / reviewer: Codex / Claude; status: in_progress; priority: P0.
- 원래 목표/합격 조건: OUT-01, OUT-08 / AC-01, AC-08.
- 다음 첫 행동: 서명 sample/0037 Evidence 원자 기록과 Windows bundle 연결은 구현·로컬 검증됐으며, 최신 보고를 따른다. 운영 OIDC 입력·최신 migration/프로필 배포 조건을 확인하고 실제 .225 설치 후 mTLS/7개 시험을 수행한다. 독립 검토·CI·운영 인수는 미완료다.
- 필요한 합격 증거: 미확인 항목에 결정 담당·차단 범위 명시, 비밀값 없는 버전 계약, Claude/Gemini가 구현할 입력·출력 합의. 실제 계정값은 운영자 확인 필요.
- 선행/차단과 해소 담당: 초안/계약 검토는 즉시 가능. 운영 권한/장비 정보 확정은 운영자 입력 필요.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-03 — 실제 원격 Node 실행 프로필과 7개 시험

- owner / reviewer: Codex / Claude; status: blocked; priority: P0.
- 원래 목표/합격 조건: OUT-03, OUT-04, OUT-12 / AC-03, AC-04, AC-12.
- 다음 첫 행동: 192.168.45.225 설치 결과의 profile/image·identity/journal 보존을 확인한 뒤 Python·CPU AI·시작 전 취소·실행 중 취소·실패·timeout·출력 복구를 원격에서 실행한다.
- 필요한 합격 증거: 실제 .225 endpoint·Node/이미지·Run/receipt/Evidence·hash·중복 방지·물리 정리/자원 반환 증거 7개. 관측 전용 상태 해소.
- 선행/차단과 해소 담당: 원격 설치 결과 미수신. 현재 lan-observe-v1; SSH/WinRM 실행 경로 미확보. 기존 설치 안내 사용.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-04 — 원격 개발 작업공간과 실제 Git 인수

- owner / reviewer: Codex / Claude; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-06 / AC-06.
- 다음 첫 행동: c5f2154 편집/PTY 계약을 실제 worker에 배포해 Node 재기동/대체 Node 재개를 확인하고, 지정 sandbox Git 저장소에서 CAS·2인 승인·응답 유실·reconcile을 시험한다.
- 필요한 합격 증거: 실제 원격 편집 bytes→승인→PTY/실행→결과 복원 일치. 지정 원격 Git의 실제 commit/충돌/불확실 dispatch 비재전송.
- 선행/차단과 해소 담당: CX-03, CL-02. 실제 Git 대상/credential/검증된 승인자 필요; 로컬 메모리 provider 시험은 이미 확보.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-05 — 5대 배치·지역성·샤드 통신·복구

- owner / reviewer: Codex / Claude; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-05, OUT-07 / AC-05, AC-07.
- 다음 첫 행동: 실제 제공량/lease/데이터 위치·링크 대역폭을 연결하고 다중 Node 샤드/부모 집계, partition·중단·중복 전달·재시작과 50동시 예약을 시험한다.
- 필요한 합격 증거: offered/lease/가용량 원자성, 데이터 해시·대체 Node 계보, Scheduler P95≤2초·취소≤10초·이탈≤60초·복구≥95%의 표본/기간/실측.
- 선행/차단과 해소 담당: CX-02/03과 추가 실제 Node 확보. 단일 호스트의 두 Node 시험을 5대 인수로 세지 않음.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-06 — Windows·GPU·BuildKit 실행과 격리

- owner / reviewer: Codex / Claude; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-08 / AC-08.
- 다음 첫 행동: 현재 Linux CPU 프로필 외 실행 backend와 GPU device 배정을 구현하고 허용 이미지·경로/ACL·권한·정지·자원 반환 경계를 시험한다.
- 필요한 합격 증거: 실장비 GPU/Windows/BuildKit 정상·거부·실패·취소 Evidence; Windows 호스트의 WSL Linux를 native Windows 실행으로 오인하지 않음.
- 선행/차단과 해소 담당: CX-02, 실제 장비/driver/격리 프로필 조사. 무제한 shell/host 권한으로 대체하지 않음.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-07 — 제품 Storage 규모와 복구 무결성

- owner / reviewer: Codex / Claude; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-04, OUT-08, OUT-11 / AC-04, AC-08, AC-11.
- 다음 첫 행동: 선정 Storage에서 50GiB 전송/중단 재개/hash·pin/GC/용량·다중 Node 복제를 검증하고 DB/object/Node journal의 epoch·fencing 복원 계약을 보강한다.
- 필요한 합격 증거: 대용량 실제 bytes/전송시간/정리 증거, 손상·보존 참조·빈/미확인 복원을 성공 처리하지 않음.
- 선행/차단과 해소 담당: CX-02, CL-03/04. 전체 복원 도구 구현은 Claude, 고위험 복원 계약·독립 검토는 Codex.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-08 — 제한 Agent·Reverse-Ontology 실행 루프

- owner / reviewer: Codex / Claude; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-09 / AC-09.
- 다음 첫 행동: Claude Context/Adapter 위에서 Prompt→Context→계획→제한 수정/시험→Evidence를 연결하고 버전·예산·종료 조건·정책 우회를 검증한다.
- 필요한 합격 증거: 실제 100 Prompt/30 coding 과제와 secret/주입/권한 평가, Prompt/Context/Harness/Skill/ROOF/Graph/Agent 버전 역추적.
- 선행/차단과 해소 담당: CX-02, CL-05. 고정 예시 평가 점수는 증거가 아님.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-09 — 릴리스 통합·5대 부하/장애·최종 인수

- **첫 항목(2026-09-22 결정 B, 코디네이터 위임 — Claude가 문서 소유자 대신 기입)**: PITR 활성(Tier-A, 보관 7일) + 외부 `wal_archive` 볼륨 사전 검증 3단계 + 실제 복구 드릴(AC-12 RPO/RTO 측정) + 정리 도구 `tools/pitr_archive_retention.py`(착지 예정). 재시작 창은 에이전트 무활동 시간(예: 다음 작업일 시작 전)에 코디네이터가 지정. 근거·절차: [[2026-09-22_CX-09_PITR_Tier-A_활성여부_결정준비_Claude]].
- owner / reviewer: Codex / Claude; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-11, OUT-12 / AC-11, AC-12.
- 다음 첫 행동: 전체 Agent 산출물을 같은 SHA에서 검토하고 장시간·5대 장애·upgrade/rollback·실제 복원·SLO와 최종 release manifest를 확정한다.
- 필요한 합격 증거: CI·독립 검토·운영 환경·5대 사용자 여정·복원/롤백·보안 합격 증거. 미측정 지표에 합격 수치 금지.
- 선행/차단과 해소 담당: CX-03~08, CL-06/07, GM-05/06, OR-02/03. CI 계정 해소는 운영자 외부 선행.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

## 작업 후 갱신할 최신 기록

아래 항목은 담당자가 매 작업 단위마다 갱신한다. 상세 기록은 History에 새 페이지로 남기며 이전 검증/실패 이력을 덮어쓰지 않는다.

| 항목 | 현재 기록 |
|---|---|
| 마지막 작업 / 카드 | CREDENTIAL-CONFORMANCE / CX-02 공통 검증 전달, 실제 backend 인수 대기 |
| owner / 진행판 / KST | Codex / 1.0.20 / 2026-09-12T00:47:43+09:00 |
| branch / base / 구현·검증 | agent/codex/workspace-bridge / 34d457c / clean8222f0b |
| 작업 | 내부 credential Protocol·39개 재사용 conformance·실제/모델 marker 분리 |
| 검증 | 합성 모델39+결함검출8=47 pass/skip0; backend 선택 exit5(모델 제외) |
| CI / peer / 운영 | CI 시작 전 계정 제한, Claude reviewer pending, 실제 backend/운영 인수 미완료 |
| 다음 첫 행동 / owner | 실제 backend 연결 / Claude; 독립 scope·회수·descriptor 검토·경합 시험 / Codex |
| History / PR / sync | [[2026-09-12_CREDENTIAL-CONFORMANCE_Codex_검증보고]] / PR19 / History 영수증 |

## 2026-09-11 18:53 Codex 수신·검증·후속 기록

- 실제 owner Codex, 진행판 시작 v1.0.14→현재 v1.0.15, base d14db0a→구현 5fc1116. CX-01/CX-07 일부 구현 전달, 카드 전체 done 아님.
- 작업: 단일 recovery_drill에 정본 감사·false-pass 거부·양쪽 RLS·시각/fencing·실제 DB 기록 연결.
- 확인: Linux64/core22/Go3 exit0, CI6 시작 전 계정 제한, 독립 reviewer Claude pending, 운영 인수 미완료.
- **다음 첫 행동 CX-01**: Claude cdf98ad F1을 두 session의 실제 함수 시험으로 재현하고 held를 단일 snapshot으로 고정하는 forward 변경. F2는 Node 중복 방어 유지하며 pre-dispatch intent/감사 정합성 검토.
- 이어 CX-02 credential/Storage 계약. CX-03 실제 원격 설치 receipt 미수신으로 blocked. PR19에 같은 변경 전달, Obsidian hash는 최종 영수증에 기록.

상세: [[2026-09-11_RECOVERY-INTEGRATION_Codex_검증보고]]. 작성자 원래 기록/진척 주장은 보존하며 위 검토와 구분한다.

## OFFER-SNAPSHOT 최신 작업 → 확인 → 다음

- 2026-09-11T23:56:33+09:00 / CX-01 / owner Codex / reviewer Claude pending. base ade6721 → clean 검증29c810f, PR19.
- 작업: F1 실제 API/lease release 경합 회귀. 확인: 실 PostgreSQL36개 exit0, 잠금 한 줄 제거 변이 exit1, 원본 복구. d14db0a에도 잠금이 있어 F1 전제 재검토를 요청한다. 제품/migration 변경 없음.
- 다음 첫 행동: F2 pre-dispatch intent/sequence/hash 감사와 응답 유실 정합성 보강; 이후 CX-02. 과거 snapshot 수정 계획은 최신 실험으로 대체.
- [[2026-09-11_OFFER-SNAPSHOT_Codex_검증보고]], [[2026-09-11_OFFER-SNAPSHOT_오류와해결]]. 전체57.29%(표시55%) 유지. CI 계정 제한·peer·원격 인수 미완료.

## PTY-INTENT 최신 작업 → 확인 → 다음

- 2026-09-12T00:24:11+09:00 / CX-01 / owner Codex / reviewer Claude pending. base fd32eda →1460634, PR19.
- 작업/확인: intent/완료 분리와 replay 보호, Linux61/core25/upgrade21 통과. [[2026-09-12_PTY-INTENT_Codex_검증보고]]. 다음 첫 행동은 CX-02 운영 credential 참조/회수/로그 및 Storage 계약이다. F1/F2 독립 검토·원격 실행 인수·CI는 남는다.

## OPERATING-CONTRACT 최신 작업 → 확인 → 다음

- 2026-09-12T00:32:00+09:00 / CX-02: [[Codex 운영 자격증명과 Storage 계약]], [[운영 환경 입력과 Agent 인계]] 전달. 내부 reference 문법 결정과 runtime resolver 구현/운영 계정 등록을 구분한다. 다음 Codex 보안 conformance와 독립 검토, Claude provider 구현, Gemini unknown/readiness 반영. 전체 진척은 운영 인수 전 임의 가산하지 않는다.

## CREDENTIAL-CONFORMANCE 최신 작업 → 확인 → 다음

- 2026-09-12T00:47:43+09:00 / CX-02:8222f0b 공통 Protocol/39개 suite 및 모델 검출력47개 확인. [[Codex 자격증명 보안 검증 인계]]에 actual harness 요구·모델 한계를 고정했다. 다음 Claude 실제 provider 연결, Codex 구현 독립 검토와 실제 inode/회수 경합 검증. 운영/실장비 증거는 아직 없다.


## 최신 작업 — BACKUP-LEDGER

420b81c Linux63/core50 완료, [[2026-09-12_BACKUP-LEDGER_Codex_검증보고]]. PR19 draft/CI 계정 차단/Claude 독립 검토 pending. 다음 첫 행동: d63717f snapshot 프로젝트/관측시점/순서 계약 확정 및 수정본 검토, ade5bb8 AC-12 집계의 운영 증거 범위 검토. CX-03 프로필 미수신 상태는 별도.


## 최신 작업 — PERMISSION-SNAPSHOT

9755c60 Linux74/core55, [[2026-09-12_PERMISSION-SNAPSHOT_Codex_검증보고]]. d63717f P1/P2 보완, ade5bb8 원본 집계 과장4개 재현/수정. PR19 draft/CI 계정 제한/Claude 독립 review pending. 다음: 실제 운영 Evidence 수집·검증 경로와 최신 변경 공통 계약 검토; 원격 profile 수신 시 CX-03 실제7개.


## 최신 작업 — BACKUP-VERIFY

4ddb622 Linux78/Windows DB60, 원본 실제5개 오류를 보완. [[2026-09-12_BACKUP-VERIFY_Codex_검증보고]]. PR19 draft/CI 계정 차단/Claude review pending. 다음 첫 행동: hash_file의 허용 root·descriptor/handle·링크/교체 경계; 그 뒤 durable 검증 관측/Evidence 연결. 02:30 .225 online/fresh, lan-observe-v1로 원격7개 미수행.


## 최신 작업 — BACKUP-ROOT

[[2026-09-12_BACKUP-ROOT_Codex_검증보고]]:6a72b9d에서 허용 root·링크/교체 차단·시간 정보가 같을 때도 bounded 재읽기 hash 비교를 구현했다. 최종 Linux103/Windows80 통과. 다음71cf2c0 storage_check 실제 node binding·root 조율/독립 검토, 이후 durable 관측/Evidence. PR19 draft/CI 계정 차단/reviewer pending/실장비 인수 미완료. 전체57.29% 유지.


## 최신 작업 — STORAGE-CHECK

[[2026-09-12_STORAGE-CHECK_Codex_검증보고]]:8c6805f/a7d0f5e 실제 local sample/READ ONLY·ReadRoot·hash/size 검증, Linux138/Windows105 통과. 입력 Node 이름은 신원 증명이 아니므로 운영 기록0. zero sample/과거 잘못된 healthy 판정을 보완했다. 다음 기존 Node 인증·epoch·challenge·root 버전/Evidence 원자 연결, Claude 독립 검토. S12-ST25→50, 전체57.81%/잔여42.19%, CI/원격 인수 미완료.


## 최신 작업 — NODE-AUTH-COMMIT

[[2026-09-12_NODE-AUTH-COMMIT_Codex_검증보고]]:2830887 ASGI 인증서 오류 거부·proxy fallback 우회 차단·heartbeat 기록 transaction에서 현재 certificate/node row lock. 원본3개 오류 재현, Windows89/Linux89 통과. storage challenge/Evidence 쓰기 자체는 아직 미구현이며 다음 기존 Go nonce/ChannelProof/epoch와 Run-bound inv.evidence 연결 계약을 진행한다. 전체57.81% 유지, CI/peer/운영 인수 pending.


다음 Codex 첫 행동: ADR-094 preflight를 전제로 durable 교체 단계와 중단 지점별 forward 재개 구현.


다음 첫 행동: Codex Windows/WSL 교체 진입점과 명시적 정책/receipt 전달·출력 검증 연결.

다음 Codex 첫 행동: 실제 원격 Ubuntu/Docker 경로·현재 policy와 receipt를 확인하고 서버 mTLS/Evidence를 연결한다.


## 2026-09-12 RETAINED-BACKUP 외부 보고와 우선순위 정정

Evidence/obsidian-proposals-20260912-retained-backup의 원문3개와hash를 보존했다. Gemini는 Idempotency-Key/route404 판별·WebTerminal apiClient와Vitest114를 보고했다. 작성자 보고이며 실제 커널의 idempotency 저장·응답 계약과 운영 인수는 검토 대기다.

Claude는 저장소의 기본 시험 credential로 운영DB 로그인이 가능하다고 보고했다. Codex가 실제 READ ONLY metadata를 확인한 결과 inv_app LOGIN=true,superuser=false,bypassrls=false,inv_kernel LOGIN=false이며 조회 순간 해당 그룹과inv_lan_runtime active session은0이었다(상시 미사용 증거 아님). 실제 password 인증은 이번 Codex 확인에서 재시도하지 않았다. deploy/init-db.sql의 고정 password LOGIN 생성뿐 아니라 tests/conftest.py의 기존 app_engine fixture에도 공용 inv_app 역할을 고정 password LOGIN으로 바꾸는 코드가 있어 재발 경로다. 폐기용 DB라도 역할은 클러스터 전역이라는 점을 반드시 수정해야 한다.

최우선 다음 Codex: init SQL/compose 고정 로그인 제거, 테스트별 난수 login 역할 생성·정리로 공용 그룹 역할 변경 금지, 해당 회귀 검증. 그 뒤 실제 서비스 의존성과 권한 확인을 마치고 운영 inv_app NOLOGIN/password 폐기 조치를 별도 critical 운영 변경으로 제시한다. 현재 사용자 지침에서 critical 변경은 자동 승인 범위에서 제외되어 있으므로 이번에는 운영 credential/역할을 변경하지 않았다. 기존 정본 서버 candidate 작업보다 이 항목을 먼저 수행한다. 미래KST 원문은 현재 실측 시각으로 채택하지 않으며 전체57.81% 유지한다.

## VF 서비스 통합 최신 기록

2026-09-15T14:27:00+09:00 / Codex / base dd04562 / agent/codex/vf-service-integration. Claude7ef9a3c 독립 검토에서 pin 이탈·URI 경계 결함4개 재현,0043·용량·parser 수정. 최종통합d237d30/PR23: 전체1779 passed/139 skipped, 최종통합115/115, image/설정거부 통과. CI billing차단. [[2026-09-15_VF-SERVICE-REVIEW_Codex]]. Claude 재검토/CI/운영 인수 pending. 다음 Codex 전달·Claude 수정 재검토.

## VF 저장소 API 착수

2026-09-15T14:59:30+09:00 / Codex / base58f0370 / agent/codex/vf-storage-api. [[2026-09-15_VF-STORAGE-API_Codex]]. 등록자 소유권과 조회전용 dispatch 검증.

## VF 저장소 API 검증·다음 행동

등록자scope·active·메서드경계 구현,123/123·image8/8·문서/ontology통과. [[2026-09-15_VF-STORAGE-API_Codex]]. 다음 Claude 독립검토, Gemini 실제FileExplorer조회연결, Codex replica/ModelManifest 관측API계약. 운영인수/CI별도.

VF-STORAGE-API 최종: b3faf98/PR24,123시험·image8시험통과,CI6run billing차단,Claude재검토/Gemini조회UI연결대기. [[2026-09-15_VF-STORAGE-API_Codex]].


## 모델 독립 검토 판정 인계

[[2026-09-15_VF-MODEL-REVIEW_Codex]]: Claude 실제 소스검토3commit 수신, 기존Schema1024상한 확인/117시험통과/상한제거 mutation1실패. [[모델 레지스트리와 실행 Manifest 권한 경계]] 결정. 이번 판정 재검토·CI·운영 미완; 다음Codex 소유자범위 replica관측API.


- 전달완료: 모델검토e735df9/PR25 및replica fc34f37/PR26 push. 후자137+image8통과,CI34936437627/572/523 billing차단. 제한Obsidian동기화완료. Claude독립재검토/Gemini4GET실화면/Codexfinding통합이 다음이며 운영인수0/5유지.


- 모델관측20ff7c2/PR27 push·로컬141(image8포함)통과·Obsidian제한동기화완료. CI34937280022/029/005 billing차단. 다음Claude독립검토/GeminiModelStudio관측/Codexfinding통합, 운영인수0/5유지. [[2026-09-15_VF-MODEL-OBSERVATION_Codex]].


- 배포registry653aea0/PR28 push·최종82시험/image8통과·제한Obsidian동기화완료. CI6run billing차단. 다음Claude신규수정검토/Gemini실화면/Codexfinding통합. [[2026-09-15_VF-DEPLOYMENT-GUARD_Codex]].


- Desktop통합착수 base7d18b62. [[2026-09-15_VF-DESKTOP-INTEGRATION_Codex]].

- Desktop 실조회 통합: GET 저장소/모델 관측, fake-success 제거, 로그인·프로젝트 경계 유지. build/242 tests 통과; 실제 Chromium HTTP-fixture 검증. [[2026-09-15_VF-DESKTOP-INTEGRATION_Codex]]. CI/독립검토/운영 별도, 다음 Gemini·Claude 검토.

- PR29/코드81987d3 push 완료. build242시험/브라우저fixture7항목통과, CI billing 실행전차단; scoped Obsidian 전달. 다음 Gemini·Claude 독립검토, 실backend/SSO/운영 미완료.

- 2026-09-15T18:54:05+09:00 Desktop 실HTTP 검증 착수, base0fcbea4/agent/codex/vf-desktop-http. [[2026-09-15_VF-DESKTOP-HTTP_Codex]].

- Desktop 실HTTP/PG: 관련57통과, 명시적browser2재검증통과/0skip. Claude b30a723 배포권한보강 독립검토 수신(Desktop검토 아님). 전용browser CI 추가. [[2026-09-15_VF-DESKTOP-HTTP_Codex]]. 다음 Gemini·Claude 이번변경검토/운영owner CI·SSO·장비.

- PR30/7c55fea push: 실제브라우저→canonical HTTP→비소유자PG 검증, 관련57/최종browser2통과. 전용Desktop CI도 billing실행전차단. [[2026-09-15_VF-DESKTOP-HTTP_Codex]], 다음 Gemini·Claude 독립검토/운영owner 선행조건.

- 2026-09-18 잔여42.19% 기준 재확인 및 Desktop 배치 복원 보강 착수(baseb947b1c). [[2026-09-18_VF-DESKTOP-LAYOUT_Codex]].

- PR31/546ec50 push·256시험/build통과, 9월18일 CI6check billing실행전차단 재확인. [[2026-09-18_VF-DESKTOP-LAYOUT_Codex]], Gemini·Claude검토/운영인수미완료.

- 사용자 Codex 영역 후속작업 승인 확인: 반복승인 없이 연속진행. 실제로그인/승인browser 통합착수 base54f3206. [[2026-09-18_VF-BROWSER-AUTH_Codex]].

- PR32/325554c:273시험/build·실HTTP브라우저6통과. 사용자승인 후 보관백업+독립PG복원/0043업그레이드·row보존/권한격리통과. [[2026-09-18_VF-RECOVERY-REHEARSAL_Codex]]. 원격3timeout·CI billing/peer/운영SSO·PITR/5대 인수미완. 승인재요청없이외부조건복구후이어감.

- 자동연속진행: Claude 신규4commit 수신/PITR출력·인수경계검토 착수basef00341e. [[2026-09-18_VF-PITR-BOUNDARY_Codex]].

- PITR 후속: Claude 4 commit 통합, 비밀출력·설정/복구 판정 경계 수정. 격리 PG16 관련 40/40 통과, 운영 archive_mode off 실측. [[2026-09-18_VF-PITR-BOUNDARY_Codex]]. CI/Claude 독립검토/운영인수는 별도 미완료. 다음 Claude는 수정본 독립검토, Codex는 실제 WAL·목표시각 복구 증거 확보 가능한 환경에서 후속 검증. 기존 잔여 42.1875%, VF 운영인수 0/5 유지.

## 이전 공유판 수신 기록

외부 공유판 원문과 hash는 Evidence/cx01-landing/shared-codex-before.txt 및 shared-codex-proposal.json에 보존했다. 아래 세 항목은 당시 고정 SHA의 기록이며 현재 착지 검증과 구분한다.

- 사용자 후속 브랜치 정리: VF-CX-01/04 기록은 파일동일, dev-environment 수정은 현 helper와AST동일/격리PG3시험통과로중복제외. workspace-bridge 신규36개 기록 수신. [[2026-09-18_Codex_미착지브랜치_정리]]. 다음VF-CX-02/03/05 준비범위 진행.

## 2026-09-18 후속 검토와 인수 준비

- Claude 8bafb60 추가3파일을 Codex 독립 검토, 관련36시험 통과 후 공유 반영. 작성자76과 중복 합산하지 않는다. VF-CX-02/03 관련104시험 통과; VF-CX-05 오프라인 패키지 검사14시험 통과, 실제 인증서/peer policy 유효기간 실패(exit1). [[2026-09-18_VF-CX-020305_인수준비_Codex]].
- Docker 정리는 사용자 완료 보고 수신. 동일 image 재검증4통과/4실패; Docker I/O·HTTP500·정리 오류 잔존. 다음 Claude VF-CL-R-001 진단/정리 개선, Codex 수신 후 재검증. 운영자는 .225 갱신 준비, CI billing 대기.

- 사용자 finding MIGRATION-PREREQUISITE-001 수용: DSN 부재가 migration 손상 신호로 변환되는 검증 결함 수정·로컬 검증 완료. CLI exit2와 공통 local-skip/CI-fail fixture; 무DSN1074통과/489skip/0실패, 실제PG account·29경로upgrade 포함10통과. [[2026-09-18_마이그레이션_DSN_선행조건_Codex]]. 다음 Codex: 공유 착지·선택 동기화, Claude 수정본 독립검토. CI billing 대기.

- [[2026-09-18_IMAGE_정리후재검증_Codex]]: 동일digest·시험소스 재검증, 첫 시도PG inspect timeout/0시험, 두 번째4passed/4failed. 이전7건중4통과/3미완, writable 정리실패 추가. 제품 단언 실패 미관측이나 전체보안검증 미완. DSN finding은 사용자 독립 검증1074/489/0수신.

- [[2026-09-18_Docker_호스트분류_Claude변경검토_Codex]]: 사용자 보고0xC0000142를 host-process-initialization-failure로 분리. HTTP500과 동일원인은 미확정, business-kernel-role 거부 미검증 유지. Claude83c0163 문서 채택;911aed8/9e69dcc는 동시prune 강제삭제·timeout전파·DSN마스킹 findings로 보류, 다음 Claude 수정/Codex 재검토.

- [[2026-09-18_Workspace_아카이브무결성_Codex]]: VF-CX-05 오프라인 내부image archive SHA-256 검사 추가(합계8GiB한도),21시험통과·실제2archive일치. 인증서/정책만료로exit1 유지. OneDrive는 쓰기버스트상관으로 정정, 일정누수/NTSTATUS인과미확정. 다음Claude 독립검토/R2수정, Codex 수정수신 후검증.

- [[2026-09-18_모델레지스트리_명시결속_Codex]]: VF-CX-02 명시registryVersionId↔manifest/content/policy 불변결속·현재권한·동시성구현,0044head,격리PG100/100통과. 실행permit연결/원격provider는후속,운영DB미변경. 사용자image XML3pass/host-init3/timeout2 직접확인, business-kernel-role미검증유지. Claude07bae29는과도한NTSTATUS재시도/R2-03미해소로보류.

- 최신 image 독립판별(XML/JSON직접확인): 동일digest3회4/3/2pass,최신2pass/6fail(host-init5/timeout1). 재시도구제실패·전체반복인수미확보, 제품보안단언실패관측0≠미통과합격. business-kernel-role미검증유지. 환경조치후조용한조건까지image추가실행중단;모델결속100PG시험은이미완료. [[2026-09-18_모델레지스트리_명시결속_Codex]].

- 원격 읽기 기반: NodeTransfer의 bounded chunk 검증 공통화·공격 입력 회귀 포함 오프라인79통과, Docker/실장비 실행 없음. 사용자 독립 5b783d2 전체비integration1081/489/0·DSN exit2 유지 수신. provider/runtime 결속·PG통합재실행/Claude검토 미완료. [[2026-09-18_모델레지스트리_명시결속_Codex]].

- 원격모델 bounded reader 구현·합성loopback mTLS 포함106시험통과, runtime/DB현재권한 연결은 후속. Claude b5f770a 재검토: R2-01/사전prune R2-02 수정인정, R3-01 오분류·변경명령재시도/R2-03 libpq미마스킹 재현으로전체착지보류. [[2026-09-18_원격모델읽기_Codex]].

- **미착지 후보** 원격권한 snapshot 전후검사·frozen source hash·승인/delivery/claim 결속 구현.132passed/29PGskip(DSN없음), 실제DB검증전 integration5e4d6ae유지. Claude71fc9f5 timeout개선인정/R3-01·R2-03·OSError잔여로보류. [[2026-09-18_원격모델권한결속_Codex]].

- **DB검증 보류해제**: 사용자disposablePG16에서파일별79passed/0failed/0skip(원격6/runtime23/registry16/locality26/retry8). 최초3fixture CAS오류수정,제품코드변경0.8c347b7권한결속을integration반영판정. 기존489skip전체검증아님/image중단유지. Claude56aa7cb의기존재현해소인정, b809fbe timeout타입불일치R4-01은mock재현/전체브랜치보류. [[2026-09-18_원격모델권한결속_Codex]].

- 사용자e89a415 독립4파일/실PG75passed·0failed수신,착지판정유지. Claude816346c 오프라인15passed/실Docker2제외,R4-01해소. cleanup skip이합성본문실패를1skip/exit0로덮는R5-01(P1), 격리소스docker_diag누락R5-02(P2) 재현으로전체착지보류. [[2026-09-18_Claude816346c_재검토_Codex]].

- 후속사용자 clean816346c 두파일17passed/0failed(실Docker포함)수신,R4-01해소확인. 새R5-01/02는해당시험밖의경계로보류유지. Claude e89a415/8c347b7 소스검토배정수신·결과대기.

- VF-CX-02/03 registry 트랜잭션 재검사 구현(base f2297ae), 실제PG 신규7+기존16=23passed/0skip/0failed. 기존 결속만 허용하고 호출자 잠금 유지. frozen workload/승인 연결은 다음 Codex, 독립검토는 Claude 대기. [[2026-09-18_Registry_트랜잭션재검사_Codex]].

- VF-CX-02/03 registry frozen workload·승인/dispatch/delivery/claim 결속 구현(base1b39d40), 실제PG84+오프라인60=144passed/0failed/0skip. policy 제거·변경/retired 거부. 독립검토 Claude 대기, 운영 정책 구성 연결은 후속. 사용자 helper 독립23통과 수신, 외부대기4건 유지. [[2026-09-18_Registry_실행권한결속_Codex]].

- Claude d59b8a6 전체 착지 보류해제: 사용자독립24/작성자24, Codex오프라인22+실Docker2제외와 격리import통과(미합산). R2~R5 blocker 해소. image미검증6/business-kernel-role 미검증은 운영인수 항목으로 유지. e2908a5 registry 실행결속은 별도 독립검토대기. [[2026-09-18_Registry_실행권한결속_Codex]].

- 기본 Docker 의존 분리: 실제prune2건만 docker_host로 기본 deselect, mock22건 유지/Core CI 명시lane 추가. 사용자1157/489/0·62초 수신, 작성자 비integration1179passed/489skip/2deselected/0failed,66.23초. 기존 Compose2건 CLI부재가드 보강, 실제CLI2통과. e2908a5 registry 독립검토는 다음 Claude. [[2026-09-18_Docker_시험선택경계_Codex]].

- 사용자1eaf285 독립1179/489skip/2deselected/0failed(75초), Claude c9e6ddf의 e2908a5 sound 소스검토/부재22pass2skip 수신. registry 운영자 설정 연결 구현, offline34+실PG12=46passed. 최초 관측용DSN application_name 차이12setup오류는 원본DSN재실행으로 분리. 이번 설정 변경 독립검토 Claude 대기. [[2026-09-18_Registry_운영정책설정_Codex]].

- 호스트조치후 사용자image4pass/2fail/2skip(exit1),XML/JSON직접확인. host-init0회/OneDrive인과미확정,잔여timeout4건·business-kernel-role미검증유지. [[2026-09-18_IMAGE_OneDrive재시작후판별_Codex]].

## PITR 준비안 검토 수신

[[2026-09-18_PITR_준비안_검토_Codex]]: Claude 8c72fbf 검토 결과 R1-01~04 수정 전 착지 보류. 논리 복원을 PITR로 간주한 판정, same-host MinIO의 off-host 보장, archive 재시도·용량 설명을 수정해야 한다. 따라서 남은 사항이 모두 외부 조치인 것은 아니다. 다음 내부 담당 Claude: 준비안/격리 PITR 증거 보강; Codex: 수정본 재검토. Docker 실행/운영 적용 없음. 사용자 image 방법론 정정 수신, 동일 lane 반복 없음.

### PITR 독립 확인 수신·수정본 대기

사용자가 R1-01~03 소스 근거를 독립 확인했고 Claude 수정 중이라고 보고했다. 원격 1ff4324는 image 지도만 갱신, PITR 수정본 미도착. [[2026-09-18_PITR_준비안_검토_Codex]]에 수신·대기 조건 기록. 다음 Codex: R1-01~04 수정본/격리 증거 재검토. 현재 새로 착수할 Codex ready 작업 없음; 동일 lane 반복 없이 대기.

## 검증 경계 표본 감사

[[2026-09-18_검증경계_표본감사_Codex]]: tools51/tests179파일 패턴 검색, 합성 CLI9관측으로 deployment_surface의 factory 오류/attr 부재 성공 처리와 위조 Bearer probe 예외 누락 P2 두 건 확인. 빈 route 입력은 P3 보강 후보. 기존 offline73시험 통과가 이 미검증 경로를 대체하지 않음. 다음 Codex: VB-AUDIT-01/02 수정; Claude: 독립 검토/PITR 수정본. 이번 감사는 미수정 finding이며 Docker/DB 실행 없음.

## 검증 경계 finding 수정

[[2026-09-18_검증경계_오류분류수정_Codex]]: VB-AUDIT-01/02 로컬 수정·offline88시험 통과, Claude 독립검토 대기. factory 인자 결속과 본문 오류 분리, 위조 Bearer 검사 미완료 nonzero, 빈 route 입력 P3는 exit2 미판정으로 보강. 과거 감사의 미수정 표기는 당시 상태. 운영인수/CI·실장비 미완 상태 유지.

### 검증 도구 수정 독립 확인 수신

[[2026-09-18_검증경계_오류분류수정_Codex]]: 사용자 bb4f4cb VB-AUDIT-01 세 경로 독립 재현 수신. VB-AUDIT-02/P3는 작성자88시험 범위이며 사용자/Claude 독립검토 미수신. Claude tip1ff4324로 PITR 수정본 대기. 다음 Codex: 수정본 재검토; 동일 image lane 반복 없음.

## 검증 감사 잔여 범위와 독립 재현 수신

[[2026-09-18_검증경계_후속감사범위_Codex]]: VB-AUDIT-02 사용자 clean worktree 두 앱(RuntimeError→exit1,실제401→exit0) 독립 재현 수신. VB01/02는 작성자 시험+사용자 명시 경로 독립 실행 확인, Claude 소스검토 대기; P3는 사용자 판단 동의. 미감사 영역6종과 다음 실패 대조군 정리. 우선순위1 Python검색 밖 .mjs 인수 스크립트,2 실행/증거/CI 집계 경계. 새 finding/추가 운영실행 없음.

## MJS 빈집합 단언 수정

[[2026-09-18_MJS_빈집합단언_감사수정_Codex]]: shard2단언에 배열/고정2개 가드,실제문장 offline Node12시험 통과. .mjs4파일 every5곳 중 나머지3곳 개수가드 확인. 추가 VB-MJS-02 UI const true PASS3건(P2) 미수정, Gemini 실제 UI 검증 보강/Codex review 인계. 과거 full smoke 실입력은 미확인. Claude PITR a681da3 도착, 다음 재검토 대상.

## PITR a681da3 재검토

[[2026-09-18_PITR_a681da3_재검토_Codex]]: 물리복원 경로/MinIO 정정 확인, Claude 성공텍스트 수신(사용자·Codex 실PG 재실행 없음). R2-01 after INSERT 실패 후 PASS 합성재현(P1), R2-02 변경명령 무차별재시도/소유권없는cleanup(P2), 기존R1-04 설명미해소로 전체착지 보류. 다음 Claude 수정/증거, Codex 재검토. shard9251f18 수정은 별개 착지.

## MJS 나머지3도구 감사

[[2026-09-18_MJS_후속3도구_감사_Codex]]: 사용자 shard가드12회귀 독립통과 수신. 합성 fetch로2PC67/67·reconcile59/59 exit0(unrelated receipt/invalid digest), 물리정지false 대조군은각1failed/exit1. VB-MJS-03 실행결속/실장비주장P1,04 로컬상수hash를snapshot검증으로표시P2,05 실패시verified문구P2 미수정 인계. handoff재현도구는 scope명시된 관측JSON이며 이번소스검토에서 추가finding없음. 다음 Gemini수정/Codex검토, 실제장비실행0.

## MJS 수치 보증 범위 정정

[[2026-09-18_MJS_수치인용_정정_Codex]]: 지도v1.2.0에67/200·202/59 checks의 응답조건·로컬계산 범위와 실제장비/화면 미보증을 명시. 공통판202/202 문구 직접정정, VF01~05 인수조건에 실제bytes/identity/장비·UI 관측 요건 보강. 실제browser6은 별도범위 유지. 운영0/5 변경없음. PITR2468912 보류사유와 다음owner 명시.

## PITR09db057 gate 재검토

[[2026-09-18_PITR_09db057_재검토_Codex]]: 사용자 실제PG 정상0/after-insert음성1 수신+소스대조로R2-01해소. Codex는PG재실행없음. archive명령 순차4조건 정상,다른writer게시 interleaving은덮어쓰기 관측. 고정tmp논거는전용아카이브·단일writer 한정이며전역직렬성아님. R2-02/R1-04미해소로전체착지보류,다음Claude수정/Codex재검토.

## 실행증거 집계 감사·최신 관측

[[2026-09-18_실행증거집계_감사_Codex]]: VF staleXML의과거PASS귀속/불완전증거exit0 두P2 확인. 실제runner외부경계stub·원문CI gate로대조,실제CI/Docker0. Gemini API79/64는보고수신+소스일부확인,독립전체해소미선언. 사용자handle119773/RAM1665MB수신,실행직전handle관측조건강화. 다음Codex집계수정/Claude리뷰.


## 실행 증거 집계 수정과 검토 인계

[[2026-09-18_실행증거집계_오류수정_Codex]]: VB-AGG-01/02 고유 run namespace·subprocessExitCode/evidenceStatus 분리·빈/미생성/깨진 XML nonzero·collect-only 거부 구현. offline43passed/2 docker_host 제외, 실제Docker/PG/CI0. 사용자 기존4prefix 비오염 및 coord-business-retry 증거부재 exit1 수신(거짓성공 아님). 다음 Claude 독립검토; 필수suite/SHA provenance 전체보강·CI·운영인수는 별도 미완.


## Fixture 표본 감사 및 집계수정 독립 실행 수신

[[2026-09-18_Fixture_검증경계_감사_Codex]]: VB-AGG 사용자 collect-only exit2/고유디렉터리 독립실행 수신, Claude 검토대기. 실제fixture 합성경계11관측으로 VB-FIX-01 setup 부분할당 DB잔재(P2), VB-FIX-02 dispose실패시 role정리 생략(P3) 확인·미수정. 성공 위장은 아님. credential action별 grant회수는 기존명시계약이므로 오탐 제외. offline47passed/실DB3skip, Docker/PG/CI0. 다음Claude fixture수정/AGG검토, Codex재검토.


## Launcher와 운영 증거 경계 감사

[[2026-09-18_Launcher와운영증거_경계감사_Codex]]: 원본PS1+native대역5조건에서 인증서생성exit23→전체exit0/All Exit Codes 0 재현, VB-LAUNCH-01 P2 미수정/Gemini owner·Codex reviewer. 운영증거5관측: LAN실패exit2에이전JSON보존 위험후보, 독립복원기존output거부/빈storage false 정상. 기존시험5passed/DB30skip, 실제배포/Docker/PG0. Claude PITR/fixture구현 중복없음. 다음 수정본검토·잔여후보대조, 운영0/5유지.


## 감사1~5 종합과 누락 없는 상태표

[[검증 경계 감사 종합과 잔여 범위]]이 감사 결과별 owner·수정·검증·잔여 검토 정본이다. 후속8건/초기AUDIT포함10건/MJS01·02포함12개 ID의 분모를 구분. 요청10건 중 사용자 수정·독립검증 확인7/미수정3, 별도MJS01수정·독립실행/MJS02 UI상수 미수정. MJS03~05 최신사용자확인 수신과 Codex계약리뷰잔여는 분리. 우선순위4확정finding추가0, 위험후보보존; 1~5첫표본정리·전수완료아님·6 frontend미착수. 제품/운영 재실행0, 운영0/5유지.


## Fixture 수정본 재검토·registry policy 검토 수신

[[2026-09-18_Fixture_a5401a7_재검토_Codex]]: a5401a7 9시험 Codex독립통과(합성DB/engine,실PG0); 사용자의 DSN설정9통과도 실제PG시험은 아님. FIX01 원래경로해소, FIX02 DROP시도해소/동시dispose+DROP 오류누락 P3잔여로전체수정종결보류·미병합. 다음Claude FIX02-R1수정/Codex재검토. 11e9f44는Claude7e3de2a sound 독립소스검토 수신으로대기해소(CI/운영별도). PITR0da140e도착·검토대기.


## Claude fixture 해소·독립커밋 착지 / PITR 잔여

[[2026-09-18_Claude_c754933_부분착지검토_Codex]]: c754933 새2건은DROP단독/양쪽실패, 원본11passed·통합32passed(합성,실PG0). FIX01/02해소, a5401a7/c754933/7e3de2a 원본커밋을0a65313/f7a46da/495df5c로반영. PITR원본함수에서cleanup조회실패은폐/제거실패후재시도 재현,PID label잔여로전체브랜치보류. 후속8건중코드미수정LAUNCH01만맞지만별도MJS02·review·PITR잔여는유지. 다음Claude PITR보강/Gemini LAUNCH01·MJS02/Codex재검토.


최신원격입력: Gemini84a86f1 VB-LAUNCH-01수정이integration에선행착지해정상병합. 후속8건은모두수정본존재로갱신하되LAUNCH01 Codex재검토/기존독립검토잔여별도. 신규launcher시험미실행. [[2026-09-18_Claude_c754933_부분착지검토_Codex]] 참조.


## Launcher scope 재검토·PITR hold 인계

[[2026-09-18_Launcher_scope와PITR_hold_Codex]]: 사용자66bbcf0 16passed수신(실PG증거아님). LAUNCH원래nativeexit누락해소, Docker SKIPPED/gateway Optional분리확인. 원본PS1합성2조건에서invalid-nonempty cert도TLS1.3 VERIFIED·고정202 E2E문구출력→Gemini scope잔여. npmbuild exit검사는수정전부터존재. PITR query/remove실패·PIDlabel잔여와nonce/cleanup상태/재시도게이트/음성대조조건명시. git cherry로fixture2커밋·registry검토 patch동등착지확인,2ed3d6은상태문서추가만/PITR코드변경없음.


## Claude 수정대기 정정 / 사용자 방법론 정정 수신

[[2026-09-18_Claude_대기상태정정과수정인계_Codex]]:2ed3d65는문서1파일뿐/PITR코드변경0. FIX02재검토·내용착지완료, PITR은Codexreview대기가아니라Claude cleanup잔여수정대기. 내용차이8/동등patch3 대조,image workspace skip누락·실PG11오표기·1179실행주체등상태문서정정인계. bb4f4cb Claude sound 문서수신(독립소스검토,런타임별도). 사용자의npm검사시점/16시험합성범위정정수용수신. 동일주입/운영시험반복없음.

## TLS 인증서 마운트·경로 방어

[[2026-09-18_TLS_마운트_경로방어_Codex]]: `65965a3`에서 production Compose 인증서·키 bind를 `create_host_path: false` long syntax로 고정하고, `deploy_intranet.ps1`의 leaf 검사·stale directory 정리와 `generate_tls_cert.py`의 정확한 출력 경로 정리를 구현. 신규 경계시험 2 passed, preflight 11 passed, Compose YAML·문서 검사 통과. 인증서 삭제·gitignore·이력 재작성은 수행하지 않음. 새 개발 인증서 발급·외부 주입은 사용자 결정 대기.

[[2026-09-18_TLS_외부주입_전환준비_Codex]]: 외부 인증서 디렉터리 `SAINTVISION_DEV_CERT_DIR`와 generator `--output-dir`를 구현하고, preflight에 PEM 인증서·개인키 공개키 일치 검증을 추가. 기본 경로 호환, 외부 경로, 누락, 불일치 회귀를 포함해 관련 27 passed. `77c5311` 준비 문서를 구현 상태로 갱신. 실제 Docker `up --no-start`와 인증서 발급은 별도 환경 검증 대기. 삭제·gitignore·이력 재작성은 수행하지 않음.

후속 보강: `verify_tls_cert_pair.py`의 cryptography import를 지연해 사용법 오류는 exit 2, `--help`는 exit 0, 유효 인자에서 의존성 부재는 exit 1로 분리. 관련 회귀 범위는 30 passed. README와 외부 주입 runbook에 clone 초기화 절차가 모두 반영되어 별도 문서 추가는 불필요.

## UI 우선순위 6 fake fallback 경계 감사

`UI-PRIORITY6-FALLBACK-AUDIT-20260919-CODEX`를 기준으로 `apps/web/src`의 화면·route adapter와 관련 시험을 정적 감사했다. ResourceExplorer의 backend 오류 후 합성 후보·capacity·detail 유지(UI-FB-01/P1 후보), PlacementSimulator의 로컬 평가 경계(UI-FB-02/P2), DeveloperStudio의 ResultView 오류 후 artifacts fallback(UI-FB-03/P2 후보)을 기록했다. `apps/web`에서 `npm exec vitest run tests/fabric-control-plane.test.tsx tests/placement-explain.test.ts`는 30 passed이며 mock/순수 계산 범위다. HTTP 실패 주입·브라우저 UI 인수·Gemini 구현은 미검증/대기이고, 다음 담당은 Gemini(구현), Codex(경계 재검토)다.

## 우선순위 4 readiness·restore·storage offline 경계 감사

`PRIORITY4-OFFLINE-BOUNDARY-AUDIT-20260919-CODEX`를 기준으로 `operational_readiness.py`, `storage_check.py`, `rehearse_independent_restore.py`, `rehearse_lan_upgrade.py`와 보고서 경계를 대조했다. PR4-01은 기존 성공 output이 실패 실행 뒤 남아 소비자가 stale 보고서를 읽을 수 있는 P2 후보, PR4-02는 independent restore의 finally cleanup 오류가 본문 보고서 생성을 가릴 수 있는 P2 후보다. 기존 stale-output 실패 주입은 exit2/기존 파일 보존까지 확인했지만 소비자 오인은 미재현했고, cleanup 장애 주입은 수행하지 않았다. offline readiness/storage는 DSN 부재로 5 passed/30 skipped이며 성공 위장은 찾지 못했다. 독립 restore 관련 시험은 cryptography 의존성 부재로 collection 불가였다. 다음 owner는 report provenance/cleanup receipt 구현 검토자이며, 실제 restore/LAN 인수는 승인·격리 조건 이후다.

우선순위 4 후속 구현(2026-09-19): `rehearse_lan_upgrade.py`는 기존 output/failure receipt를 선행 거부하고 실패 receipt를 별도 신규 경로에 기록한다. `rehearse_independent_restore.py`는 cleanup query/remove/ownership/confirmed 상태를 본문과 분리하고 cleanup 오류에도 본문 report를 보존한다. 반드시 `.venv/Scripts/python.exe`를 사용했다. 관련 두 파일은 **30 passed**이며, 이전 시스템 Python의 cryptography collection 실패 기록은 인터프리터 오류로 정정했다. 실제 Docker/PostgreSQL 복원과 운영 인수는 미실행이다.

## Credential / migration 예외 경계 보강

`CREDENTIAL-MIGRATION-ERROR-BOUNDARY-20260919-CODEX`에서 Claude 인계 finding을 구현했다. `provision_credentials.py`는 denial·DB 오류·내부 오류를 각각 분류하고 값 없이 sqlstate/type만 보고하며, `plan_lan_migration.py`도 metadata refusal·DB 오류·내부 오류를 구분한다. 호출자는 credential integration/CLI와 `rehearse_lan_upgrade.gap_plan`/core 시험으로 확인했다. `.venv\Scripts\python.exe -m pytest -q tests/core/test_credential_provision_cli.py tests/core/test_lan_migration_plan.py`는 16 passed/1 skipped(DSN 부재)다. 원복 대조에서 신규 4개 주입시험이 모두 실패했다. 실제 PostgreSQL 실행은 미수행.

종료 코드 정정(2026-09-19): 독립 검증에서 denial/DB가 둘 다 2이고 internal label이 TypeError=3/RuntimeError=2로 갈린 것을 확인해 공통 계약을 고정했다. 두 CLI는 `0=성공`, `1=정상 pending 업무 결과`, `2=의도된 거부`, `3=DB/driver`, `4=내부 결함`을 사용한다. 같은 JSON 라벨은 같은 코드를 내며 TypeError/RuntimeError는 모두 4다. `.venv\Scripts\python.exe` 기준 22 passed/1 skipped, 원복 대조 신규 종료 코드 6건 실패.

## 2026-09-19 credential catch-all 재수정·일회용 PostgreSQL 재검증

`provision_credentials.py`의 실제 `provision()` 내부 catch-all이 여전히 모든 DB/TypeError/RuntimeError를 `ProvisioningDenied`로 뭉개고 있음을 독립 실측으로 확인해 `25051e3`에서 수정했다. `ProvisioningDenied` 전파, `psycopg.Error`→검증된 sqlstate `ProvisioningDatabaseError`, 기타 예외→타입명만 담은 `ProvisioningInternalError`로 구분하며 context-manager rollback과 비밀 비노출을 유지한다. 플랫폼 비의존 합성 주입 회귀를 추가했다. `.venv\Scripts\python.exe -m pytest -q tests/core/test_credential_provision_cli.py tests/core/test_lan_migration_plan.py`는 24 passed/1 skipped.

정정 기록: 당시 `432 passed/386 skipped/0 failed`는 선택 배치 보고였으나 정확한 manifest가 없어 철회했다. 사후 확인한 그 별도 JUnit은 825 collected, 421 passed, 386 skipped, 18 setup errors였다. 최신 전체 코드 회귀는 Claude `40e921b`의 5개 JUnit 배치 산술 합 2628 tests / 2192 passed / 1 failure / 0 errors / 435 skipped이며 단일 실행은 아니다. Full collect 177 test-bearing files와 배치 manifest union 187 paths는 누락 0·중복 0이고 추가 10개는 support modules다. command/interpreter/KST/artifacts와 correction rationale: [[2026-09-19_archiver_readiness_boundary_Codex]]. 별도 DSN 대상 non-integration `97 passed/0 failed`와 초기 비밀번호 배치는 별도 실행으로 유지한다. 당시 recovery drill 11 passed/7 failed도 최신 시험수에 합산하지 않는다.

후속: `tools/recovery_drill.py`와 `tests/integration/test_recovery_drill.py`에서 definer 함수 검증을 `tools/definer-policy.json`의 exact signature set으로 결속했다. Windows/Linux 백업 경로·격리 Docker network 전제 미충족 6건은 이유가 보이는 skip으로 분리했다. `7eb0d66`을 integration에 push했고, 실제 Linux/격리 Docker 복원 인수는 여전히 미실행이다.

정정: archiver network의 `Internal=false`는 관찰된 보안 실패이므로 skip하면 안 된다. 시험이 소유 `--internal` 네트워크를 직접 생성하고, 생성 실패만 명시적 skip하며 생성 후 `Internal=false`는 실패하도록 `test_recovery_drill.py`를 수정했다. Linux 백업 경로 조건의 3개 시험군은 플랫폼 전제 skip으로 유지한다.

추가 정정: archiver `finally`의 컨테이너·네트워크 정리를 독립 상태 분류기로 바꿨다. 소유권 불일치 자원은 보존하고, 컨테이너 정리 실패에도 네트워크 정리를 계속하며, cleanup 예외가 본문 예외를 덮지 않는다. 삭제 후 재-inspect와 비소유 보존 합성 회귀시험을 추가했다.

## Docker 잔여 provenance 감사

`2026-09-19_docker_residue_provenance_audit_Codex`에 접두사·라벨·생성 경로를 대조했다. `sv-server-test`는 소유 기반 cleanup 경계를 사용하며 공통 `cleanup_owned`에 제거 후 inspect 확인을 추가했다(`7`개 unit pass). `sv-remote-workspace`, `sv-workspace-upgrade`, `saintvision-compat`는 조사 evidence 보존 정책으로 stopped/Created 자원을 남기는 구조라 무기한 retention P2 후보로 기록했다. `sv-bridge-unit` 생성자는 현재 소스에서 찾지 못했다. 이번 감사에서는 Claude 작업 중이므로 삭제하지 않았고, `saintvision-lan-db*`, `saintview-orthanc*`, `svcx01-pgaudit*`는 보존했다.

후속: `tests/test_check_kernel_docker_hygiene.py`의 finally를 공용 `cleanup_owned`로 바꿔 소유 확인·제거 후 inspect를 적용했다. `tools/cleanup_owned_docker.py`를 추가해 30분 age gate, 라벨 소유권, 보호 접두사, 기본 inventory-only, 명시적 `--delete`, 삭제 후 확인을 고정했다. 나열 모드에서 eligible 42개를 확인했지만 삭제는 0건이며, `sv-bridge-unit-*` orphan provenance를 별도 기록했다.

후속 독립 검토 보강: volume inventory의 잘못된 `-a` 플래그와 `Created`/`CreatedAt` 불일치를 수정하고, 종류별 열거 실패를 `unverified`로 노출했다. 나열 결과는 container 4/network 11/volume 84, unverified 0, 삭제 0건이다. evidence 보존 라벨은 14일 retention 정책으로 분리했으며 관련 회귀시험 포함 `9 passed`다.


### Docker inventory and user-preserved anonymous volumes — corrected record

The earlier appended block in this workboard was damaged by character-encoding conversion. Its readable replacement is below; the corrupted committed copy remains in Git history and is not treated as evidence.

- Complete inventory was container 53/53, volume 85/85, network 11/11 using Docker Engine API counts independent of docker ls. A symmetric omission of container -a was injected into both list and comparison paths; the independent count caught 3 versus 53 and --delete aborted with zero removals. Independent review reported 12 passed.
- After Claude finished Docker work, authorized cleanup removed and re-inspected 5 owned containers and 6 named volumes: counts 53/85/11 -> 48/79/11. Protected SaintVision LAN DB and Orthanc resources remained; 69 anonymous volumes were untouched.
- Upstream launch paths that could create implicit PostgreSQL volumes were changed to tmpfs or labeled named volumes. Same-day regression evidence: 14 passed.
- Anonymous-volume snapshot: 69 Docker-generated 64-hex names, no owner labels; 3 attached to PostgreSQL data containers, 66 unattached. Creation distribution and attachment sources are in the History record. Storage measurements differ by method: 3.843 GiB from Codex's sum of rounded per-volume docker system df -v SIZE entries; approximately 3.665 GiB from the user's independent docker system df -v reading. Report about 3.7 GiB and preserve both readings.
- User decision complete: preserve all 69 because upstream creation is blocked, storage is not urgent, and ownership is unprovable; deletion is irreversible. Do not revisit cleanup unless explicitly instructed.

## 2026-09-19 Audit Summary Final Update

The latest priority 1-6 state is in the final status table of the verification-boundary summary. Execution, injection, rollback comparison and source-review evidence remain separated. Gemini authentication, 69 anonymous Docker volumes and orphan-resource provenance are explicit handoff items.


## Anonymous Docker volume decision (2026-09-19)

User decision is complete: preserve all 69 currently inventoried anonymous volumes. Do not propose or perform their cleanup unless the user explicitly changes this decision. Reasons: known upstream PostgreSQL launch paths now use tmpfs or explicit named volumes; about 3.7 GiB is not urgent; anonymous volumes lack ownership proof and deletion is irreversible. `cleanup_owned_docker.py` remains fail-closed and now identifies this as `preserve-by-user-decision`.

Snapshot: 69 volumes, 64-hex Docker-generated names, no owner labels. UTC CreatedAt distribution: 2026-09-09 (4), 2026-09-11 (1), 2026-09-14 (9), 2026-09-15 (20), 2026-09-18 (35). Three are attached at `/var/lib/postgresql/data` to `/saintvision-inv-db`, `/saintvision-core-test-20260909`, `/inv-codex-core-pg`, all `pgvector/pgvector:pg16`; the other 66 were unconnected at snapshot time. Codex measurement: sum of individually rounded `SIZE` entries from `docker system df -v`, unit-converted, 3.843 GiB. User independent measurement: approximately 3.665 GiB from `docker system df -v`. Record both methods; do not force equality. `docker volume inspect` supplied CreatedAt; container `inspect` supplied image/mount linkage.

## 2026-09-19 Audit-of-audit handoff

Reviewed today's 20 changed paths exhaustively (15 detailed audit/evidence records plus 5 index/workboard/rollup/README records). Corrections AOA-01..09 are recorded in [[2026-09-19_감사에대한감사_Codex]]; prior incorrect claims remain traceable in Git/history and are not silently erased. Local rechecks used .venv\\Scripts\\python.exe; tools/check_docs.py passed (24 original hashes, 578 versioned documents, 48 tasks, 12 outcomes). No Docker, PostgreSQL, live backend, CI, GUI, or device acceptance was rerun. Next action: carry forward only the explicitly listed external/platform/operational unverified items; do not repeat their acceptance runs before prerequisites change.

## 2026-09-19 test_recovery_drill fixture boundary

AOA-05 follow-up: the old 18 setup errors had two distinct causes: unset CX01_CONTAINER caused the DSN host 127.0.0.1 to be incorrectly used as a Docker name; a separate run found our disposable codex-db-test container but the old label allowlist rejected it. tests/recovery_drill_prerequisites.py now skips missing/unreachable prerequisites with distinct reasons, accepts only explicit recognized owned-test labels, and fails for present but unowned containers. Venv offline fixture tests: 11 passed; integration file collection: 19 tests (18 use this fixture, 1 cleanup helper test does not). Full PostgreSQL test-body run remains pending while Claude's current regression is active. Next: after it ends, compare its baseline JUnit with the old 18-case result, then execute post-fix recovery cases only against a newly verified disposable container, recording command, interpreter, KST time and JUnit results.

## Integration tip verification audit

- Direct audit SHA: `cb505f6697beffe78a1cbdaee027f415003c55d3`, checkout `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`.
- Docs, ontology, schema export, contract check after `npm ci`, sync check, Vitest and Python suite passed. Python: 1338 passed / 1315 skipped / 2 deselected / 0 failed; skips are chiefly absent PostgreSQL DSN, opt-in browser lanes, Linux-only paths, and explicit local image/tool prerequisites.
- `route_coverage.py` CLI returned 1 for the known static `/v1/workspaces` configuration-string false positive; its regression tests passed 28. This is not live API acceptance. Obsidian check is read-only and reports 1 pending export.
- Exact commands, exit codes, runtime identity, scope and evidence: [[2026-09-21_integration-tip-verification_Codex]].
- Reporting rule: attach full SHA, branch, checkout path, exact command/cwd, runtime, KST start/end, direct exit, counts/reasons, artifact, and executor/reviewer identity to every verification claim.

## 2026-09-21 current continuation: contract map, CI readiness, UI-FB-03

- Response-contract map: eight functional shared adapters are inventoried. Workspace/readiness, discovery candidates, storage lists, approval review, and kernel approval challenge/decision are bound to canonical/generated shapes and shared fixtures. Remaining unbound groups are project-list legacy envelopes, run/result/artifact, run/approval queue, placement/pool/mutation, storage resolve/replica/model, shards, and node observations. Order by user-facing/control impact is in [[2026-09-21_web_response_contract_map_workspace_Codex]]. Targeted fixed-SHA kernel/approval tests: 9 passed; full Vitest: 39 files/359 passed; schema 28 and TS response types 7 passed; `tsc -b`/Vite build/docs/ontology passed at `0c248976430aac1d91fa14f7ea63f80c757997eb`.
- CI/Linux: user confirms all five workflows are Ubuntu. The selected POSIX/Linux tests should execute there. Source inspection confirms root/integration PostgreSQL gates and Node-runtime are CI-fail gates; core workflow supplies PostgreSQL 16 and builds/provides the Go node-agent binary/image with `INV_RUN_NODE_TESTS=1`. Codex prepared backend/core/browser image lanes in 9a361fe. After Claude's correction, the browser CI gate compares five normalized journey names and docker-host compares two case names; both require zero skips/failures/errors. YAML parse and collect-only (browser 6 items/5 journeys; docker-host 2 cases) passed. Actions remain unexecuted because billing is blocked; public image/package pulls and hosted runner behavior remain unverified.
- UI-FB-03: reviewed Gemini `5e2a533`; focused DOM suite is 13 passed and full Vitest includes it. Review remains pending: after a successful mount, a click-time 401 produced no alert; a temporary alert assertion failed and was removed. `handleDownloadArtifact` reuses earlier `artifactData` after non-route `/result` failure. Gemini owns the follow-up; Codex does not edit the UI.
- Provenance: latest fixed-SHA verification is recorded in the contract map History. PostgreSQL DSN absent, and this result is not CI, live HTTP, or browser acceptance. An initial wrapper call used a relative venv path and exited 127; the absolute project interpreter invocation passed and is the only positive evidence.
- Obsidian: after docs/ontology passed, the final authorized sync exported 2 files with all 1405 destination hashes matching; paired check was 1405 managed/0 pending/0 conflicts (16:52 KST).
## 2026-09-21 통합 CI 수정 확인, UI-FB-03 검토, run/approval 계약

- `agent/codex/workspace-response-contract-map`의 fast-forward 착지를 `614501a`에서 확인했고 통합에 push했다. 이후 통합은 동시 착지로 `686eecff924a5527e537c26228e2db87c00106ff`까지 전진했다. 그 기준 core workflow에 ignore 6개가 있고 LAN image 두 시험은 전용 lane에 남는다. 두 LAN 파일 일반 수집 결과는 앞서 15/15 skip, 전용 6-case passing JUnit 대조는 게이트를 통과한 바 있다. Schema 32/32 및 API response TS 9/9 체크는 통합 내용에서 exit 0.
- Gemini `beff6c1` UI-FB-03을 Codex 독립 DOM 경계에서 승인했다. 이전 성공 로드 뒤 클릭-time 401이 캐시를 재사용하지 않으며, 상주 사례가 fallback 호출 0·오류 표시·Blob 생성 0을 검증한다. 18 DOM case pass는 `614501a`에서 실행. Gemini의 mutant 증거는 검토했으나 Codex가 재실행하지 않음. 브라우저 인수 아님.
- 다음 계약 slice `runApprovalObservation.ts`는 `ControlRunPage` 및 기존 `ApprovalPage`와 공유 fixture, Python provider validation, frontend Ajv/adapter mapping을 연결했다. Base `686eecff924a5527e537c26228e2db87c00106ff`; branch `agent/codex/run-approval-observation-contract`; dirty-base provenance at 17:36 KST, executor Codex, Windows 11, Python `.venv/Scripts/python.exe` 3.14.6, Node v24.17.0, PG DSN absent, Docker present, Go absent. Provider 7 passed; full Vitest 41 files/381 passed; `tsc -b`, Vite build, schema check 32, API type check 9, docs (614 documents), ontology, and contract generation all exit 0. Shared-fixture missing-cursor mutation fails on both backend and frontend. No DB/CI/live HTTP/browser/Go compilation. Obsidian read-only check: 1407 managed/5 pending/0 conflicts; final paired sync pending.
- At 17:39 KST the task tree observed Claude's `5914f04` arriving on integration. It binds canonical backend run-result and artifact-list schemas/fixtures; Gemini frontend generated-type/Ajv fixture wiring is pending, and artifact-content remains unbound. This supersedes the older map statement that all run-result/artifact responses were unbound.
- The slice is committed as code `e7fc7a8` plus docs `7c3b1d3`, rebased on Claude `5914f04`; final SHA and clean-tree checks are recorded in the dedicated History page. At 17:42:43 KST, clean-tree provenance checks passed provider pytest 7, Claude run-result pytest 4, full Vitest 41 files/381, schema 32, API types 9, TypeScript build, docs (615 pages), ontology and generation. DSN absent, Go absent.
- `5914f04` adds backend run-result/artifact-list contract; Gemini frontend generated-type/Ajv fixture wiring remains pending, and artifact-content is unbound. This corrects the older “all result/artifact unbound” statement.
- Obsidian latest committed check found 1408 managed/2 pending/0 conflicts before final record updates. Paired sync status is in dedicated History. Next: push branch and request Claude fixed-SHA review; then take placement preview/pool/mutation as next Codex response contract. PostgreSQL/CI/browser/operational gates remain separate.
- Latest integration `8fd49a5` (VF-GM-03) is included as the base of final verification. At clean branch HEAD `f350155`, provider tests 7 + 4 passed, full Vitest 42 files/391 passed, response schemas 32, response types 9, `tsc -b`, Vite build, docs (616), ontology and SHACL passed; complete provenance is in `2026-09-21_run-approval-page-contract_Codex`. This feature branch is three commits ahead of integration; push/Claude review pending. Last sync snapshot after the rebase was 1409 managed/2 pending/0 conflicts, to be resolved after this record update.
