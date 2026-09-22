---
doc_id: "HISTORY-CODEX-FIVE-NODE-PHYSICAL-ADAPTER-20260923"
title: "5노드 물리 adapter read-only preflight 구현"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T07:25:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S05", "five-node", "adapter", "PostgreSQL", "mTLS", "ADR-100"]
---

# 5노드 물리 adapter read-only preflight 구현

## 범위와 SHA

- 카드: Codex 카드 14, 5노드 lane v1.4 물리 adapter 계약 초안과 최소 구현.
- 최초 base: `4143f375a2198572455a442cf2d80086d70f5b6b`.
- 최종 rebase parent: `8ac5caae795a54ab740d813412d483584872ae7b`.
- 구현 SHA: `ec254775`(rebase 전 `923564b2`와 코드 blob 동일).
- branch/PR: `agent/codex/five-node-adapter`, PR #101.
- 계약 변경: 공유 `contracts-*`·HTTP·DB schema 변경 없음. [[Codex 5노드 랩 opt-in lane 정의]] v1.5의 tool-local inventory/preflight 계약만 추가했다.

## 구현

`tools/placement_benchmark.py`에 기본값 `synthetic`을 유지한 채 `--adapter five-node-lab --inventory <path> --dry-run`을 추가했다. inventory는 canonical JSON SHA-256 revision, 고유 node/IP/certificate/host identity, profile, failure domain, ADR-100 co-location과 S05/S07 eligibility를 strict하게 검사한다. CP 겸임 Node는 all-five smoke에는 포함될 수 있지만 timed wave에는 선택되지 않으며, 독립 Node만 eligibility를 얻는다.

adapter는 `INV_TEST_ADMIN_DSN`으로 `SET TRANSACTION READ ONLY`와 `SHOW transaction_read_only=on`을 확인한 뒤 등록 Node, heartbeat, mTLS channel, resource snapshot만 조회한다. 합성 row/resource를 생성하지 않고 heartbeat/snapshot을 갱신하지 않는다. inventory 누락 등록, tenant 중복, endpoint/fingerprint/epoch/channel version/snapshot identity drift는 exit nonzero다. offline/stale/missing snapshot, clock skew, `lan-workspace-v1` 미충족은 false readiness와 원인을 report에 남긴다. 물리 부하 실행은 명시적으로 차단했으며 JSON은 `databaseReadOnly=true`, `syntheticRowsCreated=false`, `heartbeatUpdated=false`, `loadExecuted=false`를 고정한다.

## 검증

| 명령/대상 | 결과 |
|---|---|
| `pytest -q tests/test_placement_benchmark_five_node_adapter.py tests/test_placement_benchmark_tool.py` | 12 passed, exit 0 |
| 현 파일럿 PG 55440, online Node `.143`·`.210`, revision-fixed 2-node inventory dry-run | exit 0, registered 2, ready 0, all-five false, timed-wave false |
| 파일럿 dry-run 불변식 | read-only true, synthetic row 0, heartbeat update 0, load 0 |
| 파일럿 readiness 원인 | 두 Node 모두 실제 snapshot `lan-observe-v1`; `profile-not-lan-workspace-v1`, 승격 없음 |
| `python tools/check_docs.py` | 보고 포함 867 docs, exit 0 |
| `python tools/check_contract_bindings.py` | 54 fixtures, 19 types, 25 sites, 14 replay guards, exit 0 |
| `python tools/check_frontend_integrity.py` | 9 rules, exit 0 |
| `python tools/check_ontology.py` | 48 task mappings, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | 18 baseline pairs, exit 0 |
| `python tools/check_response_freshness.py` | advisory 10/10 present, exit 0 |
| `python tools/sync_obsidian.py --check` | 1704 managed, pending export 3, conflict 0, exit 0; apply는 코디네이터 담당 |

실 PG dry-run은 부하가 아니며 현재 두 Node가 관측 profile이라는 사실을 정직하게 드러낸다. Node 5개, CP 겸임 Node, `lan-workspace-v1`, all-five smoke와 timed legacy wave는 미측정이다. 따라서 AC-05와 S05 done을 주장하지 않고 `review`를 유지한다.

## 다음 행동

Claude가 PR #101에서 inventory strictness, read-only SQL, CP 겸임 사전 제외, 합성 기본 경로 불변을 독립 검토한다. 코디네이터는 revision-fixed 실제 inventory로 현재 파일럿 dry-run을 재실행하고, Windows CP 겸임 Node는 Docker API 1.45 준비 뒤 별도 등록한다. timed placement wave와 JUnit/JSON 물리 evidence 결속은 후속 승인 카드이며 이 PR에서는 실행하지 않는다. Codex의 다음 별도 작업은 카드 15 O1/O2/O4/O5 관찰 보강이다.
