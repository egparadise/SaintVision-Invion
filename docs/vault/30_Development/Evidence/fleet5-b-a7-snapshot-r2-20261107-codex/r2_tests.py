"""Exact A7R-L1 census delta oracle; AST text only, no product execution.

Diagnostic spans below replay existing use-site enumeration for location ONLY.
The actual existing ra.audit/module_uses results alone decide census refusal.
"""
import ast,json,sys
from collections import Counter
import a7_body as body,a7_inventory as inventory,use_sites as u
from a7_common import *
NR=CP+'node_certificates.py';OBS=CP+'observation.py';ERROR='DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:WRITE_USE:inv.node_channels.NodeChannels.snapshot'

def guard_location(path,source,error):
    f=Facts(path,source);allowed=u.baseline_sites(path,True,(),()).copy()
    for n,tag in u.audited_nodes(f,True,(),{},(),()):
        if u.class_field_factory_allowed(f,n):continue
        k=u.key_for(f,n,tag)
        if allowed[k]<=0:
            actual=('UNRESOLVED:RELEVANT_REFLECTION_USE_NOT_ALLOWLISTED:' if tag.startswith(('REFLECTION_NAMESPACE:','PROTECTED_REFLECTION_STRING:')) else 'DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:')+tag
            assert actual==error,(path,actual,error)
            return witness(f,n)
        allowed[k]-=1
    raise AssertionError(('guard diagnostic has no matching refused node',path,error))

def keys(obligations,world):
    result=Counter()
    for o in obligations:
        s=o.get('source') or {};detail=o.get('detail');subject=detail if isinstance(detail,str) else detail.get('expression',detail.get('value',detail.get('detail',''))) if isinstance(detail,dict) else str(detail)
        if isinstance(s,str):
            path=s
            if isinstance(detail,str) and ':USE_SITE_NOT_ALLOWLISTED:' in detail:s=guard_location(path,get(path,world),detail)
            else:s={'path':path}
        result[(o['code'],s.get('path'),tuple(s.get('span',[])),subject)]+=1
    return result

def serialized(counter):return [{'code':k[0],'path':k[1],'span':list(k[2]),'subject':k[3],'multiplicity':v} for k,v in sorted(counter.items())]

def coverage(c):
    parsed={r['path']:r['sha256'] for r in c['sourceFiles']};audited={r['path']:r.get('sourceSHA256',r['reflection']['sourceSHA256']) for r in c['guards']}
    assert len(parsed)==len(c['sourceFiles']) and len(audited)==len(c['guards'])
    return {'parsed':parsed,'audited':audited,'equal':parsed==audited,'uncoveredPaths':sorted(set(parsed)-set(audited))}

def main():
    sys.stdout.reconfigure(encoding='utf8');exact_only='--exact-only' in sys.argv
    raw=(E/'actual-review-reviewer_a7_probes.py.txt').read_bytes();driver=ast.parse(raw);patch=next(n.value.value for n in driver.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='PATCH' for x in n.targets));assert isinstance(patch,str)
    review=json.loads((E/'actual-review-reviewer-a7-probes-result.json').read_bytes());original=[r for r in review['rows'] if r['case']=='nonretained-candidate-class-monkeypatch'];assert len(original)==4 and {r['layer'] for r in original}=={'SPAN','BODY','CENSUS','GUARD_ONLY'}
    exact={NR:frozen_source(NR)+patch};assert sha(exact[NR])=='19c2e14eb3e586f5ed22e1fb0549fe51961a079557fba2bb07ca1b8410686191'
    assert next(r for r in original if r['layer']=='BODY')['inputSHA256'][NR]==sha(exact[NR])
    fixtures=[('actual-review-exact-nonretained-monkeypatch',exact,'MONKEYPATCH',NR)]
    if not exact_only:fixtures += [('retained-observation-same-patch',{OBS:frozen_source(OBS)+patch},'MONKEYPATCH',OBS),('nonretained-benign-comment',{NR:frozen_source(NR)+'\n# R2 benign non-retained control\n'},'BENIGN',NR),('nonretained-unused-import-alias',{NR:frozen_source(NR)+'\nfrom .node_channels import NodeChannels as _R2Unused\n'},'BENIGN',NR),('INFOI3-owner-purpose-delta-oracle',{OBS:frozen_source(OBS).replace('observation_only=True','observation_only=foreign',1)},'PURPOSE',OBS)]
    with body.target_scope():base=inventory.prove();base_body=body.prove();baseline=keys(base['obligations'],{});baseline_census=keys(base['census']['obligations'],{})
    assert base_body['bodyAccepted'] and not base['callerClosureAccepted'] and len(base['obligations'])==19 and all(o['blocksGrant'] for o in base['obligations'])
    rows=[];inputs={};result={'baseline':{'obligations':serialized(baseline),'censusObligations':serialized(baseline_census),'coverage':coverage(base['census']),'bodyAccepted':True,'callerClosureAccepted':False},'cases':rows,'reviewInputOrigin':'actual7a8012f47de5aa94a4264366df6722c1f6755a9c, four distinct SPAN/BODY/CENSUS/GUARD_ONLY rows; not three','actualRuntimeB':0,'productImportedOrExecuted':False}
    for name,world,kind,path in fixtures:
        for p,s in world.items():compile(s,p,'exec',dont_inherit=True)
        with body.target_scope():
            b=body.prove(world);c=inventory.prove(world);current=keys(c['obligations'],world);current_census=keys(c['census']['obligations'],world)
        added=current-baseline;removed=baseline-current;ca=current_census-baseline_census;cr=baseline_census-current_census
        f=Facts(path,world[path]);injected=[{'source':witness(f,n),'text':ast.get_source_segment(f.source,n)} for n in ast.walk(f.tree) if isinstance(n,ast.stmt) and not isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.With,ast.If)) and '_ReviewerA7NC' in (ast.get_source_segment(f.source,n) or '')]
        row={'name':name,'layer':'CENSUS_AND_EXISTING_GUARDS_NOT_BODY_REFUSAL','inputSHA256':{p:sha(s) for p,s in world.items()},'syntaxValid':True,'selectedBodiesUnchanged':{p:sha(frozen_source(p)) for p in (NC,CT,DB,ER)},'bodyAccepted':b['bodyAccepted'],'callerClosureAccepted':c['callerClosureAccepted'],'completeAddedVsBaseline':serialized(added),'completeRemovedVsBaseline':serialized(removed),'censusAddedVsBaseline':serialized(ca),'censusRemovedVsBaseline':serialized(cr),'coverage':coverage(c['census']),'retainedForCallClosure':next(x['retainedForCallClosure'] for x in c['census']['sourceFiles'] if x['path']==path),'injectedStatements':injected,'actualUnresolvedObligations':len(c['obligations'])}
        rows.append(row);inputs[name]=world;emit('r2-test-results.json',result);emit('r2-test-inputs.json',inputs);print(json.dumps({k:v for k,v in row.items() if k!='coverage'}),flush=True)
        assert b['bodyAccepted'] and not c['callerClosureAccepted'] and not removed and not cr
        if kind=='MONKEYPATCH':
            target=next(n for n in ast.walk(f.tree) if isinstance(n,ast.Attribute) and text(n)=='_ReviewerA7NC.snapshot' and isinstance(n.ctx,ast.Store));span=tuple(witness(f,target)['span']);expected_key=('A7_FULL_MODULE_USE_SITE_GUARD',path,span,ERROR)
            assert ca==Counter({expected_key:1}),('MISSING_OR_INEXACT_NEW_CENSUS_DELTA',name,serialized(ca),list(expected_key))
            expected_full=Counter({expected_key:1})
            if path==OBS:expected_full[('A7_FORWARD_GUARD',path,span,ERROR)]=1
            assert added==expected_full,('INEXACT_COMPLETE_DELTA',serialized(added),serialized(expected_full))
            if path==NR:
                assert not row['retainedForCallClosure'];assert [{'span':n['source']['span'],'text':n['text']} for n in injected]==next(r for r in original if r['layer']=='SPAN')['injected']
            else:assert row['retainedForCallClosure']
        elif kind=='BENIGN':assert not ca and not added and not row['retainedForCallClosure']
        else:
            expected=('A7_PURPOSE_PROVENANCE',OBS,(17,16,17,70),'foreign');assert ca[expected]==1 and baseline_census[expected]==0 and added[expected]==1
            assert all(k[1]==OBS and k[0] in {'A7_PURPOSE_PROVENANCE','A7_FULL_MODULE_USE_SITE_GUARD','A7_FORWARD_GUARD'} for k in added)
            row['qualification']='INFOI3 oracle correction only: actual new observation.py purpose key; pre-existing NodeDelivery reason cannot satisfy it; underlying purpose/body predicates unchanged'
        assert row['coverage']['equal'] and result['baseline']['coverage']['equal'],'parsed path/current-SHA set must equal audited path/current-SHA set'
        row['expectationMet']=True;emit('r2-test-results.json',result)
    assert all(r['expectationMet'] for r in rows);result['allExpected']=True;emit('r2-test-results.json',result);print(json.dumps({'cases':len(rows),'allExpected':True,'baselineUnresolved':19,'parsedEqualsAudited':True,'actualRuntimeB':0}))
if __name__=='__main__':main()
