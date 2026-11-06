"""Exact immutable transport-call inventory; no client instantiation or IO."""
import ast,hashlib,json,subprocess
from pathlib import Path
from catalog import source_bytes,source_record,build_catalog,ROOT
from io_contract import EFFECT
E=Path(__file__).resolve().parent
BASE='72028cbac903c4415d9979f980a6e0f9948e914f'
METHOD={'probe':'HEARTBEAT_OBSERVE','resource_snapshot':'GPU_ACTIVE_OBSERVE','storage_sample':'STORAGE_SAMPLE','read_chunk':'OBJECT_READ','terminal_frame':'TERMINAL_FRAME','quarantine':'QUARANTINE_RECONCILE','collect_product_health':'BUILD_HEALTH_READ','collect_cleanup_receipt':'BUILD_CLEANUP_READ'}
# A closed source binding, not an allowlist by method name. New sites require a
# reviewed registration owner/purpose/parent and cannot silently inherit a kind.
SITES={
 'observation.py':{119,124},'buildkit_transport.py':{855,895,978},
 'model_remote.py':{98},'node_transfer.py':{43},'terminal.py':{277},
 'storage_check_collect.py':{309},'storage_commit.py':{398},
 'build_execution.py':{779,787,835},'node_transport.py':{289},
 'check_remote_workspace.py':{117},'lan_execution.py':{144,174,186},
 'remote_workspace_entry.py':{205}}

QUALIFIED_SITES={('tools/' if name in ('check_remote_workspace.py','lan_execution.py','remote_workspace_entry.py') else 'services/control-plane/src/inv/')+name:ls for name,ls in SITES.items()}

def literal_kw(call,name):
    return next((ast.literal_eval(k.value) for k in call.keywords if k.arg==name and isinstance(k.value,ast.Constant)),False)

def inventory():
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'--','services/control-plane/src/inv','tools'],cwd=ROOT).decode().splitlines()
    rows=[];errors=[]
    for path in names:
        if not path.endswith('.py') or '/tests/' in path:continue
        raw=source_bytes(path);tree=ast.parse(raw.decode('utf-8-sig'))
        for call in ast.walk(tree):
            if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute):continue
            method=call.func.attr;sp=ast.unparse(call.func)
            if method not in METHOD and method!='exchange' and not (method=='execute' and sp=='self._adapter.execute'):continue
            known=call.lineno in QUALIFIED_SITES.get(path,set())
            row=source_record(path,call.lineno);row.update(call=ast.unparse(call),methodName=method,registrationBoundary=True)
            if not known:
                row.update(disposition='UNMAPPED_TRANSPORT_SURFACE_BLOCK',kind=None);errors.append(row);rows.append(row);continue
            if method=='exchange':
                if Path(path).name=='node_transport.py':
                    variants=[{'predicate':'cancel_only approved exact CANCEL','kind':'CANCEL'},
                      {'predicate':'not cancel_only and observation_only exact original observe permit','kind':'RECEIPT_OBSERVE'},
                      {'predicate':'neither selector, exact approved original dispatch','kind':'EXECUTE'}]
                else:variants=[{'predicate':'literal exact existing observation_only argument' if literal_kw(call,'observation_only') else 'literal default execution dispatch','kind':'RECEIPT_OBSERVE' if literal_kw(call,'observation_only') else 'EXECUTE'}]
            else:variants=[{'predicate':'exact registered method/path/request/handler','kind':'BUILD_DISPATCH' if method=='execute' else METHOD[method]}]
            for v in variants:v['effectClass']=EFFECT[v['kind']]
            row.update(disposition='EXACT_CALL_CLOSED_VARIANTS',variants=variants,
              callerTransaction='independent original admitted intent commits before this call; exact outcome appended in original typed consumer transaction. No locks across external call.',
              parent='exact original run/claim/permit or current authorized observation/read/safety scope; cleanup/terminal/object continuation requires exact immutable parent handle and current read rights',
              selectorAuthority='server-approved typed operation chooses exclusive handler variant; untrusted booleans/kind/effectClass cannot authorize or downgrade',
              registration='BEFORE this exact call, after DB-committed opaque handle. Method definition is not a registration boundary.')
            rows.append(row)
    expected={(name,line) for name,ls in SITES.items() for line in ls}
    seen={(Path(r['path']).name,r['line']) for r in rows}
    for missing in sorted(expected-seen):errors.append({'missingExactCall':missing})
    catalog=build_catalog()
    for row in catalog['ioKinds']:
        row['callerBoundaries']=[{'path':r['path'],'line':r['line'],'function':r['function'],'fileSHA256':r['fileSHA256']} for r in rows if any(v['kind']==row['kind'] for v in r.get('variants',[]))]
        if not row['kind'].startswith('B_') and not row['callerBoundaries']:errors.append({'kindWithoutCaller':row['kind']})
    def go_anchor(path,needle,owner=None):
        raw=source_bytes(path);lines=raw.decode().splitlines();start=next((i for i,text in enumerate(lines,1) if owner and owner in text),1)
        end=next((i for i,text in enumerate(lines,1) if owner and i>start and text.startswith('func ')),len(lines)+1)
        line=next(i for i,text in enumerate(lines,1) if start<=i<end and needle in text)
        return {'sourceSHA':BASE,'path':path,'fileSHA256':hashlib.sha256(raw).hexdigest(),'line':line,'exactLine':lines[line-1],'enclosingFunction':owner,'functionStartLine':start,'functionEndExclusive':end}
    counter=[go_anchor('services/node-agent/runtime/runner.go',needle,owner) for needle,owner in (('func (r *Runner) Observe','func (r *Runner) Observe('),('r.reconcile(*prior','func (r *Runner) Observe('),('r.engine.Stop(ctx, state.ID)','func (r *Runner) reconcile('),('r.engine.Remove(ctx, state.ID, record)','func (r *Runner) finish('),('r.journal.Save(receipt)','func (r *Runner) finish('))]
    handlers={k:go_anchor('services/node-agent/transport/server.go',n) for k,n in {
      'HEARTBEAT_OBSERVE':'config := h.authority.config','GPU_ACTIVE_OBSERVE':'telemetry.Sample(ctx)',
      'STORAGE_SAMPLE':'h.storage.Sample(ctx, raw)','OBJECT_READ':'h.objects.Read(ctx, input)',
      'TERMINAL_FRAME':'engine.Terminal(ctx, raw)','QUARANTINE_RECONCILE':'recorder.Quarantine(ctx, raw)',
      'EXECUTE':'h.runner.Execute(ctx, raw)','CANCEL':'stopper.Cancel(ctx, raw)','RECEIPT_OBSERVE':'h.runner.Observe(ctx, raw)'}.items()}
    return {'source':BASE,'callers':rows,'catalog':catalog,'handlerAnchors':handlers,
      'readOnlyException':{'kind':'RECEIPT_OBSERVE','chosenEffect':'SIDE_EFFECT','proof':counter,'reason':'Observe can Stop/Remove and persist receipt; no pure-read split exists in72028, so actual path stays side effect/HOLD on uncertainty'},
      'coverageErrors':errors,'actualNewRuntimeEnforcement':False}

if __name__=='__main__':
    d=inventory();(E/'transport-inventory.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'callers':len(d['callers']),'errors':d['coverageErrors']}));assert not d['coverageErrors']
