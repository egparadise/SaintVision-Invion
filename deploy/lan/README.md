# Two Windows PCs: connection pilot

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

`init` requires the repository Python dependencies, Docker, an available local
`pgvector/pgvector:pg16` image and loopback port 55440. The image is resolved to
its local content ID. Credentials are randomly generated in the protected state
directory and are never printed. Database migrations run on this new database
only. The runtime role inherits `inv_kernel`, has no ownership or RLS bypass.
Keep the state directory: it contains the independently generated recovery epoch
and CA. A partial failure is preserved for inspection, never reset automatically.

The download service exposes only `worker.zip`, `worker.sha256`, `node-cert.pem`
and its own `/healthz`. It binds only the configured LAN address and accepts only
the server and specified worker IP. Add a Windows inbound rule for TCP 18081 from
the worker IP only. This is a public-file transfer service, not the product API.
It has no upload/enrollment/signing endpoint and never serves private state.

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
   Node still validates the stored identity and epoch. Keys are copied with private
   Linux file modes. Docker exposes the port directly on the Windows worker IP;
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
