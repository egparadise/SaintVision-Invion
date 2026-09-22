---
doc_id: "WORKBOARD-CLAUDE-001"
title: "Claude 작업 현황"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-11T18:40:00+09:00"
source_of_truth: "Git"
---

# Claude 작업 현황

[[전체 개발 진행 현황]] → 이 페이지 → [[Agent 지속 개발 운영 규칙]] 순서로 확인한다. 이 페이지는 현재 후속 카드 목록이며 이전 장문 보고서는 SHA별 근거다.

- 배정 owner: Claude. 독립 reviewer: Codex. 최신 수신·착수·독립검토 상태는 아래 SHA별 인계 기록을 따른다.
- 공통 Skill: agent-delivery v1.1.0, 역할 Skill service-integration v1.0.0. 계획: [[Backend 최종 개발 계획]], [[DB 최종 개발 계획]], [[Storage 최종 개발 계획]].
- 계약: GUIDE-001, GOV-AGENT-001, GOV-GIT-001, ADR-INDEX-001 v1.27.0, [[Codex Workspace 편집과 PTY 및 원격 Git 계약]] v1.1.0, [[Codex 실제 실행 결과 조회 계약]]. 계약 변경 시 버전 갱신.
- 확인 기준: 2026-09-11T17:07:33+09:00. 준비됨(ready)은 아직 착수했다는 뜻이 아니다. 차단 카드 대신 선행 없이 가능한 ready 카드를 진행한다.

## 최근 확인한 진척

독립 검토 — 커널 쓰기면 감사 a2dada9a (Claude, 2026-09-22): 28 라우트 완전 확인 + 프런트 직접호출 실측 + **발견: replay 분기 앵커 12개 vacuous**(격리 워크트리 변이로 전부 제거해도 44 passed 불변; 무효-prior replay 거부 시험 부재). fresh 앵커는 무게 있음(대조). 재생/replay 자리라 어젯밤 우회와 동류. 전문 [[2026-09-22_Codex_커널쓰기면감사_독립검토_Claude]].

독립 검토 — 저위험 쓰기 계약 7건 기록 대 코드 (Claude, 2026-09-22): f2d86db5(문서 전용)가 기록한 7건이 tip `ce300cf5` 코드에 전부 live함을 대조 확인(모델·route response_model·fixture·회귀 19 passed) + 무게(7 앵커 KILLED/복원). 기록==코드, 누락 0. 전문 [[2026-09-22_Codex_저위험쓰기계약7_코드대조_독립검토_Claude]].

독립 검토 — Codex 부재주장 회귀가드 (Claude, 2026-09-22): `2679f0c7`(닫힌 도메인 + retry-terminal 가드)를 통합 tip에서 실행(29+47 passed)하고 non-vacuity 직접 확인 — 미지값 거부 loc가 전부 정확히 enum 필드, positive clean, FAILED 종단 실측. sound·non-vacuous 판정. Codex 큐 안 늘림. 전문 [[2026-09-22_Codex_부재주장회귀가드_독립검토_Claude]].

S09/S10 교차 증거 (Claude, 2026-09-22, `efdf4544`): Codex 큐(내 S02·S03, Gemini S01-FE 대기)를 안 늘리는 방향으로, c402c81a와 같은 인용용 실PG 증거를 내 레인 S09/S10에 만들었다. **S10 228 passed/0 skip**(계보·모델 append-only·보존pin·배포digest·tenant격리 → S10-DB/ST/BE), **S09 76 passed/21 skip**(불변Context·RunRecord봉인불변·eval golden·diff/test/trace pin → S09-DB/ST; skip 21=test_results.py Linux사설스토리지 정직게이팅). seam 계약(Codex) 대기가 아닌 부분만 골랐다 — 기존 테이블 불변성·계보는 이미 구현돼 실측만 필요. not_run: RunRecord 완료파이프라인 실출력바이트·물리노드·CI. self-close 아님. 전문 [[2026-09-22_계보모델불변_컨텍스트eval_교차증거_실PG_S09_S10_Claude]].

검증 정정 (Claude, 2026-09-12): 이번 세션 내내 `--ignore=tests/integration`으로 제외해 **integration 10개 파일 110건을 검증에서 빠뜨리고 있었다.** 그 10개는 Node 런타임이 필요 없고 로컬에서 그대로 통과한다. 저장소에는 이미 `tools/node_dependent_tests.py --pytest-args`가 있고 CI의 `backend.yml`은 그것을 올바르게 쓰므로 **저장소 결함이 아니라 내 검증 습관의 결함**이었다. derived 제외로 전체 재실행: **1029 passed / 20 skipped / 0 failed**. 앞선 보고의 861~919라는 수치는 실제보다 좁은 범위였다.

인계 (Claude, 2026-09-12): CL-01~CL-07의 finding 4건·필요한 결정 6건·검토 요청 도구 7종을 [[Agent 인계 대기 목록]]에 등록했다. 각 카드의 '인계' 조건은 이것으로 충족되며, **실제 수신 확인 전까지 pending이고 어떤 카드도 승인으로 표시하지 않았다.** 내가 더 진행할 수 있는 것은 결정 6건 중 하나가 오는 시점부터다.

CL-07 (Claude, 2026-09-12): 4b09dfc·c632d3f. WAL·PITR을 검증하다 **복원 시험의 RPO 숫자가 실패할 수 없는 값**임을 발견해 "이번 복원의 간격"과 "설정이 보장하는 한계"로 분리했다. 이 배포는 `archive_mode=off`라 시점 복구가 없고 **AC-12의 RPO 목표는 미달성**이다. 인수용 gate `--require-operational-rpo`는 지금 exit 1이다.

CL-05 (Claude, 2026-09-12): dcad652. Context의 redaction을 caller 선언에서 **거부**로 바꿨다. 단위 시험 13개는 배선을 끊어도 전부 통과했고, DB를 거치는 배선 시험만 그것을 잡았다. Context에 호출자가 없다는 점과 TTL이 수명 결정을 먼저 요구한다는 점을 남은 문제로 기록했다.

CL-02 (Claude, 2026-09-12): 5995b8b. 운영 준비 판정을 입력·권한·실행 admission 셋으로 분리하고 각 거부가 발동함을 실측했다. 핵심 증거는 "권한 전부 정상 + kill switch ON → 권한 거부 없음, 실행 불가"다. 실제 운영 입력(계정·폴더·원격 profile·object endpoint)은 여전히 대기 중이며 지어내지 않았다. 전문 [[Claude_CL-02_운영준비_검증보고]].

CL-01 (Claude, 2026-09-11): d14db0a 독립 검토 완료. finding 2건(F1 제공량 기록·실제 불일치 재현, F2 PTY 감사 순서)을 Codex에 인계 대기. definer 함수 9개 전수 tenant 결속을 실측으로 확인했다. 전문 [[Claude_CL-01_커널독립검토]].

9995122: 복원에 public+inv 테이블 수·권한 digest 대조를 추가하고 live pg_proc definer 점검 도구를 작성했다. 코드 변경 확인이며 이 문서 작성자가 새 도구를 실운영 검증하거나 독립 승인한 것은 아니다.

0581964 (Claude, 2026-09-11): 복원 시험에 인가 모델·definer 함수·서비스 재개·RLS 실제 작동 검사를 추가했다. policy 122개가 전부 살아 있고 digest까지 동일하면서 두 tenant가 서로 보이는 복원본이 기존 검사를 모두 통과하던 것이 핵심 결함이었다. 남은 object 저장소·journal은 각각 S01 미결정과 원격 설치에 막혀 있다.

c28cdff (Claude, 2026-09-11): CL-03이 지목한 네 결함을 수정하고 각 검사가 실패할 수 있음을 로컬에서 실증했다. 네 결함 모두 "증거 없는 통과"를 만들고 있었다 — 특히 fencing 조회 실패가 0으로 읽혀 "safe"가 출력되던 건은 복원 수락 여부를 결정하는 검사에서의 거짓 통과였다. 정상 시험 RTO 6.1s·RPO 6.2s, old epoch 시험 exit 1. 역할·RLS·object 저장소·서비스 재개는 아직 검사 밖이므로 전체 복원 합격은 미완료다. reviewer Codex의 독립 확인은 아직 없다.

## 작업 카드

각 카드의 sprint/area/outcome/acceptance는 부모 task에서 상속한다. 원래 task owner를 바꾸지 않는다. CL-01은 독립 검토 업무다. 카드 상태와 원래 48개 task의 최종 done은 별개다. 각 카드의 base/branch와 실제 검증값은 착수 시 담당자가 고정한다.

| 카드 | 우선순위 | 상태 | 부모 task | 범위 |
|---|---|---|---|---|
| CL-01 | P0 | in-progress | S01-DB S04-DB S06-BE S06-DB S08-DB | Codex 최신 커널 독립 검토 |
| CL-02 | P0 | in-progress | S02-BE S02-DB S02-ST S03-DB | 운영 로그인·권한·Workspace·폴더 적용 |
| CL-03 | P0 | in-progress | S12-DB S12-ST | 복원 도구의 남은 검증 결함 수정 |
| CL-04 | P1 | blocked | S03-DB S03-ST S09-ST S10-ST | Artifact·모델 바이트 정본과 보존 정리 |
| CL-05 | P1 | in-progress | S09-DB S09-ST S10-BE | Context와 실제 Provider/도구 Adapter |
| CL-06 | P1 | blocked | S10-BE S10-DB S10-ST | 실제 학습·평가·MLflow·승인 배포 서비스 |
| CL-07 | P1 | in-progress | S12-DB S12-ST | 운영 관측·장시간 시험·복원 절차 인수 |

### CL-01 — Codex 최신 커널 독립 검토

- owner / reviewer: Claude / Codex; status: **finding 전부 닫힘**(F1 철회·F2 수정·F3/F4 소멸); priority: P0.
- **F1 철회(2026-09-14, 내 오류)**: 재현이 실제 `release()` 경로를 쓰지 않고 lease 행만 잠그는 UPDATE를 손으로 재생했다. 실제 `release()`→`_locked_lease`→`lock_resources`는 `inv.resources`를 `FOR UPDATE` 잠근다(e6336a7, 검토 SHA 이전). `d14db0a` 소스 직접 재확인. Codex `51f4004` 회귀 시험이 정상 경로 고정. **CL-01의 finding은 모두 닫혔다.**
- 재확인(2026-09-13, workspace-bridge 6ff090b): **F2 수정 확인** — intent-before-execute, `0034` DDL(FORCE RLS·immutable) scratch DB 적용 실측. **F3/F4는 entrypoint 복원으로 소멸.** **F1 미해결**(leases/0031 무변경, 재현 절차 유효). B-9는 live에서 완전 종결(`apptestonly` 거부, role shape `ok`). 상세는 [[Agent 인계 대기 목록]] 재확인 회신.
- 원래 목표/합격 조건: OUT-01, OUT-04, OUT-06, OUT-08 / AC-01, AC-04, AC-06, AC-08.
- 검토 SHA: `agent/codex/workspace-bridge` **d14db0a**(카드가 지정한 `c5f2154`를 포함한 현재 head), migration head `0033_workspace_bridge_merge`. 전문은 [[Claude_CL-01_커널독립검토]].
- 실제 수행: 0028~0033의 적용 함수·grant, reservation/출력, PTY ticket/frame, Git dispatch/current scope를 지정된 범위대로 보았다. 작성자 시험 기록을 승인으로 옮기지 않고, 확인한 것은 직접 조회·실행한 결과만 적었다.
- **Finding 2건(수정 담당 Codex)**:
  - **F1 (중간, 재현함)** `apply_capability_offer`가 lease 총량을 서로 다른 snapshot에서 두 번 읽는다. `release()`는 lease 행만 잠그고 자원 행은 잠그지 않으므로 그 사이에 commit된다. 함수 자신의 문장 순서를 두 session으로 재생해 **요청 1000 / 기록 900 / `applied=true`**를 재현했다. `remaining`이 0으로 끝나므로 loop 끝의 검사로는 잡히지 않는다. 방향은 보수적이지만 `public.resource_offers`의 기록과 커널의 실제가 말없이 달라진다.
  - **F2 (중간)** PTY frame의 sequence·digest 감사가 Node 실행 **뒤에** 있다. 같은 sequence로 내용이 다른 frame을 다시 보내면 Node에서 실행된 뒤 거절되고, 감사 행은 첫 내용의 digest를 유지하며 event는 `if inserted`라 남지 않는다. 실행된 것과 기록된 것이 어긋날 수 있다.
  - F3(낮음) 폐기된 definer 함수 `run_committed_outputs`·`apply_resource_offer`가 grantee 없이 남는다(`proacl` 실측). F4(정보) `.git` 제외 규칙이 `export_snapshot`과 `git_files`에서 다르다.
- 실제 검증 증거(로컬 PostgreSQL 16): F1 재현 로그, head DB의 `pg_proc` 전수 판정 **definer 9개 전부 tenant 결속·`search_path` 고정·unsafe 0·오탐 0**, `proacl` 실측, offer 경로와 `lock_resources`(`leases.py:32`)의 잠금 순서 일치 확인, 경합 없는 실행에서 `sum(offered)=요청량` 일치.
- 확인하여 문제 없던 것: 0029의 처음부터의 tenant binding, 0030의 `subject_kernel_link`가 0026 누수를 막는 정의를 head에서 유지, `inv.account_provisioning_events`의 RLS ENABLE+FORCE·USING/WITH CHECK·immutable trigger·전 role REVOKE, PTY의 Node 호출 전후 이중 권한 확인과 일회용 ticket, `TerminalText`의 상한과 완전 행만 방출, Git의 요청자≠주체 시 `can_approve` 전환(4-eyes)과 snapshot/digest 검증.
- 남은 문제: F1·F2의 해결 SHA가 아직 없다. 모든 소스 줄의 보안 감사, Node 런타임이 필요한 통합 시험, 2대 이상 실장비 PTY/Git 여정은 이번 범위 밖이며 후자는 원격 설치(.225)가 선행이다.
- 다음 첫 행동: F1·F2를 Codex에 인계하고, 해결 SHA가 나오면 Claude가 재확인한다. 그동안 Claude는 CL-02 운영 준비를 진행한다.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CL-02 — 운영 로그인·권한·Workspace·폴더 적용

- owner / reviewer: Claude / Codex; status: in-progress(판정과 시험 완성, 실제 운영 입력 대기); priority: P0.
- 원래 목표/합격 조건: OUT-02, OUT-03 / AC-02, AC-03.
- 진행 branch/SHA: `review/claude-account-results` **5995b8b**. 전문은 [[Claude_CL-02_운영준비_검증보고]].
- 실제 수행: `tools/operational_readiness.py`와 `tests/test_operational_readiness.py`를 만들어, 카드가 요구한 **권한 부여와 실행 admission의 구분**을 판정 구조 자체로 분리했다. 운영 준비는 스위치 하나가 아니다 — 로그인할 수 있는 사람이 작업을 요청하지 못하고, 존재하는 project는 의도적으로 커널에 연결돼 있지 않으며, 등록된 Node는 관리자가 양을 정하기 전까지 아무것도 제공하지 않는다. 셋은 서로 다른 사람이 넣는 입력이고, "권한이 없습니다"로 뭉뚱그리면 아무도 넣지 않은 입력을 권한 문제로 오해한다.
  - `inputs` — 12개 운영 입력의 유무와 **담당자**(operator / project owner / node owner). 없음은 거부가 아니다.
  - `grants` — 5개 계층(project 소속, 역할 역량, 커널 subject 매핑, 커널 연결, operator grant/업무 관리) 중 **어느 것이 거부하는지**.
  - `admission` — kill switch·recovery epoch·살아 있는 Node·커널에 제공된 용량. **권한이 아니다.**
  - 기록된 제공량(`public.resource_offers`) 대 커널이 들고 있는 제공량(`inv.resources.offered`) 대조 — CL-01 F1이 만드는 상태를 운영 점검으로 잡는다.
- 실제 검증 증거(로컬 PostgreSQL 16, head `0031_workspace_input_state`, 각 거부가 발동함을 확인):
  - 전부 준비된 tenant → `absent=[]`, `refusedBy=[]`, `wouldAdmit=True`, exit 0.
  - 빈 tenant → 12개 입력 전부 ABSENT, 각각 담당자 명시. 역할 `viewer` → `role permits requesting work` 거부. project 미연결 / operator grant 비활성 / subject 매핑 비활성 / 폴더 revoked → 각각 단독 지목. 기록 2000 vs 커널 1800 → 불일치 보고.
  - **카드가 요구한 구분의 증거**: 권한 전부 정상 + kill switch ON → `refusedBy=[]`, `mayRequestWork=True`, `wouldAdmit=False`. 권한을 더 줘도 열리지 않는다. Node heartbeat 정지도 같은 형태다.
  - 시험 10개 통과. 역할과 소속을 다시 합치자 해당 시험만 실패(9 passed, 1 failed) → 시험이 실제로 잡는다.
- 이 과정에서 고친 내 결함 2건: (1) 첫 판은 "구성원인가"만 보고 `viewer`를 정상이라 보고했다(exit 0인데 mayRequestWork=False). 소속과 역량은 해결법이 다른 별개 실패다. (2) migration 그래프에 **통과만 가능한 단언**을 넣을 뻔했다 — `downgrade_target` 뒤에 되돌릴 수 없는 revision이 없다는 것은 그 함수의 정의상 항상 참이다. 역방향 독립 스캔 비교로 바꾸고 변조로 실패를 확인했다.
- 부수 수정: `test_integrated_migration_keeps_both_published_histories`가 `dee31e5`에서 이미 깨져 있었다(stash로 확인). 이 저장소의 **여섯·일곱 번째 하드코딩 revision 목록**이다. head를 literal로 박고, 별개 개념인 downgrade target을 head와 같다고 단언하고, unmerged 경우를 revision 이름 나열로 만들고 있었다 — 0028 이후가 생기자 `unknown revision parent`가 나면서 **unmerged 경우가 더 이상 시험되지 않고 있었다.** 셋 다 그래프에서 유도하도록 고쳤다.
- 운영 위험 1건 기록: `inv.operator_grants`는 subject로 keying돼 있어 사람의 OIDC subject를 재발급하면 operator grant가 조용히 고아가 된다. 한쪽만 고치면 계속 거부되므로 도구가 둘 다 보고한다. `inv.business_subjects`·`inv.operator_grants`는 trigger로 불변이며 운영 절차는 비활성화를 써야 한다.
- 남은 문제(실제 운영 입력 대기, 지어내지 않음): 실제 OIDC issuer와 사용자 계정(운영자), 원격 PC(.225) 실행 profile 설치(원격 운영자·Codex), 실제 제공 폴더 경로와 소유자 동의(Node 소유자), object 저장소 endpoint(Codex, S01). 이것들 전에는 "운영 로그인이 동작한다"고 말하지 않는다. 지금 말할 수 있는 것은 입력이 갖춰졌을 때 무엇이 통과하고 무엇이 거부되는지가 재현 가능하게 고정됐다는 것이다.
- 다음 첫 행동: 실제 계정·폴더·원격 profile이 들어오면 같은 도구를 운영 DB에 그대로 돌려 인수 증거로 삼는다. 담당 Claude, 입력은 운영자·Codex. 브라우저 로그인 여정은 Gemini 영역이다.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CL-03 — 복원 도구의 남은 검증 결함 수정

- owner / reviewer: Claude / Codex; status: in-progress(수행 가능한 범위 완료, 남은 2건은 외부 차단); priority: P0.
- 원래 목표/합격 조건: OUT-12 / AC-12.
- 진행 branch/SHA: `review/claude-account-results` c28cdff → 0581964 → dee31e5 (9995122의 후속). push 완료.
- 실제 수행: 지목된 네 결함을 모두 수정하고, 각 검사가 **실패할 수 있음**을 로컬 PostgreSQL 16에서 실증했다. 통과만 가능한 검사는 아무것도 증명하지 않으므로, 수정마다 거짓 통과를 재현한 뒤 차단을 확인했다.
  1. fencing 조회 실패→0: 권한 오류로 양쪽이 0을 읽어 advance가 0이 되고 "fencing safe"가 출력됐다. 복원 수락 여부를 결정하는 유일한 검사에서의 거짓 통과다. `_fencing_state`가 컬럼별 오류 종류와 함께 `None`을 돌려주고, unknown이 합격을 차단한다.
  2. content digest의 public 4개 한정: 실행 기록(`inv.evidence`·`checkpoints`·`node_stop_receipts`·`result_commitments`·`resource_leases`)이 대조 밖이었다. 두 schema를 모두 포함하도록 확장했다.
  3. 누락 대 누락 동일 처리: 양쪽에 없는 테이블이 같은 값이 되어 통과했고, 빈 테이블과 잃은 테이블이 같은 해시였다. `unreadable:<Exception>`으로 구분해 `tablesUnreadable`에 싣고 `integrityVerified`를 차단한다.
  4. mtime RPO: 파일 mtime은 복사로 갱신되므로 복구 지점이 아니라 파일시스템을 잰다. archive 헤더의 생성 시각을 읽되, pg_restore가 붙이는 zone 약어를 UTC로 가정하지 않고 `pg_timezone_abbrevs`로 해석한다. 조용히 틀린 offset은 몇 시간 어긋난 복구 지점이기 때문이다.
  - 추가로, 합격 규칙이 `record()`와 `main()` 두 곳에서 서로 달랐다. 복구 지점을 모르는 시험이 실패로 기록되면서 exit 0이었다. `_passed()` 하나로 합쳤다.
- 실제 검증 증거(로컬 PostgreSQL 16, 컨테이너 saintvision-lan-db-bff1a31d):
  - fencing 조회 불가 → `{'sequenceLastValue': None, 'errors': {...: 'UndefinedTable'}}`. 이전 동작은 0/0 → "safe".
  - `inv.evidence`가 한 필드만 다른 두 DB → row 수는 같고 digest는 `inv.evidence`만 달라짐. (해당 테이블은 `inv.immutable_record()` trigger로 갱신이 막혀 있어, SQL 변조가 아니라 원본·복원본 분기로 재현했다.)
  - 빈 테이블 `e3b0c442…`(빈 입력의 sha256) vs 삭제된 테이블 `unreadable:UndefinedTable` → 서로 다름. 양쪽 삭제 시 값은 같지만 prefix로 걸러 차단.
  - backup mtime을 24시간 과거로 강제 → RPO 222s(archive 헤더 기준). mtime 기준이면 86400s였다.
  - backup 이후 fencing token 7개 발급 → "advance inv.fencing_token_seq by 6", **exit 1**.
  - 정상 시험: RTO 6.1s, RPO 6.2s, table 1314 / column 7652 권한 일치, **exit 0**. ~~AC-12의 RPO≤15분·RTO≤1시간은 이 값으로 충족한다.~~ **정정(CL-07, 2026-09-12)**: 이 문장은 틀렸다. RPO 6.2초는 이 도구가 방금 뜬 백업과의 간격이라 서버 설정과 무관하게 거의 0이 나오며, **실패할 수 없는 숫자를 목표 충족의 증거로 쓴 것**이다. RTO 실측은 유효하다. 실제 운영 RPO는 백업 주기이고 이 배포는 `archive_mode=off`라 시점 복구가 없어 **RPO 목표는 미달성**이다. CL-07과 절차서 8-0 참조.
- 이어서 수행(0581964): 카드가 요구한 역할·RLS·definer 함수·서비스 재개를 복원 시험에 넣었다. 권한 digest만으로는 "누가 무엇을 볼 수 있는가"가 설명되지 않는다 — policy 122개를 모두 되살리고도 격리는 하나도 못 하는 복원본이 기존 검사 전부를 통과한다.
  - 인가 모델: 역할·역할 소속·`relrowsecurity`/`relforcerowsecurity`·`pg_policies`를 부분별 digest로 대조해, 실패 시 어느 부분이 움직였는지 지목한다.
  - definer 함수: `tools/check_definer_functions.py`를 **복원된 DB**에 실행한다. definer 함수는 RLS를 우회하고, 과거 두 번의 교차 tenant 결함 모두 `CREATE OR REPLACE`로 고쳤으므로 "지금 그 DB가 어떤 정의를 들고 있는가"는 복원 시점에만 물을 수 있다.
  - 서비스 재개: 실제 요청이 하는 읽기를 비소유자 역할로 tenant scope 안에서 수행한다. 모델의 두 반쪽을 각각 본다 — `inv_app`은 `public` USAGE로 요청 경로를, `inv`의 실행 기록은 `inv_kernel` 소속으로 접근한다. 한쪽만 보면 접근의 절반을 잃은 DB를 "정상"이라 부른다.
  - RLS 실제 작동: tenant 두 개를 심고 한 scope로 읽어 다른 tenant의 행이 **보이지 않아야** 통과한다. 항상 rollback하므로 `--keep`에서도 행이 남지 않는다.
- 추가 검증 증거(각 검사가 실패할 수 있음을 실증):
  - `public.projects`의 RLS를 끄면 policy 122개가 그대로 나열되고 policy digest도 바이트 동일한데 두 tenant가 모두 보인다 → `rlsScopes` False로 거부. **기존 검사 전부가 "verified"라 부르던 경우다.**
  - `inv_lan_runtime`의 `inv_kernel` 소속 해제 → memberships digest만 이동.
  - tenant 인자를 받고 scope에 묶지 않는 definer 함수 추가 → 7개 검사 중 1개 unsafe, 함수명까지 출력.
  - `inv_kernel`의 `inv` schema USAGE 회수 → `publicRead`는 여전히 True인데 `resumed` False. 요청 경로만 봤다면 "정상"이라 보고했을 것이다.
  - `inv_app`의 `public.projects` SELECT 회수 → `resumed` False.
  - 정상 시험: 역할 4·소속 2·policy 122·RLS flag 129, definer 6개 중 unsafe 0, 서비스 재개, exit 0. 원본에는 시험 행이 0개 남았다.
  - 결함이 아닌 확인: `inv_app`은 `inv.runs`를 읽지 못한다. 복원본과 **원본이 동일하게** 그렇고, 이는 모델이 의도대로 동작하는 것이다(`inv` USAGE는 `inv_kernel` 소유). 이 검사의 첫 판은 역할·테이블 짝을 잘못 잡았고, 원본을 대조해 바로잡았다.
- 정정(dee31e5): 0581964이 definer 판정을 복원 합격의 관문으로 만들었는데, 그 판정은 Codex가 지적한 대로 문자열 대조 휴리스틱이었다. 확인하려고 만든 네 정의가 **전부 누수인데 전부 통과**했다 — 주석 속 binding, 문자열 리터럴 속 binding, tenant 인자를 `org`로 개명, `search_path = pg_temp, inv`. 약한 검사가 합격을 결정하게 두는 것은 이 카드 내내 제거해 온 바로 그 실패 방식이라 먼저 고쳤다. 실측: 조작 누수 4건 전부 차단, head 6개 오탐 0, 0024 실제 누수 재검출 exit 1, 시험 17개 통과. 남은 한계는 정적 판정이라는 점이며 CX-01/CL-01 검토 범위다.
- 남은 문제(합격 미충족, 둘 다 **차단**이며 미수행이 아님):
  - **object 저장소 바이트**: `INV_OBJECT_STORE_ENDPOINT`가 `config.py`의 `S01_PENDING`이다. 확정된 저장소가 없으므로 대조할 대상이 없다. 해소 담당 Codex(S01).
  - **node 설치 journal**: 원격 호스트(.225)에 있고 DB dump에 들어오지 않는다. 원격 설치가 선행이며 해소 담당은 원격 PC 운영자·Codex다.
- 선행/차단과 해소 담당: CX-07 복원 계약·Codex 검토. 기존 권한 대조/public+inv count 보완은 인정하되 전체 복원 합격은 미완료.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.
- CI: 세 Agent 공통으로 계정 결제·한도 문제로 실행 전에 차단된다. 위 증거는 전부 로컬 실측이며 CI 통과와 동등하지 않다.

### CL-04 — Artifact·모델 바이트 정본과 보존 정리

- owner / reviewer: Claude / Codex; status: blocked(조사 완료, seam 계약 대기); priority: P1.
- 원래 목표/합격 조건: OUT-03, OUT-09, OUT-10 / AC-03, AC-09, AC-10.
- 조사 SHA: `review/claude-account-results` 5995b8b, 커널 `agent/codex/workspace-bridge` d14db0a. 전문은 [[Claude_CL-04_Artifact바이트정본_조사]].
- 실제 수행: 카드의 첫 행동인 "소비자·이력·보존 참조 조사"를 마쳤다. 조사 결과가 "연결"과 "전환 migration" 중 어느 쪽도 **내가 단독으로 고를 수 없음**을 보여준다.
- 확인한 사실(인용이 아니라 직접 확인):
  1. `public.artifacts`에 **production writer가 없다.** `Artifact(` 생성은 model 정의뿐이고, 행을 넣는 곳은 시험 fixture 3곳(`tests/test_context_eval.py:412,467`, `tests/test_execution.py:685`)뿐이다. 동반 `public.upload_sessions`도 writer가 없고 `api/v1/`에 upload endpoint가 없다 — 공개 측 바이트 수집 경로 전체가 모델만 있고 구현이 없다.
  2. 그래서 소비자가 운영에서 도달 불가다. `records.py::_pin_artifact`가 `public.artifacts`를 읽어 pin을 만드는데 원본이 없으므로 pin도 없고, `list_pinned_artifacts`는 운영에서 항상 비어 있다. `seal_run_record(artifacts=...)`는 운영에서 만족될 수 없는 인자를 받는다.
  3. **보존은 색인만 있고 수거자가 없다.** `retention_pinned_until`과 색인은 있으나 이를 읽는 GC가 공개 측·커널 측 어디에도 없다.
  4. 실제 바이트·해시는 `inv.result_commitments` + `inv.storage_objects`에 있고, 정본 reader `ResultView`가 이미 `artifacts()`·`download()`를 제공한다.
- **일방 진행이 안 되는 이유**: 가장 그럴듯한 전환(공개 측이 커널 확정 산출물을 SQL로 해석)이 바로 `0029`가 만들고 `0030`이 **의도적으로 철회한 것**이다. head DB `proacl` 실측으로 `run_committed_outputs`가 소유자 전용임을 확인했다(CL-01 F3). 되살리면 `0030` 주석이 말한 "less restrictive alternate resolver"를 복원하는 것이고, 카드가 금지한 "ResultView와 중복 결과 reader 재도입"에도 걸린다. 같은 seam에서 과거 네 번(권한·handoff·binding·결과) 양측이 같은 개념을 만들었고 네 번 모두 실행 기록에 가까운 쪽이 옳았다. 여기서도 그쪽은 커널이다.
- 아무것도 삭제하지 않았다. 카드 요구대로 테이블·이력을 그대로 두었다.
- 남은 문제 / Codex 계약 질문 4개: (1) RunRecord 산출물 pin은 공개 측 유지인가 커널 이관인가. (2) `0030`이 철회한 SQL resolver 대신 봉인 시점에 `content_hash`·크기·`evidence_id`를 얻는 승인된 경로는 무엇인가. (3) `public.artifacts`·`upload_sessions`는 유지/보류/폐기 중 무엇이며 폐기라면 이력 보존과 `run_record_artifacts` FK 완화 migration의 소유자는 누구인가. (4) 보존/GC 소유자는 누구인가.
- 만들 수 없는 합격 증거를 명시한다: "다운로드 actual bytes/hash"는 `ResultView`가 이미 제공하므로 다시 만들지 않는다. "GC/보존"은 수거자가 존재하지 않아 증거 자체를 만들 수 없다.
- 다음 첫 행동: 위 4개 질문을 Codex에 인계한다. 답이 오면 전환 migration 구현은 Claude다.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CL-05 — Context와 실제 Provider/도구 Adapter

- owner / reviewer: Claude / Codex; status: in-progress(redaction 거부 완료, Provider 실행은 CX-02 차단); priority: P1.
- 원래 목표/합격 조건: OUT-09, OUT-10 / AC-09, AC-10.
- 진행 branch/SHA: `review/claude-account-results` **dcad652**.
- 실제 수행 — **redaction을 선언에서 거부로 바꿨다**: `ContextItem.redacted`는 늘 caller의 주장이었고 모듈도 "이 모듈은 redaction이 실행됐는지 알 수 없다"고 정직하게 적으면서 도착한 것을 그대로 저장했다. bearer token을 `redacted=True`로 넘기면 그 token이 hash되고 저장되고 같은 hash를 참조하는 tenant 내 모든 bundle이 공유하며, 설계상 다시 쓰이지 않는 RunRecord에 pin된다. 이제 `build_bundle`이 **쓰기 전에** 플랫폼이 인식하는 비밀을 담은 내용을 거부한다.
  - 재작성이 아니라 거부: 이 함수는 모델에 내용을 넣는 경로가 아니므로 여기서 조용히 고치면 저장된 기록이 모델이 실제로 받은 것과 달라진다. 맞지 않는 context 기록은 기록이 없는 것보다 나쁘다.
  - 재구현이 아니라 재사용: 판정은 `adapters/reference.py`의 기존 ADR-014 패턴 목록에 `recognised_secrets()`를 더해 쓴다. 두 번째 목록은 adapter가 강제하는 것과 어긋나게 된다.
  - 종류만 말하고 일치한 문자열은 절대 말하지 않는다: 조각을 오류 메시지에 넣으면 메시지·로그·감사기록에 비밀을 쓰는 것이고, 그것이 바로 이 거부가 막으려는 누출이다. probe마다 단언한다.
- 실제 검증 증거: 시험 14개. conformance probe 4종(api_key·bearer·presigned·private_key) 전부 거부, 메시지가 비밀을 되풀이하지 않음을 각각 확인, redaction을 거친 내용은 통과, 거부 시 어느 항목·몇 번째인지 지목. **단위 시험만으로는 부족했다** — `build_bundle`에서 호출을 빼도 13개가 전부 통과했다. 그래서 공개 함수와 DB를 거치는 배선 시험을 추가해 "거부된 bundle은 snapshot을 남기지 않는다"를 확인했고, 호출을 빼면 그 시험만 실패한다.
- **한계를 시험으로 고정했다**: 인식은 증명이 아니다. ADR-014 1차 패턴이 담지 않는 형태의 비밀은 그대로 저장되며, 저장된 bundle을 "검증된 깨끗함"으로 읽으면 안 된다는 것을 `test_recognising_is_not_proving`이 기록한다.
- 확인만 하고 다시 만들지 않은 것(이미 있음): desktop/headless 지원 범위는 `agents.py`에 이미 사실대로 있다. 코드에서 뽑은 표 — claude-code/codex-cli/gemini-cli는 headless 가능, **antigravity는 headless 불가**(`prompt_args=None`)이며 `cli.py:398`이 "the platform cannot drive it"으로 **실제로 거부**하고 `test_a_tool_with_no_headless_mode_is_refused_rather_than_guessed`가 이를 시험한다. 카드의 "Antigravity 미지원 headless를 실행 가능으로 표시하지 않음"은 충족돼 있다.
- 남은 문제:
  - **Context에 호출자가 없다.** `build_bundle`/`read_bundle`을 부르는 production 코드가 없고 API도 없다(eval 실행 경로 포함). `public.artifacts`와 같은 모양이다. 따라서 "권한"을 붙일 경계가 아직 없다.
  - **TTL은 수명 결정이 먼저다.** TTL column을 수거자 없이 추가하면 CL-04에서 내가 지적한 실수(색인만 있고 수거자 없음)를 그대로 반복하게 된다. 게다가 `collect_orphan_snapshots`는 있으나 호출자가 없고, orphan은 bundle이 삭제돼야 생기는데 bundle을 삭제하는 것이 없어 구조적으로 할 일이 없다. context bundle의 보존 기간은 제품 결정이므로 내가 지어내지 않는다 — CL-04 질문 4(보존/GC 소유자)와 함께 답이 필요하다.
  - **실제 두 Provider의 실행/취소/collect/attest는 CX-02 credential 경계 대기.**
- 다음 첫 행동: CX-02 credential 계약과 context 수명 결정을 받는다. 그 전까지 Claude는 CL-07 운영 관측·장시간 시험을 진행한다.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CL-06 — 실제 학습·평가·MLflow·승인 배포 서비스

- owner / reviewer: Claude / Codex; status: blocked(CL-04 seam 계약 선행); priority: P1.
- 원래 목표/합격 조건: OUT-10 / AC-10.
- 착수 판단(Claude, 2026-09-12): 카드는 "CPU 경로 구현을 GPU 준비 때문에 멈추지 않음"이라고 하며 그 말은 옳다. 그러나 이 카드의 합격 증거는 **모델 bytes와 배포 digest의 역추적**이고, CL-04 조사에서 확인했듯 공개 측에는 바이트를 가리키는 writer가 없으며 그 연결 방식 자체가 Codex 계약 대기 중이다. 지금 CPU 경로를 구현하면 저장할 곳이 정해지지 않은 바이트를 위한 계보를 만들게 되고, 카드가 금지한 "예시 모델/메타데이터만으로 배포 완료 표시"에 가까워진다. 그래서 GPU가 아니라 **CL-04의 답**을 기다린다.
- 다음 첫 행동: CPU/GPU 학습 결과를 Dataset/commit/image/model bytes·평가·승인·배포 digest로 연결하고 전체 역추적을 구현한다.
- 필요한 합격 증거: 실제 학습→평가→모델 다운로드→승인→배포/rollback 계보와 참조 보존. 예시 모델/메타데이터만으로 배포 완료 표시 금지.
- 선행/차단과 해소 담당: CL-04/05, GPU 경로는 CX-06. CPU 경로 구현을 GPU 준비 때문에 멈추지 않음.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CL-07 — 운영 관측·장시간 시험·복원 절차 인수

- owner / reviewer: Claude / Codex; status: in-progress(WAL·PITR 검증 완료, 운영 결정과 장시간 시험 대기); priority: P1.
- 원래 목표/합격 조건: OUT-12 / AC-12.
- 진행 branch/SHA: `review/claude-account-results` **4b09dfc**(도구), **c632d3f**(절차서 8-0).
- 실제 수행 — 카드가 지목한 **WAL·PITR 절차를 검증했고, 그 과정에서 내 도구의 헤드라인 숫자가 증거가 될 수 없음을 발견해 고쳤다.**
  - 복원 시험은 백업을 방금 뜨고 곧바로 복원하므로 "recovery RPO 6초"가 나온다. 서버 설정과 무관하게 거의 0이 나오는 **실패할 수 없는 숫자**이며, AC-12의 RPO 목표 증거로 쓸 수 없다. 이 도구에서 네 번이나 제거한 결함이 헤드라인에 남아 있었다.
  - 이제 두 가지를 구분해 보고한다: `recovery RPO … for this restore`(이번 복원의 간격)와 `operational RPO bound`(설정이 보장하는 한계).
- **실측한 설정 결함(개발 컨테이너와 `docker-compose.prod.yml` 동일)**: `archive_mode=off`, `archive_command` 미설정, `wal_keep_size=0`, `archive_timeout=0`, `data_checksums=off`.
  - **연속 아카이빙이 꺼져 있어 시점 복구가 불가능하다.** 복구 지점은 마지막 전체 백업뿐이므로 **운영 RPO = 백업 주기**다. 15분 목표를 지금 설정으로 만족하려면 15분마다 전체 덤프를 떠야 하고 절차서는 그런 주기를 규정하지 않았다. → **AC-12의 RPO 목표는 현재 미달성이다.**
  - `data_checksums=off`: 이 시험은 복원본을 **원본과** 대조하므로, 원본에서 이미 손상된 페이지는 양쪽에서 같게 읽혀 모든 대조를 통과한다. 이 도구는 원본이 온전했다고 말해주지 않는다. initdb 시점에만 켤 수 있어 운영 배포 전 결정이 필요하다.
- **인수용 gate를 추가했다**: `--require-operational-rpo SECONDS`. 설정이 그 이하의 한계를 확립하지 못하면 **거부**한다. opt-in이라 일반 기능 시험은 막지 않는다 — 인수 증거를 요구하는 것은 의도적 행위여야 하기 때문이다.
- 실제 검증 증거(로컬 PostgreSQL 16): 기능 시험은 exit 0이되 한계는 NOT ESTABLISHED로 보고. 같은 시험에 `--require-operational-rpo 900`을 주면 **exit 1**. `archive_mode=on`·`archive_command`·`archive_timeout=300`으로 띄운 probe 서버에서는 한계 300s로 읽히고 900s 목표는 만족, 60s 목표는 불만족. 판정을 순수 함수로 분리해 시험 10개 — 가장 필요한 분기(아카이빙은 켰지만 `archive_timeout=0`이라 아무것도 한계 짓지 못한 경우)는 `-c archive_timeout`으로 띄운 서버에서 `ALTER SYSTEM`이 먹지 않아 **실서버로는 도달 불가**였고, 그래서 처음에 시험되지 않았다.
- 이어서 수행(d63717f) — **권한 재검증을 실제 절차로 만들었다**: 카드가 지목한 "권한 재검증"은 오늘의 권한을 마지막으로 승인된 상태와 비교하는 일이다. 기록자 `pilot.take_permission_snapshot`은 S12부터 있었지만 **호출자가 없었다** — 서비스는 기록할 줄 알고 아무도 수집할 줄 몰랐다. 두 번째 기록자를 만들지 않고 **수집자를 붙였다**.
  - 보고서가 출력한 **바로 그 계산**에서 기록한다. 따로 조회해 만들면 옆의 보고서와 어긋나고, 그 사실은 사고 중에 스냅샷 두 개를 비교할 때 처음 알게 된다.
  - 쓰기는 opt-in(`--snapshot`)이다. 기본은 운영에 그대로 겨눌 수 있는 읽기이며, 보고만 하면 아무것도 기록하지 않음을 시험한다.
  - "이전 스냅샷 없음"과 "변경 없음"을 구분한다(`changed=None`). 없음은 같음이 아니다 — 복원 시험에서 누락 대 누락에 필요했던 것과 같은 구분이다.
- **이 과정에서 찾은 내 도구의 결함 2건(고침)**: (1) `mayApprove`가 서로 다른 두 권한을 한 답으로 뭉갰다. 업무 승인은 project 역할에서 오고, 특권 operator 투표는 `inv.operator_grants.can_approve`에서 오며 `workspace_git`의 `_actor`가 투표를 세기 전에 그것을 확인한다. 그래서 `can_approve=false`인 project owner를 "승인 가능"으로 보고해 **실제보다 과장**했다. 이제 `mayApproveInProject`와 `mayApproveAsOperator`로 나눠 보고한다. (2) 도구가 `src`를 `sys.path`에 넣지 않아 첫 `--snapshot` 실행이 `ModuleNotFoundError`로 죽었고, SQLAlchemy에 psycopg 드라이버를 명시해야 했다.
- 추가 검증 증거: 읽기는 기록 0건. 첫 스냅샷은 비교 대상 없음. 변경 없으면 digest 동일. `can_approve` 회수 → digest 이동·CHANGED 보고. 되돌리면 digest가 **이전 값으로 복귀**(권한 상태의 순수 함수라면 그래야 한다). 시험 15개, 변조 2종(operator 승인을 항상 참으로 되돌리기, drift 판정 끄기)에서 각각 2개씩 실패.
- 이어서 수행(8a8f3b4) — **내 복원 도구의 기록 단계가 한 번도 실행된 적이 없었다.** 도구 docstring이 약속하는 세 가지 중 셋째가 "결과 기록"인데, 그 경로는 `--tenant`·`--user`를 함께 줄 때만 돌고 결함이 셋 겹쳐 있었다: (1) SQLAlchemy가 맨 `postgresql://`을 psycopg2로 해석하는데 설치돼 있지 않음, (2) `DrillMeasurement`를 없는 인자 이름으로 호출, (3) 백업을 원장이 허용하지 않는 종류 `database`로 기록(허용값은 `base`·`wal`·`logical`). **플래그 없이 돌린 모든 시험이 exit 0이면서 아무것도 기록하지 않아** 셋 다 드러나지 않았고, 절차서에는 "기록한다"고 적혀 있었다. 절차서 8-0-0으로 정정했다.
  - 같은 수정에서 **백업 원장을 연결했다**: `record_backup`은 S12부터 호출자가 없었고 `verify_backup`은 이미 `verification.py`에서 쓰이고 있었다 — 아무도 만들지 않는 기록을 검증하는 절반짜리 사슬이었다. `--save-backup` 덤프가 이제 원장에 기록되고 드릴 행과 연결된다.
  - 검증은 **디스크의 파일을 다시 읽어** 해시한다. 쓰려던 바이트의 해시를 재사용하지 않는다 — "검증됨"은 그 경로의 파일이 그 백업이라는 뜻이어야 하고 잘린 쓰기는 다른 해시가 나온다. 불일치면 **기록은 남기고 verified=false**로 둔다. 나쁜 백업이 있다는 사실이 복원 전에 봐야 할 증거다.
  - `off_site`는 운영자 주장(`--off-site`)이며 도구가 판단하지 않는다(ADR-018).
  - 실측: `backup ('logical', off_site=False, 590350 bytes, verified=True)`, `drill ('database','passed',rpo=6,rto=6,fencing_verified=True, backup 연결됨)`. 시험 5개, 세 결함을 각각 되돌리면 5/4/3개 실패.
  - 두 발견이 만나는 지점: 원장의 종류는 `base`·`wal`·`logical`을 상정하는데 우리는 **`logical` 하나만** 만든다. 8-0의 "시점 복구 없음"과 같은 사실이다.
- 이어서 수행(ade5bb8) — **AC-12 증거 보고에 호출자를 붙였다**: `pilot_readiness`는 S12부터 AC-12가 요구하는 증거를 모아 왔지만 **아무도 질문하지 않았다**. 이제 `--acceptance-evidence`로 묻는다.
  - `release_id`를 선택값으로 바꿨다. AC-12가 요구하는 것 대부분(통과한 DB 복원 시험, 검증된 백업, 장애 도메인 소실을 견디는 사본, 누군가 실제로 확인한 제공 폴더)은 **어느 release인지가 아니라 배포에 대한 증거**다. manifest가 있어야 gap을 볼 수 있게 두면 release를 자른 뒤에야 gap을 알게 되는데, 준비를 목적으로 하는 것에는 순서가 거꾸로다. release manifest 자체는 S12-BE(Codex) 소관이며 내가 만들 것이 아니다.
  - release 없이 부르면 승인 쪽은 **NOT ASSESSED**로 보고하고 `evidenceComplete`는 false로 둔다. 평가하지 않은 기준이 충족된 기준으로 읽혀서는 안 된다 — 복원 시험의 "누락 대 빈 테이블", 스냅샷의 "이전 없음 대 변경 없음"과 같은 구분이다.
  - 새 배포에서 실제로 지금 비어 있는 세 가지를 지목한다: 통과한 복원 시험 없음, 검증된 백업 없음, **검증된 off-site 백업 없음**(ADR-018).
- **이 기능이 드러낸 결함(고침)**: `--json` 분기와 출력 분기가 **각자의 exit 식**을 들고 있어서, AC-12 blocker를 전부 나열하고도 `--json`에서는 exit 0이었다. 복원 도구의 `_passed`에서 고쳤던 것과 같은 결함이다 — 합격 규칙 사본 두 개는 갈라지고, 각자 자기 자리에서는 맞아 보이기 때문에 갈라진 것이 보이지 않는다. `_exit_code` 하나로 합치고 text/json이 같은 값을 내는지 확인했다.
- 이어서 수행(71cf2c0) — **제공 폴더 건강 점검에 수집자를 붙였다**: `record_storage_check`도 S12부터 호출자가 없었고, 그래서 `contributions_needing_attention`이 모든 활성 폴더를 "한 번도 점검 안 됨"으로 보고했다 — 정확한 보고였다. 실제로 아무도 점검하지 않았기 때문이다. AC-12 증거의 마지막 남은 내 몫이다.
  - **존재는 건강이 아니다.** 파일 수만 세는 점검은 바이트가 썩은 폴더를 통과시킨다. 그래서 카탈로그된 위치를 **다시 해시해** 등록 당시 checksum과 대조한다. 하나라도 어긋나면 나머지가 멀쩡해도 unhealthy다.
  - **이 도구가 둘러싸고 만들어진 안전장치**: 폴더는 경로가 아니라 **node로 식별된다.** 제어 평면의 `D:/inv-share`는 pc-225의 `D:/inv-share`가 아니며, 전자를 점검해 후자의 이름으로 건강 기록을 남기는 것은 기록이 없는 것보다 나쁘다 — 아무도 가보지 않은 폴더에 대해 "누군가 확인했다"는 운영 증거가 되기 때문이다. `--node`를 필수로 두고, 다른 node의 기여는 이유와 함께 **거부**하며, 원격 node의 폴더 점검은 그 기계에서 돌려야 한다.
  - 뭉개지 않고 구분한 세 가지: 카탈로그된 파일의 부재는 **skip이 아니라 mismatch**; checksum이 없는 위치는 **verifiable 아님이며 절대 intact로 세지 않는다**(대조할 것이 없음 ≠ 대조했고 괜찮음); 표본은 폴더가 아니므로 표본 크기를 기록·출력하고 표본 밖 파일은 온전함이 보인 적 없다고 말한다.
  - 카탈로그된 상대 경로가 root를 벗어나면 따라가지 않고 **finding으로 보고**한다. 경로 결합은 `pathsafe.resolve_within`을 재사용한다.
  - 실제 검증 증거: 시험 7개. node 안전장치를 빼면 **7개 전부 실패**, 재해시를 존재 확인으로 바꾸면 해당 1개 실패. 마지막 시험이 요점을 보인다 — 점검 전에는 폴더 2개가 모두 "주의 필요", 점검 후에는 **다른 기계의 폴더 하나만** 남는다(아무도 그 기계에 가지 않았으므로).
- 이어서 수행(00b1159) — **알람 조건 평가에 수집자를 붙였다**: `GOV-ALERT-001`이 알람 17개의 조건·심각도·1차 대응 역할을 확정하고 채널·사람은 `unknown`으로 두었는데, **조건을 평가하는 것이 아무것도 없었다.** 즉 [[보안 평가 운영 가이드]] 사고 대응의 1단계(탐지)가 성립하지 않고 있었다.
  - DB가 답할 수 있는 7개를 평가한다: 세 partition 테이블의 잔여 runway, 체크섬 불일치, 미검증 백업·실패한 복원 시험, heartbeat가 끊긴 online node, 시각 스큐 한도 초과. 이 중 셋은 최근 수집자를 붙인 덕에 비로소 답할 수 있게 된 것이다.
  - **검사만큼 중요한 부분**: 평가할 수 없는 10개를 이유와 함께 출력하고, "아무것도 안 울림 ≠ 건강함"을 말로 적는다. latency·오류율을 조용히 빼고 "알람 없음"을 찍는 도구는 자기가 볼 수 있던 몇 개에 대한 사실을 전체의 건강 진단서처럼 읽히게 만든다.
  - **구현하면서 임계를 정정했다**: `partition_status`는 월 바닥부터 온전한 달 수를 센다. 그대로 쓰면 "잔여 <1개월"은 **이번 달 partition이 없을 때에야** 0이 되는데, 그 시점에는 이미 insert가 실패하고 있어 P1이 경고가 아니라 장애 통보가 된다. 그래서 마지막 partition 상계까지의 **남은 일수(runway)**로 잰다.
  - **실측 발견**: 이 배포의 partition은 **2027-01-01까지**이고 migration 밖에서 partition을 만드는 것이 없다. `ensure_partitions`는 있으나 호출자가 migration뿐이다 — 같은 유형의 네 번째 사례다. 경고가 몇 주 여유를 두고 오게 됐다.
  - 채널은 구현하지 않았다. `GOV-ALERT-001`이 채널·사람을 `unknown`으로 두었고, P1을 추측한 곳으로 보내는 것은 출력만 하는 것보다 나쁘다.
  - 실제 검증 증거: 시험 7개, 각 조건을 실제로 울렸다. partition 알람은 미래 시점 3개로 검증 — runway 45일이면 P2, 10일이면 P1, 상계를 넘기면 "inserts are failing now".
- 이어서 수행(f17ad62) — **알람이 경고하는 문제에 조치 수단을 붙였다**: `ensure_partitions`도 첫 migration부터 있었고 **호출자가 migration뿐**이다. 그래서 배포본은 마지막 migration 날 만들어진 3개월치 partition을 그대로 들고 있고, 이 배포는 **2027-01-01에 Evidence 기록이 멈춘다**(오늘 기준 약 110일).
  - 새 로직이 아니라 **runner**다. `ensure_partitions`가 이미 정하는 것을 다시 정하지 않는다. 아무도 부르지 않는 mechanism은 mechanism이 아니기 때문에 만들었다.
  - 보고가 기본값이다. partition 생성은 운영 DB에 대한 DDL이므로 `--apply`는 명시적이고, `--check`는 여유가 기준 미만이면 **exit 1**이라 무인 guard로 쓸 수 있다. 기본 45일로 알람의 30일보다 **일부러 길게** 뒀다 — 여유 있게 조치할 시간에 실패해야지, 이미 나빠진 상태를 알람과 함께 확인해서는 늦다.
  - **명령은 일정이 아니다.** 운영자가 기억해야 하는 방식이 지금의 공백을 만든 방식이다. 주기 실행은 제어 평면 호스트의 스케줄러 몫이고, 그 전까지 `alarm_check`가 안전망이다. 절차서 7-9에 적었다.
  - 실측: 조치 전 여유 110일 → 12개월 lead로 partition 27개 생성 → 383일. 두 번째 `--apply`는 아무것도 만들지 않는다(멱등). 시험 7개이며 핵심은 **`--check`가 실패할 수 있다는 것**이다. 공유 session DB에 partition을 적용하는 두 시험은 lead를 현재 상태에서 유도하도록 바꾸고 **양쪽 순서로 실행해 확인**했다.
- 부수 발견(보고만, 수정은 운영 행위): `docker-compose.prod.yml`에 `POSTGRES_PASSWORD=postgres`와 `inv_app:apptestonly`가 그대로 있다. prod 이름을 단 파일의 기본 credential이다.
- 남은 문제: 연속 아카이빙·보관 매체·백업 주기는 **운영 결정**이며 CX-09 릴리스 시험과 함께 정해야 한다. 알람/worker 재시작/partition/장시간 표본과 사용자 인수는 미수행이고, CL-02의 실제 운영 입력과 CX-09 공동 시나리오가 선행이다. 작성자(Claude)와 승인자(Codex)는 구분한다.
- 다음 첫 행동: PITR·보관 매체·주기 결정을 CX-09와 함께 받는다. 결정되면 같은 gate로 실측해 인수 증거를 만든다. 담당 Claude, 결정 Codex·운영자.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

## 작업 후 갱신할 최신 기록

아래 항목은 담당자가 매 작업 단위마다 갱신한다. 상세 기록은 History에 새 페이지로 남기며 이전 검증/실패 이력을 덮어쓰지 않는다.

| 항목 | 현재 기록 |
|---|---|
| 마지막 작업 / 착수 카드 | VF-CL-R5 수정(R5-01 cleanup skip 은폐·R5-02 격리 source 누락) + 원격 권한 결속/CAS fixture 독립 검토(8c347b7/e89a415) |
| 실제 owner / 읽은 진행판 버전 / KST | Claude(테스트/운영 문서 owner·독립 검토) / 보강 로드맵 VF-CL / 2026-09-18 22:45 KST |
| branch / base SHA / 구현 SHA | agent/claude/vf-cl-cx01 / b5f770a / 71fc9f5(image-lane 마무리) → R3 커밋(아래) |
| 작업한 것 | R3-01: `is_host_process_init_failure` 플랫폼 게이팅 + loader-stage 전용 allowlist{0xC0000142,0xC0000135}, crash(0xC0000005)·signal(−9) 미재시도(변경명령 중복 방지), describe 5범주. R2-03: `masked_stderr`가 URL·libpq(`password=`)·인용값 3형태 마스킹, 오류 종류 보존. finally: cleanup try/except + JSON write를 finally 마지막 무조건 실행(OSError에도 비밀 없는 evidence 기록). +앞 커밋(71fc9f5): retries 2→1, TimeoutExpired 분류, 선행 host 검사, exit 125 미검증, pytest.skip |
| 확인한 것 / 명령 / exit code / 실제 환경 | `pytest --noconftest tests/test_docker_diag.py tests/test_check_kernel_docker_hygiene.py tests/test_vf_docker.py` → **24 passed**(실 docker; R5-01 cleanup 6종·R5-02 재현성·타입/동시성 포함). R5-02 회귀 non-vacuous 음성 확인. model 검토는 코드 경로·계약·`channel_monotonic` SQL 대조(실 PG 실행은 사용자 75 passed / Codex 79) |
| CI / 독립 reviewer / 운영 인수 | 단위 24 passed 실측. reviewer=Codex 일관 수정본(R2·R3·타입·R5) 재검토 대기. model 검토 sound 인계 |
| 남은 문제 / 차단 이유 / 해소 담당 | 8건 중 6건(business-kernel-role 포함) **미검증** 유지(호스트 압박, 제품 결함 0건). e89a415 CAS는 실 PG로 검증됨; image lane 재판별은 여유 호스트 필요 |
| 다음 카드 / 첫 행동 / 다음 담당 | 착지 완료(11커밋 b378785). e2908a5 registry 권한 결속 독립 검토 완료(sound), docker 부재 3파일 동작 실측(22 passed/2 skipped, 깔끔 skip·가드 불필요). 남은 것: 3파일 배치/CI 경계(Codex), 여유 호스트 image lane 재판별(사용자/CI) |
| History / 오류 / Evidence / PR / sync 결과 | **상태 지도(단일 참조)**: [[2026-09-19_Claude영역_검증상태지도]] — 검증완료/미검증(정확히 기록)/외부대기 구분, image lane 6건 재실행 조건·명령 포함. History: `..._VF-CL-R-001_...근본원인과R2수정.md` v1.5.0; `..._model_remote독립검토.md`; `..._원격권한결속과CAS_fixture독립검토.md`; `..._registry권한결속_독립검토.md`. 착지 merge b378785 |


## Codex 통합 수신 (2026-09-18)

d59b8a6 전체를 b378785로 integration에 반영했다. 사용자독립24passed/0failed(실Docker포함), Codex오프라인22passed/2실Docker제외·격리import통과, 병합후동일22/2. R2~R5 보류해제와 image미검증6건/business-kernel-role미검증 운영인수는 구분한다. 8c347b7/e89a415의 Claude sound 소스검토 수신, 새 e2908a5 registry 실행 연결 독립검토는 다음 Claude(미실시).

동기화 중 외부 공유판 v1.0.10과 Git branch의 과거 v1.0.0 계보 차이를 확인했다. 외부 원문 전체와 hash는 ../Evidence/claude-d59-landing/shared-claude-before.txt 및 shared-proposal.json에 보존했다. 과거 credential/storage/RPO 후속 인계를 삭제하지 않고 제안 원문으로 수신한다. 이 과거 상태를 현재 착지·운영 인수 완료로 자동 적용하지 않는다. 최신 정본은 이 페이지와 [[2026-09-18_Registry_실행권한결속_Codex]]의 고정 SHA 증거다.
