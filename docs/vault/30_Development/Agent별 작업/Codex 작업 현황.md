---
doc_id: "WORKBOARD-CODEX-001"
title: "Codex 작업 현황"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T17:21:49+09:00"
source_of_truth: "Git"
---

# Codex 작업 현황

[[전체 개발 진행 현황]] → 이 페이지 → [[Agent 지속 개발 운영 규칙]] 순서로 확인한다. 이 페이지는 현재 후속 카드 목록이며 이전 장문 보고서는 SHA별 근거다.

- 배정 owner: Codex. 독립 reviewer: Claude. 현재 카드 수신/착수 여부: **Codex의 초기 정의이며 각 담당 Agent의 수신 확인은 아직 없다**. Codex는 이 문서 작업만 실제 수행 중이다.
- 공통 Skill: agent-delivery v1.1.0, 역할 Skill core-reliability v1.0.0. 계획: [[Backend 최종 개발 계획]], [[DB 최종 개발 계획]], [[Storage 최종 개발 계획]].
- 계약: GUIDE-001, GOV-AGENT-001, GOV-GIT-001, ADR-INDEX-001 v1.27.0, [[Codex Workspace 편집과 PTY 및 원격 Git 계약]] v1.1.0, [[Codex 실제 실행 결과 조회 계약]]. 계약 변경 시 버전 갱신.
- 확인 기준: 2026-09-11T17:07:33+09:00. 준비됨(ready)은 아직 착수했다는 뜻이 아니다. 차단 카드 대신 선행 없이 가능한 ready 카드를 진행한다.

## 최근 확인한 진척

제품 c5f2154: 편집/PTY/Git와 최신 account/tenant/offer kernel 통합. 로컬 통합 402개·기본 301개·Linux Go 고유 43개·20개 migration 경로 확인. 전달 02e6188, PR19 draft. CI/독립 검토/물리 원격 인수는 남는다.

## 작업 카드

각 카드의 sprint/area/outcome/acceptance는 부모 task에서 상속한다. 원래 task owner를 바꾸지 않는다. CL-01은 독립 검토 업무다. 카드 상태와 원래 48개 task의 최종 done은 별개다. 각 카드의 base/branch와 실제 검증값은 착수 시 담당자가 고정한다.

| 카드 | 우선순위 | 상태 | 부모 task | 범위 |
|---|---|---|---|---|
| CX-01 | P0 | ready | S01-DB S04-DB S08-DB | 최신 3 Agent 변경 통합과 보안 검토 |
| CX-02 | P0 | ready | S01-BE S01-ST S08-ST | 운영·credential·Storage 공통 계약 확정 |
| CX-03 | P0 | blocked | S03-BE S04-BE S12-BE | 실제 원격 Node 실행 프로필과 7개 시험 |
| CX-04 | P1 | planned | S06-BE S06-DB S06-ST | 원격 개발 작업공간과 실제 Git 인수 |
| CX-05 | P1 | planned | S05-BE S05-DB S05-ST S07-BE S07-DB S07-ST | 5대 배치·지역성·샤드 통신·복구 |
| CX-06 | P1 | planned | S08-BE | Windows·GPU·BuildKit 실행과 격리 |
| CX-07 | P1 | planned | S04-ST S08-ST S11-ST | 제품 Storage 규모와 복구 무결성 |
| CX-08 | P1 | planned | S09-BE | 제한 Agent·Reverse-Ontology 실행 루프 |
| CX-09 | P1 | planned | S11-BE S11-DB S12-BE | 릴리스 통합·5대 부하/장애·최종 인수 |

### CX-01 — 최신 3 Agent 변경 통합과 보안 검토

- owner / reviewer: Codex / Claude; status: ready; priority: P0.
- 원래 목표/합격 조건: OUT-01, OUT-04, OUT-08 / AC-01, AC-04, AC-08.
- 다음 첫 행동: Claude 9995122와 Gemini f08bf33을 c5f2154 계약에 대조하고 아래 신규 검토 항목을 owner에게 돌려보낸다. 수정 수신 후 하나의 통합 SHA로 정합성·tenant·결과 경계를 검증한다.
- 필요한 합격 증거: review finding별 해결 SHA/독립 검토, 현재 적용 DB 함수의 실제 다른 tenant 거부, 계약·migration 이력 보존. CI와 main 상태 별도.
- 선행/차단과 해소 담당: 검토할 코드 확보됨. 독립 승인자는 CL-01.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### CX-02 — 운영·credential·Storage 공통 계약 확정

- owner / reviewer: Codex / Claude; status: ready; priority: P0.
- 원래 목표/합격 조건: OUT-01, OUT-08 / AC-01, AC-08.
- 다음 첫 행동: 5대 조사표의 미확인 값과 허용 폴더를 정리하고 credential 참조/회수/로그 경계, S3 제품·키·보존 책임, IdP/DNS/TLS 설정 항목을 확정한다.
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
| 마지막 작업 / 착수 카드 | DEVELOPMENT-CONTINUITY / 공통 진행판 집계 대행. 제품 CX 카드의 완료를 뜻하지 않음 |
| 실제 owner / 읽은 진행판 버전 / KST | Codex / INDEX-PROGRESS-001 v1.0.12 / 2026-09-11T17:18:43+09:00 |
| branch / base SHA / 구현 SHA | agent/codex/workspace-bridge / 02e6188 / 공통 진입 b2c37f2, 문서 전달 994ab49, 최종 영수증 SHA는 Git 이력 참조 |
| 작업한 것 | 최신 3 Agent 소스·최초 12목표/48task 확인, 공통 진행판·26개 카드·상시 기록 지침 작성 |
| 확인한 것 / 명령 / exit code / 실제 환경 | check_docs.py 0; check_ontology.py 0; sync --check 0, conflict 0; 소스/PR/LAN 조회 Evidence 확보 |
| CI / 독립 reviewer / 운영 인수 | 994ab49 CI 6개 모두 계정 제한으로 시작 전 실패; Claude 독립 검토 pending; 원격/5대 운영 인수 미완료 |
| 남은 문제 / 차단 이유 / 해소 담당 | CI 계정 제한 운영자, 원격 실행 profile 설치 다른 PC 운영자+Codex 확인 |
| 다음 카드 / 첫 행동 / 다음 담당 | CX-01 / Claude 9995122 복원·definer와 Gemini f08bf33 계약 차이를 검토 / Codex |
| History / 오류 / Evidence / PR / sync 결과 | [[2026-09-11_DEVELOPMENT-CONTINUITY_Codex_검증보고]] / PR19 / 405개 hash 일치, 대기 0·충돌 0; 공통 지침 Gemini 1fba8c9·Claude 3ec288a push 확인 |
