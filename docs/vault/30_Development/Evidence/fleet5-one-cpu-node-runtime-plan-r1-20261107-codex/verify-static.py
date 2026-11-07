"""Static Git/DATA verification only; imports no product modules or crypto libraries."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone


ROOT = Path(__file__).resolve().parent
SOURCE = '1efea494f026e932360c35ae811b6423d874a2e7'
BASE = 'b51d827e507a35aca3737e31103bd3b3311298a5'
PUBLIC = 'ae211280c5c8ab50b19303450288ba1421af827e'
checks = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


def git(*args):
    return subprocess.check_output(['git', *args])


def raw(ref, path):
    return git('show', ref + ':' + path)


def sha(value):
    return hashlib.sha256(value).hexdigest()


plan = json.loads((ROOT / 'runtime-plan.json').read_bytes())
bindings = json.loads((ROOT / 'source-bindings.json').read_bytes())
check('delivery base differs from exact product target', plan['deliveryBase'] == BASE and plan['sourceTarget'] == SOURCE and BASE != SOURCE)
check('exact new delivery branch', git('branch', '--show-current').decode().strip() == plan['branch'])
check('base is delivery ancestor', subprocess.run(['git', 'merge-base', '--is-ancestor', BASE, 'HEAD'], capture_output=True).returncode == 0)
check('source is not implicitly integrated in delivery', subprocess.run(['git', 'merge-base', '--is-ancestor', SOURCE, 'HEAD'], capture_output=True).returncode == 1)
source_text = {}
for item in bindings['bindings']:
    value = raw(SOURCE, item['path'])
    lines = value.decode().splitlines()
    excerpt = '\n'.join(lines[item['lineStart']-1:item['lineEnd']]) + '\n'
    check(item['id'] + ' immutable blob/file/line range', item['ref'] == SOURCE and sha(value) == item['fileSHA256'] and git('rev-parse', SOURCE + ':' + item['path']).decode().strip() == item['gitBlobSHA1'] and 1 <= item['lineStart'] <= item['lineEnd'] <= len(lines) and sha(excerpt.encode()) == item['lineExcerptSHA256'])
    source_text[item['id']] = value.decode()
    if item['path'].endswith('.py'):
        ast.parse(value.decode('utf-8-sig'), filename=item['path'])
for item in bindings['publicRootArtifacts']:
    check('public Root input ' + item['path'].split('/')[-1], item['ref'] == PUBLIC and sha(raw(PUBLIC, item['path'])) == item['sha256'])
pub = json.loads(raw(PUBLIC, bindings['publicRootArtifacts'][0]['path']))
p = plan['publicParameters']
for name, expected in {'tenantId': pub['tenant'], 'projectId': pub['project'], 'recoveryEpoch': pub['epoch'], 'expectedTenantControlVersion': 0, 'endpoint': pub['endpoint']['planned'], 'cpuMillis': 500, 'memoryBytes': 67108864, **{k:v for k,v in pub['newPlannedIDs'].items() if k != 'registeredOrReserved'}}.items():
    check('public value ' + name, p[name] == expected)
check('public exact plan hash', bindings['publicRootArtifacts'][0]['sha256'] == '5b2a70bd9bc8217592f7cd953f18dd3516ecacfd132f6281134fbc718731213a')
schema = json.loads(raw(SOURCE, 'contracts/v1alpha1/core.schema.json'))['$defs']
check('six exact source contract shapes', all(shape == schema[name] for name, shape in bindings['contractShapes'].items()) and len(bindings['contractShapes']) == 6)
check('closed peer policy template key set', set(plan['peerPolicyTemplate']['value']) == set(schema['NodePeerPolicy']['required']) and schema['NodePeerPolicy']['additionalProperties'] is False)
fields = next(n.value for n in ast.parse(source_text['fresh-request']).body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'FIELDS' for t in n.targets))
if isinstance(fields, ast.Call):
    fields = fields.args[0]
check('closed admission template source keys', set(plan['admission']['requestTemplate']) == set(ast.literal_eval(fields)))
check('workload and resource template field names', set(plan['firstWorkspace']['workloadTemplate']) <= set(schema['WorkloadSpec']['properties']) and set(plan['firstWorkspace']['workloadTemplate']['resources']) == set(schema['ResourceRequest']['required']))
for index, shape in [(1, 'WorkspaceStartPrepareInput'), (3, 'ApprovalDecisionInput'), (4, 'WorkspaceStartEnqueueInput')]:
    check(shape + ' request keys', set(plan['firstWorkspace']['orderedAPI'][index]['bodyKeys']) == set(schema[shape]['required']))
for step in plan['firstWorkspace']['orderedAPI']:
    if 'path' in step:
        check('API route ' + step['path'], step['path'] in source_text['api-first-start-routes'])
flags = [v[2:] for v in plan['nodeArgvTemplate']['argv'][1:] if v.startswith('--')]
declared = set(re.findall(r'flag\.(?:String|Bool|Int|Int64)Var\([^,]+, "([^"]+)"', source_text['node-cli']))
check('exact declared double-dash Node flags', len(flags) == len(set(flags)) and set(flags) <= declared and {'serve', 'peer-policy', 'tls-cert', 'tls-key', 'client-ca', 'state', 'public-key'} <= set(flags))
check('excluded features absent from argv', not set(plan['nodeArgvTemplate']['excludedFlags']) & set(plan['nodeArgvTemplate']['argv']))
check('separate signer/TLS identity and pending certificate', plan['pki']['launchSigner']['algorithm'] == 'Ed25519' and plan['pki']['nodeLeaf']['DER_SHA256'] is None and plan['pki']['cpClientLeaf']['DER_SHA256'] is None)
check('profile CP ceilings distinct from Node fixed ceilings', plan['runtimeProfileTemplate']['value']['max_cpu_millis'] == 500 and plan['runtimeProfileTemplate']['nodeBuiltInCeilings']['cpuMillis'] == 1000 and 'config.MaxCPU = 1000' in source_text['node-cli'])
check('profile object matches workspace fragment', plan['cpWorkspaceTemplate']['workspace']['profile'] == plan['runtimeProfileTemplate']['value'])
check('actual DER request is deliberately incomplete', plan['admission']['requestTemplate']['certificateDERBase64'] is None and plan['admission']['status'] == 'NOT_VALID_REQUEST_DER_MISSING')
check('Docker server minimum explicitly unresolved', plan['deployment']['dockerCompatibility']['observedMinimum'] is None and plan['deployment']['dockerCompatibility']['clientCap'] == '1.45')
check('no claimed runtime authority/review/discharge', plan['authority'] == {'actualAuthority': None, 'actualAdmission': 'NOT_RUN', 'nodeExecuted': False, 'observation': 'NOT_RUN', 'run': 'NOT_RUN', 'independentPlanReview': 'PENDING_ROOT', 'K2': 'NULL_HOLD', 'operationalDischarges': 0, 'wholeProgramComplete': False})
ids = {b['id'] for b in bindings['bindings']}
check('all plan source binding IDs resolve', all(set(v['sourceBindings']) <= ids for v in plan.values() if isinstance(v, dict) and 'sourceBindings' in v))
check('reconcile bytes match accepted public artifact', plan['admission']['reconcile']['entrySHA256'] == sha(raw(PUBLIC, plan['admission']['reconcile']['entryPath'])))
receipt = {'atKST': datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds'), 'command': 'D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe -B docs/vault/30_Development/Evidence/fleet5-one-cpu-node-runtime-plan-r1-20261107-codex/verify-static.py', 'python': sys.version, 'exit': 0, 'sourceTarget': SOURCE, 'deliveryBase': BASE, 'checksPassed': len(checks), 'checks': checks, 'inputSHA256': {name: sha((ROOT/name).read_bytes()) for name in ['runtime-plan.json', 'source-bindings.json', 'verify-static.py']}, 'meaning': 'Static source/Git/DATA proof only; no product imports, crypto, host, DB or runtime execution'}
(ROOT / 'static-verification.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8', newline='\n')
print(json.dumps({'exit': 0, 'checksPassed': len(checks), 'meaning': receipt['meaning']}))
