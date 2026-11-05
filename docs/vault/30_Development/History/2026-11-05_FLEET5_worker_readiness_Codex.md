---
doc_id: "HISTORY-FLEET5-20261105-WORKER-READINESS-CODEX"
title: "2026-11-05 FLEET5 known-worker read-only readiness and Linux Node procedure"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-05T14:52:00+09:00"
source_of_truth: "Git"
---

# FLEET5 read-only readiness

Task `FLEET5-20261105-WORKER-READINESS`, Orca task `task_4cfe9dbaa805`, dispatch `ctx_a8d8ef2a7042`; owner Codex, independent reviewer Claude **pending**. This deliverable measures existing endpoints and proposes deployment; physical FIVE acceptance remains blocked. No product code, deployment, enrollment, offers, workloads, service/container/account/SSH/CA configuration or automation was changed.

## Source and contract

- Actual worktree `D:/Project/SaintVisionI-Invion/fleet5-worker-readiness-20261105`; initial Orca branch `egparadise/fleet5-worker-readiness-20261105`, clean base `9b9061ed1b7bbc5b91ea2a035ea2a54fac6f010f`; delivery branch `agent/codex/fleet5-worker-readiness-20261105`.
- Product `59f0a3c2ff41ba1ae99a38515a2cdc65b2144067`; prior report `f020a664619ac8961fedd9fbb2b4ae5512fe8173`. Relevant repository installers/tools have no diff between product59f and this base. Existing live r5 still runs source03, with executorB5 separately preserved.
- Read Index `INDEX-PROGRESS-001` v1.0.393, Codex `WORKBOARD-CODEX-001` v1.0.354, coordinator kickoff `HISTORY-FLEET5-20261105-START-CODEX` v1.0.1; shared Obsidian Index v1.0.392 is the previous deployment report, not a replacement for the newer kickoff. Shared latest deployment and private r5 remain authoritative for the running system.
- Read GUIDE-001 v1.1.0, ADR-INDEX-001 v1.37.0, GOV-AGENT-001 v1.1.3, GOV-GIT-001 v1.1.4, GOV-CONTINUITY-001 v1.0.0, INDEX-VIRTUAL-COMPUTER-001 / ROADMAP-VIRTUAL-COMPUTER-001 v1.0.0, GOV-CONTINUOUS-001 v1.1.0, verification catalog v1.6.0 and axes canon v1.2.1; task registry v1.0.1 is unchanged. Skills: agent-delivery1.1.0, core-reliability1.0.0 and the current Orca CLI/orchestration guides.
- Scope follows [[2026-11-05_기존5대_오케스트레이션_착수_Codex]] and the user's clarification: **four Linux workers plus this Windows PC as CP-colocated Node**. Remote-desktop online labels do not establish Node enrollment. The unrelated five SSH aliases were not contacted.

Public structured evidence is in `docs/vault/30_Development/Evidence/fleet5-worker-readiness-20261105-codex/readiness.json`; the proposal and hashes are beside it. Exact expanded SSH argv, raw diagnostics, private inventory and process command lines remain in ignored `.work/fleet5-readiness`. Public commands below deliberately replace host/account/key/known-host values with references to that private receipt.

## Five physical slots and present result

| Slot | Measured result, 2026-11-05 KST | Policy / remaining gate | Next owner |
|---|---|---|---|
| worker1, Linux | SSH0; hostname matches private inventory; Ubuntu26.04.1, Python3.14.4; Docker29.1.3, serverAPI1.52/min1.44/Linux; r5 mapped | Existing project/runtime directories0700, accessible; inventory allowedFolders empty; live profile is lan-observe-v1 | Codex root: bind project-only folder proposal and later workspace proof |
| worker2, Linux | SSH0; hostname matches; Ubuntu24.04.1, Python3.12.3; Docker29.8.1, serverAPI1.56/min1.40/Linux; r5 mapped | Existing project/runtime directories and explicitly listed storage directory0700, accessible; listed MinIO data path is not a general Workspace grant | Codex root: separate new Workspace folder policy from MinIO storage |
| worker3, Linux | SSH0, Ubuntu26.04.1/Python3.14.4; DockerCLI29.8.1; system daemon active; ordinary Docker query1; sudo-n query1 | Current user lacks Docker socket access; serverAPI unmeasured; no r5 enrollment; allowedFolders empty | Authorized operator + Codex: review runtime access route, then measure serverAPI |
| worker4, Linux | Friendly label known from user; endpoint/account/profile unknown; **no probe** | Identity, capacity, credentials, resource/folder policy and enrollment all missing | User supplies actual Host/profile to coordinator; no guessed target |
| fifth, current Windows CP-colocated | User confirmed physical target; this worker did not repeat Claude's CP assessment | CP/runtime/API/folder/limits assessment is separate; shared CP failure domain | Claude + coordinator |

The intranet inventory's three legacy Node IDs differ from current r5 IDs. Worker1/2 match the r5 bindings and revision-two-node inventory by endpoint; those live IDs are authoritative for r5. Worker3 is absent from r5. Never combine legacy IDs and r5 IDs into a fictitious five-Node count or reuse an old key/channel in a fresh namespace.

## Worker measurements and resource policy

Initial sessions ran at **14:44:30 KST**, one per mapped endpoint, SSH exit0 each, lasting0.500/0.360/0.375s. All three reported12 logical CPUs, x86_64 and NTP synchronized. Worker1/3 kernel7.0.0-31-generic; worker2 kernel6.8.0-48-generic. All OS/cpu/memory/disk/NTP/OpenSSL/Bash subcommands exited0; only worker3's ordinary Docker version exited1. OpenSSL versions were3.5.5 /3.0.13 /3.5.5. Current GPU/driver capability was not measured.

| Slot | RAM total / available bytes | Root storage total / available bytes | Recorded inventory ceiling CPUm / RAM bytes / GPU / storage bytes |
|---|---|---|---|
| worker1 | 15,938,523,136 /12,175,622,144 | 249,792,131,072 /209,898,684,416 | 9000 /11,953,892,352 /1 /187,344,098,304 |
| worker2 | 16,480,641,024 /13,928,435,712 | 249,792,131,072 /210,625,785,856 | 9000 /12,360,480,768 /1 /187,344,098,304 |
| worker3 | 15,938,240,512 /13,776,588,800 | 249,792,131,072 /216,340,242,432 | 9000 /11,953,680,384 /1 /187,344,098,304 |

Capacity and free space are observations, not permission to offer all hardware. Existing inventory ceilings are recorded policy inputs; actual current grants, reservations and quota enforcement were not proved. Proposed per-Linux-worker total ceiling: **CPU2000m, RAM2,147,483,648B, GPU0, storage21,474,836,480B**, all below the three recorded ceilings and measured free capacity. Keep agent overhead within this total; the repository's initial agent envelope is0.5CPU/256MiB, and its Workspace proof uses1CPU/512MiB with network disabled. No resources were offered or reserved.

For worker1/3, concretely propose only `$HOME/.local/share/saintvision/fleet5-20261105-v1/workspaces`, mode0700, owned by the eventual reviewed runtime identity, initially empty and containing this project's files only. A separate equivalent folder is proposed for worker2; its existing MinIO directory must not become a Workspace mount. These are reversible policy proposals within the approved project scope, **not existing folders or permission to expose the whole home directory**. Nothing was created. Quotas, mount scope and exact manifest still require independent review; no new blanket permission question is introduced.

Remote UTC clock values were approximately1.121/1.076/1.106s ahead of local session start, with end-relative bounds0.621/0.716/0.731s. These are short-session offset bounds, not a calibrated clock-skew acceptance test; raw timestamps and elapsed intervals are in Evidence. NTP synchronization alone does not prove every future timing gate.

## Worker3 bounded diagnosis and available choices

Historical SSH authentication failure is superseded by this successful measurement. Coordinator messages `msg_6f907ef95323` and `msg_b86151021c9d` explicitly authorized two additional sessions beyond the original single probe; there was no auth retry loop.

- **14:47:51.735–14:47:52.168 KST**, SSH0: `docker --version`0; `systemctl is-active docker`0/active; `systemctl --user is-active docker`4/inactive; `docker context show`0/default; restricted context endpoint inspection0/unix, no DOCKER_HOST override. System socket exists, mode0660, groupdocker; current user is not in that group and cannot read/write the socket; rootless user socket absent. Raw group/user details stay private.
- **14:50:34.569–14:50:34.969 KST**, one `timeout 12 sudo -n -- /usr/bin/docker version --format '{{json .Server}}'`, exit1 with interactive-authentication-required markers. No password supplied, no prompt/retry or sudoers change. ServerAPI is still **unmeasured**, rather than inferred from the CLI version.
- Category: **active system Docker daemon, current account socket access denied; existing noninteractive operator route unavailable**. This is neither proof of an old API nor a stopped daemon.

Future reviewed options: (A) an already authorized operator performs only exact project-owned Docker startup, preserving the human account's current permissions; current sudo-n capability cannot be assumed; or (B) a dedicated Node service account with an explicitly reviewed socket/runtime policy. Docker socket access is a broad host capability, so do not quietly grant it to the human account. Current shipped workspace installer uses the rootful Docker socket; rootless support was not demonstrated. No usermod, ACL/chmod, service/account/sudoers change or daemon restart occurred.

## Live r5: two real HTTP samples, no restart

| KST sample start | Overview / web | Nodes / source / safety | Heartbeat and snapshot UTC, Node ordinals1/2 |
|---|---|---|---|
| 14:44:30.435640 | 200 /200 | exact pinned2; online/fresh; live-postgresql-mtls; runs0/offers0; killtrue/workloadfalse | 05:44:30.427091 /05:44:30.463507 |
| 14:44:43.046451 | 200 /200 | same exact2 and safety gates; observed ages6.0s | 05:44:38.181779 /05:44:38.183063 |

Actual sample-start interval **12.610811s**; requested wait12s; collector wait through second response12.438s. Both heartbeat and snapshot advanced for both Nodes. Source03 overview omits trust/leaf-expiry metadata; it was not silently invented. Public files contain **three unique leaves**: CP expires11-10 14:15:35KST, Nodes14:19:30 and14:19:42; all date-valid, each leaf's signature verifies against its matching issuer in the pinned public CA bundle. This is not a new CA ceremony or a fresh revocation-registry audit.

At **14:44:32.783 KST**, exactly one loopback listener each remained: web3000/PID25608, overview18082/PID54216, DB tunnel55448/SSH PID15408. r5 serve40748 (Python redirector child52720), console54216 (parent3756), observer49276 (child11276), web25608 persist; recorded prior helper33976 and observer launch parent36884 are absent. Tunnel15408 is the expected read-only inspected SSH forward. Full process command lines are private; hashed identities are in Evidence. Values agree with the previous r5 persistence record; a new reboot/terminal-termination experiment was not performed. Services are running, so no restoration or restart was proposed/executed.

Pre/post hashes match for **2,241 protected files**, including existing keys, receipts, state and selected private scripts/configuration; no changed file was found. Source03 and executorB5 HEADs remain `03e17c31cf535008d39534aaa80d3ae274bd75cc` / `b5b8ca68398517f6227a81caac02654a848c8b1d`, with tracked-clean status/exit0. Original993/new720 packets, guardacf8/configca684/released46 parameters are untouched. This is a scoped file comparison; it does not claim a new live automation scheduler audit. No automation commands were invoked.

Normal renewal starts **2026-11-08 14:15:35KST**. Preserve enabled Nov8 14:20, Nov9 12:15, Nov10 08:00 followups and all existing claims/latches. No Cycle, Transition, Recovery, Run now, force, clock manipulation or renewal-window bypass was executed.

## Fresh FIVE proposal, not executable yet

Hash-bound proposal: `docs/vault/30_Development/Evidence/fleet5-worker-readiness-20261105-codex/five-node-proposal.json`; hashes and private receipt digests: `artifact-hashes.json`. `executable=false` remains explicit because endpoint/identity/runtime/policy inputs are missing.

Use fresh namespace/state `fleet5-20261105-v1` / `.work/lan-5node/fleet5-20261105-v1`, isolated database `saintvision_lan_fleet5_20261105_v1`, fresh tenant/epoch and per-physical-host Node keys generated only on their assigned hosts. Proposed ports bootstrap18085/overview18086/web3005/tunnel55450/NodeTLS18447 are **candidates, not verified reservations**; check actual Windows/Linux collisions and exact firewall scopes before execution. Do not add Nodes to r5 or change its listeners, manifests, keys, DB, certificate schedule or observers.

Use exactly four verified Linux hosts plus this Windows CP host; aliases/VMs/containers do not create extra physical failure domains. Bind `hostId`, `failureDomainId`, Node ID, certificate, profile and exact private address in a fresh revision-fixed inventory only when proved. CP-colocated Node shares the CP host, has `measurementEligible.s05=false`, `s07=false`, `exclusionReason=cp-host-colocation`; it may join all-five topology smoke but cannot inflate independent-host latency/recovery denominators. Full CP-host outage stays unmeasured without an external observer.

Start future fresh acceptance observation-only with killtrue/workloadfalse and zero offers/runs. Then separately prove **lan-workspace-v1**, Docker serverAPI>=1.45 and server minimum API<=1.45 for the current client cap, authenticated project grants, permitted folders/limits and actual Workspace proof. Source runtime's older-API negotiation does not waive the stricter installer/FIVE gate. Two existing lan-observe-v1 Nodes are not FIVE Workspace acceptance.

## Practical Linux Node configuration and sharing: repository procedure

The following is a **future operator procedure after the exact packet's independent review**; no command in this section was executed on a worker. It uses `deploy/lan/README.md`, `prepare-worker.sh`, `finish-worker.sh`, `worker_config.py`, `tools/lan_pilot.py`, `tools/lan_workspace.py` and `worker_workspace.py` at product59f, whose file hashes are bound in the proposal. No universal installer or remote curl-to-shell command is invented.

1. On each Linux machine, confirm its actual assigned IPv4/account/profile and a dedicated project directory; preserve existing Node state. Check `python3`, `openssl`, `curl`, `unzip`, `sha256sum`, `timeout` and Docker with `command -v`; check `docker version` and `docker version --format '{{.Server.APIVersion}}'`, plus `timedatectl show -p NTPSynchronized --value` where systemd exists. On Ubuntu/Debian, only missing prerequisites should be supplied from that distro's supported package source; other distributions use their own supported equivalents. Do not assume a different distro needs apt or systemd. Engine branding/version alone does not establish API>=1.45; worker3 first needs a reviewed execution identity with runtime access. GPU remains disabled until separately validated.
2. On Windows CP, the operator prepares the **fresh private state**, fixed source/image, five verified addresses and `--allow-server-node-colocation` using the existing `lan_pilot.py init` / `bundle` interfaces. External PostgreSQL uses the reviewed admin/runtime DSN-file and dedicated tunnel/passfile pattern in the README, not embedded passwords. Exact DB/CA inputs, ports and paths are missing from this proposal and must not be guessed. Do not replay README's old sample addresses or run init/bundle against r5. `serve` binds to the reviewed address and allows only assigned Node source IPs; request routing cannot be widened to loopback/NAT/unrelated hosts to bypass a403.
3. Deliver each Node's own bundle and SHA-256 over the existing trusted operator channel; verify before extraction. The HTTP bootstrap serves public assigned artifacts only; the hash must arrive independently. Linux example, with reviewed values substituted:

```bash
set -euo pipefail
umask 077
curl --fail --max-time 30 --output worker.zip "http://${SV_CP_IP}:${SV_DOWNLOAD_PORT}/worker.zip"
printf '%s  worker.zip\n' "$SV_ARCHIVE_SHA256" | sha256sum --check -
# Stop here if verification fails. Use a fresh dedicated extraction directory.
unzip worker.zip -d saintvision-fleet5-worker
cd saintvision-fleet5-worker
bash prepare-worker.sh
```

`SV_CP_IP`, `SV_DOWNLOAD_PORT` and `SV_ARCHIVE_SHA256` are operator-supplied placeholders, not existing configuration. Run commands one at a time and stop on nonzero; `prepare-worker.sh` is a state-changing installer and may only run after review. It checks schema-v3 topology and API, preserves an existing matching Node identity, creates the local Ed25519 key and CSR, and loads the verified image. Share **only CSR**, never the private key.

4. CP operator runs `python tools/lan_pilot.py --state <fresh-private-state> enroll --csr <matching-public-csr> --ca-key <existing-reviewed-issuer-key-path> --ca-key-password-file <protected-password-file> --ca-chain <pinned-chain>` only under the reviewed new namespace. The password is supplied by protected file, never pasted in a command or chat. Return the assigned public certificate and independently supplied file hash to that worker. On Linux, download its own `node-cert.pem`, compare SHA-256, then run **`bash finish-worker.sh`**. The shipped finish script checks identity and calls start-node; do not bypass it by calling start-node first. Keep Node private key, state volume and journal local. Firewall policy permits only the CP to the exact Node TLS address/port; bootstrap access is separately bounded.
5. CP runs the existing `status` and `observe --once` commands against the **fresh state**. Require five distinct host-bound identities, current mTLS proof and advancing persisted heartbeat/resource snapshots, zero offers/runs and all safety gates. A remote-desktop green icon, successful SSH, certificate download or running container alone is insufficient.
6. “Sharing CPU/folders” is a later explicit project grant and Workspace profile step: create the reviewed managed folder only, record exact allowed limits/mount policy, build a verified Workspace package with `tools/lan_workspace.py --state <node-state> --prepared <verified-build-json> --evidence <matching-workspace-proof-json>`. This requires a clean matching first-Workspace proof and existing enrollment; it is not a generic Linux setup command. After separate package verification, Linux runs shipped **`python3 worker_workspace.py`** from the assigned extracted Workspace bundle; Windows uses its shipped `Enable-Workspace.ps1`. This upgrade changes containers and mounts the Docker socket, so operator/runtime review precedes it. It preserves identity/journal, produces an awaiting-server-mtls receipt and still needs server validation. Do not copy a bundle between hosts, mount whole homes/MinIO data, equate hardware capacity with offers, or enable workload submission merely because the Node is online.

The current `lan_workspace.py` packager selects the state's **primary** `nodeId` and has no `--node-id` option; it also builds/saves images through local Docker. It does not provide a turnkey five-target Workspace packaging command. Repeating it against one multi-Node state would package the same primary identity, so it must not be presented as five different Nodes. A reviewed per-target packaging path and matching clean execution proof are additional implementation/input gates before five `lan-workspace-v1` upgrades; do not hand-edit/copy private state to manufacture that path. The observation enrollment instructions above are the existing multi-Node path.

## Commands, failures, validation and handoff

Live commands were bounded `timeout 55 python3 -c <collector>` inside each established SSH vector: existing key/known_hosts, BatchMode=yes, IdentitiesOnly=yes, StrictHostKeyChecking=yes, UpdateHostKeys=no, ConnectTimeout=8, ConnectionAttempts=1, NumberOfPasswordPrompts=0, server-alive5/1; local subprocess timeout65s. Collector reads `hostname` via Python, `/etc/os-release`, `lscpu -J`, `free -b`, `df -B1 --output=size,used,avail,pcent /`, `docker version --format '{{json .}}'`, `timedatectl show -p NTPSynchronized -p Timezone -p NTP`, `openssl version`, `bash --version`, and stat/access for existing project-owned paths only. Per-command timeout5s. Expanded argv and exact diagnostic commands are private, SHA-256 bound by `artifact-hashes.json`.

HTTP GETs: `http://127.0.0.1:18082/pilot/v1/overview` and `http://127.0.0.1:3000/`, timeout4s, exactly two samples; local listener inspection used `Get-NetTCPConnection` limited to3000/18082/55448 plus `Get-CimInstance Win32_Process` filtered to r5 command ownership / exact previous PIDs. No business/medical/user data was traversed. SSH and HTTP reads can create ordinary server audit logs; “read-only” describes project/configuration state, not absence of access logs.

`lint_inventory` from `tools/s01_readiness_preflight.py` on the actual private five-slot inventory returned **exit1 /BLOCKED /inventory-values-missing: nodeCount5, missingFieldCount74, invalidFieldCount0**, on supported Python3.14.7. The first system-Python3.10 attempt failed importing StrEnum/exit1; it is preserved separately. No full authenticated HTTP/storage/5Node preflight was claimed. These are honest measured outcomes, not failed delivery or manufactured PASS. See the separate error/evidence page in this task's Evidence directory.

Publication gates, exact commits, push and Docs CI are recorded in `delivery-checks.json` / `delivery-receipt.json` beside the Evidence when available; independent review remains pending. Worker scope explicitly prohibits common board/task-registry edits and Obsidian apply; coordinator owns reconciliation and sync. No product build, new physical FIVE acceptance, GPU/latency/recovery trial or project workload was run here.

At14:54:22–14:55:23KST, eight local checks each exited0 using the existing source03 Python3.14.7 against this worktree: check_docs, check_ontology, sync_obsidian --check, check_contract_bindings, check_frontend_integrity, check_doc_single_source --ratchet, check_doc_path_citations --ratchet --base-ref HEAD, and git diff --check. Sync observed2,283 managed/8 pending/0 conflicts with no writes. Ratchets retained16 known duplicate pairs and290 known broken path citations, with no new/stale entries; these are backlog-aware passes, not zero-backlog claims. Documentation gates are repeated after final prose changes and staged diff is checked before commit; exact final receipts remain separate from product acceptance.

What was done: bounded known-worker/r5 measurement, identity/policy reconciliation and practical repository Linux procedure plus a non-executable fresh FIVE proposal. What was verified: live/read-only results and protected bytes above, local docs gates and exact Docs CI recorded separately. Next first action/owner: **Codex coordinator** joins Claude's actual Windows CP result with this proposal, receives worker4's real endpoint/profile, resolves worker3 runtime access via the authorized operator, and sends a complete private identity/policy/hash packet to **Claude** before any live action; existing r5 and renewal followups remain intact. Original48-task/VF-CL operational totals are unchanged.
