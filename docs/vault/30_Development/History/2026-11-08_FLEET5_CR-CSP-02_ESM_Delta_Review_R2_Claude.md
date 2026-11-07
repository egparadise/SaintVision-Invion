---
doc_id: "HISTORY-FLEET5-CSP02-ESM-DELTA-REVIEW-R2-20261108-CLAUDE"
title: "CR-CSP-02 require-free ESM dev compatibility delta review R2"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-08"
source_of_truth: "Git"
---

Task CR-CSP-02 ESM delta review R2 (Orca task_0d8a27910659). Claude is the actual independent reviewer, the author is Codex task_e18b8724de5b, and Root is the sole APPLY owner. The delta runs `428e5fc6b822d33e7e76316f443716b03579efa0` → `cc6076254d5b8f54804081a8b1994d76d86cf81a` through `8e3fdbd0` and `3bd660b5`, and the accepted backend is `96afd799`. The Root checkpoint is `3aff6c63ddac3eb68739494d610337c5885f0cda`. Review branch: `agent/claude/fleet5-csp02-esm-delta-review-r2-20261108`, created from my R1 head `4a29b57e6c6ccb75eed50147c00d52d3c8d6ac04`. Pins and reasoning are in [review](../Evidence/fleet5-csp02-esm-delta-review-r2-20261108-claude/review.json). R1's production, semantic, strict-CSP verifier and favicon findings are inherited unchanged.

**Verdict: CHANGES_REQUIRED_CR_CSP02_RESIDUAL_DIRECT_VITE_OPERATOR_LAUNCHER_KEEP_MANUAL_AND_REAL_DEPLOYMENT_GATES.** The ESM correction itself is sound:

- **Generator:** the locked esbuild 0.25.12 bundles the standalone output into self-contained ESM. The generator fails closed on compiler inputs, external imports or a version mismatch, and the manifest pins match the cc607 blobs.
- **Dev server and build:** `npm run dev` now boots (Root's AC11 42398681339, 14/14). The build-only CommonJS option is removed, and the strict-CSP boot still passes (Frontend 42398676174, 14 + 17).
- **Tests:** the 14 prior cases are kept, plus one native-ESM boundary case. The VM loader is a real SourceTextModule in the same no-codegen context, and the worker flag is test-only. Official count is 1351/1351.
- **Fixture:** the directly launched browser fixture now generates fail-closed.
- **Unchanged bytes:** the semantic tail is byte-identical at 96, 428e and cc607. The protected trees, lock and named AC11/browser tools are unchanged.

CR-CSP-02 is not closed, because one shipped dev entry point is still broken. Evidence is static; I did not execute it. `deploy/lan/Start-LiveConsole.ps1:232` starts `node apps/web/node_modules/vite/bin/vite.js` directly with the main config. It is reached directly, through the Card 289 desktop shortcut, or through `deploy/studio/Start-Environment.ps1:20`. npm hooks never run on that path, and the main `vite.config.ts` does not generate. The validator `.mjs` is gitignored and has no install hook, so a freshly installed checkout lacks it. Vite then fails to resolve `@/contracts/node-certificate-validator.mjs` for the eagerly imported `nodeCertificateObservation.ts`, and `#root` stays empty. The launcher's health check only requires HTTP 200 for `/`, so it still reports ready. On a reused checkout, the launcher serves whatever stale generated file is there, with no drift check. Base 96 booted on this path.

cc607 names exactly this mechanism ("launched directly by Node/Vite, so npm's predev hook is not run"), but fixes only the test fixture config. I missed this launcher in R1. The bounded correction is to regenerate fail-closed from the main Vite config, so every main-config start (npm dev, direct vite.js, build) gets the same canonical ESM. Add one meaningful regression for a direct vite.js start from a checkout with no generated file. The reproduction steps are in review.json for Root to run if it chooses.

Checks I ran: git diffs of the three commits; tail, generator and manifest hashes; tree/blob OID comparisons; the lock entry for esbuild; a grep for direct Vite launches and reads of the three launcher scripts; Root input pins; and `gh run view` of the Frontend, Docs, AC11 and 428e baseline runs. Local docs gates are in [local gates](../Evidence/fleet5-csp02-esm-delta-review-r2-20261108-claude/local-gates.json), and the full canonical byte comparison is in [sync state](../Evidence/fleet5-csp02-esm-delta-review-r2-20261108-claude/sync-state-comparison.json). I ran no Node, npm, Vite, browser, Docker, pytest, DB or product execution on Main.

Retained gates: the normalized AC11 report stays MEASURED_FAIL with acceptanceClaim false, solely because same-SHA user-device screen-reader/keyboard manual acceptance is missing. That is an operating gate, not a code defect and not a pass. Also retained: PC3 strict-CSP reactivation with a real Chrome login/no-blink/resources check, real votes and Run/output/audit, PC1 key, PC5 RAM/Node, GPU/storage, all five PCs and renewal/reconnect/reboot. CR-905-01 remains CLOSED. Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN unchanged.

Next action: Root dispatches the residual to the Codex author lane. After exact-SHA hosted runs and a direct vite.js boot proof, one actual Claude reviews only that delta.
