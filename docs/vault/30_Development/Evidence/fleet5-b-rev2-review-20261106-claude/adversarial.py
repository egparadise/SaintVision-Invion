"""Reviewer adversarial checks against the owner's proposed schema and predicate model.

Usage: python -I adversarial.py <evidence_dir> <out_json>
Imports the owner's validator module from a scratch COPY only to call its pure
predicate functions; no Node/PG/Docker/PKI operations exist in it.
Each case records what the schema/model ACTUALLY returns versus what the
contract text requires. A mismatch is a finding, not a script failure.
"""
import importlib.util, json, re, sys
from copy import deepcopy

EV, OUT = sys.argv[1:3]
spec = importlib.util.spec_from_file_location("owner_validator", f"{EV}/validate_revision_fixtures.py")
ov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ov)  # module-level code only loads the schema; main() is not called

cases = []

def case(name, actual, contract_requires, note=""):
    cases.append({"case": name, "actual": actual, "contractRequires": contract_requires,
                  "agrees": actual == contract_requires, "note": note})

H = "a" * 64
SIG = "a" * 128
NOW = ov.NOW

# 1. Python jsonschema uses re.search, where '$' also matches before a final '\n'.
case("token-trailing-newline", ov.schema_ok("roleUseSignedToken", "v1.YWJj." + SIG + "\n"), False,
     "ECMA-262 '$' would reject; Python re '$' accepts before final newline")
case("token-undecodable-b64-length-1mod4", ov.schema_ok("roleUseSignedToken", "v1.A." + SIG), False,
     "shape-only; decode/re-encode equality is future code")
case("token-uppercase-sig", ov.schema_ok("roleUseSignedToken", "v1.YWJj." + "A" * 128), False)
use = {"schemaVersion": "saintvision-node-role-use:1", "releaseId": "r", "admissionId": "a", "operationId": "o",
       "cohortId": "c", "channel": ov.current(0)["channel"], "servingGeneration": "g", "roleConfigSha256": H,
       "policySha256": H, "purpose": "EXECUTION", "method": "POST", "path": "/v1/executions",
       "requestBodySha256": H, "nonce": H, "issuedAt": NOW, "expiresAt": NOW + 60}
u = deepcopy(use); u["nonce"] = H + "\n"
case("roleUse-nonce-trailing-newline", ov.schema_ok("roleUse", u), False, "same '$' semantics on every ^...$ hash pattern")
# 2. expiry grammar
u = deepcopy(use); u["expiresAt"] = NOW - 1
case("roleUse-expires-before-issued", ov.schema_ok("roleUse", u), False, "no schema/predicate expiry relation")
u = deepcopy(use); u["expiresAt"] = NOW + 10 ** 9
case("roleUse-expiry-window-1e9s", ov.schema_ok("roleUse", u), False, "<=120s is text-only; no predicate fixture")
# 3. purpose/path matrix
u = deepcopy(use); u["path"] = "/v1/executions/receipts"
case("roleUse-EXECUTION-receipts-requires-business-token", ov.schema_ok("roleUse", u), True,
     "receipts is also the CP observe/reconcile path (dispatch.py:339, node_transport.py:83)")
for p in ("/v1/snapshots", "/v1/heartbeats", "/v1/executions/cancel", "/v1/builds/quarantine"):
    u = deepcopy(use); u["path"] = p
    case("roleUse-path-not-business " + p, ov.schema_ok("roleUse", u), False)
u = deepcopy(use); u["purpose"] = "MODEL"
case("roleUse-MODEL-and-EXECUTION-share-paths", ov.schema_ok("roleUse", u), True,
     "Node cannot distinguish MODEL vs EXECUTION by path; purpose check is CP/attestor-side only")
# 4. Unicode/control characters in canonical string fields
u = deepcopy(use); u["channel"]["node_id"] = "node \u0000\ud800"
case("roleUse-string-with-U2028-NUL-lone-surrogate", ov.schema_ok("roleUse", u), False,
     "no character-class constraint; Go json would turn lone surrogate into U+FFFD")
# 5. eligibility selection semantics
base = ov.cohort()
def safe(fn):
    try:
        return fn()
    except Exception as e:  # record, do not hide
        return f"EXCEPTION {type(e).__name__}"
case("eligible-empty-selection", safe(lambda: ov.eligible(base, selected=[])), False)
case("eligible-duplicate-selection", safe(lambda: ov.eligible(base, selected=[0, 0])), False,
     "duplicates not rejected by model")
case("eligible-foreign-index", safe(lambda: ov.eligible(base, selected=[5])), False,
     "foreign Node not representable; out-of-range raises")
c = deepcopy(base); c["members"][1]["nodeOnline"] = False
case("eligible-unrelated-offline-selected-healthy", ov.eligible(c, selected=[0]), True, "ADR100 steady state")
# admissions must expire <=120s after NOW in the model
c = deepcopy(base); c["members"][0]["admission"]["expiresAt"] = NOW + 121
case("eligible-admission-expiry-over-120s", ov.eligible(c, selected=[0]), False,
     "model caps admission lifetime at 120s: attestor must refresh every Node continuously")
# release expiry is a boolean mock; no refresh semantics
c = deepcopy(base); c["releaseCurrent"] = False
case("eligible-release-not-current-denies-all", ov.eligible(c, selected=[0]), False,
     "persistence-abi gives releases 'short expiry'; refreshing needs a new all-five release -> offline worker would block steady state")
# epoch / fence / generation: model uses booleans or equality with frozen copy
c = deepcopy(base); c["fenced"] = True
case("eligible-fenced-denies", ov.eligible(c, selected=[0]), False)
c = deepcopy(base); c["members"][0]["actualGeneration"] = "restarted"
case("eligible-stale-generation-denies", ov.eligible(c, selected=[0]), False)
# 6. CAS replay: revoke during S5 leaves a permanently BLOCKed member
old = {"C": 8, "DER": "A"}; new = {"C": 9, "DER": "B"}
case("cas-revoked-before-cas", ov.cas_replay({"C": 9, "DER": "A"}, None, old, new, "op"), "BLOCK_UNKNOWN")
# 7. pin replay model conflates P and C scales
case("pin-replay-P-C-same-integer-scale", ov.pin_replay(8, 8, "B", "B", "op", "op", True), True,
     "P and C passed as one integer pair; does not model independent P/C bases")
# 8. persistence ABI internal consistency
pa = json.load(open(f"{EV}/persistence-abi.json", encoding="utf-8"))
adm = next(t for t in pa["tables"] if t["table"] == "inv.node_role_admissions")
fk_release = any("release" in f for f in adm["authorityFields"] if f.startswith("FK"))
case("persistence-admission-FK-release-vs-no-FK-ordering", fk_release and "no FK" in pa["admissionReleaseOrdering"], False,
     "tables[] lists FK ...release while admissionReleaseOrdering says no FK to an existing release")
roles = sorted({t["writer"] for t in pa["tables"]})
case("persistence-distinct-db-principals-named", any(re.search(r"\binv_[a-z_]+\b", w) for w in roles if "inv_kernel" not in w), True,
     "writers are prose ('operator attestor', 'approval writer'); no named DB role/GRANT matrix")
schema = json.load(open(f"{EV}/proposed-closed-abi.schema.json", encoding="utf-8"))
case("roleConfig-single-trust-key", sorted(k for k in schema["$defs"]["roleConfig"]["properties"] if "Key" in k),
     ["releaseAuthorityPublicKeyPath", "releaseAuthorityPublicKeySha256"],
     "one key verifies both release authority and every per-request role-use token")
ctx = schema["$defs"]["executionContext"]["properties"]
case("executionContext-has-cpu-memory-disk-network-capability", any(re.search(r"cpu|memory|disk|network|capacity", k, re.I) for k in ctx), True,
     "only boolean verified flags + capabilityEvidenceSha256")
case("executionContext-wsl2-distro-identity-field", any(re.search(r"distro|instance|vm", k, re.I) for k in ctx), True,
     "WSL2 distros share one utility-VM kernel/boot_id with Docker Desktop")
phases = [p["phase"] for p in json.load(open(f"{EV}/phase-table.json", encoding="utf-8"))["phases"]]
case("phase-table-has-revoke-epoch-grant-expiry-rows", any(re.search(r"revoke|epoch|grant|expir", p, re.I) for p in phases), True)
case("phase-table-has-post-release-member-readmission-row", any(re.search(r"readmi|restart", p, re.I) for p in phases), True)

out = {"tool": "reviewer adversarial checks", "level": "SCHEMA_AND_OWNER_MOCK_PREDICATE_ONLY",
       "cases": cases, "agree": sum(c["agrees"] for c in cases), "disagree": sum(not c["agrees"] for c in cases)}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=True)
for c in cases:
    print(("OK   " if c["agrees"] else "GAP  ") + c["case"] + " actual=" + json.dumps(c["actual"]))
print(json.dumps({"agree": out["agree"], "disagree": out["disagree"]}))
