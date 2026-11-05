"""Staleness check of proof typedSubject digests after the v4->v5 context change.
Usage: python -I -B v5_stale.py <v5_dir> <v4_dir> <out_json>
Every 64-hex value inside a proof typedSubject is classified as a current v5 node
digest, a v4-only node digest (STALE), or a non-node value (input fact / readback id).
"""
import collections, json, re, sys
V5, V4, OUT = sys.argv[1:4]
def load(d, n):
    with open(f"{d}/{n}", "rb") as f:
        return json.loads(f.read().decode("utf-8"))
n5 = load(V5, "scenario-objects.json")["nodes"]; n4 = load(V4, "scenario-objects.json")["nodes"]
d5 = {n["sha256"]: k for k, n in n5.items()}; d4 = {n["sha256"]: k for k, n in n4.items()}
HEX = re.compile(r"^[0-9a-f]{64}$")
cls = collections.Counter(); stale = []; subj = 0
def walk(v, nid, p, inproof):
    global subj
    if isinstance(v, dict):
        isp = "slotId" in v and "contractId" in v and "signatureDomainASCII" in v
        for k, x in v.items():
            walk(x, nid, p + "/" + k, inproof or (isp and k == "typedSubject"))
    elif isinstance(v, list):
        for i, x in enumerate(v): walk(x, nid, p + "/" + str(i), inproof)
    elif inproof and isinstance(v, str) and HEX.match(v):
        subj += 1
        if v in d5: cls["currentV5Node:" + n5[d5[v]]["kind"]] += 1
        elif v in d4: cls["STALE_v4_only:" + n4[d4[v]]["kind"]] += 1; stale.append([nid, p, d4[v]])
        else: cls["nonNodeValue"] += 1
for k, n in n5.items(): walk(n["payload"], k, "", False)
R = {"typedSubjectHexValues": subj, "classes": dict(cls), "stale": stale[:20],
     "v4NodeDigestsStillCurrent": len(set(d4) & set(d5))}
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(R, f, indent=1)
print(json.dumps(R))
