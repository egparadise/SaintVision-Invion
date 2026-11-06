"""Selected T1/A8 AST negatives with reparsed/rebased producer evidence."""
import ast,json
from copy import deepcopy
import bounded_analysis as a
import analysis_rules as r
import t1_provenance as t
from mutation_fixture import rebase,after_line
E=a.E;R=[]
def check(name,value,**data):
    R.append({'case':name,'pass':bool(value),**data})
    if not value:raise AssertionError(name)
def main():
    core=t.read_batch([t.CP+n for n in t.CORE]+['tools/remote_workspace_entry.py']);ctors=t.read_batch(t.MAIN_CTOR_PATHS)
    owner,error=t.provenance(core,ctors);check('A8-actual-production-graph',not error,reason=error)
    calls=[c for c in a.rows('classifiedCalls') if c['function'] in ('inv.db.Database.transaction','inv.observation.NodeObservation.mark_offline')]
    records=[x for x in a.rows('records') if x['function'] in ('inv.db.Database.transaction','inv.observation.NodeObservation.mark_offline')]
    targets=[c for c in calls if c['blocksGrant'] and isinstance(a.node_at(core[c['path']],c).func,ast.Attribute) and a.node_at(core[c['path']],c).func.attr in ('fetchone','fetchall')]
    check('A1c-exact-five-positive-edges',len(targets)==5)
    for target in targets:
        path=target['path'];source=core[path];cs=[c for c in calls if c['path']==path];rs=[x for x in records if x['path']==path]
        result=r.connection_result_explain(source,a.node_at(source,target),rs,cs,core[t.CP+'db.py'],owner)
        check('A1c-baseline-'+target['id'][:12],bool(result['proof']) and result['producerSanity'],reason=result['reason'])
    selected=[next(c for c in targets if c['function'].endswith('mark_offline')),next(c for c in targets if c['function'].endswith('transaction') and c['spelling'].startswith('conn.')),next(c for c in targets if c['spelling'].startswith('observed_conn.'))]
    for target in selected:
        path=target['path'];source=core[path];receiver='observed_conn' if target['spelling'].startswith('observed_conn.') else 'conn'
        fn=next(f for f in t.qualified_functions(source).values() if f.lineno<=target['line']<=f.end_lineno)
        if receiver=='observed_conn':line=next(n.end_lineno for n in ast.walk(fn) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id==receiver for x in n.targets))
        else:line=next(i.context_expr.end_lineno for n in ast.walk(fn) if isinstance(n,ast.With) for i in n.items if isinstance(i.optional_vars,ast.Name) and i.optional_vars.id=='conn')
        indent=' '*(len(source.splitlines()[target['line']-1])-len(source.splitlines()[target['line']-1].lstrip()))
        for statement in [f'{receiver} = foreign',f'({receiver} := foreign)',f'{receiver}.execute = foreign',f"setattr({receiver}, 'execute', foreign)",f"delattr({receiver}, 'fetchone')",f'del {receiver}.execute',f'alias = {receiver}\nalias.execute = foreign',f'for {receiver} in foreign:\n    pass',f'with foreign_factory() as {receiver}:\n    pass']:
            mutated=after_line(source,line,statement,indent);ast.parse(mutated)
            cs=rebase(source,mutated,[c for c in calls if c['path']==path]);rs=rebase(source,mutated,[x for x in records if x['path']==path]);tar=next(c for c in cs if c['id']==target['id']);node=a.node_at(mutated,tar)
            sanity,err=r.producer_sanity(mutated,node,rs,cs);check('producer-sanity-'+receiver+'-'+statement.splitlines()[0],bool(sanity) and err is None)
            modified_core=dict(core);modified_core[path]=mutated
            modified_owner,owner_error=t.provenance(modified_core,ctors)
            if modified_owner:
                result=r.connection_result_explain(mutated,node,rs,cs,modified_core[t.CP+'db.py'],modified_owner);reason=result['reason'];refused=not result['proof'] and result['producerSanity']
            else:reason=owner_error;refused=True
            check('A1c-'+target['id'][:8]+'-'+statement.splitlines()[0],refused and not any(x in (reason or '') for x in ('STALE_CALL_SPAN','MISSING_PRODUCER_RECORD')),reason=reason,producerSanityPassed=True,sourceSHA256=r.sha(mutated))
    db=core[t.CP+'db.py']
    for label,mutated in [('observed-return',db.replace('        return result','        return foreign_result')),('observed-class-patch',db+'\n_ObservedConnection.execute = foreign\n'),('observed-class-setattr',db+"\nsetattr(_ObservedConnection, 'execute', foreign)\n"),('observed-class-alias',db+'\nAlias = _ObservedConnection\nAlias.execute = foreign\n'),('subclass-override',db+'\nclass Evil(Database):\n    def transaction(self, tenant):\n        return foreign()\n')]:
        ast.parse(mutated);_,error=t.observed_union(mutated);check('union-'+label,bool(error),reason=error)
    for label,mutated in [('shadow',db.replace('from contextvars import ContextVar','from contextvars import ContextVar\nfrom evil import ContextVar')),('rebind',db+'\n_statement_phase = foreign\n'),('foreign-token',db.replace('_statement_phase.reset(phase_token)','_statement_phase.reset(foreign_token)')),('missing-finally',db.replace('        finally:\n            phase =','        except Exception:\n            phase =')),('authority-predicate',db.replace('            _statement_phase.reset(phase_token)','            _statement_phase.reset(phase_token)\n            if phase:\n                self.authority = True'))]:
        ast.parse(mutated);proof,error=t.context_phase(mutated);check('A3-'+label,proof is None and bool(error),reason=error)
    proof,error=t.context_phase(db);check('A3-actual-positive',bool(proof) and not error)
    obs=core[t.CP+'observation.py'];append=next(n for n in ast.walk(ast.parse(obs)) if isinstance(n,ast.Call) and r.text(n.func)=='changed.append')
    proof,error=t.local_list(obs,append);check('A5-local-positive',bool(proof) and not error)
    line=append.lineno-1;indent=' '*(len(obs.splitlines()[append.lineno-1])-len(obs.splitlines()[append.lineno-1].lstrip()))
    for statement in ('changed = foreign','alias = changed','foreign(changed)',"setattr(changed, 'append', foreign)"):
        mutated=after_line(obs,line,statement,indent);node=next(n for n in ast.walk(ast.parse(mutated)) if isinstance(n,ast.Call) and r.text(n.func)=='changed.append');proof,error=t.local_list(mutated,node)
        check('A5-local-'+statement,proof is None and bool(error),reason=error)
    app_path=t.CP+'app.py';app=ctors[app_path];node=next(n for n in ast.walk(ast.parse(app)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='Database')
    old=ast.get_source_segment(app,node)
    for value in ('unknown_observer','socket.send','subprocess.run'):
        changed_node=deepcopy(node);changed_node.keywords.append(ast.keyword(arg='statement_observer',value=ast.parse(value,mode='eval').body))
        changed=r.text(ast.fix_missing_locations(changed_node));mutated=app.replace(old,changed,1)
        ast.parse(mutated);modified=dict(ctors);modified[app_path]=mutated;_,error=t.database_constructors(modified)
        check('A8-unknown-prod-observer-'+value,bool(error),reason=error)
    extra=app+'\n\ndef extra_production_site():\n    return Database("synthetic", recovery_epoch="synthetic", statement_observer=unknown)\n'
    modified=dict(ctors);modified[app_path]=extra;_,error=t.database_constructors(modified);check('A8-extra-prod-site',bool(error),reason=error)
    modified=dict(core);modified[t.CP+'observer_worker.py']=core[t.CP+'observer_worker.py'].replace('NodeObservation(database, client)','NodeObservation(foreign_database, client)')
    modified_ctors=dict(ctors);modified_ctors[t.CP+'observer_worker.py']=modified[t.CP+'observer_worker.py']
    _,error=t.provenance(modified,modified_ctors);check('A8-unknown-observer-db-union',bool(error) and 'SOURCE_INPUT_DISAGREEMENT' not in error,reason=error)
    modified=dict(core);modified[t.CP+'observation.py']=core[t.CP+'observation.py'].replace('self.db, self.client = database, client','self.db, self.client = foreign_database, client')
    _,error=t.provenance(modified,ctors);check('A8-unproven-self-db-field',bool(error),reason=error)
    a.write('t1-test-results.json',{'executionOwner':'Codex','scope':'BOUNDED_STATIC_PROOFS_ONLY','cases':R,'freshMutationProducerSpansAndHashes':True,'effectfulMutantsImportedOrExecuted':False,'maximumSimultaneousSelectedSourceFiles':10,'actualRuntimeB':0,'realBindings':None})
    print(json.dumps({'passed':len(R),'A1cPositiveEdges':5,'actualRuntimeB':0}))
if __name__=='__main__':main()
