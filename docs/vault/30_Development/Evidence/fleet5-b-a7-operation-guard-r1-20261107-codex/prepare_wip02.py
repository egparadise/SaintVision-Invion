"""Preserve attributed Root observations; no runtime or remote action here."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

E = Path(__file__).resolve().parent
R = next(p for p in E.parents if (p / 'AGENTS.md').exists())
ROOT = R.parent / 'fleet-five-orchestration-20261105'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def emit(name, value):
    (E / name).write_bytes((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())


def main():
    sys.stdout.reconfigure(encoding='utf8')
    expected = {'services/control-plane/src/inv/dispatch.py': '82f029614537eb5bab56934e4b6736fe3dd52ece54b9b9a3996815b131e41de4',
                'tests/core/test_delivery_operation_origin.py': '3dacdb63f83ab1d8075ddcbe422d82daad20bd56f643adee0fc7ae97715925d2'}
    for path, digest in expected.items():
        assert sha((R / path).read_bytes()) == digest
    assert sha((E / 'existing-guard-refusal.json').read_bytes()) == '3f5e6214ca11c7b08f54412f3f351242651bc6b9b4477df0f9512859488c5759'
    observations = []
    verified_path = ROOT / '.work/b-operation-actual-pytest-root-verified.json'
    collect_path = ROOT / '.work/b-operation-pc3-collect-root-proof.json'
    vb, cb = verified_path.read_bytes(), collect_path.read_bytes()
    verified, collect = json.loads(vb), json.loads(cb)
    assert verified['green']['passed'] == 24 and verified['green']['directExit'] == 0
    assert verified['red']['failures'] == 1 and verified['red']['directExit'] == 1
    assert verified['greenProductSHA256'] == expected['services/control-plane/src/inv/dispatch.py']
    assert verified['testSHA256'] == expected['tests/core/test_delivery_operation_origin.py']
    assert verified['WIPPacketSHA256'] == '28c87c268baaf551dde15fcb35f0eb6d3b24b6861e8c1cfcb845fcb6e0a96f37'
    (E / 'root-verified-unit-observation.json').write_bytes(vb)
    # The private remote account/job path stays in Root's private receipt only.
    # This is an explicit public projection, never a claimed byte-exact copy.
    public = {k: v for k, v in collect.items() if k != 'remoteJob'}
    emit('root-collect-public-projection.json', public)
    assert 'remoteJob' not in public
    log_checks = []
    for name, row in collect['logs'].items():
        b = row['text'].encode('utf8')
        assert len(b) == row['bytes'] and sha(b) == row['SHA256'], name
        log_checks.append({'name': name, 'bytes': len(b), 'sha256': sha(b)})
    for color, total, failures in [('green', 24, 0), ('red', 1, 1)]:
        junit = ET.fromstring(collect['logs'][color + '-tests.xml']['text'])
        suites = [junit] if junit.tag == 'testsuite' else list(junit.iter('testsuite'))
        assert sum(int(s.attrib['tests']) for s in suites) == total
        assert sum(int(s.attrib['failures']) for s in suites) == failures
        assert sum(int(s.attrib.get('errors', 0)) for s in suites) == 0
        assert sum(int(s.attrib.get('skipped', 0)) for s in suites) == 0
    red = collect['logs']['red.stdout']['text']
    assert 'tests/core/test_delivery_operation_origin.py:205: AssertionError' in red
    assert 'Rejected operation reached actual once\'s delivery call' in red
    assert 'assert [(True, False)] == []' in red
    prior = json.loads((E / 'inputs.json').read_bytes())
    docs = []
    for row in prior['docs']:
        raw = row['path']
        path = ROOT / raw.removeprefix('ROOT_READ_ONLY/') if raw.startswith('ROOT_READ_ONLY/') else R / raw
        b = path.read_bytes()
        s = b.decode('utf-8-sig')
        docs.append({'path': raw, 'sha256': sha(b), 'sameBytesAsWIP01Read': sha(b) == row['sha256'],
                     'frontmatter': s.split('---', 2)[1].strip() if s.startswith('---') else None})
    for path, raw, copy, redactions in [
        (verified_path, vb, 'root-verified-unit-observation.json', []),
        (collect_path, cb, 'root-collect-public-projection.json', ['remoteJob private account/job path omitted']),
    ]:
        observations.append({'source': 'ROOT_READ_ONLY/' + path.relative_to(ROOT).as_posix(),
                             'sourceSHA256': sha(raw), 'sourceBytes': len(raw), 'copy': copy,
                             'copySHA256': sha((E / copy).read_bytes()), 'redactions': redactions})
    emit('wip02-inputs.json', {
        'task': prior['task'], 'orcaTask': prior['orcaTask'], 'dispatch': prior['dispatch'],
        'owner': 'Codex', 'reviewer': 'Actual independent CODE review through Root PENDING',
        'rootMessage': 'msg_f730b53fb339', 'rootPreviousQuestion': 'msg_d3f6facfd6b5',
        'rootHeadAtRead': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
        'base': prior['base'], 'branch': prior['branch'],
        'kst': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
        'docs': docs, 'rootObservations': observations, 'rootLogHashesVerified': log_checks,
        'rootJUnitAndCausalRedChecked': True, 'unitResultAttribution': 'Root actual bounded verification; NOT author rerun',
        'actualPeakMemory': 'NOT_MEASURED', 'installedVenvFullBeforeAfterInventory': 'NOT_MEASURED',
        'allowedDelta': 'Only NEW own finite compatibility proof/metadata/controls/History; tested product/test raw bytes unchanged',
        'legacyGuardStatus': 'REFUSED unchanged; diagnostic bytes preserved; no old-helper allowance',
        'localActualProductImportsTests': 'NOT_RUN', 'publication': 'NOT_RUN; Root next step required',
        'runtimeB': 0, 'realBindings': None, 'original19HOLD': True,
    })
    print(json.dumps({'rootGreen': verified['green'], 'rootRed': verified['red'],
                      'logHashesChecked': len(log_checks), 'rootJUnitChecked': True,
                      'productTestRawBytesUnchanged': True, 'authorProductExecuted': False}))


if __name__ == '__main__':
    main()
