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
from functools import lru_cache
from plan_specs import specialize
from rank_contract import RANK as CANONICAL_RANK,RANK_GROUPS as CANONICAL_GROUPS

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
RANK=CANONICAL_RANK
RANK_GROUPS=CANONICAL_GROUPS
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


@lru_cache(maxsize=100000)
def spelling(n):
    return ast.unparse(n) if n is not None else ''


def analyze(sources):
    spelling.cache_clear()
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

    type_sets={}
    def types(t):return set(type_sets[t]) if t in type_sets else {t}
    def join(ts):
        flat=set()
        for t in ts:flat.update(types(t))
        if len(flat)==1:return next(iter(flat))
        key='TYPE_JOIN:'+hashlib.sha256(repr(sorted(flat)).encode()).hexdigest()[:20]
        type_sets[key]=sorted(flat);return key
    environments = {}
    attrs = collections.defaultdict(dict)

    def lookup(p, expr, env, cls=None):
        if isinstance(expr,(ast.Dict,ast.DictComp)):return 'PY:dict'
        if isinstance(expr,(ast.List,ast.ListComp,ast.Tuple,ast.Set,ast.SetComp)):return 'PY:collection'
        if isinstance(expr,ast.Constant):return 'PY:str' if isinstance(expr.value,str) else 'PY:scalar'
        s = spelling(expr.func) if isinstance(expr,ast.Call) else spelling(expr)
        if isinstance(expr,ast.Subscript):
            parent=lookup(p,expr.value,env,cls)
            if parent.startswith(('PY:JSON','DB:Row')):return 'PY:JSONValue'
            if parent.startswith(('PY:dict','PY:Mapping')):return 'PY:ValueFromMapping'
            return parent
        if s in env:
            return env[s]
        if s.startswith(('self.', 'cls.')) and cls and s.count('.')==1:
            rest = s.split('.', 1)[1]
            if rest in attrs[cls]:
                return attrs[cls][rest]
            return cls + '.' + rest
        if isinstance(expr, ast.Call):
            if isinstance(expr.func,ast.Name) and expr.func.id=='getattr' and len(expr.args)>=2:
                recv=lookup(p,expr.args[0],env,cls)
                if isinstance(expr.args[1],ast.Constant) and isinstance(expr.args[1].value,str):return recv+'.'+expr.args[1].value
                return 'DYNAMIC_AUTHORITY_GETATTR:'+recv
            target = lookup(p, expr.func, env, cls)
            if target.startswith('builtins.') or isinstance(expr.func,ast.Name) and expr.func.id in ('dict','list','tuple','set'):
                return 'PY:dict' if spelling(expr.func).split('.')[-1]=='dict' else 'PY:collection'
            if target=='DB:SessionFactory':return 'DB:Session'
            if target.startswith(('json.loads','json.load')) or target.endswith(('.strict_json','.strict_json_loads')):return 'PY:JSONValue'
            if target in ('threading.Timer','subprocess.run','subprocess.Popen'):return 'STDLIB:'+target
            if target.endswith(('.make_session_factory','.sessionmaker')):return 'DB:SessionFactory'
            parent=lookup(p,expr.func.value,env,cls) if isinstance(expr.func,ast.Attribute) else ''
            method=expr.func.attr if isinstance(expr.func,ast.Attribute) else ''
            if target.startswith('psycopg.connect'):return 'DB:Connection'
            if parent=='DB:SessionFactory':return 'DB:Session'
            if method in ('transaction','begin','begin_nested') and (parent.startswith('DB:') or parent.endswith(('.Database','.BoundDatabase'))):return 'DB:Connection' if not parent.startswith('DB:Session') else parent
            if method in ('fetchone','fetchall','fetchmany') and (parent.startswith('DB:') or '.execute(' in spelling(expr.func.value)):return 'DB:RowMapping'
            if target=='types.SimpleNamespace':
                identity='NAMESPACE:'+modname(p)+':'+str(expr.lineno)+':'+str(expr.col_offset)
                for kw in expr.keywords:
                    if kw.arg:attrs[identity][kw.arg]=lookup(p,kw.value,env,cls)
                return identity
            if target in classes:
                return target
            if target in defs:
                ann = defs[target][1].returns
                if ann is not None:
                    return expand(defs[target][0], spelling(ann).split('[')[0].strip("'\""))
                fp,ff,fq=defs[target]
                returns=[r.value for r in ownwalk(ff) if isinstance(r,ast.Return) and r.value is not None]
                inferred=set()
                for value in returns:
                    if isinstance(value,ast.Name) and value.id in environments.get(target,{}):inferred.add(environments[target][value.id])
                    elif isinstance(value,ast.Call):
                        ctor=expand(fp,spelling(value.func))
                        if ctor in classes:inferred.add(ctor)
                    elif isinstance(value,(ast.Dict,ast.DictComp)):inferred.add('PY:dict')
                if len(inferred)==1:return next(iter(inferred))
            # ORM rows propagate through select/get/query/scalars/list wrappers.
            for n in ast.walk(expr):
                if isinstance(n, (ast.Name, ast.Attribute)):
                    hit = env.get(spelling(n),expand(p, spelling(n)))
                    if hit in models:
                        return hit
            if method in ('execute','executemany') and parent.startswith('DB:'):return 'DB:Cursor'
            if method in ('get','copy') and parent.startswith(('PY:dict','PY:Mapping','PY:JSON','DB:Row')):return 'PY:JSONValue'
            return 'UNRESOLVED_CALL_RETURN:'+modname(p)+':'+spelling(expr.func)
        if isinstance(expr, ast.Attribute):
            parent = lookup(p, expr.value, env, cls)
            if expr.attr=='__table__' and parent in models:return 'SQLTABLE:'+models[parent]
            candidate = parent + '.' + expr.attr
            if parent in type_sets:
                return join(attrs[t].get(expr.attr,t+'.'+expr.attr) for t in types(parent))
            if parent in classes or parent.startswith('NAMESPACE:'):
                if expr.attr in attrs[parent]:
                    return attrs[parent][expr.attr]
                return candidate
        return expand(p, s)

    def bind(p,t,v,env,cls):
        # Destructuring and chained assignment preserve each actual RHS type.
        if isinstance(t,(ast.Tuple,ast.List)):
            if isinstance(v,(ast.Tuple,ast.List)):
                star=next((i for i,x in enumerate(t.elts) if isinstance(x,ast.Starred)),None)
                for i,x in enumerate(t.elts):
                    if star is None:
                        if i<len(v.elts):bind(p,x,v.elts[i],env,cls)
                    elif i<star:bind(p,x,v.elts[i],env,cls)
                    elif i==star:env[spelling(x.value)]='PY:collection'
                    else:bind(p,x,v.elts[len(v.elts)-(len(t.elts)-i)],env,cls)
            else:
                for x in t.elts:env[spelling(x)]='UNRESOLVED_DESTRUCTURING:'+spelling(v)
            return
        value=lookup(p,v,env,cls);env[spelling(t)]=value
        if isinstance(t,ast.Attribute) and spelling(t.value) in ('self','cls') and cls:attrs[cls][t.attr]=value

    # Constructor/local/self attributes/annotated rows reach fixed point.
    for _ in range(5):
        for k, (p, fn, q) in defs.items():
            cls = modname(p) + '.' + '.'.join(q[:-1]) if len(q) > 1 else None
            env = dict(environments.get(k, {}))
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for a in fn.args.args + fn.args.kwonlyargs:
                    if a.annotation is not None:
                        ann=spelling(a.annotation).strip("'\"")
                        env[a.arg] = 'PY:Mapping' if re.search(r'\b(?:dict|Mapping)\b',ann) else 'DB:Session' if re.search(r'\bSession\b',ann) else expand(p,ann)
            for n in ownwalk(fn):
                if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None:
                    targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                    value = lookup(p, n.value, env, cls)
                    for t in targets:
                        bind(p,t,n.value,env,cls)
                elif isinstance(n, (ast.For, ast.AsyncFor)):
                    env[spelling(n.target)] = lookup(p, n.iter, env, cls)
                elif isinstance(n,(ast.With,ast.AsyncWith)):
                    for item in n.items:
                        if item.optional_vars is not None:env[spelling(item.optional_vars)]=lookup(p,item.context_expr,env,cls)
            environments[k] = env

    # Propagate constructor-typed arguments into instance helper parameters.
    # Example reserve(... lease_store=LeaseStore(...)) -> _reserve_speculative.
    injection_types=collections.defaultdict(set)
    for _ in range(12):
        injection_types.clear()
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
                    if target==k and isinstance(value,ast.Name) and value.id==name:continue # identity recursive forwarding adds no independent type constraint
                    typ = lookup(p, value, environments[k], cls)
                    injection_types[(target,name)].add(typ)
        for (target,name),injected in injection_types.items():
            # All discovered constructors/calls participate; no last-caller wins.
            environments[target][name]=join(injected)
        for k,(p,fn,q) in defs.items():
            cls=modname(p)+'.'+'.'.join(q[:-1]) if len(q)>1 else None
            env=environments[k]
            for n in ownwalk(fn):
                if isinstance(n,(ast.Assign,ast.AnnAssign)) and n.value is not None:
                    typ=lookup(p,n.value,env,cls)
                    for t in n.targets if isinstance(n,ast.Assign) else [n.target]:
                        bind(p,t,n.value,env,cls)
                elif isinstance(n,(ast.With,ast.AsyncWith)):
                    for item in n.items:
                        if item.optional_vars is not None:env[spelling(item.optional_vars)]=lookup(p,item.context_expr,env,cls)
                elif isinstance(n,(ast.For,ast.AsyncFor)):
                    env[spelling(n.target)]=lookup(p,n.iter,env,cls)

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
                left,right=sql_value(n.left,seen),sql_value(n.right,seen)
                if isinstance(n.op,ast.Add) and left and right and '<dynamic>' not in left+right:return left+right
                try:
                    val=ast.literal_eval(n.left) % ast.literal_eval(n.right) if isinstance(n.op,ast.Mod) else None
                    if isinstance(val,str):return val
                except (ValueError,TypeError,SyntaxError,KeyError):pass
                return left+'<dynamic>'+right
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
                        column=getattr(n, 'col_offset', 0),endLine=getattr(n,'end_lineno',None),endColumn=getattr(n,'end_col_offset',None), expression=expr,
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

                for match in re.finditer(r'pg_(?:try_)?advisory_(xact_)?lock(?:_shared)?\s*\(',sql,re.I):
                    result.append('TRANSACTION_ADVISORY' if match.group(1) else 'SESSION_ADVISORY_OFFLINE_ONLY')
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
                candidates=types(target)
                targets=sorted(t for t in candidates if t in defs)
                complete=all(t in defs for t in candidates)
                calls.append(dict(path=p, function=k, line=n.lineno, column=n.col_offset,
                                  spelling=s, targets=targets,endLine=n.end_lineno,endColumn=n.end_col_offset,
                                  resolution='EXACT_STATIC_TARGET' if complete else 'UNRESOLVED_STATIC_RECEIVER',resolutionComplete=complete,possibleReceiverTypes=sorted(types(lookup(p,n.func.value,env,cls))) if isinstance(n.func,ast.Attribute) else [],
                                  inferredTarget=target,
                                  receiverType=lookup(p,n.func.value,env,cls) if isinstance(n.func,ast.Attribute) else None,
                                  isDynamicGetattr=target.startswith('DYNAMIC_AUTHORITY_GETATTR:'),
                                  sourceOfType='source AST annotation/constructor/assignment/import/context-manager propagation',
                                  method=s.split('.')[-1]))
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
    # Normalized graph: closures reference local calls/records, never duplicate
    # all transitive paths or call dispositions into every source plan.
    plans=[dict(function=k,path=p,line=getattr(fn,'lineno',1),parameters=[a.arg for a in fn.args.args+fn.args.kwonlyargs] if hasattr(fn,'args') else [],
        rankedResourceLocks=[],discovery={'scopeKeys':[],'querySites':[]},recheck={'tables':[]},outerTransactionOwner='PENDING exact owner proof')
        for k,(p,fn,q) in defs.items() if k in reached]
    result=dict(source=BASE, analysis='STATIC_GIT_AST_ONLY', files=len(sources), modelTables=models,
                analysisToolSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                planSpecsSHA256=hashlib.sha256((E/'plan_specs.py').read_bytes()).hexdigest(),
                sourceFiles=[dict(path=p, sha256=hashlib.sha256(b).hexdigest()) for p, b in sorted(sources.items())],
                records=records, writers=writers, seedFunctions=sorted(seeds), reachableFunctions=sorted(reached),
                edges=edges, unknownEdges=unknown, functionPlans=plans, rankGroups=RANK_GROUPS,
                allCallSites=calls,
                warning='Not a proof of runtime dispatch or lock acquisition. Scoped unknown edges/tables are implementation blockers; no bare-method collision is authority proof.')
    from source_semantics import enhance
    result['valueConstructors']={}
    for k,(path,cls,q) in classes.items():
        dc=any('dataclass' in spelling(d) and 'frozen=True' in spelling(d) for d in cls.decorator_list)
        special=[k+'.'+n.name for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in ('__init__','__post_init__')]
        safe=dc and not cls.bases and not special and not any(isinstance(n,ast.Call) for x in cls.body if isinstance(x,(ast.Assign,ast.AnnAssign)) and x.value is not None for n in ast.walk(x.value) if x.value is not None) and not any(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and any('property' in spelling(d) for d in n.decorator_list) for n in cls.body)
        result['valueConstructors'][k]={'safeGeneratedValueInit':safe,'specialTargets':special,'path':path,'line':cls.lineno,'proof':'frozen dataclass; no bases, explicit init/post_init, property descriptors or called field defaults' if safe else 'not proven value-only initialization'}
    from writer_semantics import attach
    attach(sources,result)
    result['typeSets']=type_sets
    return enhance(sources,result)


if __name__ == '__main__':
    result = analyze(load_sources())
    import ctypes,os
    metrics={'scope':'this analysis process only','enforcedRAMLimit':None,'OSChanges':False,'reviewResourceContext':'prior reviewer190-356MiB; stream normalized ledgers and run bounded selected subsets, not a 74MB aggregate parse'}
    if os.name=='nt':
        class PMC(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        pm=PMC();pm.cb=ctypes.sizeof(pm)
        api=ctypes.windll.psapi.GetProcessMemoryInfo;api.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
        if api(ctypes.c_void_p(-1),ctypes.byref(pm),pm.cb):metrics.update(peakWorkingSetBytes=pm.PeakWorkingSetSize,workingSetBytes=pm.WorkingSetSize)
    result['memoryMetrics']=metrics
    from normalized import publish
    publish(result)
    print(json.dumps({k: len(result[k]) for k in ('records', 'writers', 'seedFunctions', 'reachableFunctions', 'edges', 'unknownEdges', 'functionPlans')}))
