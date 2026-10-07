---
doc_id: "HIST-20261007-CARD287-CODEX"
title: "Card 287 LAN pilot reconnect"
version: "1.0.1"
status: "review"
author: "Codex"
created: "2026-10-07T11:07:11+09:00"
updated: "2026-10-07T11:32:33+09:00"
source_of_truth: "Git"
---

# Card 287 LAN pilot reconnect

## Scope and safety boundary

- Base: `517880099743cf2d62131012191b7ba54650c44d`
  (`coord/train63a-ci-0847`). Branch: `agent/codex/c287-lan-pilot-reconnect`.
- The expired pilot state, issuing material, existing Node containers, database containers, and
  volumes were preserved. The accepted state is `.work/lan-5node/r2-7057dcd0`; an earlier
  non-accepted bootstrap candidate is also preserved.
- No local Docker command was used. The image was built on a Linux Node from a clean exact-source
  archive and delivered through `--prebuilt-image`. The database runs on a remote Linux Node with
  loopback publication, SCRAM roles, a private passfile, and an SSH tunnel.
- Private keys, passwords, DSNs, Node identifiers, certificate fingerprints, host names, and
  private addresses are intentionally absent from this record.

## Product/tooling defects found and fixed

1. `deploy/lan/prepare-pilot-database.sh` placed an `|| { ... }` group after a heredoc in a form
   that the remote shell parsed as an unterminated group. The command now uses an explicit
   `if ! ...; then ...; fi` boundary and has a syntax regression test.
2. The root `.dockerignore` omitted `packages/contracts-go`, although
   `deploy/lan/Dockerfile.node.remote` needs it. A clean `git archive` therefore could not build.
   The required Node and Go-contract subtrees are now explicitly allowed and statically tested.
3. Docker's containerd image store reports the OCI manifest digest as the inspected image ID,
   while the prior verifier accepted only the classic config digest. `tools/lan_pilot.py` now
   validates either the classic identity or a strict single-descriptor OCI layout: index and
   manifest digests/sizes, tag annotation, config digest, layer binding, and inspected ID must all
   agree. Wrong inspected IDs and wrong configs are negative-tested.

The focused `tests/test_lan_pilot_multinode.py` result is **25 passed, 1 skipped**. The skip is the
existing POSIX-only verifier on Windows, not an operational claim.

Local gates also passed `tools/check_docs.py`, `tools/check_ontology.py`,
`tools/check_contract_bindings.py`, and the path-citation ratchet against the assigned base.
`tools/sync_obsidian.py --check` made no writes and reported 11 pre-existing unmanaged destination
collisions (8 without a baseline and 3 where both copies diverged); those unrelated files were not
adopted or overwritten.

The first exact-head Backend run correctly rejected the stale public tooling hashes in
`card150-intranet-pki-lan-pilot.json` for the two changed bootstrap files. Those public, secret-free
SHA-256 and Git-blob bindings were regenerated from the committed files; the focused evidence
binding test and the LAN pilot suite then passed before the replacement hosted run.

## Measured deployment

- Remote database prepare and verification both passed: missing and wrong credentials were
  rejected, dedicated admin/runtime roles were accepted, SCRAM and the dedicated network were
  observed, and publication remained loopback-only.
- The accepted source/image code head is `7057dcd0d16f9932fc19a977dce90a970247868a`.
  The Linux-built image archive SHA-256 is
  `e4a1dc7b9104ada1df05d0473ea012f00ecd20569a4bb078335f790e6676b38f`.
- The fresh bootstrap service listens on the new download port and was reached from both enrolled
  Nodes. No Windows firewall rule was required for those two paths.
- Both accessible Nodes loaded the same verified archive into new, distinctly named containers on
  a non-conflicting Node port. The first foreground observation returned `observed=2` and
  `unavailable=0`; both records were `online` with heartbeats at 2026-10-07 02:06 UTC. A persistent
  observer then advanced both heartbeats again. Workload execution remains disabled and the state
  is observation-only.
- The two newly issued leaves expire on 2026-10-13 at 02:04 UTC. This is an observed operational
  expiry, not a claim that automatic rotation exists.

## Remaining user boundaries

- Worker 3: SSH and time synchronization work, but the non-root account cannot open the Docker
  socket. The operator must add that account to the Docker group, end all sessions, sign in again,
  and verify the server API before the repeated `init --node-ip`/bundle/enroll sequence.
- Worker 4: the SSH service is reachable, but the approved public key is not enrolled and the
  non-root account name is not established. The operator must install that public key for the
  selected account and provide the account name. No password fallback was attempted.
- If either later worker cannot reach the bootstrap port after it is added to the state, the
  operator may add one inbound Windows firewall rule limited to the four LAN source addresses.
  The current two-worker measurement does not require or justify that rule.

## Card 288 proposal — automatic Node leaf rotation

Card 288 should begin immediately after Card 287 independent review and target completion within
two working days, before the observed six-day leaves expire. Its scope is deliberately separate:

1. renew a Node/control leaf before a configurable safety window while preserving the Node key and
   pinned identity;
2. validate the external issuing chain, exact node binding, expiry window, and monotonic channel
   version before installation;
3. write the new public material atomically, restart only after fsync/rename, and keep a bounded
   overlap or rollback copy without accepting an expired certificate;
4. make retries and crash recovery idempotent, and refuse revoked, wrong-node, wrong-chain,
   stale-version, or concurrent second-writer input;
5. prove rotation with short-lived test leaves plus remote hosted/manual evidence, including kill
   points before install, after install, and before restart.

## Handoff

- Reviewer: Claude.
- First reviewer action: verify the three fail-closed bootstrap fixes and the focused regressions,
  then compare the redacted operational result with the LAN runbook.
- Operator continuation after Worker 3/4 prerequisites: repeat `init --node-ip` with the same
  external CA and isolated database files, regenerate the bundle with the same exact prebuilt
  image, restart `serve`, and use the documented prepare/enroll/finish sequence. Do not reuse or
  overwrite the expired pilot directories.
