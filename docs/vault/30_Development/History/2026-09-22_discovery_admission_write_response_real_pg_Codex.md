---
doc_id: "CODEX-DISCOVERY-ADMISSION-REAL-PG-001"
title: "Discovery admission 응답 계약의 실제 PostgreSQL 검증"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "pending"
updated: "2026-09-22T00:16:21+09:00"
source_of_truth: "Git"
tags: ["postgresql", "discovery", "response-model", "provenance"]
---

# Discovery admission 응답 계약의 실제 PostgreSQL 검증

## 범위

기준 코드는 integration tip `a7b6b1a1c9659fb14551bf8d89d673089ea5e8dc`이고, 검증은 `C:/Project/SaintVision-Invion/.worktrees/codex-write-response-contract`에서 수행했다. `POST /v1/discovery/candidates/{announcement_id}/admission` 한 경로에 대해 실제 마이그레이션 PostgreSQL과 서비스, FastAPI 라우트, `DiscoveryAdmissionResponse` 직렬화가 이어지는지 확인했다.

기존 `test_cli_credential_is_digest_only_and_works_from_issue_to_admission`은 실제 PostgreSQL에서 자격증명 발급과 공지를 거쳤지만 admission 마지막 단계만 `discovery_service.admit_candidate`를 직접 호출했다. 이를 실제 HTTP admission 요청으로 바꿨다. 시험은 candidate row가 실제 DB에 있는 상태에서 앱의 정상 `get_session`/tenant scope를 사용하고, 테스트 사용자 Principal만 dependency override로 제공한다. 서비스 반환이 `response_model`을 통과해 HTTP 201로 나오는지와 반환 객체의 ID·token 최소 길이·만료 시각·다음 단계 문구를 확인한다. bootstrap token 본문은 pytest 실패 메시지나 기록으로 출력하지 않으며, 원래 discovery bearer가 앱 로그에 나타나지 않는 기존 단언도 유지한다.

## 실행 증거

- 명령: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe tools/provenance.py -- C:/Project/SaintVision-Invion/.venv/Scripts/python.exe -m pytest tests/integration/test_discovery_machine_credentials.py::test_cli_credential_is_digest_only_and_works_from_issue_to_admission -q`
- provenance wrapper 결과: exit 0; `1 passed, 5 warnings in 5.44s`.
- 인터프리터: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`, Python 3.14.6. 플랫폼 Windows 11. Executor `egpar`; 이는 Codex 작성자 실행이며 독립 검토가 아니다.
- 실행 시각: 2026-09-22 00:16:21 KST. 당시 코드 SHA는 위의 `a7b6b1a...`; 수정 중인 시험 파일 하나가 있어 working tree는 dirty였고 통합 tip과 SHA는 일치했다.
- 환경: PostgreSQL 16 disposable container `sv-codex-admission-pg-2ebcee305fd0485fb87beae44ff65620`. 컨테이너에 `ai.saintvision.owner=codex` 및 고유 `ai.saintvision.write-response-test=codex-admission-2ebcee305fd0485fb87beae44ff65620` 소유 라벨을 붙였다. 데이터 경로는 tmpfs라 익명 볼륨을 만들지 않았다. 비밀번호 없는 trust 인증은 loopback의 임시 published port만 사용했다. DSN은 테스트 프로세스 환경변수로만 전달했고 문서·출력에 기록하지 않았다.
- Docker 정리: 시작 48 containers, 실행 중 49, 종료 후 48. 정리 전 정확한 소유 라벨을 inspect했고, 제거 뒤 같은 이름의 container가 더는 inspect되지 않는 것을 확인했다.
- 첫 시도는 worktree 내부에 없는 `.venv` 상대경로를 호출해 pytest가 시작되지 않았다. 이를 통과/실패 시험으로 세지 않고, 주 checkout의 절대 프로젝트 interpreter를 사용해 provenance wrapper로 다시 실행했다. 첫 시도 때 만든 컨테이너도 이후 소유 라벨을 재확인하고 제거했다.

## 판정과 남은 범위

실 PostgreSQL에서 확인된 쓰기 응답은 네 HIGH 경로 중 후보 admission 하나뿐이다. `ProjectCreateResponse`, `MemberRoleResultResponse`, `ResourceOfferResultResponse`는 이번 실행에서 실제 DB 서비스로 확인하지 않았다. 그 세 응답은 현재 TestClient와 mock 서비스 반환 기준이며, 이 한 건의 결과로 나머지 세 건까지 실 DB 검증됐다고 추론하지 않는다. Browser/실제 HTTP 배포/hosted CI도 이 시험 범위가 아니다.

다음 행동: 별도 reviewer가 현재 통합 SHA에서 새 PostgreSQL admission HTTP 단계를 고정 SHA 기준으로 검토한다. 다른 세 쓰기 경로는 실제 서비스 반환과 nullable·타입 경계를 별도 실 DB 시험으로 선택하기 전까지 mock 기준으로 표시한다.
