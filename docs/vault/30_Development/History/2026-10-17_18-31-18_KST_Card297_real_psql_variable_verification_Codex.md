---
title: "Card 297 real-psql variable verification"
date: "2026-10-17T18:31:18+09:00"
author: "Codex"
status: "review"
---

# Card 297 real-psql variable verification

## Measured failure and safety stop

The user-approved Card 296 r3 bootstrap created the isolated
`saintvision_lan_r3_4607ca85` database and its derived runtime role in the existing hardened
PostgreSQL container, then stopped at verification. Real `psql` reported a syntax error where
`verify-pilot-database.sh` supplied `runtime_role` through `-v` but referenced it from a `-c`
command string. `psql` does not perform that variable interpolation in `-c` input. No r3 state,
Node enrollment, observer, server or desktop-shortcut change followed the failure. This card does
not access or modify the live database, tunnel, Nodes, r2 state, containers or volumes.

## Product correction

The runtime-privilege and inherited-membership queries now enter `psql` through stdin, with
`-v ON_ERROR_STOP=1` and `-v runtime_role=...`. The runtime role and database are validated public
identifiers; database credentials remain mounted files or stdin and never enter argv. An audit of
`prepare-pilot-database.sh` found every query that uses a `psql` variable already supplied through
stdin/heredoc, so no prepare-path product change was required.

The Card 150 tooling evidence rotates only the verifier SHA-256 and Git blob pins. Historical
observations and verdicts are unchanged.

## Real PostgreSQL regression boundary

Core owns one dedicated hosted case. It starts the digest-pinned PostgreSQL image through the
actual prepare script, then exercises the pre-existing-container path to create a distinct
namespaced database and derived role. The actual verifier must prove:

1. missing and incorrect credentials are rejected;
2. admin and derived runtime credentials are role-bound;
3. host authentication and the stored runtime password are SCRAM-SHA-256;
4. the runtime role has no superuser, bypass-RLS, create-database, create-role, replication or
   unexpected inherited privilege;
5. changing that role to superuser makes verification fail closed; and
6. the exact former `-c` plus `:'runtime_role'` query fails against real `psql`, while the product
   stdin query succeeds.

The case owns unique container, network, volume, port and private test directory names and removes
only those exact, label-verified resources. Backend and the ordinary Core collection explicitly
ignore it; the dedicated Core step requires exactly one executed, non-skipped JUnit case. The
Docker-free fake-driver tests remain supplementary and no local Docker Desktop is used.

## Preserved live resume boundary

The live r3 database, role and credential files already exist and must be preserved. Re-running
`prepare-pilot-database.sh` is not an idempotent resume operation: after revalidating ownership and
the hardened admin credential, it intentionally detects the database/role collision and stops
without overwrite. After review and landing, the safe first command is the fixed verifier against
that existing namespaced database and its existing operator-private directory. Only a green
receipt permits resuming Card 296 at `lan_pilot.py init` and `bind-db-auth`; deletion, credential
rotation or recreation is neither required nor authorized.

The exact non-secret command form is:

```bash
bash deploy/lan/verify-pilot-database.sh \
  <existing-owned-container> <existing-owned-network> \
  saintvision_lan_r3_4607ca85 <existing-operator-private-directory>
```

Exact hosted run identifiers and the reviewed head are recorded in the PR after execution because
a run cannot attest to a future commit that records its own identifier.
