---
doc_id: "HIST-20261013-CARD294-CODEX"
title: "Card 294 fully expired LAN pilot recovery plan"
version: "0.1.0"
status: "draft"
author: "Codex"
created: "2026-10-13T22:56:04+09:00"
updated: "2026-10-13T22:56:04+09:00"
source_of_truth: "Git"
---

# Card 294 fully expired LAN pilot recovery plan

## Scope and observed starting point

- Analysis base: `7c433080ab54f802c4e85f4851a037e86bc642fb` (`coord/train70a-ci-1006`).
- This is a read-only recovery draft. No Control Plane, database, Node, certificate, tunnel,
  container, volume, or live-process state was changed while preparing it. Local Docker was not
  used.
- The preserved r2 state is `.work/lan-5node/r2-7057dcd0`. Worker A has the partially staged Card
  292 leaf and an expired overlap policy. Worker B has its original leaf and policy. Both Node
  leaves and the global old Control Plane leaf are now expired, and the global Control Plane still
  uses the old material.
- The loopback database tunnel on `127.0.0.1:55448` belongs to the desktop launcher. Every recovery
  option below preserves that listener and first verifies its owning SSH command line. None may
  stop or replace the tunnel.
- Private keys, passwords, DSNs, certificate fingerprints, concrete Node identifiers, and issuing
  material are intentionally absent from this record.

## Code facts that constrain both choices

1. A new `tools/lan_pilot.py init` creates a new epoch, tenant, and Node identifiers
   (`tools/lan_pilot.py:927-948`). An existing state instead preserves its assigned identities
   (`tools/lan_pilot.py:892-925`). There is no reviewed option that imports the r2 identity into a
   new state.
2. Bootstrap `enroll` is not a renewal operation. If the stored certificate has the CSR public
   key, it reuses that stored certificate; if the key differs, it requires explicit rotation
   (`tools/lan_pilot.py:1222-1249`). A changed database channel fingerprint is also rejected
   (`tools/lan_pilot.py:1257-1273`). Consequently, Card 287 cannot refresh an expired leaf inside
   the r2 state.
3. A fresh state cannot use the existing `saintvision_lan` database. `inv.control_epoch` is a
   singleton (`services/control-plane/src/inv/migrations/0001_core.sql:4`), and `init` refuses an
   epoch different from the stored value (`tools/lan_pilot.py:1072-1077`). The same hardened
   PostgreSQL server and the same SSH forwarding socket can be reused only with a separately named
   database and separate private DSN/passfiles. `deploy/lan/prepare-pilot-database.sh` currently
   hard-codes `saintvision_lan`, so the database-name parameter and its verification must be a
   reviewed prerequisite rather than an ad-hoc live SQL command.
4. The Card 287 worker bootstrap does not import `cryptography` and does not require a venv.
   `deploy/lan/prepare-worker.sh:5-25` needs OpenSSL, Python 3 standard-library execution, Docker,
   and Docker API 1.45 or newer; it generates the Node key and CSR in the new Node-local worker
   root. `deploy/lan/finish-worker.sh` and `deploy/lan/start-node.sh` keep the same boundary. The
   missing `python3-venv` packages therefore do not block a fresh Card 287 bootstrap.
5. The desktop launcher verifies an existing external-database tunnel before starting listeners
   (`deploy/lan/Start-LiveConsole.ps1:83-159`) and refuses a listener owned by a different state
   unless `-ReplaceForeignStateListener` is explicit (`deploy/lan/Start-LiveConsole.ps1:164-196`).
   A state cutover must use those ownership checks and may replace only the old state-owned
   observer/serve/console processes, never the port-55448 tunnel.

## Option A — fresh bootstrap in a new isolated state

### Feasibility and identity consequence

This option is feasible without trusting any expired TLS leaf. It is **not** same-identity
re-enrollment: it creates a fresh tenant, recovery epoch, Node IDs, Node-local keys, Control Plane
key, and leaves under the already approved external issuing chain. The r2 state and every existing
container and volume remain intact for evidence and possible offline analysis.

The hardened remote PostgreSQL server and the existing loopback SSH tunnel can be reused. The
database cannot: create a new, separately named database in that server and produce new protected
admin/runtime DSN files that select it. Before execution, parameterize and review
`deploy/lan/prepare-pilot-database.sh` and `deploy/lan/verify-pilot-database.sh` so that the name is
explicit, strictly validated, and used consistently; their default must remain
`saintvision_lan`. Do not create the database with an unreviewed one-off `psql` command.

### Recorded execution plan — not executed

1. Reconfirm by read-only checks that port 55448 is held by the expected SSH forward, that two new
   Control Plane/Node ports are unused, and that both remote Docker APIs are at least 1.45. Pick a
   new state such as `.work/lan-5node/r3-7c433080`; never rename or overwrite r2.
2. Create and verify the new database namespace through the reviewed parameterized database
   helper. Store its DSNs and passfiles only below `.work/intranet/` or the new untracked state.
3. Initialize the new state with the two worker addresses, unused ports, the new DSN files, and the
   same approved external issuing chain:

   ```powershell
   .\.venv\Scripts\python.exe tools/lan_pilot.py `
     --state .work/lan-5node/r3-7c433080 init `
     --server-ip <control-plane-lan-address> `
     --node-ip <worker-a-address> --node-ip <worker-b-address> `
     --download-port <unused-bootstrap-port> --node-port <unused-node-port> `
     --admin-dsn-file <private-r3-admin-dsn-file> `
     --runtime-dsn-file <private-r3-runtime-dsn-file> `
     --ca-key <private-intermediate-key> `
     --ca-key-password-file <private-password-file> `
     --ca-chain <private-exact-chain>
   ```

4. Build the exact new state tag on a Linux Node from a clean exact-source archive, inspect it
   there, and feed only the verified archive and inspection record to `bundle`. Do not use Windows
   Docker Desktop and do not silently reuse the r2 tag:

   ```powershell
   .\.venv\Scripts\python.exe tools/lan_pilot.py `
     --state .work/lan-5node/r3-7c433080 bundle `
     --prebuilt-image <verified-linux-node-image-archive> `
     --prebuilt-inspect <verified-image-inspection-json>
   ```

5. Start the r3 bootstrap service on its unused port. On each Node, download only the source-IP
   selected archive into a new working directory, verify `worker.sha256`, and run
   `bash prepare-worker.sh`. Return only `node.csr`. The script creates the new private key under
   the new Node ID and never exports it.
6. Run `lan_pilot.py enroll` once per CSR with the external CA arguments, transfer only the public
   result back, and run `bash finish-worker.sh`. The fresh Node IDs produce distinct container and
   volume names, so the r2 containers and volumes are preserved. Refuse any name, port, ownership,
   archive, or image conflict instead of deleting it.
7. Start r3 observation and require both fresh Node identities to be online with post-start
   heartbeats and unexpired leaves. Only after that acceptance, point the live console at r3:

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass `
     -File deploy/lan/Start-LiveConsole.ps1 `
     -StatePath D:\Project\SaintVisionI-Invion\.work\lan-5node\r3-7c433080 `
     -DatabaseTunnelTarget <approved-user-at-approved-db-host> `
     -SshKeyPath C:\Users\inviz\.ssh\sv-lan-ed25519 `
     -ReplaceForeignStateListener -OpenBrowser
   ```

   The launcher must prove that 55448 is the expected tunnel. Process replacement is limited to
   old state-owned console/observer/serve processes after command-line ownership verification.
8. Retain r2, its Card 292/293 journals, its containers, and its volumes unchanged. Cleanup is a
   separate destructive decision and is outside this recovery.

Expected operator time after the database-name helper is reviewed is 50–80 minutes: database
namespace and passfiles 10–15, state/image/bootstrap 15–25, two prepare/enroll/finish sequences
20–30, and cutover/observation 5–10. No sudo package installation is expected if the previously
measured OpenSSL, Python 3, Docker permission, and Docker API remain available.

## Option B — extend Card 293 to a fully expired offline recovery

### Why the train 70 command cannot run now

Installing `python3-venv` is necessary for the Card 293 worker runtime but is no longer sufficient:

- `prepare-leaf-rotation-recovery-batch` accepts only
  `overlapExpiresAt <= now < certificateNotAfter` (`tools/lan_pilot.py:1613-1618`).
- It then requires the old global Control Plane leaf to be currently valid
  (`tools/lan_pilot.py:1321-1337`, called at `tools/lan_pilot.py:1639`). That leaf is expired.
- For the previously untouched Node it loads the old stored Node certificate as the current
  rotation base (`tools/lan_pilot.py:1772-1815`); normal rotation material validation rejects an
  expired current identity.
- On the previously staged Node, journal supersession permits only
  `old_overlap <= now < old_not_after` (`deploy/lan/worker_leaf_rotation.py:350-393`). Once that
  installed Card 292 leaf expires, the Node-side supersession also fails.

These checks enforce the rule that an expired certificate is never accepted as live authority.
They must not be deleted or relaxed to make the existing command pass.

### Minimum safe code scope before B could execute

A separate, explicitly named **fully expired offline recovery** protocol would be required:

1. Keep ordinary Card 293 behavior unchanged. The new mode must first prove that all active old
   CP/Node leaves are expired and that no mixed live authority is being accepted.
2. Treat expired certificates only as historical, signed identity records. Revalidate exact issuing
   chain, revocation registry, tenant, Node, epoch, address/SAN, public-key/CSR binding, CP private
   key binding, active Node set, batch journal, database channel version/fingerprint/enabled state,
   and the concurrent-writer lock before issuing anything.
3. Require fresh CSR signatures from the existing Node-local keys and create one new shared CP
   leaf plus fresh Node leaves. Authentication and restart receipts must use the fresh leaves;
   expired leaves must never establish TLS or sign an accepted receipt.
4. Add a dedicated staged-Node transition that archives the exact expired journal and accepts its
   installed expired Card 292 leaf only as the immutable historical base. Keep atomic intent,
   replay, channel CAS, single global switch, and next-only finalize behavior.
5. Add all-expired, mixed-validity, revoked, wrong-chain, wrong-CSR, database-drift, second-writer,
   crash-point, and expired-TLS negative tests. Reverting any expired/live separation must fail.

After that code is independently reviewed and landed, each Node still needs the isolated runtime.
The exact user-owned prerequisite commands measured for the current hosts are:

```powershell
ssh -i C:/Users/inviz/.ssh/sv-lan-ed25519 saintvision-invion@192.168.45.143 -- `
  sudo apt-get install -y python3.14-venv
ssh -i C:/Users/inviz/.ssh/sv-lan-ed25519 inviz@192.168.45.210 -- `
  sudo apt-get install -y python3.12-venv
```

If either host reports stale package indexes, the user must run `sudo apt-get update` on that host
and repeat only its install. No broader package upgrade is authorized. After installation, the
reviewed `deploy/lan/prepare-leaf-rotation-runtime.sh` creates the Node-local venv and pins
`cryptography==50.0.1`; no system Python package is replaced.

Estimated time is 1–2 engineering days for the new protocol, negative tests, independent review,
and hosted CI, plus 25–45 minutes for the live recovery. Its principal risk is accidentally turning
expired historical material back into authority; that risk is materially greater than a new
bootstrap and cannot be justified merely to preserve r2 identity.

## Decision and required user action

**Recommend Option A: a new isolated r3 bootstrap.** It has the smaller trust surface, does not
need `python3-venv` or sudo, never authenticates with an expired certificate, and preserves every
r2 artifact. The cost is an intentional identity/epoch reset and a parallel database namespace.

Before live work, the user needs to approve only these two explicit consequences:

1. replace the operational pilot identity with the new r3 tenant/epoch/Node identities; and
2. create a separately named database in the existing hardened PostgreSQL server while preserving
   `saintvision_lan` and the desktop-owned tunnel.

No sudo command is required for the recommended path. The agent-side prerequisite is a small
reviewed database-name parameterization followed by an independently reviewed, exact-command
execution plan. Option B requires the two sudo package commands above **and** new recovery code; it
must not be attempted by installing venv alone.

## Review focus

- Reviewer: Claude.
- Verify the same-state enrollment and `control_epoch` impossibility claims, that the fresh path
  never deletes r2 resources or touches the tunnel, and that the proposed fully expired mode cannot
  turn an expired certificate into live authority.
- This draft authorizes no live change. A later execution requires independent review and a new
  explicit user instruction naming the selected path.
