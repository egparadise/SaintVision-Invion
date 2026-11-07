"""Git/AST/data audit only; never imports a product or test module."""
import ast
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import subprocess

BASE = '90578f49ea400958fcdbc1ded3908d624e856f57'
HERE = Path(__file__).resolve().parent
OWN = HERE.relative_to(Path.cwd()).as_posix()
TEST = 'tests/integration/test_workspace_first_intents.py'
HISTORY = 'docs/vault/30_Development/History/2026-11-07_CR90501_Direct_SQL_Guards_Test_Only_R1_Codex.md'

def git(*args):
    return subprocess.check_output(['git', *args])

changed = git('diff', BASE, '--name-only', '-z').decode('utf8').strip('\0').split('\0')
assert all(p == TEST or p == HISTORY or p.startswith(OWN + '/') for p in changed)
assert not git('diff', BASE, '--name-only', '--diff-filter=D').strip()
trees = {}
for tree in ['apps', 'services', 'contracts', 'packages', 'migrations', 'tools', '.github', 'deploy', 'skills', 'src', 'docs/sources']:
    assert not git('diff', BASE, '--name-only', '--', tree).strip()
    trees[tree] = git('rev-parse', BASE + ':' + tree).decode().strip()
assert not git('diff', BASE, '--name-only', '--', 'docs/task-registry.json').strip()
sql_path = 'services/control-plane/src/inv/migrations/0068_first_workspace_intent.sql'
sql = git('show', BASE + ':' + sql_path)
assert Path(sql_path).read_bytes().replace(b'\r\n', b'\n') == sql
assert hashlib.sha256(sql).hexdigest() == '8b79f55289661d7590dbe24e60d60d319360e7fcaf35454fe21c722fe11905d3'
old = ast.parse(git('show', BASE + ':' + TEST).decode('utf-8-sig'))
current = ast.parse(Path(TEST).read_text('utf-8-sig'))
old_functions = {n.name: ast.dump(n, include_attributes=False) for n in old.body if isinstance(n, ast.FunctionDef)}
new_functions = {n.name: ast.dump(n, include_attributes=False) for n in current.body if isinstance(n, ast.FunctionDef)}
assert old_functions.keys() <= new_functions.keys()
assert all(new_functions[k] == v for k,v in old_functions.items() if k != 'test_helper_privileges_rls_and_missing_context_are_real_not_superuser_results')
assert not any(isinstance(n, ast.Attribute) and n.attr in {'skip','skipif','xfail'} for n in ast.walk(current))
state = Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json').read_bytes()
assert state == (HERE/'sync-state-before.json').read_bytes()
value = dict(atKST=datetime.now(timezone(timedelta(hours=9))).isoformat(),base=BASE,
    checkoutHEAD=git('rev-parse','HEAD').decode().strip(),scope='Working candidate; final immutable SHA supplied by hosted publication receipt',
    onlyExistingChangedPath=TEST,unchangedProtectedTrees=trees,
    SQL=dict(path=sql_path,blob=git('rev-parse',BASE+':'+sql_path).decode().strip(),SHA256=hashlib.sha256(sql).hexdigest()),
    existingTestsUnchangedExceptRequiredContextLoop=True,noNewSkipXfail=True,
    changedTrackedPaths=changed,fullCanonicalBytes=len(state),fullCanonicalSHA256=hashlib.sha256(state).hexdigest(),fullCanonicalUnchanged=True,
    previousFrontend=dict(sourceSHA=BASE,runID=42368189302,scope='Unchanged-component evidence only, not a new-SHA frontend execution'),
    productExecutionOnMain=False,CR90501='PENDING_HOSTED_CI_AND_ACTUAL_CLAUDE_DELTA_REVIEW',wholeProgramComplete=False)
(HERE/'scope-proof.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(scope='PASS',protectedTrees=len(trees),SQLSHA256=value['SQL']['SHA256'],canonicalBytes=len(state),unchanged=True)))
