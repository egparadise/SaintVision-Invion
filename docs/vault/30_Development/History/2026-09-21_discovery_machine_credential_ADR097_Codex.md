---
doc_id: "DISCOVERY-MACHINE-CREDENTIAL-IMPLEMENTATION-CODEX-001"
title: "ADR-097 discovery credential issuer implementation and verification"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "pending"
updated: "2026-09-21T21:06:00+09:00"
source_of_truth: "Git"
tags: ["discovery", "credential", "security", "evidence"]
---

# ADR-097 임시 운영자 CLI 구현 기록

## 결정과 범위

2026-09-21 KST 사용자 결정으로 ADR-097을 Proposed에서 Accepted로 바꿨다. 임시 issuer는 operator CLI이고, tenant/installation별 발급 권한은 지정된 운영자에게 둔다. 장기 protected API는 열린 결정으로 유지한다. DB 관리자가 이름이 지정된 운영자 PostgreSQL login에만 `inv_discovery_issuer` 멤버십을 부여하며 CLI는 이 멤버십을 확인하고 작업 transaction 안에서 전용 `NOLOGIN` role로 전환한다. DB role은 최소 권한으로 tenant ID 조회, credential 발급·폐기, 감사 이벤트 기록만 할 수 있고 digest를 읽을 수 없다. 이 role은 현 구현에서 cross-tenant 운영 권한을 가지므로 승인된 소수 운영자에게만 부여해야 한다.

토큰은 `dsc1_` + 256-bit random이고 SHA-256 digest만 저장한다. CLI 사전 확인은 기본 동작이며 쓰기에는 `--apply`가 필요하다. 발급은 TTY stdout이 아닌 경우 거부하고 transaction commit 후 bearer 원문을 한 번만 출력한다. 원문은 argv, DB, audit, 앱 로그, 진단 메시지에 쓰지 않는다. TTL은 15분, linked candidate 공지 간격은 30초다. 같은 설치에 재발급하면 이전 활성 grant를 회전 폐기하고, 운영자는 tenant 및 non-secret credential ID로 명시 폐기할 수 있다. admission/decline 시 연결 grant가 폐기되며 만료는 서버 검증에서 거부된다. 이벤트에는 actor/tenant/install/credential ID/type/outcome/reason/time만 기록한다.

## 실제 PostgreSQL 및 API 실행

- 소유 확인: 최종 통과 실행 컨테이너 이름 `sv-discovery-adr097-b14efe7dfd02`, 라벨 `ai.saintvision.codex.discovery-adr097=sv-discovery-adr097-b14efe7dfd02`; PostgreSQL 16 임시 컨테이너, 768 MiB 메모리 제한, 데이터 디렉터리는 tmpfs, 랜덤 비밀번호는 PowerShell 메모리의 환경변수에만 사용했다. 2026-09-21 21:00 KST 실행 직전 Docker Server 20.10.22 응답과 호스트 가용 RAM 1,412,576 KiB를 확인했다. Docker가 컨테이너를 시작하고 PostgreSQL readiness probe가 성공했다. 소유 라벨/이름을 다시 확인한 뒤 컨테이너 제거 및 제거 후 inspect 부재를 확인했다. DB DSN이나 비밀번호는 보고서에 기록하지 않았다.
- CLI/E2E 시험 명령: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe -m pytest -q --tb=short tests/integration/test_discovery_machine_credentials.py`; 최종 disposable PostgreSQL run `3 passed`, exit 0. 경로는 issuer-role dry-run → issue/DB digest 확인 → API HTTP successful announce → linked candidate refresh → admission/automatic revoke → CLI explicit revoke/idempotency → HTTP 403이었다. 별도 경우로 다른 tenant header, installation 불일치, 만료 grant, revoked grant는 403/no candidate였고, issuer 멤버십 없는 실제 PostgreSQL login은 발급 거부 및 0 credential write였다.
- 최종 provenance-wrapped 실행은 2026-09-21 21:00:30 KST에 최신 migration/권한 코드, 일반 API의 discovery bearer 거부 assertion까지 포함한 상태로 실행했다. HEAD 당시 `462304bbf4f7d0fdce7c3ee4ee10cd9d8224698e`, branch `agent/codex/terminal-pty-contract`, worktree `C:/Project/SaintVision-Invion/.worktrees/codex-terminal-pty-contract`, Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6, Docker present, PostgreSQL test DSN set only for test duration, Go absent; dirty worktree, origin integration last-fetched `099742e8e3f5` 대비 behind 9/ahead 1. Wrapper exit 0, terminal result 3 passed/7 warnings. Provenance가 test-start 환경 게이트와 실제 interpreter를 함께 기록했다.
- Unit/migration/tenant-boundary/response-contract command `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe -m pytest -q tests/core/test_discovery_announcement_tenant_boundary.py tests/core/test_discovery_credentials.py tests/core/test_discovery_response_contract.py tests/test_migrations.py`는 provenance wrapper에서 2026-09-21 20:56:21 KST, exit 0, 40 passed/2 warnings였다. `tools/check_docs.py`와 `tools/check_ontology.py`도 exit 0. Obsidian sync는 9개 문서를 export한 뒤 `--check`에서 1439 managed/0 pending/0 conflict를 확인했다.
- 최종 보안 정정 반영 후 `check_docs.py`, `check_ontology.py`, `git diff --check`가 모두 exit 0이고 focused Python suite가 40 passed/2 warnings다. Obsidian sync는 마지막 3개 변경 파일을 export한 뒤 1439 managed/0 pending/0 conflict를 재확인했다.
- 첫 실행은 테스트의 secret-absence assertion이 의도된 one-time stdout 공개까지 금지하여 1 failed였다. 검사를 발급 stdout에 정확히 한 번만 있고 오류/후속 명령에 없는 것으로 수정한 다음 위 실행을 통과시켰다. 실패 덤프의 one-time 값은 테스트용 일회용 DB에서 나온 합성 토큰이며 운영 자격증명이 아니다. 값은 이 기록에 옮기지 않았다.
- mutation 대조: `validate_discovery_grant`의 tenant 비교만 제거 → tenant-mismatch 단언이 `DID NOT RAISE`로 실패(1 failed, 4 passed); 만료 비교만 제거 → expired 단언 실패; revoked 확인만 제거 → revoked 단언 실패. 매 대조 뒤 원래 한 줄을 복구했다. 이어 Python focused suite를 다시 실행해 40 passed, 2 warnings, exit 0을 확인했다.
- focused Python 명령은 `tests/core/test_discovery_announcement_tenant_boundary.py tests/core/test_discovery_credentials.py tests/core/test_discovery_response_contract.py tests/test_migrations.py`를 대상으로 했다. `tools/provenance.py` 실행 기록: 기준 SHA `462304bbf4f7d0fdce7c3ee4ee10cd9d8224698e`, branch `agent/codex/terminal-pty-contract`, worktree `C:/Project/SaintVision-Invion/.worktrees/codex-terminal-pty-contract`, interpreter `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` / Python 3.14.6, Node v24.17.0, Windows 11, KST `2026-09-21T20:49:19+09:00`, executor Codex, check invocation 시 PostgreSQL DSN absent/Docker present/Go absent/Node present, command exit 0. 당시 tree는 dirty였고 branch는 마지막 fetch의 origin integration SHA `5ea8ba32ac98` 대비 behind 7/ahead 1이었다.

## 경계 및 남은 확인

이 E2E는 실제 PostgreSQL과 FastAPI HTTP TestClient를 통과했지만 실제 `inv-discover` executable, 조직이 승인한 보호 전달 채널, 물리 Node 환경변수 주입, human-operated approval UI, one-time enrollment exchange, node mTLS까지 실행한 것은 아니다. `go` compiler가 이 호스트에서 제공되지 않아 Go build/test는 실행할 수 없었다. 따라서 issue-to-HTTP-announcement 기능 경로는 복구됐으나 실제 노드 전체 온보딩 운영 인수는 미완료다. 승인된 조직 전달 채널을 운영자가 확보하지 못하면 새 노드는 계속 차단된다.

Node operator instructions: `[[Codex Node와 저장소 Adapter 실행 안내]]`. Decision record: `[[2026-09-21_Discovery_기계자격증명_최소권한_계약제안_Codex]]`.

## Post-run harness redaction correction (2026-09-21 21:04 KST)

The first failed integration assertion caused pytest to render captured stdout, including a synthetic bearer for the disposable database, into the test output in this conversation. The DB container has been removed and the 15-minute credential has expired; this was not an operator or production credential. The raw value is absent from repository files and durable docs, but the already emitted conversation output cannot be retroactively erased. The test assertions now use a helper that reports only a constant failure message if a bearer is found. The product code was unchanged after the 21:00 PostgreSQL run; the latest test-only output-sanitizing edit could not be rerun against PostgreSQL because the 21:04 RAM preflight measured 645,764 KiB, below the 1 GiB safety floor. No test container was started. `py_compile`, collection of all three integration tests, and the non-database 40-test focused suite passed afterward.
