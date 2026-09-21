---
doc_id: "CODEX-WRITE-RESPONSE-BINDING-001"
title: "고위험 쓰기 라우트 응답 계약 결속"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "pending"
updated: "2026-09-22T00:09:30+09:00"
source_of_truth: "Git"
tags: ["api", "response-model", "contracts", "provenance"]
---

# 고위험 쓰기 라우트 응답 계약 결속

## 범위와 판정

시작 기준은 통합 tip `f14f4c07427a8803ed8850d9490b378e8506d0eb`이며, 작업 브랜치는 `agent/codex/write-response-contract`의 격리 worktree다. Claude의 위험도 목록 `7d75f810`을 현재 소스와 대조하고, HIGH 중 상위 네 경로를 골랐다. 프로젝트 생성, discovery 후보 admission, 멤버 역할 변경, capability 제공량 변경이다. 네 경로 모두 상태 변경 후 JSON body를 반환했으나 FastAPI `response_model`이 없어 응답 계약이 서빙 경계에서 강제되지 않았다.

## 시각 스큐 규격 드리프트 결정

커널 소스에서 `clock_skew_seconds` 부재·비유한 값·절댓값 5초 초과 노드가 scheduler, placement, lease, containment 및 readiness 적격성에서 제외되는 것을 확인했다. 이 런타임 안전 필터를 되돌리지 않는다. 필터를 되돌리면 시간 측정값이 불명확하거나 큰 스큐를 가진 노드가 자원 배정·실행 경로에 진입할 수 있다.

대신 거버넌스 문서에 구현 현실을 추가하되 ERR-DESIGN-007 전체를 Accepted로 바꾸지 않았다. ±5초는 파일럿 장비로 보정되지 않았고 NTP 전제, 운영 알림 채널 및 대응 담당도 정해지지 않았다. 따라서 런타임 적격성 필터는 유지하고 GOV-ALERT-001의 라우팅 알람은 계속 `governanceGated`다. `alarm_check.py`의 gated reason과 해당 테스트도 이 차이를 명시한다. 이는 문서·소스 검토 판정이며 실장비 스큐 측정이나 알람 전달 실험이 아니다.

## 응답 형태 측정과 구현

기존 서비스 반환 코드를 확인해 필드·타입·nullable 동작을 정했다.

- `POST /v1/projects`: `project_body`가 `projectId`, `code`, `displayName`, `status`, `memberCount`, ISO `createdAt`, `kernelLinked`, `kernelEnabled`를 반환한다. `kernelNote`는 커널 링크 상태에 따라 누락되거나 문자열이므로 선택적 nullable이다. 목록 GET 모델은 `roleCode`·권한 투영이 포함돼 생성 응답과 같지 않아 재사용하지 않았다. `response_model_exclude_unset`으로 기존의 조건부 누락을 보존했다.
- `POST /v1/discovery/candidates/{id}/admission`: announcement ID, 한 번만 반환되는 synthetic fixture 용 bootstrap token, 만료 시각, 다음 행동 문구를 반환한다. 실제 발급 비밀은 fixture나 기록에 넣지 않았다.
- `PUT /v1/projects/{id}/members/{user}`: `set_member_role`은 사용자를 확인하고 membership을 생성/갱신한 뒤 유효 권한을 다시 읽는다. 그 경로에서는 `roleCode`와 `userStatus`가 nullable이 아님을 코드 흐름으로 확인했다. 권한 세 boolean도 엄격한 boolean이다.
- `PUT /v1/capabilities/{id}/offer`: 실제 반환 builder의 canonical offer 값, 직전 제공량, 적용 결과, kernel 자원/용량 및 이유를 반영했다. 이전 제공량·kernel 자원 ID·용량·이유 코드는 반환 경로에서 null일 수 있고 `kernelReason`은 일부 결과에서 생략된다. `response_model_exclude_unset`으로 조건부 필드 생략을 보존했다.

신규 Pydantic 모델은 `StrictBool`·`StrictInt`·`StrictFloat`·`StrictStr`를 사용한다. 초기 시험에서 Pydantic의 기본 coercion이 문자열 `"yes"`를 boolean으로 받아들이는 것을 확인해, 고위험 응답에서 타입이 바뀌어도 변환되어 통과하지 않도록 했다. 모델에서 생성한 JSON Schema 네 개와 synthetic fixture 네 개를 추가했다.

## 실행 근거

`tests/core/test_write_response_contracts.py`는 각 경로에 대해 (1) fixture가 strict 모델을 통과하고, (2) FastAPI TestClient가 정상 body를 계약 모양 그대로 반환하며, (3) 서비스 응답에서 타입 위반이 나면 HTTP 500으로 거부되는지 검사한다. 선택적 `kernelNote` 누락, 실제 nullable offer 필드, 멤버 경로에서 허용되지 않는 null도 별도 고정했다.

작성자 실행:

- Interpreter: `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe` (Python 3.14.6)
- `python tools/export_schemas.py` — exit 0, 45개 schema 생성
- `python -m pytest -q tests/core/test_write_response_contracts.py tests/core/test_workspace_response_contract.py tests/test_alarm_check.py` — exit 0, 51 passed (2 third-party deprecation warnings)
- Mutation check: temporarily removed all four `response_model` declarations and ran `-k refuses_invalid_service_response`; exit 1 with precisely 4 failed / 14 deselected because all malformed outputs returned 200/201. Restored all declarations and re-ran the 51-test focused command successfully.
- `python tools/export_schemas.py --check` — exit 0, 45 schemas 일치
- 환경: Windows. 이 시험은 mock 서비스 body를 FastAPI 응답 직렬화 경계로 보내며 DB 통합 실행이 아니다.

테스트에서 유효한 경로와 타입이 잘못된 반환이 각각 성공/거부되는 것을 실행 확인했다. 네 response_model 제거 변형은 각기 malformed response를 200/201로 통과시켜 4개 negative test를 전부 실패시켰고 복원했다. 독립 검토·호스티드 CI·PostgreSQL 상태 변경 경로는 대기다. 특히 FastAPI가 반환 dict의 미선언 추가 필드를 오류로 내기보다 response model에서 걸러내는 동작을 확인했다. 현재 negative control은 그와 혼동하지 않고 누락/잘못된 타입을 사용한다.

## 다음 행동

1. reviewer가 통합에 착지된 고정 SHA에서 4개 write route 모델과 정상/위반 경로를 독립 검토한다.
2. 다음 MED-HIGH 후보는 workspace status, user status, storage contribution, node enrollment이며 같은 서비스 반환 측정과 positive/negative route 시험 후 결속한다.
3. ERR-DESIGN-007의 ±5초는 장비별 시계 자료를 모아 보정하고, 알람 채널·담당·대응절차가 정해진 뒤에만 라우팅 알람을 활성화할지 재결정한다.
