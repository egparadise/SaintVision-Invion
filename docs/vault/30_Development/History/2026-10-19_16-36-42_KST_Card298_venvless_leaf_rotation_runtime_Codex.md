---
doc_id: "HIST-20261019-CARD298-VENVLESS-CODEX"
title: "Card 298 venvless leaf-rotation runtime"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-19T16:36:42+09:00"
updated: "2026-10-19T16:36:42+09:00"
source_of_truth: "Git"
---

# Card 298 venvless leaf-rotation runtime

## Scope and live boundary

Base: train 74 candidate `01260ca4ce92fa67b6df2fb74079f48a6076f9a0`. Owner/reviewer:
Codex/Claude. This card changes code, tests, workflow measurement, and documentation only. It did
not transfer a runtime, install a package, start a rotation, issue a certificate, alter a channel,
or write either live Node. Docker Desktop was not used. Live use remains forbidden until this PR
is independently approved, lands, and the user separately authorizes the rotation.

Read-only `ssh -o BatchMode=yes` probes measured only non-secret compatibility facts:

| Node runtime | architecture | Python | platform | SOABI |
|---|---|---|---|---|
| first active r3 Node | x86_64 | 3.14.4 | linux-x86_64 | cpython-314-x86_64-linux-gnu |
| second active r3 Node | x86_64 | 3.12.3 | linux-x86_64 | cpython-312-x86_64-linux-gnu |

No address, account, key path, certificate identity, or fingerprint is recorded here.

## Reviewed supply and runtime boundary

`deploy/lan/leaf-rotation-runtime-lock.json` records the official PyPI project pages, exact
`files.pythonhosted.org` URLs, filenames, versions, and SHA-256 digests. The selected set is:

- `cryptography==50.0.1`: one CPython 3.11+ abi3 manylinux2014 x86_64 wheel shared by both Nodes;
- `cffi==2.0.0`: separate CPython 3.12 and CPython 3.14 manylinux2014 x86_64 wheels;
- `pycparser==2.23`: one pure-Python wheel shared by both Nodes.

The CP command `python tools/build_leaf_rotation_runtime.py --output <path>` downloads only those
four URLs, rejects redirects/digest drift, and emits a deterministic public offline ZIP. A local
reference build contained four wheels, measured 5,274,070 bytes, and had SHA-256
`b5de5a232ccb9954a8a5c044fe028592870c28480a4a5ca5978cc3cc6b59963b`. This is build evidence,
not a live deployment receipt; the operator recomputes and compares the actual transfer digest.

On a Node, the reviewed stdlib-only installer:

1. accepts only the two measured CPython/SOABI/architecture records;
2. verifies the repository lock digest, exact bundle member set, every wheel digest, safe paths,
   regular-file types, and bounded sizes;
3. extracts only the ABI-selected wheels into a mode-0700 temporary directory, fsyncs files and
   directories, and renames it atomically into the operator's user-owned runtime path;
4. keeps the selected original wheels and reconstructs their expected file map on every run, so
   receipt or installed-file tampering cannot authorize itself;
5. runs under `python3 -I`, replaces `sys.path` with the verified runtime, reviewed worker
   directory, and standard-library paths, and rejects an import whose origin leaves the runtime;
6. requires exact cryptography 50.0.1, cffi 2.0.0, pycparser 2.23, and the worker's existing UTC
   certificate API preflight before state-writing commands can execute.

`prepare-leaf-rotation-runtime.sh --standalone` installs and preflights this path without pip,
internet, sudo, venv, or a system package change. The prior venv/pip path remains an alternative;
operators must use one runtime consistently for install, finalize, and rollback. None of the
Cards 288/291/293/295 identity, chain, revocation, channel CAS, journal, expiry, concurrency, or
fresh-only rollback checks changed.

## Verification

- Repository Python 3.14: `pytest tests/test_lan_leaf_rotation_standalone_runtime.py
  tests/test_lan_leaf_rotation.py -q` — **52 passed**.
- `python tools/test_c298_mutations.py` — **9/9 killed**. The mutations individually remove lock
  hashing, ABI matching, wheel hashing, installed-byte comparison, isolated path replacement,
  wheel data-path rejection, non-regular member rejection, `-I` on installation, and the reviewed
  worker-script digest binding.
- Actual official wheel bundle build — success with all four metadata hashes reproduced.
- Git Bash `bash -n deploy/lan/prepare-leaf-rotation-runtime.sh` and `git diff --check` — success.
- Hosted Backend CPython 3.12/3.14 now builds the actual pinned bundle, installs it, and executes
  `worker_leaf_rotation.py runtime-preflight`. Exact-head run IDs are pending the PR push.

The local machine's default Python 3.10 cannot collect the existing rotation suite because the
product uses `enum.StrEnum`; the same suite passed under the repository Python 3.14 environment.
That environment distinction is recorded rather than treating the collection failure as product
evidence.

## Post-review operator shape

After landing and a separate user authorization, build the bundle on the reviewed CP checkout,
compare its SHA-256 out of band, transfer only public runtime/rotation material, and run the
documented standalone prepare command on both Nodes. Both runtime preflights must pass before the
CP issues a batch. Every worker command in that batch must use the same `python3 -I` standalone
launcher. A different ABI, missing/changed wheel, wrong transfer digest, system-package fallback,
or preflight failure stops before rotation state changes.

Reviewer: Claude. Verify the lock against PyPI metadata, the two measured ABI selectors, archive
and installed-tree fail-closed behavior, isolation from system cryptography, preservation of the
venv alternative and all pre-existing leaf-rotation security boundaries, the mutation results,
and the exact-head hosted Linux roundtrip before approval.
