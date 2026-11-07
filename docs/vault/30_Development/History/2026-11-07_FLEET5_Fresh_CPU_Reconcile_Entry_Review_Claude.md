---
doc_id: "HISTORY-FLEET5-20261107-FRESH-CPU-RECONCILE-ENTRY-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 신규 CPU RECONCILE 전용 운영 entry 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T15:20:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1efea494f026e932360c35ae811b6423d874a2e7"
task_ids: ["FLEET5-FRESH-CPU-RECONCILE-ENTRY-INDEPENDENT-REVIEW-20261107"]
tags: ["fleet5", "independent-review", "cpu", "reconcile", "claude"]
---

# 신규 CPU RECONCILE 전용 운영 entry 독립 검토

Orca `task_1d36969e9661` / dispatch `ctx_2a0f382b4d2f`에서 한 실제 독립 검토다. 검토자는 Claude 하나다. helper·subagent·두 번째 검토자는 쓰지 않았다. 대상은 Root가 소유한 RECONCILE 전용 운영 entry와 그 사용 계약이다. 목적은 코드 검토 `6bd81ef0`의 APPLY 전 MEDIUM `FC1E-M2`를 처분하는 것이다. 제품 재설계나 optional LOW 백로그 검토가 아니다. 이 작업은 실제 DB·profile·Node·leaf·APPLY·Run 조작을 승인하지 않는다.

- 첫 KST 기록은 branch 생성 시각 15:05:00이다. 새 branch `agent/claude/fleet5-fresh-cpu-reconcile-entry-review-20261107`을 정확히 `1efea494`에서 만들었다. reset·rebase·amend·force는 쓰지 않았다.
- 선행 검토 `ctx_5edc24050812/task_4b48b22863bb`와 author `ctx_ed23b4a777d0/task_a95ef3d8ccce`가 succeeded/settled/exited/released인 것은 Root `.work` 기록을 DATA로 읽어 확인했다(`489e940d…`, `ced685ef…`, guarded release `e81a5e1b…`). 재사용하지 않았다.
- Root 보드(`fleet-five-orchestration-20261105`, HEAD·원격 `1eb22559`): Index 1.0.507, Codex 1.0.468, Claude 1.2.130, History 1.0.116. Root507 최종 검증(`eec018cf…`, Docs `42344667364`)과 검토 spec(`252ee861…`)을 DATA로 읽었다. 1efea 후보 안의 옛 보드는 이력으로만 봤다.
- Root artifact는 이 검토 tree의 파일이 아니다. 모두 정확한 Root commit에서 `git show 1eb22559:<path>`로 읽었다: [Root Evidence @1eb22559](https://github.com/egparadise/SaintVision-Invion/tree/1eb22559b590b5bab421ca4828e8b5b1a15ef954/docs/vault/30_Development/Evidence/fleet5-20261105-root). entry blob `f0f79d0e`는 2942B, SHA256 `42e89b61…76a3aa`로 지시와 같다. LF·ASCII이며 Root 작업 사본과 바이트가 같다. library `services/control-plane/src/inv/fresh_cpu_admission.py`는 SHA256 `76407ced…bcf90d2c`로 지시와 같다.

## 판정: ACCEPT_RECONCILE_ONLY_ENTRY_AND_M1_PROFILE_CLASS_KEEP_LIVE_HOLD

entry의 필수 결함은 0건이다. HIGH 0, MEDIUM 0, LOW 1(optional), INFO 7. 상세는 [review.json](../Evidence/fleet5-fresh-cpu-reconcile-entry-review-20261107-claude/review.json)에 있다.

- **FC1E-M2:** 검토된 호출 경로가 생겼다. entry `42e89b61…`와 `operational-disposition.txt` 계약으로 Root는 같은 신뢰 연결에서 기존 read-only `reconcile_admission`을 제한된 방식으로 부를 수 있다. 처분은 검토 수준까지만이다. 실제 실행은 NOT_RUN이다. host·profile·request·identity·leaf·Node·image·fence는 아직 결속되지 않았다.
- **FC1E-M1:** 이미 있는 superuser/BYPASSRLS login 역할 등급을 받아들인다. 이 등급은 reconcile의 `_operator` 검사(inv 5개 표 INSERT와 USAGE)를 통과한다. RLS 아래 readback도 행을 본다. tenant 격리는 reconcile 경로의 모든 SELECT에 있는 tenant_id 조건이 지킨다. Root의 14:47:02 KST catalog 관측은 Root 기록 DATA로만 읽었고 재실행하지 않았다. 실제 private target/auth/TLS/환경/file profile은 APPLY 직전에 다시 고정하고 확인해야 한다.
- 원래 SOURCE 코드 수락(6bd)은 좁은 범위 그대로다. 실제 profile·Node·leaf가 미정이라는 이유로 코드를 거부하지 않는다.

### 성립을 확인한 것 (entry와 library를 직접 읽음)

- **import 범위(27-33행).** json·os·re·sys·psycopg, `DomainError`, `MAX_REQUEST_BYTES`·`SAFE_ERRORS`·`prepare_request`·`reconcile_admission`뿐이다. AST로 확인한 결과 apply/plan, subprocess, open, Path, logging, traceback, argparse, execute/cursor/commit이 없다. 제품 import는 try 안에 있어 import 실패도 HOLD가 된다.
- **입력.** argv 길이가 1이 아니면 FRESH-0001이다. argv 값은 읽지도 출력하지도 않는다. stdin은 `MAX_REQUEST_BYTES+1`(128KiB+1)만 읽고 `prepare_request`로 검사한다. 원래 digest는 고정 이름 `SV_FRESH_NODE_EXPECTED_PLAN_SHA256`에서만 온다. str 타입이고 소문자 hex 64자이며 `item.digest()`와 같아야 한다. 아니면 FRESH-0002다. 모두 연결 전에 일어난다.
- **연결.** DSN은 고정 이름 `SV_FRESH_NODE_OPERATOR_DSN`에서만 온다. 비면 FRESH-0012다. CLI의 `--dsn-env` 간접 지정보다 좁다. `psycopg.connect(dsn, autocommit=True)`로 그대로 넘긴다(`tools/fresh_cpu_admission.py:72`와 같다). IDLE 상태에서 `conn.read_only = True`를 둔 뒤 `reconcile_admission`을 정확히 한 번 부른다.
- **library 의미(`services/control-plane/src/inv/fresh_cpu_admission.py:318-344`).** 같은 바이트를 다시 준비하고 IDLE을 요구한다. 자기 transaction을 열고 첫 문장으로 `REPEATABLE READ, READ ONLY`를 건다. 그 뒤로는 SELECT만 한다. reconcile 경로 SQL 12개가 모두 SELECT/SET TRANSACTION임을 AST로 확인했다. readback은 offline·channel v1·provision audit 1개·node_controls `[(0,)]`·tenant_controls 불변을 정확히 비교한다.
- **조합의 시험 귀속.** autocommit=True 연결 + `read_only=True` + reconcile 조합은 CI의 실제 commit·ack 손실 양성 시험과 같다(`tests/core/test_fresh_cpu_admission.py:82`, `tests/core/test_fresh_cpu_admission.py:355-358`). Core `42339495593`, Root 검증. 부정 reconcile 경로는 코드로만 확인했다(FC1E-L4 유지). entry 자체는 어디서도 실행되지 않았고 시험도 없다.
- **출력.** 결과가 dict이고 mode RECONCILE, status MATCHED…, planSha256==expected일 때만 성공한다. 아니면 FRESH-0009다. 성공 출력은 닫힌 JSON이다(readOnly, automaticRetryAllowed=false, runtimeAuthorityGranted=false, operatorDispositionRequired=true). plan 본문·id·DSN·예외는 넣지 않는다.
- **예외.** `except BaseException`이 import·driver·인터럽트·예상 밖 응답을 모두 HOLD exit 2로 바꾼다. code는 `DomainError`이고 `SAFE_ERRORS` 안에 있을 때만 쓰고, 나머지는 FRESH-0011이다. `str`은 `type(...) is str` 비교의 타입 객체로만 나온다. str()/repr()/class 이름/traceback 출력은 없다.
- **하지 않는 것.** APPLY/PLAN, 쓰기·DDL·grant, 파일 탐색, subprocess, Node 효과, 자동 재시도·재개가 없다. 불일치·부재·만료·epoch·control의 정당한 변경·인터럽트는 모두 HOLD다.
- **계약 일관성.** 계약에 이렇게 적혀 있다. 이 entry는 DSN/filesystem sandbox가 아니다(Root msg97ef). 일치는 지금 있는 offline metadata만 증명할 뿐, 어느 시도나 행위자가 commit했는지, 이후 자격이 있는지는 증명하지 않는다. 부재는 재시도 허가가 아니다. PLAN은 reconcile을 대신하지 못한다. Node를 offline으로 되돌려 일치를 만들지 않는다. 이 내용은 library docstring·readback과 일치한다.
- **호출 방식.** `python -I -B`는 -E/-s/-P를 뜻한다(3.11+). 따라서 script 디렉터리와 PYTHON* 변수가 import를 바꾸지 못한다. entry는 sys.path를 추가하지 않는다.

### 발견

- **FRE-L1 (LOW, optional, 필수 아님).** handler가 받은 예외 문구는 출력하지 않는다. 그래도 좁은 잔여 경로가 둘 있다.
  - (a) except 블록 안에서 두 번째 예외가 나면 Python이 연쇄 traceback을 출력한다. 예: 두 번째 Ctrl-C, stderr 쓰기 오류. 이 traceback에는 원래 예외의 str()이 들어 있다. 예: host·port·user가 나오는 libpq 연결 오류.
  - (b) psycopg 자체 logger에는 warning 경로가 있다. 예: 인터럽트 뒤 cancel 실패, 종료 시 rollback 실패. logging을 설정하지 않으면 이 경고는 lastResort로 stderr에 나간다. (b)는 검토자의 psycopg 3.x 지식에서 나온 것이다. pinned 3.3.5 소스로 확인하지 않았다.
  - 두 경로 모두 비밀번호를 담지 않고, 쓰기를 하지 않으며, 결과는 HOLD로 남는다. 수락된 CLI도 같은 성질이다.
  - 처분(선택): stderr는 private host 세션에서만 받는다. 닫힌 HOLD JSON이 아닌 stderr 내용은 HOLD 자료로 다루고 공개하지 않는다. 이후 개정에서 psycopg logger 비활성화와 fail() 보호를 넣을 수 있다. 이것 때문에 새 LOW cycle을 열지 않는다.
- **INFO.**
  - I1: argv 검사가 import 뒤에 있다. 안전에는 영향이 없다.
  - I2: 판단 기준은 exit code다. 출력 직후 인터럽트가 오면 stdout에는 일치 JSON이, stderr에는 HOLD가 남고 exit는 2가 된다. exit 0이고 stdout JSON이 하나일 때만 일치로 본다.
  - I3: PG* 환경변수와 libpq 기본 파일은 지우지 않는다. 따라서 private profile DSN에 다음을 명시해야 한다: connect_timeout=5, options(statement 15000 / lock 2000 / idle_in_transaction 15000), TLS 기대값, 승인된 파일 참조. 실행 전 확인에서 프로세스 환경에 승인된 값만 있는지도 봐야 한다. entry는 이것들을 검증하지 않고 그대로 넘긴다.
  - I4: entry 자신의 결과 형태 guard도 FRESH-0009를 쓴다. pinned library에서는 도달하지 않는 방어층이다.
  - I5: read_only와 READ ONLY transaction은 방어층일 뿐이다. superuser에게는 권한 경계가 아니다.
  - I6: reconcile은 읽기만 하는데도 INSERT 권한 검사를 요구한다. M1 역할은 이를 만족한다. 최소 권한은 이 범위가 아니다.
  - I7: 실행 host에서는 복사한 .py 바이트의 SHA를 확인해야 한다. CRLF로 바뀌어 SHA가 다르면 정규화하지 말고 거부한다.

## 증거 귀속

- **검토자 DATA 검사.** [entry_ast_probe.py.txt](../Evidence/fleet5-fresh-cpu-reconcile-entry-review-20261107-claude/entry_ast_probe.py.txt)(`b270f1ad…`)를 `.venv` Python `-I -B`로 scratch에서 실행했고 exit 0이었다. 입력은 entry `42e89b61…`와 library `76407ced…` blob이다. 출력은 [entry-ast-probe.json](../Evidence/fleet5-fresh-cpu-reconcile-entry-review-20261107-claude/entry-ast-probe.json)(`8f4faece…`)이다. probe는 `ast.parse`만 하고 입력을 import하거나 실행하지 않는다.
- **CI.** 1efea Docs `42339493314`, Core `42339495593`, Backend `42339497490`, 검토 6bd Docs `42343810509`는 Root 검증 기록을 DATA로 인용한다. 새 CI·artifact 다운로드는 하지 않았다.
- **실행하지 않은 것.** entry 실행(fake import 포함), 제품 import/CLI/app, crypto, pytest, Go, Node/browser/runtime, SSH/Docker/PG, install/PKI/OS/process/credential, DB 관측 재실행, 옛 proof/corpus/author helper. 실제 설정·env·계정·manifest·key·cert·연결·profile·transcript는 읽지 않았다.

## 남은 것과 다음 담당

이 수락은 실행·설치·DB 쓰기·grant·등록·PKI·lease·Run 권한이 아니다. 다음은 여전히 열려 있다: Original19 HOLD, acceptedBaselineDischarges 0, runtime B0, A1–A16 PENDING, H1–H7/H3EA/RD NULL_HOLD, raw7 UNREGISTERED, A01–A40 NOT_RUN, 5대 전체·프로그램 미완료.

다음 첫 행동은 Root/Codex 집계자가 맡는다. 이 판정을 받은 뒤 다음을 고정한다: 격리 실행 host, private profile(I3), request·identity·leaf·Node·image·fence. 실행 전에는 entry·wheel·library·interpreter 출처를 확인한다. 실제 운영 요청 범위도 Root가 정한다. 나중에 기존 승인자 identity가 하나 더 필요하고, 요청자가 아닌 서로 다른 두 사람의 실제 Run 표도 필요하다. 이 문서는 그것을 만들지 않는다. 로컬 문서 gate와 sync CHECK는 [local-doc-gates.txt](../Evidence/fleet5-fresh-cpu-reconcile-entry-review-20261107-claude/local-doc-gates.txt)에 있다. 검토 SHA와 Docs run은 push 뒤 Orca worker_done으로 Root에 보고한다.
