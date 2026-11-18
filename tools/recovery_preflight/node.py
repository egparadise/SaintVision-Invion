"""Local Linux collector. Run with python -B; descriptor and node ID arrive on stdin."""
import json
import os
import stat
import subprocess
import sys
from contextlib import ExitStack
from datetime import datetime, timezone
from common import Hold, decode, digest, now, report, require, scope

FLAGS=os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_NOATIME
PUBLIC={"config":("client-ca.pem","node-cert.pem","launch-signer.pub","peer-policy.json"),
        "state":("identity.json",".peer-policy")}


def retain(stack,fd):
    stack.callback(os.close,fd)
    return fd


def directory(path,stack):
    fd=retain(stack,os.open("/",FLAGS|os.O_DIRECTORY))
    for part in path.split("/")[1:]:
        fd=retain(stack,os.open(part,FLAGS|os.O_DIRECTORY,dir_fd=fd))
    st=os.fstat(fd)
    require(st.st_uid==1000 and st.st_mode&0o077==0,"DIRECTORY_CUSTODY_UNKNOWN")
    return fd


def mount(fd):
    with open("/proc/self/fdinfo/"+str(fd),"r",encoding="ascii") as handle:
        ids=[line.split()[1] for line in handle if line.startswith("mnt_id:")]
    require(len(ids)==1,"MOUNT_ID_UNKNOWN")
    return ids[0]


def metadata(st):
    return dict(uid=st.st_uid,mode=oct(stat.S_IMODE(st.st_mode)),dev=str(st.st_dev),
                ino=str(st.st_ino),nlink=st.st_nlink,size=st.st_size)


def identity(st):
    return st.st_dev,st.st_ino,st.st_mode,st.st_uid,st.st_nlink,st.st_size,st.st_mtime_ns,st.st_ctime_ns


def inspect(cid,label):
    # No interpolation of values other than a validated label key into the template.
    fields={"cid":".Id","image":".Image","pid":".State.Pid","started":".State.StartedAt",
            "running":".State.Running","user":".Config.User","executable":".Path","args":".Args",
            "owner":'index .Config.Labels "'+label+'"',"mounts":".Mounts",
            "readOnlyRoot":".HostConfig.ReadonlyRootfs","privileged":".HostConfig.Privileged",
            "capAdd":".HostConfig.CapAdd","capDrop":".HostConfig.CapDrop","security":".HostConfig.SecurityOpt"}
    fmt="\n".join("{{json ("+expr+")}}" for expr in fields.values())
    result=subprocess.run(["docker","--host","unix:///var/run/docker.sock","container","inspect",
                           "--format",fmt,cid],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=4,check=True)
    lines=result.stdout.splitlines()
    require(len(lines)==len(fields) and len(result.stdout)<=65536,"CONTAINER_METADATA_UNKNOWN")
    return dict(zip(fields,map(json.loads,lines)))


def cert_expired(value):
    return datetime.fromisoformat(value)<=datetime.now(timezone.utc)


def process_security(pid):
    # Numeric PID from exact CID; only four named public security fields leave this scope.
    require(type(pid) is int and pid>0,"PROCESS_UNKNOWN")
    with open(f"/proc/{pid}/status","rb") as f:
        lines=f.read(65537).splitlines()
    fields={k.decode():v.strip().decode("ascii") for line in lines
            for k,sep,v in [line.partition(b":")] if sep and k in (b"Uid",b"CapEff",b"CapBnd",b"NoNewPrivs")}
    require(set(fields)=={"Uid","CapEff","CapBnd","NoNewPrivs"} and fields["Uid"].split()==["1000"]*4
            and int(fields["CapEff"],16)==int(fields["CapBnd"],16)==0 and fields["NoNewPrivs"]=="1","PROCESS_PRIVILEGES_UNKNOWN")
    return fields


def gather(d,node,out):
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding
    member=d["nodes"][node]
    initial=inspect(member["cid"],d["ownerLabel"])
    require(initial["running"] and initial["pid"]>0 and initial["cid"]==member["cid"] and
            initial["image"]=="sha256:"+member["image"] and initial["owner"]==d["ownerValue"] and
            initial["user"] in ("1000","1000:1000") and [initial["executable"],*(initial["args"] or [])]==member["argv"],
            "CONTAINER_IDENTITY_UNKNOWN")
    require(initial["readOnlyRoot"] and not initial["privileged"] and not initial["capAdd"] and
            "ALL" in (initial["capDrop"] or []) and any(x in ("no-new-privileges","no-new-privileges=true")
            for x in (initial["security"] or [])),"CONTAINER_PRIVILEGES_UNKNOWN")
    mounts={m["Destination"]:m for m in initial["mounts"]}
    require(len(mounts)==len(initial["mounts"]) and set(mounts)=={"/config","/state"},"CONTAINER_MOUNT_UNKNOWN")
    for kind in PUBLIC:
        m=mounts["/"+kind]
        require(m["Type"]=="bind" and m["Source"]==member[kind] and m["RW"]==(kind=="state"),"CONTAINER_MOUNT_UNKNOWN")
    facts=out["facts"]
    facts.update(node=node,cid=initial["cid"],image=initial["image"],pid=initial["pid"],uid=initial["user"],
                 argvMatched=True,ownerMatched=True,readOnlyRoot=initial["readOnlyRoot"],
                 capDrop=initial["capDrop"],security=initial["security"],files={},directories={})
    facts["processSecurity"]=process_security(initial["pid"])
    raw={}
    with ExitStack() as stack:
        roots={kind:directory(member[kind],stack) for kind in PUBLIC}
        require(not os.path.samestat(os.fstat(roots["state"]),os.fstat(roots["config"])),"DIRECTORY_ALIAS")
        held={}
        for kind,root in roots.items():
            facts["directories"][kind]=dict(path=member[kind],bindRW=mounts["/"+kind]["RW"],**metadata(os.fstat(root)))
            for name in (*PUBLIC[kind], ("node-key.pem" if kind=="config" else ".lock")):
                public=name in PUBLIC[kind]
                flags=FLAGS if public else os.O_PATH|os.O_NOFOLLOW|os.O_CLOEXEC
                fd=retain(stack,os.open(name,flags,dir_fd=root))
                before=os.fstat(fd)
                require(stat.S_ISREG(before.st_mode) and before.st_uid==1000 and before.st_nlink==1 and
                        before.st_mode&0o077==0 and mount(root)==mount(fd),"FILE_CUSTODY_UNKNOWN")
                held[kind,name]=fd,identity(before)
                meta=metadata(before)
                facts["files"][name]=meta
                if public:
                    require(0<before.st_size<=65536,"PUBLIC_FILE_SIZE")
                    with os.fdopen(os.dup(fd),"rb") as reader:
                        value=reader.read(65537)
                    require(len(value)==before.st_size,"PUBLIC_FILE_CHANGED")
                    raw[name]=value
                    meta["sha256"]=digest(value)
                if name==".lock" and max(before.st_dev,before.st_ino)>2**53-1:
                    out["holds"].append("RECOVERY_HOLD_FILESYSTEM_NUMBER_RANGE")
        for name,key in (("client-ca.pem","ca"),("node-cert.pem","leaf")):
            cert=x509.load_pem_x509_certificate(raw[name])
            facts[key]={"derSHA256":digest(cert.public_bytes(Encoding.DER)),
                        "expiresAt":cert.not_valid_after_utc.isoformat()}
        require(facts["ca"]["derSHA256"]==d["caDER"],"CA_IDENTITY_UNKNOWN")
        if cert_expired(facts["ca"]["expiresAt"]):
            out["holds"].append("CA_TERMINAL")
        policy=decode(raw["peer-policy.json"])
        floor=decode(raw[".peer-policy"])
        ident=decode(raw["identity.json"])
        require(ident=={"Tenant":d["tenant"],"Node":node,"Epoch":d["epoch"]} and
                policy["tenantId"]==d["tenant"] and policy["nodeId"]==node and policy["recoveryEpoch"]==d["epoch"]
                and policy["clientFingerprints"]==[d["cpDER"]],"NODE_SCOPE_UNKNOWN")
        require(type(policy["version"]) is int and 0<policy["version"]<2**53 and
                floor=={"Hash":digest(raw["peer-policy.json"]),"Version":policy["version"]},"POLICY_FLOOR_UNKNOWN")
        require(len(raw["launch-signer.pub"])==32,"LAUNCH_SIGNER_UNKNOWN")
        facts["policy"]={"P":policy["version"],"expiresAt":policy["expiresAt"],"cpDER":d["cpDER"]}
        require(process_security(initial["pid"])==facts["processSecurity"] and inspect(member["cid"],d["ownerLabel"])==initial,"CONTAINER_CHANGED")
        for kind,root in roots.items():
            check=directory(member[kind],stack)
            require(os.path.samestat(os.fstat(root),os.fstat(check)) and mount(root)==mount(check),"DIRECTORY_CHANGED")
        for (kind,name),(fd,before) in held.items():
            check=retain(stack,os.open(name,os.O_PATH|os.O_NOFOLLOW,dir_fd=roots[kind]))
            require(identity(os.fstat(fd))==identity(os.fstat(check))==before and mount(fd)==mount(check),"FILE_CHANGED")
    for key,code in (("ca","CA_TERMINAL"),("leaf","LEAF_EXPIRED"),("policy","POLICY_EXPIRED")):
        expiry=datetime.fromisoformat(facts[key]["expiresAt"].replace("Z","+00:00"))
        if expiry<=datetime.now(timezone.utc):
            if code not in out["holds"]:
                out["holds"].append(code)
    out["observationComplete"]=True


def main():
    out={"recoveryReady":False,"activationAllowed":False,"release":False,"observationComplete":False,"holds":[]}
    try:
        inp=decode(sys.stdin.buffer.read(65537))
        d=scope(inp["descriptor"])
        out=report(d,"node")
        out["holds"].extend(["KEY_CONTINUITY_UNKNOWN","QUIESCENT_STAGE_REQUIRED"])
        gather(d,inp["node"],out)
    except Exception as err:
        out["holds"].append(str(err) if isinstance(err,Hold) else "NODE_OBSERVATION_UNKNOWN")
    out["observedAt"]=now()
    print(json.dumps(out))
    return 0 if out["observationComplete"] else 2


if __name__=="__main__":
    sys.exit(main())
