---
doc_id: "HIST-SECURITY-AUDIT-INTEGRITY-VERIFY-20260911"
title: "DB 감사 무결성 보강과 3 Agent 검토 보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T18:03:37+09:00"
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
