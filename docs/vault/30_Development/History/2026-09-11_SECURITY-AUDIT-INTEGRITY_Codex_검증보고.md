---
doc_id: "HIST-SECURITY-AUDIT-INTEGRITY-VERIFY-20260911"
title: "DB 감사 무결성 보강과 3 Agent 검토 보고"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-09-11T18:10:30+09:00"
source_of_truth: "Git"
---

# DB 감사 무결성 보강과 3 Agent 검토 보고

Task SECURITY-AUDIT-INTEGRITY / CX-01; owner Codex, 변경본 reviewer Claude pending. [[2026-09-11_SECURITY-AUDIT-INTEGRITY_Codex_착수]], [[Codex DB 함수 감사와 복원 판정 검토]], [[2026-09-11_SECURITY-AUDIT-INTEGRITY_오류와해결]].

## 검토 및 구현

base 995b3a3, branch agent/codex/workspace-bridge, 기존 PR19 후속. Claude 9995122의 감사/복원과 Gemini f50310e의 결과/평가 경계를 점검했다. 현재 kernel tenant guard가 다시 누수한다고 보고한 것이 아니라, 기존 감사가 위험한 변경을 잡지 못하는 문제다.

실제 PostgreSQL에서 원래 감사의 false negative 5개와 invalid backup restore exit 1의 허위 성공을 재현했다. Codex는 `tools/check_definer_functions.py`를 전체 정의/권한/필수 inventory를 대조하도록 보강하고 9개 정책, mutation·실제 LOGIN·비밀 오류 비노출 회귀를 추가했다. migration 업그레이드의 현재 함수 검사와 Docker source 묶음에 연결했다.

복원 도구와 Frontend 구현의 해당 finding은 각각 Claude CL-03/Gemini GM-01·04로 수정 요청한다. 그들의 작업 폴더에 변경을 쓰거나 작성자의 새 코드를 대신 승인하지 않았다. 같은 개념의 새로운 ResultView/감사 도구를 만들지 않는다.

## 진행 중 확인한 증거

- 원래 검토 재현: 격리 PostgreSQL 16, 함수 9개 baseline, 위험 변형 5개 모두 기존 unsafe=0; 잘못된 백업 restore exit 1에도 두 검증 true. [재현 Evidence](../Evidence/security-audit-review-20260911.json).
- Windows + 격리 PostgreSQL 회귀: 수정 뒤 **57 passed / 1 skipped**, exit 0. skip은 Linux 실제 recovery runtime 하나이며 통과로 세지 않는다. 공통 9개 정의, 변경 거부, 실제 다른 tenant/unset/empty scope 거부를 확인했다.
- f50310e fixture handler를 독립 Python process에서 직접 호출: 없는 결과 path에 200/생성 fallback 216 bytes. 브라우저/운영 네트워크 호출이 아니다.
- 고정 SHA Linux 회귀·기본 검사·20개 migration 경로·문서 검사·CI·Obsidian 결과는 전달 단계에서 아래에 추가한다. 전체 CI/실장비 인수는 별도다.

## 전달과 다음 행동

고정 SHA 검증 후 push/CI 상태·Obsidian 동기화를 기록한다. 다음 Codex는 CX-01의 수정본 독립 재검토/통합과 CX-02 운영·credential·Storage 계약을 진행한다. CX-03 원격 설치 및 7개는 기존 선행 상태를 유지한다. 전체 CX-01/main/운영 인수를 done으로 올리지 않는다.

## 고정 SHA 검증·수정본 재검토

구현 SHA **b9a53f891a32be42da7d6cecb2a06a295814f3a1**. source copy가 clean이고 전체 source hash를 검사한 Linux 격리 환경에서 **65 passed / 0 skipped**, exit 0. 새 definer mutation/실제 로그인·기존 subject tenant·자원 제공량·프로비저닝·실제 recovery 입력·계정/migration 회귀를 포함한다. Docker runner/DB/network 정리도 모두 확인했다. [Linux Evidence](../Evidence/security-audit-b9a53f8-linux.json).

같은 SHA 기본 회귀 **304 passed / 0 skipped**, exit 0. 기존 공개 **20개 prior→head→head** 모두 제한 runtime grant와 새 9개 privileged function policy 확인에 통과했다. Windows 중간 57/skip 1은 디버깅 기록으로 남기고 최종 합계에 중복 가산하지 않는다. [검사 영수증](../Evidence/security-audit-b9a53f8-checks.json).

18:05 이후 Claude **c28cdff**를 재검토했다. 같은 invalid backup/empty DB 실제 재현에서 `restoreExitCode=1`, `integrityVerified=false`, `fencingVerified=false`로 바뀌어 **이전 허위 성공 사례의 수정은 확인**했다. inv 내용 digest·unknown fencing·archive 시각·공통 _passed 보완도 소스에서 확인했다. 다만 _passed에 명시적인 음수 RPO 입력과 restoreExitCode=1 입력을 각각 주면 true다. 이 두 항목은 판정 함수 시험이며 새로운 전체 복원 성공 재현으로 과장하지 않는다. [수정본 재검토](../Evidence/security-audit-claude-c28cdff-recheck.json).

Claude 7810ac1의 CL-03 진행 기록과 Gemini f50310e의 GM-01/02/04 기록을 수신해 각 작업판에 합쳤다. 작성자 보고의 수치와 Codex 검토 결과를 구분한다. Gemini의 없는 파일 생성 응답·인증 없는 raw fetch·고정 코딩 평가에 대해서는 **수정 요청**을 유지한다. 전체 CLAUDE/Gemini 코드를 이 보안 commit에 병합했다고 표시하지 않는다.

## GitHub 및 Obsidian

b9a53f8 origin push exit 0. 같은 SHA CI 6개는 계정 결제/사용 한도 때문에 시작 전 실패했다. [Core 34582518481](https://github.com/egparadise/SaintVision-Invion/actions/runs/34582518481), [Documentation 34582518319](https://github.com/egparadise/SaintVision-Invion/actions/runs/34582518319). [모든 CI 결과](../Evidence/security-audit-b9a53f8-ci.json). 코드의 독립 reviewer Claude pending, main/운영 인수 미완료.

Obsidian check에서 외부 변경 3개로 정상 중단했다. progress/Gemini 작업판은 f50310e, History 인덱스는 같은 source의 오래된 v1.0.16/줄바꿈 차이였다. [외부 원문과 hash](../Evidence/security-audit-sync-proposals-20260911.json)를 보존하고, 현재 Codex History v1.0.22의 내용은 유지하면서 새 담당 보고만 연결했다. 동일 원문 baseline을 바이트 변경 없이 인수한 뒤 통상 check/apply/check로 최종 내용을 전달한다. 강제 충돌 무시나 과거 이력 삭제는 하지 않는다.

다음 Codex: CX-01의 원 owner 수정본 인수·같은 SHA 통합 및 CX-02의 credential/Storage/운영 계약. Claude: CL-03에 numeric/restore exit/schema·role·RLS·definer/journal/object/서비스 재개 경계 추가, 새 감사 도구 독립 검토. Gemini: GM-01/04 수정본 제출 후 실제 인증 API·파일 bytes·평가 Evidence 대조. CX-03 원격 설치 대기는 유지한다.

## 최종 전달 확인

2026-09-11T18:13:30+09:00 문서 SHA `5a815c0e7bdbe5a39570fb6f88da5d10b4469dad`에서 Obsidian **417개 관리 파일 전체 hash 일치**, export 대기 0/conflict 0, check/apply/check exit 0. 외부 3개 원문은 보존하고 동일 baseline 인수는 destination 0 writes였다. 추가 신규 Gemini 보고서는 Git 원문과 줄바꿈만 다른 것을 확인해 로컬 사본을 같은 바이트로 맞췄다. 공유 폴더의 새 편집 내용을 강제로 덮어쓰지 않았다.

문서 검사 exit 0: 원문 hash 24, versioned 문서 262, 48 task/12 outcome/links/owner/reviewer/skills/DAG. ontology 검사와 문서 ZIP build도 exit 0. 독립 문서/코드 승인 Claude pending, CI 계정 제한과 실장비 인수는 남는다. 이 전달 기록의 후속 commit은 제품 source를 바꾸지 않으며 commit/push 뒤 다시 동기화한다.
