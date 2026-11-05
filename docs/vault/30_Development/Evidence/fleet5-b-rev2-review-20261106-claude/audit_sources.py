"""Independent reviewer audit of B rev2 source claims against exact Git objects.

Usage: python -I audit_sources.py <repo> <evidence_dir> <out_json>
Reads only Git objects (no checkout) and the owner evidence JSON as data.
"""
import hashlib, json, re, subprocess, sys, collections

REPO, EV, OUT = sys.argv[1:4]
BASE = "72028cbac903c4415d9979f980a6e0f9948e914f"
FOURF = "4f97ba71"
ORIG = "100f6f132132199d1204a76190f04712dd82de00"
REV2 = "02cfd260437e1d592cb4bf67e5d6764c4260363a"


def git(*a, check=True):
    r = subprocess.run(["git", "-C", REPO, *a], capture_output=True)
    if check and r.returncode:
        raise SystemExit(f"git {a} -> {r.returncode}: {r.stderr[:300]!r}")
    return r


def blob(rev, path):
    r = git("cat-file", "blob", f"{rev}:{path}", check=False)
    return r.stdout if r.returncode == 0 else None


def sha(b):
    return hashlib.sha256(b).hexdigest() if b is not None else None


def load(name):
    with open(f"{EV}/{name}", encoding="utf-8-sig") as f:
        return json.load(f)


res = {"base": BASE, "rev2": REV2}
fourf = git("rev-parse", FOURF).stdout.decode().strip()
res["fourF"] = fourf

# A. 46 surfaces
inv = load("source-inventory-72028.json")
a = {"count": len(inv["files"]), "shaMismatch": [], "not4f": [], "notOrig": [], "rev2Changed": [],
     "anchorTotal": 0, "anchorExact": 0, "anchorStripOnly": 0, "anchorBad": []}
for f in inv["files"]:
    p = f["path"]
    b = blob(BASE, p)
    if sha(b) != f["sha256"]:
        a["shaMismatch"].append(p)
    if sha(blob(fourf, p)) != sha(b):
        a["not4f"].append(p)
    if sha(blob(ORIG, p)) != sha(b):
        a["notOrig"].append(p)
    if sha(blob(REV2, p)) != sha(b):
        a["rev2Changed"].append(p)
    lines = b.decode("utf-8", "replace").split("\n") if b else []
    for an in f.get("anchors", []):
        a["anchorTotal"] += 1
        ok = False
        for ln in an.get("currentLines", []):
            if 1 <= ln <= len(lines):
                cur = lines[ln - 1].rstrip("\r")
                if cur == an["text"]:
                    a["anchorExact"] += 1; ok = True; break
                if cur.strip() == an["text"].strip():
                    a["anchorStripOnly"] += 1; ok = True; break
        if not ok:
            a["anchorBad"].append([p, an.get("oldLine"), an["text"][:80]])
res["surfaces46"] = a

# B. 11 additional bindings
add = load("additional-contract-bindings.json")
res["bindings"] = {"count": len(add["additionalSurfaces"]),
                   "shaMismatch": [s["path"] for s in add["additionalSurfaces"]
                                   if sha(blob(BASE, s["path"])) != s["sha256"]],
                   "overlapWith46": sorted({s["path"] for s in add["additionalSurfaces"]} & {f["path"] for f in inv["files"]})}

# C. independent lexical census
g = load("caller-lock-graph.json")
roots = g["scanRoots"]
direct_re = g["directRegex"]
related_re = g["relatedRegex"]


def grep_l(regex):
    r = git("grep", "-l", "-I", "-E", regex, BASE, "--", *roots, check=False)
    out = set()
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        out.add(line.split(":", 1)[1])
    return out

mine_direct = grep_l(direct_re)
mine_related = grep_l(related_re)
graph_paths = {f["path"]: f for f in g["files"]}
direct_in_graph = {p for p, f in graph_paths.items() if any(h.get("kind", "").startswith("DIRECT") for h in f.get("hits", []))}
kinds = collections.Counter(h.get("kind") for f in g["files"] for h in f.get("hits", []))
res["census"] = {
    "graphFiles": len(graph_paths), "graphKinds": dict(kinds),
    "graphDirectByKind": len(direct_in_graph), "mineDirect": len(mine_direct), "mineRelated": len(mine_related),
    "mineUnion": len(mine_direct | mine_related),
    "directMissingFromGraph": sorted(mine_direct - set(graph_paths)),
    "relatedMissingFromGraph": sorted(mine_related - set(graph_paths)),
    "graphNotInMineUnion": sorted(set(graph_paths) - (mine_direct | mine_related)),
    "directKindSetDiff_mineMinusGraph": sorted(mine_direct - direct_in_graph),
    "directKindSetDiff_graphMinusMine": sorted(direct_in_graph - mine_direct),
    "graphShaMismatch": sorted(p for p, f in graph_paths.items() if sha(blob(BASE, p)) != f.get("sha256")),
    "unclassifiedHits": sum(1 for f in g["files"] for h in f.get("hits", []) if not h.get("classification")),
}
cen = load("source-channel-census.json")
cen_paths = {f["path"] for f in cen["files"]}
res["census"]["narrowCensusFiles"] = len(cen_paths)
res["census"]["narrowCensusNotInGraph"] = sorted(cen_paths - set(graph_paths))
res["census"]["narrowCensusShaMismatch"] = sorted(f["path"] for f in cen["files"] if sha(blob(BASE, f["path"])) != f["sha256"])

# D. original 2bb B2 caller list classification
b2 = ["services/control-plane/src/inv/placement.py", "services/control-plane/src/inv/capacity.py",
      "services/control-plane/src/inv/gpu.py", "services/control-plane/src/inv/node_resource_usage.py",
      "services/control-plane/src/inv/containment.py", "services/control-plane/src/inv/observer_worker.py",
      "services/control-plane/src/inv/node_execution.py", "services/control-plane/src/inv/node_transfer.py",
      "services/control-plane/src/inv/terminal.py", "services/control-plane/src/inv/model_source.py",
      "services/control-plane/src/inv/model_runtime.py", "services/control-plane/src/inv/storage_commit.py",
      "services/control-plane/src/inv/storage_check_collect.py", "tools/check_lan_storage_readiness.py",
      "tools/five_node_lab_preflight.py"]
res["b2Callers"] = {p: (graph_paths[p]["classification"] if p in graph_paths else "ABSENT_FROM_GRAPH") for p in b2}

# E. transitive NodeClient / channel-consuming business entry points not lexically hit
tr = grep_l(r"NodeClient\(|node_client|\.snapshot\(|capture_channels|frozen_sources")
res["transitiveCandidatesNotInGraph"] = sorted(p for p in tr - set(graph_paths)
                                               if p.endswith((".py", ".go")) and "/tests/" not in p and not p.startswith("tests/"))

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(res, f, indent=2, ensure_ascii=False)
print(json.dumps({k: (v if k not in ("census",) else {kk: vv for kk, vv in v.items()}) for k, v in res.items()}, ensure_ascii=False)[:6000])
