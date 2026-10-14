---
doc_id: "HIST-20261014-CARD296-CODEX"
title: "Card 296 fresh isolated r3 bootstrap database namespace"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-14T12:36:01+09:00"
updated: "2026-10-14T12:36:01+09:00"
source_of_truth: "Git"
---

# Card 296 fresh isolated r3 bootstrap database namespace

## Decision and non-goals

The user selected Card 294 Option A on 2026-10-14. This creates a new r3 pilot identity: a new
state directory, tenant, recovery epoch, Node IDs, Control Plane key, and Node-local keys. It does
not recover or silently reuse the expired r2 trust authority. The existing hardened PostgreSQL
server and desktop-owned SSH tunnel are reused only as transport; r3 gets a separately named
database and a separately named login role.

This change does not run the bootstrap. It does not touch the r2 state, journal, containers,
volumes, database, tunnel, shortcut, or either Node. Live execution requires independent review,
train 72 verification, and a new final operator instruction.

## Code boundary

- `deploy/lan/prepare-pilot-database.sh` keeps `saintvision_lan` as the backwards-compatible
  default and accepts only `saintvision_lan(_[a-z0-9]+)*`, at most 63 bytes. An r3 database such as
  `saintvision_lan_r3_0123abcd` derives the equally bounded login
  `inv_lan_runtime_r3_0123abcd`. No caller-provided identifier reaches SQL.
- A pre-existing container must have the exact ownership label, image identity, dedicated network,
  loopback publication, and matching private admin credential. The requested database and derived
  role must both be absent. A collision is preserved and refused; no `DROP`, overwrite, or role
  credential rotation occurs. An orphaned volume is also preserved and refused.
- The role is reasserted as `LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE
  NOREPLICATION`. Its generated secret crosses the container boundary through stdin after statement
  logging is disabled; it never appears in `docker exec` or `psql` argv.
- `deploy/lan/verify-pilot-database.sh` recomputes the database-to-role mapping and proves missing
  and wrong credential rejection, exact admin/runtime identity, all five negative role attributes,
  no unexpected membership, SCRAM-only host rules, loopback publication, and one owned dedicated
  network. For a namespaced database its private runtime secret is read from an owner-only file and
  passed on stdin.
- `tools/lan_pilot.py` applies the same namespace and mapping to `init`, `bind-db-auth`, and pgpass
  parsing. Admin and runtime DSNs must select the same loopback host, port, and database. The r3
  runtime DSN must name the derived r3 role; the old `inv_lan_runtime` credential is never rotated.

Focused negative tests cover invalid names, a pre-existing database, role privilege drift, SCRAM
drift, membership drift, mismatched admin/runtime databases, and both default and namespaced DSNs.
The behavior tests are the mutation boundary: deleting name validation admits injection syntax;
deleting the collision check reaches the derived-role write; deleting any privilege or membership
check accepts an elevated role; replacing the derived role with the old role breaks the r3 bind
fixture.

## Reviewed train 72 execution plan

The following is the exact command shape. Values in angle brackets are operator-owned inventory or
private paths, not values to copy from this public record. `$Train72` must be the independently
verified full train 72 SHA. Do not substitute a PR head.

### 1. Freeze names and prove ports are free

```powershell
$Train72 = '<verified-train-72-full-sha>'
$Short = $Train72.Substring(0, 8)
$State = "D:\Project\SaintVisionI-Invion\.work\lan-5node\r3-$Short"
$Database = "saintvision_lan_r3_$Short"
$DownloadPort = 18083
$NodePort = 18444
$AdminDsn = "D:\Project\SaintVisionI-Invion\.work\intranet\db-private\$Database-admin.dsn"
$RuntimeDsn = "D:\Project\SaintVisionI-Invion\.work\intranet\db-private\$Database-runtime.dsn"

git rev-parse HEAD
Test-Path -LiteralPath $State
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object LocalPort -In @($DownloadPort, $NodePort)
```

The first command must equal `$Train72`, `Test-Path` must be `False`, and the port query must be
empty. The desktop-owned `127.0.0.1:55448` tunnel is expected to remain listening and must not be
stopped. The r3 state deliberately uses the same `dbPort=55448`, so the existing tunnel can carry
both database names.

### 2. Add the isolated database on the existing Linux PostgreSQL host

Run from the already approved non-root operator session on that Linux host. The image reference
must be the exact digest-pinned image already bound to `saintvision-card150-pilot-db`; the script
refuses a different image ID. `<db-private-dir>` is the existing owner-only directory and is not
under Git.

```bash
train72='<verified-train-72-full-sha>'
short="${train72%${train72#????????}}"
database="saintvision_lan_r3_${short}"
postgres_image='postgres@sha256:<approved-existing-64-hex-digest>'

bash deploy/lan/prepare-pilot-database.sh \
  "$postgres_image" saintvision-card150-pilot-db 55440 \
  '<db-private-dir>' saintvision-card150-pilot-db-internal "$database"
bash deploy/lan/verify-pilot-database.sh \
  saintvision-card150-pilot-db saintvision-card150-pilot-db-internal \
  "$database" '<db-private-dir>'
```

Both commands emit only redacted JSON. A collision exits nonzero and is not authorization to
delete or rename anything. Transfer only the two generated namespaced pgpass files through the
approved private channel. On the Control Plane, rewrite only their port field from remote loopback
`55440` to tunnel loopback `55448`, keep exactly one line, and set owner-only permissions. Do not
print either file. Create the two DSN files with these non-secret fields:

```text
host=127.0.0.1 port=55448 dbname=<database> user=postgres passfile='<r3-admin-pgpass>'
host=127.0.0.1 port=55448 dbname=<database> user=<derived-r3-runtime-role> passfile='<r3-runtime-pgpass>'
```

### 3. Build once on Linux, initialize once on the Control Plane

The Windows Control Plane must not run Docker Desktop. On an approved Linux builder, check out
`$Train72` cleanly, build `deploy/lan/Dockerfile.node.remote`, then save the image and its
`docker image inspect` JSON. Transfer those public build artifacts to the Control Plane and bind
them with `bundle --prebuilt-image` and `--prebuilt-inspect`; an older r2 archive is forbidden.

```powershell
python tools/lan_pilot.py --state $State init `
  --server-ip '<control-plane-lan-ip>' `
  --node-ip '<node-1-lan-ip>' --node-ip '<node-2-lan-ip>' `
  --download-port $DownloadPort --node-port $NodePort `
  --admin-dsn-file $AdminDsn --runtime-dsn-file $RuntimeDsn `
  --ca-key 'D:\Project\SaintVisionI-Invion\.work\intranet\ca\intermediate\private\intermediate-key.pem' `
  --ca-key-password-file 'D:\Project\SaintVisionI-Invion\.work\intranet\ca\intermediate\private\intermediate-key.pass' `
  --ca-chain 'D:\Project\SaintVisionI-Invion\.work\intranet\ca\intermediate\certs\ca-chain.pem'

python tools/lan_pilot.py --state $State bind-db-auth `
  --admin-passfile '<r3-admin-pgpass>' --runtime-passfile '<r3-runtime-pgpass>'
python tools/lan_pilot.py --state $State bundle `
  --prebuilt-image '<train72-linux-node-image.tar>' `
  --prebuilt-inspect '<train72-linux-node-image-inspect.json>'
python tools/lan_pilot.py --state $State serve
```

`init` creates new identities and applies migrations only to `$Database`. Card 287's fresh worker
path does not import `cryptography` and does not require `python3-venv`: each generated worker
bundle carries shell scripts plus the standard-library-only `worker_config.py`. Node Docker/NTP,
network reachability, and local static-address gates still apply.

### 4. Enroll each Node without moving its private key

For each assigned archive, compare its out-of-band SHA-256, extract into a new private directory,
and run `bash prepare-worker.sh` on that Node. It creates the new r3 Node key locally. Return only
`node.csr.pem` to the Control Plane, then run:

```powershell
python tools/lan_pilot.py --state $State enroll `
  --csr '<node-csr.pem>' `
  --ca-key 'D:\Project\SaintVisionI-Invion\.work\intranet\ca\intermediate\private\intermediate-key.pem' `
  --ca-key-password-file 'D:\Project\SaintVisionI-Invion\.work\intranet\ca\intermediate\private\intermediate-key.pass' `
  --ca-chain 'D:\Project\SaintVisionI-Invion\.work\intranet\ca\intermediate\certs\ca-chain.pem'
```

Return only the matching public certificate and its out-of-band hash. On that same Node run
`bash finish-worker.sh`. Repeat independently for the second Node. A failure preserves the new r3
state and the other Node; it never authorizes reuse of an r2 key or deletion of an r2 container.

### 5. Observe before switching the desktop entry point

```powershell
python tools/lan_pilot.py --state $State observe --once
python tools/lan_pilot.py --state $State observe
# In a separate operator terminal, keep the public bootstrap service on the same $State.
python tools/lan_pilot.py --state $State serve
```

Acceptance requires exactly two configured r3 Nodes, both `online` and `fresh`, with heartbeats
newer than their successful `finish-worker.sh` executions. Workload execution remains disabled.
Only after that evidence may the existing owned desktop shortcut be repointed:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\deploy\lan\Register-DesktopShortcut.ps1 `
  -StatePath $State `
  -DatabaseTunnelTarget '<approved-user>@<approved-db-host>' `
  -SshKeyPath '<approved-existing-ssh-private-key-path>'
```

The shortcut retains the established tunnel boundary. Do not terminate `127.0.0.1:55448` while
the desktop launcher owns it.

## Preservation and rollback boundary

- Keep `.work/lan-5node/r2-7057dcd0`, every Card 292/293 journal, the old database, all old
  containers, and all volumes. No cleanup command belongs to Card 296.
- Before desktop cutover, rollback means stop only r3 observer/bootstrap processes after validating
  their recorded command lines; the r2 artifacts remain untouched but are not asserted usable.
- After cutover, a failed r3 observation does not make expired r2 TLS acceptable. Preserve the r3
  failure state and return to review.

## Review handoff

Reviewer: Claude. Verify the database/role namespace is one-to-one, every collision is refused
before database or role mutation, secrets never enter argv, `init` and `bind-db-auth` accept the
namespaced passfile pair, the default r2 name remains compatible, and the operational plan has no
live execution claim.
