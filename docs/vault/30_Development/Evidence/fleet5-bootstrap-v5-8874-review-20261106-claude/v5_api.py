"""Follow-up: API:2 prior refs vs trace, object order, HOLD nulls, registry mentions.
Usage: python -I -B v5_api.py <v5_dir> <out_json>
"""
import collections, json, sys
V5, OUT = sys.argv[1:3]
def load(n):
    with open(f"{V5}/{n}", "rb") as f:
        return json.loads(f.read().decode("utf-8"))
nodes = load("scenario-objects.json")["nodes"]
graph = load("artifact-reference-graph.json")
trace = graph["trace"]
R = {}
first = {}
for t in trace:
    first.setdefault(t["request"], t)
reqs = [k for k, n in nodes.items() if n["kind"] == "api-request"]
errs = []; kinds = collections.Counter()
for k in reqs:
    p = nodes[k]["payload"]; t = first[k]; s = t["sequence"]
    node_ref, coh_ref = p["expectedNodeProjectionEnvelopeSHA256"], p["expectedCohortProjectionSetDigestSHA256"]
    if t["slot"]:
        kinds["member"] += 1
        want = nodes[f"projection-{s-1:02d}-{t['slot']}"]["sha256"] if s > 1 else None
        if node_ref != want or coh_ref is not None: errs.append([k, "member", s])
    else:
        kinds["cohort"] += 1
        want = nodes[f"cohort-{s-1:02d}"]["sha256"] if s > 1 else None
        if coh_ref != want or node_ref is not None: errs.append([k, "cohort", s])
    if nodes[f"projection-{max(s-1,1):02d}-PC2"]["kind"] != "migration-journal": errs.append([k, "kind"])
    # epoch and lease of the request must be the active lease at s
    L = nodes[t["activeLease"]]["payload"]["body"]
    if p["expectedFenceEpoch"] != L["fenceEpoch"] or p["operationId"] != L["operationId"]: errs.append([k, "epoch/op", s])
R["requests"] = {"count": len(reqs), "kinds": dict(kinds), "errors": errs,
                 "genesisNoPrior": [k for k in reqs if first[k]["sequence"] == 1]}
rs = [k for k, n in nodes.items() if n["kind"] == "api-response"]
rerr = []
for k in rs:
    p = nodes[k]["payload"]
    if p["sideEffectPermitted"] is not False: rerr.append([k, "sideEffect"])
    if p["nodeProjectionEnvelopeSHA256"] is not None and p["cohortProjectionSetDigestSHA256"] is not None: rerr.append([k, "both"])
    for f, kind in (("nodeProjectionEnvelopeSHA256", "migration-journal"), ("cohortProjectionSetDigestSHA256", "cohort-projection-set")):
        if p[f] is not None:
            hit = [x for x, n in nodes.items() if n["sha256"] == p[f]]
            if not hit or nodes[hit[0]]["kind"] != kind: rerr.append([k, f])
R["responses"] = {"count": len(rs), "errors": rerr,
                  "nodeRef": sum(nodes[k]["payload"]["nodeProjectionEnvelopeSHA256"] is not None for k in rs),
                  "cohortRef": sum(nodes[k]["payload"]["cohortProjectionSetDigestSHA256"] is not None for k in rs)}
# journals never reference a derived digest
dset = {n["sha256"] for n in nodes.values() if n["kind"] == "cohort-projection-set"}
def vals(v, acc):
    if isinstance(v, dict):
        for x in v.values(): vals(x, acc)
    elif isinstance(v, list):
        for x in v: vals(x, acc)
    elif isinstance(v, str): acc.add(v)
    return acc
R["derivedDigestReferencedBy"] = dict(collections.Counter(n["kind"] for n in nodes.values() if vals(n["payload"], set()) & dset))
# object order topological?
order = list(nodes)
pos = {k: i for i, k in enumerate(order)}
deps = collections.defaultdict(set)
def refs(e, acc):
    if isinstance(e, dict):
        for k, x in e.items():
            if k == "digest": acc.add(x)
            elif k == "field": acc.add(x["node"])
            else: refs(x, acc)
    elif isinstance(e, list):
        for x in e: refs(x, acc)
for r in graph["rules"]:
    a = set(); refs(r["expression"], a); a.discard(r["node"]); deps[r["node"]] |= a
R["publishedObjectOrderForwardRefs"] = sorted([a, b] for a in deps for b in deps[a] if pos[b] > pos[a])[:10]
# HOLD nulls
hold = load("actual-bindings-HOLD.json")
nn = []
def walk(v, p):
    if isinstance(v, dict):
        for k, x in v.items(): walk(x, p + "/" + k)
    elif isinstance(v, list):
        for i, x in enumerate(v): walk(x, p + "/" + str(i))
    elif v is not None: nn.append([p, v])
walk({"targetBindings": hold["targetBindings"], "rootBindings": hold["rootBindings"], "members": hold["members"]}, "")
R["hold"] = {"nonNullBindingLeaves": nn[:20], "status": hold["status"], "executionAuthorized": hold["executionAuthorized"],
             "candidateABIIsAccepted": hold["candidateABIIsAccepted"], "contractAcceptance": hold["contractAcceptance"]}
# registries / roles mention derived set?
inputs = load("scenario-inputs.json")
blob = json.dumps({"policy": inputs["policy"], "trust": load("trust-bootstrap-contract.json"),
                   "slots": load("proof-slot-registry.json"), "recipes": load("recipe-definitions.json")})
R["registryMentions"] = {t: blob.count(t) for t in ("cohort-projection-set", "migration-cohort-projection-set", "DERIVED_DIGEST", "derived")}
R["policyDerivedSetsAreTrustAnchors"] = inputs["policy"].get("derivedSetsAreTrustAnchors")
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(R, f, indent=1)
print(json.dumps(R)[:4000])
