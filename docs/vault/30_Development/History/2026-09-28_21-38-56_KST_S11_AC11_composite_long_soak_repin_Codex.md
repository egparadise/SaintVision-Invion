---
doc_id: "HISTORY-S11-AC11-LONG-SOAK-REPIN-20260928"
title: "S11 AC-11 composite long-soak registry repin과 physical importer"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T22:01:22+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_id: "S11-BE"
acceptance_id: "AC-11"
tags: ["S11", "AC-11", "long-soak", "registry", "importer"]
---

# S11 AC-11 composite long-soak registry repin과 physical importer

## 결과

- #204 head `dc52051bf6600470fe5f02e20ad6f8b18c686dad` 위에 #214 설계 head `5489f002305c571bcd225f40d00ab1c24d722e8a`를 merge commit `a4e0c466b6548286328117f27f5e1a9418521138`로 결속했다. 충돌은 공통 작업판과 Codex 작업판뿐이었고 양쪽 기록을 모두 보존했다.
- 정본 registry에 기존 ID를 덮어쓰지 않고 `s11-ac11-composite-long-soak-v0`를 새로 추가했다. predecessor blob은 `c08a45f8cd3a32fe6631d7f135496a5e7809ee2d`, 결과 blob은 `be99a506efecdb2ff29cf4e7a96a8772f5524473`이다. 같은 repin에서 migration target 문서의 고정 `tail=1` 문장을 graph 파생 규칙으로 고친 docs commit `4c68bc8e`와 blob `55ee8b65…`도 sourceDocument에 재결속했다.
- `tools/aggregate_ac11_evidence.py`는 `long-soak` 축을 위 target 하나에만 결속한다. migration rehearsal importer와 새 physical importer도 같은 registry blob으로 repin했다. old blob의 `tools/`, `tests/`, 정본 Evidence 잔존은 0건이다.
- `tools/import_ac11_composite_long_soak.py`는 14개 exact case identity, 20개 closed fault class, 24시간 창, ADR-100 physical topology, external observer receipt, physical storage child, hosted drift child, Git source/tree/target provenance를 다시 검증한다. child source SHA·inventory·창·canonical digest 또는 fault class가 어긋나면 import 오류다.
- G-19/G-24가 없으면 `BLOCKED_EXTERNAL`, target이 등록되지 않은 사전 상태는 `NOT_REGISTERED`로 남긴다. 이 카드에서는 물리 장비 실행·fault injection·PostgreSQL·Docker를 수행하지 않았고 AC-11 `long-soak`은 측정 완료가 아니다.

## 검증

- `python -m pytest -q tests/test_import_ac11_composite_long_soak.py tests/test_aggregate_ac11_evidence.py tests/test_import_ac11_migration_rehearsal.py` → **95 passed**, exit 0. 닫힌 operator resource, case별 fault-class 결속, 실패 case를 통과 metric으로 숨기는 변이도 포함한다.
- `python -m py_compile tools/import_ac11_composite_long_soak.py tools/aggregate_ac11_evidence.py tools/import_ac11_migration_rehearsal.py` → exit 0.
- registry와 applied patch JSON을 `python -m json.tool`로 각각 검증 → exit 0.
- `python tools/check_docs.py` → exit 0 (24 original hashes, 934 versioned documents, 48 tasks).
- `python tools/check_contract_bindings.py` → exit 0 (55 fixtures, 20 bound response types, 14 replay guards).
- `python tools/check_ontology.py` → exit 0 (RDF/SHACL/48 task mappings/Obsidian mirrors).
- `python tools/check_doc_single_source.py --ratchet` → exit 0 (18 pairs, stale 0).
- `git diff --check` → exit 0.

## 남은 일

- Claude가 registry 연속성, target source pin, fail-closed 변이 시험을 독립 검토해야 한다.
- G-19/G-24 자원이 준비된 뒤 별도 승인된 물리 카드에서만 24시간 run을 실행한다. 그 전에는 합성 fixture와 hosted reference를 물리 PASS로 세지 않는다.

관련 문서: [[S11_AC11_composite_long_soak_설계]], [[S11_AC11_composite_long_soak_target_v0]], [[S11-ST_손상_용량_backup_장애시험_설계]].
