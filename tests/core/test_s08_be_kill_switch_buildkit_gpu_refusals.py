"""S08-BE: the refusals that make ROOF, the kill switch, BuildKit and single-GPU real.

`S08-BE`'s scope is "ROOF, kill switch, BuildKit, single GPU" and the 48-task re-score kept
it at 50 because no test was bound to it. The missing thing was never the hardware: a GPU
cannot be rented into a unit test, and the row's 100 still waits on `G-19`. What *is*
observable without any of it is the set of **refusals** the design rests on, and those are
what this file holds.

Two groups, matching the four words in the scope.

* **The kill switch is fail-closed, and its scope is not negotiable.** A tenant with no
  control row at all is stopped, not allowed; the gate is read before anything else.
  Kill and clear are tenant-wide and must not name a Node, drain and resume are per-Node
  and must, and the idempotency key is required before any work happens. These guards run
  ahead of the database, so they are testable with a connection that answers one query.
* **The operator profile does not certify arbitrary OS, GPU or BuildKit capabilities.**
  `RestrictedWorkspaceRuntime` says so in its own docstring, and it enforces it by
  accepting exactly one CPU and one distinct memory allocation with a policy version, and
  nothing else. A request that smuggles a `gpu` allocation in is refused here rather than
  being trusted and passed to a Node.

What this file deliberately does not do: assert that a GPU exists, that BuildKit built
anything, or that a physical ROOF limit was hit. Those are `G-19` observations and a test
that faked them would be worse than no test.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from inv.containment import Containment, require_execution
from inv.errors import DomainError


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


# --- the profile certifies no OS, GPU or BuildKit capability -----------------------


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
    """The docstring's claim, enforced.

    `RestrictedWorkspaceRuntime` says the operator profile "does not certify arbitrary
    OS/GPU/BuildKit capabilities". A request that adds a `gpu` or `buildkit` allocation is
    refused here rather than being forwarded to a Node to discover.
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
