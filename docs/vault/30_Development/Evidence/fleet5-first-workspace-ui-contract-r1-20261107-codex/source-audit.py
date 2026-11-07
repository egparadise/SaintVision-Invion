"""Read-only Git/AST/data evidence. Never imports product modules."""
import ast
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import subprocess

BASE = '1efea494f026e932360c35ae811b6423d874a2e7'
FRONT = 'b48c2c4492f8aea4b55c33161733a9a6fb9eed8c'
ROOT_REF = '23a6cadef31053a35deae187c6991e48ebd70ff0'
HERE = Path(__file__).resolve().parent
def git(*argv):
    return subprocess.check_output(['git', *argv])
def blob(ref, path):
    return git('show', ref+':'+path)
def pin(ref, path):
    raw = blob(ref, path)
    return dict(path=path, ref=ref, blob=git('rev-parse',ref+':'+path).decode().strip(), bytes=len(raw), SHA256=hashlib.sha256(raw).hexdigest())

changed = git('diff',BASE,'--name-only','-z').decode('utf8').strip('\0').split('\0')
for path in changed:
    if path.endswith('.py'):
        ast.parse(Path(path).read_text('utf-8-sig'))
manifest = json.loads((HERE/'frontend-import.json').read_text('utf8'))
imports = []
for item in manifest['frontendPathsDifferingFromKernel']:
    original = pin(FRONT,item['path'])
    assert original['blob'] == item['acceptedFrontendBlob'] and original['SHA256'] == item['acceptedFrontendSHA256']
    current = Path(item['path']).read_bytes().replace(b'\r\n',b'\n')
    assert current == blob(FRONT,item['path'])
    imports.append(dict(**original, currentAcceptedBytesPreserved=True, integrationAdjustment=None))
schema = json.loads(Path('contracts/v1alpha1/core.schema.json').read_text('utf8'))
old_schema = json.loads(blob(BASE,'contracts/v1alpha1/core.schema.json'))
assert all(schema['$defs'][key] == value for key,value in old_schema['$defs'].items())
old_migrations = git('ls-tree','-r','--name-only',BASE,'--','migrations/versions','services/control-plane/src/inv/migrations').decode().splitlines()
for path in old_migrations:
    assert Path(path).read_bytes().replace(b'\r\n',b'\n') == blob(BASE,path).replace(b'\r\n',b'\n')
unchanged_trees = {}
for tree in ['src','deploy','.github','skills','docs/sources']:
    diff=git('diff',BASE,'--name-only','--',tree).decode().strip()
    assert not diff
    unchanged_trees[tree]=git('rev-parse',BASE+':'+tree).decode().strip()
policy = json.loads(Path('tools/definer-policy.json').read_text('utf8'))
assert policy['revision']=='0068_first_workspace_intent'
snapshot = Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json').read_bytes()
assert snapshot == (HERE/'sync-state-before.json').read_bytes()
out=dict(atKST=datetime.now(timezone(timedelta(hours=9))).isoformat(),deliveryBase=BASE,backendBase=BASE,
    importedFrontendSource=FRONT,frozenRoot=ROOT_REF,checkoutHEAD=git('rev-parse','HEAD').decode().strip(),
    note='Working source/data audit; final committed SHA is supplied by publication receipt, not predicted here',
    imports=imports,oldMigrationFilesUnchanged=len(old_migrations),oldSchemaDefinitionsUnchanged=len(old_schema['$defs']),
    unchangedTrees=unchanged_trees,changedPythonASTCount=sum(p.endswith('.py') for p in changed),
    changes=[dict(path=p,bytes=Path(p).stat().st_size,SHA256=hashlib.sha256(Path(p).read_bytes()).hexdigest()) for p in changed if Path(p).is_file() and not p.startswith('docs/')],
    fullCanonicalSyncBytes=len(snapshot),fullCanonicalSyncSHA256=hashlib.sha256(snapshot).hexdigest(),fullCanonicalSyncUnchanged=True,
    localProductTestExecution=False,actualHardwareOrApprovalExecution=False,independentReview='PENDING_ACTUAL_CLAUDE',wholeProgramComplete=False)
(HERE/'source-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=True)+'\n',encoding='utf8')
print(json.dumps(dict(imported11Preserved=len(imports),oldMigrationsUnchanged=len(old_migrations),oldDefinitionsUnchanged=len(old_schema['$defs']),changedPythonASTCount=out['changedPythonASTCount'],fullCanonicalSyncUnchanged=True)))
