---
doc_id: "HIST-CODEX-S11-AC11-REGISTRY-REPIN-001"
title: "S11 AC-11 PITR target registry 재고정"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-09-28T16:23:43+09:00"
source_of_truth: "Git"
task_id: "S11-ST"
reviewer: "Claude"
---

# S11 AC-11 PITR target registry 재고정

## 범위

- 카드 ID는 `CARD-S11-AC11-REGISTRY-REPIN-01`이다.
- #177 head `b246e7dbd597db52ae5c16be4c0a03ffd056ab93` 위 새 branch에서 #185 승인 head `33ed1b8c79d57532b92c10858241f05aff6bd8ec`를 merge commit `067e6a48ec18693c98653db18887f8f5da859e1b`로 결속했다.
- `git merge-tree --write-tree` 결과와 merge commit tree `5f254e75bd5411f43277d1ff16de52616d3211e8`이 같아 merge commit에 별도 편집이 없다.

## 구현

- 정본 `s11-ac11-target-registry-v0.json`에서 약한 `s11-actual-pitr-v0`를 제거하고 `s11-st-actual-pitr-archive-failure-v0`를 적용했다.
- 새 target은 #185 frozen source commit `3363ab77e7fc4ccf3be140466a053a973b0b65a4`, blob `421d4d3a6e39720e74bc6fd832f30e8b45f8680a`에 결속된다.
- WAL archive failure, silent exit-0 loss, retention interruption과 각 종류 뒤 recovery를 양의 기준으로 요구하고, false PITR pass·retained boundary deletion·cleanup residue는 0이어야 한다.
- 카드 90 후속 registry blob은 `c08a45f8cd3a32fe6631d7f135496a5e7809ee2d`이다. stage-1 aggregator와 migration rehearsal importer의 pin을 같은 commit에서 함께 갱신했다. 기존 PITR 교체에 더해 `s11-migration-reversible-roundtrip-v1`을 등록하고 restore-forward 부정 fixture 목표를 4건으로 올렸다.
- aggregator의 `REQUIRED_TARGET_BY_AXIS`는 PITR axis에 새 target 하나만 허용한다. `long-soak`은 composite target 승인 전 `NOT_REGISTERED`이며 map에 추가하지 않았다.
- repository 시험은 sourceDocument blob==HEAD를 계속 검사하고, old PITR targetId는 required map에서 `INVALID_RUN`으로 거부한다.

## 검증

- `python -m pytest -q tests/test_aggregate_ac11_evidence.py`: 55 passed, exit 0.
- `python -m pytest -q tests/test_import_ac11_migration_rehearsal.py`: 14 passed, exit 0.
- 로컬 PostgreSQL·Docker·전체 suite는 실행하지 않았다.
- `check_docs`, `check_ontology`, `check_contract_bindings`, `check_doc_single_source --ratchet`, JSON parse와 `git diff --check`는 모두 exit 0이다.

## 경계와 후속

- 공개 HTTP 계약·migration은 바꾸지 않았다. S11-ST parent는 S10 선행 task가 미완료라 `planned`를 유지한다.
- #177의 과거 restore artifact(run `36379743674`, artifact `10952510591`, source `abe8435a`)는 old registry blob `99e64cb4…`에 결속돼 있다. #192의 importer와 aggregator는 새 pin `c08a45f8…`이 없는 이 artifact와 이미 import한 봉투를 의도대로 `INVALID_RUN`으로 거부한다. 따라서 restore-forward와 reversible-roundtrip 증거는 `c08a45f8…`을 포함하는 release SHA에서 재생성해야 하며, 과거 CLI exit 0을 release evidence로 재사용하지 않는다.
- task registry는 고정 sprint task schema라 synthetic card row를 추가하지 않고 이 History와 [[Codex 작업 현황]]에서 카드 ID를 추적한다.
- stage-1 aggregator가 metric별 `value` 의미를 재계산하지 않는 R12는 다음 §8-3 storage importer 카드에서 machine-readable semantics를 registry에 둘지 importer-only derivation으로 둘지 결정한다.
- 다음 구현은 PG-free raw producer·storage importer이며 universe 22, PG-free 12, hosted 10 identity와 exact 분류를 부정 시험으로 고정한다.
