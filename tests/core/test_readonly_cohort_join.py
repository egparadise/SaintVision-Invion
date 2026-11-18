"""Read-only public bundle integrity. Never authenticates an operating Node."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).parents[2]/"tools/recovery_preflight"))
from common import report, scope
from join import join


def sample():
    ids=["nod_"+str(i).zfill(26) for i in range(3)]
    tenant="11111111-1111-4111-8111-111111111111"
    epoch="22222222-2222-4222-8222-222222222222"
    d=scope(dict(schema="sv-readonly-cohort:1",sourceSHA="5"*40,tenant=tenant,epoch=epoch,project="prj_"+"0"*26,
                 nodes={n:dict(cid=format(i,"064x"),image="7"*64,config="/opt/config",state="/opt/state",argv=["/fixture"]) for i,n in enumerate(ids)},
                 ownerLabel="owner",ownerValue="fixture",caDER="3"*64,cpDER="4"*64,databaseRole="fixture",maxAgeSeconds=120))
    at=datetime.now(timezone.utc)
    expired=(at-timedelta(days=1)).isoformat()
    started=(at-timedelta(seconds=3)).isoformat()
    observations=[]
    channels={}
    for i,n in enumerate(ids):
        o=report(d,"node")
        o.update(startedAt=started,observedAt=at.isoformat(),observationComplete=True)
        der=format(i+8,"064x")
        o["facts"]=dict(node=n,cid=d["nodes"][n]["cid"],image="sha256:"+"7"*64,
                        ca=dict(derSHA256=d["caDER"],expiresAt=expired),leaf=dict(derSHA256=der,expiresAt=expired),
                        policy=dict(P=4+i,cpDER=d["cpDER"],expiresAt=expired))
        observations.append(o)
        channels[n]=dict(C=20+i,leafDER=der,expiresAt=expired)
    cp=report(d,"control-plane")
    cp.update(startedAt=started,observedAt=at.isoformat(),observationComplete=True)
    cp["facts"]={"channels":channels,"operationOutcome":"UNKNOWN"}
    return d,observations+[cp]


def test_expired_ca_keeps_actual_independent_generations_and_hold():
    d,obs=sample()
    out=join(d,obs)
    assert out["observationComplete"] and not out["recoveryReady"] and not out["activationAllowed"]
    assert {"CA_TERMINAL","LEAF_EXPIRED","POLICY_EXPIRED","OPERATION_OUTCOME_UNKNOWN"}<=set(out["holds"])
    assert [(v["P"],v["C"]) for v in out["facts"]["members"].values()]==[(4,20),(5,21),(6,22)]


@pytest.mark.parametrize("defect",["duplicate","stale","der","missing","scope","expired-prepared"])
def test_join_refuses_incomplete_or_foreign_sources(defect):
    d,obs=sample()
    if defect=="duplicate": obs[1]=copy.deepcopy(obs[0])
    elif defect=="missing": obs.pop()
    elif defect=="stale": obs[0]["startedAt"]="2000-01-01T00:00:00+00:00"
    elif defect=="scope": obs[0]["descriptorSHA256"]="0"*64
    elif defect=="der": obs[0]["facts"]["leaf"]["derSHA256"]="0"*64
    else:
        obs[-1]["facts"]["operationOutcome"]="PREPARED"
        obs[-1]["facts"]["operationDeadline"]="2000-01-01T00:00:00+00:00"
    out=join(d,obs)
    assert not out["activationAllowed"] and not out["recoveryReady"]
    if defect=="expired-prepared":
        assert "EXPIRED_PREPARED_REQUIRES_FORWARD_RECONCILIATION" in out["holds"]
    else:
        assert not out["observationComplete"]
