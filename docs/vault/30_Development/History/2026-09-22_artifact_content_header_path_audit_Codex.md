---
doc_id: "HISTORY-2026-09-22-ARTIFACT-CONTENT-HEADER-AUDIT-CODEX"
title: "Artifact content SHA-256 header path audit"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-22T02:56:00+09:00"
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

## Real local HTTP server check

To check the ASGI/HTTP server layer that TestClient bypasses, a temporary probe launched Uvicorn 0.52.4 on an ephemeral `127.0.0.1` port and sent real HTTP requests with `urllib.request` to both production route aliases. The app was built with `create_app`; authentication used a local test token verifier and `ResultView.download` was replaced with a deterministic 34-byte synthetic artifact. Thus the route, middleware, Uvicorn/h11 server, TCP socket, HTTP header serialization, and client parsing were exercised, but the database/file-read path was not.

Both aliases returned `200`, the full 34-byte fixture body, and the `x-content-sha256` header with a value equal to SHA-256 of the received body. The wire spelling was lower-case; HTTP field names are case-insensitive, and lookup as `X-Content-SHA256` succeeded. The temporary server was stopped in `finally` and the probe reported `server_stopped=True`. One initial attempt failed before app startup because `src` was absent from `PYTHONPATH`; no request/server ran. Adding both `services/control-plane/src` and repository `src` corrected import resolution.

Boundary: this is a local Uvicorn process and synthetic download fixture. It does not include deployment configuration, reverse proxy/load balancer/CDN, TLS termination, cross-origin browser visibility, live database, or a committed artifact read. The legacy fixture's use by an external deployment remains unverified and was not investigated.

## Regression guard and falsification

`tests/core/test_artifact_content_contract.py` now:

1. Exercises both current route aliases with an ordinary request and with `Range` plus `If-None-Match` headers.
2. Requires HTTP 200, the complete expected bytes, and matching `X-Content-SHA256` on every case; it also checks byte length, disposition, nosniff, no-store, and absence of `Content-Range`/`ETag`.
3. Enumerates every current app route containing `/artifacts/content` and requires exactly the two expected paths to resolve to one handler. An added third content route therefore fails the inventory assertion until it is deliberately audited and added to the contract.

The central header line was removed from `artifact_content_response` as a negative control. All four parameterized successful-route cases failed, then the line was restored. This shows that the route tests actually depend on the header guarantee. The route inventory is also an exact-set assertion, so added, removed, or renamed content paths fail rather than silently escaping the checked aliases.

## Provenance

- Base SHA: `3ebbe960f8136318a16427c248d8345172805a12`.
- Implementation SHA: `b9f8212a2124a852aeaaf95a8e435e475d803cdb`, pushed to `agent/codex/artifact-content-header-audit` and fast-forwarded to `integration/all-agents-unified`.
- Branch: `agent/codex/artifact-content-header-audit`.
- Worktree: `C:/Project/SaintVision-Invion`.
- Interpreter: `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe`, Python 3.14.6.
- OS: Windows 11; environment gates at invocation: PostgreSQL DSN absent, Docker present, Go absent, Node v24.17.0.
- Initial pass run before the negative control, KST `2026-09-22 02:42:15`: `.venv/Scripts/python.exe tools/provenance.py --executor Codex -- .venv/Scripts/python.exe -m pytest -q tests/core/test_artifact_content_contract.py`; exit 0, 13 passed, 2 warnings.
- Header-removal mutation, KST `2026-09-22 02:43:26`: `.venv/Scripts/python.exe tools/provenance.py --executor Codex -- .venv/Scripts/python.exe -m pytest -q 'tests/core/test_artifact_content_contract.py::test_artifact_content_route_returns_raw_bytes_bound_to_contract_headers'`; exit 1, 4 failed as expected, 2 warnings. The production line was restored immediately afterward.
- Post-restoration pass, KST `2026-09-22 02:44:07`: same full-file command, exit 0, 13 passed, 2 warnings. `check_docs.py` and `check_ontology.py` also exited 0. `sync_obsidian.py --check` exited 0 with 1500 managed files, 3 pending exports, 0 conflicts; these are the three task documentation files listed in this work item.
- Post-commit pass at implementation SHA, KST `2026-09-22 02:45:20`: same full-file command, exit 0, 13 passed, 2 warnings. Provenance recorded a dirty worktree because another worker had modified `apps/web/src/shared/ui/Header.tsx`; that file was not part of this commit and was left untouched. The implementation commit was pushed to the task branch and fast-forwarded to integration. Integration advanced immediately afterward with a separate Claude documentation commit; the Codex follow-up record was replayed on that new tip in an isolated worktree.
- Final integrated-candidate pass, KST `2026-09-22 02:47:09`: from clean detached worktree `C:/Project/SaintVision-Invion/.worktrees/codex-artifact-header-final`, provenance SHA `69a583d208eb3cde0fa109f03ee2dc61b25a3d7e`, the full focused test file exited 0 with 13 passed and 2 warnings. `check_docs.py` exited 0 (701 versioned documents). `sync_obsidian.py --check` reported 1501 managed files, 2 pending exports, 0 conflicts after the newer upstream docs landed. Those plus the updated audit history were then exported: 3 files, all 1501 destination hashes match; a final check returned 0 pending/0 conflicts.
- Follow-up to test response-state mutations from the user's review: `artifact_content_response` was temporarily changed to emit status 206, then 304. The four route/request combinations failed in each variant (4 failed, exit 1), proving the existing `status_code == 200` and full-body assertions detect partial and bodyless success responses independently of the route inventory. Both variants were restored. During the 304 run, Gemini's unrelated browser-acceptance commit `4e9be86c5a5d9539f03608f80e9ee1945568d3bb` landed on integration; no Gemini files were modified by Codex. After restoration, that exact clean integration SHA passed the full focused file: `.venv/Scripts/python.exe tools/provenance.py --executor Codex -- .venv/Scripts/python.exe -m pytest -q tests/core/test_artifact_content_contract.py`, KST `2026-09-22 02:51:36`, exit 0, 13 passed, 2 warnings. `check_docs.py` also passed at the same SHA (702 versioned documents).
- Real Uvicorn HTTP probe, KST `2026-09-22 02:55:10`, integration SHA `dbb76517bdb0c346b6cfd455f4ff3ef99ebac259`, branch `integration/all-agents-unified`, Python `.venv/Scripts/python.exe` 3.14.6, Uvicorn 0.52.4. Command was `.venv/Scripts/python.exe tools/provenance.py --executor Codex -- .venv/Scripts/python.exe <temporary probe>` with `PYTHONPATH=services/control-plane/src;src`; exit 0. The temporary probe sent real local HTTP requests to both aliases; each got 200, 34 bytes, correct digest, and Uvicorn stopped. Provenance recorded unrelated uncommitted Gemini files; Codex did not change them. The initial missing-import-path attempt exited 1 before starting the server and is not counted as a request result.
- Executor: Codex, author-run; independent review pending. This is not browser acceptance or deployed HTTP verification.

## Next action

Request independent review at the integration tip containing this server check. Browser/deployed HTTP acceptance remains a separate boundary.
