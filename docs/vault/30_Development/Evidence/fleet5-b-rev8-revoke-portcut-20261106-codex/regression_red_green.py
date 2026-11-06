"""Same C1-C4 policy regression, parameterized by immutable/Rev8 model path."""
import json,sys
sys.path.insert(0,sys.argv[1]);sys.dont_write_bytecode=True
from model import World,binding,scope,sk,VER,OP
results=[]
for kind in ('CANCEL','RECEIPT_OBSERVE'):
    for lost in ('QUARANTINE','EXPIRED_EXECUTION_LEASE'):
        w=World();s=scope();c=w.connect(VER);p=w.register(c,binding(w,op='parent'))
        b=w.obligations[w.handles[p.handle_hash]['key']]['binding'];assert w.invoke(p,b['bodySHA'],b['method'],b['rawPath'])
        if lost=='QUARANTINE':w.set_fact(w.connect(OP),s,'QUARANTINE')
        else:w.now+=301
        h=w.register(c,binding(w,op='recover',kind=kind,parent=p.handle_hash))
        results.append({'kind':kind,'lost':lost,'matches72028AndRoot':h is not None})
print(json.dumps({'target':sys.argv[1],'cases':results,'allPass':all(x['matches72028AndRoot'] for x in results)}))
raise SystemExit(0 if all(x['matches72028AndRoot'] for x in results) else 1)
