---
doc_id: "HISTORY-FLEET5-CSP-STATIC-VALIDATOR-REVIEW-R1-20261108-CLAUDE"
title: "CR-CSP-01 static validator correction independent review R1"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-08"
source_of_truth: "Git"
---

Task CR-CSP-01 static validator review R1 (Orca task_9989fc85304e). Claude is the actual independent reviewer, the author is Codex task_1b0f4d26fa63, and Root is the sole APPLY owner. The target is `428e5fc6b822d33e7e76316f443716b03579efa0` (after `8ee1e5222b451935a96b2b74bafaba1667424375`) on the accepted base `96afd799d49717fd40e4ddabd538d82accbe1958`, and the Root checkpoint is `5e516c57da27322946acbcac4295b650b41b8ed2`. Review branch: `agent/claude/fleet5-csp-static-validator-review-r1-20261108`, created from `86acd9816f3ba397d02a07e90d2e912e414b1bac`. Pins, the causal chain and the per-area results are in [review](../Evidence/fleet5-csp-static-validator-review-r1-20261108-claude/review.json).

**Verdict: CHANGES_REQUIRED_ONE_BOUNDED_DEV_ENTRY_POINT_DEFECT_KEEP_REAL_DEPLOYMENT_GATES.** The production strict-CSP correction is sound. The generator uses the same draft2020 options, full formats and canonical `$ref` as the former runtime code, and its manifest pins match the 428e blobs. The semantic tail is byte-identical to 96, and the protected trees and package-lock are unchanged. The built source maps contain no Ajv compiler, and the hosted verifier checks headers, the sandbox, the eval/Function negative control and the real anonymous boot. Its favicon exception is limited to an exact URL with status 404 that is already absent in 96. The 14 new regressions are meaningful. CR-CSP-01 is not closed, because of one mandatory defect.

CR-CSP-02 (Medium) is a regression of the dev entry point, and it rests on static evidence; I did not execute it. The browser now default-imports a local CommonJS `.cjs` file, and `vite.config.ts` only converts it under `build.commonjsOptions`. In the locked Vite 6.4.5, `.cjs` is not a known JS source, so dev serves it unconverted with `?import`, and no dev plugin converts local CommonJS (`dep-CkSfqg8D.js` 6615, 40653-40661, 37536, 40930-40990, 46300-46307). Under `npm run dev`, linking `App.tsx`'s import of `nodeCertificateObservation` therefore fails with a missing default export, and the app does not render. That breaks the live AC11 accessibility e2e dev lane (`ac11-accessibility-e2e.yml:75`) and the S02/S04 acceptance tools. Base 96 booted under dev because it imported bare dependencies that Vite pre-bundles.

Hosted CI did not catch this: Vitest runs in Node, build applies the CommonJS plugin, and no run at 428e starts the dev server. The bounded correction is for the browser-imported module to be ESM with no `require()` or `module.exports` under both dev and build, with every generator, manifest and drift property kept. Ajv `code.esm` alone still emits `require()` for its format and runtime helpers, so it is not sufficient on its own. The fix also needs a meaningful regression plus a hosted dev-path boot proof. Root decides on the confirmation dispatch; the command is in review.json.

Checks I ran: git show/diff and tree-OID and blob SHA-256 comparisons; static reads of the locked Vite, Ajv and ajv-formats dist; `gh run view` of Frontend 42393304702 (attempt 1, 14 + 17 steps all success) and 42392904251 (failure only at the strict-CSP boot step, the favicon 404); and Root input pins. Local docs gates are in [local gates](../Evidence/fleet5-csp-static-validator-review-r1-20261108-claude/local-gates.json) and the full-byte sync comparison is in [sync state](../Evidence/fleet5-csp-static-validator-review-r1-20261108-claude/sync-state-comparison.json). I ran no Node, npm, Vite, browser, Docker, pytest, DB or product execution on Main. Hosted results are official runs, not my executions.

Retained gates: Root's actual PC3 strict-CSP deployment with a real Chrome recheck (boot, login, no-blink, resources), real votes and Run/output/audit, PC1 key, PC5 RAM/Node, GPU/storage, renewal/reboot and five-PC acceptance. CR-905-01 remains CLOSED. Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN unchanged.

Next action: Root dispatches CR-CSP-02 to the Codex author lane. After exact-SHA hosted Frontend/Docs and a hosted dev-path boot, one actual Claude reviews that delta only.
