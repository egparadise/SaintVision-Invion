---
doc_id: "HIST-FLEET5-B-A7-MODE-ORIGIN-R1-001"
title: "FLEET5 one A7 mode-origin prerequisite and minimal operation contract proposal"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Actual independent mode-origin review through Root pending"
updated: "2026-11-07T08:26:22+09:00"
source_of_truth: "Git"
---

# One prerequisite, separate from acceptance

Codex owns FLEET5-B-A7-MODE-ORIGIN-R1-20261107, task_a8fd2969f0b3 /
ctx_6f0f8253b8a7, under Root msg_ec880f3ed724. Preparation KST
2026-11-07T08:11:38.598933+09:00; branch
agent/codex/fleet5-b-a7-mode-origin-r1-20261107 starts at exact
969030dbc7716b9cadf75bd314713005306ed34c. Product source remains
72028cbac903c4415d9979f980a6e0f9948e914f. Only this new History and
Evidence/fleet5-b-a7-mode-origin-r1-20261107-codex are added. R1/R2 refs,
bodies/producers/sidecars and original19 obligations remain immutable.

Actual independent review145238898e8c86e1beb091b93efd712c70a6f5ba is direct9690,
11 own added documents, PARTIAL_STATIC_EVIDENCE_ACCEPT_L1_CLOSED_KEEP_HOLD:
A7R-L1 and I3_ORACLE CLOSED, no HIGH/MEDIUM/LOW. Root verified its Docs
42308611982/job128204216264, manual docs.yml/attempt1/title
claude-b-a7r2-9690-review-14523889-ctx_36ec44cc8ca0, all19SUCCESS and actual
reviewer succeeded/settled/exited/released. Full review, driver,12 rows and
commands were read. All11 original Git blobs/object IDs/hashes are preserved.
Reviewer attempt1 exit1 was its missing-frozen-path precheck bug; the pre-fix
driver was not retained and is not claimed replayable. Corrected attempt2
exit0 measured146444288B/196.4s in one process, not aggregate/quota. Those
historical runs are not newly executed controls. R2 historical failure receipts
remain in the immutable predecessor, with hashes in inputs.json.

INFO I1/I2/I4/I5/I6 are retained. In particular R2's actual census guard key has
span[];[76,0,76,22] is diagnostic replay, never authorization. This card does
not polish that replay or its unsupported globals branch. Prior accepted
normal/observation body proof and R2 coverage are referenced, not rerun.

Read-only Root head db32573c4245458ac8f1241de139f29bceec8924 had
INDEX-PROGRESS-001 v1.0.488 and WORKBOARD-CODEX-001 v1.0.449. inputs.json
records canonical first-read IDs/versions/hashes, AGENTS and registry:
INDEX-VIRTUAL-COMPUTER-001/ROADMAP-VIRTUAL-COMPUTER-001 v1.0.0,
GOV-CONTINUOUS-001 v1.1.0, GUIDE-001 v1.1.0, ADR-INDEX-001 v1.37.0,
GOV-AGENT-001 v1.1.3, GOV-GIT-001 v1.1.4, GOV-CONTINUITY-001 v1.0.0,
agent-delivery1.1.0 and core-reliability1.0.0. No helper was dispatched.

# Scoped graph and what it actually proves

The target is solely A7_PURPOSE_PROVENANCE at node_transport.py:280
observation_only=observation_only or cancel_only. A new auxiliary candidate is
separate from the immutable baseline; acceptedBaselineDischarges=0. No18-count
accepted artifact is published. Mode provenance is not mode permission.

The declared lexical query covers25 production Python paths, parsed/audited
one file at a time using existing finite Facts/import/caller/signature,
reflection and full-use-site helpers. Every path/current-SHA pair is recorded,
with every guard result, before classification. All25 frozen inputs are clean.
Within that explicit scope are nine constructor calls and one deliver
attribute reference, the call at dispatch.py:336. This is not arbitrary computed
import/alias/heap/language completeness; unknown dynamic receivers stay premises.
No SQL/network/effect admission follows from reading these source files.

NodeDelivery constructors occur at worker.py:122 and remote_workspace_entry.py
:107/:145. DeliveryWorker constructors occur at worker.py:142 and the tool's
:145/:161/:172. The actual frozen worker site is142, not the starting observation
133. Formal argument bindings, original import event multisets, current source
hashes, scopes/spans and expressions are recorded. Worker main's delivery local
has one NodeDelivery assignment. The tool's a.delivery is assigned in setup,
then forwarded through its returned namespace; faithful namespace ownership
and no replacement across other calls remain explicit premises. No DB owner
or client/network type is closed by those names or constructor recipes.

dispatch.py:315 stores DeliveryQueue(database) and the delivery formal into
self.queue/self.delivery. once(:323-349) takes attempt from self.queue.acquire; its
None branch returns before delivery, and there is one local attempt binding.
acquire's only non-None return is DeliveryAttempt(:243-251). The sixth argument
operation corresponds to the sixth declared frozen-dataclass field, conditional
on genuine dataclasses generation and an intact genuine result/plain field.
The str annotation itself supplies no runtime type check.

The three local operation stores are :170-174 (cancel/observe literal IfExp),
:184 (cancel literal) and :203 (execute literal). No DB column is forwarded as
the operation value. Thus a normal return has a literal-string union under
the genuine-method/no-unmodelled-frame-mutation premise, regardless of which
branch its potentially rich conditions choose. Branch permission, DB adapter
effects and _can_start effects are not proved here.

| Preserved operation, if genuine builtin str | observation_only | cancel_only | snapshot argument / body mode |
| --- | --- | --- | --- |
| execute | False | False | right False / NORMAL |
| observe | True | False | left True / OBSERVATION |
| cancel | False | True | right True / OBSERVATION |

NodeDelivery.deliver declares keyword-only defaults False/False and does not
reassign the two parameters. Its or truth-tests the left operand and returns
that operand if truthy, otherwise the right operand unchanged. It does not
normalize to bool. A literal truthy string remains a string; dual-True is part
of the legacy callee truth table but is not minted by the three-string caller.
Only with a preserved builtin-string attempt.operation does its equality to
each label yield builtin bool. A foreign value may return an arbitrary rich
comparison result or run __eq__/__bool__; comparison syntax, an annotation,
a MAY receiver or a DB column type cannot establish that premise.

The result is CONDITIONAL_SOURCE_CANDIDATE_RUNTIME_AND_OWNER_PREMISES_PENDING,
not unconditional closure. The exact unresolved mode premise is faithful
genuine attempt/field/adapter provenance and bound receiver identity through
the read/forward path, not the names of the operation labels. The other10 DB
owners and8 roots are not attempted.

# Smallest prospective code contract, product delta zero

If Root chooses to remove the field-value-type premise by a code boundary,
insert this inside DeliveryWorker.once's existing try immediately before its
deliver call, then use the captured operation in its existing two comparisons:

```python
operation = attempt.operation
if type(operation) is not str or operation not in ("execute", "observe", "cancel"):
    raise ValueError("Unsupported delivery operation origin")
# Existing deliver call keeps node/envelope, with:
# observation_only=(operation == "observe"), cancel_only=(operation == "cancel")
```

This is a prospective contract narrowing for foreign/subclass/unknown operation
values, not implemented here. Capture once prevents two stateful field reads;
exact builtin str prevents custom comparison/truthiness before membership and
the two equalities. Builtin type/str binding and genuine receiver premises still
need authentication. NodeDelivery's default/truthiness/or API and accepted
body matrix remain unchanged. This guard alone grants no permission or DB role.

The existing worker catch maps ValueError to SYS-0001 with not_sent=False;
future implementation must preserve uncertain/lease handling. No deliver call
should occur for a rejected value, but earlier acquire/reconciliation effects
are not called absent or pure. Necessary future causal tests are: each of the
three literals maps to the original flags; foreign/subclass/unknown-domain
values are rejected before equality or delivery; a changing property is read
once and cannot switch modes; removing the boundary recreates the foreign-value
case; existing finish/uncertainty/error behavior and builtin binding rejection
remain correct. None is claimed executed product validation in this cut.

# Bounded validation and next owner

Exactly six AST/DATA controls cover actual source, benign leading-comment span
shift, causal forwarded expression change, row-sourced dynamic operation,
foreign/rebound attempt constructor and literal truthiness/or operand behavior
with an unknown foreign-type premise. Syntax/current spans/hashes are checked.
The mode rule is evaluated separately: a generic older use-site failure is not
evidence of a later causal rule, and the rebound case is explicitly an earlier
binding failure. No product or mutant module is imported/executed. One empty
patch invocation was rejected before any file write; it is not a semantic run.

Final source/control receipts are final-source03.json/final-controls03.json;
six cases are six distinct controls, not extra coverage from development reruns.
docs-final01-1..8.json record required docs gates with immediate exits. Each
final command brackets all current own producers/raw harnesses and eight used
immutable helpers, with argv/cwd/Python3.14.7 -B/KST/raw logs and individual
process peaks. No giant analyzer/sealer, accepted R1/R2 body/guard polish,
33/49 corpora, model/recovery/523 assembler/3485 plans or full Core is run.
The compact manifest binds source graph, input receipt, outputs and this History.
Canonical CHECK uses immediate full-state hashes and own conflicts output;
Root may apply concurrently, so actual state changes/conflicts are preserved.
No apply/adopt/resolve/state write/stale export occurs.

Normal own commit/push and ONE exact manual Docs run follow; actual pinned
SHA/run/job/head/ref/title/attempt/path/all19 results go to Root, with no future
ID or post-CI amendment invented. Per-process peaks are observations, not
aggregate/hard quota/OS enforcement. The original19/global artifacts/counts,
12 entries/19 edges(16analysis/3runtime),598/757/1071/21/573outside/218,
model/lifecycle/stage/order, runtimeB0, bindingsNULL/HOLD and A1-A16PENDING stay
unchanged. No13th entry, runtime/source inclusion, observer/DB/clock/network/
crypto/Engine/delivery/physical acceptance or K2 H1/H2 scope is granted.

Root's next action is verify this pinned finite mode candidate and proposal,
sequence one actual independent review after readiness/predecessor custody,
then decide conditional source disposition or a concrete narrow future code
contract. The author sends a structured ASK and waits, not whole-B worker_done.
