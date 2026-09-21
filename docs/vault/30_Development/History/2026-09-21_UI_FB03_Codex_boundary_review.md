---
doc_id: "UI-FB03-CODEX-REVIEW-001"
title: "UI-FB-03 DeveloperStudio boundary review"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "pending Gemini follow-up"
updated: "2026-09-21T16:49:00+09:00"
source_of_truth: "Git"
---

# UI-FB-03 DeveloperStudio boundary review

## Scope and decision

Reviewed Gemini's UI-FB-03 implementation and its follow-up download-action probe in `5e2a5339d5297ce6d4f9210f11de9173953343bf`, merged locally after `c0436f6`. The review covers source and the happy-dom/Vitest DOM harness only. It is not a browser acceptance or deployed-backend check. Independent approval remains pending because a non-route download failure can fall through to cached `artifactData` without surfacing the error.

## Source finding

In `DeveloperStudio.tsx`, `handleDownloadArtifact` probes `/result`, and only a route-only 404 probes `/artifacts`. That route distinction is correct. However, after any other `/result` error, `serverPayload` remains null and `const effectivePayload = serverPayload || artifactData` reuses the payload loaded by the earlier successful mount. The handler then proceeds to build/download a manifest when the cached payload has an `outputHash`. A 401, 403, 5xx, malformed response or network rejection can therefore be hidden from the user during the download action. The existing label may still reflect an earlier successful fetch; the action neither clears nor qualifies that state.

The new five download DOM cases prove the `/artifacts` endpoint is not called for four non-route failures and is called for route-only 404. They do not assert a visible error, that `URL.createObjectURL` is not used, or that no download occurs after a failed probe. Because each case first mounts with a successful `/result`, `artifactData` is populated and the fallback path is available. The required follow-up is a before/after-success scenario that fails `/result` during the click and asserts the intended contract: non-route failure is visible and does not create/download a new artifact; route-only 404 alone may use `/artifacts`, and that fallback remains explicitly UNVERIFIED.

This is a review finding, not a UI code change by Codex. Gemini owns implementation and must decide whether cached successful data may be downloaded after a failed revalidation; if allowed, the UI must expose that distinction rather than silently treating the probe as successful.

## Evidence

- Source-reviewed: result-first route and `isRouteNotFoundError` guard; cached `artifactData` fallback; two download buttons and new DOM probes.
- Executed: from `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration/apps/web`, `npm test -- --run tests/developer-studio-dom.test.tsx` exited 0: 1 file, 13 passed. Start time shown by Vitest: 2026-09-21 16:48:02 KST. This was a dirty merge candidate based on local `d590b4a` plus incoming `5e2a533`; it was not run through `tools/provenance.py`, and no fixed merged SHA existed yet.
- Not run: full Vitest after `5e2a533`, browser acceptance, live HTTP, deployed backend, or Actions.

## Handoff

Next owner: Gemini. Add the click-failure assertions above and perform before/after mutation checks for both fallback allowance and non-route suppression. Codex will re-review the fixed SHA. Keep browser acceptance separate from the DOM test result.
