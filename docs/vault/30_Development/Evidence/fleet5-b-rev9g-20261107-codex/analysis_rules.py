"""Rev9 bounded rules. Source AST only; no application import or mutant execution.

The immutable Rev8 body proof is retained behind stricter binding/mutation checks.
RULE_NOT_APPLICABLE stays UNRESOLVED; no missing proof becomes a pure exemption.
"""
import ast,hashlib,importlib.util
from pathlib import Path
E=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('immutable_rev8_body_rules',E.parent/'fleet5-b-rev8-revoke-portcut-20261106-codex/bounded_analysis.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
# The retained AST body predicates never read their module's global manifest.
# Keep one live census (bounded_analysis.M), rather than a duplicate unused copy.
old.M=None
def span(n):return n.lineno,n.col_offset,n.end_lineno,n.end_col_offset
def text(n):return ast.unparse(n)
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def root_name(n):
    while isinstance(n,(ast.Attribute,ast.Subscript)):n=n.value
    return n.id if isinstance(n,ast.Name) else None
def bound_names(node):
    if isinstance(node,(ast.Import,ast.ImportFrom)):return [a.asname or (a.name.split('.')[0] if isinstance(node,ast.Import) else a.name) for a in node.names]
    if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):return [node.name]
    if isinstance(node,ast.Name) and isinstance(node.ctx,(ast.Store,ast.Del)):return [node.id]
    return []
def exact_import(tree,name,module,level=0):
    binds=[n for n in ast.walk(tree) if name in bound_names(n)]
    return len(binds)==1 and isinstance(binds[0],ast.ImportFrom) and binds[0].module==module and binds[0].level==level and any(a.name==name and not a.asname for a in binds[0].names)
def constructor_binding(caller,name='DomainError'):
    t=ast.parse(caller)
    import use_sites as u
    proof,error=u.module_uses(caller,instances=False)
    return exact_import(t,name,'errors',1) and proof is not None and error is None
def error_initializer(source,class_name):
    t=ast.parse(source);classes=[n for n in t.body if isinstance(n,ast.ClassDef) and n.name==class_name]
    if len(classes)!=1 or classes[0].keywords:return False
    if not exact_import(t,'dataclass','dataclasses'):return False
    if any('Exception' in bound_names(n) for n in ast.walk(t)):return False
    field_used=any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='field' for n in ast.walk(classes[0]))
    if field_used and not exact_import(t,'field','dataclasses'):return False
    if not field_used and any('field' in bound_names(n) and not (isinstance(n,ast.ImportFrom) and n.module=='dataclasses') for n in ast.walk(t)):return False
    class_binds=[n for n in ast.walk(t) if class_name in bound_names(n)]
    if len(class_binds)!=1 or class_binds[0] is not classes[0]:return False
    if dynamic_module_mutation(t,{class_name,'dataclass','Exception','field','ErrorCategory','_STATUS','_RETRYABLE'}):return False
    if class_name=='InvError':
        if not exact_import(t,'Enum','enum'):return False
        if len([n for n in ast.walk(t) if 'ErrorCategory' in bound_names(n)])!=1:return False
    # Defaults/decorators on methods execute at class construction, even when
    # those methods themselves are not called by __init__.
    for f in [n for n in classes[0].body if isinstance(n,ast.FunctionDef)]:
        if f.decorator_list or any(isinstance(n,ast.Call) for d in f.args.defaults+f.args.kw_defaults if d is not None for n in ast.walk(d)):return False
    return old.error_initializer(source,class_name)
def producer_sanity(source,call,records,calls):
    tree=ast.parse(source)
    current=next((n for n in ast.walk(tree) if isinstance(n,ast.Call) and span(n)==span(call)),None)
    if current is None or ast.dump(current,include_attributes=False)!=ast.dump(call,include_attributes=False):return None,'STALE_CALL_SPAN'
    inner=call.func.value if isinstance(call.func,ast.Attribute) else None
    if not isinstance(inner,ast.Call):return None,'RULE_NOT_APPLICABLE'
    record=next((r for r in records if span(inner)==(r['line'],r['column'],r['endLine'],r['endColumn'])),None)
    resolved=next((c for c in calls if span(inner)==(c['line'],c['column'],c['endLine'],c['endColumn']) and c['classification']=='RESOLVED_DB_RECORD'),None)
    if not record or not resolved:return None,'MISSING_PRODUCER_RECORD'
    if record['unresolvedSQL'] or sha(ast.get_source_segment(source,inner))!=record['expressionSHA256']:return None,'MISSING_PRODUCER_RECORD'
    return {'parse':True,'currentCallSpan':list(span(call)),'sourceSHA256':sha(source),'producerExpressionSHA256':record['expressionSHA256'],'producerRecord':record,'producerCallRef':resolved['id']},None
def cursor_result_explain(source,call,records,calls):
    sanity,error=producer_sanity(source,call,records,calls)
    if error:return {'proof':None,'reason':error,'producerSanity':False}
    inner=call.func.value
    if not isinstance(inner.func,ast.Attribute) or not isinstance(inner.func.value,ast.Name):return {'proof':None,'reason':'RULE_NOT_APPLICABLE','producerSanity':True}
    receiver=inner.func.value.id
    fn=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.lineno<=call.lineno<=n.end_lineno)
    allowed=[id(i.optional_vars) for n in ast.walk(fn) if isinstance(n,ast.With) for i in n.items if isinstance(i.optional_vars,ast.Name) and i.optional_vars.id==receiver and isinstance(i.context_expr,ast.Call) and text(i.context_expr.func)=='conn.cursor']
    import use_sites as u
    _,reason=u.module_uses(source,instances=False)
    if reason:return {'proof':None,'reason':reason,'producerSanity':True}
    _,reason=u.receiver_uses(source,fn,{receiver},allowed,records=records,calls=calls)
    if reason:return {'proof':None,'reason':reason,'producerSanity':True}
    proof=old.cursor_result(source,call,records,calls)
    if proof:proof.update(rule='A1_CURSOR_HARDENED',producerSanity=sanity,mutationScan='name/attribute/delete/setattr/delattr/class/alias/escape checked')
    return {'proof':proof,'reason':None if proof else 'RULE_NOT_APPLICABLE','producerSanity':True}
def cursor_result(source,call,records,calls):return cursor_result_explain(source,call,records,calls)['proof']

def connection_result_explain(source,call,records,calls,db_source,owner_proof):
    sanity,error=producer_sanity(source,call,records,calls)
    if error:return {'proof':None,'reason':error,'producerSanity':False}
    import t1_provenance as t
    union,error=t.observed_union(db_source)
    if error or not owner_proof or owner_proof.get('status')!='SOURCE_PROVEN_RUNTIME_PENDING' or owner_proof.get('dbSourceSHA256')!=sha(db_source):return {'proof':None,'reason':error or 'RECEIVER_UNION_UNPROVEN','producerSanity':True}
    if call.func.attr not in ('fetchone','fetchall'):return {'proof':None,'reason':'RULE_NOT_APPLICABLE','producerSanity':True}
    inner=call.func.value
    if not isinstance(inner.func,ast.Attribute) or not isinstance(inner.func.value,ast.Name) or inner.func.attr!='execute' or inner.func.value.id not in ('conn','observed_conn'):return {'proof':None,'reason':'RULE_NOT_APPLICABLE','producerSanity':True}
    receiver=inner.func.value.id;fn=next(f for f in t.qualified_functions(source).values() if f.lineno<=call.lineno<=f.end_lineno)
    allowed=[];aliases=[];owner_context=None
    if fn.name=='mark_offline':
        if owner_proof['NodeObservationDbUnion']!=['inv.db.Database']:return {'proof':None,'reason':'RECEIVER_UNION_UNPROVEN','producerSanity':True}
        for n in ast.walk(fn):
            if isinstance(n,ast.With):
                for i in n.items:
                    if isinstance(i.optional_vars,ast.Name) and i.optional_vars.id=='conn' and isinstance(i.context_expr,ast.Call) and text(i.context_expr.func)=='self.db.transaction':
                        allowed.append(id(i.optional_vars));owner_context={'span':list(span(i.context_expr)),'expressionSHA256':sha(ast.get_source_segment(source,i.context_expr))}
            if isinstance(n,ast.Attribute) and text(n)=='self.db' and isinstance(n.ctx,(ast.Store,ast.Del)):return {'proof':None,'reason':'DYNAMIC_BLOCK:SELF_DB_REBIND','producerSanity':True}
        if receiver!='conn' or not owner_context:return {'proof':None,'reason':'RECEIVER_UNION_UNPROVEN','producerSanity':True}
    elif fn.name=='transaction' and sha(source)==sha(db_source):
        for n in ast.walk(fn):
            if isinstance(n,ast.With):
                for i in n.items:
                    if isinstance(i.optional_vars,ast.Name) and i.optional_vars.id=='conn' and isinstance(i.context_expr,ast.Call) and text(i.context_expr.func)=='psycopg.connect':allowed.append(id(i.optional_vars));owner_context={'span':list(span(i.context_expr)),'genuineCredentialPort':'P-DBROLE_RUNTIME_PENDING'}
            if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='observed_conn':allowed.append(id(n.targets[0]));aliases.append(id(n))
        if not owner_context:return {'proof':None,'reason':'RECEIVER_UNION_UNPROVEN','producerSanity':True}
    else:return {'proof':None,'reason':'RULE_NOT_APPLICABLE','producerSanity':True}
    if any(isinstance(n,ast.Name) and n.id=='self' and isinstance(n.ctx,(ast.Store,ast.Del)) for n in ast.walk(fn)):return {'proof':None,'reason':'DYNAMIC_BLOCK:SELF_REBIND','producerSanity':True}
    import use_sites as u
    _,reason=u.module_uses(source,instances=False)
    if reason:return {'proof':None,'reason':reason,'producerSanity':True}
    _,reason=u.receiver_uses(source,fn,{'conn','observed_conn'},allowed,aliases,records,calls,allow_yield=fn.name=='transaction')
    if reason:return {'proof':None,'reason':reason,'producerSanity':True}
    proof={'classification':'RESOLVED_DB_CURSOR_RESULT','rule':'A1c_CONNECTION_UNION','producerSanity':sanity,'receiver':receiver,'receiverUnionProof':union,'transactionOwner':owner_context,
      'retainsDatabaseReadWriteAndControlFlow':True,'tables':sanity['producerRecord']['tables'],'lockModes':sanity['producerRecord']['modes'],'runtimeBinding':None}
    return {'proof':proof,'reason':None,'producerSanity':True}

# Namespace access is an allowlist of individual bounded contexts, with aliases
# resolved. Retain this API for the immutable reviewer scripts; no denylist is
# used to manufacture proof after an unrecognized access.
def dynamic_module_mutation(tree,names):
    import use_sites as u
    _,error=u.module_uses(ast.unparse(tree),instances=False)
    return error is not None
