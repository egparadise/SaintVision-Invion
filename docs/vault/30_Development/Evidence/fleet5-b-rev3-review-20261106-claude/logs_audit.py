"""Re-hash every log path/sha256 pair recorded in the rev3 evidence against committed git blob bytes."""
import hashlib
import json
import subprocess
import sys

repo, sha = sys.argv[1], sys.argv[2]
D = "docs/vault/30_Development/Evidence/fleet5-b-contract-rev3-20261106-codex/"

def blob(path):
    return subprocess.check_output(["git", "show", sha + ":" + path], cwd=repo)

pairs = []
def walk(x, src):
    if isinstance(x, dict):
        log = x.get("log") or x.get("rawLog")
        h = x.get("sha256") or x.get("rawLogSHA256") or x.get("logSha256")
        if isinstance(log, str) and isinstance(h, str):
            pairs.append((src, log if log.startswith("docs/") else D + log, h))
        for v in x.values():
            walk(v, src)
    elif isinstance(x, list):
        for v in x:
            walk(v, src)

names = subprocess.check_output(["git", "ls-tree", "--name-only", sha, D], cwd=repo).decode().split()
for n in names:
    if n.endswith(".json"):
        walk(json.loads(blob(n)), n.rsplit("/", 1)[-1])
seen = {}
for src, log, h in pairs:
    actual = hashlib.sha256(blob(log)).hexdigest()
    seen.setdefault(log, []).append({"recordedIn": src, "match": actual == h})
logs = [n for n in names if n.endswith(".log")]
init = json.loads(blob(D + "initial-fixture-red.json"))
fails = [c for c in init.get("cases", []) if not c.get("passed", True)] if isinstance(init, dict) else []
print(json.dumps({
    "commit": sha,
    "logFilesInDir": len(logs),
    "logsWithRecordedHash": len(seen),
    "allRecordedHashesMatch": all(r["match"] for v in seen.values() for r in v),
    "logsWithoutRecordedHash": sorted(set(logs) - set(seen)),
    "perLog": seen,
    "initialFixtureRed": {k: init[k] for k in ("passed", "failed") if k in init},
    "initialFixtureRedFailedNames": [c.get("name") for c in fails],
}, indent=1))
