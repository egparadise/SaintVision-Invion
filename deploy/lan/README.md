# Windows server and LAN workers: connection pilot

This package starts the real `inv-node` TLS transport and PostgreSQL-backed
`ObservationWorker`. The initial scope is enrollment, current mTLS possession,
heartbeat and resource snapshots. It does not provide web login or a production
Control Plane API. No OIDC provider is assumed. Workload dispatch, workspace
mounts, offered resources and project grants are not provisioned. The tenant
kill switch is enabled and the Node container does not mount the Docker socket.

The server runs the Python observer on Windows and a separate PostgreSQL 16
container on loopback. Existing containers and databases are preserved. The
worker uses Docker Desktop's Linux engine; Ubuntu supplies the installation
shell and OpenSSL. Go is not required there. Resource measurements describe the
Linux environment visible to the Node, not pooled Windows RAM or GPU capacity.

## Operator preparation

Use a private ignored state directory outside the public download directory:

```powershell
python tools/lan_pilot.py --state C:/Project/SaintVision-Invion/.work/lan-pilot init --server-ip 192.168.45.99 --node-ip 192.168.45.225
python tools/lan_pilot.py --state C:/Project/SaintVision-Invion/.work/lan-pilot bundle --go <path-to-go>
python tools/lan_pilot.py --state C:/Project/SaintVision-Invion/.work/lan-pilot serve
python tools/lan_pilot.py --state C:/Project/SaintVision-Invion/.work/lan-pilot observe
```

`--node-ip` may be repeated. A repeated `init` against the same state may add
addresses, but it never removes an existing Node or changes its Node ID, key,
channel, CA, database, or recovery epoch. The original single-Node command and
top-level state fields remain supported; the first Node is the compatibility
primary.

`init` requires the repository Python dependencies, Docker, an available local
`pgvector/pgvector:pg16` image and loopback port 55440. The image is resolved to
its local content ID. Credentials are randomly generated in the protected state
directory and are never printed. Database migrations run on this new database
only. The runtime role inherits `inv_kernel`, has no ownership or RLS bypass.
Keep the state directory: it contains the independently generated recovery epoch
and CA. A partial failure is preserved for inspection, never reset automatically.

The download service exposes only the requesting Node's `worker.zip`,
`node-cert.pem`, optional workspace bundle, and its own `/healthz`. It binds only
the configured LAN address and maps the TCP source address to one configured
Node ID; another configured Node cannot download that bundle. Hash sidecar files
remain on the server for the operator and are deliberately not served over this
channel. Add a Windows inbound rule for TCP 18081 whose remote-address list is
exactly the configured worker IP list printed by `serve`. This is a public-file
transfer service, not the product API. It has no upload/enrollment/signing
endpoint and never serves private state.

## Four Ubuntu workers on one pilot state

The Windows PC remains the server. Reserve four stable worker IPv4 addresses and
initialize all four against one state, isolated PostgreSQL database, CA, and
recovery epoch:

```powershell
python tools/lan_pilot.py --state C:/Project/SaintVision-Invion/.work/lan-pilot init `
  --server-ip 192.168.45.74 `
  --node-ip 192.168.45.81 --node-ip 192.168.45.82 `
  --node-ip 192.168.45.83 --node-ip 192.168.45.84
python tools/lan_pilot.py --state C:/Project/SaintVision-Invion/.work/lan-pilot bundle --go <path-to-go>
python tools/lan_pilot.py --state C:/Project/SaintVision-Invion/.work/lan-pilot serve
```

`bundle` prints one archive path and SHA-256 per Node. Send each worker only its
own SHA-256 through the already trusted operator channel; do not fetch a hash
from the bootstrap HTTP service. The same `/worker.zip` URL returns a different,
Node-bound archive according to the request source IP. A proxy, NAT, or shared
download host therefore is not supported for this enrollment step.

Before enrollment, each Ubuntu worker must meet all of these conditions:

- Docker Engine/CLI 25 or newer and Docker **server API 1.45 or newer**. Check
  both `docker version` and `docker version --format '{{.Server.APIVersion}}'`;
  an Engine 25 installation exposing only API 1.44 must be upgraded.
- NTP synchronized (`timedatectl show -p NTPSynchronized --value` prints
  `yes`) and no unresolved clock-skew alarm.
- The assigned static/reserved IPv4 is present locally. TCP 18443 inbound is
  allowed only from `192.168.45.74`; enforce this in the host/upstream firewall
  or Docker `DOCKER-USER` path and verify a non-server source is denied.
- TCP 18081 outbound to the server is available only for bootstrap downloads.

On each Ubuntu worker, download and verify its archive, extract it into a fresh
private directory, and run the shipped scripts from that directory:

```bash
curl --fail --output worker.zip http://192.168.45.74:18081/worker.zip
sha256sum worker.zip                         # compare out-of-band value
unzip worker.zip -d saintvision-worker
cd saintvision-worker
bash prepare-worker.sh                       # creates local key and prints public CSR
```

Return only the CSR to the server operator. For each CSR, the same command is
used; enrollment reads the CSR common name and selects the already assigned
Node ID rather than relying on command order:

```powershell
python tools/lan_pilot.py --state C:/Project/SaintVision-Invion/.work/lan-pilot enroll --csr <node-csr.pem>
```

Send that command's certificate file SHA-256 to the matching worker over the
trusted channel. The worker downloads `/node-cert.pem`, verifies the supplied
hash, places it beside the extracted files, then runs:

```bash
curl --fail --output node-cert.pem http://192.168.45.74:18081/node-cert.pem
printf '%s  node-cert.pem\n' '<operator-supplied-sha256>' | sha256sum --check -
bash finish-worker.sh
```

`finish-worker.sh` rechecks the fixed identity, preserves the key made by
`prepare-worker.sh`, copies only the assigned public/configuration material, and
delegates container startup to `start-node.sh`. Therefore the operator does not
need to call `start-node.sh` directly; doing so before the certificate and
identity checks bypasses the intended installation sequence. Finally run `status` and `observe
--once` on the server. Their `nodes` arrays must show four distinct Node IDs and
IP addresses; each Node is accepted only after its own current mTLS observation
and persisted resource snapshot. One failed worker does not authorize replacing
or re-enrolling the other three; preserve the state and retry that worker.

## Windows Control Plane host as a co-located worker

ADR-100 allows one additional Node identity in Docker Desktop on the Windows
Control Plane host. This is an explicit exception to the normal address
separation rule: `init` continues to reject `serverIP == nodeIP` unless the
operator supplies `--allow-server-node-colocation`. For the current pilot state,
add only the Windows host address and preserve every existing Node, key, channel,
CA, database, and recovery epoch:

```powershell
python tools/lan_pilot.py --state .work/lan-5node/node1 init `
  --server-ip 192.168.45.74 --node-ip 192.168.45.74 `
  --allow-server-node-colocation
python tools/lan_pilot.py --state .work/lan-5node/node1 bundle --reuse-image
```

The generated schema-v3 manifest derives co-location from the immutable server
and Node addresses. It must contain `coLocatedWithControlPlane: true`,
`measurementEligible.s05: false`, `measurementEligible.s07: false`, and
`exclusionReason: cp-host-colocation`. The installer rejects a manifest whose
declaration differs from its addresses or whose ADR-100 exclusions are missing.
Independent worker manifests use `null` eligibility here: this bootstrap does
not silently promote them into a measurement lane before the full preflight.

Restart `serve` after adding the Node so it reloads the state. Its
`allowedNodeIPs` and Windows TCP 18081 firewall remote-address list must now
include `192.168.45.74` exactly once. From the same Windows host, download
`http://192.168.45.74:18081/worker.zip`; source-IP routing returns only the
bundle assigned to the co-located Node. Compare it with that Node's separately
printed SHA-256, extract it into a fresh directory outside `.work/lan-5node`,
and use the ordinary Windows sequence:

```powershell
.\Prepare-Worker.ps1
# Send only the printed CSR to the operator, then enroll it on the server.
.\Start-Worker.ps1 -CertificateSHA256 <operator-supplied-file-sha256>
```

Do not copy schema-v3 scripts into an old schema-v2 extraction directory. The
new installer checks `manifest.json` first and fails closed with a schema-v3
message when scripts and bundle generation differ. Generate the v3 bundle and
extract it into a fresh per-Node directory. The existing three Ubuntu Nodes do
not require reinstallation; preserve their current keys, journals, containers,
channels, and working directories.

Docker Desktop must be 4.27 or newer (Docker Engine 25+), use Linux containers,
expose server API 1.45 or newer, and
have WSL integration enabled for the `Ubuntu` distribution because both
PowerShell entry points delegate into the shipped shell scripts. The configured
`192.168.45.74` address must be present on Windows. `Start-Worker.ps1` accepts an
exact existing Node firewall rule or creates one limited to local TCP 18443 and
the server address; it does not alter global profiles or add a port proxy.
`finish-worker.sh` invokes `start-node.sh`, so do not call the latter directly.
If the API is older, preparation stops with a `BLOCKED` message naming Docker
API 1.45, Engine 25+, and Docker Desktop 4.27+; do not bypass that preflight.

Bootstrap artifact routing uses the request's source address. A request for
`worker.zip` or `node-cert.pem` that arrives as loopback or a WSL NAT address
instead of the inventory Node IP receives HTTP 403 by design. Do not widen the
allowlist or add a portproxy. For the co-located Node, use the Node-specific
bundle produced on the Control Plane host and let `Start-Worker.ps1` perform the
certificate download from Windows, where the configured Node IP is visible.

Acceptance still requires `status` and `observe --once` to show this distinct
Node ID online with its own certificate, epoch, heartbeat, and current resource
snapshot. It counts as the one co-located identity but does not by itself prove
that five Nodes are registered; that requires all four Ubuntu identities too.
It remains excluded in advance from S05 timed P95 and the S07 independent-host
recovery denominator.
It may appear only in the all-five topology smoke and the separately named
`colocated-node-process-loss` scenario. A full Windows host outage is
`correlated-cp-node-host-loss` and remains `UNMEASURED` without an external
monotonic observer or separate Control Plane.

To withdraw the exceptional co-location opt-in without deleting identity or
evidence, run:

```powershell
python tools/lan_pilot.py --state .work/lan-5node/node1 revoke-server-node-colocation
```

The command first preserves the existing Node ID, files, key, journal, and DB
row while setting `disabled: true`,
`disabledReason: server-node-colocation-revoked`, and
`serverNodeColocationAllowed: false`. It then revokes an enrolled channel with
the normal monotonic channel audit, or records `not-enrolled`; it never deletes
the Node or rotates credentials. Disabled Nodes remain visible in `status` but
are excluded from bundles, enrollment, observation serving, and all wave target
sets. Restart `serve` after revocation so its source-IP allowlist is reloaded.

Revocation has no implicit reverse path. Re-running `init` with
`--allow-server-node-colocation` does not clear `disabled` and does not enable a
revoked channel. Do not edit private state, re-enroll the old certificate, or
create a replacement Node to work around this boundary. Reactivation requires a
separately reviewed operator command that revalidates the preserved Node/key,
uses the current channel version, appends a new audit entry, and only then
clears the disabled marker; that command is not implemented in this version.

Running `revoke-server-node-colocation` before a co-located Node exists is a
harmless idempotent opt-out: it persists
`serverNodeColocationAllowed: false`, reports empty `disabledNodes` and
`channels`, and does not alter any independent Node. It is not evidence that a
co-located identity or channel ever existed.

## Worker enrollment

1. Obtain `http://192.168.45.99:18081/worker.zip` and verify its SHA-256 against
   the value supplied independently by the server operator. Do not use a hash
   downloaded over the same connection as the trust anchor. Only after the hash
   matches, extract and run `Prepare-Worker.ps1` in Windows PowerShell.
2. Preparation checks Docker API >=1.45, loads the pinned Node image, and creates
   an Ed25519 key in Ubuntu's private `~/.local/share/saintvision/<nodeId>` folder.
   Send only the printed public CSR to the server operator through the trusted
   conversation. Never send `node-key.pem`.
3. The operator saves that CSR and runs `lan_pilot.py --state <state> enroll
   --csr <file>`. Enrollment validates its signature, key type and assigned Node,
   refuses requested extensions, and pins the resulting certificate in the DB.
   Existing different keys/channels require explicit rotation, not replacement.
4. In **Administrator Windows PowerShell**, run `Start-Worker.ps1
   -CertificateSHA256 <fileSHA256-from-operator>`. It verifies the certificate
   download, adds an inbound rule limited to TCP 18443 from the server IP, and
   starts the Node container with a durable named volume. It preserves existing
   containers and stops on container name conflicts. A retry can reuse an exact
   firewall rule and an unused volume bearing this Node's ownership label; the
   Node still validates the stored identity and epoch. Keys are copied through an
   in-memory archive with explicit container UID/GID 0:0 and permissions 600;
   their bytes and metadata are read back before startup. Host private keys are
   unchanged. Startup checks that the process remains running for five seconds.
   Docker exposes the port directly on the Windows worker IP;
   WSL portproxy and global network-profile changes are unnecessary.
5. Run `lan_pilot.py --state <state> status` on the server. Completion requires
   `observed: true`, a current persisted snapshot, and the Node online through
   a successful mTLS observation. A running container, successful ping, generated
   certificate, or download alone is not sufficient.

The image archive preserves its repository tag. Startup imports it into the
current engine, verifies Linux/amd64, filesystem layer digests and execution
configuration against the independently verified bundle, then uses that engine's
inspected content ID. It does not assume an image ID from a different store can
address the imported image. This check precedes volume/container creation.
Installer metadata upgrades compare the fixed identity fields and preserve the
worker private key. No Docker image-store setting is changed during recovery.

For the earlier installer failure `NODE-0005: pinned public key unavailable`,
first stop the assigned Node and inspect `signer.pub` metadata without printing
the private key. An owner of 1000 with mode 600 prevents the capability-dropped
root process from reading it. Obtain and independently verify the corrected
bundle, extract it, then run `Repair-Worker.ps1` on that worker. Repair requires
the assigned stopped container, matching Node/tenant/epoch and credential paths,
and its writable owned state volume. It recopies only the five existing local
credential/configuration files with explicit ownership and verifies their bytes;
it preserves the Node key, journal, image, volume and container configuration.
It starts the existing container and checks process stability. The operator must
still confirm an actual mTLS observation from the server before calling it connected.

CA lifetime is seven days; peer certificates and the initial allowlist last at
most six days. Expiry fails closed. This first bootstrap intentionally does not
implement renewal: preserve keys, advance the peer-policy version, and reconcile
the certificate channel through the existing operator contracts before extending
the pilot. Windows reboot does not automatically relaunch the server's observer
or download process. The worker and database use `unless-stopped`.

Stop the bootstrap and observer processes by their recorded PIDs after validating
their command lines. Remove only the named `SaintVision-LAN-Bootstrap-<workerIP>`
or `SaintVision-LAN-Node-<nodeId>` firewall rules to withdraw access. Stop the named
pilot containers to suspend the pilot. Do not delete volumes, unregister WSL,
reset Docker, or use `docker compose down -v` to recover connection failures.
