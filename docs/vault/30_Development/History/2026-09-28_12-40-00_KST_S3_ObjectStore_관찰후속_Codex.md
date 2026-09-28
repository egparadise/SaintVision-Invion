---
doc_id: "HIST-CODEX-S3-OBJECT-STORE-OBSERVATIONS-003"
title: "S3 ObjectStore 비차단 관찰 후속 — checkout provider pin·GC prefix 선검증·오류/restore 순서 결속"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T12:53:48+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "c654fada64a3d6804416c928908fdeb7566dfb2e"
implementation_sha: "ae20b0e446a35f42f6ae2304567426d622316b9c"
task_ids: ["S01-ST"]
tags: ["object-store", "s3", "workspace", "gc", "provider-binding", "codex"]
---

# S3 ObjectStore 비차단 관찰 후속

## 시작 조건과 범위

- Card 52, owner Codex / reviewer Claude. PR #159 보고 head `c654fada` 위 branch `agent/codex/s3-object-store-observations`, PR #173이다.
- #159 Claude r3 승인 뒤 남은 비차단 관찰 다섯 항목만 다뤘다. 공개 HTTP 계약·schema·migration·registry는 바꾸지 않았고 로컬 실 PostgreSQL·Docker는 실행하지 않았다.

## 구현과 판정

- `_checkout_reader`의 S3 경로는 persisted row의 `provider_id`를 registry에서 exact resolve한다. writer인 `self.snapshots.provider`로 되돌리는 변이는 direct 시험에서 Local provider가 선택되는 즉시 실패한다.
- `ObjectStore` 내부 SPI에 `validate_locator`를 추가했다. `SnapshotStore.collect`는 provider 결속과 locator를 확인한 뒤에만 pin/commitment를 확인하고 `deleting` tombstone을 커밋한다. 따라서 운영 prefix가 바뀐 canonical locator는 행을 `deleting`에 묶지 않고 `STORE-0001`/503/retryable로 닫는다.
- S3 locator는 마지막 7개 canonical scope segment를 먼저 검증한 뒤 그 앞 prefix 전체가 configured prefix와 exact match하는지 본다. `product/nested/...`처럼 현재 prefix를 접두사로 포함한 다른 provider identity도 422 입력 오류가 아니라 `STORE-0001`/503/retryable이다. 문법·UUID·namespace가 잘못된 locator는 기존 `STORE-0002`/422를 유지한다.
- `SnapshotStore.begin`의 provider/locator drift도 `IDEM-0001`/409에서 `STORE-0001`/503/retryable로 통일했다. 같은 provider/locator에서 digest·size·terminal state가 달라지는 실제 upload identity 충돌은 계속 `IDEM-0001`이다.
- 새 restore는 Run이 `recovering`이고 version/attempt가 현재인지 checkpoint pin 조회 전에 검사한다. 실패는 기존 `GRAPH-0003`이고 exact replay는 저장된 restore를 확인해 기존 우회 의미를 유지한다.
- result prepare/complete, shard completion, snapshot put/finalize/checkpoint/restore/collect, workspace restore/checkout/output commit의 모든 byte I/O·삭제 상태 변경 앞에 provider mismatch guard가 존재함을 호출 지점별 회귀 시험으로 고정했다.

## 검증

| 명령/범위 | 결과 |
|---|---|
| `pytest tests/core/test_s3_object_store.py tests/core/test_object_store_provider_binding.py -q` | 46 passed, exit 0 |
| object locator/config/workspace contract/artifact/serving anchor focused 5파일 | 53 passed, 1 Windows symlink skip, exit 0. skip은 통과로 합산하지 않음 |
| `pytest tests/test_route_coverage.py -q` | 40 passed, exit 0 |
| Python compile + `tools/check_contract_bindings.py` | exit 0; fixture 55 / response type 20 / replay guard 14 |
| `tools/check_frontend_integrity.py` | 9 rules, 0 violations, exit 0 |
| `tools/check_response_freshness.py` | advisory 10/10, exit 0 |
| `tools/check_ontology.py` | RDF/SHACL/task mappings/Obsidian mirrors PASS, exit 0 |
| `tools/check_doc_single_source.py --ratchet` | baseline 18 pairs, new/stale 0, exit 0 |
| `tools/check_docs.py` | 구현 push 전 900 docs, exit 0 |
| `git diff --check` | exit 0 |

## Hosted·인계

- 구현 head `ae20b0e4`를 force 없이 push했고 PR #173을 #159 branch 위에 stack했다. `run-core` label을 붙여 Core와 `s01-storage-roundtrip`을 실제 실행한다.
- 이 문서 작성 시 hosted Backend/Core가 진행 중이다. 완료 run ID·passed/skip/failed 분포와 Claude 독립 검토 판정은 후속 revision에서 적는다. 진행 중을 통과로 세지 않는다.
- `sync_obsidian.py --check`는 기존 공유 진행판 `both-diverged`와 Gemini 작업판 `destination-edited` 충돌 2건을 보고하고 쓰기 없이 종료했다. 코디네이터 지시대로 이 worktree에서는 `--apply`를 실행하지 않았고, 해당 충돌 파일을 편집하지 않았다.
- 다음 Claude: direct checkout provider 선택, prefix-only collect tombstone 선차단, `STORE-0001` 일관성, restore `GRAPH-0003` 순서와 호출 지점 되살림을 독립 재검토한다. 병합은 사용자/코디네이터 결정이다.
