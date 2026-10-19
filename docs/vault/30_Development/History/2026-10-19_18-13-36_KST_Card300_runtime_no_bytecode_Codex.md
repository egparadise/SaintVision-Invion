---
doc_id: "HIST-20261019-CARD300-RUNTIME-NO-BYTECODE-CODEX"
title: "Card 300 leaf-rotation runtime bytecode-free repeatability"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-19T18:13:36+09:00"
updated: "2026-10-19T18:13:36+09:00"
source_of_truth: "Git"
---

# Card 300 leaf-rotation runtime bytecode-free repeatability

## Scope and measured failure

Base: train 75 candidate `089bb51d92931c558dfaf875ec4334b34de78e45`. Owner/reviewer:
Codex/Claude. During the separately authorized r3 rotation, both Nodes accepted the exact Card 298
runtime bundle and passed `runtime-preflight`. Before any Node certificate, policy, container,
channel, or global Control Plane leaf changed, the first subsequent `install` failed closed because
the preflight imports had written `__pycache__` into the otherwise immutable runtime. The exact-tree
validator correctly rejected those extra bytes. The operation stopped with both Nodes online and
fresh on their old leaves, zero staged Nodes, the global old Control Plane leaf, and no rollback
required. No secret, DSN, private key, Node identity, or certificate fingerprint is recorded here.

This card changes code, tests, workflow measurement, and documentation only. It performs no live
cleanup, journal abandonment, certificate issuance, channel CAS, restart, or rotation.

## Bytecode-free execution and narrow repair

All reviewed standalone shell and hosted commands now invoke Python with both `-I` and `-B`.
`leaf_rotation_standalone_runtime.py` independently fixes `sys.dont_write_bytecode = True` before
loading any wheel module, so an omitted environment variable cannot weaken the boundary and `-I`
does not discard the protection. The immutable installed-tree validator is unchanged: it still
requires the exact files reconstructed from pinned wheels and rejects every extra member.

For the two already-installed Node runtimes, the explicit one-time recovery command is:

```bash
python3 -I -B leaf_rotation_standalone_runtime.py clean-bytecode-cache \
  --runtime-dir "$HOME/.local/share/saintvision/leaf-rotation-runtime-820cfd0d"
```

The command validates receipt authority, platform, lock, original wheel hashes, expected file
count/digest, and every pinned byte before removing anything. It accepts only the current
interpreter's exact `importlib` cache path for a pinned `.py` source. An unknown `.pyc`, changed
pinned file, symlink, non-regular file, receipt drift, or any other extra remains a hard refusal.
After fsyncing each removal it re-runs the unchanged exact-tree validator. Repeating the command is
idempotent. A fresh atomic reinstall remains an alternative, but no runtime directory is deleted or
replaced implicitly.

A read-only `python3 -I -B -` inventory measured both installed Node runtimes present, with exactly
61 cache files apiece under `__pycache__` paths and zero symlinks. It did not delete, rewrite, or
otherwise repair either live directory; the reviewed cleanup remains a post-landing operation.

## Expired live prepared batch

Read-only inspection measured the live Card 298 attempt as `prepared`, staged count zero, global
old Control Plane leaf, and both Nodes unchanged. Its overlap expired at
`2026-10-19T22:00:38+09:00`. The old general supersession path is deliberately inapplicable: it
requires an expired partial batch in `staging` or `staged` phase with a non-empty proper subset of
Nodes already channel-CASed. A merely prepared journal therefore continues to own the state and
blocks a new batch even after expiry.

Card 300 adds a distinct operator command for exactly this case:

```powershell
& <repo-venv-python> tools/lan_pilot.py `
  --state <private-r3-state> `
  abandon-expired-prepared-leaf-rotation-batch `
  --bundle <expired-card298-batch>
```

It succeeds only after overlap expiry, only for `phase=prepared` with zero staged Nodes, and only
after re-reading the exact batch and proving the global CP leaf, every DB channel version/digest/
endpoint, and every published Node leaf remain at the declared current authority. It writes a
durable redacted abandonment record before unlinking the active journal. Drift, an unexpired
window, any staged Node, a different batch, or an unsafe journal path is rejected. The public old
batch remains preserved, and an exact replay is idempotent. This is not the partial-batch recovery
path and does not accept expired credentials as authority.

## Verification

- Repository Python 3.14: `pytest -q tests/test_lan_leaf_rotation_standalone_runtime.py
  tests/test_lan_leaf_rotation.py -x` — **55 passed**.
- `python tools/test_c298_mutations.py` — **10/10 killed**, including removal of `-B` and removal
  of the independent `sys.dont_write_bytecode` guard.
- The focused cycle installs the fixture runtime, executes the reviewed worker twice, reinstalls
  between executions, proves identical receipts, and observes no `__pycache__`.
- The repair tests accept one interpreter-derived cache, are idempotent, and reject an unknown
  cache file or tampered receipt without deleting the cache.
- The batch tests reject pre-expiry abandonment and channel drift, preserve a redacted archive,
  replay exactly, and permit a new all-Node batch only after the old journal is removed.
- Hosted Backend CPython 3.12/3.14 now performs actual pinned-wheel
  `install -> worker preflight -> install -> worker preflight`, compares both receipts, and asserts
  zero cache directories. Exact-head run IDs are pending the PR push.

## Review and live boundary

Reviewer: Claude. Review the redundant `-B`/runtime guard, the narrow cache-path derivation,
delete-after-authority-validation ordering, repeat-cycle mutation evidence, and the abandonment
command's exact unchanged-authority proof. After approval and landing, a separately authorized live
retry must first run the cache cleanup on both Nodes, then abandon the expired unstaged batch, then
prepare a fresh shared batch. No command in this card has been run against live state.
