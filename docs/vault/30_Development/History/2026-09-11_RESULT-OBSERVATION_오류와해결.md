---
doc_id: "ERROR-RESULT-OBSERVATION-20260911"
title: "RESULT-OBSERVATION 오류와 해결"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T13:44:00+09:00"
source_of_truth: "Git"
---

# 결과 조회 통합 중 발견한 오류

| 발견 내용 | 조치 |
|---|---|
| Claude 새 0026과 Codex 0027로 migration head가 둘 | 과거 파일을 유지한 0028 merge + tenant/현재 grant guard |
| subject definer가 인자 tenant만 신뢰 | current transaction tenant와 일치, 활성 계정/subject 일치 검사 |
| public Run 결과를 실제 커널과 같은 원본이라고 기술 | 실행 API는 현재 inv Run/attempt/receipt/Evidence를 조회. public 기록은 업무 기록으로 구분 |
| 원격 도구 준비 상태를 CP 로컬 CLI에서 검사 | 로컬 probe 호출 제거, 원격 관측 전 unknown 유지 |
| 업무 새 router에 /v1 prefix 없음 | /v1로 등록, combined API에서 Workspace readiness만 업무 라우팅 |
| 첫 통합 시험 수집 중 test_results 이름 충돌 | Claude 업무 시험을 test_business_results.py로 이동해 기존 kernel fixture와 분리. 이 실패를 통과로 집계하지 않음 |
| 이동 직후 준비 도구가 삭제 전 Git index 경로를 복사 | 이동을 index에 반영한 뒤 새 source 준비. 실패한 준비본으로 실행하지 않음 |
| 두 번째 통합 262개 중 신규 5개에서 approval fixture가 누락되어 setup 실패 | 공유 Node fixture의 approval 의존성을 명시적으로 import. 나머지 257개 통과와 신규 5개 미실행을 구분 |
| 교차 tenant 시험에 존재하지 않는 tenant를 사용해 403 전 containment 미설정 503 발생 | 이미 마련한 두 번째 실제 tenant를 사용해 RLS 거부를 검증 |
| 집중 시험에서 업무/통합 경로를 교차 나열할 때 일부 env fixture 미발견 | 기존 전체 시험과 같이 업무 경로 뒤 통합 경로로 묶어 실행. fixture 미실행을 통과로 집계하지 않음 |

개인키·실제 DB 자격증명·운영 epoch/profile은 변경하지 않았다. 시험 로그는 접근 제한 .work에 두고 공개 기록에는 testcase 상태와 SHA만 남긴다. 작성자가 시행한 시험과 Codex의 검증을 구분하며 독립 재검토는 Claude 대기다.
