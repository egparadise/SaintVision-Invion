"""Reviewer-independent offline check of bootstrap v5 (8874b2df) evidence.

Usage: python -I -B v5_check.py <repo> <v5_dir> <v4_dir> <out_json>
Reads Git objects and extracted JSON as DATA only; owner programs are not run.
No network, no signatures, no Node/Docker/PG. Synthetic values only.
"""
import copy, hashlib, json, re, subprocess, sys, collections

REPO, V5, V4, OUT = sys.argv[1:5]
TARGET = "8874b2dfe0dda9a019bd5f334636668290702e13"
PARENT = "eed826e7fb066193d3a2d9d28abda15216264f77"
DOMAIN = b"saintvision/derived/migration-cohort-projection-set/v1"
R = {"target": TARGET, "parent": PARENT}


def git(*a):
    p = subprocess.run(["git", "-C", REPO, *a], capture_output=True)
    return p.returncode, p.stdout, p.stderr


def load(d, n):
    with open(f"{d}/{n}", "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ---------- C2: Go json.Marshal of generic maps (sorted keys, HTML + U+2028/9 escapes)
def _s(x):
    out = ['"']
    for ch in x:
        o = ord(ch)
        if 0xD800 <= o <= 0xDFFF:
            raise ValueError("surrogate")
        if ch == '"': out.append('\\"')
        elif ch == '\\': out.append('\\\\')
        elif ch == '\n': out.append('\\n')
        elif ch == '\r': out.append('\\r')
        elif ch == '\t': out.append('\\t')
        elif o < 0x20 or ch in '<>&' or o in (0x2028, 0x2029): out.append('\\u%04x' % o)
        else: out.append(ch)
    out.append('"')
    return ''.join(out)


def c2s(v):
    if v is None: return 'null'
    if v is True: return 'true'
    if v is False: return 'false'
    if isinstance(v, int): return str(v)
    if isinstance(v, float): raise ValueError("float")
    if isinstance(v, str): return _s(v)
    if isinstance(v, list): return '[' + ','.join(c2s(x) for x in v) + ']'
    if isinstance(v, dict):
        ks = sorted(v, key=lambda k: k.encode('utf-8'))
        return '{' + ','.join(_s(k) + ':' + c2s(v[k]) for k in ks) + '}'
    raise TypeError(type(v))


def c2(v):
    return c2s(v).encode('utf-8')


PINNED = {"cohort-projection-set": "DERIVED_DIGEST", "api-request": "TRANSPORT_DATA", "api-response": "TRANSPORT_DATA"}


def pinned(kind):
    return PINNED.get(kind, "SIGNED_ENVELOPE")


def node_digest(kind, payload):
    if pinned(kind) == "DERIVED_DIGEST":
        return sha(DOMAIN + b"\x00" + c2(payload))
    return sha(c2(payload))


def is_proof(v):
    return isinstance(v, dict) and "slotId" in v and "contractId" in v and "signatureDomainASCII" in v


def strip(v):
    if isinstance(v, dict):
        return {k: strip(x) for k, x in v.items() if not is_proof(x)}
    if isinstance(v, list):
        return [strip(x) for x in v if not is_proof(x)]
    return v


def ptr_get(obj, p):
    if p == "":
        return obj
    for part in p.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def ptr_set(obj, p, val):
    parts = [x.replace("~1", "/").replace("~0", "~") for x in p.split("/")[1:]]
    for part in parts[:-1]:
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    last = parts[-1]
    if isinstance(obj, list): obj[int(last)] = val
    else: obj[last] = val


# ---------- load
nodes = load(V5, "scenario-objects.json")["nodes"]
graph = load(V5, "artifact-reference-graph.json")
inputs = load(V5, "scenario-inputs.json")
rules = graph["rules"]
GRAMMAR = set(graph["expressionGrammar"])


class Ctx:
    def __init__(self, nodes):
        self.nodes = nodes
        self.final = set()
        self.cache = {}

    def dig(self, nid):
        if nid not in self.final:
            raise LookupError("forward/unknown node " + nid)
        if nid not in self.cache:
            n = self.nodes[nid]
            self.cache[nid] = node_digest(n["kind"], n["payload"])
        return self.cache[nid]


def plan_subject(ctx):
    body = copy.deepcopy(ctx.nodes["plan"]["payload"]["body"])
    for k in ("planSubjectSHA256", "independentPlanReview", "rootPublicationIntent"):
        body.pop(k, None)
    return sha(c2(body))


def ev(e, ctx, self_node):
    if not isinstance(e, dict) or len(e) != 1:
        raise ValueError("bad expression")
    (op, a), = e.items()
    if op not in GRAMMAR: raise ValueError("unknown op " + op)
    if op == "const": return copy.deepcopy(a)
    if op == "input": return copy.deepcopy(ptr_get(inputs, a))
    if op == "field":
        if a["node"] != self_node and a["node"] not in ctx.final: raise LookupError("forward field " + a["node"])
        return copy.deepcopy(ptr_get(ctx.nodes[a["node"]]["payload"], a["pointer"]))
    if op == "digest": return ctx.dig(a)
    if op == "object": return {k: ev(x, ctx, self_node) for k, x in a.items()}
    if op == "array": return [ev(x, ctx, self_node) for x in a]
    if op == "add": return sum(ev(x, ctx, self_node) for x in a)
    if op == "canonicalSHA256": return sha(c2(ev(a, ctx, self_node)))
    if op == "planSubject": return plan_subject(ctx)
    raise ValueError(op)


ORDER0 = []
for r in rules:
    if r["node"] not in ORDER0: ORDER0.append(r["node"])
BYNODE = collections.defaultdict(list)
for r in rules: BYNODE[r["node"]].append(r)
DEPS = collections.defaultdict(set)
def _refs(e, acc):
    if isinstance(e, dict):
        for k, x in e.items():
            if k == "digest": acc.add(x)
            elif k == "field": acc.add(x["node"])
            elif k == "planSubject": pass
            else: _refs(x, acc)
    elif isinstance(e, list):
        for x in e: _refs(x, acc)
for r in rules:
    a = set(); _refs(r["expression"], a); a.discard(r["node"]); DEPS[r["node"]] |= a
ORDER = []; _state = {}
CYCLE = []
def _visit(n, stack):
    if _state.get(n) == 2: return
    if _state.get(n) == 1: CYCLE.append(stack[stack.index(n):] + [n]); return
    _state[n] = 1
    for d in sorted(DEPS[n]): _visit(d, stack + [n])
    _state[n] = 2; ORDER.append(n)
for n in ORDER0: _visit(n, [])
FIRST_FORWARD = next(((a, b) for a in ORDER0 for b in DEPS[a] if ORDER0.index(b) > ORDER0.index(a)), None)


def check_graph(ns):
    ctx = Ctx(ns); fails = []
    for nid in ORDER:
        for r in BYNODE[nid]:
            try:
                ok = strip(ptr_get(ns[nid]["payload"], r["pointer"])) == strip(ev(r["expression"], ctx, nid))
            except Exception as e:
                ok = False
            if not ok: fails.append((nid, r["pointer"]))
        ctx.final.add(nid)
    return fails


def regen(ns, override=None):
    """Rebind every rule value in dependency order; optional (node,pointer,value) kept bad."""
    ns = copy.deepcopy(ns); ctx = Ctx(ns)
    for nid in ORDER:
        for r in BYNODE[nid]:
            val = ev(r["expression"], ctx, nid)
            cur = ptr_get(ns[nid]["payload"], r["pointer"])
            if strip(cur) != strip(val):
                ptr_set(ns[nid]["payload"], r["pointer"], val)
        if override and override[0] == nid:
            ptr_set(ns[nid]["payload"], override[1], copy.deepcopy(override[2]))
            # rebind this node's other rules after the bad field (e.g. planSubject), keep the bad field
            for r in BYNODE[nid]:
                if override[1] == r["pointer"] or override[1].startswith(r["pointer"] + "/"): continue
                val = ev(r["expression"], ctx, nid)
                if strip(ptr_get(ns[nid]["payload"], r["pointer"])) != strip(val):
                    ptr_set(ns[nid]["payload"], r["pointer"], val)
        ctx.final.add(nid)
    return ns


# ---------- 1. Git path audit
rc, raw, err = git("diff", "--no-ext-diff", "--no-renames", "--name-status", "-z", PARENT, TARGET)
items = raw.decode("utf-8", "strict").split("\x00")
pairs = [(items[i], items[i + 1]) for i in range(0, len(items) - 1, 2)]
audit = load(V5, "actual-git-path-audit.json")
R["gitAudit"] = {"exit": rc, "pairs": len(pairs), "allA": all(s == "A" for s, _ in pairs),
                 "rawSha256": sha(raw), "ownerRawSha256": audit.get("rawOutputSHA256"),
                 "pathsEqualOwner": sorted(pairs) == sorted((x["status"], x["path"]) for x in audit["actualNameStatus"]),
                 "ownerChangedPaths": audit["changedPaths"], "ownerArgvHasNoSecondRev": len(audit["argv"]) == 7}

# ---------- 2. artifact hashes vs owner proposal-validation (from Git blobs)
pv = load(V5, "proposal-validation.json")
mism = []
for path, h in pv["artifactHashes"].items():
    full = path if path.startswith("docs/") else "docs/vault/30_Development/Evidence/fleet5-bootstrap-normative-contracts-20261105-v5/" + path
    rc2, b, _ = git("cat-file", "blob", f"{TARGET}:{full}")
    if rc2 or sha(b) != h: mism.append(path)
hist = [p for _, p in pairs if "/History/" in p][0]
_, hb, _ = git("cat-file", "blob", f"{TARGET}:{hist}")
R["artifactHashes"] = {"count": len(pv["artifactHashes"]), "mismatch": mism, "historyMatches": sha(hb) == pv["historySHA256"]}

# ---------- 3. node digests, kinds, closure of derived records
kinds = collections.Counter(n["kind"] for n in nodes.values())
dk = collections.Counter(pinned(n["kind"]) for n in nodes.values())
bad_digest = [k for k, n in nodes.items() if node_digest(n["kind"], n["payload"]) != n["sha256"]]
label_mismatch = [k for k, n in nodes.items() if n.get("digestKind") != pinned(n["kind"])]
FORBID = re.compile(r"signature|signer|key|grant|producerrole", re.I)
def keys(v, acc):
    if isinstance(v, dict):
        for k, x in v.items(): acc.add(k); keys(x, acc)
    elif isinstance(v, list):
        for x in v: keys(x, acc)
    return acc
derived = {k: n for k, n in nodes.items() if n["kind"] == "cohort-projection-set"}
forbidden_in_derived = sorted({k for n in derived.values() for k in keys(n["payload"], set()) if FORBID.search(k)})
plain_alias = [k for k, n in derived.items() if sha(c2(n["payload"])) == n["sha256"]]
nl = [k for k, n in derived.items() if c2(n["payload"]).endswith(b"\n")]
R["objects"] = {"total": len(nodes), "kinds": dict(kinds), "digestKinds": dict(dk), "digestMismatch": bad_digest,
                "labelVsPinnedMismatch": label_mismatch, "derivedForbiddenKeys": forbidden_in_derived,
                "derivedDigestEqualsPlainSha": plain_alias, "derivedBodyTrailingLF": nl,
                "distinctDerivedDigests": len({n["sha256"] for n in derived.values()})}

# ---------- 4. rule evaluation, regeneration, coverage, proofs
fails = check_graph(nodes)
ops = collections.Counter()
def walk(e):
    if isinstance(e, dict):
        for k, x in e.items():
            if k in GRAMMAR: ops[k] += 1
            walk(x)
    elif isinstance(e, list):
        for x in e: walk(x)
for r in rules: walk(r["expression"])
reg = regen(nodes)
regen_diff = [k for k in nodes if node_digest(reg[k]["kind"], reg[k]["payload"]) != nodes[k]["sha256"]]
proofs = []
def find_proofs(v, p, nid):
    if is_proof(v): proofs.append((nid, p)); return
    if isinstance(v, dict):
        for k, x in v.items(): find_proofs(x, p + "/" + k, nid)
    elif isinstance(v, list):
        for i, x in enumerate(v): find_proofs(x, p + "/" + str(i), nid)
for k, n in nodes.items(): find_proofs(n["payload"], "", k)
leaves = []
def find_leaves(v, p, nid):
    if is_proof(v): return
    if isinstance(v, dict) and v:
        for k, x in v.items(): find_leaves(x, p + "/" + k, nid)
    elif isinstance(v, list) and v:
        for i, x in enumerate(v): find_leaves(x, p + "/" + str(i), nid)
    else: leaves.append((nid, p))
for k, n in nodes.items(): find_leaves(n["payload"], "", k)
cover = collections.Counter()
rp = collections.defaultdict(list)
for r in rules: rp[r["node"]].append(r["pointer"])
for nid, p in leaves:
    cover[(nid, p)] = sum(1 for q in rp[nid] if p == q or p.startswith(q + "/"))
R["graph"] = {"rules": len(rules), "cycles": CYCLE[:5], "ruleListFirstForwardRef": FIRST_FORWARD, "dependencyEdges": sum(len(v) for v in DEPS.values()), "relations": dict(collections.Counter(r["relation"] for r in rules)),
              "ops": dict(ops), "failingRules": fails[:20], "failingCount": len(fails),
              "regenerationDigestDiffs": regen_diff, "proofObjects": len(proofs),
              "ownerStructuredRefs": len(load(V5, "reference-graph-coverage.json")["structuredProofReferences"]),
              "nonProofLeaves": len(leaves), "uncovered": sum(1 for v in cover.values() if v == 0),
              "multiplyCovered": sum(1 for v in cover.values() if v > 1)}

# ---------- 5. derived-context semantics independent of the rules (trace-driven)
trace = {t["sequence"]: t for t in graph["trace"]}
sem = []
for k, n in sorted(derived.items()):
    p = n["payload"]; seq = p["sequence"]; t = trace[seq]
    lease_node = t["activeLease"]
    # after a release outcome the genuine lease is the RELEASED fence record
    if t["method"] == "release" and t["recordKind"] == "outcome": lease_node = "fence-released"
    L = nodes[lease_node]["payload"]["body"]
    errs = []
    if p["planEnvelopeSHA256"] != nodes["plan"]["sha256"]: errs.append("plan")
    if p["leaseEnvelopeSHA256"] != nodes[lease_node]["sha256"]: errs.append("lease")
    if p["fenceEpoch"] != L["fenceEpoch"] or p["operationId"] != L["operationId"]: errs.append("epoch/op")
    head = t["head"]
    if (head is None) != (p["inventoryHead"]["presence"] == "ABSENT"): errs.append("headPresence")
    if head and p["inventoryHead"]["envelopeSHA256"] != nodes[head]["sha256"]: errs.append("headDigest")
    if [m["slot"] for m in p["members"]] != ["PC2", "PC4"]: errs.append("order")
    for m in p["members"]:
        pn = f"projection-{seq:02d}-{m['slot']}"
        if m["projectionEnvelopeSHA256"] != nodes[pn]["sha256"]: errs.append("member " + m["slot"])
        if nodes[pn]["kind"] != "migration-journal": errs.append("memberKind")
    if p["inventoryHeadReadbackSHA256"] not in inputs["verifiedReadbackIds"].values(): errs.append("readback")
    if p["cohortId"] != inputs["facts"]["cohortId"]: errs.append("cohort")
    sem.append({"node": k, "seq": seq, "lease": lease_node, "epoch": p["fenceEpoch"], "head": p["inventoryHead"]["presence"], "errors": errs})
R["derivedSemantics"] = {"records": len(sem), "withErrors": [s for s in sem if s["errors"]],
                         "epochs": dict(collections.Counter(s["epoch"] for s in sem)),
                         "leases": dict(collections.Counter(s["lease"] for s in sem))}

# ---------- 6. signer policy (I2) and root-fence scope
pol = inputs["dummySignerPolicy"]; pol_file = load(V5, "dummy-signer-policy.json")
signed = {k: n for k, n in nodes.items() if pinned(n["kind"]) == "SIGNED_ENVELOPE"}
sigs = [n["payload"]["signer"]["signatureHex"] for n in signed.values()]
def scope_of(k, n):
    m = re.search(r"-(PC2|PC4)$", k)
    if m: return m.group(1)
    return "COHORT"
smis = []
for k, n in signed.items():
    s = n["payload"]["signer"]; a = pol["artifactAssignments"].get(k)
    want = pol["roleKeys"].get(f"{s['role']}@{scope_of(k, n)}")
    if a != s or want != s["keySPKISHA256"]: smis.append((k, s["role"], scope_of(k, n)))
rootfence = sorted(k for k, n in signed.items() if n["payload"]["signer"]["role"] == "root-fence")
proof_keymis = []
for nid, p in proofs:
    pr = ptr_get(nodes[nid]["payload"], p)
    if pr["signerKeySPKISHA256"] not in pol["roleKeys"].values(): proof_keymis.append((nid, p))
R["signers"] = {"signedEnvelopes": len(signed), "distinctSignatureHex": len(set(sigs)),
                "assignmentOrScopeMismatch": smis, "rootFenceSigned": rootfence,
                "derivedInAssignments": sorted(set(pol["artifactAssignments"]) & set(derived)),
                "policyFileEqualsInput": pol_file == pol, "keysAreReal": pol["keysAreReal"],
                "distinctNodeScopedKeys": {r: len({pol["roleKeys"].get(f"{r}@PC2"), pol["roleKeys"].get(f"{r}@PC4")} - {None})
                                           for r in sorted({k.split("@")[0] for k in pol["roleKeys"] if k.endswith(("@PC2", "@PC4"))})},
                "proofRefKeyNotInPolicy": len(proof_keymis)}

# ---------- 7. negatives: rebind and re-evaluate
def neg(cases, tag, sample_all=True):
    res = {"cases": len(cases), "candidateDigestMatch": 0, "rejected": 0, "onlyTargetRuleFails": 0, "errors": []}
    for c in cases:
        try:
            ns = regen(nodes, (c["node"], c["pointer"], c["value"]))
            n = ns[c["node"]]
            if node_digest(n["kind"], n["payload"]) == c["candidateNodeDigest"]: res["candidateDigestMatch"] += 1
            f = check_graph(ns)
            if f: res["rejected"] += 1
            kind = "outer" if c["pointer"].startswith("/signer/") else ("proof" if "signerKeySPKISHA256" in c["pointer"] else "context")
            res.setdefault("byKind", {}).setdefault(kind, [0, 0, 0])
            res["byKind"][kind][0] += 1; res["byKind"][kind][1] += int(node_digest(n["kind"], n["payload"]) == c["candidateNodeDigest"]); res["byKind"][kind][2] += int(bool(f))
            if f and all(x[0] == c["node"] for x in f): res["onlyTargetRuleFails"] += 1
        except Exception as e:
            res["errors"].append([c.get("label") or c["node"], repr(e)[:120]])
    return res
ctxneg = load(V5, "derived-context-rehash-negative-fixtures.json")["cases"]
signeg = load(V5, "dummy-signer-swap-negative-fixtures.json")["cases"]
R["negatives"] = {"derivedContext": neg(ctxneg, "ctx"), "dummySigner": neg(signeg, "sig"),
                  "contextCaseNodes": dict(collections.Counter(c["node"].split("-")[0] for c in ctxneg)),
                  "signerCasePointers": dict(collections.Counter(c["pointer"] for c in signeg))}

# ---------- 8. schemas (offline registry), API:2 old-field rejects, v4 signed shape reject
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
ID_SOURCE = {}
deps = load(V5, "effective-schema-document-dependencies.json")
reg_res = []; dep_bad = []
for d in deps["documents"]:
    rc3, b, _ = git("cat-file", "blob", f"{TARGET}:{d['path']}")
    if rc3 or sha(b) != d["sha256"] or len(b) != d["bytes"]: dep_bad.append(d["path"])
    doc = json.loads(b.decode("utf-8"))
    Draft202012Validator.check_schema(doc)
    uri = doc.get("$id") or ("https://fleet5-doc-fixture.invalid/" + d["path"].split("contracts-20261105-")[1])
    ID_SOURCE[uri] = "declared" if doc.get("$id") else "reviewer-assigned-from-path"
    reg_res.append((uri, Resource.from_contents(doc, default_specification=DRAFT202012)))
registry = Registry().with_resources(reg_res)
def valid(kind_or_id, inst):
    sid = deps["rootSchemas"].get(kind_or_id, kind_or_id)
    return Draft202012Validator({"$ref": sid}, registry=registry).is_valid(inst)
sch_bad = [k for k, n in nodes.items() if not valid(n["kind"], n["payload"])]
old = load(V5, "explicit-prior-reference-negative-fixtures.json")["cases"]
old_accept = []
for c in old:
    p = copy.deepcopy(nodes[c["node"]]["payload"]); p[c["field"]] = c["value"]
    if valid(nodes[c["node"]]["kind"], p): old_accept.append(c["node"])
v4n = load(V4, "scenario-objects.json")["nodes"]
v4sets = [n for n in v4n.values() if n["kind"] == "cohort-projection-set"]
v4accept = sum(valid("cohort-projection-set", n["payload"]) for n in v4sets)
# member vs cohort field variants on API:2 requests
var = {"memberWithCohortRef": 0, "cohortWithNodeRef": 0}
for k, n in nodes.items():
    if n["kind"] != "api-request": continue
    p = n["payload"]
    if p["expectedNodeProjectionEnvelopeSHA256"] is not None and p["expectedCohortProjectionSetDigestSHA256"] is not None: var["memberWithCohortRef"] += 1
    if p["expectedNodeProjectionEnvelopeSHA256"] is None and p["expectedCohortProjectionSetDigestSHA256"] is None: var.setdefault("bothNull", []).append(k)
ts = load(V5, "type-separation-fixtures.json")["cases"]
swap = [c for c in ts if c["mutation"] != "caller digest classification"]
swap_schema_ok = []; swap_graph_rej = 0
for c in swap:
    k = c["node"]; ok = valid(nodes[k]["kind"], c["candidate"])
    if c["expected"] == "REJECT_SCHEMA" and ok: swap_schema_ok.append(k)
    if c["expected"] != "REJECT_SCHEMA":
        ns = copy.deepcopy(nodes); ns[k]["payload"] = c["candidate"]
        if check_graph(ns): swap_graph_rej += 1
label_cases = [c for c in ts if c["mutation"] == "caller digest classification"]
label_rej = sum(1 for c in label_cases if c["value"] != pinned(nodes[c["node"]]["kind"]))
R["schemas"] = {"documents": len(deps["documents"]), "idSources": dict(collections.Counter(ID_SOURCE.values())), "depMismatch": dep_bad,
                "v4SignedAggregateInClosure": any("v4/cohort-projection-set" in d["path"] for d in deps["documents"]),
                "nodesSchemaInvalid": sch_bad, "oldFieldCases": len(old), "oldFieldAccepted": old_accept,
                "v4SignedSetsAcceptedByV5Schema": f"{v4accept}/{len(v4sets)}", "requestVariants": var,
                "swapCases": len(swap), "swapSchemaWronglyAccepted": swap_schema_ok,
                "swapGraphRejected": swap_graph_rej, "labelCases": len(label_cases), "labelRejectedByPinnedKind": label_rej}

# ---------- 9. byte vectors
vec = load(V5, "derived-byte-ordering-vectors.json")
vp = []
for v in vec["positive"]:
    body = c2(v["body"]); msg = DOMAIN + bytes([0]) + body
    vp.append({"id": v["id"], "bodyHex": body.hex() == v["canonicalBodyHex"], "bodySha": sha(body) == v["canonicalBodySHA256"],
               "domainHex": (DOMAIN + bytes([0])).hex() == v["derivedDomainHex"],
               "messageHex": msg.hex() == v["domainPlusBodyHex"],
               "digest": sha(msg) == v["derivedDigestSHA256"], "noLF": not body.endswith(bytes([10])),
               "schemaValid": valid("cohort-projection-set", v["body"]),
               "equalsScenario": any(n["payload"] == v["body"] for n in derived.values())})
vn = [{"label": v["label"], "expected": v["expected"], "schemaRejects": not valid("cohort-projection-set", v["body"]),
       "recomputedDigestMatches": (sha(DOMAIN + bytes([0]) + c2(v["body"])) == v["recomputedDigestSHA256"]) if v.get("recomputedDigestSHA256") else None} for v in vec["negative"]]
R["vectors"] = {"positive": vp, "negative": vn, "vectorKeys": sorted(vec["positive"][0])}

# ---------- 10. I3 pre-prune recovery and 102-pointer equivalence
rc4, t, _ = git("cat-file", "-t", "b8c66b46bf4c431c0d59b79941d2da868f2c523d")
rc5, blob, _ = git("cat-file", "blob", "b8c66b46bf4c431c0d59b79941d2da868f2c523d")
_, pub, _ = git("cat-file", "blob", f"{TARGET}:docs/vault/30_Development/Evidence/fleet5-bootstrap-normative-contracts-20261105-v5/recovered-original-preprune-seed.json")
v4g = load(V4, "artifact-reference-graph.json")
ptrs = set()
def inp(e):
    if isinstance(e, dict):
        for k, x in e.items():
            if k == "input": ptrs.add(x)
            else: inp(x)
    elif isinstance(e, list):
        for x in e: inp(x)
for r in v4g["rules"]: inp(r["expression"])
_, v4seed_b, _ = git("cat-file", "blob", f"{PARENT}:docs/vault/30_Development/Evidence/fleet5-bootstrap-normative-contracts-20261105-v4/scenario-inputs.json")
orig = json.loads(blob.decode("utf-8")); v4seed = json.loads(v4seed_b.decode("utf-8"))
neq = []; miss = []
for p in sorted(ptrs):
    try:
        a = ptr_get(orig, p); b = ptr_get(v4seed, p)
        if c2(a) != c2(b): neq.append(p)
    except Exception:
        miss.append(p)
eqf = load(V5, "preprune-equivalence.json")
R["I3"] = {"typeExit": rc4, "type": t.decode().strip(), "blobExit": rc5, "bytes": len(blob), "sha256": sha(blob),
           "publishedFileByteIdentical": pub == blob, "v4InputPointers": len(ptrs), "unequal": neq, "unresolved": miss,
           "ownerPointersEqualSet": sorted(x["pointer"] for x in eqf["pointers"]) == sorted(ptrs),
           "finalV4SeedSha256": sha(v4seed_b), "ownerFinalV4SeedSha256": eqf["finalPublishedV4SeedSHA256"]}

# ---------- 11. HOLD bindings stay null
hold = load(V5, "actual-bindings-HOLD.json")
def nonnull(v, p, acc):
    if isinstance(v, dict):
        for k, x in v.items(): nonnull(x, p + "/" + k, acc)
    elif isinstance(v, list):
        for i, x in enumerate(v): nonnull(x, p + "/" + str(i), acc)
    return acc
R["hold"] = {"topKeys": sorted(hold)[:30]}

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(R, f, indent=1, ensure_ascii=True)
print(json.dumps(R, ensure_ascii=True)[:9000])
