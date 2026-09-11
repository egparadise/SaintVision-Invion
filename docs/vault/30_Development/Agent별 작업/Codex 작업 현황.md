---
doc_id: "WORKBOARD-CODEX-001"
title: "Codex 작업 현황"
version: "1.0.11"
status: "review"
author: "Codex"
updated: "2026-09-12T02:08:57+09:00"
source_of_truth: "Git"
---

# Codex 작업 현황

[[전체 개발 진행 현황]] → 이 페이지 → [[Agent 지속 개발 운영 규칙]] 순서로 확인한다. 이 페이지는 현재 후속 카드 목록이며 이전 장문 보고서는 SHA별 근거다.

- 배정 owner: Codex. 독립 reviewer: Claude. 현재 착수/검토 기록은 아래 실제 SHA와 History로 확인한다. 작성자 보고를 독립 승인으로 바꾸지 않는다.
- 공통 Skill: agent-delivery v1.1.0, 역할 Skill core-reliability v1.0.0. 계획: [[Backend 최종 개발 계획]], [[DB 최종 개발 계획]], [[Storage 최종 개발 계획]].
- 계약: GUIDE-001, GOV-AGENT-001, GOV-GIT-001, ADR-INDEX-001 v1.29.0, [[Codex Workspace 편집과 PTY 및 원격 Git 계약]] v1.1.0, [[Codex 실제 실행 결과 조회 계약]]. 계약 변경 시 버전 갱신.
- 확인 기준: 2026-09-11T17:07:33+09:00. 준비됨(ready)은 아직 착수했다는 뜻이 아니다. 차단 카드 대신 선행 없이 가능한 ready 카드를 진행한다.

## 최근 확인한 진척

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
- 다음 첫 행동: 74012b3 실제 Linux/DB backend와 0f5f4e8 통합을 전달했다. 보호 registry CLI/원자 회전76ba5ba와 운영 절차를 전달했다. RPO 판정/서비스/0036을 b49ecd3로 전달했다. 다음 Claude8a8f3b4 backup ledger와d63717f permission snapshot을 검토하고 Storage 인수를 진행하며 독립 검토를 받는다. 실제 파일 교체/회수 경합48개는 검증됐다.
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
