---
doc_id: "HST-PROBLEM-DETAILS-001"
title: "ProblemDetails backend anchor와 NodeStopReceipt 이름 경계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
created: "2026-09-21T18:51:00+09:00"
updated: "2026-09-21T18:51:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["api-contract", "problem-details", "type-drift", "verification"]
---

# ProblemDetails backend anchor와 NodeStopReceipt 이름 경계

## 판정과 변경

`ProblemDetails`의 생성 경계는 Codex 소관이다. `services/control-plane/src/inv/app.py:problem`은 DomainError·HTTP 오류·FastAPI 입력 오류뿐 아니라 동시성 슬롯 포화(429)와 middleware 내부 오류의 공통 응답 생성점이다. 각 route에 중복 검사를 두지 않고 이 함수에서 `validate_contract("ProblemDetails", body)`를 실행해 모든 오류 응답 경로에 backend anchor를 추가했다. 오류 detail은 schema의 1000자 상한으로 제한하며 검증 오류에는 원 입력값을 넣지 않는다.

프런트 `ProblemDetails`는 기존 수기 선언 대신 `packages/contracts-ts` 생성 타입을 참조한다. `apiClient`의 로컬 통신 실패와 JSON이 정본 shape가 아닌 응답은 정본 `about:blank` 모양으로 정규화하며, 필수 nullable `causeRef`와 `evidenceId`를 포함한다. 공유 fixture를 backend 계약 시험과 Ajv 시험이 함께 읽는다.

이름 충돌은 개념 드리프트가 아니다. `contracts/v1alpha1/core.schema.json`과 생성 패키지의 `NodeStopReceipt`는 내부 wire claim이다. 기존 `apps/web` 선언은 화면에서 소비하는 물리 정지 증거 투영이다. 정본 wire 이름은 유지하고 프런트 선언·소비 참조를 `NodeStopReceiptView`로 바꿨다. 거버넌스 규칙에 wire 이름은 wire 의미에만 쓰고 화면 투영은 `View`/`Projection` 접미사를 쓰도록 추가했다. 화면 표시나 API 의미는 바꾸지 않았다.

## 검증 기록

아래 시험은 Codex가 dirty source를 사용해 직접 실행했다. 당시 checkout은 `agent/codex/problem-details-contract`, HEAD `2c473f4637a05bba59562b3a6a75cdb340a55f29`, integration과 동기화 상태였으며 구현 파일은 아직 미커밋이었다. 정확한 provenance header의 명령·exit code·환경은 해당 실행 시점 출력에 기록됐다.

| KST | 명령 | 결과 | 실행 범위 |
|---|---|---|---|
| 18:48:02 | `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe -m pytest tests/core -q` (`PYTHONPATH=services/control-plane/src`) | exit 0; 715 passed, 4 skipped, 0 failed, 0 errors | 1 DSN 부재, 1 launcher prerequisite 부재, 2 opt-in local image 부재로 이유가 보이는 skip |
| 18:52:58 | `npm test` (`apps/web`) | exit 0; 52 files, 470 passed | 전체 Vitest; browser/실 HTTP 인수 아님 |
| 18:52:41–18:52:52 | `npm run build` (`apps/web`) | exit 0 | `tsc -b`와 Vite production build |
| 18:51:53–18:51:54 | `python tools/export_schemas.py --check`; `npm --prefix apps/web run contracts:check` | 둘 다 exit 0; 41 schema와 15 API 응답 타입 동기화 | 변경 없는 생성 산출물도 drift 없는지 확인 |
| 18:51 | `python tools/check_docs.py`; `python tools/check_ontology.py` | 둘 다 exit 0; 문서 629개, ontology/SHACL checks 통과 | 이력·진행판·거버넌스 링크 및 task mapping 검사 |

새 Python 시험은 실제 middleware의 503 오류와 강제 포화 429 오류에서 공통 validator가 호출되는지 spy로 확인하며, 장문 detail이 계약 상한 아래로 잘리는지도 검증한다. validator 호출을 제거한 되돌림 대조에서는 spy 단언이 실패했고 복원 후 통과했다. 프런트 계약 시험은 shared JSON fixture를 canonical JSON Schema로 검사하고 nullable required 필드 제거를 거부한다. 추가 API client 대조는 canonical 응답, text 실패, malformed JSON, 비정본 JSON을 다룬다. 해당 변경에서 full Vitest 최초 실행은 integration보다 2 commit 뒤진 `d0d41c3` tree에서 RunLogView DOM 시험 6개가 실패했다. 최신 `2c473f4` integration으로 fast-forward한 뒤 같은 영역이 포함된 전체 Vitest가 통과했으므로 stale-tree 결과는 제품 회귀로 집계하지 않았다.

## 범위와 남은 검토

- 독립 리뷰는 아직 받지 않았다. 구현자 Codex의 실행은 Claude 독립 검토를 대체하지 않는다.
- PostgreSQL integration은 DSN이 없어 실행하지 않았다. backend 계약 anchor와 FastAPI 단위 경로 검증은 DB 없이 실행됐다.
- 화면 동작 수정은 없다. 전체 Vitest와 타입/빌드는 통과했지만 실제 브라우저 인수는 주장하지 않는다.
- CI 실행·배포된 HTTP 경계·장비 인수는 별도다.
- `NodeStopReceiptView`는 기존 화면 projection의 이름을 명확히 했다. 실제 wire-to-view 매핑의 추가 검증이나 화면 의미 변경은 별도 UI 카드 범위다.

다음 담당자: Claude가 고정 SHA를 독립 검토한다. Gemini 화면 소유권은 바뀌지 않는다.
