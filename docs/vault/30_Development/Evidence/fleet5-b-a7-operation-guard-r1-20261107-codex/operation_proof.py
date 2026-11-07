"""One finite mode-origin graph. AST/data only; no delivery/effect admission."""
import ast,hashlib,json,subprocess,sys
from contextlib import contextmanager
from pathlib import Path
E=Path(__file__).resolve().parent;R=next(p for p in E.parents if (p/'AGENTS.md').exists());OLD=E.parent/'fleet5-b-a7-snapshot-r2-20261107-codex';sys.path.insert(0,str(OLD))
from source_bindings import Facts,sha,text,SOURCE as HELPER_BASELINE
import call_binding as cb,callee_identity as ci,reflection_audit as ra,use_sites as u,owner_transfer as ot
CP='services/control-plane/src/inv/';DC=CP+'dispatch.py';NT=CP+'node_transport.py';WK=CP+'worker.py';REMOTE='tools/remote_workspace_entry.py'
SYMBOLS={'inv.node_transport.NodeDelivery','inv.dispatch.DeliveryWorker','inv.dispatch.DeliveryQueue','inv.dispatch.DeliveryAttempt'}
PATTERN=r'NodeDelivery|DeliveryWorker|DeliveryAttempt|DeliveryQueue|node_transport|from[[:space:]].*dispatch|import[[:space:]].*dispatch|\.deliver\b'
SOURCE='b3bbdc8d92a39f2f797a7680deb2770d6f705af0'

def frozen_source(path):
    # First-party proof input is real BASE Git, not the historical guard baseline.
    return subprocess.check_output(['git','show',SOURCE+':'+path],cwd=R,stderr=subprocess.PIPE).decode('utf-8-sig')
def emit(name,data):(E/name).write_bytes((json.dumps(data,sort_keys=True,indent=2)+'\n').encode())
def source(path,world):return world[path] if path in world else frozen_source(path)
def shape(n):return ast.dump(n,include_attributes=False)
@contextmanager
def scope():
    old=(u.PROTECTED_PREFIXES,set(u.PROTECTED_CLASS_NAMES),ot.PREFIXES,set(ra.MODULES),set(ra.NAMES))
    u.PROTECTED_PREFIXES+=('inv.node_transport','inv.dispatch');u.PROTECTED_CLASS_NAMES.update(x.rsplit('.',1)[-1] for x in SYMBOLS);ot.PREFIXES+=('inv.node_transport','inv.dispatch');ra.MODULES.update({'inv.node_transport','inv.dispatch'});ra.NAMES.update(x.rsplit('.',1)[-1] for x in SYMBOLS)
    u.baseline_sites.cache_clear();u.baseline_owners.cache_clear();ra.frozen_hits.cache_clear()
    try:yield
    finally:
        u.PROTECTED_PREFIXES,u.PROTECTED_CLASS_NAMES,ot.PREFIXES,ra.MODULES,ra.NAMES=old;u.baseline_sites.cache_clear();u.baseline_owners.cache_clear();ra.frozen_hits.cache_clear()
def rule(facts):
    """Direct mode-layer predicate, separate from the older no-new-use guard."""
    d,n=facts[DC],facts[NT];functions,classes=cb.registry(facts);edges=[]
    def fail(code,detail):return {'status':'UNRESOLVED','reason':code,'detail':detail,'edges':edges,'acceptedDischarge':False}
    for f,q in ((d,'DeliveryQueue'),(d,'DeliveryWorker'),(d,'DeliveryAttempt'),(n,'NodeDelivery')):
        error=ci.construction(f,q,classes)
        if error:return fail('EARLIER_CALLEE_BINDING',error)
    for f in facts.values():
        for c in ast.walk(f.tree):
            if not isinstance(c,ast.Call):continue
            resolved=f.resolve(c.func)
            if resolved not in SYMBOLS and not (isinstance(c.func,ast.Name) and c.func.id in {'DeliveryAttempt','DeliveryWorker','DeliveryQueue','NodeDelivery'}):continue
            error=ci.caller_error(f,c)
            if error or resolved not in SYMBOLS:return fail('EARLIER_CALLEE_BINDING',error or str(resolved))
    deliver=n.functions['NodeDelivery.deliver'];once=d.functions['DeliveryWorker.once'];acquire=d.functions['DeliveryQueue.acquire'];init=d.functions['DeliveryWorker.__init__']
    if shape(deliver.args)!=shape(ast.parse('def deliver(self,node,permit,*,observation_only=False,cancel_only=False): pass').body[0].args):return fail('DELIVER_SIGNATURE_CHANGED','not the original defaults/signature')
    edges.append({'kind':'SIGNATURES_AND_DEFAULTS','deliver':{'source':n.witness(deliver),'argumentAST':shape(deliver.args),'observation_onlyDefault':False,'cancel_onlyDefault':False,'runtimeExactBoolValidation':False},'once':{'source':d.witness(once),'argumentAST':shape(once.args)},'acquire':{'source':d.witness(acquire),'argumentAST':shape(acquire.args)}})
    if any(isinstance(x,ast.Name) and x.id in {'observation_only','cancel_only'} and isinstance(x.ctx,(ast.Store,ast.Del)) for x in ast.walk(deliver)):return fail('FLAG_PARAMETER_REBOUND','original forwarded parameters must not be reassigned')
    first=init.body[0]
    if text(first)!='self.queue, self.delivery = (DeliveryQueue(database), delivery)':return fail('WORKER_RECEIVER_STORE_CHANGED',text(first))
    edges.append({'kind':'CONDITIONAL_RECEIVER_FIELD_STORES','source':d.witness(first),'premise':'genuine unchanged DeliveryWorker and DeliveryQueue instances; field ownership is not proved by spelling'})
    acalls=[c for c in ast.walk(once) if isinstance(c,ast.Call) and text(c.func)=='self.queue.acquire'];calls=[c for c in ast.walk(once) if isinstance(c,ast.Call) and text(c.func)=='self.delivery.deliver'];snap=[c for c in ast.walk(deliver) if isinstance(c,ast.Call) and text(c.func)=='self.channels.snapshot']
    if len(acalls)!=1 or len(calls)!=1 or len(snap)!=1:return fail('MODE_CALL_GRAPH_CHANGED','expected one acquire/deliver/snapshot site')
    a=acalls[0];parent=d.parent[id(a)]
    if not isinstance(parent,ast.Assign) or [text(x) for x in parent.targets]!=['attempt']:return fail('ATTEMPT_FORWARDING_CHANGED',text(parent))
    if len([x for x in ast.walk(once) if isinstance(x,ast.Name) and x.id=='attempt' and isinstance(x.ctx,(ast.Store,ast.Del))])!=1:return fail('ATTEMPT_LOCAL_REBOUND','the acquire result must be the sole local attempt binding')
    guards=[x for x in once.body if isinstance(x,ast.If) and text(x.test)=='attempt is None']
    if len(guards)!=1 or not isinstance(guards[0].body[-1],ast.Return):return fail('ATTEMPT_NONE_GUARD_CHANGED','None branch must return rather than reach the delivery call')
    tries=[x for x in once.body if isinstance(x,ast.Try)]
    capture=ast.parse('operation = attempt.operation').body[0]
    exact_guard=ast.parse('if type(operation) is not str or operation not in ("execute", "observe", "cancel"):\n    raise ValueError("Unsupported delivery operation origin")').body[0]
    if len(tries)!=1 or len(tries[0].body)!=3 or shape(tries[0].body[0])!=shape(capture) or shape(tries[0].body[1])!=shape(exact_guard) or not isinstance(tries[0].body[2],ast.Expr) or tries[0].body[2].value is not calls[0]:return fail('OPERATION_CAPTURE_GUARD_CHANGED','capture, exact guard, and existing direct deliver must be the three ordered try statements')
    opstores=[x for x in ast.walk(once) if isinstance(x,ast.Name) and x.id=='operation' and isinstance(x.ctx,(ast.Store,ast.Del))]
    opreads=[x for x in ast.walk(once) if isinstance(x,ast.Attribute) and x.attr=='operation']
    if len(opstores)!=1 or len(opreads)!=1 or opreads[0] is not tries[0].body[0].value or any(isinstance(x,(ast.Global,ast.Nonlocal)) and 'operation' in x.names for x in ast.walk(once)):return fail('OPERATION_CAPTURE_NOT_SINGLE_READ','no extra operation store or attribute read in once is allowed')
    edges.append({'kind':'OPERATION_CAPTURE_AND_EXACT_DOMAIN_GUARD','capture':d.witness(tries[0].body[0]),'guard':d.witness(tries[0].body[1]),'singleAttributeRead':d.witness(opreads[0]),'builtinPremises':['genuine builtin type, str and ValueError bindings','the property read itself can execute code; only the captured result is type/domain checked'],'failureBoundary':'inside existing try; non-DomainError maps to SYS-0001/not_sent=False; earlier reconciliation/acquire have happened'})
    mapping,error=cb.arguments(calls[0],deliver,True)
    if error:return fail('EARLIER_ARGUMENT_BINDING',error)
    wanted={'observation_only':"operation == 'observe'",'cancel_only':"operation == 'cancel'"}
    actual={k:text(mapping[k]) for k in wanted if k in mapping}
    edges.append({'kind':'MODE_FORWARD_ARGUMENT_BINDING','source':d.witness(calls[0]),'callNodeKind':type(calls[0]).__name__,'calleeAttributeSource':d.witness(calls[0].func),'calleeNodeKind':type(calls[0].func).__name__,'directProjectionVerified':d.parent[id(calls[0].func)] is calls[0] and calls[0].func is d.parent[id(calls[0].func)].func,'actual':actual,'receiverPremise':'self.delivery is the NodeDelivery constructor result, not an arbitrary duck adapter'})
    if actual!=wanted:return fail('MODE_FORWARDING_CHANGED',actual)
    expr=next((x.value for x in snap[0].keywords if x.arg=='observation_only'),None)
    if expr is None or shape(expr)!=shape(ast.parse('observation_only or cancel_only',mode='eval').body):return fail('OR_OPERAND_EXPRESSION_CHANGED',text(expr) if expr else None)
    edges.append({'kind':'SNAPSHOT_OR_OPERAND_FORWARD','source':n.witness(snap[0]),'expression':text(expr),'semantics':'truth-test left; return left if truthy, else return right unchanged; no bool coercion/type validation is added'})
    stores=[x for x in ast.walk(acquire) if isinstance(x,ast.Name) and x.id=='operation' and isinstance(x.ctx,(ast.Store,ast.Del))]
    if len(stores)!=3 or any(isinstance(x,(ast.Global,ast.Nonlocal)) and 'operation' in x.names for x in ast.walk(acquire)):return fail('OPERATION_LOCAL_BINDING_CHANGED',len(stores))
    def literals(x):
        if isinstance(x,ast.Constant) and type(x.value) is str:return {x.value}
        if isinstance(x,ast.IfExp):
            left,right=literals(x.body),literals(x.orelse);return left|right if left is not None and right is not None else None
        return None
    union=set();assignments=[]
    for store in stores:
        stmt=d.parent[id(store)];values=literals(stmt.value) if isinstance(stmt,ast.Assign) else None
        assignments.append({'source':d.witness(stmt),'valueAST':text(stmt.value) if isinstance(stmt,ast.Assign) else text(stmt),'literalValues':sorted(values) if values is not None else None,'branchAncestors':[d.witness(p) for p in ancestors(d,stmt) if isinstance(p,ast.If)]})
        if values is None:return fail('UNRESOLVED_DYNAMIC_OPERATION_ORIGIN',assignments)
        union|=values
    if union!={'execute','observe','cancel'}:return fail('OPERATION_LITERAL_DOMAIN_CHANGED',sorted(union))
    attempts=[c for c in ast.walk(acquire) if isinstance(c,ast.Call) and d.resolve(c.func)=='inv.dispatch.DeliveryAttempt']
    if len(attempts)!=1 or len(attempts[0].args)!=7 or text(attempts[0].args[5])!='operation' or attempts[0].keywords:return fail('ATTEMPT_CONSTRUCTOR_FORWARDING_CHANGED','seven declared fields, sixth argument operation')
    returns=[x for x in ast.walk(acquire) if isinstance(x,ast.Return) and x.value is not None and not (isinstance(x.value,ast.Constant) and x.value.value is None)]
    if len(returns)!=1 or returns[0].value is not attempts[0]:return fail('FOREIGN_ACQUIRE_RETURN','all other normal returns must be None')
    fields=[x.target.id for x in d.classes['DeliveryAttempt'].body if isinstance(x,ast.AnnAssign) and isinstance(x.target,ast.Name)]
    if fields!=['node','project_id','run_id','command_id','token','operation','envelope'] or [text(x) for x in d.classes['DeliveryAttempt'].decorator_list]!=['dataclass(frozen=True)']:return fail('ATTEMPT_DECLARATION_CHANGED',fields)
    decorator=d.classes['DeliveryAttempt'].decorator_list[0]
    if d.resolve(decorator.func)!='dataclasses.dataclass' or ci.caller_error(d,decorator):return fail('EARLIER_DATACLASS_IMPORT_BINDING','not the frozen canonical dataclass import')
    edges.extend([{'kind':'LITERAL_OPERATION_ASSIGNMENTS','assignments':assignments,'literalUnion':sorted(union),'notProven':'which branch is permitted, SQL/DB/clock effects and rich condition comparisons are outside this value-origin proof'}, {'kind':'CONDITIONAL_DATACLASS_ARGUMENT_TO_FIELD','source':d.witness(attempts[0]),'classDeclaration':d.witness(d.classes['DeliveryAttempt']),'fieldOrder':fields,'premise':'genuine dataclasses decorator/generated initializer, genuine returned object and faithful unchanged plain operation field; annotation str is not proof of runtime type'}])
    return {'status':'CONDITIONAL_CAPTURED_MODE_ORIGIN_CANDIDATE','reason':None,'edges':edges,'acceptedDischarge':False,'operationMatrix':[{'operation':x,'observation_only':x=='observe','cancel_only':x=='cancel','snapshotMode':'NORMAL' if x=='execute' else 'OBSERVATION'} for x in sorted(union)],'premises':['genuine bound NodeDelivery / DeliveryWorker / DeliveryQueue methods and source constructors; no unmodelled heap/callback/frame mutation','genuine builtin type, str, ValueError and exception handler bindings','attempt.operation capture itself and earlier reconciliation/acquire effects remain outside the captured-value type/domain guarantee','scoped aliases and reflection are bounded source evidence, not universal dynamic caller/heap completeness'],'runtimeVerification':'NOT_RUN locally; Root must run actual-import unit and causal baseline RED tests in bounded isolation; no runtime/permission or 19-obligation discharge'}
def ancestors(f,n):
    while id(n) in f.parent:n=f.parent[id(n)];yield n
def reference_contract(refs,mode):
    """Project the actual forwarding Call.func, never compare Call to Attribute."""
    edges=[e for e in mode['edges'] if e['kind']=='MODE_FORWARD_ARGUMENT_BINDING']
    edge=edges[0] if len(edges)==1 else None
    valid=(len(refs)==1 and edge is not None and edge['callNodeKind']=='Call' and edge['calleeNodeKind']=='Attribute' and edge['directProjectionVerified'] is True)
    if valid:
        ref=refs[0]
        valid=(ref['kind']=='CALL' and ref['nodeKind']=='Attribute' and ref['directParentKind']=='Call' and ref['isParentFunc'] is True and ref['source']==edge['calleeAttributeSource'] and ref['parentCallSource']==edge['source'])
    return {'status':'CONDITIONAL_EXACT_SINGLE_FORWARD_REFERENCE' if valid else 'UNRESOLVED','reason':None if valid else 'DELIVER_REFERENCE_SET_CHANGED','referenceCount':len(refs),'forwardingCallSource':edge['source'] if edge else None,'projectedAttributeSource':edge['calleeAttributeSource'] if edge else None,'binding':'current path + fileSHA256 + function + span + expressionSHA256 AND actual AST node kinds/direct Call.func parent relation; not text/name/span alone','acceptedDischarge':False}

def analyze(world=None):
    world={DC:(R/DC).read_bytes().decode('utf-8-sig'),**(world or {})};argv=['git','grep','-l','-E',PATTERN,SOURCE,'--','services/control-plane/src','src','tools'];p=subprocess.run(argv,cwd=R,stdout=subprocess.PIPE,stderr=subprocess.PIPE);assert p.returncode in (0,1)
    paths=sorted({s.split(':',1)[1] for s in p.stdout.decode('utf8').splitlines() if s.endswith('.py')}|set(world));assert len(paths)<=32
    facts={};files=[];ctors=[];refs=[];guards=[]
    with scope():
        for path in paths:
            f=Facts(path,source(path,world));ra_result=ra.audit(f,SYMBOLS);uses,error=u.module_uses(f.source,path,instances=True,factories=(),parameter_context={});files.append({'path':path,'sha256':sha(f.source),'bytes':len(f.source.encode())});guards.append({'path':path,'sha256':sha(f.source),'reflection':ra_result,'useSites':uses,'error':error})
            if path in {DC,NT,WK,REMOTE}:facts[path]=f
            for c in ast.walk(f.tree):
                if isinstance(c,ast.Call) and f.resolve(c.func) in SYMBOLS:
                    symbol=f.resolve(c.func);pair=facts.get(DC) if symbol.startswith('inv.dispatch.') else facts.get(NT);reason=ci.caller_error(f,c);ctors.append({'target':symbol,'source':f.witness(c),'arguments':[text(x) for x in c.args],'keywords':{x.arg:text(x.value) for x in c.keywords},'callerBindingError':reason,'callerBinding':getattr(f,'_caller_binding_proofs',{}).get(tuple(f.witness(c)['span'])),'ownerState':'CONSTRUCTOR_SOURCE_BINDING_ONLY_NOT_GENUINE_RUNTIME_TYPE'})
                if isinstance(c,ast.Attribute) and c.attr=='deliver':
                    parent=f.parent.get(id(c));direct=isinstance(parent,ast.Call) and parent.func is c
                    refs.append({'source':f.witness(c),'expression':text(c),'kind':'CALL' if direct else 'UNRESOLVED_METHOD_REFERENCE_ESCAPE','nodeKind':type(c).__name__,'directParentKind':type(parent).__name__,'isParentFunc':direct,'parentCallSource':f.witness(parent) if direct else None})
        assert {r['path']:r['sha256'] for r in files}=={r['path']:r['sha256'] for r in guards}
        for row in ctors:
            owner,q=row['target'].rsplit('.',1);definition=facts[DC if owner=='inv.dispatch' else NT].functions.get(q+'.__init__')
            f=facts.get(row['source']['path'])
            if definition is not None and f is not None:
                call=next(c for c in ast.walk(f.tree) if isinstance(c,ast.Call) and f.witness(c)['span']==row['source']['span']);mapping,error=cb.arguments(call,definition,True);row['formalArgumentBinding']={k:text(v) for k,v in (mapping or {}).items()};row['argumentError']=error
            else:row['formalArgumentBinding']='Generated dataclass initializer is a named genuine-decorator premise, not a supplied source signature'
        mode=rule(facts)
    forwarding=[]
    for row in ctors:
        if row['target']!='inv.dispatch.DeliveryWorker':continue
        f=facts[row['source']['path']];arg=row['formalArgumentBinding'].get('delivery');entry={'consumer':row['source'],'deliveryArgument':arg,'state':'CONDITIONAL_SOURCE_FORWARDING_NOT_RUNTIME_OWNER_PROOF'}
        if arg=='delivery':
            assigns=[x for x in ast.walk(f.functions['main']) if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='delivery' for t in x.targets)];entry['localStores']=[f.witness(x) for x in assigns];entry['producerExpressions']=[text(x.value) for x in assigns]
        elif arg=='a.delivery':
            stores=[x for x in ast.walk(f.functions['setup']) if isinstance(x,ast.Assign) and any(text(t)=='a.delivery' for t in x.targets)];entry['namespaceStores']=[f.witness(x) for x in stores];entry['setupCall']=[f.witness(x) for x in ast.walk(f.functions['execute']) if isinstance(x,ast.Call) and text(x.func)=='setup'];entry['premise']='faithful returned SimpleNamespace a, no replacement of its delivery attribute across other calls'
        else:entry['inlineConstructorExpression']=arg
        forwarding.append(entry)
    contract=reference_contract(refs,mode)
    return {'source':SOURCE,'overlay':{'path':DC,'sha256':sha(world[DC]),'kind':'CURRENT_WIP_DISPATCH'},'historicalGuardBaseline':HELPER_BASELINE,'query':{'argv':argv,'exit':p.returncode,'outputSHA256':hashlib.sha256(p.stdout).hexdigest()},'parsedScope':files,'auditedScope':guards,'parsedEqualsAudited':True,'constructorInventory':ctors,'constructorArgumentBindingsValid':all(not x.get('argumentError') and not x.get('callerBindingError') for x in ctors),'workerDeliveryForwarding':forwarding,'deliverReferences':refs,'referenceContract':contract,'modeRule':mode,'guardCompatibilityClean':all(not g['reflection']['newRelevantHits'] and g['error'] is None for g in guards),'scopeBound':'Complete observed references/constructors in the explicit lexical production universe, not arbitrary computed imports/aliases/heap/language; unknown receivers remain premises','independentReview':'PENDING through Root','originalBaseline19Unchanged':True,'actualRuntimeB':0,'realBindings':None,'unadmitted':['NodeDelivery delivery/network/receipt/Engine/SQL/DB/PKI/observer/clock effects or permission','10 DB owners and8 reverse roots','full runtime/caller/source inclusion/port acceptance']}

def verdict(result):
    if result['referenceContract']['reason']:
        return {'status':'UNRESOLVED_OPERATION_ORIGIN','reason':result['referenceContract']['reason']}
    if result['modeRule']['reason']:
        return {'status':'UNRESOLVED_OPERATION_ORIGIN','reason':result['modeRule']['reason']}
    if not result['guardCompatibilityClean']:
        return {'status':'UNRESOLVED_OPERATION_ORIGIN','reason':'EXISTING_GUARD_REFUSED_WIP_PATTERN'}
    if not result['constructorArgumentBindingsValid']:
        return {'status':'UNRESOLVED_OPERATION_ORIGIN','reason':'EARLIER_CONSTRUCTOR_ARGUMENT_BINDING'}
    return {'status':'CONDITIONAL_SOURCE_CANDIDATE_RUNTIME_AND_OWNER_PREMISES_PENDING','reason':None}
def main():
    sys.stdout.reconfigure(encoding='utf8');result=analyze();emit('operation-origin-graph.json',result)
    decision=verdict(result)
    baseline=json.loads((OLD/'a7-snapshot-sidecar.json').read_bytes())['callers']['obligations'];target=[o for o in baseline if o['code']=='A7_PURPOSE_PROVENANCE'];assert len(baseline)==19 and len(target)==1
    emit('operation-obligation-auxiliary.json',{'target':target[0],'candidate':result['modeRule'],'referenceContract':result['referenceContract'],'scopedGuardsClean':result['guardCompatibilityClean'],'guardRefusals':[{'path':g['path'],'error':g['error'],'reflection':g['reflection']['newRelevantHits']} for g in result['auditedScope'] if g['error'] or g['reflection']['newRelevantHits']],'independentReview':'PENDING','actualProductTests':'NOT_RUN locally, Root bounded isolation pending','acceptedBaselineDischarges':0,'originalBaseline19Unchanged':True,'baselineObligationListSHA256':sha(json.dumps(baseline,sort_keys=True)),**decision,'actualRuntimeB':0,'realBindings':None});print(json.dumps({'parsed':len(result['parsedScope']),'audited':len(result['auditedScope']),'constructors':len(result['constructorInventory']),'deliverReferences':len(result['deliverReferences']),'rule':result['modeRule']['status'],'referenceContract':result['referenceContract']['status'],'guardClean':result['guardCompatibilityClean'],'verdict':decision,'baselineDischarges':0}))
if __name__=='__main__':main()
