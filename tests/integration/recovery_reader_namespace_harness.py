"""Root-only harness: run the unmodified cp.provisioned_reader() path in a private mount namespace.

Started by tests/integration/test_recovery_cohort_preflight.py as
``sudo -n unshare --mount --propagation private -- python -I -B <this file>``.
The spec arrives on stdin (the database connection string never appears in argv).

The harness connects first, then bind-mounts a freshly built fixture directory
over /etc *inside its own mount namespace only*, so the collector opens the real
"/" and walks the real fixed path etc/saintvision/recovery-reader.json, with no
path override and no change to the collector. The host /etc is never written.
One case per process: the namespace and the fixture disappear when it exits.
"""
import ctypes
import json
import os
import shutil
import stat
import sys
import tempfile

MS_BIND = 4096
NOBODY = 65534


def build(root, case):
    """Lay out <root>/etc/saintvision/recovery-reader.json for one case."""
    etc = os.path.join(root, "etc")
    sv = os.path.join(etc, "saintvision")
    target = os.path.join(sv, "recovery-reader.json")
    os.mkdir(etc, 0o755)
    kind = case["kind"]
    content = None if case["content"] is None else case["content"].encode()

    def regular(path, mode=0o644, owner=0):
        with open(path, "wb") as handle:
            handle.write(content)
        os.chown(path, owner, 0)
        os.chmod(path, mode)

    if kind == "dir-symlink":
        real = os.path.join(root, "real-saintvision")
        os.mkdir(real, 0o755)
        regular(os.path.join(real, "recovery-reader.json"))
        os.symlink(real, sv)
    elif kind != "missing-dir":
        os.mkdir(sv, 0o755)
    if kind == "regular":
        regular(target, case.get("fileMode", 0o644), case.get("fileOwner", 0))
    elif kind == "symlink":
        real = os.path.join(root, "real-recovery-reader.json")
        regular(real)
        os.symlink(real, target)
    elif kind == "hardlink":
        regular(target)
        os.link(target, os.path.join(sv, "second-name.json"))
    elif kind == "fifo":
        os.mkfifo(target, 0o644)
    elif kind == "directory":
        os.mkdir(target, 0o755)
    if kind not in ("missing-dir", "dir-symlink"):
        os.chown(sv, case.get("dirOwner", 0), 0)
        os.chmod(sv, case.get("dirMode", 0o755))
    os.chown(etc, case.get("etcOwner", 0), 0)
    os.chmod(etc, case.get("etcMode", 0o755))
    return etc


def bind_over_etc(source):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.mount.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_void_p)
    libc.mount.restype = ctypes.c_int
    if libc.mount(source.encode(), b"/etc", None, MS_BIND, None) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), "/etc")


def main():
    if os.geteuid() != 0:
        raise SystemExit("harness requires root inside a private mount namespace")
    spec = json.loads(sys.stdin.buffer.read())
    sys.path.insert(0, spec["toolDir"])
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import psycopg
    from cp import observe
    from common import Hold
    from recovery_guard_trace import TracingConnection, attribute

    # Never bind over the host /etc: refuse unless this mount namespace differs from PID 1's.
    if os.stat("/proc/self/ns/mnt").st_ino == os.stat("/proc/1/ns/mnt").st_ino:
        raise SystemExit("harness is not in a private mount namespace")
    case = spec["case"]
    root = tempfile.mkdtemp(prefix="sv-reader-root-")
    result = {"case": case["name"], "complete": False, "code": None, "guard": None, "guardRows": None}
    try:
        etc = build(root, case)
        with psycopg.connect(spec["connection"], autocommit=True, connect_timeout=4) as db:
            db.execute("SELECT set_config('inv.tenant_id',%s,false)", (spec["tenant"],))
            bind_over_etc(etc)
            probe = os.stat("/etc", follow_symlinks=False)
            result["etcFixture"] = {"uid": probe.st_uid, "mode": oct(stat.S_IMODE(probe.st_mode)),
                                    "sameInode": probe.st_ino == os.stat(etc).st_ino}
            traced = TracingConnection(db)
            out = {"facts": {}, "holds": []}
            try:
                observe(traced, spec["descriptor"], out)
                result["complete"] = True
                facts = out["facts"]
                result["observed"] = {
                    "transactionReadOnly": facts["transactionReadOnly"],
                    "assignedTransactionID": facts["assignedTransactionID"],
                    "transactionTupleChanges": facts["transactionTupleChanges"],
                    "channelMembers": sorted(facts["channels"]),
                    "obligations": facts["obligations"],
                    "holds": out["holds"],
                }
            except Hold as refused:
                result["code"] = str(refused)
                result["guard"], result["guardRows"] = attribute(refused, traced.trace)
                result["facts"] = out["facts"]
            finally:
                db.execute("ROLLBACK")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
