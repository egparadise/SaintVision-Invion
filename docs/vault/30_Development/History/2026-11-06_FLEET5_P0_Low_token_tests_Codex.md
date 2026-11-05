---
doc_id: "HIST-FLEET5-P0-LOW-TOKEN-TESTS-001"
title: "FLEET5 provisional Low verifier token test-strength delta"
version: "1.0.0"
status: "in-progress"
author: "Codex"
reviewer: "Actual independent Claude Low-delta review pending via root"
updated: "2026-11-06T01:43:00+09:00"
source_of_truth: "Git"
---

# Separate nonblocking test-strength delta

Owner Codex; task `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`; optional Root direction
`msg_c1ad8cf50b7c`. Branch `agent/codex/fleet5-p0-low-token-tests-20261106` starts
from frozen accepted source `4f97ba71b1482ae70d72dda1833a28fddcd05994`. The main
DOCS-only frozen handoff `3af3334ec7577f96b1d377164675e544504407ad` and its exact
Docs `42066623585` are both published/successful. Original guidance versions,
Index401/Codex362, skills and scopes remain recorded in the original inventory
and [[2026-11-06_FLEET5_T123_review_closure_Codex]].

Actual independent 4f verdict `2736aec1303ca6b6ed80bdc4aa6b9c23c3693985` accepts
bounded P0 source and identifies these two nonblocking Low test-strength gaps.
This separate delta changes only three lines in the existing default-dispatch
unit: oversize output is a complete valid token with more than 65536 leading
space bytes; duplicate verified is inside the otherwise complete exact token.
An independent normal JSON parse must reproduce the original valid value for
both payloads before the production guard is exercised. No production guard,
parser, signature, helper, CI workflow or accepted source ref changes.

Focused full-file command with main .venv Python 3.14.7 -B passes eleven,
zero skipped, exit 0. The disposable-source-copy mutation proof executes ten
default-dispatch cases per child. Baseline passes ten; removing only the stdout
bound fails exactly oversize, and replacing only strict_json with json.loads
fails exactly duplicate. Both expected mutant exits are 1, errors/skips are 0;
the overall proof exits 0. Failure means the invalid dispatch would otherwise
admit an operation. Three production original source hashes remain unchanged.
Commands/construction, exact failed cases and raw log hashes are in
`Evidence/fleet5-p0-low-token-tests-20261106-codex/mutation-result.json`.

This patch is provisional until actual independent Low-delta review. Its
focused/local checks and Docs run are separate from source 4f's accepted full CI;
no whole Core rerun is dispatched for these two Low cases. Root's final combined
CI must collect the patch before whole integration acceptance. No shared board,
registry, ADR, protected pilot, private config/key, host Go/Docker/SSH/WSL/trust,
clock/schedule or Obsidian apply action was made. Codex next publishes this
small immutable delta to root for actual review, then returns to the original
OPEN Broad B DOCS-only architecture proposal; production B waits for Root's
concrete design decision.
