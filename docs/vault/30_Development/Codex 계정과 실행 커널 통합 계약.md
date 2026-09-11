---
doc_id: "CONTRACT-ACCOUNT-KERNEL-001"
title: "Codex 계정과 실행 커널 통합 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T13:10:00+09:00"
source_of_truth: "Git"
---

# 계정·프로젝트와 실행 커널 통합

ACCOUNT-KERNEL의 owner는 Codex, 수정 코드 reviewer는 Claude 대기다. Claude 작성 계정/프로젝트 코드와 ADR-063의 첫 실행을 연결한다. [[2026-09-11_ACCOUNT-KERNEL_Codex_착수]]의 base와 [[최종 개발 계획 - 모든 개발의 지침]]을 따른다.

## ADR-064: 동일 인증, 분리된 DB 권한, 명시적 업무 라우팅

`inv.app.create_configured_app` 설정의 `business: true`를 명시하면 업무 CRUD를 연결한다. 기존 identity/JWKS/tenant/allowedOrigins를 재사용하며 새로운 로그인 신뢰를 만들지 않는다. 실제 IdP·브라우저 로그인·운영 계정 등록은 배포 환경의 선행 조건이다.

업무 계정 연결 문자열은 `INV_BUSINESS_DSN` 환경으로 공급한다. 명시한 host/port/dbname 및 접속 옵션은 `INV_RUNTIME_DSN`과 일치해야 하며 user/password만 달라진다. 업무 role은 비superuser·NOBYPASSRLS·inv_app 구성원이면서 inv_kernel 구성원이 아니어야 한다. 운영 DB/계정은 자동 생성하지 않는다. 업무와 kernel DB를 다른 호스트의 같은 이름 DB로 연결하는 구성도 거부한다.

업무 라우팅은 `/v1/projects` 목록/생성·상세·Workspace·구성원·설정, `/v1/users/*/status`, `/v1/capabilities/*/offer`, `/v1/nodes/*/offers`, `/v1/adapters`의 명시된 route만 받는다. `/v1/projects/{project}/runs` 이하 첫 실행/승인/취소/복구 및 binding/control은 기존 kernel이 처리한다. 양쪽 모두 기존 HTTP Origin·크기·중복 헤더·JSON·no-store 경계를 통과한다.

업무 토큰 검증은 AccessTokens에 위임하고, 검증 실패를 401로 변환한다. 현재 public.users의 subject/status에서 계정을 확인하고 요청 시 현재 멤버십을 조회한다. 미등록 사용자는 생성하지 않는다. 새 프로젝트의 소유권은 실행 grant를 만들지 않는다. 운영자가 business_projects/business_subjects/project_grants를 등록한 경우에만 기존 kernel의 권한 교집합으로 실행할 수 있다.

## ADR-065: 업무 관리 권한과 직렬화

프로젝트 소유권으로 다른 사용자를 정지하거나 물리 자원 제공량을 바꿀 수 없다. `inv.business_admin_grants`의 별도 `users.manage`/`resources.manage`와 활성 사용자를 확인한다. 이 grant는 운영자 소유이며 inv_app/inv_kernel에 직접 조회·쓰기 권한을 부여하지 않는다. 임의 UI 역할이나 JWT role로 grant를 생성하지 않는다. 현재 tenant에 한정된 definer 함수가 권한을 검사하고 트랜잭션 동안 grant 공유 잠금을 유지한다. API가 권한을 검사하기 전에 관련 사용자 행을 ID 순서로 잠가 권한 회수·상호 정지 경합을 직렬화한다.

멤버십 writer는 Project 잠금 후 현재 권한과 마지막 owner 수를 다시 검사한다. 다른 프로젝트의 구성원/권한 조회는 같은 403으로 거부한다. 보관 프로젝트는 실행 불가로 표시하되 활성 owner의 재활성화 경로를 유지한다. 자원 제공 변경은 Node→Capability 잠금 후 열린 제공 이력을 다시 읽고 이전 구간을 닫는다. Workspace 도구 선택은 선택 Node의 검증된 관측이 없으면 준비 상태 unknown을 반환한다. Control Plane PC의 CLI 설치 상태는 원격 Node의 실행 가능 증거가 아니다.

## DB 이력과 후속 경계

Gemini가 사용할 응답 키는 추정하지 않는다. 업무 `GET /v1/projects`는 `projects[]/count`, 생성 응답은 `projectId`, Workspace 목록은 `workspaces[]/count`, Workspace 식별자는 `workspaceId`다. kernel Run 목록은 `items[]/nextCursor`, 생성 응답은 `runId/state/version`이다. 사업체 project role의 canRequest와 kernelLinked/kernelEnabled 및 Node 실행 가능량은 별도 조건이다. 새 Run 생성은 draft이며 실행 시작 메시지를 만들 근거가 아니다. 첫 실행은 ADR-063의 실제 snapshotBase64/고정 입력·start/prepare·새 승인·start/enqueue를 따른다. 실행자 ID는 검증된 토큰에서 정하며 UI requestedBy 값을 신뢰하지 않는다.

과거 `0025_workspace_start`와 `0024_project_kernel_link→0025_workspace_tool_choice`는 수정하지 않는다. `0026_business_start_merge`에서 합치고 `0027_business_api_guards`로 권한/tenant 함수 수정을 적용한다. 운영 downgrade 대신 검증된 backup 복원과 forward fix를 사용한다. 원래 branch 어느 쪽에서 출발해도 통합 head에 도달해야 한다.

이 통합은 운영 IdP 설정·사용자/프로젝트 provisioning 자동화·Workspace 파일 준비·도구 원격 실행을 대신하지 않는다. public ResourceOffer와 kernel inv.resources 제공량의 운영 연결, 사용자 업무의 결과/로그/다운로드 API, 실제 UI 인수는 Claude/Gemini 후속 작업이다. 원격 프로필 설치 및 실제 2-PC 시험은 [[2026-09-11_REMOTE-WORKSPACE_다른PC설치안내]]의 별도 인수 범위다.
