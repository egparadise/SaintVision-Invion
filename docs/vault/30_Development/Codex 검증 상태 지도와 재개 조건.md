---
doc_id: "STATUS-CODEX-VERIFICATION-001"
title: "Codex 검증 상태 지도와 재개 조건"
version: "1.5.25"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T07:00:00+09:00"
source_of_truth: "Git"
---

# Codex 검증 상태 지도와 재개 조건

## 2026-09-23 S05-DB log_lock_waits 진단 설계

- Card19의 55P03 부재 원인은 계속 미확정이다. Claude 카드 21 probe는 idempotency FK가 project KEY SHARE를 먼저 잡아 tuple FIFO를 우회한다는 가설을 제시했지만 제품 인과로 승격하지 않았다.
- 후속 설계는 disposable DB의 `log_lock_waits=on`, `deadlock_timeout=50ms`와 `pgrowlocks('inv.projects')`를 legacy 20×1에서 함께 수집한다. holder별 다른 xid wait/acquired 반복·tuple wait 0·다수 Key Share+하나 No Key Update·55P03 0을 모두 본 경우에만 `KEY_SHARE_RESET_SUPPORTED`다.
- 실행 유효성은 승인 SHA·네 SHOW 값·request/backend 1:1·log pair completeness·pgrowlocks snapshot·DB/role/raw scratch 잔존 0이 모두 필요하다. sampler 5ms는 명목/실측 약 17ms를 병기하고, arrival 0.793ms는 client barrier 기준, DB 첫 Lock 표본 515ms, 외부 role/DB blocker는 invalid로 처리한다.
- 정책 재개 조건: 확인 시험 뒤 별도 결정. 옵션 A는 limits `FOR NO KEY UPDATE` 전환과 기아/thundering herd 위험, 옵션 B는 FIFO queue 깊이 상한과 admission 원자성을 다룬다. workflow/runner/parser는 미구현, 실제 PG/부하는 미실행이며 Claude의 실수 50동시 수치는 사용하지 않는다. flag off·S05 `review`·candidate/50/5노드 금지 유지. [[S05 log_lock_waits opt-in 재실행 설계]].

## 2026-09-23 S05-DB legacy 큐 깊이 실측

- legacy 20동시 1회는 20/20 성공·timeout 0, request/acquire/hold P95 2142.809/1588.193/151.225ms였다. 0.793ms arrival spread와 98개 wait-event 표본에서 max project-lock waiter 19, blocking chain depth 1을 관측했다.
- `lock_timeout=500ms`인데 55P03이 없었던 이유는 `log_lock_waits=off`·server log 미수집이라 미확정이다. holder 교체마다 wait segment timeout이 재시작된다는 가설은 별도 `log_lock_waits=on` 카드 전까지 주장으로 승격하지 않는다.
- 재개 조건: Claude 카드 21이 schema 1.6 queue observer와 O1/O2/O3 경계를 검토한다. candidate 정책·20동시 재실행·50동시·5노드는 별도 승인 전 금지, flag off·S05 `review` 유지. [[2026-09-23_05-55-00_KST_S05_legacy_큐깊이_실측_Codex]].

## 2026-09-23 S05-DB 결정 (b) · P1/P2 대칭 계측

- 코디네이터는 (b) legacy 유지·5노드 후 재판단을 확정했다. `placementShortCommit=false`, S05-DB `review`, 20동시 초과·50동시/5노드 미승격을 유지한다.
- F-C1 정정: 기존 1526.365→116.848ms hold 비교는 legacy만 lock 대기를 포함해 비대칭이므로 “감소 통과”를 철회했다. 대칭 20동시 1회는 legacy 20/20, hold/acquire/client request P95 289.365/1453.658/1885.489ms; candidate 8/20, 170.766/528.705/1054.907ms다. candidate 실패 12건은 모두 limits `FOR UPDATE`의 `55P03`이다.
- 양 mode에 다른 lock_timeout 경로는 없다. legacy 1453.658ms acquire elapsed는 client wall clock이고 server wait_event가 없어 500ms 면제의 증거가 아니다. 원인은 F-S05-02 경계에서 미확정, 57014는 이번 wave 0건이다.
- 재개 조건: Claude 카드 20이 P1/P2 코드·수치·정직성을 검토한다. 다음 후보인 candidate lock-timeout 예산/queue 깊이 상한은 별도 결정 전 미구현이다. [[2026-09-23_03-45-00_KST_S05_P1_P2_대칭계측_Codex]].

## 2026-09-23 S05-DB F-S05-03 fail-fast 재판정

- candidate의 database contention 내부 retry를 제거했다. 첫 limit-row `55P03`은 기존 `RES-0007`/503/retryable로 즉시 반환하며 stale speculative decision 재계획은 유지한다. flag 기본 off, 공개 계약 변경 0이다.
- F-R1 tight-fit과 F-R2 BoundDatabase `55P03` savepoint 시험을 추가했다. 원본 focused는 13 passed/exit 0, active_total 제거와 savepoint 제거 mutation은 각각 대상 시험 exit 1로 KILLED다. 카드 14의 두 되살림 미확인을 정정했다.
- 최종 a60313a7 20동시×3은 legacy timeout 2, candidate 외부 `55P03` 27·내부 retry 0이다. 당시 hold P95 1526.365→116.848ms는 비대칭 계측이라 비교 근거에서 철회하며, request P95(all) 1817.763→922.915ms와 외부 timeout 비증가 실패 기록은 유지한다. 5a612ebd 첫 세트는 schema 명명 결함이 있는 calibration으로 분리 보존했다.
- 이 과거 선택 대기는 위 결정 (b)로 해소됐다. flag 활성, limit-row migration, 20동시 초과·50동시는 여전히 금지한다. [[2026-09-23_02-50-00_KST_S05_fail-fast_F-R1_F-R2_Codex]]

## 2026-09-23 S05-DB F-S05-01 timeout 실측

- 실 PG 단일 project lock 주입은 `55P03 LockNotAvailable` → 기존 `RES-0007`/503/retryable, 1 passed/exit 0, 잔존 0을 확인했다. `LockNotAvailable` 미매핑·계약 변경 필요 전제는 해소됐다.
- 개발 PC·한 합성 measured-node의 20동시 한 라운드는 17 성공/3 실패, 성공 P95 2,417.912ms였다. 실패는 모두 `57014 QueryCanceled` statement timeout → `RES-0007`이며 fencing 유일성·no-overbooking·active 합계는 정상이다.
- 기존 “project 직렬 대기 → 15초 freshness → `RES-0003`” 인과는 철회한다. 3·10·20동시 비교는 각각 861.651ms/실패0, 1,738.762ms/실패0, 2,417.912ms/실패3이다. 50동시·물리 5노드·20동시 peak·server-side row별 lock hold는 미측정이다.
- 재개 조건: Claude가 결정 초안 v1.1의 active fit 재계산, Node/Resource 병목, 중복 project lock, 네 admission 순서, lock hold 계측을 승인하고 코디네이터가 A/B/C를 재결정해야 한다. 그 전 커널 구현·50동시 재실행·AC-05 판정 금지. [[2026-09-23_00-18-00_KST_S05_timeout_실측과_결정초안_v1_1_Codex]]

2026-09-21 최신 Obsidian 결과: 사용자는 두 checkout을 모두 `b5ea2a5`로 고정한 paired `--check`에서 각각 1373 managed/6 pending/0 conflicts를 확인했다. 6개를 적용해 exit 0, 1373 destination hashes 일치, 사후 check 1373/0/0 및 당시 vault 1384 files를 확인했다. 이후 `a39fc13`의 14개 regression evidence와 Codex 문서를 함께 동기화해 1388 managed/0 pending/0 conflicts로 끝났다. Vault recursive count 1399는 managed count와 범위가 다르다. 6/5 pending은 다른 snapshot에 대한 과거 중간 관측이며 현재 기준이 아니다. 최신 기록은 [[2026-09-21_sync_common_state_UI_FB_boundary_Codex]] 및 [[2026-09-21_discovery_candidates_response_contract_Codex]].

2026-09-21 mock/API 계약 첫 slice: `/v1/discovery/candidates` wire response를 strict Pydantic→JSON Schema→generated TypeScript로 연결했고 shared fixture를 FastAPI provider 및 frontend Ajv/Pydantic test에서 검증한다. fixture/schema/type drift 변형이 각각 거부됨을 확인했다. Python contract+route tests 36 passed, Vitest 전체 34 files/332 passed, production build 통과. route coverage는 path-only. 다른 adapter 확장은 미착수다. 코드 독립 검토 Claude 대기. UI-FB-03 component transition은 Gemini 대기이며 브라우저 인수와 별개다. Obsidian 최종 check는 1374/0/0이다.

2026-09-21 Obsidian state split corrected (historical intermediate check): user apply/check was valid in C:\vw but `--git-path` kept a separate main-checkout baseline. The original 1370-entry state passed pre-migration check (1372 managed/10 pending/0 conflict). At this earlier point, main HEAD b5ea2a5 returned 1373/6/0 and C:\vw HEAD 507a486 returned 1373/3/0; both exit 0. Both resolve to the common `.git\obsidian-sync-state.json`; document snapshots differ, so pending counts are not a like-for-like comparison. `tools/test_sync.py` linked-worktree regression fails if reverted to `--git-path`; 14 passed, 5 subtests. No pending vault files were applied at that historical point; later paired apply and final check are recorded above. [[2026-09-21_sync_common_state_UI_FB_boundary_Codex]]

2026-09-21 UI-FB review: FB-01 is approved on user's three matched DOM mutants failing (empty requery, error requery, error render guard). FB-02 component boundary is approved: 9 placement tests passed and replacing the local UNVERIFIED badge with “server verified” failed the corresponding test. FB-03 source path is narrow, but its current 13 helper tests all passed when Codex mutated the component branch to send every ResultView error to artifacts fallback; component-level regression remains required. Browser/live backend acceptance remains separate. Mock/backend schema proposal is recorded. [[2026-09-21_sync_common_state_UI_FB_boundary_Codex]]

2026-09-21 current handoff: Gemini owns UI-FB-03 component fallback tests (401/403/5xx/parse/network must not call artifacts; unmapped 404 may call it and must remain unverified); external CI billing/auth; platform/DSN-dependent integration cases; authorized restore/real-node/AC-12 operational acceptance. Existing 69 anonymous Docker volumes remain preserved by completed user decision. Today's claims corrected in [[2026-09-21_하루정정대장과_감사잔여_Codex]].

2026-09-21 sync EOL: 비교는 CRLF→LF 정규화 SHA, 쓰기는 source 원본 바이트 유지. index 흡수 `7404a6a` 뒤 sync check 14 no-baseline/0 both-diverged. Claude는 남은 14를 SAFE(old 10 + whitespace 4)로 판정했으나 Codex는 그 git-history 근거를 재실행하지 않았고 `--apply`도 미실행. 683개 synthetic fixture rollback은 683 conflict로 실패 확인. [[2026-09-21_sync_obsidian_state_and_static_markup_audit_Codex]]

2026-09-21 sync/UI 시험방법 후속: sync baseline adoption이 충돌 시에도 metadata-only로 보존되고 기본 state가 `.git`/worktree metadata에 있다. 임시 CLI/cleanup 테스트 5 passed 및 rollback-fail 근거. `apps/web/tests` 정적 SSR 인벤토리 7파일·27호출, UI-FB 두 suite는 fetch/effect가 아닌 상태 prop 렌더다. Gemini test-method handoff 기록: [[2026-09-21_sync_obsidian_state_and_static_markup_audit_Codex]].

2026-09-21 UI-FB 구현 `c6dc915` 경계 재검토: 세 컴포넌트의 방향과 작성자 회귀시험은 확인했고 Vitest 322/route coverage 28이 통과한다. 다만 fetch→render 전이를 실제 실행하지 않는 SSR 시험 및 되돌림 대조 3건 통과, 오류 알림 접근성, PlacementSimulator local eligible 인상, DeveloperStudio `currentRun.succeeded`만으로 `Output Verified`를 표시하는 잔여가 있다. UI-FB 독립 검토 pending. Gemini가 finding을 수정한 고정 SHA에서 재개한다. [[2026-09-21_UI_FB_contract_readiness_review_Codex]]

2026-09-21 재개 관측: tip `08f2a4d` 기본 비통합·비Dockerhost 회귀 **1324 passed / 489 skipped / 2 deselected / 0 failed**, 105.48초. 별도 PG DSN 없음, Docker daemon은 응답했으나 가용 RAM 788MB라 새 disposable DB를 시작하지 않음. integration의 66 skip은 Windows Linux-backend 및 PostgreSQL 선행조건 미충족으로 미실행이다. 이후 해당 선행조건이 충족된 격리 환경에서만 재개한다. 상세: [[2026-09-19_pytest_skip_baseexception_assertion_boundary_Codex]].

2026-09-19 추가 검증 경계: pytest의 `Skipped`는 `BaseException`이라 실패 기대 `pytest.raises`가 skip을 초록 통과 대신 test skip으로 노출할 수 있다. seven scoped files now use `raises_without_skip`; four environment-independent modules reject any skip report; two integration files keep valid prerequisites skips and guard only failure assertions. Direct and grouped skip injections, module-level skip mutations, and target-helper rollback contrasts failed visibly. See [[2026-09-19_pytest_skip_baseexception_assertion_boundary_Codex]].

최종 착지 재검토: [[2026-09-18_Claude8b49981_최종착지와routecoverage_재검토_Codex]]. Claude `8b49981` 문서 정정과 PITR cleanup hold는 `0955202` 병합으로 닫혔다. 최신 사용자 회귀는 최종 tip에서 **1264 passed / 489 skipped / 2 deselected / 0 failed, 69초**다(tests/integration 제외·기본 not docker_host·DSN 없음). 1074 대비 +190이나 추가 시험의 기원을 전수 대조하지 않아 감사 회귀 증가로 귀속하지 않는다. 감사 12개 ID와 341c035 evidence 잔여 3건은 모두 수정·명시 범위 검증 기록을 보유한다. route coverage 실제 계약 불일치는 현재 프론트 정렬로 해소됐고 정적 도구의 bare workspace 1건은 오탐이다. 관련 회귀 29 passed; live HTTP 인수는 미실행.


고정SHA 후속 재검토: [[2026-09-18_PITR63fb71c와MJS02_bfb225e_재검토_Codex]]. PITR63fb71c cleanup 코드 hold 해제(대역13체크+보강5시나리오); 전체branch는 기존 문서 정정 잔여. MJS02 지정3항목 해소(격리집계3시나리오), Gemini 잔여는 backend의존 기본시험과 hasDesktopShell 상수 단언. 실Docker/PG/전체smoke 인수 없음.


개발 기준 코드 d7e7d13, 후속image실행 기준 f4b3f73, 공유 branch integration/all-agents-unified. 사용자 요청에 따른 상태 감사이며 새 제품 구현/운영 재실행은 하지 않았다. 각 행의 SHA·범위에만 결과를 적용한다. 통과 건수는 중복 합산하지 않는다. 작성자 실행, 사용자 독립 실행, Claude 소스 검토, CI, 운영 인수는 서로 대체하지 않는다.

## 오늘 사이클 최종 상태 — 회귀 기준6feccd8

[[2026-09-18_Codex_감사사이클종료와다음세션인계]]이 다음세션 인계 정본이다. 사용자독립실행 **1254passed/489skipped/2deselected/0failed,80초**: integration제외/기본not docker_host/DSN없음.1074대비180증가(1081대비173). 작성자전체재실행0.

- 후속감사8건수정본·명시범위검증존재. review/CI/운영별도. 별도MJS02 UI상수는미수정.
- FIX02검토·내용착지완료. PITR은Claude cleanup잔여수정대기이며운영조건때문의hold아님.
- Gemini summary2건 **해소(bcec3e0)**: TLS파일관측·암호미검증 및 smoke exit0·실장비미검증 분리. Codex3034ce0 회귀10passed/5.31초/exit0, 사용자독립10통과와합산금지. Docker없음/gateway실패/invalid nonempty cert/개수미제공 네조건 확인. 실제배포인수아님.
- image최신4pass/2daemon-timeout fail/2operation-timeout skip. workspace/business-kernel-role둘다skip. host-init0은인과확정아님.
- 외부5건은§3,미감사/부분감사6영역은위인계. 새감사/동일인수재실행없이사이클종료.

## MJS 검사 수치의 보증 범위 (과거 실행과 현재 수정 구분)

수신 숫자는 실행별 기록으로 보존하되 실제 장비·화면 인수로 승격하지 않는다. [[2026-09-18_MJS_수치인용_정정_Codex]] 및 [[2026-09-18_MJS_후속3도구_감사_Codex]]가 아래 범위의 근거다.

| 수치·도구 | 수치가 보여주는 범위 | 보증하지 않는 것 / 남은 조건 |
|---|---|---|
| 2-PC67 checks / verify_two_pc_distributed_execution.mjs | 해당 실행의 HTTP 응답 필드·상태 조건. 감사에서는 합성 fetch로67/67 재현 | 새dispatch와 receipt의run/node/attempt/epoch 결속, artifact bytes/hash, 실제2PC·GPU 학습·브라우저. 1ecdb12 수정79/79보고수신. 실제장비관측/음성대조경로review잔여 |
| browser smoke200/202 checks / run_browser_smoke.mjs | 당시 runner의 HTTP/WebSocket 등 조건 집계. 숫자 자체가 DOM/화면 조작 관측 수는 아님 | UI상수true3건은 관측0인 PASS, 구버전shard2단언은 빈목록가드 없음. shard가드는9251f18 수정/작성자·사용자12회귀 확인, 전체200/202 재실행/재인증 아님. VB-MJS-02 수정 필요 |
| reconciliation59 checks / reconcile_receipts_evidence.mjs | 감사의 합성 응답+로컬해시 계산으로59/59. 과거보고는 각 실행SHA·입력 범위만 적용 | 실제5화면 DOM관측, working/frozen bytes대조, receipt-shard-output 결속. 1ecdb12 수정64/64보고수신. 실제editor/계약review잔여 |
| 별도 실제 browser6passed | 합성IdP+실제HTTP+격리PG 기반 해당 브라우저 시나리오 | 위MJS와 다른 harness/분모다. 운영SSO·5대장비·전체UI 인수로 확대하지 않으며 MJS결함으로 자동무효화하지도 않음 |

MJS 전체가 실패 불가능하다는 뜻이 아니다. 물리정지false 대조군은2PC66/1·reconciliation58/1 exit1이었다. 과거 실제 실행이 mock/조작이었다고 주장하지 않는다. 과거200/202에서 결함단언을 산술로 빼 새합격수로 제시하지 않는다. [[2026-09-18_MJS_빈집합단언_감사수정_Codex]]의 빈배열이 과거실행에 실제발생했는지도 미확인이다.

## 1. 실제 검증 완료 — 명시한 범위만

| 범위 / 고정 SHA | 실제 증거 | 독립 확인과 한계 |
|---|---|---|
| CX-01 canonical 제어 평면 / fe4c04c | 실제 인증/PG·owner scope·통합 route, 별도 실제 HTTP browser6통과 | 개발 기준선 병합. 합성 IdP와 격리PG이며 운영 SSO/실장비 완료 아님. [[2026-09-18_CX-01_정본착지_Codex]] |
| 원격 모델 권한 결속 / 8c347b7→e89a415 | 파일별 실제PG79passed/0skip. CAS fixture 정상화 후 remote6건 도달·통과 | 사용자 명시4파일75통과, Claude c9e6ddf 이전8c/e89 sound 소스검토. 합산하지 않음. [[2026-09-18_원격모델권한결속_Codex]] |
| 호출자 transaction registry 재검사 / 0a16658→1b39d40 | 실제PG 신규7+기존16=23passed/0skip | 사용자 같은2파일23통과. 기존 binding만 허용·SHARE 잠금 유지. [[2026-09-18_Registry_트랜잭션재검사_Codex]] |
| frozen registry→승인/dispatch/delivery/claim / e2908a5 | 명시5파일실PG84+오프라인60=144passed | Claude c9e6ddf sound/finding없음 **소스검토**. 원격 전송/실행 장비 인수 아님. [[2026-09-18_Registry_실행권한결속_Codex]] |
| 운영자 policy 설정 연결 / 11e9f44→d7e7d13 | offline34+실PG 기존catalog API12=46passed/0skip | **Claude7e3de2a 독립 소스 검토 sound 수신**. 초기 관측용DSN application_name 차이12setup오류 별도 보존. [[2026-09-18_Registry_운영정책설정_Codex]] |
| Claude diagnostics/cleanup R2~R5 / d59b8a6→b378785 | 사용자독립24passed(실Docker2포함), Codex22passed/실Docker2제외·격리import통과 | 브랜치 blocker 해소. image 보안8케이스 합격 아님. [[2026-09-18_Registry_실행권한결속_Codex]] |
| 기본 시험 선택 / 3afe227→1eaf285 | 비integration1179passed/489skip/2deselected,66.23초 | 사용자같은선택1179/489/2/0,75초. CI설정은 수정만 했고 CI실행 없음. Claude Docker부재22pass/2skip은 marker분리 전 세파일 시험. [[2026-09-18_Docker_시험선택경계_Codex]] |
| VF-CX-05 패키지 무결성 / 50fbb1a | offline21passed, 실제패키지2archive hash일치 | certificate/peer policy 만료로 전체exit1. 설치가능/운영인수 아님. [[2026-09-18_Workspace_아카이브무결성_Codex]] |
| 복원 관측 도구 경계 / 22059e9 | 격리PG 관련40passed/0skip, 설정·실제PITR 증거 분리 | 운영 --require-pitr는exit1/archive_mode off/pitrVerified false. **운영 RPO 충족 증거가 아님**. [[2026-09-18_VF-PITR-BOUNDARY_Codex]] |

이전 VF-CX-04 Linux140/140은 한 Docker host의 격리 Node 시험이었다. 실제2PC/5PC·GPU 인수로 바꾸지 않는다. 기존 점수2775/4800=57.8125%,잔여42.1875%는 과거 산식이며 최신 구현을 재채점하지 않았다.

## 2. 미검증/미완으로 기록된 것

| 항목 | 정확한 현재 상태 | 다음 내부 행동 / 담당 |
|---|---|---|
| 최신 image lane | f4b3f73 harness + b93b5ef1f944… digest:4passed/2failed/2skipped. public-signing-key/business-workspace daemon I/O timeout2, workspace/business-kernel-role operation-timeout2. 해당4건 케이스전체단언 미검증, host-init 관측0 | 아래 호스트 재개 조건 충족 전 추가실행 중단. Codex |
| business-kernel-role | 잘못된 DB role의 image 기동 거부 단언은 네 실행 모두 미검증 | 전체image실행에서 해당 단언 도달·거부를 별도case evidence로 확인. classifier24통과로 대체 금지 |
| 최신489skip | 사용자6feccd8 비integration/DSN없음의미실행,개별원인분포전수미확인 | 전체가 해소됐다고 하지 않음. 필요 변경별 파일 단위 실PG 검증, skip이유·SHA 기록. Codex |
| 2deselected Docker host 시험 | 기본 경로에서 의도적 제외. 과거사용자d59실제2건통과와 최신선택에서의 미실행은 별도 | 격리host의 명시 docker_host lane/Core CI에서 실행. 공유host에서 자동prune 금지 |
| 11e9f44 policy 설정 | 로컬46통과, Claude7e3de2a sound; 운영rollout 미완 | 운영owner rollout 준비. 모든worker에 같은시작policy 전달·구프로세스 종료 계획 필요. hot reload/전역policyepoch 없음 |
| 공개 registry/runtime 준비 서비스 | trusted worker 및 승인 경계는 구현. 신규 공개 prepare API·대용량/GPU/routing/data/tensor-pipeline은 이 증거에 없음 | 미지원/후속구현과 미검증을 구분. 현재 상태정리 요청에서 새 구현 생성하지 않음 |
| .225/실5대 | 18443 연결3회timeout 과거증거, 유효profile/mTLS·장비 실행·이탈/복구 인수 없음 | 운영자 준비 후 아래 단계별 재개. 소프트웨어 mock/loopback시험으로 대체 금지 |
| AC-12 RPO/PITR | 목표 달성 **미입증**. 최신 운영관측 archive_mode off/pitrVerified false. 백업 직후의 거의0초 간격은 RPO 인수 증거가 아님 | Claude는 사용자 배정 compose변경안·격리리허설·용량/저장소 요구 준비. Codex는 인수지표·증거 독립검토. 실제 적용은 운영자 결정 |

4/3/2 image 통과수 변동은 harness가90c07c6/9e69dcc/b5f770a로 달라 호스트 조건만 통제한 인과실험이 아니다. OneDrive 핸들 증가와 쓰기버스트 상관은 기록하되 NTSTATUS의 원인으로 확정하지 않는다. 제품단언 실패관측0은 미도달 단언의 통과가 아니다.

## 3. 외부 조치 대기와 재시도 조건

| 대기 / 담당 | 재개를 여는 확인 가능한 조건 | 재개 첫 행동 / 합격에 필요한 증거 |
|---|---|---|
| GitHub Actions 결제·지출한도 / 운영자 | 계정 한도 해소 및 runner가 실제 job을 시작할 수 있음 | Codex가 검사할integration SHA를 고정하고 필수workflows 실행 확인. run ID/commit/exit/artifact·선택범위 기록. job시작 전billing 실패는 코드시험실패/통과 어느 것도 아님 |
| gh CLI 인증 / 운영자 | 저장소의 run/artifact를 읽을 수 있는 인증 복구 | Codex가 동일SHA run상태 조회. 인증은 조회조건이고 결제·CI통과를 대신하지 않음. 현재조회재시도 요청 없음 |
| 호스트 환경 / 사용자 | 사용자 환경조치 완료 보고, 실행 직전 시각·OneDrive handle 수준과 증가 추세·가용RAM·Docker process 시작 상태 관측, 동시agent의image실행이 없는 조용한 구간 확보.119773을안전임계치로가정하지않음 | Codex가 **같은 고정 harness SHA·같은image digest**로8케이스를 순차 재실행. 각 보안단언 도달/결과·cleanup미확정·JUnit/JSON·환경조건 기록. b5f770a와최신harness 결과를 섞어 인과판정하지 않음. 8건 도달/통과 전 전체합격 금지 |
| 원격192.168.45.225 profile/mTLS / 원격운영자 | 승인된 설치 대상·접근경로와 유효한서버/peer인증서·신뢰root/endpoint/Node/epoch/profile 제공, 장비 접속 가능 | Codex는 읽기전용 preflight→패키지archive/digest/인증서/peer policy검사→fresh mTLS/Node identity확인. 통과 후 승인된 운영계획에 따라 실제workspace/terminal·storage/model·거부·Node이탈/복구를 순서대로 검증. 5대 전체 확인·인수기록 없으면 VF05완료 금지 |
| AC-12 운영PITR 적용 / 운영자, 준비Claude | 변경안 검토·운영적용 결정, 실제archive저장소/용량·보존기간·키/접근·실패감시·복원대상 확보 | Claude격리리허설을 Codex가 먼저검토. 적용 후 실제설정/연속WAL·basebackup을 확인하고 격리복원대상에서 목표시각 전후transaction으로 도달/제외를 증명. 실패기준시각 대비 복구된 최신 durable transaction 시각의 차이를 RPO로 측정하고 승인된 AC-12 목표와 비교. 복구시작~서비스사용가능 RTO·무결성·tenant권한도 별도 기록 |

기존 사용자 대기4건(CI결제,gh인증,호스트,원격설치)은 유지한다. **AC-12 운영PITR 적용은 이번에 별도로 명시한 운영준비도 의존성**이며 routine 코드승인으로 해소되지 않는다. 설정명 존재나 백업복원 성공만으로 목표를 충족 처리하지 않는다. 운영정량목표는 승인된 인수 manifest의 수치를 사용하며 이 문서에서 새 숫자를 만들지 않는다.

두 compose의 archive_mode/archive_command/wal_level/archive_timeout/data_checksums 명시문자열은 기준SHA에서 없음(rg exit1). 이는 배포정의 확인이며 실제서버 값을 새로 측정한 것이 아니다. 운영 archive_mode off는 앞선 고정증거다. archive/checksum 설정 자체도 PITR/RPO 합격의 충분조건은 아니다.

## VF 운영인수 0/5의 의미와 카드별 재개

| 카드 | 이미 있는 개발 기반 | 운영인수에 추가로 필요한 조건 |
|---|---|---|
| VF-CX-01 | canonical factory/실제JWT/PG·route·image 일부단언 | 해당SHA CI·전체image보안단언·운영IdP/HTTPS/역할경계·복구준비, 독립리뷰와 운영자 인수. MJS 상태코드/필드 숫자로 인증·역할 인수를 대체하지 않음 |
| VF-CX-02 | ModelManifest/hash/lease·registry binding/정책 검사 | 실제Node 저장·손상/repair/retention·권한거부 증거, 운영policy와profile확정, 전체필수검사/리뷰. 해시 접두사/string 존재가 아닌 실제 bytes·검증digest 필요 |
| VF-CX-03 | locality/예약·bounded remote 읽기·frozen authority | 실제 장비 topology·현재grant/channel/location·실제전송/스케줄실행·장애경계와 측정값. 67checks 대신 해당dispatch와 node/receipt identity 결속 증거 필요 |
| VF-CX-04 | CPU32KiB bounded adapter·fence/retry·단일host 격리Node시험 | 실제장비에서 승인/취소/stale permit/Node-loss·대체실행과결과 무결성. 미지원GPU/collective를 합격범위에 포함하지 않음. receipt의run/node/attempt/epoch·stop·artifact bytes를 대조; 고정receipt나GPU telemetry만으로 실행 인수 금지 |
| VF-CX-05 | 오프라인패키지검사·preflight·복사본migration/복원준비 | 선행카드 인수+5대 전체여정·운영권한/HTTPS·장애복구·AC-12정량증거·사용자 인수. 200/202·59 숫자 대신 실제화면 조작/재로드·실장비·frozen bytes 증거와 통제된 복원 판정 필요 |

0/5는 위5개 운영인수 카드의 완료0건이다. 구현0%, 모든시험미실행, 또는 실제PC0/5라는 뜻으로 쓰지 않는다. formal48task done0/48과도 다른 분모다. 현재 문서감사로 어느 카드도 done으로 바꾸지 않는다.

## 이번 정리의 검증 및 인계

owner Codex, reviewer Claude(지도 자체는미검토), branch agent/codex/model-registry-binding. agent-delivery1.1.0 적용. 공통판1.0.96/Codex1.0.63/VF1.0.22, History·image-tests.json·AC-12 registry 기준을 대조했다. 사용자 CL-07 정정·compose관측 수신, compose텍스트 독립확인. CI/Docker/원격/DB 재실행0,제품코드변경0. 다음 Claude: PITR준비안/실측증거 제출, 이번지도 및11e9f44 설정검토. 다음 Codex: 제출증거의 도달여부/실측범위 검토. 외부조건 변화 전 동일인수 재시도를 반복하지 않는다.


## 호스트 조치 후 갱신

[[2026-09-18_IMAGE_OneDrive재시작후판별_Codex]]: 사용자OneDrive재시작/조용한구간재검증완료수신. 핸들감소와host-init0회는확인,원인확정은보류. 현재4pass/2daemon-timeout fail/2operation-timeout skip. 호스트조치대기는 '최초조치미실시'에서 '잔여timeout진단/조건개선대기'로갱신한다. Docker사용은허용됐지만추가인수반복실행없음. 최신image-tests.json/이전보존JSON참조. 기존표의호스트재개조건은다음재검증에도적용하며전체image합격/운영0/5는바뀌지않는다.

## PITR 준비안 검토 수신

[[2026-09-18_PITR_준비안_검토_Codex]]: Claude 8c72fbf 검토 결과 R1-01~04 수정 전 착지 보류. 논리 복원을 PITR로 간주한 판정, same-host MinIO의 off-host 보장, archive 재시도·용량 설명을 수정해야 한다. 따라서 남은 사항이 모두 외부 조치인 것은 아니다. 다음 내부 담당 Claude: 준비안/격리 PITR 증거 보강; Codex: 수정본 재검토. Docker 실행/운영 적용 없음. 사용자 image 방법론 정정 수신, 동일 lane 반복 없음.

## 검증 경계 표본 감사

[[2026-09-18_검증경계_표본감사_Codex]]: tools51/tests179파일 패턴 검색, 합성 CLI9관측으로 deployment_surface의 factory 오류/attr 부재 성공 처리와 위조 Bearer probe 예외 누락 P2 두 건 확인. 빈 route 입력은 P3 보강 후보. 기존 offline73시험 통과가 이 미검증 경로를 대체하지 않음. 다음 Codex: VB-AUDIT-01/02 수정; Claude: 독립 검토/PITR 수정본. 이번 감사는 미수정 finding이며 Docker/DB 실행 없음.

## 검증 경계 finding 수정

[[2026-09-18_검증경계_오류분류수정_Codex]]: VB-AUDIT-01/02 로컬 수정·offline88시험 통과, Claude 독립검토 대기. factory 인자 결속과 본문 오류 분리, 위조 Bearer 검사 미완료 nonzero, 빈 route 입력 P3는 exit2 미판정으로 보강. 과거 감사의 미수정 표기는 당시 상태. 운영인수/CI·실장비 미완 상태 유지.

## 검증 감사 잔여 범위와 독립 재현 수신

[[2026-09-18_검증경계_후속감사범위_Codex]]: VB-AUDIT-02 사용자 clean worktree 두 앱(RuntimeError→exit1,실제401→exit0) 독립 재현 수신. VB01/02는 작성자 시험+사용자 명시 경로 독립 실행 확인, Claude 소스검토 대기; P3는 사용자 판단 동의. 미감사 영역6종과 다음 실패 대조군 정리. 우선순위1 Python검색 밖 .mjs 인수 스크립트,2 실행/증거/CI 집계 경계. 새 finding/추가 운영실행 없음.

## MJS 빈집합 단언 수정

[[2026-09-18_MJS_빈집합단언_감사수정_Codex]]: shard2단언에 배열/고정2개 가드,실제문장 offline Node12시험 통과. .mjs4파일 every5곳 중 나머지3곳 개수가드 확인. 추가 VB-MJS-02 UI const true PASS3건(P2) 미수정, Gemini 실제 UI 검증 보강/Codex review 인계. 과거 full smoke 실입력은 미확인. Claude PITR a681da3 도착, 다음 재검토 대상.

## PITR a681da3 재검토

[[2026-09-18_PITR_a681da3_재검토_Codex]]: 물리복원 경로/MinIO 정정 확인, Claude 성공텍스트 수신(사용자·Codex 실PG 재실행 없음). R2-01 after INSERT 실패 후 PASS 합성재현(P1), R2-02 변경명령 무차별재시도/소유권없는cleanup(P2), 기존R1-04 설명미해소로 전체착지 보류. 다음 Claude 수정/증거, Codex 재검토. shard9251f18 수정은 별개 착지.

## MJS 나머지3도구 감사

[[2026-09-18_MJS_후속3도구_감사_Codex]]: 사용자 shard가드12회귀 독립통과 수신. 합성 fetch로2PC67/67·reconcile59/59 exit0(unrelated receipt/invalid digest), 물리정지false 대조군은각1failed/exit1. VB-MJS-03 실행결속/실장비주장P1,04 로컬상수hash를snapshot검증으로표시P2,05 실패시verified문구P2 미수정 인계. handoff재현도구는 scope명시된 관측JSON이며 이번소스검토에서 추가finding없음. 다음 Gemini수정/Codex검토, 실제장비실행0.

## PITR09db057 gate 재검토

[[2026-09-18_PITR_09db057_재검토_Codex]]: 사용자 실제PG 정상0/after-insert음성1 수신+소스대조로R2-01해소. Codex는PG재실행없음. archive명령 순차4조건 정상,다른writer게시 interleaving은덮어쓰기 관측. 고정tmp논거는전용아카이브·단일writer 한정이며전역직렬성아님. R2-02/R1-04미해소로전체착지보류,다음Claude수정/Codex재검토.

## 최신 API smoke 및 호스트 관측 수신

[[2026-09-18_실행증거집계_감사_Codex]]: 사용자/Gemini1ecdb12 API smoke79/79·reconciliation64/64 보고수신, Codex실HTTP재실행없음. label/조건부배너/추가bytes·digest비교는소스확인,음성대조와실editor관측의계약검토는잔여이므로이전finding전체해소미선언. 앞선67/59는이전SHA감사증거로보존. 검사증가12개를누락조건전체수로해석하지않음.

사용자OneDrive handle2421→약1시간후119773/RAM1665MB관측수신. 호스트재개조건에실행직전level·추세·시각을명시. 누수원인/안전임계치/NTSTATUS인과확정없음. 집계감사AGG01staleXML및AGG02불완전증거exit0 두P2 미수정, 다음Codex수정/Claude검토.


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

MJS-02 인계 구체화(기준8a8e3db): Gemini owner/Codex reviewer. 상수 UI 3건은 API smoke PASS에서 제외·미검증 표기가 최소 수정이며, 실제 browser 관측을 선택하면 항목별 음성 대조가 필요하다. [[2026-09-18_Codex_감사사이클종료와다음세션인계]]의 처리 계획 참조. owner 수신·착수는 미확인. PITR/해당 수정본 대기, 새 감사 없음.

최종 호스트 관측(사용자 보고): OneDrive handle은 재시작 직후 **2,421 → 약 1시간 후 119,773 → 현재 296,475**, 가용 RAM은 현재 **1,078MB**다. 과거 641,442에서 image host-init 실패가 관측된 이력과 함께 다음 재개 조건에 추가한다. 재시작은 임시 완화이며 vault가 OneDrive 동기화 경로에 있는 한 handle이 다시 증가할 수 있다. image lane 재개 전에는 실행 직전 handle 수준과 증가 추세, 가용 RAM, Docker process 시작 상태, 동시 image 실행 부재를 다시 확인한다. 이 시계열은 호스트 압박과 정합하지만 OneDrive 단일 원인이나 안전 임계치를 확정하지 않는다. 추가 image 실행은 새 환경 조치 없이 반복하지 않는다.

## 2026-09-19 recovery fixture와 cleanup backstop 최신 상태

- 코드 기준 `aeec9b3`는 수정 전 checkout `53f81ba` 뒤다. 그 checkout의 당시 terminal-only 수치는 전체 JUnit이 없어 역사적 요약으로만 남긴다. 후속 `40e921b` JUnit 5배치에서는 recovery 기존 setup errors 18건이 모두 사유가 보이는 skips로 기록되고 errors는 0이다.
- Codex의 `.venv\\Scripts\\python.exe -m pytest -q tests/integration/test_recovery_drill.py` 실제 disposable PostgreSQL 16 결과: `CX01_CONTAINER` unset 시 19 tests 중 18 reasoned skips/1 standalone pass/0 error/failure(exit 0); 명시된 owner-label container 시 13 passed/4 Linux-only skips/2 archiver fixture readiness failures/0 errors(exit 1). 18개의 DB fixture tests 중 12 본문 pass, 4 플랫폼 skip, 2 준비 timeout이며 full test file clean-pass는 아니다. 상세 JUnit 경로·시각은 [[2026-09-19_recovery_drill_Docker_전제_skip_경계_Codex]].
- 정리 도구 allowlist의 실제 누락 `ai.saintvision.rpo-test`와 `ai.saintvision.rpo-network`를 포함해 literal label inventory를 보강했다. 신규 policy test는 26개 코드 label literal의 cleanup eligibility 또는 explicit non-cleanup 분류를 검증한다. rpo-test 누락 변이에서 exit 1, 복구 후 cleanup/recovery unit 17 passed. 삭제는 실행하지 않았다.
- 두 archiver parameter의 최신 재실행은 실제 inspect/logs 상태에 맞춰 각각 host-network prerequisite skip으로 분류됐다. 별도 실제 exited/FATAL negative control은 failure였다. 상세 기록 [[2026-09-19_archiver_readiness_boundary_Codex]].
- 외부 차단은 그대로 분리: CI billing/gh 인증, Gemini 인증, 타 플랫폼 조건, 원격 실장비 및 AC-12 운영 PITR.

## Claude 40e921b 통합 회귀 JUnit — 5배치 산술 합

Claude 작성 실행을 Codex가 원본 JUnit과 manifest로 재파싱했다. 다섯 배치 합은 **2628 tests / 2192 passed / 1 failed / 0 errors / 435 skipped**이며 단일 실행 결과가 아니다. Absolute interpreter는 프로젝트 `.venv`, KST JUnit timestamps는 17:59:10~18:24:06, full collect 177 test files와 배치 합집합 187 files 사이 누락 0/중복 0이다. 추가 10개는 support modules다. 단일 failure는 migration-head upgrade가 부하 중 subprocess `TimeoutExpired` 180초였다. 전체 aggregate의 exact command skeleton, 배치별 결과, artifact 경로 및 해석 한계는 [[2026-09-19_archiver_readiness_boundary_Codex]].
