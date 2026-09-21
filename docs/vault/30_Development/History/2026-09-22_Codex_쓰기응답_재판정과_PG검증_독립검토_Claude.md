---
doc_id: "CLAUDE-REVIEW-WRITE-RESPONSE-FOLLOWUPS-PG-001"
title: "독립검토 — Codex 쓰기응답 재판정(목록 닫기=부재 주장)과 PG 실측(건너뛰기 거동). 두 주장 성립, 잔여는 CI 개방 의존"
version: "1.0.0"
status: "review-done"
author: "Claude"
reviewer: "Codex(작성자)"
subject_commits: ["ce3ea282", "7f0fbdf3", "f0a96dc8(결속)", "945496234f(Claude 재판정 기준)"]
reviewed_at_tip: "acdb6225 (origin/integration; 세션 중 이동)"
executed_at_tip: "b3a14db6 (vw clean, 비-DB 계약시험 직접 실행)"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["independent-review", "write-response-contract", "absence-claim", "postgres", "silent-skip", "revive", "green-vs-reached"]
---

# 독립검토 — 쓰기응답 재판정과 PostgreSQL 실측

Codex는 작성자 실행이라 명시했고 독립검토를 인계했다. 두 초점(사용자 지정)을 origin/integration 착지본에서 내 손으로 확인했다. 검토는 diverged 워크트리가 아니라 origin 참조로 읽었다([[judge-integration-files-from-origin-not-worktree]]).

## 초점 1 — 목록을 닫은 근거(부재 주장) : **성립**
Codex 규칙 = 응답의 값이 다음 요청의 대상·입력·경로를 정하는 새 id·handle·전이집합·경로를 내는가. `src/saintvision/api/v1/*`의 **모든 쓰기 라우트를 전수로 직접 읽어** 규칙을 적용했다(표를 믿지 않고 각 return 본문 확인).

- **결속됨(gap 아님)**: POST /nodes(NodeEnrollResponse), admission(DiscoveryAdmissionResponse), POST /pools(PoolCreatedResponse·새 poolId지만 이미 결속), pool member put/delete, placement-preview, distributed-plan, POST /projects(ProjectCreateResponse), POST /workspaces(WorkspaceSummaryResponse), member role, workspace status(WorkspaceStatusResponse·allowedNext), resource-offer, POST /storage/contributions(ContributionRegistrationResponse).
- **미결속 10개 — 전부 새 후속 handle 없음 확인**:
  - heartbeat `{nodeId(요청경로),applied,heartbeatSequence}` · liveness-sweep `{markedLost,timeoutSeconds}` = 카운트/플래그.
  - decline `{announcementId(요청경로),state}` · member removal `{projectId,userId(요청),removed}` · activation/revoke `{contribution:_body}`(요청경로 id의 기존 필드 반향) = 수령증.
  - **user status `{userId,status}` · project status `{projectId,status}` = 전이집합(allowedNext) 없음** — workspace-status가 HIGH였던 바로 그 요소가 없다(핵심 구분).
  - **announce `{accepted,state}` — announcement_id 미반환.** 새 candidate id는 만들어지나 **읽기 `GET /discovery/candidates`가 handle을 제공**하고 admission/decline은 그 id를 경로로 받는다. 쓰기 응답이 handle을 안 내므로 결속해도 보호할 대상이 없다(비자명 사례, 정확).

**판정**: 선재 미결속 HIGH는 NodeEnroll(새 nodeId)·ContributionRegistration(새 contributionId+normalizedPath) 둘뿐이 맞다. Codex의 하위 분류도 규칙에 맞다. Codex가 눈에 띄는 것만 본 게 아니라는 증거: status 전이집합 구분, announce의 read-served handle 구분, **idempotency replay가 저장 dict를 반환해 생성자 검증을 우회하던 비자명 gap 발견**.

**경미 잔여(하위 우선순위, Codex 판정과 일치·위험 아님)**: 미결속 쓰기는 raw dict 반환으로 response_model 부재(계약 드리프트 위생). 특히 activation/revoke의 `_contribution_body`는 **등록 시엔 검증되나 그 두 라우트에선 미검증**(비대칭). workspace-tool은 미결속 중 본문이 가장 풍부(choice+usability, 잔여=표시 정확도). 다음 결속 후보이나 후속-handle 위험은 아님.
**범위 경계**: 이 sweep은 saintvision /v1 쓰기면(재판정 대상). 커널/control-plane 쓰기면은 별도 계약 트랙.

## 초점 2 — PG 시험이 다른 환경에서 무엇을 하는가(조용한 건너뛰기 우려) : **보호가 견고히 배선됨(일회성 실측 아님)**
사용자 우려 = 컨테이너 없는 곳에서 조용히 skip하면 시험이 아니라 Codex의 한 번짜리 실측이다. **설계상 조용한 skip이 green으로 통과 불가**:

- `tests/conftest.py::test_admin_dsn`: 로컬 DSN 부재 → `pytest.skip(사유 명시)`; **CI 부재 → `pytest.fail("CI requires INV_TEST_ADMIN_DSN")`**. 문서: skip은 not_run, never pass. 로컬 사유는 pyproject `addopts="-ra"`로 **화면에 보인다**([[skip-inherits-the-guard-fail-provided]]·[[passing-but-never-reached-trap]] 형태를 막음).
- `.github/workflows/backend.yml`: 실 `postgres:16` 서비스 + `INV_TEST_ADMIN_DSN` 제공 → 시험 **실행**. pytest 호출에 `-m "not postgres"` **없음**(docker_host만 배제) → 수집. `tests/test_api.py`는 sibling-import 없어 node-dependent/ignore 아님 → 포함. 주석: "Without it the suite would skip and report a false green."
- **이중 반-거짓초록 가드**: (1) conftest CI-fail, (2) 마지막 스텝이 junit에서 `.//skipped` 발견 시 build fail("Backend tests must not be skipped").
- **시험 자체가 무게를 진다(실행 시 진짜)**: node DB 거부 = `_node_body`에 unexpected 주입 → `pytest.raises(ResponseValidationError)` + **owner_engine으로 node row 실제 커밋 확인**(mock 아닌 실 PG 경로). idempotency replay = **durable `idempotency_records` 행을 UPDATE로 오염(rowcount==1)** 후 같은 키 재요청으로 replay 경로 태워 `pytest.raises(ResponseValidationError)`. 앵커 제거 시 둘 다 깨짐(Codex 되살림 주장과 일치).

**내가 직접 실행/확인한 것**: 비-DB 계약시험 `tests/core/test_write_response_contracts.py` **33 passed**(vw clean b3a14db6, 메인 .venv python) + 그 거부시험이 fixture에 unexpected/`status="made-up"` 주입 후 **`status_code==500` 단언** = response_model 없으면 깨지는 구조(무게 확인). 착지 라우트에 두 앵커 존재 확인(nodes.py:49, storage.py:68).

**정직한 경계(내가 못 한 것)**:
- **CI 실제 가동 여부는 세션 내 확인 불가**(gh 미인증) [측정불가/외부조회 필요]. 프로젝트 기록(§5)은 CI 미개방(결제 대기=사용자 결정 ①). 즉 **오늘 이 PG 시험은 Codex의 일회용 컨테이너로만 실행**됐고, CI가 열리면 매 push마다 자동 실행된다. 보호는 **트리에 배선·무장돼 있고 첫 CI 실행에서 발화**한다 — "보호가 사라졌다"와는 다르다. Codex도 "작성자 실행이며 CI/독립검토 아님"으로 정직히 표시.
- **DB 경로 실행·되살림은 이 호스트에서 못 함**(PG 컨테이너 부재). 앵커 제거 되살림 시도는 classifier가 차단(앵커 제거=계약 무력화로 보임) → 무게는 **단언 구조 열람**으로 확인(위). DB-경로 되살림(앵커 제거→DB 시험 실패)은 Codex 문서 기록에 의존.

## 결론
두 Codex 주장 모두 독립검토로 성립. **수정 필요한 결함 없음.** 유일한 실질 잔여는 **CI 개방(사용자 결정 ①)** — 그 전까지 PG 시험의 자동 강제는 없고 재실행은 PG DSN 수동 제공이 필요하다(Codex가 이미 정직히 라벨). 경미 계약위생 잔여(미결속 쓰기 raw dict, activation/revoke 비대칭)는 하위 우선순위로 유지.

관련: [[2026-09-21_이어가기_상태와규칙_Claude]] · [[skip-inherits-the-guard-fail-provided]] · [[passing-but-never-reached-trap]] · [[empty-output-is-not-evidence]] · [[검증규칙과_세축_canon]]
