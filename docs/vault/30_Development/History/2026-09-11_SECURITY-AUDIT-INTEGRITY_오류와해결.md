---
doc_id: "ERR-SECURITY-AUDIT-INTEGRITY-20260911"
title: "DB 감사·복원·결과 검토 오류와 해결"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-09-11T18:10:30+09:00"
source_of_truth: "Git"
---

# DB 감사·복원·결과 검토 오류와 해결

기준: [[Codex DB 함수 감사와 복원 판정 검토]]. 원래 작성물의 독립 점검과 Codex 수정본의 자기 검증을 구분한다.

| ID / 우선순위 | 재현·영향 | 조치 / 다음 owner |
|---|---|---|
| CX01-01 / P1 | Claude 9995122 감사: zero-argument definer·binding 주석·인증 함수 overload·unsafe search_path·폐기 출력 reader의 EXECUTE 재부여 모두 unsafe=0 | Codex: 동일 도구의 전체 정의/ACL/inventory 정책 대조와 실제 PostgreSQL mutation 회귀. Claude가 변경본 독립 검토 |
| CX01-02 / P1 | Claude 9995122 복원: 비어 있는 source와 잘못된 backup bytes, 실제 pg_restore exit 1인데 integrityVerified=true, fencingVerified=true. 필수 table/digest는 absent, 조회 실패 fence는 0 | Claude CL-03: restore nonzero/필수 schema 누락/미측정/조회 실패는 성공 금지. source/target 집합 합집합 비교, inv 실제 내용, epoch·journal 포함 범위/불가 분리 |
| CX01-03 / P1 | f50310e fixture route에 존재하지 않는 path를 전달하니 216 bytes의 생성 코드와 HTTP 200을 반환. 내용에 Verified Output Artifact 문구가 있으나 실제 실행 결과가 아님 | Gemini GM-01: fallback 제거, 실제 kernel 인증/manifest/bytes/오류 경계 연결. fixture 통과를 운영 인수로 세지 않음 |
| CX01-04 / P1 | f50310e DeveloperStudio raw fetch에 공통 Authorization 없음; kernel 결과는 Depends(authenticated)로 JWT 요구. 반환 hash도 미대조, metadata는 구형 /artifacts/download 유지 | Gemini GM-01: 기존 인증 client에 binary response 지원, 실제 /artifacts 목록의 path/size/hash와 X-Content-SHA256 일치 확인 |
| CX01-05 / P1 | f50310e agentEngine codingTasks를 여전히 24 pass=true/6=false로 생성. secretLeaksDetected는 0 초기값 유지. 99+1 고정 예시 스캔은 실제 Agent/Context 100/30 평가가 아님 | Gemini GM-04: 미측정 상태 또는 실제 평가 Evidence 표시. Codex CX-08/Claude CL-05의 실행 평가와 연결 |
| CX01-06 / 로컬 시험 fixture | 첫 real-login 테스트가 public.projects의 없는 name 열 사용으로 실패 | 실제 code/display_name 열로 fixture 수정 후 같은 시험 재실행. 제품 DB schema 변경 없음 |

재현 원본은 [review reproduction](../Evidence/security-audit-review-20260911.json). 테스트용 DB/container만 사용하고 운영 데이터·계정·Node는 변경하지 않았다. Claude recovery 및 Gemini UI의 이 시각 이후 수정은 별도 SHA에서 재검토한다.

## 수정본과 동기화 후속

- c28cdff 재검토: CX01-02의 기존 invalid backup/empty DB 허위 성공은 거부로 바뀌었다. 전체 복원 인수는 미완료. `_passed`의 음수 RPO·restore nonzero 판정은 아직 true이며 별도 판정 함수 시험으로 재현했다. Claude CL-03에서 유한/비음수 측정·명시적 restore 오류 정책·필수 schema/role/RLS/함수/object/journal/서비스 재개를 연결한다.
- sync --check는 외부 문서 3개 충돌로 exit 1, no writes. 외부 원문·hash와 소스 commit을 Evidence에 보존하고 신선한 History/검토 기록을 유지하여 병합한다. 바이트가 동일한 캡처 baseline만 state로 인수한 뒤 정상 동기화한다.
- CI 6개 account billing/spending limit 때문에 시작 불가. 운영 책임자 해소 후 같은 구현 SHA에서 재실행. 로컬 통과를 CI 성공이라 쓰지 않는다.
