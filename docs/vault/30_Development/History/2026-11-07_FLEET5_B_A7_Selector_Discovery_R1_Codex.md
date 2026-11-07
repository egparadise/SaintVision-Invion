---
doc_id: "HISTORY-FLEET5-B-A7-SELECTOR-DISCOVERY-R1-CODEX-20261107"
title: "FLEET5 B A7 selector discovery R1"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-07T11:45:36+09:00"
source_of_truth: "Git; target-derived AST and source data"
---

Root message `msg_984f62d6c820` assigns this finite evidence task to Codex under
`task_a8fd2969f0b3` / `ctx_6f0f8253b8a7`. Branch is
`agent/codex/fleet5-b-a7-selector-discovery-r1-20261107`, based directly on
`746789a36091c8601afea23fe176069e2fa7d87b`. Independent delta review is PENDING
through Root. The only new tracked scope is this History and own Evidence
prefix `fleet5-b-a7-selector-discovery-r1-20261107-codex`. Product, test, old
collector, helpers, frozen outputs, boards, registry and incident remain intact.

Canonical first-read versions at Root HEAD
`11386fc1b1850ed7e402e0214e02d1322c974f4a` are Index `1.0.500` and Codex
board `1.0.461`, updated 11:38:47 KST. `probe01/inputs.json` records full IDs,
versions/hashes, base/task/owner/reviewer, AGENTS, agent-delivery `1.1.0`,
core-reliability `1.0.0`, canonical plans and registry. It pins 17 published
review references and the exact accepted proof inputs without copying the old
corpus. It also inventories 64 prior untracked files for preservation/exclusion.

Actual independent CODE review is
`dc18f6681627aca9d3eceb7d5a85dbc97b551b5b`, direct parent 746789a, verdict
**ACCEPT_NARROW_CODE_KEEP_HOLD**, with no mandatory product/test correction.
Root verified reviewer Docs `42329333553`, job `128271989583`, attempt 1,
all 19 successful. Its LOW OPG-L1 is nonblocking for actual 746789a because
reviewer P06 independently enumerated that HEAD. It applies to future reuse:
the frozen `finite_compatibility.current_world()` builds its paths from
`base_world()`, so a new matching production file could escape that discovery.
The old function stays unchanged; this task supplies a separate collector.

The new `collector.py` discovers the evaluated target first. It uses the exact
original POSIX ERE through `git grep -E` over the three production roots:
`services/control-plane/src`, `src`, and `tools`. Commit mode resolves the
requested ref once, enumerates its Git tree, selects on that same immutable
commit, and reads actual Git blob objects. Working mode enumerates physical
Python files independently of the index, so new tracked, untracked and ignored
files are considered. Index membership is reported separately and does not
seed enumeration. Literal path chunks bound Windows command length.

Selected inventories record path, raw byte length/SHA256, decoded source hash,
Git object ID when applicable, and actual target membership. Filesystem paths,
bytes and stamps are checked again around selection. Unsupported paths,
symlinks, read/search/encoding failures and selected-source parse failures
refuse or become unresolved. This is a static filesystem model, not an atomic
hostile-filesystem, runtime receiver, dynamic import or type-identity proof.

Only after target discovery does `probe.py` compare the selected set with the
existing finite predicate's expected set. Changed sets reject with
**SOURCE_WORLD_PATH_SET_CHANGED** before that predicate runs. Equal sets enter
the unchanged accepted source/AST predicate. No base path list or caller-injected
world is substituted for discovery.

The serial command at **11:44:56–11:45:36 KST** was:

```text
D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe -B docs/vault/30_Development/Evidence/fleet5-b-a7-selector-discovery-r1-20261107-codex/probe.py probe01
```

Direct exit was **0**, Windows / existing Python **3.14.7**. The command receipt
records actual cwd/interpreter, producer hashes, exact stdout bytes/hash and
timestamps. No application/test/mutant module was executed; no pytest, Go,
Node, compiler, crypto, browser, Docker, SSH or build ran. Peak memory was not
measured. Immutable 746789a independently selects **25 of 398** production Python
files; actual working-tree selection independently selects the same **25**, all
currently tracked, with identical raw bytes. Working enumeration supports newly
present untracked files; the real product tree was not changed to create one.

The accepted whole-module AST/other-24-byte/reference/owner classification remains
**EXACT_CAPTURE_GUARD_DELTA_COVERED_WITH_LEGACY_REFUSAL_PRESERVED** for both real
targets. Static legacy analysis was given all 25 actual target Git blobs and
still reports exactly
`DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:INSTANCE:operation`.
Its compatibility-clean flag remains false; 25 parsed/audited and nine
constructors are reported. No allowance or old proof was changed.

Six filesystem controls use the collector's normal enumeration/read entrypoint
under a unique own `.work` data directory. These are source-data fixtures with
no `.git`, application execution, real checkout or tracked/untracked claim:

| Physically present fixture | Selected | Observed result |
| --- | ---: | --- |
| Exact 25 selected source blobs | 25 | Existing finite predicate accepts conditionally |
| New matching production module with second `.deliver` | 26 | SOURCE_WORLD_PATH_SET_CHANGED; predicate not entered; two references counted |
| One selected worker module absent | 24 | SOURCE_WORLD_PATH_SET_CHANGED; missing path identified |
| Extra nonmatching production Python module | 25 of 26 | Nonmatching file is enumerated and excluded by selector; scoped predicate unchanged |
| Invalid UTF8 production source | unresolved | SOURCE_ENCODING_UNRESOLVED |
| Matching source with invalid syntax | unresolved | SELECTED_SOURCE_PARSE_UNRESOLVED |

All **6/6 expected results** were observed. `fixture-input-inventories.json`
records every physically materialized Python file/hash. No fixture cleanup,
move or deletion was attempted. The old `modified-unrelated-module` result is
retained by hash and row as **INHERITED_CALLER_INJECTED_WORLD_CONTROL**, explicitly
distinct from the new tree-discovery evidence. It is not renamed a discovery
control. OPG-I2 remains qualified: earlier real BASE RED removed both capture
and guard; no capture-only mutant runtime result is invented.

Normal delivery for this new evidence scope runs docs, ontology, path ratchet
against 746789a, single-source ratchet, canonical sync CHECK and diff gates,
then explicit own-scope stage/commit/push and one exact Documentation workflow.
Those publication/CI receipts are separate from the static probe results. Every
CHECK keeps complete canonical-state bytes before and after; Root alone may
apply. Core/Backend and product tests are not repeated for this docs-only delta.

Next owner is Root: verify the immutable new docs SHA and Documentation result,
then arrange one actual independent delta review. Author reports the discovery
remedy and controls, not a self-awarded review closure. Existing 48/VFCL status,
original 19 HOLD, acceptedBaselineDischarges=0, actualRuntimeB=0, A1–A16 pending,
all actual bindings/authority NULL_HOLD and full five-PC/program incomplete state
remain. The retained two-byte incident is separate and nonblocking; no cleanup
or retry is authorized or performed here.
