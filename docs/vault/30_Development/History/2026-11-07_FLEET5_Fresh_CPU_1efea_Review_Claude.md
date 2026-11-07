---
doc_id: "HISTORY-FLEET5-20261107-FRESH-CPU-1EFEA-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 신규 CPU 메타데이터 등록 1efea 독립 코드 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T14:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1efea494f026e932360c35ae811b6423d874a2e7"
task_ids: ["FLEET5-FRESH-CPU-ADMISSION-1EFEA-INDEPENDENT-CODE-REVIEW-20261107"]
tags: ["fleet5", "independent-review", "cpu", "metadata", "claude"]
---

# 신규 CPU 메타데이터 등록 1efea 독립 코드 검토

Orca `task_4b48b22863bb` / dispatch `ctx_5edc24050812`에서 한 실제 독립 CODE 검토다. 검토자는 Claude 하나다. helper·subagent·두 번째 검토자는 쓰지 않았다. 대상은 Codex의 `1efea494`(직계 부모 `7033778a`, branch `agent/codex/fleet5-fresh-cpu-admission-r1-20261107`)다. 이 후보가 추가한 신규 파일 넷만 판정한다. base703의 수락(`7023992f`, Docs `42340533148`)을 이 판정 대신 쓰지 않는다.

- 시작 14:34:44 KST. 선행 통합 검토 `ctx_1ba53b566ab1/task_65b33b98a1b9`가 succeeded/settled/exited/released인 것은 Root 기록(`.work/fresh-cpu-1efea-review-predecessor-final-show.json`, `cab184f0…`)을 DATA로 읽어 확인했다.
- 새 branch `agent/claude/fleet5-fresh-cpu-1efea-review-20261107`을 정확히 `1efea494`에서 만들었다. reset·rebase·amend·force는 쓰지 않았다. author 원격 ref도 정확히 `1efea494`다.
- Root 보드(`fleet-five-orchestration-20261105`, HEAD `9149c6e7`): Index 1.0.506, Codex 1.0.467, Claude 1.2.130, History 1.0.115. Root 검증 `.work/fresh-admission-1efea-source-ci-root-verified.json`(`a34b777d…`)은 정본 RootEvidence `cpu-fresh-admission-1efea-source-ci-root-verification.json`과 바이트가 같다. step 확인은 `9d95ca6b…`, scope는 `7da516ba…`다. 후보 안에 있는 옛 보드는 이력으로만 봤다.

## 판정: ACCEPT_FRESH_CPU_ADMISSION_OPERATOR_CODE_KEEP_ACTUAL_HOLD

현재 범위의 필수 코드 수정은 0건이다. HIGH 0, MEDIUM 2, LOW 4, INFO 6. MEDIUM 둘은 코드 결함이 아니다. 실제 APPLY 전에 Root가 처분해야 하는 전제다. 상세는 [review.json](../Evidence/fleet5-fresh-cpu-1efea-review-20261107-claude/review.json)에 있다.

### 성립을 확인한 것 (소스를 직접 읽음)

- **범위.** 변경 경로는 56개이고 모두 추가다. 신규 source/test 4개와 author 자체 문서 52개뿐이다. 기존 제품·시험·schema·contract·migration·의존성·workflow·Go·node-agent 변경은 없다. 4개 blob의 SHA256은 지시와 같다.
- **입력 계약.** 다음은 모두 DB 작업 전에 거부한다.
  - 정확히 12개 key만 받는다. `type is int`로 bool을 제외하고, 중복 key와 NaN/Infinity를 거부한다. `1e400`은 float이 되어 타입 검사에서 거부된다.
  - 잘못된 UTF-8, 깊은 중첩(RecursionError), 128KiB 초과를 거부한다.
  - UUID는 정규형으로 왕복해야 한다. prj/nod/res ULID 정규식은 schema CHECK·`NodeId` 계약과 같다. 두 자원 id는 서로 달라야 한다.
  - base64는 정규형으로 왕복해야 하고, 해독 크기는 65536 이하다.
  - endpoint와 leaf 식별(URI/EKU/nonCA/유효기간)은 바뀌지 않은 helper로 검사한다.
- **APPLY 결속.** plan digest는 DB 작업 전에 비교한다. digest는 검증된 요청과 고정 profile에서만 나오는 의도 결속이다. DB 예약이 아니다.
- **소유 transaction.** `_idle`은 IDLE이 아닌 연결(INTRANS/INERROR 포함)을 FRESH-0003으로 거부한다. 그래서 caller의 savepoint 안에서 COMMITTED가 나올 수 없다.
- **한 transaction 안의 쓰기 순서.** 모든 insert는 바깥 transaction 하나 안에서 일어난다. `provision_channel`은 바뀌지 않았고 중첩 savepoint를 쓴다. `expected_version=0`이므로 channel v1과 audit을 함께 만든다.
- **잠금 순서.** control_epoch → tenants → projects → tenant_controls → business_projects → public.projects에 FOR SHARE를 건다.
  - READ COMMITTED에서 동시 kill switch나 version 변경이 먼저 commit되면 다시 읽어 FRESH-0007이 된다.
  - epoch 회전은 transaction 동안 막힌다.
  - 경합하는 행의 잠금을 올리지 않으므로, 이 코드끼리 deadlock을 새로 만들지 않는다.
- **중복과 원자성.** 동시 중복 요청은 PK 덕분에 하나만 이긴다. 진 쪽은 FRESH-0008이고 전부 rollback된다.
- **commit 전 readback.** 다음을 정확히 비교하고, 하나라도 다르면 FRESH-0009로 rollback한다.
  - node가 offline이고 epoch가 맞다.
  - 자원은 둘이고 capacity=offered다.
  - 활성 membership이 하나다.
  - channel v1의 필드가 맞고, provision audit이 하나다.
  - tenant_controls는 version·kill_switch·updated_at이 그대로다.
  - node_controls는 `[(0,)]`이다.
- **commit 확인.** COMMITTED는 context가 정상 종료한 뒤(commit 확인 뒤)에만 반환한다. commit 단계 오류는 FRESH-0010이 되며 exit 3, 자동 재시도는 없다. 이 경로는 실제 PG commit 뒤 fault injection으로 시험했다.
- **reconcile.** 첫 문장이 `REPEATABLE READ, READ ONLY`이고, 쓰기·재시도가 없다.
- **권한.** catalog의 실제 권한으로 검사한다. inv_kernel은 project_nodes·channel·audit INSERT가 없다(`0019_runtime_role.sql:20,24`). inv_app은 inv INSERT가 없다. 둘 다 FRESH-0004로 거부되고 모든 행이 보존된다(시험).
- **건드리지 않는 것.**
  - kill switch는 켜진 채로 둘 수 있고 쓰지 않는다.
  - 모듈에 UPDATE/DELETE 문이 없다.
  - lan_pilot·remote_workspace_entry·grant 모듈을 import하지 않는다.
  - tenant/project/user/grant/control 행을 만들지 않는다.
- **CLI.** DSN은 이름이 지정된 환경변수 하나에서만 오며, 값이 비면 FRESH-0012다. autocommit으로 바꾸지 않고 그대로 넘긴다. AST상 open·subprocess·socket이 없다. argparse 오류 문구, 예외 문자열, 닫힌 집합 밖의 code는 출력하지 않는다. 신뢰 전제 `msg_97efddc65fbd`를 사실대로 지킨다: libpq sandbox도, issuer chain 검증도 주장하지 않는다. plan에는 `certificateIssuerChainVerified=false`, `executionAuthorized=false`가 들어 있다.

### 발견 (자세한 내용은 review.json)

- **FC1E-M1 (MEDIUM, Root가 APPLY 전에 처분).**
  - 사실: `public.projects`는 FORCE RLS다. 정책은 inv_app(FOR ALL)과 inv_cancel_bridge_owner(SELECT만) 둘뿐이다(`migrations/versions/0001_s02_baseline.py:470-476`, `0056_kernel_cancel_audit_bridge.py:99-102`). PostgreSQL 정책표에서 FOR SHARE에는 UPDATE 정책 가시성도 필요하다.
  - 결과: superuser도 BYPASSRLS도 아닌 operator는 business link가 있는 project에서 항상 FRESH-0005로 거부된다(`fresh_cpu_admission.py:199-209`).
  - 시험의 한계: CI는 superuser `postgres`로만 돌므로(`core.yml:64`) 이 경로를 증명하지 않는다.
  - 영향: fail-closed라서 쓰기와 누출은 없다. 그러나 Root가 계획한 실제 target에는 business link가 있다.
  - 확인한 것: 모든 tenant 표 SQL에 tenant_id 조건이 명시돼 있다. 따라서 RLS를 우회하는 operator로도 tenant 격리는 유지된다.
  - 처분: Root가 private profile에 operator 역할 등급을 정한다. non-bypass operator로 하려면 이후 따로 검토된 변경(정책 작업)이 필요하다.
- **FC1E-M2 (MEDIUM, 운영 공백).**
  - 사실: CLI는 UNKNOWN_RECONCILE_REQUIRED(exit 3)를 알리지만 PLAN/APPLY만 제공한다. `reconcile_admission`은 library에만 있으며, 시험돼 있다. author History가 이 제외를 명시한다.
  - 영향: PLAN은 reconcile을 대신하지 못한다. commit 뒤에는 FRESH-0008, commit 전에는 READY가 나올 뿐 정확한 행을 증명하지 않는다.
  - 처분: Root가 실제 APPLY 전에, 같은 신뢰 연결로 reconcile을 부르는 검토된 방법을 고정한다.
- **FC1E-L1.** `_operator`는 INSERT 5개와 USAGE만 본다. APPLY에는 추가로 FOR SHARE용 UPDATE 권한, trigger가 쓰는 node_controls INSERT, RLS 가시성이 필요하다. 따라서 READY가 APPLY 성공을 보장하지 않는다. 실패하면 FRESH-0011로 rollback된다.
- **FC1E-L2.** cryptography `DuplicateExtension`(Exception 하위)은 helper가 잡지 않는다. 그래서 FRESH-0011(503)로 잘못 분류된다. 쓰기와 누출은 없다.
- **FC1E-L3.** lock_timeout이 없다. 중단(BaseException)은 닫힌 JSON으로 바뀌지 않는다.
- **FC1E-L4.** reconcile의 부정 경로는 시험이 없다. 코드로는 fail-closed임을 확인했다.
- **INFO.**
  - I1: 양성 경로는 모두 superuser로 돈다.
  - I2: scope 시험의 'wrong-epoch' case는 DB 이전에 일어나는 인증서 거부다. 실제 DB epoch 거부는 197행 시험이 맡는다.
  - I3: 'association'과 'channel' 충돌 case는 nodes 충돌이 먼저 걸린다. 나머지 EXISTS 조건은 FK 때문에 따로는 닿지 않는 방어층이다.
  - I4: 기본값 `heartbeat_at`은 어떤 소비자에게서도 자격을 주지 않는다. 모든 소비자가 online이나 snapshot·skew를 함께 요구한다.
  - I5: business link가 없으면 잠글 것이 없다. 조정되지 않은 외부 mutator는 author가 범위 밖으로 둔다.
  - I6: 나중에 kill switch version이 바뀌면 reconcile은 FRESH-0007 HOLD가 된다. 안전한 거짓 음성이다.

## 증거 귀속

- **CI (검토자의 읽기 전용 `gh api`).** Docs `42339493314`, Core `42339495593`, Backend `42339497490` 셋 모두 head `1efea494`, author branch, `workflow_dispatch`, attempt 1, completed/success다. display title은 correlation `freshcpu-1efea494-{docs,core,backend}-37e26ae0fb9f`와 같다.
- **Root receipt를 DATA로만 읽은 수치.** job·step counter, Core XML 13개(별도, 합산하지 않음; core-tests 9452 = 9406 pass + 46 skip), 신규 70 case PASS, Go 146/550, Docker 1/4(hosted CI이며 5대 실장비가 아니다), Backend 각 9047/75/2, MLflow 3, wheel·binary static. 검토자는 artifact·log·XML·ZIP을 내려받거나 파싱하지 않았다.
- **검토자 DATA 검사.** [review_data_probe.py.txt](../Evidence/fleet5-fresh-cpu-1efea-review-20261107-claude/review_data_probe.py.txt)(`210b064c…`)를 `.venv` Python 3.14.7 `-I -B -X utf8`로 두 번 돌렸다. 둘 다 exit 0이고 출력이 같다: [review-data-probe.json](../Evidence/fleet5-fresh-cpu-1efea-review-20261107-claude/review-data-probe.json)(`c74b6017…`). 내용은 git argv와 blob `ast.parse`뿐이다. AST로 센 결과는 함수 24, case 70, fixture 기반 PG case 25로 Root 수치와 같다. 다만 그중 한 case는 DB 이전 거부다(I2).
- **실행하지 않은 것.** 제품 import/app, CLI, crypto, pytest, Go/compiler, Node/browser/runtime, SSH/Docker/PG, install/PKI/trust/OS/process/credential, 새 Core/Backend/Frontend CI, author script·collector·다운로드 binary, 옛 finite corpus/main. 실제 profile·DSN·secret·config·manifest·transcript는 읽지 않았다.

## 남은 것과 다음 담당

이 수락은 install·deploy·merge·실제 DB 쓰기·CA 신뢰·실제 등록·권한 승인이 아니다. 다음은 여전히 열려 있다: Original19 HOLD, acceptedBaselineDischarges 0, runtime B0, A1–A16 PENDING, H1–H7/H3EA/RD NULL_HOLD, raw7 UNREGISTERED, A01–A40 NOT_RUN, 5대 전체·프로그램 미완료.

Root에게 아직 필요한 것은 다음과 같다. 실제 self-contained profile, 선택된 현재 tenant+project+epoch, 새 Node+image+leaf+fence/관측, M1·M2 처분, 그리고 이후 요청자가 아닌 서로 다른 두 사람의 실제 Run 승인. 다음 첫 행동은 Root/Codex 집계자가 이 판정을 받고 M1·M2를 처분한 뒤 다음 범위를 정하는 것이다. 로컬 문서 gate와 sync CHECK는 [local-doc-gates.txt](../Evidence/fleet5-fresh-cpu-1efea-review-20261107-claude/local-doc-gates.txt)에 있다. 검토 SHA와 Docs run은 push 뒤 Orca worker_done으로 Root에 보고한다.
