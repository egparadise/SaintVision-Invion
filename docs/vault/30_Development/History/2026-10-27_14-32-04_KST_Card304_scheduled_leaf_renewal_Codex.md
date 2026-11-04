---
doc_id: "HIST-CARD304-SCHEDULED-LEAF-RENEWAL-20261027"
title: "Card 304 session-independent scheduled leaf renewal"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-27T14:32:04+09:00"
source_of_truth: "Git"
---

# Card 304 session-independent scheduled leaf renewal

## Scope and decision

The r3 leaf expiry proved that an agent-session timer is not an operational scheduler. This card
adds an OS-owned Windows Task Scheduler entry point without registering it. The user's standing
approval remains limited to a reviewed, landed batch rotation beginning two days before the
earliest public leaf expiry. Task installation is a separate post-review/train action.

The private task configuration is digest-pinned at registration, binds the exact checkout commit,
and has an exact schema. It names
paths, command arguments, and SHA-256 pins; it must not contain credential values, DSNs, private
keys, or password values. Every executable and referenced input is rehashed immediately before its
gate. The only admitted order is:

1. read the Control Plane and exact two Node **public** certificates and calculate the two-day
   window;
2. require the tool-native current status to show exactly two online/fresh Nodes;
3. run both standalone-runtime preflights;
4. prepare one shared-Control-Plane batch, install both Nodes, and stage both channel CAS receipts;
5. commit the single global transition, run the reviewed transition command, and observe both
   Nodes online/fresh with post-transition heartbeats;
6. finalize both Nodes and repeat the exact online/fresh observation.

The runner does not read `private-state.json`, reveal subprocess output, synthesize a retry, edit a
journal, or accept expired material. Outside the window it records a no-op. At or after expiry it
records `expired-alert`, invokes no renewal command, and returns non-success. Any gate failure
records only its gate name and stops before all later commands; partial rotation state remains for
the reviewed recovery tools.

## Scheduler and operator visibility

The registrar derives one deterministic task name from the normalized state path, requires the
current Windows SID, refuses a foreign task, uses S4U/limited/non-interactive execution, installs
00:15 and 12:15 daily triggers, and sets Task Scheduler `IgnoreNew`. The executor independently
uses an atomic single-instance lock. Each outcome appends one secret-free JSON line, atomically
replaces a configured Desktop status JSON file, and attempts a generic Windows notification only
when the registered private plan explicitly enables it. Live registration requires that bit;
direct/test plans keep it disabled, and an outside-window no-op never displays a pop-up. The
durable status file is authoritative when notification delivery is unavailable.

No Task Scheduler entry or live LAN state was changed by this card.

## Verification

- `pytest -q tests/test_scheduled_leaf_renewal.py`: 20 passed. The suite covers outside-window
  no-op, expired alert/no commands, the exact success sequence, all fourteen independently failing
  gates with no later execution, lock exclusion, executable/input/config digest drift, strict
  shape/cardinality, and a twice-daily limited S4U registration plan.
- An initial local behavior run exposed that generic Windows notification was being invoked by
  test/direct plans. Notification is now an explicit Boolean that live registration requires,
  while test/direct plans disable it; the repeated 20-case run produced no pop-up.
- `pytest -q tests/core/test_launcher_failure_boundaries.py
  -k every_deploy_powershell_script_parses`: 1 passed; every deploy PowerShell file, including the
  two new files, parses.
- Local Docker was not used. No private state, DSN, credential, key, fingerprint, or live Task
  Scheduler object was read or changed.

## Post-review registration shape

After this PR is independently reviewed, included in a green train, landed, and the coordinator
issues the separate live-registration instruction, create the private exact plan, inspect
`-PlanOnly`, then register it:

```powershell
deploy/lan/Register-LeafRenewalTask.ps1 `
  -ConfigPath <operator-private-plan.json> `
  -PythonPath <reviewed-repository-python.exe> `
  -PlanOnly

deploy/lan/Register-LeafRenewalTask.ps1 `
  -ConfigPath <operator-private-plan.json> `
  -PythonPath <reviewed-repository-python.exe>
```

The live plan must point to the already reviewed Card 291/298/300/301 commands and r4 paths. New
code, a different command count/order, a changed binary/input digest, a third Node, an expired
leaf, or a foreign existing task all require a stop and a new review; they are not scheduler
recovery inputs.

Reviewer: Claude. Review the fixed sequence, public-only window probe, strict plan and digest pins,
stop-before-next-gate behavior, observation freshness, lock/Task ownership, secret-free receipts,
and the fact that registration and live renewal did not occur in this card.
