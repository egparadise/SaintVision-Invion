---
doc_id: "HIST-2026-09-22-ARTIFACT-REAL-PG-HTTP-CODEX"
title: "산출물 다운로드 실제 PostgreSQL·Uvicorn 검증과 파일 원본 경계"
version: "1.0.0"
status: "evidence"
author: "Codex"
updated: "2026-09-22T03:14:55+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["artifact-download", "postgresql", "uvicorn", "integrity", "evidence-boundary"]
---

# 산출물 다운로드 실제 PostgreSQL·Uvicorn 검증과 파일 원본 경계

## 범위와 provenance

- 기준 코드 SHA: `a0839b4a2aa3f22bd6872bfbe50d339bfccd1d92` (integration worktree).
- 실행 시점에는 Gemini의 미커밋 변경이 공용 worktree에 있었다. Codex는 이를 수정하거나 stage하지 않았다. 실제 PostgreSQL/Uvicorn 검증용 임시 시험 파일도 실행 후 원복했다.
- KST 실행 시각: 2026-09-22 03:09:09 (JUnit UTC `2026-09-21T18:09:09Z`).
- 실행 명령: `.venv/Scripts/python.exe .work/run_artifact_e2e.py`.
- 이 orchestration은 자체 라벨이 붙은 PostgreSQL 16, 격리 Docker network, Linux test runner만 만들었다. Runner 내부 시험 명령은 `/usr/local/bin/python -m pytest -q tests/integration/test_result_observation.py::test_uvicorn_download_matches_persisted_workspace_file_and_exposes_disk_source_boundary --junitxml=/tmp/result.xml`이다.
- Host orchestrator interpreter: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6. Runner interpreter: `/usr/local/bin/python` 3.12.14 (Linux Docker image). Node runner/image는 기존 로컬 테스트 이미지에서 사용했으며 저장소의 현재 Go 소스에서 새로 빌드한 바이너리 인수는 아니다.
- JUnit: `docs/vault/30_Development/Evidence/artifact-download-real-pg-uvicorn.xml` — 1 test, 1 passed, 0 failed, 0 errors, 0 skipped.
- Post-run documentation checks: the first `.venv/Scripts/python.exe tools/check_docs.py` returned exit 1 on six memory/wiki links in the separate Claude document `2026-09-22_Codex_쓰기응답_재판정과_PG검증_독립검토_Claude.md`. Claude's concurrently updated document was left untouched; a later rerun returned exit 0 (`24 original hashes, 706 versioned documents`). Final `.venv/Scripts/python.exe tools/check_ontology.py` exit 0. Final `.venv/Scripts/python.exe tools/sync_obsidian.py --check` returned exit 0 (1507 managed, 3 pending exports, 0 conflicts; read-only). `git diff --check` and `git diff --exit-code HEAD -- tests/integration/test_result_observation.py` returned exit 0. Pending Obsidian exports were not applied.

## 실제로 확인한 것

1. disposable PostgreSQL에서 기존 통합 fixture가 실제 Run을 생성하고 승인·등록된 synthetic Node의 실행과 output ingestion 및 결과 확정을 수행했다. 산출물은 실제 Linux `LocalObjects` 저장소에 게시됐다.
2. 저장소 파일을 독립적으로 다시 읽어 `outputs/metrics.json`의 manifest SHA-256과 파일 바이트를 확인했다.
3. DB와 실제 JWT를 쓰는 `create_app`을 Uvicorn 0.52.4로 ephemeral localhost TCP port에 기동하고 `urllib`로 실제 HTTP 요청을 보냈다. 응답은 200이었고 다운로드 바이트가 저장 snapshot에서 독립적으로 읽은 파일 바이트와 같았으며, wire `x-content-sha256`도 그 바이트의 SHA-256 및 manifest hash와 같았다.
4. 저장된 workspace snapshot object 파일을 서버 뒤에서 변조했다. 실제 파일의 SHA-256은 DB `storage_objects.content_hash`와 달라졌지만 HTTP endpoint는 계속 200을 반환하고 DB stop receipt에서 재구성한 원래 바이트와 그 해시를 보냈다. 따라서 파일 대조의 불일치는 실제로 만들어졌으나 HTTP 경로는 파일 변조를 감지하지 않았다. 이는 파일 기반 다운로드 검증의 통과가 아니다. 라우트는 GET에서 LocalObjects 파일을 다시 열지 않는다는 동작을 실측했다.
5. DB의 immutable `storage_objects.content_hash`를 직접 변경하려는 별도 대조는 `inv.guard_storage_object()` trigger가 거부했다. 해당 UPDATE는 커밋되지 않았다.

## 결론과 미확인 경계

본문과 헤더가 실제 DB 실행 및 실제 저장 파일의 정상 시점에서 일치하는 것은 확인됐다. 다만 제품의 `ResultView._output`은 GET 시 물리 object 파일을 읽는 대신 PostgreSQL stop receipt의 base64 bytes를 읽고 DB commitment hash와 비교한다. `ResultView._files`도 receipt 안의 workspace snapshot으로 파일을 재구성한다. 반면 성공 완료 때는 workspace snapshot을 LocalObjects에 별도로 게시한다. 그러므로 현재 API는 receipt 무결성을 읽기 시 검증하지만, 이후의 filesystem 저장본이 바이트 원본이라는 보장은 하지 않는다.

이 동작이 의도된 receipt-authoritative 설계인지, 아니면 artifact endpoint가 게시된 workspace object를 읽어야 하는지는 후속 제품 결정/설계 검토가 필요하다. 현재 `create_app`/`create_configured_app`에는 ResultView용 output provider 설정이 없고 `INV_OUTPUT_ROOT`는 worker 설정에만 등장한다. 따라서 production API가 object 파일을 재개방하는 구성은 이번 실행에 없었다. 제품 결함으로 단정하지 않았으며, 이번 검증은 “실제 파일을 읽는 HTTP download”를 승인하지 않는다.

실제 TLS/CDN/reverse proxy, deployment volume 공유, 실제 장비 Node, 브라우저 다운로드는 확인하지 않았다. Uvicorn 서버 thread는 `finally`에서 중지했고 종료를 확인했다.

## 일회용 Docker 정리

- 소유 라벨: `ai.saintvision.artifact-e2e=codex-artifact-e2e-e73b9eedb0bc`.
- PostgreSQL 컨테이너, Linux runner 컨테이너, 격리 network를 라벨과 고유 이름으로 확인한 뒤 정리했다. 제거 후 같은 라벨 조회는 container 0, network 0이었다.
- 보호 컨테이너 `saintvision-lan-db-bff1a31d`, `saintview-orthanc-h1`, `saintview-orthanc-h2`는 실행 후에도 살아 있는 것을 이름으로 확인했다. 다른 호스트 컨테이너는 대상으로 삼지 않았다.

## 다음 행동

Codex는 저장 artifact를 GET의 정본으로 삼을지 receipt bytes를 정본으로 삼을지 현재 결과/복구 계약과 대조해 제안한다. 파일 원본이 요구된다면 API에 output provider와 운영상 공유 저장소 설정을 추가하고, 물리 파일 변조 시 실제 HTTP가 422/503으로 실패하는 시험을 고정한 뒤 재검증한다. 배포 proxy와 브라우저 인수는 별도 담당/환경에서 수행한다.
