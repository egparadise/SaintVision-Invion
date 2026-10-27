---
doc_id: "HIST-20261019-CARD301-STANDALONE-WORKER-MODULES-CODEX"
title: "Card 301 standalone worker local-module closure"
version: "1.0.1"
status: "review"
author: "Codex"
created: "2026-10-19T22:44:21+09:00"
updated: "2026-10-19T22:57:36+09:00"
source_of_truth: "Git"
---

# Card 301 standalone worker local-module closure

## Measured failure and boundary

Base: train 76 candidate `b3ef33c5407a1356343cb457126d2f1217bc7427`. Owner/reviewer:
Codex/Claude. In the separately authorized r3 retry, the expired prepared-zero batch was abandoned,
both Node runtimes were cleaned and preflighted, and a fresh shared-Control-Plane batch was
prepared. The first Node then failed at the restart seam with `ModuleNotFoundError`. The standalone
runtime had pinned `worker_leaf_rotation.py`, but its delayed `docker_restart()` import of the
repository-local `worker_config.py` was absent.

The operation stopped immediately. The first Node journal is `installed` with `restartRequired`
true and no receipt. Its host public directory contains the next Node leaf and overlap policy, but
`worker_config` failed before `install_files()`, so the running container volume retains the old
leaf and policy. The second Node, both DB channels, and the global Control Plane leaf were not
changed. At the stop-time read-back both Nodes were online and fresh. No secret, DSN, private key,
Node identity, or certificate fingerprint is recorded here.

## Exact local-module closure

The offline runtime manifest now binds a sorted `workerModules` map containing exactly
`worker_leaf_rotation.py` and `worker_config.py`. Before downloading a wheel, the builder parses
all imports in those files and compares the repository-local import closure with that fixed set.
A missing module, newly introduced unreviewed local import, relative import, changed source digest,
extra archive member, or changed installed module fails closed.

Installation puts the two sources under the private runtime's `worker/` directory. The receipt
adds the canonical worker-module map digest, and every validation reconstructs the wheel tree and
the exact worker-module bytes. `run` keeps `-I -B`, removes cached local-module objects, places only
the installed pinned worker directory on the local-import path, and retains the separately checked
entry-point digest. An external sibling `worker_config.py` cannot shadow the installed copy.

Hosted Backend CPython 3.12 and 3.14 build the real four-wheel bundle and run the real worker through
a disposable fake Docker CLI implementing the exact `cp`, `restart`, and `inspect` calls. The cycle
requires install plus restart receipt, finalize plus restart, and a separate install plus rollback
restart; it also rechecks zero bytecode caches. No Docker daemon or live Node is used.

## Read-only live-state conclusions

No command in this card changes the live r3 state.

1. **Unexpected restart.** A plain `docker restart` currently reuses the container volume, which
   still contains the old leaf and old policy, because the failed function imports `worker_config`
   before `install_files()`. That narrow restart remains on the old channel authority. A reviewed
   worker retry is different: it would copy the host's next leaf and overlap policy before restart.
   With the DB channel still old, that next leaf is not yet the admitted channel identity; after
   overlap expiry its policy also rejects the old Control Plane. Recreate/sync tooling must not be
   used as an accidental retry.
2. **Same-batch retry.** Before the recorded overlap deadline, `install()` would validate the same
   proposal with `installed=True`, preserve the exact journal/backup, run the missing restart seam,
   and return the receipt idempotently. At this card's 2026-10-19 22:57 KST read-back, the
   `2026-10-20 02:23:05 KST` deadline had **not** passed, so the exact same batch remained
   technically resumable until that deadline. This card has no live authorization and does not
   resume it. After the deadline, `validate_bundle()` rejects the expired overlap before restart.
3. **Card 293 supersession.** `_supersede_expired_journal()` requires the old Node journal phase to
   be `restarted` and the new channel baseline to be the old target version. The measured journal is
   `installed`, no receipt was staged, and the DB channel remains the old current version. The
   existing Card 293 path therefore cannot consume this state. A new batch would also see the host
   next leaf rather than its declared old base.
4. **Rollback recommendation.** The reviewed rollback explicitly accepts `installed`, validates
   the exact proposal and backup, and restores only while the prior Node leaf and one-fingerprint
   policy are fresh. The old Control Plane/Node authority remains within its 2026-10-23 window.
   Therefore an exact fresh-only rollback is safe and is the recommended alternative if the same
   batch will not complete inside its remaining overlap window; after expiry it is the prerequisite
   before any new batch. It removes the host/container split and unexpected-restart risk, but it
   requires separate live authorization and is not executed here.

## Verification

- Repository Python 3.14 focused suites: **60 passed**.
- Card 301 mutations: **2/2 killed** — removing `worker_config.py` from the fixed closure and
  letting the external worker directory shadow local modules both fail.
- Card 298 boundary mutations remain **10/10 killed**.
- Real pinned bundle build: eight exact archive members, including exactly two worker modules;
  bundle schema v2 and worker-module count 2.
- `python -m py_compile` for the launcher and hosted lifecycle tool: success.
- Hosted Backend 3.12/3.14 full lifecycle and exact-head Core/Docs run IDs are pending the PR push.

## Review boundary

Claude should review the AST closure rule, module/receipt digests, import-path precedence, actual
fake-Docker lifecycle, and the four read-only conclusions above. Live rollback or another rotation
is explicitly outside this PR.
