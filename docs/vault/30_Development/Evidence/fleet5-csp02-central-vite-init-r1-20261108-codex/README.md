---
doc_id: "EVIDENCE-FLEET5-CSP02-CENTRAL-VITE-INIT-R1-CODEX"
title: "FLEET5 CR-CSP-02 central main Vite initialization"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-08T03:48:26+09:00"
source_of_truth: "Git"
---

# Central correction for the shipped direct launcher

Owner Codex; base cc6076254d5b8f54804081a8b1994d76d86cf81a; branch agent/codex/fleet5-csp02-central-vite-init-r1-20261108. Root528 source6c12a9f1c74a5d9f6d4bce139ed6ee0a084f98fe and actual Claude R2 source63f3eeb661c565d864e14c2395f68c6715d109c0 were read as public immutable inputs. Sound R1/R2 ESM/schema/full-format/semantic/15-test/fixture/CSP findings are inherited without rewriting them. Root starts one actual review of this central-config/new-proof delta only after this worker settles/exits/releases. Context, read pins, review and public repro copies are in this directory; root public raw bytes are archived separately from readable JSON.

## Actual failure kept separate

Root's fresh isolated public-source cc607 repro at03:33:02KST actually returned index200 but required source module500 with unresolved generated ESM, absent both before/after. Archive5089280B/SHA256b62dbe1b9dcb9cbb08fc651b61a5123f794fd21cb51ed8e8e651d99800e7fcc8; owned probe stopped, services/credentials/API/DB/user/Run/votes untouched. This author never reruns that baseline or SSH. Named public receipt/program copies and raw hashes are pinned. Older428e default-export baseline,8e3f VM flag failure,3bd4/6 browser measurement are retained at their immutable sources and in inherited-failure-pins.json, not reclassified as success.

## Small source change and actual fresh regression

The main apps/web/vite.config.ts now calls the SAME existing generator synchronously using process.execPath and an absolute generator path, --write, before defineConfig can return. A thrown generator failure aborts Vite before readiness, and every new main-config load regenerates missing or stale output. This is the inherited fixture's fail-closed mechanism applied centrally; no launcher argv, lifecycle or health code is edited. Generator, .mjs format/declaration, deterministic manifest, lock, canonical schema, all app source/semantic-tail bytes, fixture config,15 cases, AC11 policy/workflow and strict CSP are byte-identical to cc607.

The new hosted regression runs AFTER npmci but BEFORE any lint/test/build/dev npm hook. It asserts both ignored files are absent in the owned clean checkout and tracked output list empty; it deletes no file. It starts direct node node_modules/vite/bin/vite.js with the MAIN config and loopback strict port, records argv/config/source hashes and missing-before/generated-after manifest/output hashes, and requires actual ordinary-sandbox Chrome to render the anonymous login h1/button. The required generated module must return200, all page/module/network errors fail except the already accepted exact favicon404, GET-only requests and owned live Vite are checked, and only its owned process session/browser is stopped. Index200 alone never passes. No credential form action, real backend or operational acceptance is involved. Existing built-dist strict-CSP eval/Function negative controls and all previous frontend tests remain.

## One-pass supported launcher/config audit

A single tracked-source inventory covers deploy/tools/tests/.github/apps and records all matches/context in tracked-launch-audit.json, plus the focused raw grep. It found exactly two Vite configs: main and tests/browser fixture. Non-launching source tests/comments/assets are classified rather than treated as new operator entry points.

| Supported caller | Config selected | Fresh/stale-generation guard at a new start |
|---|---|---|
| deploy/lan/Start-LiveConsole.ps1 direct node vite.js | main apps/web/vite.config.ts | New unconditional synchronous SAME generator --write before config export/listener; exceptions abort load |
| deploy/lan/Register-DesktopShortcut.ps1 / Card289 | Start-LiveConsole -> main | Same central guard; shortcut and launcher argv unchanged |
| deploy/studio/Start-Environment.ps1 and Register-EnvironmentStartup.ps1 | Start-LiveConsole -> main | Same central guard; existing service lifecycle/health logic untouched |
| tools/run_s02_real_api_acceptance.py start_frontend | npm dev -> main | Existing predev plus central guard |
| tools/run_s04_fe_matrix.py start_frontend | npm dev -> main | Existing predev plus central guard; existing NODE_OPTIONS untouched |
| AC11 desktop-invariants step | npm dev -> main | Existing predev plus central guard; workflow/normalizer/assertions/30min unchanged |
| tests/integration/test_approval_browser.py browser_page, reused by desktop/Studio journeys | direct vite.js -> tests/browser/vite.config.ts | Inherited fixture's synchronous SAME generator --write before graph |
| normal npm dev | main | predev plus central guard |
| normal npm build / direct Vite build with main config | main | prebuild before tsc for npm; central guard before Vite bundles in either case |
| normal npm lint | no browser config needed | prelint writes canonical output; lint still checks source |
| normal npm test / npm eval:check | Vite/Vitest main config | pretest/preeval hooks plus central guard; inherited 15 cases and parser flag unchanged |
| npm contracts:generate / contracts:check | generator CLI | Explicit write / exact drift check; missing or stale output fails check |
| npm preview | main, serves built dist | Config refreshes source output; preview still requires the already-built artifact and does not rebuild it |
| apps/web/Dockerfile, deploy/intranet/portal/Dockerfile, Frontend and desktop-browser workflows, tools/deploy_intranet.ps1 | npm build -> main | Existing build hooks plus central guard; no deployment script/argv edits |
| tools/run_real_browser_acceptance.py and verify_desktop_observation_browser.py | Consumers of an already-started server | Do not launch Vite; startup guard belongs to their caller, not an invented new command |


These guards run when a config is loaded, not inside a preexisting listener. S02/S04 and operator helpers can reuse an already-running listener under their existing logic; this task does not claim to refresh or restart it. Root owns controlled cutover and actual browser acceptance. Existing index-only checks remain transport checks; the new hosted proof explicitly verifies the real browser graph. No arbitrary unsupported command gates were added. Audit is source coverage; this task does not claim fresh S02/S04/operator/Windows execution.

## Verification and handoff

Main executes only permitted Git/source/AST/JSON/hash/docs metadata. local-gates.py records all eight lightweight commands with immediate exit and stops nonzero. NEW full canonical-state baseline 536738B/SHA2566d699b94160c7a323502e3547ecdec7379e9c3d8238fd0ec1a1de738957cc6cc is copied at task start; historical534872/529870B snapshots are not this baseline. End/afterCI --check and raw byte comparison must match within this window. Root alone owns APPLY; old-branch pending exports do not authorize exporting its whole vault.

Exact corrected-head workflow_dispatch/manualattempt1 Frontend, Docs(all19) and unchanged AC11 require unique correlations and every actual job/step success. Raw1351 Vitest counts,6 actual browser cases/5 journeys/9 invariants and artifact ZIP digests are checked, not just green job colors. Normalized AC11 must keep manualAcceptanceMissingCount1/MEASURED_FAIL until genuine same-SHA user-device acceptance. The official direct evidence artifact must prove missing-before and render success; its manifest must match canonical inputs and later strict-CSP/built-dist evidence. Any genuine candidate failure is preserved at its source; no blind same-head redispatch. Backend/Core96 runs are inherited only because protected product trees remain identical, never claimed as new-head executions.

Published task source/docs/History are paired with Root-ready public postCI delivery.json, official metadata/artifacts, exact diff/component/semantic/manifest/dist pins and full canonical-state proof; postCI files may remain untracked to avoid self-reference. Root first verifies exact delivery and starts one actual central-only Claude delta review inheriting sound R1/R2. After acceptance Root alone deploys/restarts the correct artifact/config under unchanged strict CSP and checks PC3 login/no-blink/resources/API. Oldb48 recovery/API96/schema0068/observer/genuine ready Workspace remain operator-owned. Manual user-device acceptance, two genuine distinct nonrequester approvals/Run/output/audit, PC1key/PC5RAM+Node, GPU/storage/all5/renewal/reconnect/reboot are separate live gates. CR90501 CLOSED and Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN unchanged; no whole-program completion.
