"""Contract schema/predicate fixtures ONLY: no Node/PG/Docker/PKI operations.

These values and signature/witness predicates are synthetic. A pass means the
proposal is internally consistent; it is not implementation or runtime proof.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / "proposed-closed-abi.schema.json").read_bytes())
RESULTS = []
CASES = []
NOW = 2000000000
H = "a" * 64


def check(name, actual, expected, level="SCHEMA_OR_MOCK_PREDICATE"):
    RESULTS.append({"case": name, "actual": actual, "expected": expected, "passed": actual == expected, "level": level})


def schema_ok(kind, obj):
    scoped = {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{kind}"}
    return Draft202012Validator(scoped).is_valid(obj)


def record_schema(name, kind, obj, expected):
    CASES.append({"name": name, "schema": kind, "value": obj, "expected": expected})
    check(name, schema_ok(kind, obj), expected)


def context():
    props = SCHEMA["$defs"]["executionContext"]["properties"]
    values = {k: H if "Sha256" in k else "fixture-context" for k in props}
    for k,v in props.items():
        if "const" in v:
            values[k] = v["const"]
        elif "enum" in v:
            values[k] = v["enum"][0]
    return values


def current(i):
    return {"channel": {"tenant_id": "fixture-tenant", "node_id": f"fixture-node-{i}", "recovery_epoch": "fixture-epoch", "version": 9, "endpoint": f"https://fixture-node-{i}.invalid:7443", "certificate_sha256": "b"*64},
            "contributionId": f"fixture-contribution-{i}", "rootVersion": 1, "policySha256": H,
            "imageSha256": H, "exeSha256": H, "configSha256": H, "argvSha256": H,
            "generation": f"fixture-boot:pid-start:nonce-{i}", "contextSha256": H,
            "root": {"device": "fixture-dev", "inode": "fixture-inode", "filesystem": "ext4", "uid": 0, "mode": "0750", "sourceIdentitySha256": H, "guestBootId": "fixture-boot", "guestMountNamespace": "fixture-host-ns", "guestMountId": "123", "nodeMountNamespace": "fixture-node-ns", "nodeMountId": "456"},
            "peerFloorSha256": H, "storageFloorSha256": H}


def admission(i):
    props = SCHEMA["$defs"]["admission"]["properties"]
    a = {k: H if "Sha256" in k or k in ("servingCid", "servingNonce", "nonce") else f"fixture-{k}" for k in props}
    a.update(current=current(i), servingPid=123, servingUid=0, pidStartTicks=999,
             observedAt=NOW-1, expiresAt=NOW+60, peerP=9, storageC=9, storageR=1,
             role="workspace-storage-ro-v1", roleFloorSchema="saintvision-node-peer-policy-floor:3", bootId="fixture-boot")
    return a


def cohort():
    members = []
    for i in range(5):
        a = admission(i)
        members.append({"admission": a, "current": deepcopy(a["current"]), "frozenTarget": deepcopy(a["current"]),
                        "actualGeneration": a["current"]["generation"], "expectedFinalP": 9,
                        "nodeOnline": True, "publicNodeActive": True, "heartbeatFresh": True,
                        "contributionActive": True, "channelEnabled": True, "certificateTimeValid": True,
                        "grantCurrent": True, "assignmentCurrent": True, "latestPointerMatches": True,
                        "mockNodeSignatureValid": True, "mockHostProofValid": True,
                        "mockCASLedgerMatches": True, "extraFloorsVerifiedHistorical": True})
    return {"phase": "S9-released", "fenced": False, "actualCPClientBAllAdapters": True,
            "releaseCurrent": True, "epochCurrent": True, "mockNonceUnused": True, "members": members}


def eligible(c, selected=None):
    # All-five activation when selected=None; steady-state selected Nodes only.
    # Unrelated worker failure must not become a global ADR100 dependency.
    if (c["phase"] != "S9-released" or c["fenced"] or not c["actualCPClientBAllAdapters"]
            or not c["releaseCurrent"] or not c["epochCurrent"] or not c["mockNonceUnused"] or len(c["members"]) != 5):
        return False
    ids = [m["current"]["channel"]["node_id"] for m in c["members"]]
    if len(set(ids)) != 5:
        return False
    members = c["members"] if selected is None else [c["members"][i] for i in selected]
    for m in members:
        a, cur = m["admission"], m["current"]
        if not schema_ok("admission", a) or a["current"] != cur or cur != m["frozenTarget"]:
            return False
        if not all(m[k] for k in ("nodeOnline", "publicNodeActive", "heartbeatFresh", "contributionActive", "channelEnabled", "certificateTimeValid", "grantCurrent", "assignmentCurrent", "latestPointerMatches", "mockNodeSignatureValid", "mockHostProofValid", "mockCASLedgerMatches", "extraFloorsVerifiedHistorical")):
            return False
        if (not NOW-30 <= a["observedAt"] <= NOW or not NOW < a["expiresAt"] <= NOW+120
                or a["storageC"] != cur["channel"]["version"] or a["storageR"] != cur["rootVersion"]
                or a["peerP"] != m["expectedFinalP"] or a["policyBytesSha256"] != cur["policySha256"]
                or cur["generation"] != m["actualGeneration"] or a["bootId"] != cur["root"]["guestBootId"]):
            return False
    return True


def cas_replay(row, ledger, expected, target, operation):
    if row == expected and ledger is None:
        return "RETRY_EXACT_CAS"
    if row == target and ledger == {"operation": operation, "old": expected, "target": target}:
        return "REPLAY_CONFIRMED"
    return "BLOCK_UNKNOWN"


def pin_replay(peer, storage, config, expected_config, intent, expected_intent, complete):
    return (complete and config == expected_config and intent == expected_intent
            and (peer, storage) in ((8,8), (8,9), (9,9)))


def role_mounts(mounts):
    expected = [
        {"target":"/state","type":"volume","source":"fixture-owned-volume","rw":True,"propagation":"rprivate","nonrecursive":None},
        {"target":"/var/run/docker.sock","type":"bind","source":"/var/run/docker.sock","rw":True,"propagation":"rprivate","nonrecursive":None},
        {"target":"/contribution","type":"bind","source":"fixture-approved-linux-source","rw":False,"propagation":"rprivate","nonrecursive":True},
    ]
    return sorted(mounts,key=lambda m:m["target"]) == sorted(expected,key=lambda m:m["target"])


def workload_mounts(inspection):
    h=inspection["HostConfig"]
    return all(not h.get(k) for k in ("Binds","Mounts","VolumesFrom","Devices","PortBindings")) and not inspection.get("Mounts")


def main():
    Draft202012Validator.check_schema(SCHEMA)
    ctx = context()
    record_schema("native-context-positive", "executionContext", ctx, True)
    for value in ("windows-desktop", "drvfs", "9p", "desktop-remap", "unknown"):
        obj=deepcopy(ctx);obj["kind"]=value
        record_schema(f"context-kind-{value}-deny", "executionContext", obj, False)
    for field in ("nativeMountAncestryVerified", "noLinkParentsVerified", "sourceContained", "endpointProbeVerified", "hostToNodeRootVerified"):
        obj=deepcopy(ctx);obj[field]=False
        record_schema(f"context-{field}-deny", "executionContext", obj, False)
    for field,value in (("apiVersion","1.41"),("socketPath","/tmp/docker.sock"),("linux",False),("unknown",True)):
        obj=deepcopy(ctx);obj[field]=value
        record_schema(f"context-{field}-deny", "executionContext", obj, False)
    m={"schemaVersion":4,"role":"workspace-storage-ro-v1","executionProfile":"lan-workspace-v1","roleFloor":3,"normalLeafContract":4,"runtimeInventorySha256":H,"policySha256":H,"contextSha256":H,"baseServingArgvSha256":H,
       "roleArguments":["--serve","--storage-policy","/state/storage-policy.json","--socket","/var/run/docker.sock","--role-config","/state/node-role.json"]}
    record_schema("role-bindings-positive", "manifest", m, True)
    for args in (["-storage-policy","/state/node-storage.json"],["--storage-policy=/state/node-storage.json"],m["roleArguments"]+["--storage-policy","/state/node-storage.json"],["--serve","--contribution","/arbitrary"],m["roleArguments"]+["--unknown"]):
        obj=deepcopy(m);obj["roleArguments"]=args
        record_schema("role-option-alias-equal-duplicate-unknown-deny-"+str(len(CASES)),"manifest",obj,False)
    for field,value in (("schemaVersion",3),("roleFloor",2),("normalLeafContract",3),("role","workspace"),("allowStorage",True)):
        obj=deepcopy(m);obj[field]=value
        record_schema(f"role-binding-{field}-deny","manifest",obj,False)
    a=admission(0)
    record_schema("closed-admission-positive","admission",a,True)
    for field in a:
        obj=deepcopy(a);obj.pop(field)
        record_schema("admission-missing-"+field,"admission",obj,False)
    obj=deepcopy(a);obj["success"]=True
    record_schema("admission-independent-success-deny","admission",obj,False)
    config={"schemaVersion":"saintvision-node-role-config:1","role":"workspace-storage-ro-v1","executionContextSha256":H,"releaseAuthorityPublicKeySha256":H,"releaseAuthorityPublicKeyPath":"/state/role-release-authority.pub","roleUseProtocol":"saintvision-node-role-use:1","maxRoleUseSeconds":120,"operationId":"fixture-op","cohortId":"fixture-cohort","operatorApprovalRef":"fixture-approval"}
    record_schema("role-config-positive","roleConfig",config,True)
    for field,value in (("maxRoleUseSeconds",121),("releaseAuthorityPublicKeyPath","/tmp/key.pub"),("allowUnknown",True)):
        changed=deepcopy(config);changed[field]=value
        record_schema("role-config-"+field+"-deny","roleConfig",changed,False)
    use={"schemaVersion":"saintvision-node-role-use:1","releaseId":"fixture-release","admissionId":"fixture-admission","operationId":"fixture-op","cohortId":"fixture-cohort","channel":current(0)["channel"],"servingGeneration":"fixture-generation","roleConfigSha256":H,"policySha256":H,"purpose":"EXECUTION","method":"POST","path":"/v1/executions","requestBodySha256":H,"nonce":H,"issuedAt":NOW,"expiresAt":NOW+60}
    record_schema("role-use-positive","roleUse",use,True)
    for field,value in (("purpose","DIAGNOSTIC"),("purpose","STORAGE_COMMIT"),("method","GET"),("path","/v1/storage/sample"),("path","/v1/executions?override=1"),("success",True)):
        changed=deepcopy(use);changed[field]=value
        record_schema("role-use-"+field+"-deny-"+str(len(CASES)),"roleUse",changed,False)
    for purpose,path in (("TRANSFER","/v1/objects/read"),("TERMINAL","/v1/terminals/frame"),("STORAGE_COLLECT","/v1/storage/sample"),("MODEL","/v1/executions")):
        changed=deepcopy(use);changed.update(purpose=purpose,path=path)
        record_schema("role-purpose-path-positive-"+purpose,"roleUse",changed,True)
        changed["path"]="/v1/executions/receipts" if purpose!="MODEL" else "/v1/objects/read"
        record_schema("role-purpose-path-cross-deny-"+purpose,"roleUse",changed,False)
    token="v1.YWJj."+"a"*128
    record_schema("token-shape-positive-only","roleUseSignedToken",token,True)
    for name,token_value in (("alias",token.replace("v1.","v2.",1)),("duplicate-segment",token+".extra"),("padded",token.replace("YWJj","YWJj=")),("overlong","v1."+"a"*65536+"."+"a"*128)):
        record_schema("token-"+name+"-deny","roleUseSignedToken",token_value,False)
    for field,val in (("peerP",9007199254740992),("storageC",2147483648),("storageR",2147483648),("peerP",True)):
        obj=deepcopy(a);obj[field]=val
        record_schema(f"admission-bound-{field}-{val}","admission",obj,False)
    base=cohort()
    check("current-all-five-positive",eligible(base),True)
    c=deepcopy(base);c["members"][1]["nodeOnline"]=False
    check("offline-member-blocks-new-all-five-activation",eligible(c),False)
    check("offline-unselected-worker-does-not-block-healthy-worker",eligible(c,selected=[0]),True)
    check("offline-selected-worker-denied",eligible(c,selected=[1]),False)
    # Mount IDs intentionally differ across namespaces in the positive fixture.
    check("namespace-local-mount-ids-not-compared",base["members"][0]["current"]["root"]["guestMountId"] != base["members"][0]["current"]["root"]["nodeMountId"] and eligible(base),True)
    for key in ("nodeOnline", "publicNodeActive", "heartbeatFresh", "contributionActive", "channelEnabled", "certificateTimeValid", "grantCurrent", "assignmentCurrent", "latestPointerMatches", "mockNodeSignatureValid", "mockHostProofValid", "mockCASLedgerMatches", "extraFloorsVerifiedHistorical"):
        c=deepcopy(base);c["members"][0][key]=False
        check("current-join-"+key+"-deny",eligible(c),False)
    for field in ("policySha256","imageSha256","exeSha256","configSha256","argvSha256","generation","contextSha256","peerFloorSha256","storageFloorSha256"):
        c=deepcopy(base);c["members"][0]["current"][field]="changed"
        check("current-drift-"+field+"-deny",eligible(c),False)
    for field,value in (("version",10),("certificate_sha256","c"*64),("recovery_epoch","new-epoch"),("endpoint","https://other.invalid")):
        c=deepcopy(base);c["members"][0]["current"]["channel"][field]=value
        check("current-channel-"+field+"-deny",eligible(c),False)
    for field,value in (("rootVersion",2),("contributionId","other")):
        c=deepcopy(base);c["members"][0]["current"][field]=value
        check("current-root-"+field+"-deny",eligible(c),False)
    for field in ("device","inode","filesystem","uid","mode","sourceIdentitySha256","guestBootId"):
        c=deepcopy(base);c["members"][0]["current"]["root"][field]="changed"
        check("root-substitution-"+field+"-deny",eligible(c),False)
    for field,value in (("expiresAt",NOW),("observedAt",NOW-31),("observedAt",NOW+1),("peerP",8),("storageC",8),("storageR",2),("policyBytesSha256","c"*64)):
        c=deepcopy(base);c["members"][0]["admission"][field]=value
        check("stale-floor-proof-"+field+"-"+str(value),eligible(c),False)
    c=deepcopy(base);c["members"][0]["actualGeneration"]="new-process"
    check("old-release-after-restart-deny",eligible(c),False)
    for field in ("actualCPClientBAllAdapters","releaseCurrent","epochCurrent","mockNonceUnused"):
        c=deepcopy(base);c[field]=False
        check("cohort-"+field+"-deny",eligible(c),False)
    c=deepcopy(base);c["members"].pop()
    check("four-members-no-plain-PC5-fallback",eligible(c),False)
    c=deepcopy(base);c["members"][4]=deepcopy(c["members"][0])
    check("duplicate-node-deny",eligible(c),False)
    mounts=[{"target":"/state","type":"volume","source":"fixture-owned-volume","rw":True,"propagation":"rprivate","nonrecursive":None},
            {"target":"/var/run/docker.sock","type":"bind","source":"/var/run/docker.sock","rw":True,"propagation":"rprivate","nonrecursive":None},
            {"target":"/contribution","type":"bind","source":"fixture-approved-linux-source","rw":False,"propagation":"rprivate","nonrecursive":True}]
    check("exact-three-mounts-positive",role_mounts(mounts),True)
    for name,index,field,value in (("RW-contribution",2,"rw",True),("recursive-contribution",2,"nonrecursive",False),("shared-propagation",2,"propagation","shared"),("substituted-root",2,"source","other"),("alternate-socket",1,"source","/tmp/docker.sock"),("wrong-state-owner-volume",0,"source","other")):
        changed=deepcopy(mounts);changed[index][field]=value
        check(name,role_mounts(changed),False)
    check("extra-mount-deny",role_mounts(mounts+[deepcopy(mounts[2])]),False)
    check("missing-contribution-deny",role_mounts(mounts[:2]),False)
    inspect={"HostConfig":{"Binds":[],"Mounts":[],"VolumesFrom":[],"Devices":[],"PortBindings":{}},"Mounts":[]}
    check("workload-empty-host-mount-surfaces-positive",workload_mounts(inspect),True)
    for surface in ("Binds","Mounts","VolumesFrom","Devices","PortBindings","top-level-Mounts"):
        changed=deepcopy(inspect)
        if surface=="top-level-Mounts":changed["Mounts"]=[{"Source":"/contribution","Destination":"/workspace"}]
        else:changed["HostConfig"][surface]=["fixture-unauthorized-host-access"]
        check("workload-"+surface+"-deny",workload_mounts(changed),False)
    phases=json.loads((HERE/"phase-table.json").read_bytes())["phases"]
    for p in phases:
        if p["phase"] == "S9-released":continue
        c=deepcopy(base);c["phase"]=p["phase"];c["fenced"]=p["cohortFence"]
        check("phase-no-premature-readmission-"+p["phase"],eligible(c),False)
    old={"C":8,"DER":"A"};new={"C":9,"DER":"B"};ledger={"operation":"op","old":old,"target":new}
    for name,row,l,expected in (("before-CAS",old,None,"RETRY_EXACT_CAS"),("lost-reply-committed",new,ledger,"REPLAY_CONFIRMED"),("target-no-ledger",new,None,"BLOCK_UNKNOWN"),("old-with-ledger",old,ledger,"BLOCK_UNKNOWN"),("wrong-operation",new,{**ledger,"operation":"other"},"BLOCK_UNKNOWN"),("revoke-C-jump",{"C":10,"DER":"B"},ledger,"BLOCK_UNKNOWN")):
        check(name,cas_replay(row,l,old,new,"op"),expected)
    for name,p,s,cfg,intent,complete,expected in (("S4a-exact-forward",8,8,"B","op",True,True),("S4b-exact-replay",8,9,"B","op",True,True),("final-exact-replay",9,9,"B","op",True,True),("old-config",8,8,"A","op",True,False),("changed-intent",8,8,"B","other",True,False),("half-copy",8,8,"B","op",False,False),("before-copy",7,8,"B","op",True,False),("unknown-floor",9,8,"B","op",True,False)):
        check(name,pin_replay(p,s,cfg,"B",intent,"op",complete),expected)
    graph=json.loads((HERE/"caller-lock-graph.json").read_bytes())
    ranks={r["name"]:r["rank"] for r in graph["lockRanks"]}
    check("proposed-lock-DAG",all(ranks[a]<ranks[b] for a,b in graph["lockEdges"]),True,"SOURCE_STATIC_ONLY")
    check("channel-before-node-negative",ranks["shared_channels_sorted"]<ranks["inv_nodes_sorted"],False,"SOURCE_STATIC_ONLY")
    check("no-unclassified-source-occurrences",not graph["unclassified"] and all(h["classification"] for f in graph["files"] for h in f["hits"]),True,"SOURCE_STATIC_ONLY")
    CASES.append({"name":"all-five-current-model-positive","modelInput":base,"expected":True})
    (HERE/"synthetic-fixture-inputs.json").write_bytes((json.dumps({"warning":"SYNTHETIC SCHEMA/PREDICATE ONLY, NO REAL SIGNATURES OR SYSTEMS", "cases":CASES},indent=2)+"\n").encode())
    result={"schemaVersion":"fleet5-b-revision-fixture-result:2","python":sys.version,"level":"SCHEMA_SYNTHETIC_PREDICATE_AND_STATIC_SOURCE_ONLY","realGo":0,"realPG":0,"realDocker":0,"realPhysical":0,"cases":RESULTS,"passed":sum(x["passed"] for x in RESULTS),"failed":sum(not x["passed"] for x in RESULTS)}
    (HERE/"synthetic-fixture-results.json").write_bytes((json.dumps(result,indent=2)+"\n").encode())
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}))
    if result["failed"]:
        print(json.dumps([x for x in RESULTS if not x["passed"]]))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
