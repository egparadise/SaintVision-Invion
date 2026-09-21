---
doc_id: "UI-FB03-CODEX-REVIEW-001"
title: "UI-FB-03 DeveloperStudio boundary review"
version: "1.1.0"
status: "reviewed"
author: "Codex"
reviewer: "Codex"
updated: "2026-09-21T17:32:00+09:00"
source_of_truth: "Git"
---

# UI-FB-03 DeveloperStudio boundary review

## Scope and decision

Initial review of Gemini's UI-FB-03 implementation at `5e2a5339d5297ce6d4f9210f11de9173953343bf`, merged locally after `c0436f6`, found a click-time cached-payload failure. The review covers source and happy-dom/Vitest DOM behavior only, not browser or deployed-backend acceptance. The finding and subsequent closure are recorded below.

## Source finding

In `DeveloperStudio.tsx`, `handleDownloadArtifact` probes `/result`, and only a route-only 404 probes `/artifacts`. That route distinction is correct. However, after any other `/result` error, `serverPayload` remains null and `const effectivePayload = serverPayload || artifactData` reuses the payload loaded by the earlier successful mount. The handler then proceeds to build/download a manifest when the cached payload has an `outputHash`. A 401, 403, 5xx, malformed response or network rejection can therefore be hidden from the user during the download action. The existing label may still reflect an earlier successful fetch; the action neither clears nor qualifies that state.

The new five download DOM cases prove the `/artifacts` endpoint is not called for four non-route failures and is called for route-only 404. They do not assert a visible error, that `URL.createObjectURL` is not used, or that no download occurs after a failed probe. Because each case first mounts with a successful `/result`, `artifactData` is populated and the fallback path is available. The required follow-up is a before/after-success scenario that fails `/result` during the click and asserts the intended contract: non-route failure is visible and does not create/download a new artifact; route-only 404 alone may use `/artifacts`, and that fallback remains explicitly UNVERIFIED.

This is a review finding, not a UI code change by Codex. Gemini owns implementation and must decide whether cached successful data may be downloaded after a failed revalidation; if allowed, the UI must expose that distinction rather than silently treating the probe as successful.

## Evidence

- Source-reviewed: result-first route and `isRouteNotFoundError` guard; cached `artifactData` fallback; two download buttons and new DOM probes.
- Executed before the later error-exposure probe: from `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration/apps/web`, `npm test -- --run tests/developer-studio-dom.test.tsx` exited 0: 1 file, 13 passed. Start time shown by Vitest: 2026-09-21 16:48:02 KST. This was a dirty merge candidate based on local `d590b4a` plus incoming `5e2a533`; it was not run through `tools/provenance.py`, and no fixed merged SHA existed yet.
- Falsifiability probe at clean SHA `28fd8dba5ffed0b442e428f31c2d8416743cacab`: temporarily added `expect(window.alert).toHaveBeenCalled()` to the existing successful-mount-then-401 download case. The focused test failed exactly there (1 failed/12 skipped, exit 1): no error was surfaced. Removed the temporary assertion; restored focused DOM suite then passed all 13 at 16:59:26 KST through the provenance wrapper. Working tree returned clean. This behavior confirms the cached `artifactData` fallback is live, not merely a source-level possibility.
- Not run: full Vitest after `5e2a533`, browser acceptance, live HTTP, deployed backend, or Actions.

## Handoff at initial review

Next owner: Gemini. Add the click-failure assertions above and perform before/after mutation checks for both fallback allowance and non-route suppression. Codex will re-review the fixed SHA. Keep browser acceptance separate from the DOM test result.

## 2026-09-21 Gemini follow-up review closure

Reviewed Gemini's fix at integration commit `beff6c1` and rechecked from the updated integration content at `614501a`. In `handleDownloadArtifact`, every click requests canonical `/result`; non-route errors alert and return, route-only 404 alone reaches `/artifacts`, failed fallback alerts and returns, and `effectivePayload` is `serverPayload` only. A stale successful `artifactData` cache cannot satisfy a later failed download probe. A successful route-only 404 remains marked `fallbackUsed` and the UI labels it UNVERIFIED.

The exact earlier defect is now a resident DOM scenario: the mock returns a valid result on component mount, then a 401 after the download button is clicked. It asserts `/artifacts` is called zero times, the authorization error is visible, and `URL.createObjectURL` is not called. Codex ran `node node_modules/vitest/vitest.mjs run tests/developer-studio-dom.test.tsx` on integration SHA `614501aacbc029688d98c7718c88eddebee1d3`; 1 file / 18 tests passed (17:21:51 KST). The worktree had unrelated `ResourceExplorer.tsx` edits; the reviewed DeveloperStudio source and test were unmodified. Source and tests also cover 403/500/network/app-404 suppression, route-only 404 fallback, legacy-fallback failure, missing-receipt no-banner, and raw-download failure without a synthesized Blob.

Gemini's History report `2026-09-21_UI_FB03_DeveloperStudio_DOM_라우트404폴백검증_Gemini.md` records the mutation checks: restoring all-error fallback causes five click scenarios to fail, while disabling the required route fallback causes its paired scenario to fail; receipt checks also have positive/negative mutations. Codex reviewed that report but did not rerun those mutations. The source review and focused 18-case normal run support approval of the component-level DOM contract. Browser/OS file download, live HTTP, deployed backend, CI, and operational acceptance remain unverified and are not approved by Vitest.

Decision: **UI-FB-03 component boundary approved by Codex at source commit `beff6c1`; browser acceptance remains separate.**
