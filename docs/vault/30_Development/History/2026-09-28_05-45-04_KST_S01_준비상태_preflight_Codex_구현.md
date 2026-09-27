---
doc_id: "HIST-CODEX-2026-09-28-S01-READINESS-PREFLIGHT"
title: "S01-BE·S01-ST 준비 상태 preflight 수집기 구현"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T06:12:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf045c5a554209aaef601ae4883b64da50a7"
implementation_sha: "15f84413"
task_ids: ["S01-BE", "S01-ST"]
tags: ["S01", "preflight", "read-only", "redaction", "evidence"]
---

# S01-BE·S01-ST 준비 상태 preflight 수집기 구현

## 착수와 범위

[[2026-09-22_21-55-00_KST_review_done_차단지도_Codex]]의 S01-BE·S01-ST 행과
[[S02_선행입력_체크리스트_2026-09-22]] §7을 기준으로 Card 35를 base `1e8baf04`,
branch `agent/codex/s01-readiness-preflight`, owner Codex/reviewer Claude로 시작했다.
S01 상태·registry·공개 계약은 변경하지 않고, 입력 U1~U6이 들어왔을 때 한 번 실행할
읽기 전용 수집기와 1쪽 설계만 추가했다.

## 구현

- `tools/s01_readiness_preflight.py`는 health unresolved setting, readiness, 실토큰/무토큰
  session 경계, pilot CA→등록 Node leaf 체인, DNS, S01 inventory lint, pilot PG capability
  대조를 수행한다.
- inventory는 5 Node의 식별·OS·CPU/GPU/storage/network·허용 자원/절대 폴더·NTP·인증
  값을 정본 단위로 검사한다. 값이 없으면 `BLOCKED`, 제공된 값이 잘못됐거나 관측과
  다르면 `FAIL`이며 `FAIL > BLOCKED > PASS`로 U1~U6을 집계한다.
- HTTP는 GET만, pilot DB는 `REPEATABLE READ READ ONLY`·2초 timeout·tenant local scope의
  SELECT만 사용한다. token/DSN/URL/hostname/IP/Node·tenant ID/fingerprint/path/인증서와
  예외 원문은 JSON에 넣지 않는다. 기존 output은 관측 시작 시 삭제한다.
- 구현 commit은 `c959e158`이다. LAN state·serve/observe·heartbeat·인증서·DB row는
  변경하지 않았다.

## 검증

| 명령/관측 | 결과 |
|---|---|
| `pytest tests/test_s01_readiness_preflight.py -q` | 23 passed, exit 0 |
| `py_compile` + CLI `--help` + `git diff --check` | 각각 exit 0 |
| `pytest tests/test_route_coverage.py -q` | 39 passed, exit 0 |
| `check_docs.py` | 894 documents, exit 0 |
| `check_contract_bindings.py` | 54 fixtures·19 types·25 sites·14 guards, exit 0 |
| `check_frontend_integrity.py` | 9 rules, 0 violations, exit 0 |
| `check_ontology.py` | 48 task mappings, exit 0 |
| `check_doc_single_source.py --ratchet` | 18 pairs, exit 0 |
| `check_response_freshness.py` | advisory 10/10, exit 0 |
| `sync_obsidian.py --check` | 1734 managed·4 pending export·0 conflict, exit 0; read-only |

현재 dev API/LAN state 예비 실행은 redacted JSON만 남겼다. API가 응답하지 않아 HTTP
3건은 `FAIL`, 실 inventory·access token이 없어 나머지 4건은 `BLOCKED`, exit 1이었다.
실값을 합성하지 않았고 이를 S01 합격으로 세지 않는다. inventory가 없으므로 pilot PG를
조회하지 않았으며, DB 경계는 PG-free fake connection 시험으로 read-only SQL 순서와
redaction을 고정했다. disposable 실 PG는 필요하지 않아 실행하지 않았다.

## 남은 것과 인계

Claude는 구현 SHA의 입력 누락/오류 구분, stale evidence 제거, secret redaction,
read-only SQL과 certificate identity 결속을 독립 검토한다. 사용자 U1~U6가 준비되면
보호 inventory와 실토큰 환경변수로 재실행하고, 그때의 PASS/FAIL/BLOCKED JSON을 S01
인수 증거로 연결한다. Storage SHA-256 왕복·retention/GC·독립 검토·운영 인수와
S01-BE/S01-ST `done` 판정은 이 카드에서 수행하지 않았다.

## Claude 수정 요청 반영

PR #122 독립 검토의 차단 6건을 구현 `15f84413`에서 보정했다. inventory의 명시적
`null`은 invalid나 PASS가 아니라 missing/BLOCKED로 집계한다. output은 unlink 전에
inventory·Node/HTTP CA·state 전체 하위와 겹치는지 검사한다. pilot leaf는 제품
`certificate_identity`를 직접 재사용해 정확한 nodeId/epoch SPIFFE URI, `SERVER_AUTH`,
`ca=false`, 유효한 CA와 fingerprint를 검사하며 5대 미등록은 BLOCKED다.

`/v1/health`는 inv.app의 `/readyz`·`/v1/session`과 다른 표면이므로 `--health-url`로
분리했다. Node CA와 HTTP TLS CA도 분리했고 실토큰의 평문 HTTP 전송은 거부한다.
`nodes:null`은 예외 대신 BLOCKED로 판정한다. focused 시험은 실제 pilot 형식 leaf 5장,
1/5 BLOCKED, 잘못된 SPIFFE, DNS PASS/FAIL/BLOCKED, 보호 경로 선검증, PEM과 `main()` 종단
redaction을 포함해 23 passed다. PG 대조는 DB 정본에 있는 CPU/RAM/profile/cert만 다루며
GPU/NTP DB 일치는 이 카드가 주장하지 않는다.
