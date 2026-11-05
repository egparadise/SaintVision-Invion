---
doc_id: "HIST-FLEET5-B-ROLE-STORAGE-CONTRACT-001"
title: "FLEET5 Broad B role-aware compute storage and coherent renewal proposal"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Independent Claude DOCS review via root pending; architecture decision pending"
updated: "2026-11-06T02:20:05+09:00"
source_of_truth: "Git"
---

# Decision proposal after frozen P0

This is a DOCS-only proposal, not an accepted ABI, ADR, implementation or active
storage result. Owner Codex; task `FLEET5-COMPUTE-STORAGE-CONTRACT-20261105`,
Orca `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`; own branch
`agent/codex/fleet5-compute-storage-contract-20261105`. Base is docs-only
`3af3334ec7577f96b1d377164675e544504407ad`, runtime/source ABI
`4f97ba71b1482ae70d72dda1833a28fddcd05994`. Exact first-read doc versions,
Index401/Codex362 and delivery/core-reliability skills remain in the original
source inventory and [[2026-11-05_FLEET5_compute_storage_contract_Codex]].

P0 source 4f has actual independent CODE ACCEPT `2736aec1303ca6b6ed80bdc4aa6b9c23c3693985`,
full exact Core/Backend/Docs SUCCESS and Root's bounded candidate selection.
Its separate report 3af and Docs `42066623585` also pass. That delivery is complete;
combined acceptance, NodeOps, bootstrap and physical five-PC acceptance remain
HOLD. The separate optional Low test delta `f0af307705b4923ebc3e231db5238af4c70aa389`
is not part of 4f or this DOCS-only proposal. Root messages `msg_c1ad8cf50b7c`,
`msg_2170d0e42ec4` and `msg_1f7d3011c86c` authorize this proposal; production B
must wait for a concrete Root design decision and actual independent review.
Root subsequently relays actual Low-only ACCEPT
`70f7502bd7a25d1e133280fecf0ee2391ae82f33`; that separate patch and its exact Docs
pass do not reassign 4f CI or authorize B.

All real Node IDs, physical addresses, source paths, target images/executables,
leases, deployment/archive hashes and acceptance bindings remain **NULL/HOLD**.
Old PC2/PC4 pilot identities remain distinct and untouched. The new five-PC fleet
is not initialized. No source originals, ADR, board, registry or Obsidian apply
changes are made.

## Existing supported contracts and actual gaps

| Source at frozen 4f | Existing supported behavior | Missing B behavior |
|---|---|---|
| `deploy/lan/worker_workspace.py:72` | R4 refuses storage flags and mounts beyond owned state plus the exact default socket | Cannot preserve an approved contribution through workspace upgrade; keep this default refusal |
| `deploy/lan/worker_storage.py:163`, `:178` | One readonly, nonrecursive, rprivate contribution; exactly two user mounts, no socket | Cannot validate a three-mount workspace/storage Node |
| `deploy/lan/worker_replacement.py:103` | Clean stopped observation profile; exact volume owner and consumers | Existing replacement is not a workspace or settled-P0 migration contract |
| `services/node-agent/cmd/inv-node/main.go:112` | Constructs storage sampler alongside execution runner, then HandlerWithStorage | Go can serve both in principle; deployment authority and lifecycle proof are missing |
| `services/node-agent/runtime/peer_floor_linux.go:142`, `:192` | M2 v2 explicitly rejects storage-policy arguments and contribution mounts | A storage-enabled process cannot truthfully produce the accepted plain observation |
| `deploy/lan/peer_policy_phase.py:144`, `:149` | Exact floor :2 shape with plainServingProcess true; normal/batch :3 | No role-aware floor or storage-preserving renewal; no schema fallback is safe |
| `services/node-agent/storage/sample.go:49`, `:97`; `transport/storage.go:44` | Active DER leaf, key, policy, scope and expiry checked before startup pin and sampling | Renewing the Node leaf while retaining old storage-policy certificate hash fails closed |
| `runtime/storage_policy.go:38` | Monotonic root/channel floors; same channel version with a changed channel hash rejected | A certificate update cannot be hidden by rewriting policy at the old channel version or resetting counters |
| `storage_sampling.py:29`, `:76`; `storage_commit.py:79`, `:86` | Storage uses the SAME ChannelProof and inv.node_channels row as execution | Do not invent a second CP storage channel, independent counter or dual-row CAS |
| `storage_sampling.py:101` | Sampling v1 caps channel/root versions at 2^31-1 | B must use this effective bound, or separately approve a new sampling wire; plain P0's larger bound is not evidence of storage support |
| `runtime/docker.go:217`, `:256` | Private tmpfs workspace/tmp, UID 65532, network none, inspected rejection of binds/devices/ports | A Node contribution must never become a workload host bind or writeback grant |
| `tools/lan_workspace.py:20`, `:65` | Workspace manifest 1 and nine pinned installer hashes after P0 | No combined role/mount/root/renewal intent or supported B migration |

The updated disposable fixture on unchanged guarded runtime exits **1 as expected**
for `python -B tests/proofs/fleet5_compute_storage_contract_probe.py --require-coexistence`.
The default command exits 0 and proves both legitimate two-mount storage and
plain workspace targets, R4 refusal, third-socket storage refusal, alias refusals
and unchanged policy/inspection bytes. It never calls Docker, PKI or a live Node.
This red result proves the current source gap; it is not a task failure or Linux
enforcement/active-storage proof. Exact command/exits/source hashes are in the
`b-after-p0-proposal` evidence siblings.

## Recommended bounded decision B-FRESH1

Authorize implementation only for **new, homogeneous five-Node fleet bundles**
with one explicit approved readonly contribution per Node, existing execution
profile `lan-workspace-v1`, a separately versioned role observation and coherent
renewal. Four independent Linux workers remain eligible for S05/S07; the
CP-colocated fifth Node retains ADR100 exclusions. Do not dedicate an independent
worker to storage or count folder preparation as storage acceptance.

This does not migrate old pilots, existing storage-only images, in-flight leaf
operations, or settled P0 containers. Unknown/legacy capability remains BLOCK.
The new fleet is not initialized, so fresh installation avoids inventing an
unsafe predecessor conversion. Post-settled migration is separately specified
below as B-MIG1 and is not implicitly authorized by B-FRESH1.

The execution profile stays existing workspace v1; the new authority is an
explicit combined **deployment role**, not a broader workload profile. No new
storage sampling HTTP protocol or separate CP channel is needed for B-FRESH1.
The necessary new local observation/renewal ABI is real scope, not a guard tweak.

### Proposed interfaces, not implemented

1. A new closed bundle/installer manifest 4 declares contract
   `workspace-storage-ro-v1`, exact identity/epoch/endpoints and co-location
   metadata, current DER and file hashes separately, existing profile, one
   contribution/root version, exact raw policy hash, approved source identity,
   three-mount class, image and every helper/runtime hash. A protected local
   request carries the canonical Linux-daemon source path; public evidence does
   not carry private physical paths. Unknown fields/contracts/aliases refuse.
2. Dedicated `worker_compute_storage.py` and explicit wrapper entry point build
   only the approved mount set. Existing workspace/storage/replacement defaults
   and R4 remain unchanged. No arbitrary mount copying, force option, environment
   bypass, abbreviated/single-dash/equal-form flag or alternate socket is added.
3. Proposed signed `saintvision-node-peer-policy-floor:3`, domain
   `saintvision/node-peer-policy-floor/v3` plus NUL, is distinct from plain v2.
   It retains v2's identity, nonce/time, certificate DER, peer floor/raw journal
   hashes, actual serving PID/UID, raw cmdline and executable BYTES hashes. Replace
   plainServingProcess with exact servingRole `workspace-storage-ro-v1`; add
   the actual six-field StoragePolicyPin, raw storage-floor SHA-256 and a closed
   kernel mount/root observation. Read existing peer/storage floor files without
   creating a journal or taking the serving process's lock; enforce its UID,
   private mode, regular/no-link bounded reads and coherent before/after identity.
   The new observer uses explicit exclusive full-spelling CLI
   arguments; plain v2 continues to refuse storage without fallback.
4. Kernel observations measure the serving process's critical state,
   contribution and socket targets, actual root descriptor identity, mount IDs,
   readonly/private flags and absence of contribution submounts before/after.
   Device/inode values use canonical fixed-width hexadecimal strings, avoiding
   JSON integer rounding. They do NOT claim a host source path, volume name or
   HostConfig NonRecursive value that the container cannot itself observe.
   The host validator independently checks exact Docker configuration/ownership
   and matches observed root identity to the approved daemon-side source.
5. New normal/batch leaf protocol :4 binds the role :3 floor, storage policy and
   storage floor along with existing peer/channel fields. Plain floor :2 and
   leaf :3 remain closed and unchanged. Add a separate pinned role-aware runtime
   manifest/launcher version with an exact module inventory; do not broaden the
   existing five-module plain runtime, fixed verifier path or SF1 token by
   inference. Generated schemas/fixtures/canonical vectors are required.

The new floor uses the already reviewed Go Marshal map UTF-8/HTML/U+2028/U+2029
body convention without a body newline. Existing storage-sample v1 signing and
legacy outer receipt bytes are not globally recanonicalized. StoragePolicyPin
hash derivation must retain the existing Go storage serializer; its rootSha256
is the configured root string hash, NOT filesystem identity. Publish actual
Go/Python vectors before relying on channel/policy hash reconstruction.

CP admission is also explicit: a valid shared channel or mounted folder does
not establish the deployment role. Workload dispatch and storage issue/commit
remain quarantined until the exact current epoch/C, contribution/R, policy,
image/executable and root/mount observations are verified and recorded for this
role. Missing/stale attestation or an operation fence denies admission. Include
the relevant resource/readiness, challenge/collector/committer and execution
callers in this contract; do not add a second channel or treat a local ready
file as authority. Renewal re-establishes readiness at its committed target C.

### Fixed mount, state and workload boundary

Exactly three user mounts are permitted: the existing labelled owned RW state
volume at `/state`, the existing default daemon socket bind at
`/var/run/docker.sock`, and the single approved contribution at `/contribution`
with readonly, `bind-recursive=disabled` and rprivate. Root filesystem stays
readonly, no privileged/devices/extra binds/alternate consumers. A Node-level
socket does not enter workloads. Workloads keep their current inspected private
tmpfs/isolation and cannot bind the contribution, host path, state or socket.
Readonly contribution does not grant workload access or storage writeback.

Validate every contribution-source and private policy/state path component
without symlinks; preserve the existing exact default-socket contract without
adding alternate paths or alias resolution. Record/recheck policy
bytes, source device/inode, owned volume, image/config/argv/mounts and all volume
consumers before/after create/copy/start and observation. Require a supported
Linux daemon-side source namespace; refuse uncertain Windows/VM path mappings.
No link, traversal, hardlink/device substitution, stale/tampered/mismatched
policy, changed root, mount substitution, duplicate flag or unknown state is
adopted. Real Linux Docker tests must demonstrate readonly and propagation
behavior; inspecting an option bit alone is insufficient.

Fresh installation uses the already authorized Node identity/key/leaf/channel
and epoch. It does not enroll, renew, merge identities or create policy authority.
The manifest's storage policy bytes and root identity are preserved exactly.
Only an owned fresh target with no predecessor/unknown consumer and a verified
initial state layout is eligible. Record exact operation/candidate CID; retain
container/state evidence on failed or uncertain responses. Do not adopt an
existing target merely because its name resembles the manifest.

Existing per-workload cgroup/isolation limits stay as implemented. Proposed
Node CPU/I/O reserve or scheduling budgets are resource-policy hints until
separately enforced and verified; they are not host/disk hard quotas. Existing
sampling file/count/TTL read bounds are protocol limits, not storage capacity.

## Coherent renewal :4 on the SAME channel

Let P be actual peer floor, C the shared Node channel, and R contribution root
version. Reuse storage-sample v1; for B require C and R in 1..2147483647 and
reject C+1 overflow before publication. P retains its independent exact-safe
bound and rejects P+2 overflow. Do not reset/version-jump/widen v1 on this path.

| Phase | Actual peer policy | Active Node DER | Storage pin/policy | CP shared channel |
|---|---|---|---|---|
| Current | P/current hash | A | R,C,policy A binding DER A | C,DER A |
| Installed overlap | P+1/overlap hash | B | R,C+1,policy B binding DER B | C until exact commit |
| CP commit | exact signed role receipt verified | B | unchanged policy B | one existing CAS C to C+1,DER B |
| Final | P+2/final hash | B | SAME R,C+1,exact policy B bytes | C+1,DER B |

Policy B changes only the explicitly authorized shared channel/certificate
tuple; contribution ID, root R, actual source/root identity and readonly mount
class stay unchanged. This deliberate renewal update is distinct from migration,
which preserves existing policy bytes and C/DER. Same-C/different-channel-hash
must continue to fail at the actual Go storage pin. Never invent a second
storage channel/CAS or use a root-version bump to evade the channel floor.

All members pass current channel/role/root/floor/expiry preflight before any
output or CAS. Freeze exact current/next storage bytes and signed observations
in the proposal/journal. Serialize/fence contribution-root authority changes
against the operation, and recheck contribution status/R and the shared channel
inside the commit transaction before its existing C CAS. A concurrent version
change blocks or remains forward-only; it never silently regenerates policy or
becomes a successful renewal. Quiesce storage issue/commit during the installed
overlap before CP commit; mixed old-channel challenges cannot be accepted as
current storage. Existing StorageCommitter rechecks the same inv.node_channels
row and consumes nonce with Run Evidence/StorageCheck transactionally. After
commit, old challenges/DER fail. Final restart advances only P again; the storage
pin is exact replay at C+1. Prove two COMPLETE cycles with native Go/Docker,
actual mTLS narrowing and transactional storage acceptance.

Leaf :4 keeps same CID/image/profile/mounts/volume and key/identity/epoch while
publishing the expressly authorized new leaf and policies. Durable publication
intent is forward-only. Full exact phase credentials, actual peer/storage floors,
root identity and fresh expected signed :3 observations are mandatory before
acknowledgement. A stopped fully copied exact phase may have a separately
reviewed bounded same-CID start rule. Unknown/partially copied states, before-copy
and restarted recovery are BLOCK; no copying/old restore is smuggled into RS1.
Original :3 archives stay byte-identical; no in-flight conversion or legacy
offline/expired recovery expansion is included.

## Separately gated B-MIG1 post-settled proposal

P0 SF1 authorizes only idempotent/same-byte actions. Adding a bind, role or new
binary requires a NEW migration contract and common mutation fence; it cannot
inherit a settled token. The future common-lease/bootstrap plan is DOCS-only,
not accepted implementation or a present bypass. All same-Node helpers and
direct-function/wrapper callers must honor that fence before B-MIG1 can run.

A potential bounded B-MIG1 accepts only completed plain 4f :3 history with
verified current actual v2 floor and immutable archives, then an explicit
approved target image/role, unchanged identity/key/DER/C/epoch/endpoints, state
volume and approved policy/root. Any image bridge, actual storage-floor proof,
old/new CID ownership, consumer fence and operation lease must be specified and
independently reviewed first. No unsigned inspection substitutes for an absent
capability. Existing storage-only/old-pilot images cannot produce plain v2 and
remain HOLD under their separately required legacy capability migration.

Retain the exact stopped predecessor and original state/journal; permit only a
recorded candidate and known fenced consumers. Lost/unknown responses never
authorize new consumers, old restart, journal edit or policy rollback. Once a
new durable storage floor exists, automatic restoration of old policy/role is
not a rollback. Before publication/preflight failure preserves current running
container and journal; post-intent failure preserves exact containers/journals
and remains forward-only or BLOCK. No cleanup/adoption rule is inferred.

Mixed plain/coexist cohorts also need a CP-wide control-leaf renewal/fence plan;
they cannot independently publish conflicting control leaves through :3/:4.
B-FRESH1 intentionally requires a homogeneous new fleet. B-MIG1 therefore stays
a separate design gate, not a partly implemented success path for first B.

## Coordinated surfaces and acceptance gates

Source-surface inventory records exact hashes/anchors for workspace, storage,
bridge, replacement, config, execution, peer-floor/leaf helpers, pinned launcher,
Go runtime/transport/storage, CP channel/sampling/commit, package/acceptance and
all shipped Windows/Linux prepare/finish/start/repair/workspace/storage/renewal
wrappers. Their generated bundles/manifests/hash bindings and direct callers
must agree. Unknown role routes fail closed; no general mount-preservation helper.

Required meaningful red/green evidence before inclusion:

- Preserve current R4/plain :2/:3 and legacy-history tests. New fixtures reject
  aliases, extra/RW mounts, wrong socket/policy/channel/root, links, TOCTOU,
  stale/expired/partial states and unknown consumers without container/journal
  mutation. Kill missing role/mount/floor/renewal/fence guards explicitly.
- Actual Linux Docker proves readonly write rejection, nonrecursive child-mount
  exclusion, rprivate propagation isolation, root/volume ownership and workload
  inability to access host/state/contribution/socket. No mock-only mount claim.
- Actual Go observes :3 peer AND storage floors with PID/raw argv/executable
  descriptor identity and root stability; wrong phase/hash/DER/role/counter,
  absent journal, mount substitution and malformed schema fail. Cross-language
  canonical bytes/signatures cover Unicode and exact integer limits.
- Real Go plus PostgreSQL completes TWO coherent :4 renewals, shared C CAS and
  storage nonce/version/DER rejection. Same-C changed policy stays rejected;
  old storage policy never restarts after its monotonic pin advanced.
- Inject crashes and lost responses at every create/copy/start/ack/CP-CAS phase;
  race all helper/renewal/migration entry points. No two serving consumers, stale
  lock theft, inode substitution, old restore or false readiness. Document BLOCK
  states rather than marking whole-operation recovery complete.
- Rebuild closed package/runtime/schema bindings, run appropriate full CI and
  actual independent review. Five-PC operational proof remains separate: four
  independent workspace workers plus excluded CP Node, and actual authenticated
  current storage acceptance on all required Nodes. Folder preparation, local
  installation receipt and unsigned status are insufficient.

## Concrete Root decision request

Choose **B-FRESH1 (recommended)**: authorize implementation of the new explicit
combined fresh-fleet manifest/factory, role-aware floor :3, separate closed
runtime, explicit CP role-admission gate and coherent :4 renewal, reusing shared C and sampling v1 with its
effective integer/DER constraints; keep legacy and post-settled B-MIG1 blocked.
Alternatively choose **B-FRESH1 plus B-MIG1 design-first**: first close and review
the common-fence/predecessor/cohort-renewal contract before any migration code.
Or keep **B-HOLD**, continuing the useful plain baseline while explicitly leaving
the original five-PC contributed-storage objective OPEN. No option silently
weakens current guards or treats unimplemented/active-storage claims as done.

Codex next publishes this immutable DOCS-only proposal and exact Docs result,
requests independent Claude architecture review via Root and uses a structured
orchestration ask for Root's concrete scope/ABI decision. No B production code
changes until that reply; no repeated end-user approval is requested.
