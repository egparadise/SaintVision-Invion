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

9995122: 복원에 public+inv 테이블 수·권한 digest 대조를 추가하고 live pg_proc definer 점검 도구를 작성했다. 코드 변경 확인이며 이 문서 작성자가 새 도구를 실운영 검증하거나 독립 승인한 것은 아니다.

c28cdff (Claude, 2026-09-11): CL-03이 지목한 네 결함을 수정하고 각 검사가 실패할 수 있음을 로컬에서 실증했다. 네 결함 모두 "증거 없는 통과"를 만들고 있었다 — 특히 fencing 조회 실패가 0으로 읽혀 "safe"가 출력되던 건은 복원 수락 여부를 결정하는 검사에서의 거짓 통과였다. 정상 시험 RTO 6.1s·RPO 6.2s, old epoch 시험 exit 1. 역할·RLS·object 저장소·서비스 재개는 아직 검사 밖이므로 전체 복원 합격은 미완료다. reviewer Codex의 독립 확인은 아직 없다.

## 작업 카드

각 카드의 sprint/area/outcome/acceptance는 부모 task에서 상속한다. 원래 task owner를 바꾸지 않는다. CL-01은 독립 검토 업무다. 카드 상태와 원래 48개 task의 최종 done은 별개다. 각 카드의 base/branch와 실제 검증값은 착수 시 담당자가 고정한다.

| 카드 | 우선순위 | 상태 | 부모 task | 범위 |
|---|---|---|---|---|
| CL-01 | P0 | ready | S01-DB S04-DB S06-BE S06-DB S08-DB | Codex 최신 커널 독립 검토 |
| CL-02 | P0 | ready | S02-BE S02-DB S02-ST S03-DB | 운영 로그인·권한·Workspace·폴더 적용 |
| CL-03 | P0 | in-progress | S12-DB S12-ST | 복원 도구의 남은 검증 결함 수정 |
| CL-04 | P1 | ready | S03-DB S03-ST S09-ST S10-ST | Artifact·모델 바이트 정본과 보존 정리 |
| CL-05 | P1 | planned | S09-DB S09-ST S10-BE | Context와 실제 Provider/도구 Adapter |
| CL-06 | P1 | planned | S10-BE S10-DB S10-ST | 실제 학습·평가·MLflow·승인 배포 서비스 |
| CL-07 | P1 | planned | S12-DB S12-ST | 운영 관측·장시간 시험·복원 절차 인수 |

### CL-01 — Codex 최신 커널 독립 검토

- owner / reviewer: Claude / Codex; status: ready; priority: P0.
- 원래 목표/합격 조건: OUT-01, OUT-04, OUT-06, OUT-08 / AC-01, AC-04, AC-06, AC-08.
- 다음 첫 행동: 제품 c5f2154와 #21→#22→#19를 대상으로 0028~0033 적용 함수·grant·reservation/출력·PTY ticket/frame·Git dispatch/current scope를 독립 검토한다.
- 필요한 합격 증거: 구체 finding/코드 위치/재현/해결 SHA·review 결론. 작성자 시험 기록을 그대로 승인이라 하지 않음.
- 선행/차단과 해소 담당: 코드/로컬 402개/20개 upgrade 증거 확보됨. Codex 구현의 reviewer 역할이며 원래 task owner 변경 아님.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CL-02 — 운영 로그인·권한·Workspace·폴더 적용

- owner / reviewer: Claude / Codex; status: ready; priority: P0.
- 원래 목표/합격 조건: OUT-02, OUT-03 / AC-02, AC-03.
- 다음 첫 행동: 현재 CRUD/OIDC/provisioning을 실제 허용 계정·project·Workspace·Node·제공 폴더에 연결한다. 없는 운영 입력은 명시하고 현재 grant 교집합을 시험한다.
- 필요한 합격 증거: 실제 로그인/권한 거부·public/kernel 매핑·ready Workspace·허용 폴더·Node 제공량 일치. 권한 부여와 실행 admission 구분.
- 선행/차단과 해소 담당: CX-02 계약 및 운영자 계정/폴더 입력. 로컬 준비/설정 점검은 즉시 가능.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CL-03 — 복원 도구의 남은 검증 결함 수정

- owner / reviewer: Claude / Codex; status: in-progress(네 결함 수정 완료, 합격 조건 일부 미충족); priority: P0.
- 원래 목표/합격 조건: OUT-12 / AC-12.
- 진행 branch/SHA: `review/claude-account-results` c28cdff (9995122의 후속). push 완료.
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
- 남은 문제(합격 미충족): 카드가 요구한 범위 중 **역할·definer 함수·RLS policy·object 저장소·journal·서비스 재개는 복원 시험이 아직 검사하지 않는다**. 현재 도구가 대조하는 것은 테이블/컬럼 권한, 두 schema의 row 수와 내용 digest, fencing 상태뿐이다. definer 함수는 별도 도구 `tools/check_definer_functions.py`가 live pg_proc로 보지만 복원 시험에 연결돼 있지 않다. 따라서 "전체 복원 합격"은 여전히 미완료다.
- 다음 첫 행동: 복원 시험에 (a) `pg_roles`·role membership, (b) `pg_policy`와 `relrowsecurity`/`relforcerowsecurity`, (c) `check_definer_functions.py`의 판정, (d) object 저장소 바이트와 DB 참조의 일치, (e) 복원 후 서비스 재개(실제 기동과 첫 요청)를 추가한다. 담당 Claude, reviewer Codex.
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
