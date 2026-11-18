"""Join public observations from a single descriptor and bounded observation window."""
import json
import sys
from datetime import datetime, timezone
from common import Hold, decode, now, report, require, scope


def join(d, observations):
    out=report(d,"cohort")
    try:
        require(len(observations)==4,"OBSERVATIONS_MISSING")
        at=datetime.now(timezone.utc)
        sources={}
        for item in observations:
            require(item["schema"]==out["schema"] and item["descriptorSHA256"]==out["descriptorSHA256"]
                    and item["sourceSHA"]==out["sourceSHA"] and item["apiSource"]==out["apiSource"]
                    and all(item[k] is False for k in ("recoveryReady","activationAllowed","release")),"FOREIGN_EVIDENCE")
            start=datetime.fromisoformat(item["startedAt"])
            end=datetime.fromisoformat(item["observedAt"])
            require(start<=end<=at and (at-start).total_seconds()<=d["maxAgeSeconds"],"STALE_EVIDENCE")
            key=("node",item["facts"]["node"]) if item["source"]=="node" else (item["source"],None)
            require(key not in sources,"DUPLICATE_SOURCE")
            sources[key]=item
            out["holds"].extend(item["holds"])
            require(item["observationComplete"] is True,"INCOMPLETE_SOURCE")
        rows=sources["control-plane",None]["facts"]["channels"]
        require(set(rows)==set(d["nodes"]),"CHANNEL_COHORT_UNKNOWN")
        members={}
        for node,member in d["nodes"].items():
            facts=sources["node",node]["facts"]
            ch=rows[node]
            require(facts["cid"]==member["cid"] and facts["image"]=="sha256:"+member["image"] and
                    facts["ca"]["derSHA256"]==d["caDER"] and facts["policy"]["cpDER"]==d["cpDER"] and
                    facts["leaf"]["derSHA256"]==ch["leafDER"] and
                    datetime.fromisoformat(facts["leaf"]["expiresAt"])==datetime.fromisoformat(ch["expiresAt"]),
                    "AUTHORITY_SCOPE_MISMATCH")
            for source,code in (("ca","CA_TERMINAL"),("leaf","LEAF_EXPIRED"),("policy","POLICY_EXPIRED")):
                if datetime.fromisoformat(facts[source]["expiresAt"].replace("Z","+00:00"))<=datetime.now(timezone.utc):
                    out["holds"].append(code)
            members[node]={"P":facts["policy"]["P"],"C":ch["C"],"leafDER":ch["leafDER"]}
        out["facts"]["members"]=members
        out["observationComplete"]=True
    except Exception as err:
        out["holds"].append(str(err) if isinstance(err,Hold) else "OBSERVATION_UNKNOWN")
    out["holds"]=sorted(set(out["holds"]+["B_RPOLICY_UNBOUND","OPERATION_OUTCOME_UNKNOWN","RELEASE_UNBOUND"]))
    out["observedAt"]=now()
    return out


if __name__=="__main__":
    try:
        data=decode(sys.stdin.buffer.read(65537))
        result=join(scope(data["descriptor"]),data["observations"])
    except Exception:
        result={"observedAt":now(),"observationComplete":False,"recoveryReady":False,"activationAllowed":False,
                "release":False,"holds":["DESCRIPTOR_UNKNOWN"]}
    print(json.dumps(result))
    sys.exit(0 if result["observationComplete"] else 2)
