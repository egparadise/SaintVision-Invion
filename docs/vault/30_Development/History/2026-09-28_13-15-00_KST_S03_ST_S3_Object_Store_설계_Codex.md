---
doc_id: "HIST-CODEX-S03-ST-S3-OBJECT-STORE-DESIGN-001"
title: "S03-ST S3 호환 Object Store Adapter 설계"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T15:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S03-ST"]
tags: ["history", "storage", "s3", "sigv4", "design"]
---

# S03-ST S3 호환 Object Store Adapter 설계

## 작업한 것

- 카드 40, base `1e8baf045c5a554209aaef601ae4883b64da50a7`, branch `agent/codex/s3-object-store-design`에서 구현 전 설계만 작성했다.
- 현행 `LocalObjects`, `inv.storage_objects`, snapshot/result reader, Artifact HTTP download와 PR #129 configuration-readiness, PR #135 SigV4 왕복 도구를 대조했다.
- opaque locator 기반 공통 `put/get/delete/exists/hash`, Local service/RLS와 S3 prefix 격리의 의도적 차이, 단일 제품 SigV4 구현, 보호된 설정 정본, digest/header 결속, timeout·부분 쓰기·삭제 잔존 처리, provider-id/locator migration과 hosted MinIO lane을 고정했다.

## 확인한 것

- 현행 로컬 provider는 `locked()` 아래 `ObjectHandle.read/put/remove`이고 S3 구현은 없다. storage row에는 provider 식별자가 없으며 checkpoint 응답은 `local-bounded-v1`을 하드코딩한다.
- 현행 result-view download는 provider를 읽지 않고 receipt-derived bytes만 읽으므로 제품 provider body를 주 경로로 교체해야 한다. read ticket 뒤 provider I/O와 짧은 DB 재검증으로 DB→provider lock 역전을 피하도록 설계했다.
- PR #135의 SigV4 client는 preflight 도구 내부 구현이다. 제품 adapter와 도구가 이를 각각 복제하지 않고 제품 모듈 하나를 사용해야 한다.
- 이 카드는 docs-only이며 제품 코드, migration, JSON Schema, 생성 타입, MinIO/Docker, 실 PG, 운영 인수를 실행하지 않았다.

## reviewer 수정 요청 보정 v1.1

- F1은 option (b)로 결정했다. Local flat locator 격리는 tenant-scoped DB service/RLS가 맡고 provider-internal prefix 격리는 S3 전용이다. 공통 SPI에 scope를 넘겨 Local이 버리는 설계와 Local re-key는 채택하지 않았다.
- F2는 provider ID가 checkpoint identity/content/event/응답에 이미 참여하는 불변을 유지한다. 기존 row는 정확히 `local-bounded-v1`로 backfill하고 `snapshots.py`와 `workspace_resume.py`가 모두 row의 immutable provider ID를 쓰며 두 생산자 replay guard를 요구한다.
- F3은 receipt를 audit evidence로만 남기고 provider body로 주 경로를 교체한다. ready row+provider missing은 fallback 200이 아니라 `STORE-0001`/503/retryable이며 내부 integrity alert 대상이다.
- F4는 `configurationReadiness.objectStore`를 단일 정본으로 정했다. 새 binary가 legacy 또는 new 중 하나만 받는 binary-first rollout 뒤 config 전환, legacy 제거 순서이며 old binary+new config와 dual-key는 startup 거부다.
- F5는 live `ArtifactContentResponse.artifact.checksumSha256`과 설계-only `ArtifactDownloadMetadata.contentSha256`을 구분하고 DB/provider/body/header 4중 결속으로 바로잡았다.

## 검증

- `PYTHONUTF8=1 PYTHONPATH=src;services/control-plane/src .venv/Scripts/python.exe tools/check_docs.py` → exit 0 (`894 versioned documents`, task 48/outcome 12).
- 같은 interpreter로 `tools/check_doc_single_source.py --ratchet` → exit 0 (baseline 18 pairs, 새 중복 0), `tools/check_ontology.py` → exit 0, `git diff --check` → exit 0.
- `tools/sync_obsidian.py --check` → exit 0 (`1734 managed`, `4 pending exports`, `0 conflicts`, write 0). 실제 `--apply`는 코디네이터 정본 sync 범위라 실행하지 않았다.
- 현재 문서 상태는 `proposed/review`다. reviewer 승인을 구현 완료나 운영 S3 선정으로 해석하지 않는다.

## 다음 첫 행동과 담당

Claude가 v1.1의 Local 격리 예외, checkpoint provider identity, download lock 순서, strict configuration rollout을 재검토한다. 승인 뒤 Codex가 계약/schema·migration·PG-free conformance부터 별도 구현 카드로 시작하며, hosted MinIO와 실제 Artifact download evidence는 이후 CI 카드에서 수집한다.
