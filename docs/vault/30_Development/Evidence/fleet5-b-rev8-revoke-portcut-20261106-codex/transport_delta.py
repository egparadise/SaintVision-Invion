"""Exact Go function/path branch binding plus absent optional hook contract."""
import ast,hashlib,json,re,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent
ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
R7=E.parent/'fleet5-b-contract-rev7-20261106-codex'
SOURCE='72028cbac903c4415d9979f980a6e0f9948e914f'
def raw(path):return subprocess.check_output(['git','show',SOURCE+':'+path],cwd=ROOT)
def sha(x):return hashlib.sha256(x).hexdigest()
def end_brace(text,start):
    depth=0;i=start;quote=None
    while i<len(text):
        c=text[i]
        if quote:
            if c=='\\' and quote!='`':i+=2;continue
            if c==quote:quote=None
        elif text[i:i+2]=='//':
            j=text.find('\n',i);i=len(text) if j<0 else j;continue
        elif text[i:i+2]=='/*':
            j=text.find('*/',i+2);assert j>=0;i=j+2;continue
        elif c in ('"',"'",'`'):quote=c
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return i
        i+=1
    raise AssertionError('unterminated Go block')
def anchors(text):
    start=text.index('func (h *handler) ServeHTTP(');open_at=text.index('{',start);end=end_brace(text,open_at)
    line=lambda pos:text.count('\n',0,pos)+1
    function={'name':'func (h *handler) ServeHTTP(','startLine':line(start),'endLine':line(end),'sha256':sha(text[start:end+1].encode())}
    mapping={
      'HEARTBEAT_OBSERVE':('/v1/heartbeats','probe','config := h.authority.config','if probe || snapshot {'),
      'GPU_ACTIVE_OBSERVE':('/v1/snapshots','snapshot','telemetry.Sample(ctx)','if snapshot {'),
      'STORAGE_SAMPLE':('/v1/storage/sample','storageSample','h.storage.Sample(ctx, raw)','if storageSample {'),
      'OBJECT_READ':('/v1/objects/read','chunk','h.objects.Read(ctx, input)','if chunk {'),
      'TERMINAL_FRAME':('/v1/terminals/frame','terminal','engine.Terminal(ctx, raw)','if terminal {'),
      'QUARANTINE_RECONCILE':('/v1/builds/quarantine','quarantine','recorder.Quarantine(ctx, raw)','if quarantine {'),
      'CANCEL':('/v1/executions/cancel','cancelling','stopper.Cancel(ctx, raw)','if cancelling {'),
      'RECEIPT_OBSERVE':('/v1/executions/receipts',None,'h.runner.Observe(ctx, raw)','else if r.URL.Path == "/v1/executions/receipts" {'),
      'EXECUTE':('/v1/executions',None,'h.runner.Execute(ctx, raw)','else {')}
    out={}
    for k,(path,selector,needle,condition) in mapping.items():
        positions=[m.start() for m in re.finditer(re.escape(needle),text) if start<m.start()<end];assert len(positions)==1
        at=positions[0];blocks=[]
        for m in re.finditer(re.escape(condition),text[start:end]):
            a=start+m.start();b=text.index('{',a);z=end_brace(text,b)
            if b<at<z:blocks.append((a,z))
        assert len(blocks)==1,(k,blocks);a,z=blocks[0]
        selector_text=f'{selector} := r.URL.Path == "{path}"' if selector else 'r.URL.Path == "'+path+'"' if k=='RECEIPT_OBSERVE' else 'r.URL.Path != "/v1/executions"'
        assert selector_text in text[start:end]
        guard='r.URL.RawQuery != "" || r.URL.RawPath != ""'
        assert guard in text[start:end] and 'r.Method != "POST"' in text[start:end]
        out[k]={'rawPath':path,'method':'POST','enclosingFunction':function,'branch':{'condition':condition,'startLine':line(a),'endLine':line(z),'sha256':sha(text[a:z+1].encode())},
          'selector':{'expression':selector_text,'line':line(text.index(selector_text,start))},'line':line(at),'exactLine':text.splitlines()[line(at)-1],
          'rawPathGuard':guard,'effectivePathProof':'Validated closed URL.Path set; earlier distinct path handlers return. Default execute branch excludes cancelling and receipts; probe/snapshot branch uses exact selector. No first-substring/whole-file anchor.'}
    return out
def main():
    path='services/node-agent/transport/server.go';data=raw(path);text=data.decode();out=anchors(text)
    parent=json.loads((R7/'transport-inventory.json').read_bytes());assert len(parent['callers'])==19
    # Mutation: correct needle in a different branch must not retain its anchor.
    mutant=text.replace('h.runner.Observe(ctx, raw)','REV8_SWAP_PLACEHOLDER').replace('h.runner.Execute(ctx, raw)','h.runner.Observe(ctx, raw)').replace('REV8_SWAP_PLACEHOLDER','h.runner.Execute(ctx, raw)')
    refused=False
    try:anchors(mutant)
    except AssertionError:refused=True
    assert refused
    hook_path='services/control-plane/src/inv/build_execution.py';hook=raw(hook_path).decode();tree=ast.parse(hook)
    call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='getattr' and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and n.args[1].value=='materialize_source_capsule')
    scan=['git','grep','-n','-E','def materialize_source_capsule|materialize_source_capsule[[:space:]]*=',SOURCE,'--','services/control-plane/src','src','deploy']
    r=subprocess.run(scan,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    assert r.returncode==1, 'Any implementation needs a NEW catalog IO kind and review'
    value={'source':SOURCE,'parentTransportInventorySHA256':sha((R7/'transport-inventory.json').read_bytes()),'unchangedCallerBoundaries':19,'handlerFile':{'path':path,'sha256':sha(data)},'handlerAnchors':out,
      'I1MutationBranchSubstitutionRefused':refused,'optionalHook':{'path':hook_path,'line':call.lineno,'expression':ast.get_source_segment(hook,call),'fileSHA256':sha(hook.encode()),'disposition':'ABSENT_IN72028_ALWAYS_RES0006','scope':'Exact optional literal getattr only','scanCommand':scan,'scanExit':r.returncode,'scanOutputSHA256':sha(r.stdout),'futureImplementation':'NEW IO kind/method/effect/owner registration plus independent review; never silently inherit BUILD_DISPATCH or a generic filesystem port'},
      'actualRuntimeB':0}
    (E/'transport-delta.json').write_bytes((json.dumps(value,indent=2)+'\n').encode());print(json.dumps({'branchBoundHandlers':len(out),'callerBoundaries':19,'absentHookScanExit':r.returncode}))
if __name__=='__main__':main()
