---
doc_id: "HIST-CLAUDE-2026-09-28-G02-LIVE-ARCHIVER-DESIGN"
title: "G-02 live archiver hosted 실행 설계 v1.0 (docs-only) — 두 겹 skip 원인 실측(CX01 fixture 전제가 먼저, 내부 네트워크 도달성이 다음), 권고안 (a) docker exec 실행자 주입, exact skip-map 19→17, fail-closed·되돌림 시험 목록 (카드 54)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T13:54:47+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S12-ST"]
tags: ["G-02", "recovery", "hosted", "design", "claude"]
---

# G-02 설계 (2026-09-28, 카드 54)

설계 본문: [[G-02 live archiver hosted 실행 설계 v1.0]]. 요지:

- **실측 정정**: hosted skip의 첫 장벽은 `args` fixture의 CX01 소유 컨테이너 전제(`tests/recovery_drill_prerequisites.py:22`; Backend run 36377166070 `-rs`에 `[2] test_recovery_drill.py:488: CX01_CONTAINER is unset`)이고, #179 §3-2가 인용한 내부 네트워크 도달성은 둘째 장벽. 둘 다 풀어야 skip 2 → 실행 2.
- 권고안 (a): `docker network create --internal`·port publish 금지 불변, `_recovery_capability(dsn=None, *, execute=None)`로 실행자 주입(기본 psycopg 실행자 = 오늘과 동일, `docker exec … psql` 실행자 추가), 접기 SQL은 도구 안 상수 하나를 두 실행자가 공유(판정 미복제). 호출자 4곳 목록은 `git grep` 결과 그대로. 워크플로 최소 변경(env 1줄, exact skip-map 19→17 두 파일).
- fail-closed: 실행자 실패는 RuntimeError(원문 미노출), 값 없으면 dict 없음, skip 사유 2개만 고정. 되돌림 시험 7항.
- migration 없음. 2단계 구현 PR은 이 설계 위 stack.

로컬 검증: docs-only, check_docs·single_source 통과. owner Claude / reviewer Codex(worker) / 병합 금지.
