"""Synthetic certs plus real mandatory PostgreSQL admission boundaries.

These tests are NOT executed on the author's main host. The shared migrated /
owner_engine fixtures allocate a disposable DB, fail on missing CI admin input,
and audit it at teardown. No extra opt-in skip or live Node transport is used.
"""

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

from inv import fresh_cpu_admission as subject
from inv.capacity import project_capacity
from inv.errors import DomainError
from inv.ids import new_id
from inv.node_channels import node_uri, provision_channel
from inv.tooling import NodePrincipal


def encoded(body):
    return json.dumps(body, separators=(",", ":")).encode()


@pytest.fixture
def request_factory():
    def make(*, tenant=None, epoch=None, project=None, node=None, uri=None,
             start=None, end=None, ca=False, client_only=False):
        tenant, epoch = tenant or str(uuid4()), epoch or str(uuid4())
        node = node or new_id("nod")
        now = datetime.now(timezone.utc)
        # Synthetic key exists only during a future test execution; never saved.
        key = ed25519.Ed25519PrivateKey.generate()
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic-admission")])
        certificate = (
            x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(start or now - timedelta(minutes=1))
            .not_valid_after(end or now + timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(
                uri or node_uri(NodePrincipal(tenant, node), epoch),
            )]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.CLIENT_AUTH if client_only else ExtendedKeyUsageOID.SERVER_AUTH,
            ]), critical=False).sign(key, algorithm=None)
        )
        return {
            "requestVersion": 1, "tenantId": tenant, "recoveryEpoch": epoch,
            "projectId": project or new_id("prj"), "nodeId": node,
            "cpuResourceId": new_id("res"), "memoryResourceId": new_id("res"),
            "endpoint": "https://cpu.synthetic.invalid:9443",
            "certificateDERBase64": base64.b64encode(certificate.public_bytes(
                serialization.Encoding.DER,
            )).decode(),
            "expectedTenantControlVersion": 0,
            "cpuMillis": 500, "memoryBytes": 67108864,
        }
    return make


@pytest.fixture
def fresh_db(migrated, owner_engine, request_factory):
    # Reuse mandatory root fixtures, including real production migrations.
    params = owner_engine.url.translate_connect_args(username="user", database="dbname")
    driver_connect = psycopg.connect

    def connect():
        return driver_connect(**params, autocommit=True)

    tenant, other, project = str(uuid4()), str(uuid4()), new_id("prj")
    with connect() as conn:
        conn.execute("""INSERT INTO inv.control_epoch(singleton,epoch) VALUES(true,%s)
            ON CONFLICT(singleton) DO NOTHING""", (str(uuid4()),))
        epoch = str(conn.execute("SELECT epoch FROM inv.control_epoch WHERE singleton").fetchone()[0])
        conn.execute("INSERT INTO inv.tenants(tenant_id,name) VALUES(%s,'synthetic'),(%s,'other')",
                     (tenant, other))
        conn.execute("INSERT INTO inv.projects(tenant_id,project_id) VALUES(%s,%s)", (tenant, project))
    body = request_factory(tenant=tenant, epoch=epoch, project=project)
    return SimpleNamespace(connect=connect, tenant=tenant, other=other,
                           project=project, epoch=epoch, body=body)


TABLES = ("nodes", "resources", "project_nodes", "node_channels", "node_channel_audit",
          "node_controls", "node_resource_snapshots", "tenant_controls", "project_grants")


def snapshot(db):
    with db.connect() as conn:
        return {
            table: conn.execute(sql.SQL("SELECT to_jsonb(t) FROM inv.{} t WHERE tenant_id=%s "
                                       "ORDER BY to_jsonb(t)::text").format(sql.Identifier(table)),
                                (db.tenant,)).fetchall()
            for table in TABLES
        }


def commit(db, body=None):
    raw = encoded(db.body if body is None else body)
    digest = subject.prepare_request(raw).digest()
    with db.connect() as conn:
        return subject.apply_admission(conn, raw, expected_plan_sha256=digest)


def expect_refusal(db, code, body=None):
    before = snapshot(db)
    with pytest.raises(DomainError) as error:
        commit(db, body)
    assert error.value.code == code
    assert snapshot(db) == before


@pytest.mark.postgres
def test_plan_select_only_and_apply_commits_exact_offline_rows(fresh_db):
    db = fresh_db
    before = snapshot(db)
    with db.connect() as conn:
        # PostgreSQL itself refuses persistent writes in this PLAN transaction.
        conn.read_only = True
        plan = subject.plan_admission(conn, encoded(db.body))
    assert snapshot(db) == before
    assert plan["mode"] == "PLAN" and plan["status"] == "READY"
    assert plan["plan"]["certificateIssuerChainVerified"] is False
    result = commit(db)
    assert result["status"] == "COMMITTED" and result["planSha256"] == plan["planSha256"]
    after = snapshot(db)
    assert after["tenant_controls"] == before["tenant_controls"]
    assert after["project_grants"] == before["project_grants"]
    assert [len(after[t]) - len(before[t]) for t in TABLES[:6]] == [1, 2, 1, 1, 1, 1]
    assert after["node_resource_snapshots"] == []
    with db.connect() as conn:
        conn.row_factory = dict_row
        with conn.transaction():
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (db.tenant,))
            capacity = project_capacity(conn, db.project, db.epoch)
        assert capacity["nodes"] == []
        assert capacity["spareNow"] == {"cpuMillis": 0, "memoryBytes": 0}
        node = conn.execute("SELECT status FROM inv.nodes WHERE tenant_id=%s AND node_id=%s",
                            (db.tenant, db.body["nodeId"])).fetchone()
        assert node["status"] == "offline"
    with db.connect() as conn:
        assert subject.reconcile_admission(conn, encoded(db.body))["mode"] == "RECONCILE"
    expect_refusal(db, "FRESH-0008")  # not an idempotent upsert/resume API


@pytest.mark.postgres
@pytest.mark.parametrize("role", ["inv_kernel", "inv_app"])
def test_real_nonoperator_role_cannot_admit(fresh_db, role):
    db = fresh_db
    before = snapshot(db)
    with db.connect() as conn:
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        with pytest.raises(DomainError) as error:
            subject.apply_admission(conn, encoded(db.body),
                                    expected_plan_sha256=subject.prepare_request(encoded(db.body)).digest())
    assert error.value.code == "FRESH-0004"
    assert snapshot(db) == before


@pytest.mark.postgres
@pytest.mark.parametrize("case", ["wrong-tenant", "missing-project", "wrong-epoch", "control-version"])
def test_scope_epoch_version_refusals_preserve_every_row(fresh_db, case):
    db, body = fresh_db, deepcopy(fresh_db.body)
    code = "FRESH-0005"
    if case == "wrong-tenant":
        # Keep a valid matching certificate: the refusal must be DB scope, not DER.
        with db.connect() as conn:
            conn.execute("DELETE FROM inv.projects WHERE tenant_id=%s AND project_id=%s",
                         (db.tenant, db.project))
            conn.execute("INSERT INTO inv.projects(tenant_id,project_id) VALUES(%s,%s)",
                         (db.other, db.project))
    elif case == "missing-project":
        body["projectId"] = new_id("prj")
    elif case == "wrong-epoch":
        # Replacing only epoch would be an earlier certificate refusal.
        code = "NODE-0032"
        body["recoveryEpoch"] = str(uuid4())
    else:
        code, body["expectedTenantControlVersion"] = "FRESH-0007", 1
    expect_refusal(db, code, body)


@pytest.mark.postgres
def test_matching_certificate_with_wrong_current_epoch_is_refused(fresh_db, request_factory):
    db = fresh_db
    body = request_factory(tenant=db.tenant, project=db.project, epoch=str(uuid4()))
    expect_refusal(db, "FRESH-0006", body)


@pytest.mark.postgres
@pytest.mark.parametrize("enabled,status,accepted", [(True, "active", True),
                                                    (False, "active", False),
                                                    (True, "archived", False)])
def test_existing_business_link_requires_enabled_active_project(fresh_db, enabled, status, accepted):
    db = fresh_db
    with db.connect() as conn:
        conn.execute("""INSERT INTO public.tenants(tenant_id,slug,display_name,version)
            VALUES(%s,%s,'synthetic',1)""", (db.tenant, "admission-" + uuid4().hex))
        conn.execute("""INSERT INTO public.projects
            (project_id,tenant_id,code,display_name,status,version) VALUES(%s,%s,%s,'synthetic',%s,1)""",
                     (db.project, db.tenant, "admission-" + uuid4().hex, status))
        conn.execute("INSERT INTO inv.business_projects(tenant_id,project_id,enabled) VALUES(%s,%s,%s)",
                     (db.tenant, db.project, enabled))
    if accepted:
        assert commit(db)["status"] == "COMMITTED"
    else:
        expect_refusal(db, "FRESH-0005")


@pytest.mark.postgres
def test_kill_switch_does_not_block_metadata_and_is_not_cleared(fresh_db):
    db = fresh_db
    with db.connect() as conn:
        conn.execute("UPDATE inv.tenant_controls SET kill_switch=true,version=7 WHERE tenant_id=%s",
                     (db.tenant,))
    db.body["expectedTenantControlVersion"] = 7
    before = snapshot(db)["tenant_controls"]
    assert commit(db)["status"] == "COMMITTED"
    assert snapshot(db)["tenant_controls"] == before


@pytest.mark.postgres
@pytest.mark.parametrize("collision", ["node", "cpu-resource", "memory-resource", "association", "channel"])
def test_existing_identity_or_channel_is_never_repaired(fresh_db, collision):
    db, body = fresh_db, fresh_db.body
    old_node = new_id("nod") if collision.endswith("resource") else body["nodeId"]
    with db.connect() as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (db.tenant,))
            conn.execute("""INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch)
                VALUES(%s,%s,'offline',%s)""", (db.tenant, old_node, db.epoch))
            if collision.endswith("resource"):
                resource = body["cpuResourceId" if collision == "cpu-resource" else "memoryResourceId"]
                conn.execute("""INSERT INTO inv.resources(tenant_id,resource_id,node_id,kind,capacity,offered)
                    VALUES(%s,%s,%s,'cpu',1,1)""", (db.tenant, resource, old_node))
            elif collision == "association":
                conn.execute("INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)",
                             (db.tenant, db.project, old_node))
            elif collision == "channel":
                provision_channel(conn, NodePrincipal(db.tenant, old_node), epoch=db.epoch,
                                  endpoint=body["endpoint"], expected_version=0,
                                  certificate_der=base64.b64decode(body["certificateDERBase64"]))
    expect_refusal(db, "FRESH-0008")


@pytest.mark.postgres
def test_changed_plan_and_outer_transaction_cannot_apply(fresh_db):
    db = fresh_db
    raw = encoded(db.body)
    digest = subject.prepare_request(raw).digest()
    changed = {**db.body, "endpoint": "https://different.synthetic.invalid:9443"}
    before = snapshot(db)
    with db.connect() as conn:
        with pytest.raises(DomainError) as error:
            subject.apply_admission(conn, encoded(changed), expected_plan_sha256=digest)
        assert error.value.code == "FRESH-0002"
        with conn.transaction():
            conn.execute("SELECT 1")
            with pytest.raises(DomainError) as error:
                subject.apply_admission(conn, raw, expected_plan_sha256=digest)
            assert error.value.code == "FRESH-0003"
    assert snapshot(db) == before


@pytest.mark.postgres
def test_real_sql_failure_after_channel_audit_rolls_back_all_rows(fresh_db, monkeypatch):
    db, original = fresh_db, subject.provision_channel

    def fail_after_audit(conn, *args, **kwargs):
        original(conn, *args, **kwargs)
        conn.execute("SELECT 1/0")  # actual PostgreSQL transaction-aborting error

    monkeypatch.setattr(subject, "provision_channel", fail_after_audit)
    expect_refusal(db, "FRESH-0011")


@pytest.mark.postgres
def test_actual_readback_inconsistency_rolls_back(fresh_db, monkeypatch):
    db, original = fresh_db, subject.provision_channel

    def change_after_audit(conn, node, **kwargs):
        original(conn, node, **kwargs)
        conn.execute("""UPDATE inv.resources SET offered=0
            WHERE tenant_id=%s AND node_id=%s""", (node.tenant_id, node.node_id))

    monkeypatch.setattr(subject, "provision_channel", change_after_audit)
    expect_refusal(db, "FRESH-0009")


@pytest.mark.postgres
def test_ready_plan_rechecks_controls_on_apply(fresh_db):
    db = fresh_db
    with db.connect() as conn:
        plan = subject.plan_admission(conn, encoded(db.body))
        conn.execute("""UPDATE inv.tenant_controls SET version=version+1,kill_switch=true
            WHERE tenant_id=%s""", (db.tenant,))
    assert plan["status"] == "READY"
    expect_refusal(db, "FRESH-0007")


@pytest.mark.postgres
def test_unknown_commit_requires_read_only_reconcile_not_retry(fresh_db):
    db = fresh_db

    class LoseCommitAcknowledgement:
        """Fault injection after a REAL outer PostgreSQL commit, not a fake DB."""
        def __init__(self, conn):
            self.conn, self.depth = conn, 0

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def transaction(self):
            inner, owner = self.conn.transaction(), self
            outer = self.depth == 0

            class Transaction:
                def __enter__(self):
                    owner.depth += 1
                    return inner.__enter__()

                def __exit__(self, typ, value, traceback):
                    try:
                        result = inner.__exit__(typ, value, traceback)
                    finally:
                        owner.depth -= 1
                    if outer and typ is None:
                        raise OSError("synthetic lost commit acknowledgement")
                    return result

            return Transaction()

    raw = encoded(db.body)
    with db.connect() as conn:
        with pytest.raises(DomainError) as error:
            subject.apply_admission(LoseCommitAcknowledgement(conn), raw,
                                    expected_plan_sha256=subject.prepare_request(raw).digest())
        assert error.value.code == "FRESH-0010"
    # A new connection observes the committed rows. No second APPLY is attempted.
    assert [len(snapshot(db)[t]) for t in TABLES[:6]] == [1, 2, 1, 1, 1, 1]
    before = snapshot(db)
    with db.connect() as conn:
        conn.read_only = True
        assert subject.reconcile_admission(conn, raw)["status"] == "MATCHED_METADATA_REQUIRES_OPERATOR_DISPOSITION"
    assert snapshot(db) == before


@pytest.mark.postgres
def test_concurrent_duplicate_has_one_committed_winner_no_partial(fresh_db, monkeypatch):
    db, original, barrier = fresh_db, subject._preflight, Barrier(2)

    def both_observe_absence(cursor, item, *, locked):
        result = original(cursor, item, locked=locked)
        barrier.wait(timeout=15)
        return result

    monkeypatch.setattr(subject, "_preflight", both_observe_absence)

    def attempt(_):
        try:
            return commit(db)["status"]
        except DomainError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sorted(results) == ["COMMITTED", "FRESH-0008"]
    after = snapshot(db)
    assert [len(after[t]) for t in TABLES[:6]] == [1, 2, 1, 1, 1, 1]


@pytest.mark.parametrize("change", [
    {"requestVersion": True}, {"requestVersion": 2}, {"cpuMillis": 500.0},
    {"cpuMillis": True}, {"cpuMillis": 501}, {"memoryBytes": 0},
    {"expectedTenantControlVersion": False}, {"expectedTenantControlVersion": -1},
    {"expectedTenantControlVersion": 9007199254740992}, {"expectedTenantControlVersion": 1.0},
    {"force": True}, {"operator": True}, {"tenantId": "invalid"}, {"projectId": "prj_bad"},
    {"nodeId": None}, {"cpuResourceId": "res_bad"}, {"endpoint": 4},
    {"certificateDERBase64": "@@"}, {"certificateDERBase64": "YQ==\n"},
])
def test_closed_request_types_and_limits_before_any_db(change, request_factory):
    body = {**request_factory(), **change}
    with pytest.raises(DomainError) as error:
        subject.apply_admission(object(), encoded(body), expected_plan_sha256="0" * 64)
    assert error.value.code == "FRESH-0001"


def test_duplicate_keys_ids_nonfinite_oversize_and_noncanonical_base64(request_factory):
    body = request_factory()
    invalid = [
        b'{"requestVersion":1,"requestVersion":1}', b'{"value":NaN}', b'[]', b'{}', b'\xff',
        b'{"value":Infinity}', b"[" * 5000, b"x" * (subject.MAX_REQUEST_BYTES + 1),
        encoded({**body, "memoryResourceId": body["cpuResourceId"]}),
        encoded({**body, "certificateDERBase64": base64.b64encode(b"x" * 65537).decode()}),
        encoded({**body, "certificateDERBase64": "YR=="}),  # decodes like YQ==, noncanonical
    ]
    for raw in invalid:
        with pytest.raises(DomainError) as error:
            subject.prepare_request(raw)
        assert error.value.code == "FRESH-0001"


@pytest.mark.postgres
def test_missing_tenant_with_matching_public_identity_is_refused(fresh_db, request_factory):
    db = fresh_db
    body = request_factory(project=db.project, epoch=db.epoch)
    expect_refusal(db, "FRESH-0005", body)


@pytest.mark.parametrize("case", ["wrong-uri", "wrong-epoch", "expired", "future", "ca", "client", "malformed"])
def test_public_certificate_identity_rejections(request_factory, case):
    now = datetime.now(timezone.utc)
    kwargs = {
        "wrong-uri": {"uri": "spiffe://synthetic.invalid/wrong"},
        "wrong-epoch": {"uri": node_uri(NodePrincipal(str(uuid4()), new_id("nod")), str(uuid4()))},
        "expired": {"start": now - timedelta(hours=2), "end": now - timedelta(hours=1)},
        "future": {"start": now + timedelta(hours=1), "end": now + timedelta(hours=2)},
        "ca": {"ca": True}, "client": {"client_only": True}, "malformed": {},
    }[case]
    body = request_factory(**kwargs)
    if case == "malformed":
        body["certificateDERBase64"] = base64.b64encode(b"not-a-certificate").decode()
    with pytest.raises(DomainError) as error:
        subject.apply_admission(object(), encoded(body), expected_plan_sha256="0" * 64)
    assert error.value.code == "NODE-0032"


@pytest.mark.parametrize("endpoint", ["http://synthetic.invalid", "https://u:p@synthetic.invalid",
                                      "https://synthetic.invalid/path", "https://synthetic.invalid?secret=x"])
def test_endpoint_contract_is_unchanged(request_factory, endpoint):
    body = {**request_factory(), "endpoint": endpoint}
    with pytest.raises(DomainError) as error:
        subject.prepare_request(encoded(body))
    assert error.value.code == "NODE-0031"
