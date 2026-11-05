"""Rev5 read-only Git AST census. No application imports, database or Node IO.

Inference is finite/static: unresolved relevant edges are explicit scoped BLOCKs,
never silently classified as MVCC/non-DB. Actual lock traces remain future.
"""
import ast
import collections
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
from plan_specs import specialize

E = Path(__file__).resolve().parent
ROOT = next(p for p in E.parents if (p / 'AGENTS.md').exists())
BASE = '72028cbac903c4415d9979f980a6e0f9948e914f'
DB = {'execute', 'executemany', 'execute_values', 'scalar', 'scalars', 'query',
      'get', 'refresh', 'with_for_update', 'add', 'add_all', 'delete', 'merge',
      'flush', 'bulk_insert_mappings', 'bulk_update_mappings'}
HELPERS = {'lock_run', 'lock_resources', 'require_execution'}
# Explicit ranks, including all observed locked classes. Not inferred alphabetical order.
RANK_GROUPS = [
 ['inv.control_epoch'], ['inv.tenant_controls'],
 ['inv.node_role_routing', 'inv.node_role_cohorts'], ['@transaction_advisory'],
 ['inv.nodes'], ['public.nodes'], ['public.storage_contributions'],
 ['inv.node_channels'], ['inv.node_role_current'], ['inv.projects'],
 ['inv.project_resource_limits', 'public.project_resource_limits'],
 ['inv.storage_budgets'], ['inv.shard_plans'], ['inv.approval_requests'],
 ['inv.runs'], ['inv.operator_grants'],
 ['inv.resources', 'public.node_capabilities', 'public.resource_offers'],
 ['inv.resource_claims', 'inv.storage_claims', 'public.resource_claims', 'inv.leases'],
 ['inv.transfers', 'inv.transfer_claims', 'inv.transfer_chunks', 'public.transfers'],
 ['inv.model_versions', 'inv.model_chunks', 'inv.model_locations', 'inv.models',
  'public.model_versions', 'public.models', 'public.model_chunks'],
 ['inv.storage_locations', 'inv.storage_samples', 'public.storage_locations',
  'public.storage_copies', 'public.storage_chunks', 'public.storage_manifests'],
 ['inv.build_preparations', 'inv.build_executions', 'inv.build_execution_jobs',
  'inv.terminal_commands', 'inv.terminal_sessions', 'inv.shards', 'inv.contexts',
  'public.projects', 'public.workspaces', 'public.files', 'public.file_versions',
  'public.contexts', 'public.context_items', 'public.context_sessions',
  'public.context_budgets', 'public.user_capabilities'],
 ['inv.nonces', 'inv.evidence', 'inv.audit', 'inv.audit_log',
  'inv.node_role_activation_ledger', 'public.evidence', 'public.lineage_events']]
# Remaining observed classes get explicit positions inside the appropriate stage.
RANK_GROUPS[2] += ['inv.project_nodes']
RANK_GROUPS[9] += ['inv.business_projects', 'public.project_kernel_link']
RANK_GROUPS[13] += ['inv.containment_approvals', 'inv.containment_requests']
RANK_GROUPS[14] += ['inv.business_runs', 'public.runs', 'inv.run_attempts']
RANK_GROUPS[15] += ['inv.business_admin_grants', 'inv.project_grants', 'inv.credential_grants',
                   'inv.business_subjects', 'public.users', 'public.project_members']
RANK_GROUPS[17] += ['inv.resource_leases', 'inv.tool_claims']
RANK_GROUPS[19] += ['inv.model_registry_bindings']
RANK_GROUPS[20] += ['inv.storage_objects', 'public.data_locations', 'public.data_replicas']
RANK_GROUPS[21] += ['inv.build_execution_admissions', 'inv.build_execution_intents',
                   'inv.execution_deliveries', 'inv.git_operations', 'inv.output_ingestions',
                   'inv.terminal_connections', 'inv.workspace_checkouts', 'inv.workspace_edits',
                   'public.workloads', 'public.workspace_edit_locks', 'inv.node_probes']
RANK_GROUPS[22] += ['inv.approval_dispatches', 'inv.approval_nonces', 'inv.idempotency',
                   'inv.outbox', 'public.audit_events']
RANK_GROUPS[16] += ['public.resource_pools']
RANK_GROUPS[15] += ['public.discovery_machine_credentials']
RANK_GROUPS[13] += ['public.approvals']
RANK_GROUPS[21] += ['public.artifacts', 'public.backup_records', 'public.node_announcements',
                   'public.release_acceptance_slots', 'public.release_manifests', 'public.acceptance_records']
RANK_GROUPS[22] += ['public.outbox_events']
RANK = {t: i for i, group in enumerate(RANK_GROUPS) for t in group}
TABLE = re.compile(r'\b(?:inv|public)\.[a-z_][a-z_0-9]*', re.I)
WRITE = re.compile(r'\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+((?:inv|public)\.[a-z_][a-z_0-9]*)', re.I)


def dump(path, obj):
    path.write_bytes((json.dumps(obj, ensure_ascii=True, indent=2) + '\n').encode())


def load_sources():
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE], cwd=ROOT).decode().splitlines()
    names = [p for p in names if p.endswith(('.py','.sql')) and not p.startswith(('docs/', 'tests/')) and '/tests/' not in p]
    raw = subprocess.check_output(['git', 'archive', BASE, *names], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(raw)) as ar:
        return {p: ar.extractfile(p).read() for p in names}


def modname(path):
    for prefix in ('services/control-plane/src/', 'src/'):
        if path.startswith(prefix):
            path = path[len(prefix):]
    return path.removesuffix('.py').replace('/', '.').removesuffix('.__init__')


def ownwalk(node):
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield from ownwalk(child)


def spelling(n):
    return ast.unparse(n) if n is not None else ''


def analyze(sources):
    trees = {p: ast.parse(b.decode('utf-8-sig')) for p, b in sources.items() if p.endswith('.py')}
    text = {p: b.decode('utf-8-sig') for p, b in sources.items()}
    source_lines={p:s.encode().splitlines(keepends=True) for p,s in text.items()}
    defs, classes, module_consts, imports, fimports = {}, {}, {}, {}, {}
    for p, tree in trees.items():
        mod = modname(p)
        bindings = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    # Python import a.b binds a, unlike import a.b as x.
                    bindings[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
            elif isinstance(n, ast.ImportFrom):
                depth = n.level - (1 if p.endswith('/__init__.py') else 0)
                prefix = (mod.split('.')[:-depth] if depth else mod.split('.')) if n.level else []
                target = '.'.join(prefix + ([n.module] if n.module else []))
                for a in n.names:
                    bindings[a.asname or a.name] = target + '.' + a.name
        imports[p] = bindings
        module_consts[p] = {t.id: n.value for n in tree.body if isinstance(n, ast.Assign)
                            for t in n.targets if isinstance(t, ast.Name)}

        def visit(n, scope=()):
            for c in ast.iter_child_nodes(n):
                if isinstance(c, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    q = scope + (c.name,)
                    k = mod + '.' + '.'.join(q)
                    if isinstance(c, ast.ClassDef):
                        classes[k] = (p, c, q)
                    else:
                        defs[k] = (p, c, q)
                    visit(c, q)
                else:
                    visit(c, scope)
        visit(tree)
        defs[mod + '.<module>'] = (p, tree, ())

    export_aliases = {}
    for p, binding in imports.items():
        for alias, target in binding.items():
            export_aliases[modname(p) + '.' + alias] = target

    def deref(s):
        seen = set()
        while s not in seen:
            seen.add(s)
            if s in export_aliases:
                s = export_aliases[s]
            else:
                break
        return s

    def expand(p, s):
        root, _, tail = s.partition('.')
        return deref(imports[p].get(root, modname(p) + '.' + root) + ('.' + tail if tail else ''))

    models = {}
    global_constants={modname(p)+'.'+name:(p,value) for p,values in module_consts.items() for name,value in values.items()}
    for k, (p, cls, q) in classes.items():
        tab = None
        schema = 'public'
        for n in cls.body:
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id == '__tablename__' and isinstance(n.value, ast.Constant):
                        tab = n.value.value
                    if isinstance(t, ast.Name) and t.id == '__table_args__':
                        m = re.search(r"['\"]schema['\"]:\s*['\"](\w+)['\"]", spelling(n.value))
                        if m:
                            schema = m.group(1)
        if tab:
            models[k] = schema + '.' + tab

    environments = {}
    attrs = collections.defaultdict(dict)

    def lookup(p, expr, env, cls=None):
        s = spelling(expr)
        if s in env:
            return env[s]
        if s.startswith(('self.', 'cls.')) and cls and s.count('.')==1:
            rest = s.split('.', 1)[1]
            if rest in attrs[cls]:
                return attrs[cls][rest]
            return cls + '.' + rest
        if isinstance(expr, ast.Call):
            target = lookup(p, expr.func, env, cls)
            if target in classes:
                return target
            if target in defs:
                ann = defs[target][1].returns
                if ann is not None:
                    return expand(defs[target][0], spelling(ann).split('[')[0].strip("'\""))
            # ORM rows propagate through select/get/query/scalars/list wrappers.
            for n in ast.walk(expr):
                if isinstance(n, (ast.Name, ast.Attribute)):
                    hit = env.get(spelling(n),expand(p, spelling(n)))
                    if hit in models:
                        return hit
        if isinstance(expr, ast.Attribute):
            parent = lookup(p, expr.value, env, cls)
            candidate = parent + '.' + expr.attr
            if parent in classes:
                if expr.attr in attrs[parent]:
                    return attrs[parent][expr.attr]
                return candidate
        return expand(p, s)

    # Constructor/local/self attributes/annotated rows reach fixed point.
    for _ in range(5):
        for k, (p, fn, q) in defs.items():
            cls = modname(p) + '.' + '.'.join(q[:-1]) if len(q) > 1 else None
            env = dict(environments.get(k, {}))
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for a in fn.args.args + fn.args.kwonlyargs:
                    if a.annotation is not None:
                        env[a.arg] = expand(p, spelling(a.annotation).strip("'\""))
            for n in ownwalk(fn):
                if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None:
                    targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                    value = lookup(p, n.value, env, cls)
                    for t in targets:
                        env[spelling(t)] = value
                        if isinstance(t, ast.Attribute) and spelling(t.value) in ('self', 'cls') and cls:
                            attrs[cls][t.attr] = value
                elif isinstance(n, (ast.For, ast.AsyncFor)):
                    env[spelling(n.target)] = lookup(p, n.iter, env, cls)
            environments[k] = env

    # Propagate constructor-typed arguments into instance helper parameters.
    # Example reserve(... lease_store=LeaseStore(...)) -> _reserve_speculative.
    for _ in range(4):
        for k, (p, fn, q) in defs.items():
            cls = modname(p) + '.' + '.'.join(q[:-1]) if len(q) > 1 else None
            for call in (n for n in ownwalk(fn) if isinstance(n, ast.Call)):
                target = lookup(p, call.func, environments[k], cls)
                if target in classes and target+'.__init__' in defs:
                    target=target+'.__init__'
                if target not in defs or not hasattr(defs[target][1], 'args'):
                    continue
                params = [a.arg for a in defs[target][1].args.args]
                if params and params[0] in ('self', 'cls'):
                    params = params[1:]
                supplied = dict(zip(params, call.args))
                supplied.update({kw.arg: kw.value for kw in call.keywords if kw.arg})
                for name, value in supplied.items():
                    typ = lookup(p, value, environments[k], cls)
                    if typ in classes:
                        environments[target][name] = typ
        for k,(p,fn,q) in defs.items():
            cls=modname(p)+'.'+'.'.join(q[:-1]) if len(q)>1 else None
            env=environments[k]
            for n in ownwalk(fn):
                if isinstance(n,(ast.Assign,ast.AnnAssign)) and n.value is not None:
                    typ=lookup(p,n.value,env,cls)
                    for t in n.targets if isinstance(n,ast.Assign) else [n.target]:
                        env[spelling(t)]=typ
                        if isinstance(t,ast.Attribute) and spelling(t.value) in ('self','cls') and cls:
                            attrs[cls][t.attr]=typ

    records, writers, calls = [], [], []
    for k, (p, fn, q) in defs.items():
        cls = modname(p) + '.' + '.'.join(q[:-1]) if len(q) > 1 else None
        env = environments[k]
        consts = dict(module_consts[p])
        for n in ownwalk(fn):
            if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None:
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    if isinstance(t, ast.Name):
                        consts[t.id] = n.value
            if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
                prior = consts.get(n.target.id)
                if prior is not None:
                    consts[n.target.id] = ast.BinOp(left=prior, op=ast.Add(), right=n.value)

        def sql_value(n, seen=frozenset()):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                return n.value
            if isinstance(n, ast.Name) and n.id in consts and n.id not in seen:
                return sql_value(consts[n.id], seen | {n.id})
            if isinstance(n,(ast.Name,ast.Attribute)):
                target=expand(p,spelling(n))
                if target in global_constants and target not in seen:
                    other_path,value=global_constants[target]
                    if isinstance(value,ast.Constant) and isinstance(value.value,str):return value.value
                    # Non-literal imported constants remain explicit unknown SQL.
            if isinstance(n, ast.BinOp):
                return sql_value(n.left, seen) + ' ' + sql_value(n.right, seen)
            if isinstance(n, ast.JoinedStr):
                return ''.join(sql_value(v, seen) if isinstance(v, ast.Constant) else '<dynamic>' for v in n.values)
            if isinstance(n, ast.Call):
                return ' '.join(sql_value(a, seen) for a in n.args)
            if isinstance(n, (ast.Tuple, ast.List)):
                return ' '.join(sql_value(a, seen) for a in n.elts)
            return ''

        def base(n, kind):
            # AST offsets are UTF8 bytes, not Unicode character indices.
            lines=source_lines[p];start=n.lineno-1;end=n.end_lineno-1
            fragment=(lines[start][n.col_offset:n.end_col_offset] if start==end else
                lines[start][n.col_offset:]+b''.join(lines[start+1:end])+lines[end][:n.end_col_offset])
            expr=fragment.decode() or spelling(n)
            return dict(source=BASE, path=p, function=k, line=getattr(n, 'lineno', 1),
                        column=getattr(n, 'col_offset', 0), expression=expr,
                        expressionSHA256=hashlib.sha256(expr.encode()).hexdigest(), kind=kind)

        def orm_tables(n):
            found = set()
            for c in ast.walk(n):
                if isinstance(c, (ast.Name, ast.Attribute)):
                    model = lookup(p, c, env, cls)
                    if model in models:
                        found.add(models[model])
            return found

        def modes(n, sql):
            result = sorted(set(re.findall(r'FOR\s+(?:NO\s+KEY\s+UPDATE|KEY\s+SHARE|UPDATE|SHARE)', sql.upper())))
            if re.search(r'pg_(?:try_)?advisory_(?:xact_)?lock', sql, re.I):
                result.append('TRANSACTION_ADVISORY' if 'xact' in sql.lower() else 'SESSION_ADVISORY_OFFLINE_ONLY')
            for c in ast.walk(n):
                if not isinstance(c, ast.Call):
                    continue
                name = spelling(c.func).split('.')[-1]
                opts = None
                if name == 'with_for_update':
                    opts = {kw.arg: spelling(kw.value) for kw in c.keywords}
                else:
                    for kw in c.keywords:
                        if kw.arg == 'with_for_update' and spelling(kw.value) != 'False':
                            if isinstance(kw.value, ast.Dict):
                                opts = {a.value: spelling(b) for a, b in zip(kw.value.keys, kw.value.values) if isinstance(a, ast.Constant)}
                            elif spelling(kw.value) == 'True':
                                opts = {}
                            else:
                                result.append('UNKNOWN_LOCK_OPTIONS_BLOCK')
                if opts is not None:
                    read = opts.get('read') == 'True'
                    key = opts.get('key_share') == 'True'
                    mode = 'FOR KEY SHARE' if read and key else 'FOR SHARE' if read else 'FOR NO KEY UPDATE' if key else 'FOR UPDATE'
                    for flag in ('skip_locked', 'nowait'):
                        if opts.get(flag) == 'True':
                            mode += ' ' + flag.replace('_',' ').upper()
                    if any(v not in ('True', 'False', 'None') for a, v in opts.items() if a not in ('of',)):
                        mode += ' UNKNOWN_DYNAMIC_OPTION_BLOCK'
                    result.append(mode)
            return sorted(set(result))

        for n in ownwalk(fn):
            if isinstance(n, ast.Call):
                s = spelling(n.func)
                target = lookup(p, n.func, env, cls)
                if target in classes and target+'.__init__' in defs:
                    target=target+'.__init__'
                targets = [target] if target in defs else []
                calls.append(dict(path=p, function=k, line=n.lineno, column=n.col_offset,
                                  spelling=s, targets=targets,
                                  resolution='EXACT_STATIC_TARGET' if targets else 'UNRESOLVED_STATIC_RECEIVER',
                                  inferredTarget=target))
                method = s.split('.')[-1]
                if method in DB and not targets:
                    sql = sql_value(n.args[0]) if n.args else ''
                    # Qualified function names and GUCs are not table locks.
                    sql_tables = re.findall(r'\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+((?:inv|public)\.[a-z_][a-z_0-9]*)', sql, re.I)
                    ts = sorted(set(sql_tables) | orm_tables(n))
                    ms = modes(n, sql)
                    if 'ADVISORY' in ' '.join(ms):
                        ts = sorted(set(ts) | {'@transaction_advisory'})
                    if ts or ms or method in ('execute', 'executemany', 'execute_values', 'with_for_update'):
                        r = base(n, 'SQL' if sql.strip() else 'ORM_OR_UNRESOLVED_DB')
                        external=s in ('self._adapter.execute',)
                        unresolved=method in ('execute','executemany') and not sql.strip() and not ts and not external
                        r.update(tables=ts, modes=ms, resolvedSQL=sql,unresolvedSQL=unresolved,
                                 scopeDisposition='UNKNOWN_SQL_SCOPE_BLOCK_THIS_ENTRY' if unresolved else 'PROVEN_EXTERNAL_ADAPTER_IO' if external else 'STATIC_NAMED_SCOPE')
                        records.append(r)
                        for m in WRITE.finditer(sql):
                            verb, table = m.group(1).split()[0].upper(), m.group(2).lower()
                            fragment = sql[m.start():]
                            if verb == 'INSERT':
                                col = re.match(r'INSERT\s+INTO\s+\S+\s*\(([^)]+)\)', fragment, re.I)
                                cols = [c.strip() for c in col.group(1).split(',')] if col else ['UNKNOWN_COLUMNS_BLOCK']
                            elif verb == 'UPDATE':
                                part = re.split(r'\bSET\b', fragment, maxsplit=1, flags=re.I)
                                tail = re.split(r'\bWHERE\b|\bRETURNING\b', part[1], maxsplit=1, flags=re.I)[0] if len(part) > 1 else ''
                                cols = sorted(set(re.findall(r'\b([a-z_][a-z_0-9]*)\s*=(?!=)', tail, re.I))) or ['UNKNOWN_COLUMNS_BLOCK']
                            else:
                                cols = ['ROW_DELETE']
                            w = dict(r, verb=verb, table=table, columns=cols)
                            writers.append(w)
                    # ORM UPDATE/DELETE must be taken from the executing chain.
                    if method in ('execute', 'scalar', 'scalars'):
                        for c in ast.walk(n):
                            if isinstance(c, ast.Call) and spelling(c.func).split('.')[-1] in ('update', 'delete') and c.args:
                                model = lookup(p, c.args[0], env, cls)
                                if model in models:
                                    verb = spelling(c.func).split('.')[-1].upper()
                                    cols = set()
                                    for v in ast.walk(n):
                                        if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == 'values':
                                            cols.update(kw.arg for kw in v.keywords if kw.arg)
                                    writers.append(dict(base(n, 'ORM_DML'), table=models[model], verb=verb,
                                                        columns=sorted(cols) if cols else ['ROW_DELETE' if verb == 'DELETE' else 'UNKNOWN_COLUMNS_BLOCK']))
                if target in models:
                    writers.append(dict(base(n, 'ORM_CONSTRUCTOR'), table=models[target], verb='INSERT',
                                        columns=sorted(kw.arg for kw in n.keywords if kw.arg)))
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                for t in targets:
                    if isinstance(t, ast.Attribute):
                        model = lookup(p, t.value, env, cls)
                        if model in models:
                            writers.append(dict(base(n, 'ORM_ATTRIBUTE'), table=models[model], verb='UPDATE', columns=[t.attr]))

    # Include SQL migrations/trigger/function bodies. They are not AST imports.
    for p,raw in sources.items():
        if not p.endswith('.sql'):continue
        original_sql=raw.decode('utf-8-sig')
        # Ignore comments without changing source byte/line offsets.
        sql=re.sub(r'--[^\n]*|/\*[\s\S]*?\*/',lambda m:''.join('\n' if c=='\n' else ' ' for c in m.group(0)),original_sql)
        for match in WRITE.finditer(sql):
            start=match.start();end=sql.find(';',start)
            expr=sql[start:end if end>=0 else len(sql)]
            functions=list(re.finditer(r'CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+([a-z_.]+)',sql[:start],re.I))
            # Function body scope ends at the next dollar quote after body start.
            enclosing=None
            if functions:
                f=functions[-1];tail=sql[f.end():start]
                if tail.count('$$')==1:enclosing=f.group(1)
            fn='SQL:'+p+':'+(enclosing or '<migration>')
            line=sql.count('\n',0,start)+1
            defs.setdefault(fn,(p,ast.Module(body=[],type_ignores=[]),()))
            table=match.group(2).lower();verb=match.group(1).split()[0].upper()
            col=re.match(r'INSERT\s+INTO\s+\S+?\s*\(([^)]+)\)',expr,re.I)
            cols=[x.strip() for x in col.group(1).split(',')] if col else ['UNKNOWN_COLUMNS_BLOCK']
            if verb=='UPDATE':
                cols=sorted(set(re.findall(r'\b([a-z_][a-z_0-9]*)\s*=(?!=)',re.split(r'\bWHERE\b',expr,flags=re.I)[0],re.I)))
            elif verb=='DELETE':cols=['ROW_DELETE']
            writers.append(dict(source=BASE,path=p,function=fn,line=line,column=0,expression=expr,
                expressionSHA256=hashlib.sha256(expr.encode()).hexdigest(),kind='SQL_FUNCTION_OR_MIGRATION',
                table=table,verb=verb,columns=cols))
        for match in re.finditer(r'FOR\s+(?:NO\s+KEY\s+UPDATE|KEY\s+SHARE|UPDATE|SHARE)\b',sql,re.I):
            start=sql.rfind(';',0,match.start())+1;end=sql.find(';',match.end())
            expr=sql[start:end if end>=0 else len(sql)]
            functions=list(re.finditer(r'CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+([a-z_.]+)',sql[:match.start()],re.I))
            fn='SQL:'+p+':'+(functions[-1].group(1) if functions else '<migration>')
            defs.setdefault(fn,(p,ast.Module(body=[],type_ignores=[]),()))
            ts=sorted(set(re.findall(r'\b(?:FROM|JOIN|UPDATE)\s+((?:inv|public)\.[a-z_][a-z_0-9]*)',expr,re.I)))
            records.append(dict(source=BASE,path=p,function=fn,line=sql.count('\n',0,match.start())+1,
                column=0,expression=expr,expressionSHA256=hashlib.sha256(expr.encode()).hexdigest(),
                kind='SQL_ROUTINE_ROWLOCK',tables=ts,modes=[match.group(0).upper()],
                resolvedSQL=expr,unresolvedSQL=not bool(ts)))

    # Dedup nested executing wrappers by exact source identity, preserving real writers.
    def unique(items, fields):
        out = {}
        for r in items:
            key = tuple(json.dumps(r.get(f), sort_keys=True) for f in fields)
            out[key] = r
        return sorted(out.values(), key=lambda r: (r['path'], r['line'], r['column']))
    writers = unique(writers, ['path', 'line', 'column', 'table', 'verb', 'columns'])
    # Seed EVERY observed row/advisory locker, not only three helper names.
    seeds = {r['function'] for r in records if r['modes'] or r['unresolvedSQL']} | {w['function'] for w in writers}
    seeds |= {k for k in defs if k.split('.')[-1] in HELPERS}
    reached = set(seeds)
    while True:
        more = {c['function'] for c in calls if set(c['targets']) & reached}
        if more <= reached:
            break
        reached |= more
    edges = [c for c in calls if set(c['targets']) & reached]
    relevant_names = {k.split('.')[-1] for k in reached}
    unknown = [dict(c, disposition='BLOCK_THIS_ENTRY_UNTIL_STATIC_RESOLUTION_OR_ACTUAL_TRACE') for c in calls
               if not c['targets'] and c['spelling'].split('.')[-1] in relevant_names
               and c['spelling'].split('.')[-1] != '__init__']
    forward = collections.defaultdict(set)
    for c in edges:
        forward[c['function']].update(c['targets'])
    local = collections.defaultdict(list)
    for r in records:
        local[r['function']].append(r)
    plans = []
    for k in sorted(reached):
        seen, todo = set(), [k]
        while todo:
            v = todo.pop()
            if v in seen:
                continue
            seen.add(v)
            todo.extend(forward[v] - seen)
        relevant = [r for f in sorted(seen) for r in local[f]]
        locks = sorted({(t, mode) for r in relevant for t in r['tables'] for mode in r['modes']}, key=lambda x: (RANK.get(x[0], 999), x))
        p, fn, q = defs[k]
        args = [a.arg for a in fn.args.args + fn.args.kwonlyargs] if hasattr(fn, 'args') else []
        plan = dict(function=k, path=p, line=getattr(fn, 'lineno', 1), parameters=args,
                    discoveredTables=sorted({t for r in relevant for t in r['tables']}),
                    originalLexicalLocks=[dict(line=r['line'], tables=r['tables'], modes=r['modes']) for r in local[k] if r['modes']],
                    unresolvedDbSites=[dict(line=r['line'],expression=r['expression'],disposition='BLOCK_THIS_ENTRY_UNTIL_TYPED_SQL_OR_CALLER_FORWARDING_IS_PROVEN') for r in relevant if r['unresolvedSQL']],
                    transitiveFunctions=sorted(seen),
                    rankedResourceLocks=[dict(table=t, mode=m, rank=RANK.get(t),
                                              disposition='NAMED_RANK' if t in RANK else 'UNKNOWN_LOCKED_TABLE_BLOCK') for t, m in locks],
                    outerTransactionOwner=('offline maintenance operator; exclusive no-B-traffic prerequisite' if p.startswith('tools/') else k + ' caller transaction; fixed SD guard must be first lock acquisition'),
                    discovery=dict(scopeKeys=args, querySites=[dict(function=r['function'], line=r['line'], tables=r['tables']) for r in relevant if r['tables']],
                                   rule='derive complete tenant/Node/run/project/contribution/resource keys using the listed queries without locks; Node set comes from persisted associations, never request profile'),
                    recheck=dict(tables=sorted({t for r in relevant for t in r['tables']}),
                                 rule='compare exact discovered keys/versions/status/current lineage and authorization under ranked locks before effects; late earlier-rank key aborts entire transaction and replans'),
                    externalIO=[dict(line=n.lineno, expression=spelling(n.func)) for n in ownwalk(fn) if isinstance(n, ast.Call) and re.search(r'http|request|transport|send|adapter', spelling(n.func), re.I)],
                    rewrite='replace original inversions, do not bless source lexical order; external Node/network/filesystem IO outside transaction with durable intent then exact outcome reconciliation',
                    actualPGTrace=False)
        specialize(plan)
        plans.append(plan)
    return dict(source=BASE, analysis='STATIC_GIT_AST_ONLY', files=len(sources), modelTables=models,
                analysisToolSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                planSpecsSHA256=hashlib.sha256((E/'plan_specs.py').read_bytes()).hexdigest(),
                sourceFiles=[dict(path=p, sha256=hashlib.sha256(b).hexdigest()) for p, b in sorted(sources.items())],
                records=records, writers=writers, seedFunctions=sorted(seeds), reachableFunctions=sorted(reached),
                edges=edges, unknownEdges=unknown, functionPlans=plans, rankGroups=RANK_GROUPS,
                warning='Not a proof of runtime dispatch or lock acquisition. Scoped unknown edges/tables are implementation blockers; known required entries have explicit plans. No global B refusal substitute.')


if __name__ == '__main__':
    result = analyze(load_sources())
    dump(E / 'source-analysis.json', result)
    print(json.dumps({k: len(result[k]) for k in ('records', 'writers', 'seedFunctions', 'reachableFunctions', 'edges', 'unknownEdges', 'functionPlans')}))
