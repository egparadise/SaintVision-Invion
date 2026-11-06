"""Finite source census, receiver stores and reverse argument forwarding.

This deliberately stops at unproven owners/modes. A name such as database is
never treated as a Database instance. No product is imported or executed.
"""
import ast,re
import call_binding as cb,callee_identity as ci,reflection_audit as ra,use_sites as u
from a7_common import *

CARRIERS={'inv.node_transfer.NodeTransfer','inv.node_transport.NodeDelivery','inv.observation.NodeObservation'}

def key(f,n):return [f.path,f.enclosing(n),n.lineno,n.col_offset]

def mode(call):
    values=[x.value for x in call.keywords if x.arg=='observation_only']
    if any(x.arg is None for x in call.keywords):return {'state':'UNRESOLVED','reason':'keyword spread may supply foreign mode','blocksGrant':True}
    if not values:return {'state':'SOURCE_LITERAL','purpose':'NORMAL','value':False,'origin':'snapshot default False; no runtime type check'}
    if len(values)!=1:return {'state':'UNRESOLVED','reason':'duplicate mode','blocksGrant':True}
    n=values[0]
    if isinstance(n,ast.Constant) and type(n.value) in (bool,int,float,str,type(None)):
        return {'state':'SOURCE_LITERAL','purpose':'OBSERVATION' if bool(n.value) else 'NORMAL','value':n.value,'origin':'Python literal truthiness; not an exact-bool runtime rule'}
    return {'state':'UNRESOLVED','expression':text(n),'reason':'foreign/dynamic truthiness requires complete caller and value provenance','blocksGrant':True}

def census(world=None):
    world=world or {};queries=[];paths,q=grep(r'NodeChannels|node_channels|\.snapshot[[:space:]]*\(');queries.append(q)
    paths=sorted(set(paths)|set(world));constructors=[];snapshots=[];other=[];files=[];guards=[];failures=[];selected={};carrier_rows=[];frozen_keys=[]
    for path in paths:
        source=get(path,world);f=Facts(path,source)
        old=Facts(path,frozen_source(path))
        frozen_keys.extend(key(old,n) for n in ast.walk(old.tree) if isinstance(n,ast.Call) and old.resolve(n.func)==TARGET)
        # Parse the complete lexical candidate universe, but retain only the
        # necessary call/import owners, not every SQL node_channels reference.
        relevant=any(isinstance(n,ast.Call) and (f.resolve(n.func)==TARGET or isinstance(n.func,ast.Attribute) and n.func.attr=='snapshot') for n in ast.walk(f.tree)) or path in (NC,CT,DB,ER)
        files.append({'path':path,'sha256':sha(source),'bytes':len(source.encode()),'parsed':True,'retainedForCallClosure':relevant})
        if not relevant:continue
        selected[path]=source
        audit=ra.audit(f,PROTECTED)
        if audit['newRelevantHits']:failures.append(obligation('A7_RELEVANT_REFLECTION',audit['newRelevantHits'],path))
        uses,error=u.module_uses(source,path,instances=True,factories=(),parameter_context={})
        guards.append({'path':path,'reflection':audit,'useSites':uses,'error':error,'meaning':'frozen no-new-use compatibility, not callable purity/type proof'})
        if error:failures.append(obligation('A7_FULL_MODULE_USE_SITE_GUARD',error,path))
        fields={}
        for qname,fn in f.functions.items():
            if not qname.endswith('.__init__'):continue
            owner=qname.rsplit('.',1)[0]
            for n in ast.walk(fn):
                if not isinstance(n,ast.Assign) or not isinstance(n.value,ast.Call) or f.resolve(n.value.func)!=TARGET:continue
                for dst in n.targets:
                    if not isinstance(dst,ast.Attribute) or text(dst.value)!='self':continue
                    stores=[x for x in ast.walk(f.classes[owner]) if isinstance(x,ast.Attribute) and isinstance(x.ctx,(ast.Store,ast.Del)) and text(x)==text(dst)]
                    if len(stores)==1:fields[(owner,dst.attr)]=n
                    else:failures.append(obligation('A7_CHANNEL_RECEIVER_REBOUND',text(dst),witness(f,n)))
        for call in ast.walk(f.tree):
            if not isinstance(call,ast.Call):continue
            target=f.resolve(call.func)
            if target==TARGET:
                reason=ci.caller_error(f,call)
                row={'target':target,'source':witness(f,call),'key':key(f,call),'databaseExpression':text(call.args[0]) if call.args else None,'argumentShape':shape(call),'callerBinding':getattr(f,'_caller_binding_proofs',{}).get(tuple(witness(f,call)['span'])),'bindingError':reason,'ownerState':'UNRESOLVED_DATABASE_INPUT_TYPE'}
                constructors.append(row)
                if reason:failures.append(obligation('A7_CONSTRUCTOR_BINDING',reason,row['source']))
                if len(call.args)!=1 or call.keywords:failures.append(obligation('A7_CONSTRUCTOR_ARGUMENTS','not the exact one positional database contract',row['source']))
            elif isinstance(call.func,ast.Name) and call.func.id=='NodeChannels':
                failures.append(obligation('A7_CONSTRUCTOR_WRONG_TARGET',target or 'unbound NodeChannels',witness(f,call)))
            if not isinstance(call.func,ast.Attribute) or call.func.attr!='snapshot':continue
            receiver=call.func.value;origin=None;kind=None
            if isinstance(receiver,ast.Call) and f.resolve(receiver.func)==TARGET:origin=receiver;kind='INLINE_AUTHENTICATED_CONSTRUCTOR_PENDING_DB_OWNER'
            elif isinstance(receiver,ast.Attribute) and isinstance(receiver.value,ast.Name) and receiver.value.id=='self':
                owner=f.enclosing(call).rsplit('.',1)[0];store=fields.get((owner,receiver.attr))
                if store is not None:origin=store.value;kind='SINGLE_CLASS_INIT_ATTRIBUTE_STORE_PENDING_OUTER_OWNER'
            row={'source':witness(f,call),'key':key(f,call),'receiver':text(receiver),'purpose':mode(call)}
            if origin is None:
                row.update({'state':'OTHER_SNAPSHOT_RECEIVER_UNRESOLVED_NOT_NONAUTHORITY','blocksGrantForThisReceiver':True});other.append(row);continue
            row.update({'target':SNAP,'receiverKind':kind,'constructorKey':key(f,origin),'constructor':witness(f,origin),'argumentBinding':'source receiver relation only; receiver escapes/type/caller closure still required'})
            mapping,error=cb.arguments(call,Facts(NC,get(NC,world)).functions['NodeChannels.snapshot'],True)
            row['argumentError']=error
            if error:failures.append(obligation('A7_SNAPSHOT_ARGUMENTS',error,row['source']))
            if row['purpose']['state']=='UNRESOLVED':failures.append(obligation('A7_PURPOSE_PROVENANCE',row['purpose'],row['source']))
            snapshots.append(row)
        for owner in sorted({f.enclosing(c).rsplit('.',1)[0] for c in ast.walk(f.tree) if isinstance(c,ast.Call) and f.resolve(c.func)==TARGET and f.enclosing(c).endswith('.__init__')}):
            carrier_rows.append({'symbol':f.module+'.'+owner,'path':path,'init':witness(f,f.functions[owner+'.__init__'])})
    if sorted({tuple(x['key']) for x in constructors})!=sorted({tuple(x) for x in frozen_keys}):failures.append(obligation('A7_CONSTRUCTOR_CENSUS_CHANGED','frozen source constructor keys must be preserved'))
    return {'source':SOURCE,'queries':queries,'sourceFiles':files,'constructorSites':sorted(constructors,key=lambda x:x['key']),'snapshotSites':sorted(snapshots,key=lambda x:x['key']),'otherSnapshotReceivers':other,'carrierClasses':carrier_rows,'guards':guards,'obligations':failures,'selectedSources':selected,'scope':'finite textual/import-aware source census; dynamic aliases/heap roots not declared complete'}

def reverse_forwarding(c,world=None):
    """Derive source call sites of database-forwarding carriers, not their types.

    Existing binder checks authenticate imports and signatures; arbitrary call
    results, attributes and unclosed root formals remain explicit obligations.
    """
    world=world or {};sources=dict(c['selectedSources']);queue=[];seen=set();events=[];queries=[];obligations=[];roots=[]
    for row in c['carrierClasses']:queue.append((row['symbol'],row['path'],'database'))
    # Direct constructor call expressions are all retained; these are not all
    # reducible to a formal or a certified factory with this bounded proof.
    for row in c['constructorSites']:
        roots.append({'source':row['source'],'expression':row['databaseExpression'],'state':'UNRESOLVED_DATABASE_TYPE_AND_ROOT_CLOSURE','blocksGrant':True})
        path=row['source']['path'];sf=Facts(path,get(path,world));caller=row['source']['function'].removeprefix(sf.module+'.');fn=sf.functions.get(caller)
        if fn is None:continue
        expression=ast.parse(row['databaseExpression'],mode='eval').body
        formals={a.arg for a in fn.args.posonlyargs+fn.args.args+fn.args.kwonlyargs}
        if isinstance(expression,ast.Name) and expression.id in formals:
            queue.append((sf.module+'.'+caller.removesuffix('.__init__'),path,expression.id))
        elif isinstance(expression,ast.Attribute) and text(expression).startswith('self.') and '.' in caller:
            cls=caller.split('.')[0];init=sf.functions.get(cls+'.__init__')
            if init:
                import t1_provenance as t
                for a in init.args.args[1:]:
                    if t.local_field_proof(sf.source,cls,expression.attr,a.arg):queue.append((sf.module+'.'+cls,path,a.arg));break
    while queue:
        symbol,defpath,param=queue.pop(0);state=(symbol,defpath,param)
        if state in seen:continue
        seen.add(state)
        if len(seen)>24:
            obligations.append(obligation('A7_FORWARDING_BOUND','24 source-symbol reverse states exhausted'));break
        df=Facts(defpath,get(defpath,world));short=symbol.rsplit('.',1)[-1];qname=symbol.removeprefix(df.module+'.')
        fn=df.functions.get(qname+'.__init__') or df.functions.get(qname)
        if fn is None:obligations.append(obligation('A7_FORWARDING_SIGNATURE',symbol));continue
        paths,q=grep(r'\b'+re.escape(short)+r'\b');queries.append(q);paths=sorted(set(paths)|set(world))
        for path in paths:
            sf=Facts(path,get(path,world))
            for call in ast.walk(sf.tree):
                if not isinstance(call,ast.Call) or sf.resolve(call.func)!=symbol:continue
                sources[path]=sf.source;reason=ci.caller_error(sf,call);mapping,error=cb.arguments(call,fn,qname in df.classes)
                value=(mapping or {}).get(param);row={'callee':symbol,'parameter':param,'source':witness(sf,call),'value':text(value) if value is not None else None,'bindingError':reason or error,'callerBinding':getattr(sf,'_caller_binding_proofs',{}).get(tuple(witness(sf,call)['span'])),'state':'MAY_FORWARD_ONLY_NOT_DATABASE_TYPE'};events.append(row)
                if reason or error:obligations.append(obligation('A7_REVERSE_BINDING',reason or error,row['source']));continue
                caller=sf.enclosing(call);callerfn=sf.functions.get(caller);formal={a.arg for a in callerfn.args.posonlyargs+callerfn.args.args+callerfn.args.kwonlyargs} if callerfn else set()
                if isinstance(value,ast.Name) and value.id in formal:
                    if value.id=='self':obligations.append(obligation('A7_FORWARD_SELF_UNPROVEN',row,row['source']));continue
                    forwarded=caller.removesuffix('.__init__') if caller.endswith('.__init__') else caller
                    queue.append((sf.module+'.'+forwarded,path,value.id));row['forwardingFormal']=value.id
                elif isinstance(value,ast.Attribute) and text(value).startswith('self.') and '.' in caller:
                    cls=caller.split('.')[0];init=sf.functions.get(cls+'.__init__');matched=False
                    if init:
                        import t1_provenance as t
                        for a in init.args.args[1:]:
                            if t.local_field_proof(sf.source,cls,value.attr,a.arg):queue.append((sf.module+'.'+cls,path,a.arg));row['forwardingConstructorField']=value.attr;matched=True;break
                    if not matched:obligations.append(obligation('A7_FORWARD_FIELD_UNPROVEN',row,row['source']))
                else:obligations.append(obligation('A7_FORWARD_ROOT_TYPE_UNPROVEN',row,row['source']))
    for root in roots:obligations.append(obligation('A7_DATABASE_OWNER_CLOSURE',root['expression'],root['source']))
    return {'queries':queries,'states':[list(x) for x in sorted(seen)],'events':events,'directDatabaseInputs':roots,'obligations':obligations,'sourceFiles':[{'path':p,'sha256':sha(s),'bytes':len(s.encode())} for p,s in sorted(sources.items())],'sources':sources,'completeness':'UNRESOLVED; finite source argument census, no dynamic heap/type resolver, genuine Database owners not asserted'}

def prove(world=None):
    c=census(world);r=reverse_forwarding(c,world);obligations=c['obligations']+r['obligations'];guards=[]
    # Necessary forwarded callers receive the same current finite refusal guards.
    for path,source in sorted(r.pop('sources').items()):
        f=Facts(path,source);a=ra.audit(f,PROTECTED);uses,error=u.module_uses(source,path,instances=True,factories=(),parameter_context={})
        guards.append({'path':path,'reflection':a,'useSites':uses,'error':error})
        if a['newRelevantHits'] or error:obligations.append(obligation('A7_FORWARD_GUARD',error or a['newRelevantHits'],path))
    c.pop('selectedSources');return {'callerClosureAccepted':not obligations,'census':c,'forwarding':r,'forwardedGuards':guards,'obligations':obligations,'runtimeBinding':None,'actualRuntimeB':0}
