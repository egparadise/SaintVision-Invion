---
doc_id: "CODEX-WRITE-RESPONSES-REAL-PG-001"
title: "고위험 쓰기 응답 계약의 실제 PostgreSQL 검증"
version: "1.2.0"
status: "review"
author: "Codex"
reviewer: "pending"
updated: "2026-09-22T00:40:09+09:00"
source_of_truth: "Git"
tags: ["postgresql", "discovery", "response-model", "provenance"]
---

# 고위험 쓰기 응답 계약의 실제 PostgreSQL 검증

## 범위

기준 코드는 integration tip `33bf07657a0043a3aa19d08c33c95b517b36ab37`이고, 검증은 `C:/Project/SaintVision-Invion/.worktrees/codex-write-response-contract`에서 수행했다. 실제 마이그레이션 PostgreSQL과 서비스, FastAPI 라우트, strict response model이 이어지는지 기존 HIGH 쓰기 응답 네 경로에 새 HIGH workspace status 경로를 더해 확인했다.

기존 `test_cli_credential_is_digest_only_and_works_from_issue_to_admission`은 실제 PostgreSQL에서 자격증명 발급과 공지를 거쳤지만 admission 마지막 단계만 `discovery_service.admit_candidate`를 직접 호출했다. 이를 실제 HTTP admission 요청으로 바꿨다. 시험은 candidate row가 실제 DB에 있는 상태에서 앱의 정상 `get_session`/tenant scope를 사용하고, 테스트 사용자 Principal만 dependency override로 제공한다. 서비스 반환이 `response_model`을 통과해 HTTP 201로 나오는지와 반환 객체의 ID·token 최소 길이·만료 시각·다음 단계 문구를 확인한다. bootstrap token 본문은 pytest 실패 메시지나 기록으로 출력하지 않으며, 원래 discovery bearer가 앱 로그에 나타나지 않는 기존 단언도 유지한다.

이어 `test_member_role_write_response_matches_real_postgres_state`를 추가했다. 두 실제 users, project, owner/viewer memberships 및 업무 관리자 grant를 PostgreSQL에 시드하고, 정상 DB session/tenant scope에서 `PUT /v1/projects/{project_id}/members/{user_id}`를 호출한다. DB에 저장된 `maintainer` 역할과 HTTP 응답의 project/user/status/권한 boolean을 대조한다. `canRequest=true`, `canApprove=false`, `canAdminister=false`는 mock 반환이 아니라 실제 권한 계산 결과다.

사용자가 새로 올린 HIGH 재판정에 따라 `PUT /v1/workspaces/{workspace_id}/status`를 두 응답보다 먼저 포함했다. `WorkspaceStatusResponse`는 lifecycle 상태와 `allowedNext` 원소 모두를 다섯 상태 Literal로 제한하고 extra 필드를 거부한다. route는 service transition 이후 다음 상태 집합을 만들어 반환한다. core 시험은 상태 전이표 전체를 독립 기대 그래프와 비교하고 모든 대상이 알려진 상태인지 검사한다. 실제 PG 시험은 `provisioning → ready` 전이를 수행해 DB 상태와 응답을 대조하고 `allowedNext == ["deleting", "suspended"]`를 확인한다. 즉 상태 집합만 맞는지와 그 상태에서 다음 간선 집합이 맞는지를 모두 확인한다.

나머지 두 경로도 실제 DB 시험으로 확장했다. 프로젝트 생성은 실 DB의 project와 owner membership이 만들어지고 `memberCount=1`, kernel link 미설정 상태가 응답에 반영되는 것을 확인한다. 제공량 변경은 실제 capability와 관리자 권한을 시드하고, PostgreSQL의 `apply_capability_offer` 경계를 호출한 뒤 offer row의 canonical 8000 millicores를 응답과 대조한다. 이 시험에서는 대응하는 `inv.nodes`/resource가 없어 적용 결과는 의도된 `appliedToKernel=false`, `resource_not_registered`다. 커널 자원 등록 후 `appliedToKernel=true` 성공 경로까지 검증한 것은 아니다.

## 실행 증거

- 명령: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe tools/provenance.py -- C:/Project/SaintVision-Invion/.venv/Scripts/python.exe -m pytest tests/integration/test_discovery_machine_credentials.py::test_cli_credential_is_digest_only_and_works_from_issue_to_admission tests/integration/test_write_response_contract_real_pg.py -q`
- provenance wrapper 결과: exit 0; `5 passed, 13 warnings in 6.80s`. 각 PG 시험은 직렬 실행됐으며 같은 세션의 isolated migrated test database를 썼다.
- 인터프리터: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`, Python 3.14.6. 플랫폼 Windows 11. Executor `egpar`; 이는 Codex 작성자 실행이며 독립 검토가 아니다.
- 실행 시각: 2026-09-22 00:29:54 KST. 코드 기준 SHA는 `33bf07657a0043a3aa19d08c33c95b517b36ab37`; 실행 당시 작업 트리는 dirty였고 코드 변경과 추가 산출물이 있는 것을 provenance가 기록했다. 따라서 이 결과는 해당 SHA에 수정 중인 변경을 적용한 작성자 실측이지 clean/통합 commit SHA에서의 실행이 아니다.
- 환경: Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6, Windows 11; executor `egpar`/Codex. PostgreSQL 16 disposable container `sv-codex-write-responses-pg-2bac4707a81d40be8798a7129fb3dd81`. `ai.saintvision.owner=codex` 및 고유 `ai.saintvision.write-response-test=codex-write-responses-2bac4707a81d40be8798a7129fb3dd81` 라벨을 inspect했다. 데이터 경로는 tmpfs라 익명 볼륨을 만들지 않았다. 비밀번호 없는 trust 인증은 loopback 임시 published port만 사용했다. DSN은 테스트 프로세스 환경변수로만 전달했고 기록하지 않았다.
- Docker 정리: 시작 48 containers, 실행 중 49, 종료 후 48. 정확한 소유 라벨을 확인한 뒤 제거했고, 제거 후 inspect에서 부재를 확인했다.

### 추가 로컬 검사

같은 worktree에서 dirty 작업 트리로 다음을 각각 `tools/provenance.py -- <command>`에 감싸 실행했다. 각 명령의 provenance는 시각과 상태를 함께 출력했다. 모두 `.venv/Scripts/python.exe` 3.14.6, executor Codex였다. Schema/core/binding/docs/ontology 검사는 현재 integration base `5eb308507c8119ed639df221f3910d835132d932`에서 00:38:36 KST에 실행했다. PG 실행은 이전 base `33bf07657a0043a3aa19d08c33c95b517b36ab37`에서 00:29:54 KST에 실행됐다. 그 뒤 integration 커밋 `5eb3085`의 변경 경로는 `apps/web`과 문서뿐이고 backend/service/API 경로는 포함하지 않는다. 그러므로 PG 검증 대상 코드는 바뀌지 않았지만, PG 테스트를 새 SHA에서 다시 실행한 것은 아니다.

- `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe -m pytest tests/core/test_write_response_contracts.py -q`: exit 0, 27 passed, 2 warnings. PG DSN은 absent; 이는 mock/contract slice다. 상태별 다섯 응답의 `allowedNext`를 각각 검사한다.
- `tools/export_schemas.py --check`: exit 0, 46 schemas current.
- `tools/check_contract_bindings.py`: exit 0, 35 fixtures covered; 11 kernel response anchors tested.
- `tools/check_docs.py`: exit 0, 24 source hashes, 679 versioned documents, 48 tasks, 12 outcomes.
- `tools/check_ontology.py`: exit 0; RDF, SHACL and competency checks passed.
- `git diff --check`: exit 0.
- 전이표 되돌림 대조(33bf 작업 트리, 00:35:04 KST): service의 `ready → deleting` 간선을 임시 제거한 뒤 `test_workspace_status_allowed_next_matches_the_lifecycle_graph`가 1 failed/exit 1로 정확히 검출했다. 간선을 원복한 뒤 새 integration base `5eb3085`에서 위 core suite는 27 passed/exit 0이다. 테스트 보강 중 한 차례 요청 helper가 잘못된 상태를 보내 invalid-response 케이스에서 422를 받았고, helper를 고쳐 검증 대상인 service 응답 오류가 라우트에 도달하도록 한 뒤 재실행했다. 그 중간 실패는 제품 결함이 아니다.
- Obsidian: check→apply→check, 2026-09-22 00:35:44–00:35:53 KST. 첫 check는 1473 managed/3 pending/0 conflicts, apply는 3개 export와 1473 destination hashes 일치, 마지막 check는 1473 managed/0 pending/0 conflicts였다. 각 exit 0.
- 이 History 문서의 마지막 문구를 정리한 뒤 00:36:13 KST에 재동기화했다: `--check`에서 1 pending/0 conflicts, `--apply` 1 file 및 destination hashes 일치, 후속 `--check` 1473 managed/0 pending/0 conflicts. 각 exit 0.
- 최신 integration `5eb308507c8119ed639df221f3910d835132d932`를 받아온 뒤 Obsidian은 1474 managed/4 pending/0 conflicts였다. 00:39:20 KST에 `--apply`가 4개 파일을 export하고 전체 destination hash를 맞췄고, `--check`는 1474 managed/0 pending/0 conflicts, exit 0을 반환했다. worktree-relative `.venv`로 먼저 호출한 시도는 command-not-found로 도구가 시작되지 않아 절대 경로 프로젝트 interpreter로 재실행했다.
- 이후 History 문구 수정으로 1건 pending이 생긴 것을 00:40:09 KST에 다시 apply/check했다. 1 file exported, 모든 destination hash 일치, 1474 managed/0 pending/0 conflicts; 두 명령 exit 0.

## 판정과 남은 범위

실 PostgreSQL에서 확인된 네 HIGH 쓰기 응답은 `ProjectCreateResponse`, `DiscoveryAdmissionResponse`, `MemberRoleResultResponse`, `ResourceOfferResultResponse`다. 또한 새 HIGH `WorkspaceStatusResponse`도 실 DB로 확인했다. 앞 네 건의 51 focused TestClient/mock 검증은 기존에 별도로 실행된 것이며, 이번 다섯 PG-backed HTTP 시험은 모의 service 반환이 아니다. 범위는 로컬 FastAPI TestClient와 실제 PostgreSQL 16이다. 운영 서버 HTTP, hosted CI, 브라우저, 실 kernel resource가 등록된 제공량 적용 성공 경로는 포함하지 않는다.

다음 행동: 별도 reviewer가 통합에 반영된 최종 SHA에서 네 원 HIGH 쓰기 응답과 재판정으로 HIGH가 된 workspace lifecycle 응답의 PostgreSQL 시험을 고정 SHA 기준으로 검토한다. 실제 kernel resource가 등록된 상태의 제공량 적용 성공 분기와 운영 HTTP/browser 인수는 별도 근거로 남긴다.
