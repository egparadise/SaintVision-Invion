---
doc_id: "HIST-CODEX-S03-ST-S3-OBJECT-STORE-DESIGN-001"
title: "S03-ST S3 호환 Object Store Adapter 설계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T13:15:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S03-ST"]
tags: ["history", "storage", "s3", "sigv4", "design"]
---

# S03-ST S3 호환 Object Store Adapter 설계

## 작업한 것

- 카드 40, base `1e8baf045c5a554209aaef601ae4883b64da50a7`, branch `agent/codex/s3-object-store-design`에서 구현 전 설계만 작성했다.
- 현행 `LocalObjects`, `inv.storage_objects`, snapshot/result reader, Artifact HTTP download와 PR #129 configuration-readiness, PR #135 SigV4 왕복 도구를 대조했다.
- 공통 `put/get/delete/exists/hash` 의미, server-derived tenant/project prefix, 단일 제품 SigV4 구현, 보호된 설정 정본, digest/header 결속, timeout·부분 쓰기·삭제 잔존 처리, provider-id migration과 hosted MinIO lane을 고정했다.

## 확인한 것

- 현행 로컬 provider는 `locked()` 아래 `ObjectHandle.read/put/remove`이고 S3 구현은 없다. storage row에는 provider 식별자가 없으며 checkpoint 응답은 `local-bounded-v1`을 하드코딩한다.
- 현행 result-view download는 receipt-derived bytes를 읽으므로 ADR-099의 storage object bytes 정본에 아직 결속되지 않았다.
- PR #135의 SigV4 client는 preflight 도구 내부 구현이다. 제품 adapter와 도구가 이를 각각 복제하지 않고 제품 모듈 하나를 사용해야 한다.
- 이 카드는 docs-only이며 제품 코드, migration, JSON Schema, 생성 타입, MinIO/Docker, 실 PG, 운영 인수를 실행하지 않았다.

## 검증

- `PYTHONUTF8=1 PYTHONPATH=src;services/control-plane/src .venv/Scripts/python.exe tools/check_docs.py` → exit 0 (`894 versioned documents`, task 48/outcome 12).
- 같은 interpreter로 `tools/check_doc_single_source.py --ratchet` → exit 0 (baseline 18 pairs, 새 중복 0), `tools/check_ontology.py` → exit 0, `git diff --check` → exit 0.
- `tools/sync_obsidian.py --check` → exit 0 (`1734 managed`, `4 pending exports`, `0 conflicts`, write 0). 실제 `--apply`는 코디네이터 정본 sync 범위라 실행하지 않았다.
- 현재 문서 상태는 `proposed/review`다. reviewer 승인을 구현 완료나 운영 S3 선정으로 해석하지 않는다.

## 다음 첫 행동과 담당

Claude가 설계의 adapter 의미, ambiguous timeout reconciliation, provider-id migration, configuration-readiness 계약 영향을 독립 검토한다. 승인 뒤 Codex가 계약/schema·migration·PG-free conformance부터 별도 구현 카드로 시작하며, hosted MinIO와 실제 Artifact download evidence는 이후 CI 카드에서 수집한다.
