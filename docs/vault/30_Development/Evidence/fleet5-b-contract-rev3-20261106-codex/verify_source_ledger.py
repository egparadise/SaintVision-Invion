"""Verify ledger byte/AST coverage against immutable Git objects, no app imports."""
from pathlib import Path
import ast
import collections
import csv
import hashlib
import json
import subprocess

E=Path(__file__).resolve().parent
ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
meta=json.loads((E/'callsite-locks.json').read_bytes())
rows=list(csv.DictReader((E/'callsite-locks.csv').read_text(encoding='utf-8').splitlines()))
expected=collections.Counter((r['sourceCallsite'],r['expressionSha256']) for r in rows)
actual=collections.Counter()
for f in meta['sourceFiles']:
    raw=subprocess.check_output(['git','show',meta['source']+':'+f['path']],cwd=ROOT)
    assert hashlib.sha256(raw).hexdigest()==f['sha256'],f['path']
    s=raw.decode('utf-8-sig');tree=ast.parse(s)
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call) or not isinstance(n.func,ast.Attribute) or n.func.attr not in ('execute','executemany','get','add','flush','delete'):continue
        if n.func.attr not in ('execute','executemany') and ast.unparse(n.func.value) not in ('session','db_session'):continue
        text=ast.get_source_segment(s,n) or ast.unparse(n)
        actual[(f['path']+':'+str(n.lineno),hashlib.sha256(text.encode()).hexdigest())]+=1
assert actual==expected,{'missing':list((actual-expected).elements()),'extra':list((expected-actual).elements())}
schema_count=0
for f in meta['schemaAssets']:
    raw=subprocess.check_output(['git','show',meta['source']+':'+f['path']],cwd=ROOT)
    assert hashlib.sha256(raw).hexdigest()==f['sha256'],f['path']
    lines=raw.decode('utf-8-sig').splitlines()
    for a in f['anchors']:assert lines[a['line']-1].strip()==a['text'],(f['path'],a['line'])
    schema_count+=1
print(json.dumps({'level':'GIT_OBJECT_AST_AND_ANCHOR_VERIFICATION_ONLY','source':meta['source'],'sourceFiles':len(meta['sourceFiles']),'callExpressions':sum(actual.values()),'schemaAssets':schema_count,'mismatches':0,'actualPGLockTrace':False}))
