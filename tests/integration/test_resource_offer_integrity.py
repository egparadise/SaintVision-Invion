"""Real API/DB offers meet the same Node locks as actual lease reservation."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID, uuid4
import time

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from saintvision.db.models import ResourceOffer
from fastapi.testclient import TestClient
import pytest

from inv.app import create_app
from inv.business_surface import configured_business
from inv.errors import DomainError
from inv.leases import Allocation
from saintvision.ids import new_id
from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.services.settings import set_resource_offer
from jwt_support import jwt_fixture
from test_postgres import planned, release


@pytest.fixture
def offers(env, tmp_path, monkeypatch):
    jwt = jwt_fixture(tmp_path, env.tenant)
    user, cap, extra = new_id("user"), new_id("capability"), new_id("run").replace("run_", "res_")
    role = "inv_offer_test_" + uuid4().hex[:20]
    password = uuid4().hex
    with psycopg.connect(env.owner) as c:
        c.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        c.execute(sql.SQL("GRANT inv_app TO {}").format(sql.Identifier(role)))
        c.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'test')",
            (env.tenant, uuid4().hex),
        )
        c.execute(
            "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,'test')",
            (env.tenant, user, jwt.subject("owner")),
        )
        c.execute(
            "INSERT INTO inv.business_admin_grants VALUES(%s,%s,'resources.manage',true)",
            (env.tenant, user),
        )
        c.execute(
            "INSERT INTO public.nodes(tenant_id,node_id,hostname,os_type,os_version,agent_version,status) VALUES(%s,%s,'offer-node','linux','test','test','active')",
            (env.tenant, env.node),
        )
        c.execute(
            "INSERT INTO public.node_capabilities(tenant_id,node_id,capability_id,kind,total_quantity,unit,divisible) VALUES(%s,%s,%s,'cpu',4000,'millicores',true)",
            (env.tenant, env.node, cap),
        )
        c.execute(
            "UPDATE inv.resources SET capacity=2000,offered=1000 WHERE resource_id=%s",
            (env.resource,),
        )
        c.execute(
            "INSERT INTO inv.resources VALUES(%s,%s,%s,'cpu',2000,1000)",
            (env.tenant, extra, env.node),
        )
    info = conninfo_to_dict(env.runtime)
    url = URL.create(
        "postgresql+psycopg",
        username=role,
        password=password,
        host=info["host"],
        port=int(info["port"]),
        database=info["dbname"],
    )
    monkeypatch.setenv("INV_BUSINESS_DSN", url.render_as_string(hide_password=False))
    business = configured_business(env.db, jwt.auth)
    try:
        with TestClient(
            create_app(env.db, jwt.auth, business=business), raise_server_exceptions=False
        ) as client:
            yield SimpleNamespace(
                e=env,
                user=user,
                cap=cap,
                resources=sorted([env.resource, extra]),
                client=client,
                engine=business.state.engine,
                headers={"Authorization": "Bearer " + jwt.token("owner")},
            )
    finally:
        business.state.engine.dispose()
        with psycopg.connect(env.owner) as c:
            c.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def put(a, quantity, unit="millicores", cap=None):
    return a.client.put(
        "/v1/capabilities/" + (cap or a.cap) + "/offer",
        json={"offeredQuantity": quantity, "unit": unit},
        headers=a.headers,
    )


def amounts(a):
    with psycopg.connect(a.e.owner) as c:
        return c.execute(
            "SELECT resource_id,offered FROM inv.resources WHERE tenant_id=%s ORDER BY resource_id",
            (a.e.tenant,),
        ).fetchall()


def test_http_offer_sets_one_budget_across_every_slice_and_replay(offers):
    a = offers
    r = put(a, 2.5, "cores")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["appliedToKernel"] and not b["executionReady"]
    assert b["kernelResourceIds"] == a.resources and b["kernelResourceId"] is None
    assert [n for _, n in amounts(a)] == [2000, 500]
    assert put(a, 2500).status_code == 200
    with psycopg.connect(a.e.owner) as c:
        assert c.execute(
            "SELECT offered_quantity FROM public.resource_offers WHERE capability_id=%s", (a.cap,)
        ).fetchall() == [(2500,)]


def test_real_leases_prevent_lowering_and_future_reservations_obey_the_budget(offers):
    a = offers
    assert put(a, 2000).status_code == 200
    r = planned(a.e)
    lease = a.e.leases.reserve(
        a.e.tenant, a.e.project, r["runId"], [Allocation(a.resources[0], 1500)], key=uuid4().hex
    )[0]
    assert put(a, 1000).status_code == 422
    assert sum(v for _, v in amounts(a)) == 2000
    assert put(a, 1500).status_code == 200
    with pytest.raises(DomainError, match="Insufficient offered"):
        a.e.leases.reserve(
            a.e.tenant,
            a.e.project,
            planned(a.e)["runId"],
            [Allocation(a.resources[0], 1)],
            key=uuid4().hex,
        )
    # Expiry alone does not release a physical allocation.
    with psycopg.connect(a.e.owner) as c:
        c.execute(
            "UPDATE inv.resource_leases SET expires_at=granted_at+interval '1 millisecond' WHERE lease_id=%s",
            (lease["leaseId"],),
        )
    assert put(a, 0).status_code == 422
    release(a.e, lease)
    assert put(a, 0).status_code == 200
    assert sum(v for _, v in amounts(a)) == 0


def test_reservation_and_offer_reduction_cannot_both_spend_the_same_capacity(offers):
    a = offers
    assert put(a, 2000).status_code == 200
    run = planned(a.e)
    barrier = Barrier(2)

    def reserve():
        barrier.wait(timeout=5)
        try:
            a.e.leases.reserve(
                a.e.tenant,
                a.e.project,
                run["runId"],
                [Allocation(a.resources[0], 1500)],
                key=uuid4().hex,
            )
            return True
        except DomainError as exc:
            assert exc.code in {"RES-0001", "RES-0007"}
            return False

    def lower():
        barrier.wait(timeout=5)
        response = put(a, 0)
        assert response.status_code in {200, 422}
        return response.status_code == 200

    with ThreadPoolExecutor(max_workers=2) as pool:
        f, g = pool.submit(reserve), pool.submit(lower)
        assert sum([f.result(timeout=10), g.result(timeout=10)]) == 1
    with psycopg.connect(a.e.owner) as c:
        held = c.execute(
            "SELECT coalesce(sum(amount),0) FROM inv.resource_leases WHERE tenant_id=%s AND released_at IS NULL",
            (a.e.tenant,),
        ).fetchone()[0]
    assert sum(v for _, v in amounts(a)) >= held


@pytest.mark.parametrize("change", ["revoke", "suspend", "wrong-permission"])
def test_current_administration_is_required_in_http_and_definer(offers, change):
    a = offers
    with psycopg.connect(a.e.owner) as c:
        if change == "revoke":
            c.execute(
                "UPDATE inv.business_admin_grants SET enabled=false WHERE tenant_id=%s",
                (a.e.tenant,),
            )
        elif change == "suspend":
            c.execute("UPDATE public.users SET status='suspended' WHERE user_id=%s", (a.user,))
        else:
            c.execute(
                "UPDATE inv.business_admin_grants SET permission='users.manage' WHERE tenant_id=%s",
                (a.e.tenant,),
            )
    assert put(a, 0).status_code in {401, 403}
    with a.engine.begin() as c, pytest.raises(DBAPIError) as caught:
        c.execute(text("SELECT set_config('inv.tenant_id',:t,true)"), {"t": a.e.tenant})
        c.execute(
            text("SELECT * FROM public.apply_capability_offer(:t,:c,:u,0)"),
            {"t": a.e.tenant, "c": a.cap, "u": a.user},
        )
    assert getattr(caught.value.orig, "sqlstate", None) == "42501"
    assert sum(v for _, v in amounts(a)) == 2000


def test_old_definer_and_direct_kernel_updates_are_unavailable(offers):
    a = offers
    with a.engine.connect() as c:
        role = c.execute(text("SELECT current_user")).scalar_one()
        assert (
            c.execute(
                text(
                    "SELECT has_function_privilege(current_user,'public.apply_resource_offer(uuid,char(30),text,bigint)','EXECUTE')"
                )
            ).scalar_one()
            is False
        )
    # Runtime cannot even resolve names in inv; inspect its ACL as the owner.
    with psycopg.connect(a.e.owner) as c:
        assert c.execute(
            "SELECT has_table_privilege(%s,'inv.resources','UPDATE')", (role,)
        ).fetchone() == (False,)


def test_cross_tenant_definer_never_changes_resources(offers):
    a = offers
    with a.engine.begin() as c:
        c.execute(text("SELECT set_config('inv.tenant_id',:t,true)"), {"t": a.e.other})
        assert c.execute(
            text("SELECT applied,reason FROM public.apply_capability_offer(:t,:c,:u,0)"),
            {"t": a.e.tenant, "c": a.cap, "u": a.user},
        ).one() == (False, "tenant_scope_mismatch")
    assert sum(v for _, v in amounts(a)) == 2000


def test_gpu_offer_is_intent_until_the_device_identity_can_be_mapped(offers):
    a = offers
    caps = [new_id("capability") for _ in range(2)]
    gpu = new_id("run").replace("run_", "res_")
    with psycopg.connect(a.e.owner) as c:
        for index, cap in enumerate(caps):
            c.execute(
                "INSERT INTO public.node_capabilities(tenant_id,node_id,capability_id,kind,device_index,total_quantity,unit) VALUES(%s,%s,%s,'gpu',%s,1,'devices')",
                (a.e.tenant, a.e.node, cap, index),
            )
        c.execute(
            "INSERT INTO inv.resources VALUES(%s,%s,%s,'gpu',1,0)", (a.e.tenant, gpu, a.e.node)
        )
    for cap in caps:
        response = put(a, 1, "devices", cap).json()
        assert (
            not response["appliedToKernel"]
            and response["kernelReasonCode"] == "device_mapping_required"
        )
    assert dict(amounts(a))[gpu] == 0


def test_late_business_history_failure_rolls_back_kernel_change(offers):
    a = offers
    with pytest.raises(DBAPIError) as caught:
        with Session(a.engine) as s, s.begin(), tenant_scope(s, a.e.tenant):

            original_flush = s.flush

            def fail(*args, **kwargs):
                if any(isinstance(row, ResourceOffer) for row in s.new):
                    with s.no_autoflush:
                        s.execute(text("SELECT 1/0"))
                return original_flush(*args, **kwargs)

            s.flush = fail
            set_resource_offer(
                s,
                tenant_id=UUID(a.e.tenant),
                capability_id=a.cap,
                acting_user_id=a.user,
                offered_quantity=0,
                unit="millicores",
                now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
    assert getattr(caught.value.orig, "sqlstate", None) == "22012"
    assert sum(v for _, v in amounts(a)) == 2000
    with psycopg.connect(a.e.owner) as c:
        assert c.execute(
            "SELECT count(*) FROM public.resource_offers WHERE capability_id=%s", (a.cap,)
        ).fetchone() == (0,)


def test_release_during_actual_offer_keeps_recorded_and_applied_totals_equal(offers):
    """The real release must wait for the real offer, preserving its snapshot.

    Only the disposable test DB gets this invoker trigger. An advisory lock
    makes the release interleaving deterministic without changing production SQL.
    """
    a = offers
    lease = a.e.leases.reserve(
        a.e.tenant,
        a.e.project,
        planned(a.e)["runId"],
        [Allocation(a.resources[1], 100)],
        key=uuid4().hex,
    )[0]
    key = uuid4().int % 2_000_000_000 + 1
    with psycopg.connect(a.e.owner, autocommit=True) as blocker:
        blocker.execute(sql.SQL("""
            CREATE FUNCTION public.offer_test_barrier() RETURNS trigger
            LANGUAGE plpgsql AS $body$ BEGIN
              PERFORM pg_catalog.pg_advisory_xact_lock({}); RETURN NEW;
            END $body$;
        """).format(sql.Literal(key)))
        blocker.execute(sql.SQL("""
            CREATE TRIGGER offer_test_barrier BEFORE UPDATE ON inv.resources
            FOR EACH ROW WHEN (NEW.resource_id={})
            EXECUTE FUNCTION public.offer_test_barrier()
        """).format(sql.Literal(a.resources[0])))
        blocker.execute("SELECT pg_advisory_lock(%s)", (key,))
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                future = pool.submit(put, a, 1000)
                try:
                    deadline = time.monotonic() + 8
                    while not blocker.execute(
                        "SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_locks WHERE "
                        "locktype='advisory' AND classid=0 AND objid=%s AND NOT granted)",
                        (key,),
                    ).fetchone()[0]:
                        assert (
                            time.monotonic() < deadline
                        ), "Offer did not reach the controlled interleaving"
                        time.sleep(0.01)
                    # Release locks Run -> Node -> Resource before its lease.
                    # Observe the actual PostgreSQL wait, not a timing assumption.
                    releasing = pool.submit(release, a.e, lease)
                    deadline = time.monotonic() + 8
                    while not blocker.execute(
                        "SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_stat_activity a "
                        "WHERE a.datname=current_database() AND a.wait_event_type='Lock' "
                        "AND EXISTS(SELECT 1 FROM pg_catalog.pg_locks l "
                        "WHERE l.locktype='advisory' AND l.classid=0 AND l.objid=%s "
                        "AND NOT l.granted AND l.pid=ANY(pg_catalog.pg_blocking_pids(a.pid))))",
                        (key,),
                    ).fetchone()[0]:
                        assert not releasing.done(), "Release bypassed the offer's resource locks"
                        assert time.monotonic() < deadline, "Release did not wait for the offer"
                        time.sleep(0.01)
                    assert blocker.execute(
                        "SELECT released_at IS NOT NULL FROM inv.resource_leases WHERE lease_id=%s",
                        (lease["leaseId"],),
                    ).fetchone() == (False,)
                finally:
                    blocker.execute("SELECT pg_advisory_unlock(%s)", (key,))
                response = future.result(timeout=10)
                releasing.result(timeout=10)
            assert response.status_code == 200
            assert response.json()["appliedToKernel"] is True
            recorded = blocker.execute(
                "SELECT offered_quantity FROM public.resource_offers WHERE capability_id=%s",
                (a.cap,),
            ).fetchone()[0]
            applied = sum(value for _, value in amounts(a))
            assert applied == recorded == 1000, f"Recorded {recorded}, applied {applied}"
            assert blocker.execute(
                "SELECT released_at IS NOT NULL FROM inv.resource_leases WHERE lease_id=%s",
                (lease["leaseId"],),
            ).fetchone() == (True,)
        finally:
            blocker.execute("DROP TRIGGER offer_test_barrier ON inv.resources")
            blocker.execute("DROP FUNCTION public.offer_test_barrier()")
