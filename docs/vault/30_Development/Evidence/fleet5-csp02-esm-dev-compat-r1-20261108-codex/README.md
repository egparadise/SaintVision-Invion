---
doc_id: "EVIDENCE-FLEET5-CSP02-ESM-DEV-COMPAT-R1-CODEX"
title: "FLEET5 CR-CSP-02 self-contained ESM dev compatibility"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-08T02:44:28+09:00"
source_of_truth: "Git"
---

# CR-CSP-02 bounded source correction

Owner Codex; new branch `agent/codex/fleet5-csp02-esm-dev-compat-r1-20261108` from exact428e5fc6b822d33e7e76316f443716b03579efa0. Accepted backend source remains96afd799d49717fd40e4ddabd538d82accbe1958. Actual Claude4a29 R1 sound production findings are inherited, not self-reviewed or reopened. Root alone starts one actual bounded delta review after this worker settles/exits/releases. Latest common/own boards were read at Root526/41c3e18ff16d97299567a0403ce018c2ca767ea5, separately from this older source branch. Context/read/public input pins are in this directory.

## Actual baseline and scope

Root's official AC11 baseline42396627296/job128475294431 on unchanged428e, manualattempt1/correlation fleet5-root-csp02-baseline-dev428e-7179ec272d3b4ae9ad2ed1432ee9b3cd, actually FAILED. Vite served local CJS unchanged; the App graph failed to link the missing default export and header locator timed out. Subsequent evidence upload failed because normalization never ran. That consequence is not a second defect. The exact named public final proof/run/jobs were copied before publication; baseline-final-proof includes the official183381B/log SHA2569bdb52a85d19b3e0389ee406b7659bd576b9e8e7d1c55e46f8774e0737ed0553 and observed error lines. Baseline is preserved and never redispatched. Root526's earlier pending snapshot is distinguished from the02:34:05 final proof.

Production strict-CSP correction428e was sound under actual R1. This task only closes the local CommonJS dev entry point defect. Canonical schema, full formats, old semantics, b48 observation guards/no-blink, first Workspace/CR90501, backend/SQL0068/definer/AC11 policy and deployed CSP stay unchanged. No operator/live/API/DB/browser action occurs on Main.

## Implementation and regression

Ajv2020 still compiles the exact canonical draft2020 core $id/$defs response reference using strict:false and full addFormats, now with code.esm:true. Since that alone still emits require references, generation bundles the standalone code and its pure helpers to a self-contained browser ESM with Vite's already locked esbuild0.25.12. No dependency/lock change. The same default-export .mjs is served directly by Vite dev and consumed by Vite build; matching .d.mts, import, exact ignore paths and artifact filename are updated. Obsolete build-only commonjsOptions is removed. Existing predev/prelint/pretest/prebuild/preeval hooks and contracts:generate/check remain, with a deterministic manifest extended by ESM/selfContained, actual locked esbuild version and hashed runtime inputs. Generator rejects compiler inputs/external imports. It writes no timestamps or machine-specific paths.

All14 prior VM/wire/semantic/freshness/drift cases remain. The VM loader now parses/links/evaluates the ACTUAL generated ESM with SourceTextModule in the same strings:false/wasm:false realm and rejects any external dependency. eval/Function negative controls and full-format malformed values still run there. npm test enables Node's VM module parser only; code-generation restrictions, existing tests, counts and timeouts are not weakened. One additional case walks the actual output syntax for raw require/module.exports and uses a cold native Node ESM import to prove a usable default export with the canonical fixture. Drift checks still reject missing/tampered validator/manifest and prove exact regeneration equality. This catches the old .cjs boundary rather than mocking/transpiling it into success.

Frontend retains the existing ordinary-sandbox strict-CSP built-dist Chrome gate, eval/Function controls, compiler absence, exact favicon404-only exception and all previous hardened runtime steps. Only its generated evidence filename changes. Existing AC11 workflow/30min timeout/normalizer/assertions/five journeys/six cases/nine invariants remain byte-identical and must execute on the corrected exact source. AC11 is an existing isolated dev fixture, not real production auth/votes/hardware. Its existing browser launch settings are inherited unchanged; the separate production strict-CSP smoke retains its ordinary sandbox.

## Verification and delivery

Main performs only source/Git/AST/JSON/hash/docs checks, never Node/npm/build/pytest/app/browser/crypto/product execution or setup. local-gates.py records eight sequential lightweight commands with immediate exit, full stdout and check-only state comparison. NEW CURRENT canonical baseline is 529870B/SHA25643600e1941cb3527e80adc2daac2064c53a44d129094da53869e6f50d46e334e; old Root525/review snapshots are not reused. Root alone may APPLY. Stale branch pending exports are reported as that view, never as permission to export the older whole vault.

Exact corrected-source Frontend, Docs(all19) and AC11 workflow_dispatch/manualattempt1 require unique correlations and all actual jobs/steps success. ci-receipts.py dispatches/binds only those existing hosted workflows; it never redispatches the baseline. Any first corrected-source failure must be kept distinct and fixed at a new real head. Public postCI delivery.json/official receipts/artifact ZIPs/digests/diff/manifest/dist pins are Root-ready after success and may remain untracked to avoid a self-referential final-SHA claim. Tracked source/History/Evidence are published at the corrected source SHA. Protected component pins and semantic-tail byte equality to96/428e are in protected-components.json. Backend/Core96 evidence is inherited only, not rerun or claimed on the corrected SHA.

Root's first action is to verify final exact source/artifacts and start one actual Claude bounded delta review inheriting sound R1; after acceptance Root alone deploys the exact dist/image with unchanged strict CSP and checks real PC3 login/no-blink/resources/API. Oldb48 recovery/API96/0068/realPC2/3/4 measurements/genuine ready Workspace version2 nodeNULL and first-intents items0 remain operator-owned. No Run/votes are created. Two distinct real nonrequester approvals, genuine requester enqueue/Run/output/audit, PC1key/PC5RAM+Node, GPU/storage/all5/renewal/reconnect/reboot remain live gates. Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN unchanged; whole-program completion is not claimed.

Primary API references: [esbuild bundle API](https://esbuild.github.io/api/#bundle), [Node VM modules](https://nodejs.org/api/vm.html#class-vmsourcetextmodule).
