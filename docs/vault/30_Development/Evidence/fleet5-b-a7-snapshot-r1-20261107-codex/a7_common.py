"""A7-only frozen source utilities; no product import, effects or live bindings."""
import ast,hashlib,json,subprocess
from pathlib import Path
from source_bindings import Facts,ROOT,SOURCE,frozen_source,sha,text
E=Path(__file__).resolve().parent;CP='services/control-plane/src/inv/';NC=CP+'node_channels.py';CT=CP+'containment.py';DB=CP+'db.py';ER=CP+'errors.py'
TARGET='inv.node_channels.NodeChannels';SNAP=TARGET+'.snapshot';REQUIRE='inv.containment.require_execution'
PROTECTED=(TARGET,'inv.node_channels.ChannelProof','inv.node_channels.proof','inv.node_channels.assert_channel',REQUIRE,'inv.db.Database')
def get(path,world=None):return world[path] if world and path in world else frozen_source(path)
def witness(f,n):return f.witness(n)
def shape(n):return ast.dump(n,include_attributes=False)
def one_function(f,q):return f.functions.get(q)
def grep(pattern,scope=('services/control-plane/src','src','tools')):
    argv=['git','grep','-l','-E',pattern,SOURCE,'--',*scope];r=subprocess.run(argv,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE);assert r.returncode in (0,1)
    return sorted({x.split(':',1)[1] for x in r.stdout.decode('utf8').splitlines() if x.endswith('.py')}),{'argv':argv,'exit':r.returncode,'outputSHA256':hashlib.sha256(r.stdout).hexdigest()}
def emit(name,data):(E/name).write_bytes((json.dumps(data,indent=2,sort_keys=True)+'\n').encode())
def obligation(code,detail,source=None):return {'code':code,'detail':detail,'source':source,'blocksGrant':True,'state':'UNRESOLVED'}
