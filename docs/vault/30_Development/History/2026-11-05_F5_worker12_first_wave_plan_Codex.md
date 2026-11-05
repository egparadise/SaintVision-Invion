---
doc_id: "HISTORY-F5-20261105-WORKER12-FIRST-WAVE-PLAN-CODEX"
title: "2026-11-05 F5 worker1/2 first-wave plan and Docker API floor correction"
version: "1.1.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-05T15:38:00+09:00"
source_of_truth: "Git"
---

# F5 worker1/2 first wave: nonexecuting packet

Task FLEET5-FIRST-WAVE-PLAN-20261105, Orca task `task_05d9dcda1dca`, dispatch `ctx_faa86b318dd8`. Owner Codex; independent reviewer Claude. Claude53f5722f reviewed the early packet and required P1–P8; the corrected packet was sent to active dispatch `ctx_88febf51813a` / message `msg_e0847905db9f`. This task prepares a concrete plan and corrects narrow minimum-version text; it performs **no remote configuration change, install, enrollment, CA/DB/container creation, workload, resource offer or password authentication**. Root explicitly authorized one read-only noninteractive sudo capability query per known worker1/2; both failed and were not retried.

Branch `agent/codex/fleet5-first-wave-plan-20261105`, actual worktree `D:/Project/SaintVisionI-Invion/fleet5-worker-readiness-20261105`, base `6ba9ee4686ab2ec1b2e566b13edef016fa4f8d4e`; runtime product pin `59f0a3c2ff41ba1ae99a38515a2cdc65b2144067`. Read current local Index1.0.393/Codex1.0.354, agent-delivery1.1.0/core-reliability1.0.0, the unchanged required governance versions recorded in [[2026-11-05_FLEET5_worker_readiness_Codex]], and Claude's **published138ece54** CP Evidence and History directly from Git. Common boards/registry and Obsidian apply remain untouched.

## Decision and smallest next gate

**A short attended worker1/2 connection phase is not barred by a Nov10 date, but execution is currently blocked by real host-firewall authority and outstanding proof gates.** Both authorized sudo-n firewall reads returned1/authentication-required. An actual authorized operator must install and prove the narrowly scoped rules; no privileged Docker helper or socket-group grant may bypass this. There is no measured shared-resource conflict requiring blanket postponement. CP-colocated Node installation remains blocked by API1.41/no Ubuntu and its own policy/upgrade requirements; phase1 does not require local Docker, a CP upgrade or the CP Node.

Use existing trusted SSH/SCP for per-Node public bundle/CSR/certificate transfer. This removes any need for a new Windows HTTP bootstrap listener, firewall exception, web server, console daemon or Ubuntu distro. Only a new loopback DB tunnel and sequential transient Python commands are needed on Windows. Linux worker1 is the candidate builder after actual cap proof; worker2 hosts the proposed isolated PG16 database. New phase1 Nodes remain `lan-observe-v1`, **offers0/runs0/killtrue/workloadfalse**. No Workspace folder or contribution mount is requested.

The phase is **two of planned five**, visibly partial. worker3 runtime authority, worker4 endpoint/profile and Windows CP Node readiness remain unresolved; no placeholder endpoints or invented Node IDs enter init. All-five registration/workspace/independent-host acceptance remains false. The screenshot's friendly names are not substituted for private endpoint proof.

Next technical gate/owner: **Claude** reviews the exact public plan and private resolved command vectors. **Codex coordinator** then admits only the isolated first phase after current port/source/headroom/owned-name/firewall checks; newly generated identity/CA/epoch/image hashes form another mandatory pre-install checkpoint. This is not permission to execute the packet during this planning task.

## Concrete namespace and collision measurements

Namespace/state `f5-59f0a3c2-20261105-w12` / `.work/lan-5node/f5-59f0a3c2-20261105-w12`; database `saintvision_lan_f5_59f0a3c2_20261105_w12`; separate database runtime role derived by the shipped helper; unique container `saintvision-f5-59f0a3c2-20261105-w12-db`, network suffix `-db-net`, volume suffix `-db-data`. The new state and managed worker directories do not exist. No namespace/port was bound at the OS level.

| Plan binding | Read-only evidence | Reservation meaning |
|---|---|---|
| Windows loopback55458, SSH tunnel |15:10:01KST Get-NetTCPConnection: no listener | Only this packet; recheck immediately before binding |
| worker2 loopback55458, new PG | Both workers' `/proc/net/tcp{,6}`: no listener; all container HostConfig.PortBindings checked0, no conflict | New DB only; never old55447/55448 |
| worker1 LAN18515, worker2 LAN18515 | Both listeners absent; existing16/8 container port configurations inspected without names/env/data, no conflict | One distinct binding per existing physical endpoint |
| optional bootstrap18115 | No CP/worker listener/container/historical-state overlap | Reserved in metadata but **unused in SCP-first phase** |

This explicitly supersedes the previous unverified18085/18086/18447 candidates; they appear in historical deployment bindings and are not reused. Current/historical state-file ports and Claude's published used-port list were compared. A measured-free port is not a durable lock: the packet reserves the chosen values logically and requires a new collision check before each real bind.

At15:09:58KST, bounded SSH reads to the two established mappings exited0. Worker1 API1.52/min1.44, worker2 API1.56/min1.40; memory/disk/Docker-version/port-list queries0. A second bounded read inspected only all containers' port bindings and the selected cached PostgreSQL digest, exit0 on both. No payload, environment variables, other-project configuration or user data was read. Worker1's pinned Go image is cached/inspect0; worker2's corresponding Go inspect returned1/cache absent, so **build is assigned to worker1**, not represented as an available capability on both.

## Resource policy, actual CP impact and timing

Claude's138ece54 measured **25 CP containers,8 running, actual Docker API1.41, no Ubuntu WSL distro and0.55GB host free physical RAM**. Its inventory is not authority to stop/update any of those containers. It also identifies r5 as remote-DB/SSH based, not a local r5 Docker container.

This task measured Windows free physical RAM **1,128,951,808B** at15:10:01.315KST, with no selected-port listeners. Admission proposes at least512MiB free before each transient step; stop the new phase if free falls below256MiB or r5 freshness regresses. Those are proposed admission/stop thresholds, not a hard Windows memory reservation or proven future peak. No local Docker/WSL restart, CP Node, source checkout copy, new web/console process or new automation is required. An existing tracked-clean exact59f source is available read-only. The corrected packet uses the **non-r5 main repository .venv Python3.14.7**, always `-B` / `PYTHONDONTWRITEBYTECODE=1`, no pip and full environment-tree pre/post comparison. Its required imports and exact59f CLI help returned0; all7,333 files matched before/after. Requirements closure source03-to59f has no diff, but no r5 interpreter is selected for future phase execution.

| Worker | New F5 total admission ceiling | Measured available RAM / root storage | Phase impact |
|---|---|---|---|
|1 |CPU2000m /RAM2,147,483,648B /GPU0 /storage21,474,836,480B |9,414,676,480B /209,872,973,824B |Proposed2CPU/1GiB build; actual cap proof required before build acceptance; then Node0.5CPU/256MiB |
|2 |Same |13,966,442,496B /210,626,019,328B |PG1CPU/768MiB plus Node0.5CPU/256MiB, total1.5CPU/1GiB |

These proposed ceilings fit the existing recorded9000m CPU, RAM11,953,892,352B /12,360,480,768B, storage187,344,098,304B and GPU1 limits; observed free capacity is not an offer/grant. The resource proposal is within the existing project authorization and goes to technical review, with no new blanket permission question.

Only new `$HOME/.local/share/saintvision/f5-59f0a3c2-20261105-w12` inputs/artifacts and worker2 db-private directories are proposed, mode0700/credential files0600. The unused workspace directory is omitted. Shipped prepare/finish additionally create the **new assigned Node ID's** private directory under `$HOME/.local/share/saintvision/<fresh Node ID>`; assert it is absent and disjoint from every old state's IDs first. No whole-home, business/medical or existing MinIO path is mounted, and no storage contribution/Workspace combination is requested. The new named DB volume and owned image/artifact bytes count toward the20GiB **policy admission ceiling**. The shipped helper does not enforce a hard filesystem quota; actual owned usage and abort thresholds remain explicit.

PG/Node limits are present in their shipped helper commands. Classic builder flags appearing in help do **not** prove enforcement. Before the source build, a separately hashed nonexecuted cap-probe Dockerfile must establish actual classic RUN cgroup values and HostConfig CPU quota200000/period100000/memory1073741824; retain legacy-builder output and inspect actual source RUN containers too. Until that proof, caps are unproved proposals. Stop on unsupported builder behavior or missing proof; do not omit flags or change global builder settings. Record actual GOPROXY/GOSUMDB/egress (including any direct fallback) for jsonschema/v6@v6.0.2 and x/text@v0.14.0; go.sum/TLS verification remain enabled. A client timeout does not prove daemon exit: journal exact new RUN CIDs/creation/command/image ownership and settle or stop only matching new RUN containers; ambiguous completion blocks further work without pruning or touching r5. Heavy build is sequential and must stop if r5 health regresses.

The existing r5 SSH tunnel15408 was read-only mapped to **worker1 as its database host**. The proposed worker1 build therefore shares hardware with r5 PostgreSQL; the1GiB/2CPU limit,9.41GB measured available RAM and live before/after gate address this real coupling. No observed saturation/degradation proves a Nov10 delay is necessary. The new F5 database on worker2 would also share worker2's failure domain: losing that host affects its new Node and the F5 database together. This first phase proves connection only; later recovery acceptance must model that correlation or separate storage and must not call it independent Node-host recovery.

## Input hashes and exact command sequence

Public packet: `docs/vault/30_Development/Evidence/f5-first-wave-plan-20261105-codex/first-wave-plan.json`; digest receipt `packet-digests.json`. Resolved private parameters and exact transport/command vectors are ignored under `.work/f5-first-wave-plan`; they contain real existing host/account/source paths and no password/key bytes. Raw SSH output stays there. The source archive is a **local-only staged file**, not transferred or installed:

- Source archive:757,760B, SHA256 `a9f0a3b88c6b9f31b5133bf1bce388fa574f201832d32b324b1a08ed3d9911a9`; produced by `git archive --format=tar 59f0a3c2ff41ba1ae99a38515a2cdc65b2144067 deploy/lan services/node-agent packages/contracts-go` from the exact59f source.
- Go base: `golang@sha256:60deed95d3888cc5e4d9ff8a10c54e5edc008c6ae3fba6187be6fb592e19e8c0` already cached on worker1.
- Worker2 PG16 image: `postgres@sha256:1a6ab3f5345eb6dbe04a1349529caabdb0ab09293a09590fad07b2246bfa4b54`, cached image inspected0. No tag-only upgrade or image pull occurred.
- `sourceFileSHA256` binds Git blob bytes for tools, installer/database scripts, Go module files and requirements. Generated Node IDs/epoch/CA/leaf/image digests do not yet exist; **they are not fabricated as fully bound runtime outputs**. Freeze those in a second receipt after reviewed init and before Node preparation.

The following commands are **planned, not executed**. Variables represent values bound in the private packet, not values to guess. Every command records direct exit/KST and stops on nonzero; PowerShell gates use immediate `$LASTEXITCODE` capture and throw, never a semicolon-chained next action. Exact corrected vectors use the main non-r5 interpreter with `-B`; schematic `python` below denotes only that bound executable.

1. Verify exact59f tracked-clean source and staged archive hash; repeat port/resource/namespace absence checks. On each worker create only the new managed directory, then SCP, then verify source archive hash and extract into its new `input` directory, in that order. Existing SSH key/known_hosts, BatchMode, strict host-key checking and known endpoint mappings persist. Do not use sudo or retry candidate accounts.
2. Worker2, against only the new names:

```bash
set -euo pipefail
bash "$F5_INPUT/deploy/lan/prepare-pilot-database.sh" "$F5_PG_IMAGE" \
  saintvision-f5-59f0a3c2-20261105-w12-db 55458 "$F5_ROOT/db-private" \
  saintvision-f5-59f0a3c2-20261105-w12-db-net saintvision_lan_f5_59f0a3c2_20261105_w12
bash "$F5_INPUT/deploy/lan/verify-pilot-database.sh" \
  saintvision-f5-59f0a3c2-20261105-w12-db \
  saintvision-f5-59f0a3c2-20261105-w12-db-net saintvision_lan_f5_59f0a3c2_20261105_w12 "$F5_ROOT/db-private"
```

The helper refuses old-name/ownership mismatches, creates the new volume/network/PG role, enforces loopback exposure and verifies missing/wrong credentials and privilege/SCRAM boundaries. No old database is a target. No verification authentication attempt was made in this planning task.

The selected worker2 digest's image metadata **PG_MAJOR=16** was read successfully; no worker1 alternate PostgreSQL digest is selected. After future startup, query `SHOW server_version_num` inside only the new owned container using its new password file on stdin (never printed), and require160000–169999 **before migrations**. A tag or image-major field alone is not actual server-version proof.

3. In a dedicated attended owner context, start only the **new** SSH `-N -o ExitOnForwardFailure=yes -L 127.0.0.1:55458:127.0.0.1:55458` to established worker2; keep existing55448 untouched. Securely SCP only the new DB's two passfiles into a new owner-only Windows private directory. Construct admin/runtime DSN files with `psycopg.conninfo.make_conninfo`, localhost55458/new database/appropriate new role/absolute protected passfile; **omit password fields** and never print file contents.
4. On Windows use the existing pinned Python and the tracked-clean exact59f tool path:

```text
python -B <source59f>/tools/intranet_pki.py --ca-dir <fresh-F5-node-CA> init-node-mtls --root-password-file <new-path-outside-online-CA>
python -B <source59f>/tools/lan_pilot.py --state <fresh-f5-state> init --server-ip <verified-CP-IP> --node-ip <verified-worker1-IP> --node-ip <verified-worker2-IP> --download-port 18115 --node-port 18515 --admin-dsn-file <new-admin.dsn> --runtime-dsn-file <new-runtime.dsn> --ca-key <fresh-encrypted-intermediate-key> --ca-key-password-file <fresh-intermediate-password-file> --ca-chain <fresh-intermediate-root-chain>
python -B <source59f>/tools/lan_pilot.py --state <fresh-f5-state> bind-db-auth --admin-passfile <new-admin.pgpass> --runtime-passfile <new-runtime.pgpass>
```

No `--allow-server-node-colocation` or worker3/4/CP placeholders belong to this phase. **Codex root selected a fresh external Ed25519 intermediate/chain at first init** for the continuing five-Node campaign; a disposable default seven-day CA is superseded. The source59f PKI tool generates encrypted root/intermediate keys, protected password files, a public chain and revocations registry only after review; the root passphrase destination is new and outside the online CA directory. Nothing was generated here, no r5 issuer/trust/key is reused, and offline root custody is not claimed. Bind actual new private/public file hashes and all NotAfter values after generation. A bounded catalog covers10 old states plus inventory:9 old tenants/epochs,20 Node IDs and4 CA certificates; require new tenant/epoch/IDs/CA DER fingerprints disjoint from all of them before installation. Codex root owns expiry and legitimate same-key batch renewal; r5's three followups are never repurposed.
5. Derive `F5_AGENT_TAG=saintvision-lan-node:<new-epoch-first8>` from the new state and pin that derivation. Worker1 builds only the verified source context:

```bash
set -euo pipefail
export DOCKER_BUILDKIT=0
timeout 300 docker build --pull=false --cpu-period=100000 --cpu-quota=200000 \
  --memory=1073741824 --memory-swap=1073741824 \
  -f "$F5_INPUT/deploy/lan/Dockerfile.node.remote" -t "$F5_AGENT_TAG" "$F5_INPUT"
docker image inspect "$F5_AGENT_TAG" > "$F5_ROOT/node-image-inspect.json"
timeout 90 docker save --output "$F5_ROOT/node-agent.tar" "$F5_AGENT_TAG"
sha256sum "$F5_ROOT/node-agent.tar" "$F5_ROOT/node-image-inspect.json"
```

`DOCKER_BUILDKIT=0` is scoped to this operator build invocation, not a global daemon change; verify the selected bounded builder actually works and stop otherwise. Source `go.sum` pins dependencies. No source cache, r5 tag or unrelated images are pruned. SCP the new archive/inspect to CP, verify actual hashes/size (reject archive>128MiB), then run `python <source59f>/tools/lan_pilot.py --state <fresh-f5-state> bundle --prebuilt-image <new-node-agent.tar> --prebuilt-inspect <new-inspect.json>`. The tool validates tag, configuration/layers/content IDs without local Docker.
6. SCP each own `public/nodes/<new ID>/worker.zip` and separately pinned hash to its assigned worker, verify before extraction, run shipped `bash prepare-worker.sh`; return **CSR only**. CP enrolls only that CSR with `python -B <source59f>/tools/lan_pilot.py --state <fresh-f5-state> enroll --csr <assigned-public-CSR> --ca-key <fresh-encrypted-intermediate-key> --ca-key-password-file <fresh-intermediate-password-file> --ca-chain <fresh-chain>`. SCP its own leaf plus independently pinned hash back, verify, then `bash finish-worker.sh` from that assigned extraction. Do not call start-node directly, move existing keys, reuse an old ID or mount the Docker socket. The private packet now contains exact **authorized-host-root** DOCKER-USER allow/deny vectors scoped to each verified Node IP and `-m conntrack --ctorigdstport 18515` (Docker DNAT's container port18443 is not the original destination). It never flushes unrelated rules. Both sudo-n capability queries were1/auth-required, so this is a real external operator gate. Require simultaneous successful fresh-CA CP observation, failed worker3 TCP connection and rule-counter/exit evidence; an absent listener alone cannot prove filtering. No privileged Docker, ACL or socket-group workaround is allowed.
7. Run `observe --once`, wait12s, run `observe --once`, then `status` against only new state. Bind exact KST/exit/source SHA, actual new2 Node IDs, fresh advancing mTLS heartbeat/snapshot and safety gates to Evidence while separately checking old r5 is still healthy and byte-identical. No `lan-workspace-v1` upgrade, project grant or offer is part of connection acceptance. No persistent F5 observer/web/console/schedule is claimed by this attended phase.

## P1–P8 corrected packet and current proof boundary

Claude53f5722f reviewed the early `b1bacdd3` packet; the published22fa/c23 receipt and their CI are preserved as history, **not execution acceptance**. Root instructed a distinct corrected commit. The latest `first-wave-plan.json` / `packet-digests.json` supersede those draft hashes and bind corrected private vectors. No source/storage/Workspace guard repair is duplicated here: root assigned that separate source change to task_30f1fb073ec1, while this wave keeps storage and Workspace disabled and its exact59f source archive unchanged.

| Review | Correction and measured result | Remaining execution gate |
|---|---|---|
|P1 |Fresh external Node intermediate/chain, encrypted key/password-file/revocations paths bound at first init; Codex root owns expiry |Reviewed generation, actual hashes/NotAfter and same-key renewal runtime; no default pilot CA fallback |
|P2 |Exact CP-only original-destination DOCKER-USER vectors and CP-success/worker3-denial proof; one permitted sudo-n query each returned1/auth-required |Actual authorized host-root operator is unavailable in this session; no retry or Docker privilege bypass |
|P3 |Hashed nonexecuted cgroup/HostConfig cap-probe; actual source RUN proof, egress/go.sum and daemon ownership/timeout settlement specified |Actual classic-builder/cap/clean completion proof, otherwise abort |
|P4 |Selected worker2 cached digest PG_MAJOR16 read0 |Actual new server_version_num160000–169999 before migration |
|P5 |Non-r5 main Python3.14.7 imports/help0,7,333 files unchanged before/after |Always -B/no pip; repeat complete tree pre/post comparison around future phase |
|P6 |10 old states plus old inventory catalog,9 tenants/epochs,20 IDs,4 CA certs |Generated values disjoint and actual root/intermediate/CP/Node notAfter in receipt |
|P7 |Unused workspace directory removed |Only private input/artifact/DB paths; policy ceiling is not a quota or storage/Workspace grant |
|P8 |Exact reviewed exclusion intervals and attended process lifetime decided |No new step within windows; new tunnel/idle F5 resources settled and stopped before entry |

Exclusions are **Nov8 14:20–18:32, Nov9 12:15–16:27, Nov10 08:00–12:12KST** (slot +600s grace +14520s maximum wait). They do not bar a safe admitted phase today or outside those intervals, but actual r5 completion-unknown/child activity can extend a pause. No new F5 launch/registration/build begins in a window. Tunnel55458 is attended only: close only its recorded new PID/creation/command identity at session end and before each exclusion; never touch existing15408/55448. After time-bounded connection evidence, stop only the new owned F5 Nodes/PG before a window and retain all keys/epoch/volume/state. Stopped F5 resources are not reported online, and no new automation or implicit persistence is claimed.

Legitimate fresh-F5 renewal uses the actual earliest leaf NotAfter minus48h, outside those r5 exclusions, without clock/window/expired-authority bypass:

```text
python -B <source59f>/tools/lan_pilot.py --state <f5> prepare-leaf-rotation-batch --csr <same-key-worker1-CSR> --csr <same-key-worker2-CSR> --output <new-f5-batch> --ca-key <fresh-encrypted-intermediate-key> --ca-key-password-file <fresh-intermediate-password-file> --ca-chain <fresh-chain> --revocations <fresh-registry> --safety-window-hours 48 --overlap-seconds 14400 --leaf-valid-seconds 518400
```

With verified per-worker renewal runtimes and matching generated hashes, each Node installs its assigned bundle, CP stages each matching Node receipt, CP commits the shared batch only after all active Nodes, then each Node finalizes with the new commit receipt. The exact existing `worker_leaf_rotation.py install/finalize`, `stage-leaf-rotation-batch` and `commit-leaf-rotation-batch` vectors are in the private packet. As the campaign grows, every active F5 Node must participate; existing r5 followups/configuration/runtime are not reused. This is a planned legitimate renewal path, not an executed rotation or scheduled task.

The frozen core packet's public hash remains `5121cb834016ebf86fd7433bcca3c3c89446374965a05f71a069158afe44d35f`. A separate `extension-and-runtime-env-contract.json` binds supplemental context without replacing those reviewed private bytes. Set `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` in the owner process before every command, in addition to `-B`: the environment must propagate to child Alembic processes, because `-B` alone is not inherited.

Later extension is an actual supported source59f contract, not an assumption of immutability. `add_requested_nodes` retains all old entries/IDs, skips known addresses and appends a fresh ID for a newly verified address; the existing Node port must remain18515. Repeat `init` on **only F5 state**, same server/DSNs/download18115 and the same external issuer options; add only the newly ready endpoint (CP later requires `--allow-server-node-colocation`). `ensure_pilot_pki` compares external chain bytes and preserves existing CA/control/signing keys; a different chain fails. Existing tenant/node INSERTs use ON CONFLICT DO NOTHING, but F5's killSwitch=true control version increments and its private-state hash changes. Thus first-init tenant/epoch/CA disjointness is not reused as an extension rule: extension preserves current F5 tenant/epoch/CA/old keys, adds new IDs and requires a new expected-state receipt. Peer policies and rotations must be settled and current leaves valid with adequate margin first. Repackage using retained prebuilt artifacts without CP Docker; public bundles may be rewritten, but do not reinstall old Nodes. None of this targets r5 or makes all-five acceptance true. Exact templates, source semantics and remaining3/4/CP gates are in the supplement. Existing multinode contract tests returned **39 passed /3 Windows platform skips /exit0**; those skips are not Linux execution proof.

## Preservation and stop/rollback contract

At15:10 this task re-read r5 overview200: exact actual2 online/fresh, source live-postgresql-mtls, runs0/offers0, killtrue/workloadfalse, and its private-state bytes were unchanged across measurement. Prior6ba9 Evidence preserves2,241 matching protected file hashes and original source03/executorB5 identities. Current task never invokes Cycle/Transition/Recovery/Run now, changes keys/epochs/profiles/containers or edits automations.

At15:23:34KST, this task independently rehashed those **2,241 existing protected files:0 changed**; source03 and executorB5 remained at their exact preserved HEADs with tracked-clean status/exit0. `preservation-check.json` records this current comparison and the earlier baseline digest. This is a byte comparison, not a fabricated fresh automation-scheduler run or admin probe.

Keep old source03, executorB5, original993/new720 packets, guardacf8/configca684/released46 and all keys/receipts byte-identical. Normal r5 renewal starts Nov8 14:15:35KST, with existing followups Nov8 14:20 /Nov9 12:15 /Nov10 08:00. There is no clock/window/latch bypass, forced rotation or automatic date deferral in this packet.

Any nonzero command, wrong scope/hash, r5 degradation, new port conflict or budget/headroom breach stops **new F5 progress**. After exact owner/PID/command/container-label checks, an operator may stop only newly created F5 processes/containers; preserve new CA/state/DB/volume/keys/receipts for diagnosis. Do not restart/stop r5, delete any DB/volume, prune caches, modify global builder/daemon settings or weaken profiles. This rollback is preservation and isolation, not restoring old bytes over new state.

## Narrow API-floor wording correction and verification

`deploy/lan/README.md` and the blocked error text in `deploy/lan/prepare-worker.sh` now identify historical feature floors **Engine26 /Desktop4.29**, leaving the numeric API>=1.45 assertion unchanged. The existing test's expected message in `tests/core/test_lan_worker_config.py` was updated; no new tests or gate changes were added. Historical Engine25→API1.44 explanation and unrelated synthetic fixture/runtime strings remain valid and unchanged.

The [official API matrix](https://docs.docker.com/reference/api/engine/#api-version-matrix) maps26.0 to1.45 and25.0 to1.44; [Desktop4.29 release notes](https://docs.docker.com/desktop/release-notes/#4290) list Engine26.0.0. These are historical feature floors, **not recommendations to install old releases**. Any actual future CP upgrade must select a currently supported compatible version and verify the real API range against the Node client's1.45 cap; no CP upgrade is performed or required for this first phase. Exact59f artifacts remain source-pinned; this branch's message-only correction is separately reviewed for integration, not silently copied into the preserved59f/03 trees.

Existing worker-config suite ran at15:17:00–15:17:06KST with supported existing Python3.14.7: **32 passed**, exit0. Wording search for old false floors returned1/no matches in live deploy text and the updated assertion, which is the expected search outcome, not a test failure. Local docs/ontology/ratchet/sync-check and exact hosted Docs CI are recorded in this task's Evidence receipts; independent review and operational acceptance are separate. No test or plan output is promoted to actual installation or physical FIVE success.

What was done: a private exact-input/command packet, collision/resource/CP analysis, bounded per-Node proposals and a narrow floor-text correction. What was checked: read-only measurements, source/archive/policy hashes and existing/local/hosted checks in Evidence. Next owner **Codex coordinator /Claude**: resolve review findings and actual live admission gates, hash generated material before any future installation, and keep3/4/CP incomplete until independently ready; Obsidian reconciliation and final common-board updates remain with the coordinator.
