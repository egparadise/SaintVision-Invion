---
doc_id: "EVIDENCE-FLEET5-CSP-STATIC-VALIDATOR-R1-CODEX"
title: "FLEET5 CR-CSP-01 canonical static validator correction"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-08T01:42:11+09:00"
source_of_truth: "Git"
---

# CR-CSP-01 source correction and handoff

Owner Codex; actual independent Claude review is Root-owned and pending. Base `96afd799d49717fd40e4ddabd538d82accbe1958`; branch `agent/codex/fleet5-csp-static-validator-r1-20261108`. Root524 management source `76c06dc8f9e93250e6045383891e266c6aa2a747` was read separately from this branch's older boards. This branch must never export the old whole vault. Task and dispatch IDs, read pins, KST and the NEW full canonical-state snapshot are in `context.json` and `read-pins.json` here.

The real PC3 Chrome157 failure was Ajv.compile at module import under the canonical script-src self policy. Named public Root diagnostics are preserved here. No actual credential POST, user Run or successful new production UI was proven by that failure. Root's b48 rollback is temporary prior-state recovery. This task changes no operator/deployment state.

## Correction

The browser imports only a standalone validator and its pure format/runtime helpers. The generator uses Ajv2020 strict:false, full addFormats and the EXACT canonical core schema plus its original ProjectNodeCertificateObservationResponse reference. No duplicate or reduced schema is introduced. The rest of nodeCertificateObservation.ts is unchanged, retaining all freshness, project, duplicate, unknown trust, full observation, microsecond expiry, summary and transition semantics. Source audit found no other browser-source Ajv import/compile path.

Standalone output is an ephemeral build product, intentionally ignored beside a tracked type declaration. Every npm dev/lint/test/build/eval entry regenerates it. Docker already uses npm run build, so it also generates before TypeScript/Vite. No install hook or Main execution is added. Existing contracts:generate/ contracts:check now include generation/exact byte drift verification. A deterministic manifest pins canonical schema bytes, generator bytes, complete lock bytes, locked Ajv/formats versions and validator bytes; no timestamps or machine paths. The output is included in the official CSP evidence artifact. Vite bundles local CommonJS and pure helpers; a built source-map audit rejects Ajv compiler modules. Dependencies/lock/schema/security headers remain unchanged.

## Regression evidence to collect on exact candidate

- A VM realm forbids string and Wasm code generation for the standalone file AND recursively loaded JS helpers; negative eval/new Function controls must throw before the fixture is validated.
- Canonical provider fixture must pass; date-time format fields, ID formats and the canonical 200-item bound must reject malformed data. Date.parse-compatible non-RFC3339 dates ensure formats were not dropped.
- Existing observations tests remain, with new malformed shape, enum, integer, invalid calendar date, project, freshness, false summary, disabled/incomplete, and precision overflow cases. Existing microsecond/duplicate/polling/no-blink/session tests are retained unchanged.
- An isolated output-directory test proves deterministic generation and refusal of missing output, modified validator and modified manifest, followed by regeneration equality.
- Hosted ordinary-sandbox Chrome loads the ACTUAL dist bytes served with exact canonical CSP/security-header values. A separate external probe proves eval/Function are blocked by that header. Then the actual anonymous app must render the login h1/button, fetch JS/CSS/auth-config successfully, raise no page/CSP errors, and issue GETs only. No login click, credential, synthetic healthy state or user Run. This loopback HTTP browser fixture does not prove deployed TLS/Nginx/PC3 acceptance.

Frontend workflow retains all existing lint/test/type/drift/build, dist and hardened-container/TLS smoke steps and adds the hosted anonymous strict-CSP browser gate plus public output evidence artifact. Documentation requires all19 steps. Final exact SHA, official run/job/step/attempt/correlation and artifact digests are published in the post-CI delivery JSON in this directory. Genuine failures, if any, are preserved there. No Backend/Core rebuild is claimed: protected component object pins and diffs against96 are in protected-components.json; source96 accepted backend/Core evidence is inherited only.

## Verification and next owner

Main executes only allowed source/AST/hash/data/docs checks; actual Node/npm/build/test/browser run in hosted CI. local-gates.py records each of eight gate commands and immediate exit, then copies full canonical sync-state bytes after --check and compares with the NEW before snapshot. Root alone owns APPLY. Post-CI receipt can remain untracked for Root publication to avoid self-referential SHA claims.

Root first verifies published exact source/artifacts, starts the one actual Claude review, and after acceptance stages the exact new dist/image and rechecks ordinary-sandbox PC3 Chrome with unchanged strict CSP. Actual authenticated API/no-blink/resource checks, two distinct real nonrequester approvals, requester enqueue, genuine Run/output and all5/GPU/storage/renewal/reconnect/reboot acceptance remain Root-only live gates. CR90501 stays closed and unchanged. Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN remain unchanged; this is not whole-program completion.

Public implementation reference: [Ajv standalone validation](https://ajv.js.org/standalone.html). Hosted Chrome availability: [official runner image manifest](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md); actual version is measured in CI.

Pre-push local source/docs verification: all eight gates exited0 after correcting three new wiki targets from page titles to real filenames; the initial docs failure is preserved in local-gates-initial-broken-links.json. Sync CHECK reports2394 pending exports/0conflicts in this older branch view, performs no writes, and the full522559B state remains byte-identical. This is not an APPLY or latest whole-vault sync success.
