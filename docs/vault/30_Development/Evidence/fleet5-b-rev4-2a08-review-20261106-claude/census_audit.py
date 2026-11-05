"""Reviewer (Claude) independent audit of the owner Rev4 source census.

Read-only: imports the owner's source_census.py by path (it imports no application
code) and re-runs its analyze() on IN-MEMORY mutated copies of the exact 72028 Git
objects. Nothing under the owner's Evidence directory is written. STATIC only.
Usage: python -B census_audit.py  -> writes census-audit-result.json next to itself.
"""
from pathlib import Path
import ast
import collections
import importlib.util
import json
import re
import sys
import time

HERE = Path(__file__).resolve().parent
OWNER = HERE.parent / 'fleet5-b-contract-rev4-20261106-codex'
spec = importlib.util.spec_from_file_location('owner_source_census', OWNER / 'source_census.py')
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

stored = json.loads((OWNER / 'expanded-source-census.json').read_bytes())
matrix = json.loads((OWNER / 'authority-matrix.json').read_bytes())
sources = sc.load_sources()
out = {'level': 'STATIC_GIT_AST_REVIEWER_AUDIT', 'source': sc.BASE, 'ownerScript': str((OWNER / 'source_census.py').relative_to(sc.ROOT)).replace('\\', '/')}

# 0. Baseline: owner analyze() on unmodified Git objects equals stored census.
t = time.time(); base = sc.analyze(sources); out['baselineMatches'] = sc.audit_matches(stored, base); out['baselineSeconds'] = round(time.time() - t, 1)

# 1. Every textual call of a seed helper at 72028 has a helperEdge at that line.
textual = []
for p, raw in sources.items():
    for n in ast.walk(ast.parse(raw.decode('utf-8-sig'))):
        if isinstance(n, ast.Call):
            name = ast.unparse(n.func).split('.')[-1]
            if name in sc.HELPERS:
                textual.append((p, n.lineno, ast.unparse(n.func)))
edge_lines = {(e['path'], e['line']) for e in base['helperEdges']}
missing = [t for t in textual if (t[0], t[1]) not in edge_lines]
out['helperCallsTextual'] = len(textual); out['helperCallsWithoutEdge'] = missing

# 2. Calls through instance receivers to methods that reach a helper are dropped
#    silently (neither an edge nor an explicit unknown).
reached = set(base['reachableFunctions'])
reached_methods = collections.defaultdict(set)
for f in reached:
    parts = f.split('.')
    if len(parts) >= 3 and parts[-2][:1].isupper():
        reached_methods[parts[-1]].add(f)
dropped = []
edge_keys = {(e['path'], e['line'], e['spelling']) for e in base['helperEdges']}
for p, raw in sources.items():
    for n in ast.walk(ast.parse(raw.decode('utf-8-sig'))):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            spelling = ast.unparse(n.func); name = n.func.attr
            if name in reached_methods and not spelling.startswith(('self.', 'cls.')) and (p, n.lineno, spelling) not in edge_keys:
                if name.startswith('_') or name in ('reserve', 'renew', 'set_offer', 'lock_current', 'grant', 'admit'):
                    dropped.append({'path': p, 'line': n.lineno, 'spelling': spelling, 'wouldReach': sorted(reached_methods[name])[:3]})
unknown_keys = {(u['path'], u['line'], u['spelling']) for u in base['unknownStaticReceivers']}
out['instanceReceiverHelperCallsDropped'] = dropped
out['droppedAlsoListedUnknown'] = sum((d['path'], d['line'], d['spelling']) in unknown_keys for d in dropped)

# 3. Lock-mode labelling fidelity: real row/advisory locks labelled as MVCC.
LOCKTEXT = re.compile(r'FOR\s+NO\s+KEY\s+UPDATE|with_for_update\s*=|["\']with_for_update["\']|pg_advisory|read\s*=\s*True|skip_locked', re.I)
mis = [{'path': r['path'], 'line': r['line'], 'modes': r['currentModes'], 'expression': r['expression'][:160]} for r in base['records']
       if LOCKTEXT.search(r['expression']) and (r['currentModes'][0].startswith('MVCC') or 'read=True' in r['expression'] or 'skip_locked' in r['expression'])]
out['lockModeMislabels'] = mis

# 4. Census <-> authority matrix: every 72028 SQL writer of a table the matrix
#    claims to own exhaustively must map to a listed B procedure.
W = re.compile(r'\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+((?:inv|public)\.[a-z_]+)', re.I)
writers = collections.defaultdict(set)
for r in base['records']:
    if r['kind'] == 'SQL_EXPRESSION' and not r['path'].startswith('tools/'):
        for verb, table in W.findall(r['expression']):
            if table in matrix['tables']:
                writers[table].add((r['path'], r['line'], verb.split()[0].upper(), r['function']))
out['productSqlWritersOfMatrixTables'] = {t: {'matrixProcedures': [w['procedure'] for w in matrix['tables'][t]], 'source72028': sorted(map(list, v))} for t, v in sorted(writers.items())}
orm = []
for path, pat in [('src/saintvision/services/nodes.py', r'Node\(|node\.status = |update\(Node\)'), ('src/saintvision/services/storage.py', r'StorageContribution\(|contribution\.(status|revoked_at) = ')]:
    for i, line in enumerate(sources[path].decode('utf-8').splitlines(), 1):
        if re.search(pat, line): orm.append({'path': path, 'line': i, 'text': line.strip()[:120]})
out['ormWritersOfMatrixPublicTables'] = orm
out['matrixPublicWriters'] = {t: matrix['tables'][t] for t in ('public.nodes', 'public.storage_contributions')}


# 5. Source-level causal mutations: mutate the Git object bytes, re-run analyze().
def mutate(path, old, new, count=1):
    s = dict(sources); text = s[path].decode('utf-8-sig')
    assert text.count(old) >= 1, (path, old)
    s[path] = text.replace(old, new, count).encode('utf-8'); return s


def add_file(path, text):
    s = dict(sources); s[path] = text.encode('utf-8'); return s


BP = 'services/control-plane/src/inv/build_preparations.py'
NA = 'src/saintvision/identity/node_auth.py'
mutations = [
    ('S1-remove-known-lock_run-call-build_preparations223', 'DETECT', mutate(BP, 'run = lock_run(conn, preparation["run_id"], preparation["project_id"])', 'run = None')),
    ('S2-remove-orm-with_for_update-node_auth111', 'DETECT', mutate(NA, '.with_for_update()\n            .execution_options(populate_existing=True)', '\n            .execution_options(populate_existing=True)')),
    ('S3-add-aliased-lock_run-caller-new-module', 'DETECT', add_file('services/control-plane/src/inv/zz_reviewer_probe.py', 'from .leases import lock_run as _lr\n\n\ndef sneaky(conn, run_id):\n    return _lr(conn, run_id)\n')),
    ('S4-blindspot-dotted-import-call', 'BLIND_SPOT_PROBE', add_file('services/control-plane/src/inv/zz_reviewer_probe.py', 'import inv.leases\n\n\ndef sneaky(conn, run_id):\n    return inv.leases.lock_run(conn, run_id)\n')),
    ('S5-blindspot-instance-receiver-wrapper', 'BLIND_SPOT_PROBE', add_file('services/control-plane/src/inv/zz_reviewer_probe.py', 'from .leases import LeaseStore\n\n\ndef sneaky(db, conn, project, run_id):\n    store = LeaseStore(db)\n    return store._admit_locked(conn, project, run_id)\n')),
    ('S6-blindspot-sql-constant-inv-nodes-for-update', 'BLIND_SPOT_PROBE', add_file('services/control-plane/src/inv/zz_reviewer_probe.py', '_SQL = "SELECT node_id FROM inv.nodes WHERE node_id=%s FOR UPDATE"\n\n\ndef sneaky(conn, node_id):\n    return conn.execute(_SQL, (node_id,)).fetchone()\n')),
]
results = []
for label, expectation, srcs in mutations:
    t = time.time(); got = sc.analyze(srcs)
    names = {f for f in got['reachableFunctions'] if 'zz_reviewer_probe' in f}
    recs = [r for r in got['records'] if 'zz_reviewer_probe' in r['path']]
    results.append({'mutation': label, 'expectation': expectation, 'censusDiffersFromStored': not sc.audit_matches(stored, got),
                    'probeFunctionReached': sorted(names), 'probeRecords': [{k: r[k] for k in ('line', 'kind', 'currentModes', 'tables')} for r in recs],
                    'probeFileInScope': any('zz_reviewer_probe' in p for p in got['scopeFiles']), 'seconds': round(time.time() - t, 1)})
    print(json.dumps(results[-1]), flush=True)
out['sourceMutations'] = results
(HERE / 'census-audit-result.json').write_bytes((json.dumps(out, indent=2) + '\n').encode())
print(json.dumps({k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in out.items()}))
