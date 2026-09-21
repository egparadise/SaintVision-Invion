---
doc_id: "CODEX-WRITE-RESPONSES-REAL-PG-001"
title: "고위험 쓰기 응답 계약의 실제 PostgreSQL 검증"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "pending"
updated: "2026-09-22T00:20:36+09:00"
source_of_truth: "Git"
tags: ["postgresql", "discovery", "response-model", "provenance"]
---

# 고위험 쓰기 응답 계약의 실제 PostgreSQL 검증

## 범위

기준 코드는 integration tip `c4b62108adce9e0273baabca0f051211920359bd`이고, 검증은 `C:/Project/SaintVision-Invion/.worktrees/codex-write-response-contract`에서 수행했다. 실제 마이그레이션 PostgreSQL과 서비스, FastAPI 라우트, strict response model이 이어지는지 높은 위험도의 쓰기 응답 두 경로에서 확인했다.

기존 `test_cli_credential_is_digest_only_and_works_from_issue_to_admission`은 실제 PostgreSQL에서 자격증명 발급과 공지를 거쳤지만 admission 마지막 단계만 `discovery_service.admit_candidate`를 직접 호출했다. 이를 실제 HTTP admission 요청으로 바꿨다. 시험은 candidate row가 실제 DB에 있는 상태에서 앱의 정상 `get_session`/tenant scope를 사용하고, 테스트 사용자 Principal만 dependency override로 제공한다. 서비스 반환이 `response_model`을 통과해 HTTP 201로 나오는지와 반환 객체의 ID·token 최소 길이·만료 시각·다음 단계 문구를 확인한다. bootstrap token 본문은 pytest 실패 메시지나 기록으로 출력하지 않으며, 원래 discovery bearer가 앱 로그에 나타나지 않는 기존 단언도 유지한다.

이어 `test_member_role_write_response_matches_real_postgres_state`를 추가했다. 두 실제 users, project, owner/viewer memberships 및 업무 관리자 grant를 PostgreSQL에 시드하고, 정상 DB session/tenant scope에서 `PUT /v1/projects/{project_id}/members/{user_id}`를 호출한다. DB에 저장된 `maintainer` 역할과 HTTP 응답의 project/user/status/권한 boolean을 대조한다. `canRequest=true`, `canApprove=false`, `canAdminister=false`는 mock 반환이 아니라 실제 권한 계산 결과다.

## 실행 증거

- 명령: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe tools/provenance.py -- C:/Project/SaintVision-Invion/.venv/Scripts/python.exe -m pytest tests/integration/test_discovery_machine_credentials.py::test_cli_credential_is_digest_only_and_works_from_issue_to_admission tests/integration/test_write_response_contract_real_pg.py::test_member_role_write_response_matches_real_postgres_state -q`
- provenance wrapper 결과: exit 0; `2 passed, 7 warnings in 4.73s`.
- 인터프리터: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`, Python 3.14.6. 플랫폼 Windows 11. Executor `egpar`; 이는 Codex 작성자 실행이며 독립 검토가 아니다.
- 실행 시각: 2026-09-22 00:20:36 KST. 기준 SHA는 `c4b62108...`; 새 멤버 경로 시험 파일 하나가 untracked였으나 tracked admission 경로와 나머지 tree 내용은 기준 tip이었다. 통합 tip과 SHA는 일치했다.
- 환경: PostgreSQL 16 disposable container `sv-codex-write-responses-pg-12a4a2690b40496fb2ddbe64173fa1e2`. 컨테이너에 `ai.saintvision.owner=codex` 및 고유 `ai.saintvision.write-response-test=codex-write-responses-12a4a2690b40496fb2ddbe64173fa1e2` 소유 라벨을 붙였다. 데이터 경로는 tmpfs라 익명 볼륨을 만들지 않았다. 비밀번호 없는 trust 인증은 loopback의 임시 published port만 사용했다. DSN은 테스트 프로세스 환경변수로만 전달했고 문서·출력에 기록하지 않았다.
- Docker 정리: 시작 48 containers, 실행 중 49, 종료 후 48. 정리 전 정확한 소유 라벨을 inspect했고, 제거 뒤 같은 이름의 container가 더는 inspect되지 않는 것을 확인했다.
- 첫 시도는 worktree 내부에 없는 `.venv` 상대경로를 호출해 pytest가 시작되지 않았다. 이를 통과/실패 시험으로 세지 않았다. 첫 시도 컨테이너는 같은 스크립트가 생성한 GUID 포함 이름으로 그 실행에서만 추적해 제거했지만, 그때 Docker inspect 템플릿 오류로 라벨을 다시 읽어 확인하지 못했다. 이 절차는 증거로 세지 않는다. 두 번째 provenance 실행에서는 라벨 JSON을 성공적으로 inspect해 일치한 뒤 제거하고 제거 여부까지 확인했다.

## 판정과 남은 범위

실 PostgreSQL에서 확인된 쓰기 응답은 네 HIGH 경로 중 후보 admission과 멤버 역할 변경 두 개다. `ProjectCreateResponse`와 `ResourceOfferResultResponse`는 이번 실행에서 실제 DB 서비스로 확인하지 않았다. 이 둘은 현재 TestClient와 mock 서비스 반환 기준이다. 둘을 실 DB로 확인했다고 나머지 둘까지 실 DB 검증됐다고 추론하지 않는다. Browser/실제 HTTP 배포/hosted CI도 이 시험 범위가 아니다.

다음 행동: 별도 reviewer가 현재 통합 SHA에서 두 PostgreSQL HTTP 경로를 고정 SHA 기준으로 검토한다. 프로젝트 생성과 자원 제공량 변경은 실제 서비스 반환과 nullable·타입 경계를 별도 실 DB 시험으로 선택하기 전까지 mock 기준으로 표시한다.
