"""Reviewer adversarial probes of the rev3 owner model/schema (SCHEMA/STATIC/SYMBOLIC only).

Loads the owner's contract_fixtures.py from a scratch copy by path. Each case records what
the contract text requires ("contract") and what the owner model/schema actually does.
"""
import base64
import collections
import hashlib
import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

E = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("owner_fixtures", E / "contract_fixtures.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
from jsonschema import Draft202012Validator

OUT = []
def case(name, actual, contract, note=""):
    OUT.append({"name": name, "actual": actual, "contract": contract, "agrees": actual == contract, "note": note})

def schema_only(kind, obj):
    return Draft202012Validator({"$schema": m.SCHEMA["$schema"], "$defs": m.SCHEMA["$defs"], "$ref": "#/$defs/" + kind}).is_valid(obj)

NOW = m.NOW
chain = m.make_chain()
ub = chain["use"]["body"]

# 1. exact-int time: schema alone vs owner predicate
f = deepcopy(ub); f["issuedAt"] = float(f["issuedAt"])
case("schema-only-accepts-float-time", schema_only("roleUse", f), False, "JSON Schema 'integer' admits 2.0e9; only no_float()/strict_json reject")
case("owner-shape-rejects-float-time", m.shape("roleUse", f), False)
big = deepcopy(ub); big["expiresAt"] = 2 ** 60
case("time-above-2^53-rejected", m.shape("roleUse", big), False)

# 2. purpose/path coupling lives only in predicate
pp = deepcopy(ub); pp["purpose"] = "STORAGE_COLLECT"
case("schema-accepts-purpose-path-mismatch", schema_only("roleUse", pp), False, "schema enums are independent")
c2 = deepcopy(chain); c2["use"] = m.seal("saintvision/node-role-use/v1", pp, "delegated-use")
case("predicate-rejects-purpose-path-mismatch", m.valid_chain(c2), False)

# 3. schemas never exercised by owner fixtures
src = (E / "contract_fixtures.py").read_text(encoding="utf-8")
for kind in ("gateControl", "safety", "observeInput", "signedEnvelope", "roleConfig"):
    case("owner-fixtures-exercise-schema-" + kind, ("'" + kind + "'") in src, True, "new R1/R2 lanes need positive+negative shape fixtures")

# 4. gate state / key delivery / ObservationScope are not inputs to the owner chain model
import inspect
sig = inspect.signature(m.valid_chain).parameters
case("chain-model-has-gate-armed-or-invalidated-input", any(p in sig for p in ("gate", "armed", "gate_state", "invalidated")), True, "INVALIDATE_EXACT_GATE / restart-no-gate not modelled")
case("chain-model-has-key-delivery-receipt-input", any("deliver" in p or "receipt" in p for p in sig), True, "post-activation key delivery receipt not modelled")
case("owner-defines-ObservationScope-schema", "observationScope" in m.SCHEMA["$defs"], True, "prose only")
case("owner-defines-key-delivery-receipt-schema", any("deliver" in k.lower() for k in m.SCHEMA["$defs"]), True, "prose only")

# 5. safety envelope binds no method/path
case("safety-schema-binds-path", "path" in m.SCHEMA["$defs"]["safety"]["properties"], True, "action->path mapping must be normative")

# 6. roleUse binds no stream/sequence/channel field
props = m.SCHEMA["$defs"]["roleUse"]["properties"]
case("roleUse-binds-stream-or-sequence", any(k in props for k in ("streamId", "sequence", "frameSequence", "channel")), True, "frame sequence only via bodySha256 of frame body (if body carries it)")

# 7. approval bound in model is a constant, not the approval record
case("chain-model-binds-approval-expiry", "approval_end" in sig or "approval_expires" in sig, True, "release<=approval uses constant NOW+4000")

# 8. readmit accepts unchanged generation (no fresh-generation requirement)
case("readmit-same-generation-accepted", m.readmit(m.tuple_value(), m.tuple_value()), False, "contract: fresh actual generation after restart/expiry")

# 9. grant-consistency check is vacuous for writers named only in prose
abi = json.loads((E / "authority-abi.json").read_bytes())
import re
named = [t["table"] for t in abi["tableGrantMatrix"] if re.findall(r"\bb_[a-z_]+", t["writer"])]
case("tables-whose-writer-names-a-procedure", len(named), len(abi["tableGrantMatrix"]), "owner check only covers %d/%d tables: %s" % (len(named), len(abi["tableGrantMatrix"]), named))

# 10. key hierarchy lists gate ARM signer
signs = {k["key"]: k["signs"] for k in abi["keyHierarchy"]}
case("release-anchor-listed-as-ARM-signer", any("ARM" in s.upper() for s in signs["operator-release-anchor"]), True, "History/schema: ARM_EXACT_RELEASE signed by release authority; ABI lists only invalidation")
case("budget-signer-is-release-anchor-in-fixture", m.signed(m.budget_value(), "saintvision/context-budget/v1", "protected-release"), False, "budget approval uses release key in fixture; not in keyHierarchy")

# 11. displayLabel length unit
lab = "é" * 64
case("displayLabel-128-codepoints-192-bytes-schema-valid", schema_only("displayLabel", lab), True, "unit (code points vs UTF-8 bytes) must be stated for Go")

# 12. phase matrix independent regeneration
rows = json.loads((E / "phase-authority-matrix.json").read_bytes())["cases"]
recovery = {"REVOKE_C_JUMP", "EPOCH_CHANGE", "APPROVAL_EXPIRED", "OPERATION_GRANT_EXPIRED", "TARGET_RELEASE_EXPIRED", "TARGET_DELEGATION_EXPIRED", "LOST_RESPONSE_UNKNOWN"}
short = {"SOURCE_DELEGATION_EXPIRED", "ADMISSION_LEASE_EXPIRED", "ROLE_USE_EXPIRED", "CANDIDATE_PROOF_EXPIRED"}
phases = ["BEFORE_INTENT"] + ["AFTER_INTENT_kCAS_%d" % k for k in range(6)]
grid = collections.Counter((r["phase"], r["event"]) for r in rows)
case("matrix-is-exact-7x11-grid", sorted(grid) == sorted((p, e) for p in phases for e in recovery | short) and set(grid.values()) == {1}, True)
bad = []
for r in rows:
    k = None if r["phase"] == "BEFORE_INTENT" else int(r["phase"][-1])
    if k is None:
        ok = r["fence"] is False and r["sameIntentReplay"] is False
    else:
        ok = r["fence"] is True and r["business"] == "DENY_ALL_FIVE" and r["newOrdinaryIntent"] is False and \
             r["sameIntentReplay"] == (r["event"] in short) and (r["next"] == "B_RECOVERY1_REVIEWED_GATE") == (r["event"] in recovery)
        mem = deepcopy(r["members"])
        if r["event"] == "REVOKE_C_JUMP":
            # revoked member node0: +1 revocation jump on top of its CAS state, channel disabled
            j = mem[0]
            ok = ok and j.get("channelEnabled") is False and j["CP_C"] == (9 if k >= 1 else 8) and j["CP_DER"] == ("B" if k >= 1 else "A")
            j["CP_C"] = 8 if k >= 1 else 7
        cas = [mm["CP_C"] == 8 and mm["CP_DER"] == "B" for mm in mem]
        ok = ok and cas == [True] * k + [False] * (5 - k) and all(mm["P"] == 102 and mm["storageC"] == 8 and mm["nodeDER"] == "B" and mm["R"] == 2 for mm in mem)
    if not ok:
        bad.append(r["phase"] + "/" + r["event"])
case("matrix-rows-match-reviewer-rules", bad, [], "reviewer-derived: k CP CAS done, Node P/C/DER already target, recovery vs short-lived split")
lost = [r for r in rows if r["event"] == "LOST_RESPONSE_UNKNOWN" and r["phase"] != "BEFORE_INTENT"]
case("lost-response-always-recovery-gate-even-with-all-authority-valid", all(r["next"] == "B_RECOVERY1_REVIEWED_GATE" and r["approval"] == "VALID" and r["operationGrant"] == "VALID" for r in lost), True,
     "History R4/R6 resolve lost commit via exact ledger reread; matrix must say this row means ledger-unresolvable")
pre = [r for r in rows if r["phase"] == "BEFORE_INTENT" and r["event"] in short]
case("before-intent-short-lived-expiry-labelled-preflight-fail", all("preflight fails" in r["next"] for r in pre), True, "conservative; reissue/re-observe would suffice")
revoked_uncas = [r for r in rows if r["event"] == "REVOKE_C_JUMP" and r["phase"] not in ("BEFORE_INTENT", "AFTER_INTENT_kCAS_0", "AFTER_INTENT_kCAS_5")
                 and any(mm.get("channelEnabled") is False and mm["CP_DER"] == "A" for mm in r["members"])]
case("matrix-has-revoke-of-not-yet-CAS-member-at-k1-4", len(revoked_uncas) > 0, True,
     "revocation C+1 equals renewal target C=8 for an un-CAS'd member (DER A); must assert CAS refuses and C alone never means CAS-done")

# 13. selection and token strictness spot checks
members = ["node-%d" % i for i in range(5)]
for sel in (("node-0",), "node-0", ["node-0", True], ["NODE-0"]):
    case("selection-reject-" + repr(sel), m.selected_valid(sel, members, members), False)
body = m.canonical(ub)
obj = json.loads(body)
reordered = json.dumps(dict(reversed(list(obj.items()))), separators=(",", ":"), ensure_ascii=False).encode()
assert reordered != body
tok = "v1." + base64.urlsafe_b64encode(reordered).rstrip(b"=").decode() + "." + "a" * 128
case("token-noncanonical-key-order-rejected", m.token_syntax(tok), False)
good = "v1." + base64.urlsafe_b64encode(body).rstrip(b"=").decode() + "." + "a" * 128
case("token-canonical-positive-NO_CRYPTO", m.token_syntax(good), True)

res = {"level": "REVIEWER_SCHEMA_STATIC_SYMBOLIC_ONLY", "cases": len(OUT), "agree": sum(c["agrees"] for c in OUT), "disagree": sum(not c["agrees"] for c in OUT), "results": OUT}
print(json.dumps(res, indent=1, ensure_ascii=True))
