---
doc_id: "HISTORY-20261001-CARD166-S04-SHARD-CANCEL-BRIDGE-CODEX"
title: "CARD-166 S04 shard parent/member cancel bridge 후속"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T10:40:20+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "73fa1274ce23e050bae60e4ee8228484b6316647"
task_ids: ["S04-DB"]
tags: ["card-166", "s04-db", "cancel", "shard", "audit", "real-pg"]
---

# CARD-166 S04 shard parent/member cancel bridge 후속

## 선택 근거와 범위

train 4d 후보 `73fa1274ce23e050bae60e4ee8228484b6316647`에는 PR #257의
normal cancel 제품 bridge와 hosted real-PG 17건이 들어 있다. 다만 설계 시험 7의
shard parent/member 경로는 PG-free 호출부 guard만 있고 real-PG fixture가 없어
`NOT_RUN`이었다. 외부 장비 없이 hosted PostgreSQL로 닫을 수 있는 CARD-160의 명시적
후속이므로 CARD-166으로 선택했다.

범위는 시험뿐이다. 공개 route·schema·ProblemDetails, migration 0056, bridge 함수와
제품 Python 호출부는 변경하지 않는다. S04-DB는 계속 `review`다.

## 구현

1. 실제 shard admission으로 child 두 개와 parent 한 개를 만들고 세 kernel run을
   business run에 결속한다.
2. child 하나를 요청 전에 kernel에서 cancel한다. parent cancel HTTP 한 요청은 남은
   child와 parent만 실제 전이하므로 그 둘만 public cancelled·audit 각 1건이고,
   선취소 child는 public draft·audit 0이어야 한다. 같은 key replay는 응답과 audit
   건수를 바꾸지 않는다.
3. SECURITY DEFINER 직접 호출 부정군에 viewer role, archived public project,
   disabled business project를 추가했다. 모두 SQLSTATE `42501`, public draft,
   audit 0을 요구한다.
4. 중복 잠금 guard는 `FOR SHARE` 한 문자열 대신 PostgreSQL row-lock 네 형태
   `KEY SHARE|SHARE|NO KEY UPDATE|UPDATE`를 정규식으로 검출한다. 의도된 public run
   최종 lock은 유지한다.

## 검증 상태

- `python -m pytest tests/core/test_kernel_cancel_bridge.py -q`: **21 passed**.
- `git diff --check`: exit 0.
- 로컬 기본 Python 3.10은 `StrEnum`이 없어 integration collect가 불가능했고,
  설치된 Python 3.14에는 pytest가 없다. 이 환경에서 실 PG 결과를 합성하지 않는다.
- real-PG fixture와 직접 함수 부정군은 PR exact head의 `run-core` JUnit으로만
  판정한다. 그 전 상태는 **NOT_RUN**이다.
