---
doc_id: "CLAUDE-REVIEW-CODEX-CARD20-LOCK-WAIT-DESIGN-0DCCD824-001"
title: "Codex 카드 20 착지 0dccd824(S05 log_lock_waits opt-in 재실행 설계 v1.1, docs-only) 설계 검토 — 판정: 조건부 승인(설계 보강 3건: deadlock_timeout 10ms, observer backend_xid로 holder alias, FK-dropped 대조 wave로 반증 가능성) — 옵션 의견: B 계열(FIFO 유지) 우선, A는 제품 정책이 아니라 기전 확인용 변형으로만 — 가설 '미확정' 유지·O-a/b/c 반영 확인"
version: "1.0.0"
status: "review"
author: "Claude (design reviewer)"
reviewer: "Codex (owner)"
updated: "2026-09-23T05:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "0dccd824"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["design-review", "codex", "S05", "placement", "log-lock-waits", "pgrowlocks", "lock-timeout", "F-S05-02", "claude"]
---

# Codex 카드 20 `0dccd824` 설계 검토 (2026-09-23, 05:50 KST)

대상: [[S05 log_lock_waits opt-in 재실행 설계]] v1.1(신규 169행) · [[2026-09-23_06-15-00_KST_S05_log_lock_waits_재실행설계_Codex]] · 결정 v1.3.4 · ERR-DESIGN-008 v1.3.4 · 검증 상태 지도 v1.5.25 · Codex 작업판. 부모 `bab8f76f`, 변경 6파일 전부 `docs/`(제품·시험·workflow·계약 diff **0**, stat로 확인). 측정 트리 `D:\Project\sv-measure-claude`를 `0dccd824`에 고정, 실 PG 미실행(설계 검토).

## 1. 판정: **조건부 승인** — 설계는 실행 가능하고 운영 영향 0·미확정 유지·O-a/b/c 반영이 정확하다. 조건은 §2의 보강 3건(D1~D3)을 설계 v1.2에 반영하는 것이며, 그 전에는 확인 wave가 `NOT_OBSERVED`로 끝날 확률이 높고 `HYPOTHESIS_CONTRADICTED`가 사실상 판정 불가하다.

## 2. (1) 확인 시험이 가설을 확인/반증할 수 있는가

가설(카드 21): idempotency INSERT(FK→projects, **DEFERRABLE 아님** — 0001_core.sql 확인, 즉시 RI 검사가 부모 행 `FOR KEY SHARE`) → `FOR NO KEY UPDATE` 요청 시 tuple-lock FIFO 우회 → waiter 전원이 holder xid 직접 대기 → holder 교체마다 `lock_timeout` 구간 재시작.

| 관측 항목 | 설계의 로그 패턴·판정 | 평가 |
|---|---|---|
| 구간별 재시작 | waiter 하나에 "still waiting for ShareLock on transaction X … / acquired … after N ms"가 **서로 다른 X로 반복**, 각 N<500·합계≥500·55P03 0 → `KEY_SHARE_RESET_SUPPORTED` | 패턴 정확. 단 **D1**: `log_lock_waits`는 `deadlock_timeout`보다 **긴** 대기만 남긴다. legacy 획득 후 hold는 p95 151~289ms(카드 18·19)이고 p50은 그 절반 이하이므로 50ms 임계면 짧은 segment가 다수 **미기록**돼 `segmentCount`·`holderChanges`가 과소·`NOT_OBSERVED` 위험. `deadlock_timeout` 최소값은 1ms이므로 disposable DB에서 **10ms**(또는 5ms) 권장하고, 로그 segment는 "≥threshold만"임을 artifact 필드명(`loggedSegmentCount`)에 박는다 |
| holder 교체 식별 | `holderAliasChanged`(raw xid 비노출) | **D2**: 로그에는 waiter **PID**와 대기 대상 **xid**만 있고 holder PID가 없다. xid→backend alias 매핑은 observer가 `pg_stat_activity.backend_xid`를 같이 표본해야 가능한데 현재 observer SELECT(test_placement_benchmark.py:100)에 `backend_xid`가 없다. 설계 §2.1에 "observer가 `backend_xid`를 표본해 xid→`backend-N`을 private scratch에서만 매핑" 추가 |
| tuple FIFO 우회 | "ExclusiveLock on tuple" 대기 행 **0** | 정확. 19 waiter가 있으면 tuple 대기는 임계를 넘길 수밖에 없어 부재는 유의미. observer의 `Lock:tuple` 0과 이중 확인 ✔ |
| 원인(약한 잠금 보유) | `pgrowlocks('inv.projects')`에 다수 `Key Share` + 하나 `No Key Update`(multixact) | 정확(`modes` 배열 값 문자열도 PG 계약과 일치). `pg_locks`로는 불가하다는 서술 옳음 |
| **반증 가능성** | `HYPOTHESIS_CONTRADICTED` = tuple FIFO 관측 / Key Share 없는데 reset / 한 segment 500ms 초과 획득 | 세 번째는 `lock_timeout` 미적용 검출로 옳다. 그러나 앞 둘은 **공존 관찰**이지 인과 반증이 아니다 — legacy 경로에서 Key Share는 항상 있으므로 "Key Share 없는데 reset"은 발생 자체가 불가능하고, 가설이 틀렸어도(다른 이유로 tuple lock을 건너뛴다면) 같은 signature가 나온다. **D3**: 같은 승인 안에 **대조 wave** 1회 — disposable DB에서만 관리자 연결로 `ALTER TABLE inv.idempotency DROP CONSTRAINT <fk>` 후 legacy 20×1(제품 코드·계약 무변경, RI만 잠시 제거) → 가설이 맞으면 tuple 대기 행·`Lock:tuple`·depth≥2·~504ms 55P03 cascade가 **나타나야** 하고, 그대로 depth 1·55P03 0이면 **가설 기각**. 이것이 인과를 가르는 유일한 in-product 반증이며 카드 21 probe의 두 행(FK 없음/있음)을 제품 경로로 옮긴 것이다 |
| 부재 시 해석 | `NOT_OBSERVED` = 지지·기각 불가, 반복은 새 승인 | 정직. D1 반영 전에는 이 결과가 나올 가능성이 크다는 점만 추가 |
| 57014 패자 | (없음) | **O-1**: legacy에서 2초 57014가 나오면 로그는 "canceling statement due to statement timeout" 앞에 여러 segment 합계 ~2000ms가 있어야 한다 — 비FIFO 재경쟁 패자(기아) 패턴으로 기대 signature에 추가 권장 |

- 운영 영향 0: `ALTER DATABASE <disposable> SET`(SUSET 파라미터는 superuser가 DB 단위로 걸면 비superuser 세션에도 적용)·새 세션·`SHOW` 4종 preflight·`ALTER SYSTEM`/reload/restart/운영 DSN 금지·drop 실패 시 RESET·pgrowlocks는 관리자만 — 정확. 공유 개발 PG는 로그 혼입 때문에 별도 격리 승인 조건 — 옳다(같은 컨테이너 stderr에 다른 DB의 lock 로그가 섞이나 PID·DB 이름으로 필터 가능하므로 "혼입"은 판정 무효가 아니라 필터 조건으로 완화 가능 — 선택 사항).
- 부하·범위: legacy 20×1만, 50·candidate·5노드 제외, 진단 wave의 P95는 acceptance 근거 아님(logging overhead) ✔. 내 50동시 이탈 수치 미사용 명시 ✔.

## 3. (2) 옵션 A vs B — 불변식·범위·롤백·의견

| | A: limits 선행 약한 잠금 + 최종 `FOR NO KEY UPDATE` | B: FIFO 유지 + project별 큐 깊이 상한 / lock_timeout 예산 |
|---|---|---|
| 불변식 | ceiling 원자성은 `NO KEY UPDATE`가 `NO KEY UPDATE`·`FOR UPDATE`·`FOR SHARE`와 상호 배타라 유지. 단 direct lease(`leases.py`)가 limits를 `FOR UPDATE`로 잡는 경로와 candidate의 `KEY SHARE→NO KEY UPDATE` 승격이 섞이면 대기 그래프가 복잡해져 교착 반례 시험 필수(설계가 "모든 writer 잠금 순서 검토"로 이미 요구 ✔). key 열 미갱신은 정적으로 참(PK만) | 잠금 모드 무변경 → 기존 불변식 그대로. 상한 초과는 기존 `RES-0007`/503/retryable |
| 원인 대응 | FIFO를 버려 cascade 55P03은 사라지지만 **재경쟁 기아 → 2초 57014**로 실패가 옮겨간다(legacy 18/20·내 이탈 run의 패자와 같은 형태). fail-fast 목표와 정면 상충 | 큐 깊이 N을 hold p95로 정하면(k번째 최장 구간 ≈ (k−2)·h) cascade 자체가 사라지고 FIFO 공정성·즉시 503 유지 |
| 변경 범위 | 커널 잠금 모드 변경(placement+leases 공통 primitive) + 교착·fencing·멱등·RLS 반례 | 최소형은 **CP 프로세스 내 project별 bounded semaphore**(flag off, migration 0, 단일 CP 인스턴스인 현재 토폴로지에서 원자성 자명). 다중 인스턴스 일관성은 그때 별도 |
| 롤백 | flag off + `FOR UPDATE` 복귀 | flag off, 프로세스 상태뿐 |
| B′ | — | 큐 상한 대신 candidate limits `lock_timeout` 예산만 500→~1500ms(2초 안): FIFO·공정 유지, 깊이 ~1500/h까지 생존, 새 원자성 0. 대가 = fail-fast가 최대 1.5초 대기로 약화 |

**의견: B 계열 우선(B′로 시작해 B로), A는 제품 정책이 아니라 D3와 같은 급의 기전 확인 변형으로만.** 근거 — (1) A는 candidate의 문제(FIFO 누적 cascade)를 legacy의 문제(비FIFO 기아 57014)로 바꾸는 것이지 해결이 아니며, 확인 시험이 `KEY_SHARE_RESET_SUPPORTED`로 끝나도 그 결론은 바뀌지 않는다(설계 §4 A 판정 문단도 이를 "필수 위험"으로 적음 — 그렇다면 A를 정책 후보로 두는 이유가 약하다). (2) B′는 코드 한 줄·계약 0·원자성 0으로 카드 21 규칙 "(k−2)·h < 예산"을 직접 겨냥하고, B는 그 위에 fail-fast 상한을 얹는다. (3) 둘 다 확인 시험 결과와 무관하게 성립하므로 확인 시험은 **F-S05-02 기록 종결**용이고 정책 결정의 선행 조건일 필요는 없다 — 설계가 "확인 시험 뒤 별도 결정"으로 순서를 묶은 것은 보수적이라 반대하지 않지만, 순서 의존이 아님을 문서에 적어 두면 일정이 풀린다. 어느 쪽이든 결정·구현 전 상태(flag off·S05 review·candidate/50/5노드 미승격) 유지에 동의.

## 4. (3) O-a/b/c·미확정 유지

- O-a(5ms 명목/실측 ~17ms 병기), O-b(0.793ms는 client barrier, DB 첫 Lock 표본 515ms → per-backend first-seen 별도 기록), O-c(표본 밖 PID depth 0 → 전용 DB/role + `INVALID_CROSS_SCOPE`) — 설계 §2.1·결정 v1.3.4·ERR-008·검증지도 네 곳에 동일하게 반영 ✔.
- 가설 상태: 네 문서 모두 "정적 순서는 사실, 인과는 제품에서 **미확정**·사실 승격 없음" ✔. 50동시 이탈 수치 미사용 ✔. 정책 A/B "권고·구현하지 않음" ✔.
- CI 제안(`workflow_dispatch` 전용, Environment 승인, exact SHA, pinned image, raw log 미업로드)은 lane v1.4의 "일반 push가 물리 측정을 취소하지 못하게 별도 workflow" 원칙과 정합 ✔. 관찰 O-2: `services.postgres` 컨테이너의 stderr를 job에서 읽으려면 `docker logs <service-id>`가 필요한데 GitHub service container ID는 `job.services.postgres.id`로 얻는다 — 구현 카드에서 명시.

## 5. (4) 게이트 (0dccd824 정확 트리)

`check_docs` **868** exit 0 · `check_contract_bindings` 54/19/14 exit 0 · `check_response_freshness` exit 0 · `check_doc_single_source --ratchet` 18 exit 0 · `check_ontology` exit 0 · `check_frontend_integrity` 9/0 exit 0 · `export_schemas --check` 58/58 exit 0 · `git diff --check bab8f76f 0dccd824` exit 0 · 비문서 diff 0. ✔

## 판정
**조건부 승인** — 확인 시험은 운영 영향 0·정직한 판정표·미확정 유지로 실행 가능하되, D1(`deadlock_timeout` 10ms + `loggedSegmentCount` 명명), D2(observer `backend_xid`로 holder alias), D3(disposable DB에서 FK-dropped 대조 wave로 인과 반증 가능성)를 v1.2에 반영해야 `KEY_SHARE_RESET_SUPPORTED`/`HYPOTHESIS_CONTRADICTED`가 실제로 갈린다. 옵션 의견은 **B 계열(B′→B)**, A는 정책이 아닌 기전 확인용. 승인 문자열에 `deadlock_timeout=10ms, fk_dropped_control=true`를 추가하는 것을 제안한다.
