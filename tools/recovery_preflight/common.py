"""Read-only preflight input and output contracts. No ambient discovery."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath

API_SOURCE = "96afd799d49717fd40e4ddabd538d82accbe1958"
SCHEMA = "0068_first_workspace_intent"


class Hold(ValueError):
    pass


def require(value, code):
    if not value:
        raise Hold(code)


def now():
    return datetime.now(timezone.utc).isoformat()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_FIELD")
        result[key] = value
    return result


def decode(raw):
    require(len(raw) <= 65536, "INPUT_LIMIT")
    return json.loads(raw, object_pairs_hook=unique)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def scope(d):
    require(set(d) == {"schema", "sourceSHA", "tenant", "epoch", "project", "nodes", "caDER", "cpDER",
                       "ownerLabel", "ownerValue", "databaseRole", "maxAgeSeconds"}, "DESCRIPTOR_SHAPE")
    require(d["schema"] == "sv-readonly-cohort:1" and re.fullmatch("[0-9a-f]{40}", d["sourceSHA"]), "DESCRIPTOR_VERSION")
    require(all(re.fullmatch("[0-9a-f]{64}", d[k]) for k in ("caDER", "cpDER")), "DESCRIPTOR_CERTIFICATES")
    import uuid
    for key in ("tenant", "epoch"):
        require(str(uuid.UUID(d[key])) == d[key], "DESCRIPTOR_SCOPE")
    require(re.fullmatch("prj_[0-9A-HJKMNP-TV-Z]{26}", d["project"]), "DESCRIPTOR_PROJECT")
    require(type(d["maxAgeSeconds"]) is int and 0 < d["maxAgeSeconds"] <= 300, "DESCRIPTOR_AGE")
    require(re.fullmatch("[a-zA-Z0-9_.-]{1,100}", d["ownerLabel"]) and
            re.fullmatch("[a-zA-Z0-9_.-]{1,100}", d["ownerValue"]), "DESCRIPTOR_LABEL")
    require(re.fullmatch("[a-zA-Z_][a-zA-Z0-9_]{0,62}", d["databaseRole"]), "DESCRIPTOR_ROLE")
    require(type(d["nodes"]) is dict and len(d["nodes"]) == 3, "DESCRIPTOR_MEMBERS")
    for node, member in d["nodes"].items():
        require(re.fullmatch("nod_[0-9A-HJKMNP-TV-Z]{26}", node), "DESCRIPTOR_MEMBER")
        require(set(member) == {"cid","image","config","state","argv"}, "DESCRIPTOR_MEMBER_SHAPE")
        require(all(re.fullmatch("[0-9a-f]{64}",member[k]) for k in ("cid","image")), "DESCRIPTOR_IMAGE")
        require(type(member["argv"]) is list and 0 < len(member["argv"]) <= 64 and
                all(type(arg) is str and len(arg) <= 512 for arg in member["argv"]), "DESCRIPTOR_ARGV")
        for key in ("config","state"):
            p=PurePosixPath(member[key])
            require(p.is_absolute() and len(p.parts)>1 and p.parts[0]=="/" and ".." not in p.parts and str(p)==member[key], "DESCRIPTOR_PATH")
        require(member["config"] != member["state"], "DESCRIPTOR_PATH")
    require(len({m["cid"] for m in d["nodes"].values()})==3,"DESCRIPTOR_MEMBERS")
    return d


def report(d, kind):
    return {"schema":"sv-readonly-observation:1","sourceSHA":d["sourceSHA"],"apiSource":API_SOURCE,
            "descriptorSHA256":digest(json.dumps(d,sort_keys=True,separators=(",",":")).encode()),
            "source":kind,"startedAt":now(),"observedAt":None,"observationComplete":False,
            "recoveryReady":False,"activationAllowed":False,"release":False,"facts":{},"holds":[]}
