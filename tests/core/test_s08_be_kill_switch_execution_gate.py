"""The kill-switch execution gate, bound to the Run write path that has to honour it.

`S08-BE`'s scope is "ROOF, kill switch, BuildKit, single GPU". Only one of those four is
implemented, and this file is about that one. The 48-task re-score keeps the row at **50**,
and this file is recorded as partial evidence for a single axis -- not as a promotion.

What the searches actually show, which an earlier version of this file got wrong:

* **ROOF**: `roof` as a whole word appears once in all product and test code, as the policy
  version string `"roof:test:1"` in a Go test. The re-score's claim that ROOF is
  implemented in `adapters/cli.py`, `services/pilot.py` and `services/replica_observation.py`
  came from `grep -i roof` matching **proof**. There is no ROOF implementation to test.
* **BuildKit**: one occurrence in all product code, the word "BuildKit" inside a docstring
  (`workspace_api.py:36`). No daemon, socket, privileged mode or build boundary exists here.
* **single GPU**: `sandbox.compile_launch` *refuses* every GPU workload and `placement`
  fails closed until measured GPU providers are configured. A refusal is not support, and a
  test of the refusal is not evidence that the row's GPU work is done.
* **kill switch**: real -- `containment.require_execution` is called by `RunStore.create`
  and by every state change into execution. That is what this file observes.

The gate is tested **through `RunStore`**, not through the helper. An earlier version called
`require_execution(conn)` directly, and deleting the `require_execution(conn)` call from
`RunStore.create` left all of its tests passing: the helper still refused when asked, and
nothing asked it. A test of a guard that no product path reaches proves only that the guard
compiles. So the assertions here are about what the write path does -- that a closed gate
leaves no Run written, and that the gate is read *before* the insert, since a gate read
afterwards is not a gate.

The rest of the file stays with the containment argument guards and the operator
Workspace-config refusals, which are real product refusals in their own right and are
described at exactly their strength where they appear.
"""

from __future__ import annotations

import contextlib
from uuid import uuid4

import pytest

from inv.containment import Containment, require_execution
from inv.errors import DomainError
from inv.runs import RunStore


#: `ResourceId` and `NodeId` are Crockford base32 with a prefix, not UUIDs. Using a UUID
#: here made the contract check refuse before the rule under test could be reached.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def identifier(prefix: str, seed: int = 0) -> str:
    body = "".join(ALPHABET[(seed + i) % len(ALPHABET)] for i in range(26))
    return f"{prefix}_{body}"


VALID_INPUT = {
    "expectedVersion": 3,
    "reasonCode": "incident",
    "approvalId": str(uuid4()),
}


class OneRowConnection:
    """A connection that answers the gate query and nothing else.

    `require_execution` issues exactly one statement, so a stub this small is enough and
    keeps the test about the refusal rather than about a database.
    """

    def __init__(self, row):
        self.row = row
        self.statements: list[str] = []

    def execute(self, sql, params=None):
        self.statements.append(sql)
        return self

    def fetchone(self):
        return self.row


class ReachedTheDatabase(Exception):
    """Raised by the stub to prove the argument guards let a call through."""


class RefusingDatabase:
    """Raises as soon as a transaction is opened, which is the first thing after the
    guards. `containment_write` is part of that call's shape, so it is accepted here."""

    recovery_epoch = "epoch-1"

    def transaction(self, tenant_id, containment_write=None):
        raise ReachedTheDatabase((tenant_id, containment_write))


# --- the kill switch is fail-closed -------------------------------------------------


def test_a_tenant_with_no_control_row_is_stopped_not_allowed():
    """Absence is the case that decides whether a gate is a gate.

    A missing `inv.tenant_controls` row means nobody has said this tenant may execute. The
    permissive reading of that would let a tenant run because its controls were never
    written, which is the opposite of a kill switch.
    """
    conn = OneRowConnection(None)
    with pytest.raises(DomainError) as refusal:
        require_execution(conn)
    assert refusal.value.code == "AUTH-0061"
    assert refusal.value.status == 409


def test_an_active_kill_switch_stops_execution():
    conn = OneRowConnection({"kill_switch": True})
    with pytest.raises(DomainError) as refusal:
        require_execution(conn)
    assert refusal.value.code == "AUTH-0061"
    assert refusal.value.status == 409


def test_a_cleared_kill_switch_allows_execution():
    """The control: the gate is not simply always closed."""
    conn = OneRowConnection({"kill_switch": False})
    assert require_execution(conn) is None
    assert len(conn.statements) == 1, "the gate is one query, read before anything else"


def test_the_gate_is_read_from_tenant_controls():
    """Judge the statement, not the outcome: a gate that reads something else is not this
    gate. The table name is the contract between this check and the migration."""
    conn = OneRowConnection({"kill_switch": False})
    require_execution(conn)
    assert "inv.tenant_controls" in conn.statements[0]
    assert "kill_switch" in conn.statements[0]


# --- containment scope and idempotency are settled before any work -----------------


def principal():
    return type("P", (), {"tenant_id": str(uuid4()), "subject_id": str(uuid4())})()


@pytest.mark.parametrize("operation", ["stop", "halt", "KILL", "", "kill ", "resume\n"])
@pytest.mark.parametrize("named_node", [False, True])
def test_an_unknown_containment_operation_is_refused(operation, named_node):
    """And refused *as* an unknown operation.

    Asserting only the code and status was not enough: this guard and the scope guard
    both answer VAL-0003/422, so removing this one left the scope guard refusing
    instead and the test still passed. The detail is what separates them, and the
    mutation that accepts any operation name only dies once it is asserted.
    """
    with pytest.raises(DomainError) as refusal:
        Containment(RefusingDatabase()).change(
            principal(),
            operation,
            dict(VALID_INPUT),
            "key-1",
            node_id=identifier("nod") if named_node else None,
        )
    assert refusal.value.code == "VAL-0003"
    assert refusal.value.status == 422
    assert "unknown containment operation" in refusal.value.detail.lower(), (
        f"refused as {refusal.value.detail!r}, which is a different guard"
    )


@pytest.mark.parametrize("operation", ["kill", "clear"])
def test_a_tenant_wide_operation_may_not_name_a_node(operation):
    """Kill and clear take the tenant gate. Naming a Node would describe a different act."""
    with pytest.raises(DomainError) as refusal:
        Containment(RefusingDatabase()).change(
            principal(), operation, dict(VALID_INPUT), "key-1", node_id=identifier("nod")
        )
    assert refusal.value.code == "VAL-0003"
    assert "scope" in refusal.value.detail.lower()


@pytest.mark.parametrize("operation", ["drain", "resume"])
def test_a_per_node_operation_must_name_a_node(operation):
    with pytest.raises(DomainError) as refusal:
        Containment(RefusingDatabase()).change(
            principal(), operation, dict(VALID_INPUT), "key-1"
        )
    assert refusal.value.code == "VAL-0003"
    assert "scope" in refusal.value.detail.lower()


@pytest.mark.parametrize(
    ("operation", "node_id"),
    [("kill", None), ("clear", None), ("drain", "node"), ("resume", "node")],
)
def test_the_four_correct_shapes_pass_the_guards(operation, node_id):
    """The mirror of the two refusals above: the permitted shapes must not be refused.

    Reaching the database is the proof that the guards passed, so the stub raises there.
    """
    with pytest.raises(ReachedTheDatabase):
        Containment(RefusingDatabase()).change(
            principal(),
            operation,
            dict(VALID_INPUT),
            "key-1",
            node_id=identifier("nod") if node_id else None,
        )


@pytest.mark.parametrize("key", ["", None, 7, b"key", "x" * 201])
def test_an_unusable_idempotency_key_is_refused_before_any_work(key):
    with pytest.raises(DomainError) as refusal:
        Containment(RefusingDatabase()).change(principal(), "kill", dict(VALID_INPUT), key)
    assert refusal.value.code == "VAL-0003"
    assert refusal.value.status == 422


def test_a_key_at_the_length_limit_is_accepted():
    with pytest.raises(ReachedTheDatabase):
        Containment(RefusingDatabase()).change(
            principal(), "kill", dict(VALID_INPUT), "x" * 200
        )


@pytest.mark.parametrize(
    "mutation",
    [
        {"reasonCode": "because-i-said-so"},
        {"expectedVersion": -1},
        {"expectedVersion": "3"},
        {"approvalId": "not-a-uuid"},
        {"operatorNote": "smuggled"},
    ],
)
def test_a_containment_input_outside_its_contract_is_refused(mutation):
    """`additionalProperties: false` and the reason enum are part of the refusal surface."""
    data = dict(VALID_INPUT)
    data.update(mutation)
    with pytest.raises(Exception) as refusal:
        Containment(RefusingDatabase()).change(principal(), "kill", data, "key-1")
    assert not isinstance(refusal.value, ReachedTheDatabase), (
        f"{mutation} reached the database instead of being refused"
    )


@pytest.mark.parametrize("missing", ["expectedVersion", "reasonCode", "approvalId"])
def test_a_containment_input_missing_a_required_field_is_refused(missing):
    data = {k: v for k, v in VALID_INPUT.items() if k != missing}
    with pytest.raises(Exception) as refusal:
        Containment(RefusingDatabase()).change(principal(), "kill", data, "key-1")
    assert not isinstance(refusal.value, ReachedTheDatabase)


# --- the operator Workspace config accepts exactly one CPU and one memory ---------
#
# These cases observe one thing: `RestrictedWorkspaceRuntime` takes exactly a `cpu` and
# a `memory` allocation plus a policy version, so any other key is refused before the
# request reaches a Node. `gpu` and `buildkit` appear below as examples of such a key,
# and that is all they are. This is **not** an observation of GPU support, nor of a
# BuildKit daemon, socket, privileged-mode or host-access boundary -- no such product
# path exists to observe.


def runtime(**overrides):
    from inv.workspace_api import RestrictedWorkspaceRuntime

    arguments = {
        "profile": "restricted-l2",
        "node": type("N", (), {"node_id": identifier("nod"), "tenant_id": str(uuid4())})(),
        "resources": {"cpu": identifier("res", 0), "memory": identifier("res", 1)},
        "signing_key": "k",
        "policy_version": "v1",
        "client": object(),
    }
    arguments.update(overrides)
    return RestrictedWorkspaceRuntime(object(), **arguments)


def test_the_accepted_allocation_is_exactly_one_cpu_and_one_memory():
    """The control: the shape the design permits is permitted."""
    assert runtime() is not None


@pytest.mark.parametrize(
    "resources",
    [
        {"cpu": "c", "memory": "m", "gpu": "g"},
        {"cpu": "c", "memory": "m", "buildkit": "b"},
        {"cpu": "c"},
        {"memory": "m"},
        {},
    ],
)
def test_a_smuggled_capability_allocation_is_refused(resources):
    """An unknown allocation key is refused here rather than forwarded to a Node.

    `RestrictedWorkspaceRuntime`'s docstring says the operator profile "does not certify
    arbitrary OS/GPU/BuildKit capabilities", and the enforcement is this narrow: the
    mapping must be exactly `cpu` and `memory`. `gpu` and `buildkit` are refused because
    they are not those two keys -- not because anything here understands a GPU or a build
    daemon.
    """
    with pytest.raises(ValueError):
        runtime(resources={k: identifier("res", n) for n, k in enumerate(resources)})


def test_cpu_and_memory_must_be_distinct_resources():
    """One identifier used twice would make a single resource look like two."""
    same = identifier("res", 5)
    with pytest.raises(ValueError):
        runtime(resources={"cpu": same, "memory": same})


@pytest.mark.parametrize("policy_version", ["", None, 0])
def test_an_allocation_without_a_policy_version_is_refused(policy_version):
    with pytest.raises(ValueError):
        runtime(policy_version=policy_version)


# --- the gate, on the write path that has to honour it ----------------------------


TENANT = str(uuid4())
PROJECT = identifier("prj")
RUN_ROW = {
    "run_id": identifier("run", 3),
    "tenant_id": TENANT,
    "project_id": PROJECT,
    "state": "planned",
    "version": 1,
    "attempt": 0,
}


class ScriptedConnection:
    """Answers by statement and records the order it was asked in.

    The order is half the point. A gate consulted after the row is written refuses nothing
    that matters, and only the sequence of statements shows which it was.
    """

    def __init__(self, gate, run_row=None, updated_row=None):
        self.gate = gate
        self.run_row = run_row if run_row is not None else dict(RUN_ROW)
        self.updated_row = updated_row
        self.statements: list[str] = []
        self._answer = None

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        self.statements.append(text)
        if "inv.tenant_controls" in text:
            self._answer = self.gate
        elif text.startswith("UPDATE inv.runs"):
            self._answer = self.updated_row
        elif "inv.runs" in text:
            self._answer = self.run_row
        elif "inv.outbox" in text or "inv.run_attempts" in text:
            self._answer = None
        else:  # pragma: no cover - a new statement must be scripted deliberately
            raise AssertionError(f"unscripted statement: {text}")
        return self

    def fetchone(self):
        return self._answer

    def writes_to_runs(self):
        return [
            text
            for text in self.statements
            if text.startswith(("INSERT INTO inv.runs", "UPDATE inv.runs"))
        ]

    def index_of(self, needle):
        for position, text in enumerate(self.statements):
            if needle in text:
                return position
        raise AssertionError(f"no statement contained {needle!r}")


class ScriptedDatabase:
    recovery_epoch = "epoch-1"

    def __init__(self, conn):
        self.conn = conn

    @contextlib.contextmanager
    def transaction(self, tenant_id, **_):
        yield self.conn


@pytest.mark.parametrize(
    "gate", [None, {"kill_switch": True}], ids=["no-control-row", "switch-on"]
)
def test_run_creation_is_stopped_by_the_gate_before_anything_is_written(gate):
    """`RunStore.create`, not `require_execution`.

    Deleting `require_execution(conn)` from `runs.py` is the mutation this case exists for;
    nothing that only calls the helper can see it.
    """
    conn = ScriptedConnection(gate)
    with pytest.raises(DomainError) as refusal:
        RunStore(ScriptedDatabase(conn)).create(TENANT, PROJECT)
    assert refusal.value.code == "AUTH-0061"
    assert refusal.value.status == 409
    assert conn.writes_to_runs() == [], "a Run was written while the gate was closed"


def test_run_creation_reads_the_gate_before_it_inserts():
    """The positive control, and the ordering.

    A cleared gate must let the Run through -- otherwise the case above would pass for a
    `create` that always refuses -- and the gate must be the earlier statement.
    """
    conn = ScriptedConnection({"kill_switch": False})
    created = RunStore(ScriptedDatabase(conn)).create(TENANT, PROJECT)
    assert created["runId"] == RUN_ROW["run_id"]
    assert conn.index_of("inv.tenant_controls") < conn.index_of("INSERT INTO inv.runs"), (
        "the gate was read after the Run was already written"
    )


@pytest.mark.parametrize(
    "gate", [None, {"kill_switch": True}], ids=["no-control-row", "switch-on"]
)
def test_a_state_change_into_execution_is_stopped_by_the_gate(gate):
    """Creation is not the only way in: a planned Run becoming scheduled is execution too."""
    conn = ScriptedConnection(gate)
    with pytest.raises(DomainError) as refusal:
        RunStore(ScriptedDatabase(conn)).transition(
            TENANT, RUN_ROW["run_id"], "scheduled", expected_version=1
        )
    assert refusal.value.code == "AUTH-0061"
    assert conn.writes_to_runs() == [], "the state changed while the gate was closed"
    # The lock did happen: the refusal came from the gate inside the transaction, not
    # from failing to find the Run.
    assert conn.index_of("FOR UPDATE") < conn.index_of("inv.tenant_controls")


def test_a_state_change_passes_a_cleared_gate():
    """The control for the case above."""
    conn = ScriptedConnection(
        {"kill_switch": False}, updated_row={**RUN_ROW, "state": "scheduled", "version": 2}
    )
    result = RunStore(ScriptedDatabase(conn)).transition(
        TENANT, RUN_ROW["run_id"], "scheduled", expected_version=1
    )
    assert result["state"] == "scheduled" and result["version"] == 2
    assert conn.index_of("inv.tenant_controls") < conn.index_of("UPDATE inv.runs")
