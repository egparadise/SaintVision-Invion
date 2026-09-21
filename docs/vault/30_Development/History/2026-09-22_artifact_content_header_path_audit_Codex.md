---
doc_id: "HISTORY-2026-09-22-ARTIFACT-CONTENT-HEADER-AUDIT-CODEX"
title: "Artifact content SHA-256 header path audit"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-22T02:45:00+09:00"
source_of_truth: "Git"
---

# Artifact content SHA-256 header path audit

## Scope and conclusion

Task: verify whether every successful production artifact-content response carries the `X-Content-SHA256` header required by Gemini's download verifier. No Gemini/UI source was changed.

The current control-plane has exactly two artifact-content route aliases:

- `GET /v1/runs/{run_id}/artifacts/content`
- `GET /v1/projects/{project}/runs/{run_id}/artifacts/content`

Both decorators resolve to the same `run_file` handler in `services/control-plane/src/inv/app.py`. That handler calls `result_view.download(...)`, then passes its materialized body bytes and artifact metadata to `artifact_content_response(...)`. The response builder verifies byte length and SHA-256 against metadata, validates the response contract, and constructs a raw `Response` with `X-Content-SHA256`, `Content-Length`, `Content-Disposition`, and `X-Content-Type-Options`. The `Boundary` middleware retains this header and sets `Cache-Control: no-store`.

Source review of `ResultView.download` found the current workspace-output read/verification path; it does not stream, redirect to object storage, presign a URL, or branch to a separate cache/range response. There is no conditional response implementation (`ETag`/304), `Content-Range`/206 handling, or other production artifact-content route. Requests carrying `Range` and `If-None-Match` are currently ignored and return the same full 200 response through the shared builder. This last behavior is also covered by TestClient checks. This is a source and in-process HTTP conclusion; no deployed reverse proxy, cross-origin browser, or production HTTP path was exercised.

## Legacy fixture boundary

Repository-wide search found another pair of paths with the same URL shape in `tests/fixtures/legacy_control.py`. That quarantined fixture returns `X-Checksum-SHA256` with a legacy `sha256:` value, not `X-Content-SHA256`. The only Python import sites found are `tests/test_server_project_api.py` and `tests/test_server_auth_integrity.py`; those are legacy fixture tests, not the current control-plane app. No production imports of the fixture were found. Therefore it is not a header-less success branch in the current product server. Whether any out-of-repository deployment still runs this legacy fixture is outside repository evidence; if so, Gemini's strict client would reject downloads from it until it is retired or brought to the current response contract.

Other `StreamingResponse` hits were inspected. The current control-plane stream is the unrelated `/events` SSE route; fixture streams are also event streams. They do not serve artifact bytes.

## Regression guard and falsification

`tests/core/test_artifact_content_contract.py` now:

1. Exercises both current route aliases with an ordinary request and with `Range` plus `If-None-Match` headers.
2. Requires HTTP 200, the complete expected bytes, and matching `X-Content-SHA256` on every case; it also checks byte length, disposition, nosniff, no-store, and absence of `Content-Range`/`ETag`.
3. Enumerates every current app route containing `/artifacts/content` and requires exactly the two expected paths to resolve to one handler. An added third content route therefore fails the inventory assertion until it is deliberately audited and added to the contract.

The central header line was removed from `artifact_content_response` as a negative control. All four parameterized successful-route cases failed, then the line was restored. This shows that the route tests actually depend on the header guarantee. The route inventory is also an exact-set assertion, so added, removed, or renamed content paths fail rather than silently escaping the checked aliases.

## Provenance

- Base/code-under-test SHA: `3ebbe960f8136318a16427c248d8345172805a12`.
- Branch: `agent/codex/artifact-content-header-audit`.
- Worktree: `C:/Project/SaintVision-Invion`.
- Interpreter: `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe`, Python 3.14.6.
- OS: Windows 11; environment gates at invocation: PostgreSQL DSN absent, Docker present, Go absent, Node v24.17.0.
- Initial pass run before the negative control, KST `2026-09-22 02:42:15`: `.venv/Scripts/python.exe tools/provenance.py --executor Codex -- .venv/Scripts/python.exe -m pytest -q tests/core/test_artifact_content_contract.py`; exit 0, 13 passed, 2 warnings.
- Header-removal mutation, KST `2026-09-22 02:43:26`: `.venv/Scripts/python.exe tools/provenance.py --executor Codex -- .venv/Scripts/python.exe -m pytest -q 'tests/core/test_artifact_content_contract.py::test_artifact_content_route_returns_raw_bytes_bound_to_contract_headers'`; exit 1, 4 failed as expected, 2 warnings. The production line was restored immediately afterward.
- Post-restoration pass, KST `2026-09-22 02:44:07`: same full-file command, exit 0, 13 passed, 2 warnings. `check_docs.py` and `check_ontology.py` also exited 0. `sync_obsidian.py --check` exited 0 with 1500 managed files, 3 pending exports, 0 conflicts; these are the three task documentation files listed in this work item.
- Executor: Codex, author-run; independent review pending. This is not browser acceptance or deployed HTTP verification.

## Next action

Complete the three pending Obsidian exports, then commit/push and request independent review at the resulting integration SHA.
