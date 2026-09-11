---
doc_id: "WORKBOARD-CLAUDE-001"
title: "Claude 작업 현황"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T18:40:00+09:00"
source_of_truth: "Git"
---

# Claude 작업 현황

[[전체 개발 진행 현황]] → 이 페이지 → [[Agent 지속 개발 운영 규칙]] 순서로 확인한다. 이 페이지는 현재 후속 카드 목록이며 이전 장문 보고서는 SHA별 근거다.

- 배정 owner: Claude. 독립 reviewer: Codex. 현재 카드 수신/착수 여부: **Codex의 초기 정의이며 각 담당 Agent의 수신 확인은 아직 없다**. Codex는 이 문서 작업만 실제 수행 중이다.
- 공통 Skill: agent-delivery v1.1.0, 역할 Skill service-integration v1.0.0. 계획: [[Backend 최종 개발 계획]], [[DB 최종 개발 계획]], [[Storage 최종 개발 계획]].
- 계약: GUIDE-001, GOV-AGENT-001, GOV-GIT-001, ADR-INDEX-001 v1.27.0, [[Codex Workspace 편집과 PTY 및 원격 Git 계약]] v1.1.0, [[Codex 실제 실행 결과 조회 계약]]. 계약 변경 시 버전 갱신.
- 확인 기준: 2026-09-11T17:07:33+09:00. 준비됨(ready)은 아직 착수했다는 뜻이 아니다. 차단 카드 대신 선행 없이 가능한 ready 카드를 진행한다.

## 최근 확인한 진척

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
| CL-04 | P1 | ready | S03-DB S03-ST S09-ST S10-ST | Artifact·모델 바이트 정본과 보존 정리 |
| CL-05 | P1 | planned | S09-DB S09-ST S10-BE | Context와 실제 Provider/도구 Adapter |
| CL-06 | P1 | planned | S10-BE S10-DB S10-ST | 실제 학습·평가·MLflow·승인 배포 서비스 |
| CL-07 | P1 | planned | S12-DB S12-ST | 운영 관측·장시간 시험·복원 절차 인수 |

### CL-01 — Codex 최신 커널 독립 검토

- owner / reviewer: Claude / Codex; status: in-progress(검토 완료, finding 2건 인계 대기); priority: P0.
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
  - 정상 시험: RTO 6.1s, RPO 6.2s, table 1314 / column 7652 권한 일치, **exit 0**. AC-12의 RPO≤15분·RTO≤1시간은 이 값으로 충족한다.
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

- owner / reviewer: Claude / Codex; status: ready; priority: P1.
- 원래 목표/합격 조건: OUT-03, OUT-09, OUT-10 / AC-03, AC-09, AC-10.
- 다음 첫 행동: public.artifacts 소비자/이력/보존 참조를 조사해 kernel 실제 object bytes로 연결하거나 보존 가능한 전환 migration을 만든다.
- 필요한 합격 증거: 다운로드 actual bytes/hash·Evidence/model pin·GC/보존·기존 참조 이관 증거. ResultView와 중복 결과 reader 재도입 금지.
- 선행/차단과 해소 담당: 현재 코드 조사 가능. 테이블/이력을 먼저 삭제하지 않음.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CL-05 — Context와 실제 Provider/도구 Adapter

- owner / reviewer: Claude / Codex; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-09, OUT-10 / AC-09, AC-10.
- 다음 첫 행동: credential 계약 아래 Context 권한·TTL·redaction과 실제 두 Provider의 실행/취소/collect/attest를 연결한다. Orca/Codex/Claude/Antigravity의 desktop와 headless 지원 범위를 분명히 한다.
- 필요한 합격 증거: 실제 Provider별 정상·실패·취소·누출 거부·trace/산출물 bytes. 모델 확정 전 vector 차원 고정 금지.
- 선행/차단과 해소 담당: CX-02 credential 경계. Antigravity 미지원 headless를 실행 가능으로 표시하지 않음.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CL-06 — 실제 학습·평가·MLflow·승인 배포 서비스

- owner / reviewer: Claude / Codex; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-10 / AC-10.
- 다음 첫 행동: CPU/GPU 학습 결과를 Dataset/commit/image/model bytes·평가·승인·배포 digest로 연결하고 전체 역추적을 구현한다.
- 필요한 합격 증거: 실제 학습→평가→모델 다운로드→승인→배포/rollback 계보와 참조 보존. 예시 모델/메타데이터만으로 배포 완료 표시 금지.
- 선행/차단과 해소 담당: CL-04/05, GPU 경로는 CX-06. CPU 경로 구현을 GPU 준비 때문에 멈추지 않음.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CL-07 — 운영 관측·장시간 시험·복원 절차 인수

- owner / reviewer: Claude / Codex; status: planned; priority: P1.
- 원래 목표/합격 조건: OUT-12 / AC-12.
- 다음 첫 행동: 알람/worker 재시작/partition/보존/백업 매체/WAL·PITR·권한 재검증 절차를 검증하고 Codex·Gemini 릴리스 시험을 지원한다.
- 필요한 합격 증거: 실제 운영 로그/알람·장시간 표본·전체 복구/사용자 인수와 실패 처리 절차. 작성자와 승인자 구분.
- 선행/차단과 해소 담당: CL-02/03/06, CX-09와 공동 시나리오. 각각 owner는 유지.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

## 작업 후 갱신할 최신 기록

아래 항목은 담당자가 매 작업 단위마다 갱신한다. 상세 기록은 History에 새 페이지로 남기며 이전 검증/실패 이력을 덮어쓰지 않는다.

| 항목 | 현재 기록 |
|---|---|
| 마지막 작업 / 착수 카드 | 초기 배정표 작성. 제품 작업 착수는 담당 확인 대기 |
| 실제 owner / 읽은 진행판 버전 / KST | 담당자 입력 대기 |
| branch / base SHA / 구현 SHA | 담당자 입력 대기 |
| 작업한 것 | 담당자 입력 대기 |
| 확인한 것 / 명령 / exit code / 실제 환경 | 담당자 입력 대기 |
| CI / 독립 reviewer / 운영 인수 | 각 상태를 따로 기록. 현재 전체 인수 완료 아님 |
| 남은 문제 / 차단 이유 / 해소 담당 | 해당 카드의 선행 조건 참조 |
| 다음 카드 / 첫 행동 / 다음 담당 | 위 ready 카드부터 하나 선택 후 담당자가 명시 |
| History / 오류 / Evidence / PR / sync 결과 | 실제 링크와 SHA를 담당자가 기록 |
