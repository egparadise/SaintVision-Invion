---
doc_id: "CLAUDE-INDEP-REVIEW-CODEX-CONTRACTS-001"
title: "독립 검토 — Codex ProblemDetails 앵커·NodeStopReceiptView·pool/placement/distributed 결속"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex(피검토)"
source_of_truth: "Git"
tags: ["independent-review", "codex", "ProblemDetails", "fixed-sha"]
---

# 독립 검토 — Codex 계약 작업

## 검토 트리 못 박기 (오늘 뒤처진 트리 오판 방지)
- 조사 시작 시 origin/integration = **`dff6223`**. 그 시점 실측: ProblemDetails 앵커·NodeStopReceiptView **integration에 없었고** `agent/codex/problem-details-contract`의 코드 커밋 **`3451880`**에만 있었다(미병합 확인).
- 검토 중 트리 이동: origin/integration = **`ac78bf8`**로 전진. `dff6223..ac78bf8`에 **3451880(ProblemDetails+receipt view) 병합** + **9728556(PTY ticket/WS auth, terminal)** 병합됨. 재확인으로 못 박음(보고 전). → ProblemDetails/NodeStopReceiptView는 **지금 integration에 있다**. 병합된 것이 정확히 `3451880` 동일 SHA라 아래 심층검토 그대로 유효.
- 인터프리터 `.venv/Scripts/python.exe`(3.14.6). ProblemDetails는 worktree(2f41851, 3451880 포함, 폐포 clean)에서, 나머지는 integration 워킹트리(ac78bf8)에서 실행.
- **PTY/terminal(9728556)은 검토 범위 밖**(사용자가 terminal=Codex 보안경계로 제외). 착지만 기록, 미검토.

## 직접 확인한 것 (실행·probe)
### ProblemDetails 앵커 (최고 위험 — 오류 경로, 깊이 집중)
- **단일 funnel**: `app.py problem(error, trace_id)`가 body 구성 후 반환 직전 `validate_contract("ProblemDetails", body)`. 예외 핸들러 DomainError/RequestValidationError/HTTPException + 미들웨어 내부오류가 전부 `problem()` 경유. `/readyz` 503(`{status:not_ready}`)은 헬스 응답이라 ProblemDetails 아님이 정당(우회 아님).
- **무게 짐 — 직접 돌연변이**: `validate_contract`가 causeRef/code/detail/traceId 제거를 전부 거부(내 probe). 커버리지 시험 `test_problem_contract_anchor_covers_domain_error_and_capacity_rejection`이 monkeypatch로 503·429 실경로가 둘 다 앵커 호출함을 단언(`validated==["ProblemDetails","ProblemDetails"]` + `application/problem+json`). **초록≠도달 아님 — 도달 확인.** 시험 **3 passed** 직접 실행.
- **detail 한계 정합**: 스키마 detail maxLength=1000 = 코드 `str(error.detail)[:1000]` 정확 일치. 1200자 입력 시 정확히 1000으로 절단됨(시험·probe 확인).
- **HTTPException code 안전**: 핸들러가 `DomainError("HTTP-0001", ...)`(정형)로 매핑 — "HTTP-404"(3자리→패턴 위반) 같은 위험 회피.

### NodeStopReceiptView (내가 드리프트 훑기에서 flag한 이름충돌)
- 프런트 `NodeStopReceipt`(UI 투영) → **`NodeStopReceiptView`로 개명**(주석 "distinct from the NodeStopReceipt wire contract"), 커널 wire `$def`는 NodeStopReceipt 유지 → 네임스페이스 분리로 **충돌 해소**. 참조 전부 갱신 확인.

### pool/placement/distributed/approval 결속 (integration ac78bf8)
- `test_pool_placement_response_contract.py`·`test_kernel_mutation_response_contract.py`·`test_run_approval_observation_contract.py`·`test_problem_details_contract.py` 직접 실행 **33 passed**.
- **무게 짐**: pool/placement 시험이 `test_contract_fixture_mutations_are_rejected`(필수필드 `pop` → `raises(ValidationError)`)로 음성대조. 6개 fixture(distributed-plan·pool-capacity·pool-created·pool-member·pool-member-removal·placement-preview) 전부 이 시험이 참조 — **고아 fixture 없음**.

## 보고로 수용한 것 (직접 재실행 안 함)
- run-approval: 이미 고정 SHA `7a9b500`(현 병합)에서 **심층 독립검토 완료**(별도 문서). 이번엔 시험 통과만 재확인.
- 거버넌스: `governance-rules.test.ts`(RFC 9457 ProblemDetails/ApiError + 승인 불변식) 읽음. `인계 계약` doc 존재 확인.

## 판정
검토 대상 전부 **sound**. 결함 0. 아래 저심각 노트 1건.

### 관찰 1 (저심각 하드닝 — 결함 아님): ProblemDetails 앵커의 새 실패 모드
`problem()`이 오류 body를 validate하므로, 만약 **비정형 코드**(`^[A-Z]+-[0-9]{4}$` 위반)의 DomainError가 어디선가 raise되면 `category=code.split("-")[0]`가 스키마 `^[A-Z]+$`를 위반해 **validate가 오류 핸들러 내부에서 throw** → 깨끗한 4xx가 미처리 500으로 전락. **라이브 트리거 없음**: 커널 DomainError 코드 92개 전수 조사 결과 위반 0. 즉 방어 강화 제안일 뿐. 권고: `problem()`이 validate 전 code/category를 정형으로 fallback 강제(예: 위반 시 "SYS-0001")하면 오류 경로가 **절대** 안 터진다.

### 관찰 2 (경미): governance-rules.test.ts 샘플의 `category:'SEC'` + `code:'GOV-0001'` 불일치 — 스키마 위반은 아님(category는 임의 대문자 허용, 백엔드는 code에서 category 유도). 테스트 샘플 정합성 정도.

관련: [[2026-09-21_수기타입_계약_드리프트_전수훑기_Claude]](NodeStopReceipt 충돌 최초 발견) · [[2026-09-21_run-approval-page-contract_독립검토_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
