"""Follow-up: scoped dummy signer mapping (V4-I2) with trace-derived event scope and
proof-reference role/scope policy check; analyse the 342 signer-swap negatives.
Usage: python -I -B v5_signer.py <v5_dir> <out_json>
Imports reviewer v5_check helpers by path only for C2/digest/regen (no owner code).
"""
import collections, copy, importlib.util, json, re, sys
V5, OUT = sys.argv[1:3]
here = sys.argv[0].rsplit("/", 1)[0] if "/" in sys.argv[0] else "."

def load(n):
    with open(f"{V5}/{n}", "rb") as f:
        return json.loads(f.read().decode("utf-8"))

nodes = load("scenario-objects.json")["nodes"]
graph = load("artifact-reference-graph.json")
pol = load("dummy-signer-policy.json")
cov = load("reference-graph-coverage.json")
trace = {t["event"]: t for t in graph["trace"]}
R = {"roleKeyNames": sorted(pol["roleKeys"])}

def scope(nid):
    m = re.search(r"-(PC2|PC4)$", nid)
    if m: return m.group(1)
    if nid in trace and trace[nid]["slot"]: return trace[nid]["slot"]
    return "COHORT"

mis = []
for nid, n in nodes.items():
    if "signer" not in n["payload"]: continue
    s = n["payload"]["signer"]
    want = pol["roleKeys"].get(f"{s['role']}@{scope(nid)}")
    if want != s["keySPKISHA256"] or pol["artifactAssignments"].get(nid) != s:
        mis.append([nid, s["role"], scope(nid), want is not None])
R["outerSignerScopeMismatchTraceScope"] = mis
R["outerRoleScopeCounts"] = dict(collections.Counter(f"{n['payload']['signer']['role']}@{scope(k)}" for k, n in nodes.items() if "signer" in n["payload"]))

def ptr(o, p):
    for x in p.split("/")[1:]:
        o = o[int(x)] if isinstance(o, list) else o[x]
    return o

pm = []
for r in cov["structuredProofReferences"]:
    pr = ptr(nodes[r["node"]]["payload"], r["pointer"])
    want = pol["roleKeys"].get(f"{pr['signerRole']}@{r['scope']}")
    if want != pr["signerKeySPKISHA256"] or pr["signerRole"] != r["role"]:
        pm.append([r["node"], r["pointer"], pr["signerRole"], r["scope"], want is not None])
R["proofRefRoleScopeMismatch"] = pm
R["proofRefRoleScopes"] = dict(collections.Counter(f"{r['role']}@{r['scope']}" for r in cov["structuredProofReferences"]))

# signer-swap negatives: does each swapped value violate the role@scope policy?
cases = load("dummy-signer-swap-negative-fixtures.json")["cases"]
proofptr = {(r["node"], r["pointer"]): r for r in cov["structuredProofReferences"]}
res = collections.Counter(); notpolicy = []
for c in cases:
    nid, p, v = c["node"], c["pointer"], c["value"]
    if p.startswith("/signer/"):
        s = dict(nodes[nid]["payload"]["signer"]); s[p.split("/")[-1]] = v
        ok = pol["roleKeys"].get(f"{s['role']}@{scope(nid)}") == s["keySPKISHA256"]
        kind = "outer-" + p.split("/")[-1]
    else:
        base = p.rsplit("/", 1)[0]
        r = proofptr.get((nid, base))
        pr = dict(ptr(nodes[nid]["payload"], base)); pr[p.rsplit("/", 1)[1]] = v
        ok = r is not None and pol["roleKeys"].get(f"{pr['signerRole']}@{r['scope']}") == pr["signerKeySPKISHA256"]
        kind = "proof-ref-key"
    res[(kind, "violatesPolicy" if not ok else "STILL_POLICY_VALID")] += 1
    if ok: notpolicy.append([nid, p])
    # is the swapped value another real key of the same role (Node swap) or a different role key?
R["swapPolicyClassification"] = {f"{a}:{b}": n for (a, b), n in res.items()}
R["swapsStillPolicyValid"] = notpolicy[:20]
# what swapped keys are: cross-Node same role / other role
kinds = collections.Counter()
inv = {v: k for k, v in pol["roleKeys"].items()}
for c in cases:
    if c["pointer"].endswith("keySPKISHA256") or c["pointer"].endswith("signerKeySPKISHA256"):
        kinds[(inv.get(c["value"], "NOT_A_POLICY_KEY").split("@")[1] if "@" in inv.get(c["value"], "") else "NOT_A_POLICY_KEY")] += 1
R["swappedKeyTargetScopes"] = dict(kinds)
R["cases"] = len(cases)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(R, f, indent=1)
print(json.dumps(R)[:5000])
