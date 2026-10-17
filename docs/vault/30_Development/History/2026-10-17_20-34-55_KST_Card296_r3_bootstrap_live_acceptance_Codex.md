---
doc_id: "HIST-20261017-CARD296-LIVE-CODEX"
title: "Card 296 fresh isolated r3 bootstrap live acceptance"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-17T20:34:55+09:00"
updated: "2026-10-17T20:34:55+09:00"
source_of_truth: "Git"
---

# Card 296 fresh isolated r3 bootstrap live acceptance

## Authority, source, and redaction boundary

The user approved the fresh isolated r3 bootstrap after Card 296, Card 297, and merge train 73
were independently reviewed. The executed source was the exact train 73 candidate
`c04d5162995e5443287dd9214b9f379c5b05874c`. The existing r2 state, database, journals,
containers, volumes, and Node keys were not reused or deleted. The desktop-owned loopback
database tunnel remained running throughout, and Docker Desktop was not used by this procedure.

This record intentionally omits database and role names, DSNs, account names, Node IDs and
addresses, private paths, certificate fingerprints, and all private-key material. It records only
the public control results needed for review.

## Execution record

1. The first live attempt created the isolated r3 database and least-privilege runtime role, then
   stopped when real `psql` showed that `-v` variables are not interpolated inside `-c` strings.
   Card 297 moved variable-bearing verification SQL to stdin and added a hosted real-PostgreSQL
   roundtrip. After train 73, the preserved database passed the fixed verifier without recreation.
2. The first Control Plane `init` attempt used the machine's default Python 3.10 and stopped at
   `enum.StrEnum`. All subsequent `lan_pilot.py` commands used the repository Python 3.14 venv,
   which had the required `cryptography` and `psycopg` dependencies.
3. `init` and `bind-db-auth` succeeded against the isolated database. The exact train 73 Linux
   Node image was built on an approved Linux host, transferred as public build output, and bound
   into the r3 bundle. The selected bootstrap and Node ports did not collide with existing r2
   services.
4. A local postcondition incorrectly looked only for top-level `worker.zip` and stopped even
   though the bundle had correctly emitted two Node-specific archives under
   `public/nodes/<node-id>/worker.zip`. No Node mutation had occurred at that stop.
5. Each Node received only its assigned archive. Control Plane and Node SHA-256 calculations
   matched. Each Node ran `prepare-worker.sh`, generated its new key locally, and returned only a
   signed, extension-free CSR. The private keys never left their Nodes.
6. A second local postcondition incorrectly expected the issued certificate's common name to be
   the Node ID. The repository contract uses the fixed peer common name and binds identity through
   the exact Node URI SAN, IP SAN, CSR public key, external issuing chain, and validity window.
   `lan_pilot enroll` passed for both Nodes; the incorrect extra assertion was discarded rather
   than weakening the repository validator.
7. Each public Node certificate was transferred only to its assigned Node and its file SHA-256
   matched out of band. `finish-worker.sh` passed on both Nodes, preserving each local key and
   starting the new observation-only container. The r3 observer then reported exactly two Nodes,
   both `observed=true`, `status=online`, with fresh post-install heartbeats and persisted
   snapshots.
8. The first desktop cutover attempt correctly failed before changing a listener because the
   review checkout's Git common directory did not contain the venv that the launcher derives.
   The coordinator then used a train-73 detached worktree whose repository venv satisfied that
   gate. The reviewed `-ReplaceForeignStateListener` path replaced the owned r2 console, reused the
   owned database tunnel, and registered the owned shortcut only after the two-Node acceptance.

## Final measured state

- The loopback overview endpoint reports `source=live-postgresql-mtls`.
- Exactly two r3 Nodes are online and fresh; their accepted heartbeats are after their successful
  `finish-worker.sh` executions.
- The web, overview, and database-forward listeners are loopback-only. The desktop shortcut
  carries the r3 state path.
- The r3 `serve` and `observe` processes are state-bound. Workload execution remains disabled.
- The Control Plane leaf expires at **2026-10-23 20:10:38 KST**. The two Node leaves expire at
  **2026-10-23 20:19:52 KST** and **2026-10-23 20:25:05 KST**.

## Next rotation prerequisite

Fresh bootstrap itself is standard-library-only on the Nodes and therefore did not install or
prove a Python venv. Leaf rotation is different: `prepare-leaf-rotation-runtime.sh` runs
`python3 -m venv`, pins `cryptography==50.0.1`, and executes `runtime-preflight`; install,
finalize, and rollback must use that same isolated interpreter. The earlier host measurement found
the matching venv packages absent, and this bootstrap did not change that host state. Treat both
as unmet until remeasured:

- install `python3.14-venv` on the Python 3.14 Node;
- install `python3.12-venv` on the Python 3.12 Node.

Those package installations require the operator's `sudo` authority and are not part of this
run. Prepare both isolated runtimes and pass `runtime-preflight` before issuing any rotation
material. Because the earliest leaf is the Control Plane leaf, a reviewed batch rotation must
complete before 2026-10-23 20:10:38 KST; begin with ample margin before the four-hour overlap
window rather than treating the expiry as a start time.

## Review handoff

Reviewer: Claude. Confirm the redaction boundary, the exact train 73 source, the distinction
between the standard-library fresh bootstrap and the venv-backed rotation path, the three public
expiry timestamps, and that the two mistaken local postconditions did not weaken or replace the
repository validators.
