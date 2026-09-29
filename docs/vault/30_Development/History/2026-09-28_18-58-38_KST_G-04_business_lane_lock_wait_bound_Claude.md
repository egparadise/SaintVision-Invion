---
title: "G-04 business lane lock-wait bound 통일 (카드 84)"
version: "1.0"
status: "review"
author: "Claude"
updated: "2026-09-28T18:58:38+09:00"
---

# G-04 business lane lock-wait bound 통일 (카드 84)

branch `agent/claude/g04-lock-wait-bound`, base #201 head `9dfb2878`(#199·#191·#184 포함) + #196 head `5c7a773e` merge(`schemas.py` import·`projects.py` import union, 해소만). #191 Codex 비차단 지적(W2 `model_versions.py:60` "sets no lock_timeout or statement_timeout", `deps.py` advisory lock 대기 상한 없음)의 후속.

## 한 것

- `src/saintvision/api/lock_wait.py` 신설 — lane의 **단일** helper: `validate_lock_timeout`(1~600000 ms 정수, bool 거부), `bound_lock_wait`(`SET LOCAL lock_timeout = '<n>ms'`), `lock_wait_problem`(55P03·40P01 → `SYS-0001/503/retryable=true`, 고정 detail·값 비노출; 그 외 OperationalError는 전파), `bounded_lock_wait` context manager(둘을 묶음).
- 적용: W1 `run_seal.py`·W4 `model_retention.py`(각자의 사본 삭제), W2 `model_versions.py`(문서화된 gap → bound), #167 `model_release.py`(write tx에 bound; `Settings` 의존성 추가). `deps.serialise_idempotent_write` docstring: advisory lock은 heavyweight lock이라 호출자의 `lock_timeout`을 따름(자체 timeout 없음).
- `Settings.__post_init__`에서 `business_lock_timeout_ms` 검증(잘못된 값이면 기동 실패). `INV_BUSINESS_LOCK_TIMEOUT_MS`.
- **statement_timeout은 두지 않음**(판단): 대기가 아니라 작업 중인 문장을 끊어 느린 문장을 경합으로 위장한다. helper docstring에 결정으로 명시.
- migration 없음.

## 검증

- PG-free: `tests/core/test_lock_wait.py`(24) + W1·W4·W2·release harness(SET LOCAL 관측·55P03/40P01→503·기타→500) = 공용 `.venv`(3.14) 263 passed.
- 실 PG(hosted) `tests/integration/test_lock_wait_real_pg.py`(7): 독립 연결이 advisory lock(같은 키 파생) 또는 row `FOR UPDATE`를 쥔 상태에서 W2 register·W4 pin(row/key)·W1 seal(row/key)·#167 release가 300 ms 예산 안에 `SYS-0001/503/retryable` + 기록 0으로 끝남(요청 deadline 20 s: bound를 되돌리면 무한 대기 → deadline 실패); 503 뒤 같은 engine의 다음 쓰기가 정상 201(SET LOCAL이 pool 연결에 새지 않음).
- NOT_OBSERVED: deadlock(40P01) 실측(PG-free 분류만).

## 다음

Codex 검토(동시성) → hosted 인용. W3 route(#209 계약 확정 뒤)도 같은 helper를 쓴다.
