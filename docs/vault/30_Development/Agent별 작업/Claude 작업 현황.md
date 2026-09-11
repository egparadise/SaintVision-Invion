---
doc_id: "WORKBOARD-CLAUDE-001"
title: "Claude 작업 현황"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T17:13:25+09:00"
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

## 작업 카드

각 카드의 sprint/area/outcome/acceptance는 부모 task에서 상속한다. 원래 task owner를 바꾸지 않는다. CL-01은 독립 검토 업무다. 카드 상태와 원래 48개 task의 최종 done은 별개다. 각 카드의 base/branch와 실제 검증값은 착수 시 담당자가 고정한다.

| 카드 | 우선순위 | 상태 | 부모 task | 범위 |
|---|---|---|---|---|
| CL-01 | P0 | ready | S01-DB S04-DB S06-BE S06-DB S08-DB | Codex 최신 커널 독립 검토 |
| CL-02 | P0 | ready | S02-BE S02-DB S02-ST S03-DB | 운영 로그인·권한·Workspace·폴더 적용 |
| CL-03 | P0 | ready | S12-DB S12-ST | 복원 도구의 남은 검증 결함 수정 |
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

- owner / reviewer: Claude / Codex; status: ready; priority: P0.
- 원래 목표/합격 조건: OUT-12 / AC-12.
- 다음 첫 행동: 9995122의 fencing 조회 실패→0, content digest의 public 일부 한정, 누락 대 누락 동일 처리와 mtime RPO를 고친다. 역할/함수/RLS/object/journal/서비스 재개를 포함한다.
- 필요한 합격 증거: 조회 실패는 unknown/실패, 내용 손상/누락/권한 소실/old epoch가 확실히 거부됨. 실제 복구 지점 기준 RPO≤15분·서비스 정상화까지 RTO≤1시간 실측.
- 선행/차단과 해소 담당: CX-07 복원 계약·Codex 검토. 기존 권한 대조/public+inv count 보완은 인정하되 전체 복원 합격은 미완료.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

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
