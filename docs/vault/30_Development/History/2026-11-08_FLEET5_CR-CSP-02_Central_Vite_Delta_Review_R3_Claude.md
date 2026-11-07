---
doc_id: "HISTORY-FLEET5-CSP02-CENTRAL-VITE-DELTA-REVIEW-R3-20261108-CLAUDE"
title: "CR-CSP-02 central main-Vite startup delta review R3"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-08"
source_of_truth: "Git"
---

Task CR-CSP-02 central Vite delta review R3 (Orca task_ce91b9bbce0b). Claude is the actual independent reviewer, the author is Codex task_83732e149ebb, and Root is the sole APPLY owner. The delta runs `cc6076254d5b8f54804081a8b1994d76d86cf81a` → `e4e07bfd6b94e57edc64d158e208df01b9319deb` (through `2c6bbdbe`), the backend stays `96afd799`, and the Root checkpoint is `a5e8bd98141e6f81887c8dca9956da525fe99d33`. Review branch: `agent/claude/fleet5-csp02-central-vite-delta-review-r3-20261108`, created from my R2 head `63f3eeb661c565d864e14c2395f68c6715d109c0`. Pins are in [review](../Evidence/fleet5-csp02-central-vite-delta-review-r3-20261108-claude/review.json). Everything sound from R1/R2 is inherited unchanged.

**Verdict: ACCEPT_CR_CSP02_CENTRAL_VITE_DELTA_KEEP_MANUAL_AND_REAL_DEPLOYMENT_GATES, mandatory defects 0.** My R2 residual, the direct `node vite.js` launch of the main config, is closed at the source.

- **Main Vite config:** `apps/web/vite.config.ts` now runs the same reviewed generator synchronously at module top level, before `defineConfig`. Vite evaluates the config before any dev server, build or preview, and Vitest uses it too, so every main-config start produces the canonical ESM. That includes the launcher's `vite.js` (auto-loaded from `apps/web`) and the npm callers. A generator failure aborts config load, so Vite never listens. No launcher, generator, lock, CSP, contract or backend object changed.
- **Direct-launch proof:** the new target script verify_vite_direct_launch.py (exists only at e4e07) runs only on hosted Linux and requires both untracked outputs absent before it starts. It deletes nothing, starts the real direct `vite.js` command without npm on its own port and process group, and requires the outputs to appear with a matching manifest. Real sandboxed Chrome must show the login UI, the validator module must return 200, and errors, non-GET requests and HTTP failures other than the exact `favicon.svg` 404 fail it. It runs before every npm hook, so what it observes can only come from the config. The same script would fail at cc607, matching Root's PC3 reproduction.
- **Workflow:** the step order is setup, direct proof, then lint/test/build/strict-CSP. Frontend 42404194858 passed 19 + 14 steps.
- **Test wait:** the test blob is cc607 plus exactly one line, a wait on the existing 2000 ms `untilVisible` helper before the unchanged not-null assertion. The authored patch hashes to the Root-approved `736cd6ca…4379`. The panel renders that select only after its async load, so the wait is correct synchronization and does not weaken the test. The original 2c6bbdbe failure (Frontend 42403333297, 1350/1) is retained, and the race explanation stays a hypothesis.

Checks I ran: git diffs; object ID and SHA-256 comparisons against cc607 and Root pins; source reads of the proof, workflow and panel; Root input pins; and `gh run view` of Frontend (with steps), Docs 42404197444 (19), AC11 42404200030 (14) and the failed first candidate. Local docs gates are in [local gates](../Evidence/fleet5-csp02-central-vite-delta-review-r3-20261108-claude/local-gates.json), and the full canonical byte comparison is in [sync state](../Evidence/fleet5-csp02-central-vite-delta-review-r3-20261108-claude/sync-state-comparison.json). I ran no Node, npm, Vite, browser, Docker, pytest, DB or product execution on Main.

Retained gates: Root's exact-e4e07 PC3 strict-CSP deployment with a real Chrome login/no-blink/resources check, and AC11 manual user-device acceptance. The normalized AC11 report stays MEASURED_FAIL solely because manualAcceptanceMissingCount is 1; that is not a pass and not a code defect. Also retained: real votes, Run/output/audit, PC1 key, PC5 RAM/Node, GPU/storage, all five PCs and renewal/reconnect/reboot. All earlier genuine failures are kept. CR-905-01 remains CLOSED. Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN unchanged.

Next action: Root verifies the originals, deploys the exact e4e07 artifact and tests it in a real PC3 browser.
