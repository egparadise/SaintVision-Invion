"""Disposable-PG S07 measurement invoked only by tools/measure_s07_recovery.py."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import time
import uuid

import pytest
from sqlalchemy import text

from saintvision.db.session import tenant_scope
from saintvision.ids import new_id
from saintvision.services import nodes, pools, replica_repair
from saintvision.services.nodes import ObservationInput
from tools.measure_s07_recovery import KERNEL_FRESHNESS_SECONDS, summarize

pytestmark = pytest.mark.postgres
UTC = dt.timezone.utc
SHA = "7" * 64


def _configuration() -> dict:
    raw = os.environ.get("INV_S07_MEASUREMENT_CONFIG")
    if not raw:
        pytest.skip("run through tools/measure_s07_recovery.py")
    return json.loads(raw)


def _seed_round(owner_engine, *, node_count: int, round_index: int):
    tenant_id = uuid.uuid4()
    user_id = new_id("user")
    node_ids = [new_id("node") for _ in range(node_count)]
    capability_ids = [new_id("capability") for _ in node_ids]
    departed_at = dt.datetime.now(UTC)
    contribution_id = new_id("storage_contribution")
    shard_count = max(1, node_count - 2)
    locations: list[str] = []
    with owner_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tenants(tenant_id,slug,display_name,created_at) "
                "VALUES(:t,:s,:d,:n)"
            ),
            {
                "t": tenant_id,
                "s": f"s07-{round_index}-{tenant_id.hex[:10]}",
                "d": f"S07 round {round_index}",
                "n": departed_at,
            },
        )
        connection.execute(
            text(
                "INSERT INTO users(user_id,tenant_id,external_subject,display_name,status,"
                "created_at,updated_at,version) VALUES(:u,:t,:s,'S07','active',:n,:n,1)"
            ),
            {"u": user_id, "t": tenant_id, "s": f"s07:{round_index}", "n": departed_at},
        )
        for index, (node_id, capability_id) in enumerate(zip(node_ids, capability_ids)):
            connection.execute(
                text(
                    "INSERT INTO nodes(node_id,tenant_id,hostname,os_type,os_version,agent_version,"
                    "status,enrolled_at,last_heartbeat_at,heartbeat_sequence,version) "
                    "VALUES(:node,:tenant,:host,'linux','synthetic','s07-measure','active',:seen,:seen,1,1)"
                ),
                {
                    "node": node_id,
                    "tenant": tenant_id,
                    "host": f"s07-r{round_index}-n{index}",
                    "seen": departed_at,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO node_capabilities(capability_id,tenant_id,node_id,kind,total_quantity,"
                    "unit,divisible,detected_at,version) VALUES(:c,:t,:n,'cpu',1000,'millicores',true,:at,1)"
                ),
                {"c": capability_id, "t": tenant_id, "n": node_id, "at": departed_at},
            )
            connection.execute(
                text(
                    "INSERT INTO resource_offers(offer_id,tenant_id,capability_id,offered_quantity,"
                    "effective_from,version) VALUES(:o,:t,:c,1000,:at,1)"
                ),
                {"o": new_id("offer"), "t": tenant_id, "c": capability_id, "at": departed_at},
            )
            connection.execute(
                text(
                    "INSERT INTO resource_snapshots(snapshot_id,observed_at,tenant_id,node_id,"
                    "capability_id,used_quantity,detail) VALUES(:s,:at,:t,:n,:c,0,'{}')"
                ),
                {
                    "s": new_id("snapshot"),
                    "at": departed_at,
                    "t": tenant_id,
                    "n": node_id,
                    "c": capability_id,
                },
            )
        connection.execute(
            text(
                "INSERT INTO storage_contributions(contribution_id,tenant_id,node_id,declared_path,"
                "normalized_path,mode,status,registered_by_user_id,registered_at,version) "
                "VALUES(:c,:t,:n,'/s07','/s07','read_write','active',:u,:at,1)"
            ),
            {
                "c": contribution_id,
                "t": tenant_id,
                "n": node_ids[0],
                "u": user_id,
                "at": departed_at,
            },
        )
        for shard_index in range(shard_count):
            location_id = new_id("data_location")
            locations.append(location_id)
            connection.execute(
                text(
                    "INSERT INTO data_locations(location_id,tenant_id,contribution_id,uri,kind,"
                    "relative_path,byte_size,checksum_sha256,verified_at,ready,catalogued_at,version) "
                    "VALUES(:l,:t,:c,:uri,'dataset',:path,4096,:sha,:at,true,:at,1)"
                ),
                {
                    "l": location_id,
                    "t": tenant_id,
                    "c": contribution_id,
                    "uri": f"inv://datasets/s07-{round_index}@1/shard-{shard_index}.bin",
                    "path": f"shard-{shard_index}.bin",
                    "sha": SHA,
                    "at": departed_at,
                },
            )
            for node_id in node_ids[:2]:
                connection.execute(
                    text(
                        "INSERT INTO data_replicas(replica_id,tenant_id,location_id,node_id,"
                        "contribution_id,state,local_bytes,checksum_sha256,verified_at,last_used_at,created_at) "
                        "VALUES(:r,:t,:l,:n,:c,'ready',4096,:sha,:at,:at,:at)"
                    ),
                    {
                        "r": new_id("replica"),
                        "t": tenant_id,
                        "l": location_id,
                        "n": node_id,
                        "c": contribution_id,
                        "sha": SHA,
                        "at": departed_at,
                    },
                )
    return tenant_id, node_ids, capability_ids, contribution_id, locations, departed_at


def test_repeated_node_loss_and_synthetic_repair_measurement(
    owner_engine, app_sessionmaker, clean_tables
):
    config = _configuration()
    rounds = []
    for round_index in range(config["repetitions"]):
        tenant_id, node_ids, capability_ids, contribution_id, locations, departed_at = _seed_round(
            owner_engine, node_count=config["nodes"], round_index=round_index
        )
        deadline = time.monotonic() + config["livenessTimeoutSeconds"] + max(
            2.0, config["pollIntervalSeconds"] * 4
        )
        detected_at = None
        heartbeat_sequence = 1
        while time.monotonic() < deadline:
            now = dt.datetime.now(UTC)
            with app_sessionmaker() as session:
                with session.begin():
                    with tenant_scope(session, tenant_id):
                        heartbeat_sequence += 1
                        for node_id, capability_id in zip(node_ids[1:], capability_ids[1:]):
                            assert nodes.record_heartbeat(
                                session,
                                tenant_id=tenant_id,
                                node_id=node_id,
                                sequence=heartbeat_sequence,
                                now=now,
                            ).applied
                            assert nodes.record_observations(
                                session,
                                tenant_id=tenant_id,
                                node_id=node_id,
                                observations=[ObservationInput(capability_id, 0, "millicores")],
                                now=now,
                            ) == 1
                        nodes.mark_lost_nodes(
                            session,
                            tenant_id=tenant_id,
                            now=now,
                            timeout_seconds=config["livenessTimeoutSeconds"],
                        )
                        status = session.execute(
                            text("SELECT status FROM nodes WHERE node_id=:n"),
                            {"n": node_ids[0]},
                        ).scalar_one()
            if status == "lost":
                detected_at = now
                break
            time.sleep(config["pollIntervalSeconds"])
        detection_delay = (
            (detected_at - departed_at).total_seconds() if detected_at is not None else None
        )
        repair_started = dt.datetime.now(UTC)
        with app_sessionmaker() as session:
            with session.begin():
                with tenant_scope(session, tenant_id):
                    planned = replica_repair.locations_needing_repair(
                        session, tenant_id=tenant_id, desired=2
                    )
                    spare = pools.node_spare(
                        session,
                        tenant_id=tenant_id,
                        node_ids=node_ids[1:],
                        now=repair_started,
                        freshness_seconds=int(KERNEL_FRESHNESS_SECONDS),
                    )
        fresh_targets = [item.node_id for item in spare if item.measured and item.node_id != node_ids[1]]
        recovered = 0
        if detected_at is not None and fresh_targets and len(planned) == len(locations):
            with owner_engine.begin() as connection:
                for index, location_id in enumerate(locations):
                    target = fresh_targets[index % len(fresh_targets)]
                    connection.execute(
                        text(
                            "INSERT INTO data_replicas(replica_id,tenant_id,location_id,node_id,"
                            "contribution_id,state,local_bytes,checksum_sha256,verified_at,last_used_at,created_at) "
                            "VALUES(:r,:t,:l,:n,:c,'ready',4096,:sha,now(),now(),now())"
                        ),
                        {
                            "r": new_id("replica"),
                            "t": tenant_id,
                            "l": location_id,
                            "n": target,
                            "c": contribution_id,
                            "sha": SHA,
                        },
                    )
            with app_sessionmaker() as session:
                with session.begin():
                    with tenant_scope(session, tenant_id):
                        recovered = sum(
                            replica_repair.replica_health(
                                session, tenant_id=tenant_id, location_id=location_id, desired=2
                            ).classification
                            == "healthy"
                            for location_id in locations
                        )
        with owner_engine.connect() as connection:
            stale = connection.execute(
                text(
                    "SELECT count(*) FROM data_replicas WHERE tenant_id=:t AND node_id=:n "
                    "AND state='stale'"
                ),
                {"t": tenant_id, "n": node_ids[0]},
            ).scalar_one()
        rounds.append(
            {
                "round": round_index + 1,
                "departedNodeId": node_ids[0],
                "detected": detected_at is not None,
                "detectionDelaySeconds": round(detection_delay, 6)
                if detection_delay is not None
                else None,
                "detectedWithinConfiguredLimit": detection_delay is not None
                and detection_delay <= config["maxDetectionSeconds"],
                "freshReplacementCandidates": len(fresh_targets),
                "departedReplicasStale": stale,
                "shardsAttempted": len(locations),
                "shardsRecovered": recovered,
                "recoveryDurationSeconds": round(
                    (dt.datetime.now(UTC) - repair_started).total_seconds(), 6
                ),
            }
        )
    report = summarize(config, rounds)
    output = Path(os.environ["INV_S07_MEASUREMENT_JSON"])
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert len(rounds) == config["repetitions"]
    assert all(item["detected"] for item in rounds), report
    assert report["detectionSloMet"], report
    assert report["recoveryTargetMet"], report
