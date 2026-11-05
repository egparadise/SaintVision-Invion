"""Reviewer census audit of the owner's 72028 callsite ledger (git objects only, no app imports)."""
import ast
import collections
import json
import re
import subprocess
import sys

repo, ledger_path = sys.argv[1], sys.argv[2]
SRC = "72028cbac903c4415d9979f980a6e0f9948e914f"
L = json.load(open(ledger_path, encoding="utf-8"))
ledger_files = {f["path"] for f in L["sourceFiles"]}

def git(*a):
    return subprocess.check_output(["git", *a], cwd=repo)

all_py = [p for p in git("ls-tree", "-r", "--name-only", SRC).decode().splitlines()
          if p.endswith(".py") and not p.startswith(("tests/", "docs/")) and "/tests/" not in p]
B_TABLES = re.compile(r"\b(?:inv\.)?(nodes|node_channels|storage_contributions|control_epoch|tenant_controls|runs|operator_grants|resource_claims|claims)\b")
ORM_EXTRA = {"query", "scalars", "scalar", "merge", "refresh", "bulk_save_objects", "bulk_insert_mappings", "bulk_update_mappings", "execute_values", "copy"}
DB_ATTR = {"execute", "executemany"} | ORM_EXTRA | {"get", "add", "flush", "delete"}

outside = []
inside_uncovered = collections.Counter()
inside_uncovered_examples = []
for p in all_py:
    raw = git("show", SRC + ":" + p)
    s = raw.decode("utf-8-sig", "replace")
    try:
        tree = ast.parse(s)
    except SyntaxError:
        continue
    calls = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in DB_ATTR:
            recv = ast.unparse(n.func.value)
            calls.append((n.lineno, n.func.attr, recv, ast.get_source_segment(s, n) or ""))
    sql_calls = [c for c in calls if c[1] in ("execute", "executemany")]
    if p not in ledger_files:
        hits = [c for c in sql_calls if B_TABLES.search(c[3])]
        if hits:
            outside.append({"path": p, "executeCalls": len(sql_calls), "bTableExecuteCalls": len(hits),
                            "examples": [f"{p}:{c[0]} {c[2]}.{c[1]} :: {' '.join(c[3].split())[:140]}" for c in hits[:3]]})
    else:
        for c in calls:
            covered = c[1] in ("execute", "executemany") or (c[1] in ("get", "add", "flush", "delete") and c[2] in ("session", "db_session"))
            if not covered and (c[1] in ORM_EXTRA or c[2].endswith("session")):
                inside_uncovered[c[1]] += 1
                if len(inside_uncovered_examples) < 12:
                    inside_uncovered_examples.append(f"{p}:{c[0]} {c[2]}.{c[1]}")

print(json.dumps({
    "level": "REVIEWER_STATIC_GIT_OBJECT_AUDIT_ONLY",
    "source": SRC,
    "nonTestPythonFiles": len(all_py),
    "ledgerFiles": len(ledger_files),
    "filesOutsideLedgerWithBTableExecute": len(outside),
    "outside": outside,
    "insideLedgerUncoveredDbLikeCalls": dict(inside_uncovered),
    "insideExamples": inside_uncovered_examples,
}, indent=1))
