"""Git/AST/DATA proof; no application imports, crypto or runtime operations."""
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID

HERE = Path(__file__).resolve().parent
S = '1efea494f026e932360c35ae811b6423d874a2e7'
R = 'baaa8ea99919a7fec40f8f853a648f4067d7248d'
B = '5ba7cfb795135e1f74c0d3e83e0fea285d3cc987'
passed = []


def check(name, value):
    if not value:
        raise AssertionError(name)
    passed.append(name)


def git(*args):
    return subprocess.check_output(['git', *args])


def raw(ref, path):
    return git('show', ref + ':' + path)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def function(tree, name):
    return next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def literal_sets(tree):
    values = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Set):
            try:
                values.append(ast.literal_eval(n))
            except (ValueError, TypeError):
                pass
    return values


d = json.loads((HERE / 'source-bindings.json').read_bytes())
c = json.loads((HERE / 'context.json').read_bytes())
e = json.loads((HERE / 'typed-examples.json').read_bytes())
check('exact source/base/root authorities', d['productSource'] == c['productSource'] == S and d['deliveryBase'] == c['deliveryBase'] == B and d['rootPublicRef'] == c['rootRef'] == R)
check('new exact own branch', git('branch', '--show-current').decode().strip() == c['branch'])
check('delivery base ancestor', subprocess.run(['git', 'merge-base', '--is-ancestor', B, 'HEAD'], capture_output=True).returncode == 0)
text = {}
trees = {}
for p in d['pins']:
    b = raw(S, p['path']); lines = b.decode().splitlines()
    excerpt = '\n'.join(lines[p['startLine']-1:p['endLine']]) + '\n'
    check('immutable source ' + p['id'], p['ref'] == S and sha(b) == p['fileSHA256'] and git('rev-parse', S + ':' + p['path']).decode().strip() == p['gitBlobSHA1'] and 1 <= p['startLine'] <= p['endLine'] <= len(lines) and excerpt == p['excerpt'] and sha(excerpt.encode()) == p['excerptSHA256'])
    text[p['id']] = b.decode('utf-8-sig')
    if p['path'].endswith('.py'):
        trees[p['id']] = ast.parse(text[p['id']], filename=p['path'])
for p in d['publicInputs'] + d['publicInventoryVerified']:
    b = raw(R, p['path'])
    check('public input ' + p['path'].split('/')[-1], p['ref'] == R and len(b) == p['bytes'] and sha(b) == p['sha256'])
schema = json.loads(raw(S, d['wireSchema']['path']))
check('wire schema immutable', sha(raw(S, d['wireSchema']['path'])) == d['wireSchema']['sha256'])
check('six exact wire shapes', len(d['wireSchema']['shapes']) == 6 and all(v == schema['$defs'][k] for k,v in d['wireSchema']['shapes'].items()))
api = e['apiConfig']; w = api['workspace']; profile = w['profile']
top = next(x for x in literal_sets(trees['api-config']) if {'identity', 'business', 'workspace', 'storageSample'} <= x)
check('minimal main config closed source field set', set(api) == {'identity','allowedOrigins','business','workspace'} and set(api) <= top and api['business'] is True)
identity_init = next(function(n, '__init__') for n in trees['offline-jwks'].body if isinstance(n, ast.ClassDef) and n.name == 'AccessTokens')
check('identity exact constructor key set', set(api['identity']) == {a.arg for a in identity_init.args.kwonlyargs})
check('tenant and existing issuer/client preserved', str(UUID(api['identity']['tenant_id'])) == api['identity']['tenant_id'] and api['identity']['issuer'] == 'https://127.0.0.1:8443/realms/saintvision' and api['identity']['audience'] == 'sv-api' and api['identity']['client_ids'] == ['sv-portal'])
required = next(x for x in literal_sets(trees['workspace-config']) if {'workingRoot','signingKeyFile','tls'} <= x)
optional = {n.args[0].value for n in ast.walk(function(trees['workspace-config'], 'configured_workspace')) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'pop' and isinstance(n.func.value, ast.Name) and n.func.value.id == 'settings'}
check('closed workspace required/optional fields', required <= set(w) <= required | optional and set(w)-required == {'snapshotObjectRoot','restoreRoot'})
check('paired local output provider reaches API and worker', w['snapshotObjectRoot'] == e['deliveryWorkerConfig']['outputRoot'] and w['restoreRoot'] != w['workingRoot'] and 'if self.provider is None:' in text['output-provider-required'])
fields = {n.target.id for cl in trees['sandbox-profile'].body if isinstance(cl, ast.ClassDef) and cl.name == 'SandboxProfile' for n in cl.body if isinstance(n, ast.AnnAssign)}
check('exact profile constructor field names', set(profile) == fields)
check('profile integer/bool types and per-run ceilings', all(type(profile[k]) is int and 1 <= profile[k] <= 9007199254740991 for k in ['max_cpu_millis','max_memory_bytes','max_timeout_seconds']) and [profile[k] for k in ['max_cpu_millis','max_memory_bytes','max_timeout_seconds']] == [500,67108864,30] and profile['allow_terminal'] is False)
check('actual public image/executable/profile', profile['version'] == 'cpu-pilot-1efea-r1' and profile['images'] == ['sha256:ffee58e8dbefc6c0db68810cd1597f8cc589cf01112c434ed7fda8d4af415634'] and profile['executables'] == ['/usr/local/bin/python3'] and re.fullmatch(r'sha256:[0-9a-f]{64}',profile['images'][0]) is not None)
resource_re = schema['$defs']['ResourceId']['pattern']
check('distinct exact CPU/memory ResourceId map', set(w['resources']) == {'cpu','memory'} and len(set(w['resources'].values())) == 2 and all(re.fullmatch(resource_re,v) for v in w['resources'].values()))
tls_init = next(function(n, '__init__') for n in trees['cp-tls'].body if isinstance(n, ast.ClassDef) and n.name == 'NodeTLSClient')
check('TLS exact constructor keys and timeout type', set(w['tls']) == {a.arg for a in tls_init.args.kwonlyargs} and type(w['tls']['timeout']) is int and 0.1 <= w['tls']['timeout'] <= 40 and e['deliveryWorkerConfig']['tls'] == w['tls'])
check('worker exact optional outputRoot keys', set(e['deliveryWorkerConfig']) == {'tenantId','tls','outputRoot'} and 'buildExecution' not in e['deliveryWorkerConfig'])
check('API exact example environment names present in source', all(k in text['api-config'] + text['business-role'] for k in e['apiEnvironment']))
check('worker exact example environment names present in source', all(k in text['worker-start'] for k in e['workerEnvironment']))
check('private credentials stay explicit placeholders', all(e['apiEnvironment'][k].startswith('ROOT_ONLY_UNBOUND_') and e['protectedFileBindings'][k].startswith('/ROOT_ONLY_UNBOUND/') for k in ['INV_RUNTIME_DSN','INV_BUSINESS_DSN']))
paths = [api['identity']['jwks_file'],w['workingRoot'],w['restoreRoot'],w['snapshotObjectRoot'],w['signingKeyFile'],*w['tls'].values(),*e['protectedFileBindings'].values(),e['apiEnvironment']['INV_API_CONFIG'],e['workerEnvironment']['INV_WORKER_CONFIG']]
check('all placeholder paths canonical POSIX strings', all(isinstance(v,int) or isinstance(v,str) and v.startswith('/ROOT_ONLY_UNBOUND/') and str(PurePosixPath(v)) == v and not any(x in {'.','..',''} for x in v.split('/')[1:]) and '\\' not in v and '\x00' not in v for v in paths))
check('fixed API startup port and configured entrypoint', 'host="127.0.0.1"' in text['api-start'] and 'port=8080' in text['api-start'] and 'create_configured_app()' in text['api-start'] and e['apiEnvironment']['INV_KERNEL_BASE_URL'] == 'http://127.0.0.1:8080')
check('offline bundle outer shape and no crypto execution claim', set(e['publicJWKSContract']['outerRequiredAndOnlyKeys']) == {'issuer','expiresAt','keys'} and e['publicJWKSContract']['requiresIssuerHTTPSFetchOnPC3'] is False and e['publicJWKSContract']['actualJWKSOrTokenReadOrCryptoValidationHere'] is False)
check('no network discovery in AccessTokens source', not any(x in text['offline-jwks'] for x in ['urlopen(', 'requests.', 'PyJWKClient(']))
check('portal API relative fetch and startup proxy source', 'fetch(endpoint,' in text['web-api'] and "process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8080'" in text['vite-proxy'] and 'ws:' not in text['vite-proxy'])
block = '\n'.join(text['web-dispatch'].splitlines()[395:465])
empty = schema['$defs']['EmptyRequest']
check('static causal RED: Studio nonempty body cannot satisfy EmptyRequest', empty['additionalProperties'] is False and 'workspaceId: selectedWorkspaceId' in block and 'body: JSON.stringify({' in block and 'idempotencyKey' not in block and 'validate_contract("EmptyRequest", await request.json())' in text['api-create'])
check('static causal RED: required Idempotency-Key not supplied by Studio', 'Idempotency-Key required' in text['api-idempotency'] and 'options.idempotencyKey' in text['web-api'] and 'idempotencyKey' not in block)
r = subprocess.run(['git','grep','-n','-e','/start/prepare','-e','/start/enqueue',S,'--','apps/web/src'],capture_output=True)
check('no fixed frontend first-Workspace prepare/enqueue literal call', r.returncode == 1 and r.stdout == b'')
check('backend first-Workspace routes available', '/start/prepare' in text['api-first-start'] and '/start/enqueue' in text['api-first-start'])
check('business routes do not override project Run create', '/runs' not in raw(S,'src/saintvision/api/v1/projects.py').decode())
pilot = json.loads(raw(R,d['publicInputs'][0]['path']))
actual = next(n for n in pilot['freshRealAdminProjectAPIs']['nodes'] if n['node']['nodeId'] == w['nodeId'])
check('default PC3 resource bindings equal actual public readback', w['resources'] == {r['kind']:r['resourceId'] for r in actual['resourceUsage']['resources']})
check('unused SSE helper is not portal acceptance', len(git('grep','-n','SseStreamManager',S,'--','apps/web/src').decode().splitlines()) == 1)
check('existing three pilot observations distinct from live Run', c['rootObservation']['nodeCount'] == 3 and c['rootObservation']['contribution']['totalCPUMillis'] == 1500 and c['rootObservation']['contribution']['totalMemoryBytes'] == 201326592 and c['rootObservation']['actualUserRun'] == 'NOT_RUN')
check('new routing and repair stay unapplied', e['rootOnlyRouteProposal']['mainOperationPermittedByThisRecipe'] is False and e['boundedRequiredChange']['status'] == 'SOURCE_DEFECT_PROVEN_STATIC_NOT_IMPLEMENTED')
receipt = {'atKST':datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds'),'command':'D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe -B docs/vault/30_Development/Evidence/fleet5-cp-workspace-deploy-recipe-r1-20261107-codex/verify-static.py','python':sys.version,'exit':0,'passed':len(passed),'checks':passed,'inputsSHA256':{n:sha((HERE/n).read_bytes()) for n in ['context.json','source-bindings.json','typed-examples.json','recipe.md','verify-static.py']},'meaning':'Source/AST/type/key/path/immutable-data checks only, including static causal contract mismatch; no HTTP or product runtime tests and no actual secrets/JWKS/crypto inspected'}
(HERE/'static-verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps({'exit':0,'staticChecksPassed':len(passed),'runtimeOrHTTPTests':0}))
