"""OWNER exact70 replay and additional constructor/use-site controls."""
import ast,json,subprocess,sys
from pathlib import Path
import t1_provenance as t
import constructor_graph as cg
from source_bindings import Facts,frozen_source,sha
import bounded_analysis as a
import analysis_rules as rules
from mutation_fixture import rebase,after_line
E=Path(__file__).resolve().parent;R=[]
def check(name,value,**data):
    R.append({'case':name,'pass':bool(value),**data})
    if not value:raise AssertionError(name)
def main():
    # Original reviewer script/requirements remain byte-exact. The containing
    # receipt identifies this execution as OWNER reproduction, not new review.
    script=E/'rev9-review-reviewer_rev9_l1_t1_mutations.py.txt';out=E/'owner-original-reviewer70-results.json'
    cmd=[sys.executable,'-B',str(script),str(E),str(out)]
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE);(E/'owner-original-reviewer70.log').write_bytes(p.stdout+p.stderr)
    assert p.returncode==0,p.stderr.decode(errors='replace')
    raw=json.loads(out.read_bytes());check('exact-original70-replay',raw['total']==70 and not raw['soundGaps'] and not raw['positiveFailures'])
    check('exact70-current-producer-sanity',all(c.get('producerSanity',True) for c in raw['cases']))
    core=t.read_batch([t.CP+n for n in t.CORE]+['tools/remote_workspace_entry.py']);ctors=t.read_batch(t.MAIN_CTOR_PATHS)
    graph,error=cg.prove({**core,**ctors});check('derived-census-actual-positive',not error and len(graph['census']['production'])==6 and len(graph['census']['harness'])==20)
    check('all-three-constructor-input-unions',all(v==['inv.db.Database'] for v in graph['classDbInputUnions'].values()))
    check('local-helper-returns-source-proven',{p['helper'] for p in graph['localHelperProofs']}=={'tools.lan_pilot.runtime','tools.remote_workspace_entry.database'})
    path='tools/lan_pilot.py';source=ctors[path];f=Facts(path,source);fn=f.functions['runtime'];ret=next(n for n in fn.body if isinstance(n,ast.Return));segment=ast.get_source_segment(source,ret)
    for label,mutated in [('helper-object-return',source.replace(segment,'return object()',1)),('helper-foreign-return',source.replace(segment,'return foreign_database',1)),('helper-alias-escape',source+'\nruntime_alias = runtime\n'),('helper-rebound',source+'\nruntime = foreign_runtime\n')]:
        ast.parse(mutated);changed=dict(ctors);changed[path]=mutated
        if label=='helper-alias-escape':
            mutated=mutated.replace('ObservationWorker(runtime(state), ','ObservationWorker(runtime_alias(state), ',1);changed[path]=mutated
        _,error=t.provenance(core,changed)
        check(label,bool(error) and ('RECEIVER_UNION_UNPROVEN' in error or 'UNRESOLVED' in error),reason=error,parsePassed=True,sourceSHA256=sha(mutated))
    # Actual import aliases are resolved in the census. This no-effect rename
    # retains exactly the same constructor, arguments and local-helper proof.
    alias=source.replace('from inv.observer_worker import ObservationWorker','from inv.observer_worker import ObservationWorker as WorkerAlias').replace('ObservationWorker(runtime(state), ','WorkerAlias(runtime(state), ')
    ast.parse(alias);changed=dict(ctors);changed[path]=alias;alias_graph,error=cg.prove({**core,**changed})
    check('import-alias-constructor-census',not error and any(r['calleeSpelling']=='WorkerAlias' and r['constructor']=='inv.observer_worker.ObservationWorker' for r in alias_graph['census']['production']))
    _,error=t.provenance(core,changed);check('import-alias-full-use-site-proof',not error,reason=error)
    obs_path=t.CP+'observation.py';obs=core[obs_path]
    cs=[c for c in a.rows('classifiedCalls') if c['function']=='inv.observation.NodeObservation.mark_offline'];rs=[r for r in a.rows('records') if r['function']=='inv.observation.NodeObservation.mark_offline']
    target=next(c for c in cs if c['blocksGrant'] and c['spelling'].endswith('.fetchall'))
    fn=t.function(obs,'NodeObservation.mark_offline');line=next(i.context_expr.end_lineno for n in ast.walk(fn) if isinstance(n,ast.With) for i in n.items if isinstance(i.optional_vars,ast.Name) and i.optional_vars.id=='conn')
    for statement in ('foreign(owner=self.db)','foreign([self.db])','foreign(self.db.transaction)','alias = self.db','foreign(owner=self)'):
        mutated=after_line(obs,line,statement,'            ');ast.parse(mutated)
        new_cs=rebase(obs,mutated,cs);new_rs=rebase(obs,mutated,rs);tar=next(c for c in new_cs if c['id']==target['id']);node=a.node_at(mutated,tar)
        sane,sanity_error=rules.producer_sanity(mutated,node,new_rs,new_cs)
        modified=dict(core);modified[obs_path]=mutated;_,error=t.provenance(modified,ctors)
        check('owner-use-site-'+statement,bool(sane) and sanity_error is None and bool(error),reason=error,producerSanity=True)
    path=t.CP+'observer_worker.py';source=core[path];extra=source+'\n\ndef additional_root():\n    return ObservationWorker(foreign_database, None)\n';ast.parse(extra)
    changed_core=dict(core);changed_ctors=dict(ctors);changed_core[path]=extra;changed_ctors[path]=extra
    census=cg.current_census({**changed_core,**changed_ctors});check('extra-production-root-not-dropped',len(census['production'])==7)
    _,error=t.provenance(changed_core,changed_ctors);check('extra-unknown-root-refused',bool(error) and 'RECEIVER_UNION_UNPROVEN' in error,reason=error)
    path='tests/integration/test_node_extensions.py';source=frozen_source(path);extra=source+'\nfrom inv.observer_worker import ObservationWorker as HarnessWorkerAlias\n\ndef extra_harness_root():\n    return HarnessWorkerAlias(object(), None)\n';ast.parse(extra)
    census=cg.current_census({path:extra});check('harness-alias-call-catalogued-separately',len(census['production'])==6 and len(census['harness'])==21 and any(r.get('calleeSpelling')=='HarnessWorkerAlias' and r['scope']=='HARNESS_ONLY_PROVENANCE' for r in census['harness']))
    result={'executionOwner':'Codex','notIndependentReview':True,'exactOriginal70Command':cmd,'exactOriginal70Exit':p.returncode,'exactOriginal70SoundGaps':raw['soundGaps'],'exactOriginal70PositiveFailures':raw['positiveFailures'],'additionalCases':R,'effectfulMutantsImportedOrExecuted':False,'actualRuntimeB':0,'runtimeBindings':None}
    (E/'rev9b-analysis-test-results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps({'originalCases':70,'soundGaps':len(raw['soundGaps']),'additionalCases':len(R)}))
if __name__=='__main__':main()
