---
doc_id: "HIST-PERMISSION-SNAPSHOT-REPORT-20260912"
title: "2026-09-12 PERMISSION-SNAPSHOT Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T02:08:57+09:00"
source_of_truth: "Git"
---

# 2026-09-12 PERMISSION-SNAPSHOT Codex 검증보고

CX-01/CX-09 · S08-DB/S11-DB/S12-DB. owner Codex / reviewer Claude pending. basec3b0482, 구현 **9755c6089e72a4d04e79e3a3218395c12c20241b**, agent/codex/workspace-bridge, PR19 draft. [[2026-09-12_PERMISSION-SNAPSHOT_Codex_착수]], [[Codex 권한 관측과 운영 인수 집계 계약]].

## 변경

d63717f의 수집 의도를 기존 PermissionSnapshot/pilot 서비스에 조율했다. tenant/project/user/contract 범위로 비교하고, 먼저 대상별 transaction advisory lock을 잡은 뒤 REPEATABLE READ 관측·기록을 수행한다. 프로젝트 A→B→A 동일 권한은 [null,null,false]다. disabled operator의 승인 capability 관측은 false이며 현재 인가 필드는 null을 유지한다. 관측 시각을 taken_at으로 보존하고 rollback/clock 역행을 거부한다. owner 아닌 runtime 쓰기 및 타 tenant subject/project를 거부한다.

ade5bb8의 release 없는 집계·명시적 CLI 호출·공통 종료 코드도 통합하되 기록 존재와 운영 인수를 분리했다. catalogComplete와 scope/unverified를 도입하고 evidenceComplete/operationalAcceptanceAssessed는 운영 증거 검증 계약이 아직 없어 false다. 만료 백업, 목표 미달 복원, 다른 criterion만 있는 인수 기록은 목록 충족에 쓰지 않는다. 기존 b49ecd3 실패/중단 met_targets 방어·420b81c 백업 파일/원장 연결·definer/RPO 정본을 보존했다. DB migration 없음.

## 실제 검증

| 명령·환경 | 결과 | 증거 |
|---|---|---|
| check_kernel_docker.py --tests test_permission_observation, test_operational_readiness, test_pilot, integration/test_recovery_drill | **74 passed /0 skipped/exit0**, clean9755c60 Linux | [74개 사례·이미지·정리](../Evidence/permission-observation-9755c60.json) |
| pytest core readiness_cli_boundary/recovery_verdict/recovery_capability | **55 passed/exit0**, Windows | [기본 검사·원본 재현](../Evidence/permission-review-20260912.json) |
| 동일56개 DB 사례의 Windows 클라이언트 + 격리 PostgreSQL 사전 검증 |56 passed/exit0, 최종74에 포함되는 사례로 합산하지 않음 | private cx01-2b3f98713ec0 기록; 최종 Linux 증거를 인수 근거로 사용 |
| 원본ade5bb8 pilot_readiness·격리 PostgreSQL | 문제4개 재현/exit0, 기능 합격 의미 아님 | 같은 기본 검사·재현 근거 |
| git push origin agent/codex/workspace-bridge |9755c60 exit0 | PR19 |
| 같은 SHA GitHub Actions6개 | 전부 계정 결제/한도로 job 시작 전 failure | [CI ID·annotation](../Evidence/permission-observation-9755c60-ci.json) |

74개는 새 관측/CLI11 + 기존 운영 진단10 + pilot35 + 실제 복원18이다. 대상별 동시2개가 하나의 first/하나의 predecessor를 이루는지, 관측 중 grant 회수가 이후 관측에서 드러나는지, 저장한 시각과 출력 시각이 일치하는지, flush 뒤 실패의 rollback/lock 해제, runtime/tenant 거부, 주입한 시계 역행 거부를 확인했다. JSON/text CLI는 snapshot commit 및 운영 인수 미검증 exit1이 일치한다. read-only 인수 목록 요청은 snapshot0행이다. 첫 개발 중50개 사전 검증은 최종 숫자에 가산하지 않는다.

## Claude 원본 독립 검토 근거

원본ade5bb8 함수에 실제 동일 DB fixture를 넣으면 ①metadata-only ②보존 기간 만료 ③목표 초과 복원 ④AC-11만 존재의 네 경우 모두 evidenceComplete=true를 반환했다. 목표 초과는 drillsMissingTargets에 표시하면서 완료였다. [원본 함수 재현 코드](../Evidence/acceptance-original-reproduction-20260912.txt)는 함수 return을 변경하지 않으며 새 catalogComplete 필드가 없는 KeyError 뒤 캡처한 원본 결과를 검사한다. 기존 d63717f의 프로젝트/disabled 오류2개는 [[2026-09-12_BACKUP-LEDGER_Codex_검증보고]]의 실제 재현을 이어 수정했다.

독립 검토는 Claude 원본에 대한 Codex 검토다. Codex 수정 자체의 독립 reviewer 승인은 아직 받지 않았다. 운영 성능/5대 부하/실제 시스템 시계 변경/production credential 변경을 시험한 것이 아니다. migration 변경이 없어 이전23개 업그레이드를 반복하지 않았으며 과거 결과를 이번 재실행으로 쓰지 않는다.

## 다음 행동과 담당

- Claude: 9755c60 및 ADR-082/083 독립 검토. 자신의 운영 절차/서비스 consumer에서 catalogComplete와 실제 운영 인수의 의미를 맞춘다. snapshot/집계 정본을 별도로 복제하지 않는다.
- Gemini: observedAt/changed/null 인가, catalogComplete/operationalAcceptanceAssessed/unverified를 구분해 표시. 기존 결과 인증/hash·drain/ticket·실장비 인수 지적은 별도다.
- Codex: 운영 인수를 true로 만들 실제 Evidence 수집·검증 경로와 최신 Agent 변경의 공통 계약을 검토한다. 원격 profile 수신 시 CX-03 실제7개를 재개하고 그 전에는 기존 계획의 실행 가능한 보안/복구 후속을 진행한다.
- Orca/운영 책임자: CI 계정 해소·실장비 설치 및 운영 입력 추적. PR21→22→19 검토 순서를 유지하며 미검토 main 병합을 하지 않는다.

전체 추정 **57.29% 완료/42.71% 잔여 유지**. 코드·로컬 검증은 진행됐으나 CI·peer·운영 증거/물리 인수 미완료로 공식 task done을 올리지 않는다. check_docs.py(원문24·문서298·작업48), check_ontology.py, 변경3개 Python Black 검사, git diff --check exit0. Obsidian 최초 check는 외부편집2개로 exit1·쓰기0: 원본을 보존하고 새 Agent 보고를 작성자 주장으로 조율했다. 최종 push/동기화는 영수증에 기록한다.
