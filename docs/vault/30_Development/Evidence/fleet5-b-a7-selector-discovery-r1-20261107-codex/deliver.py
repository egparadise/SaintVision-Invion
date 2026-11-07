"""Bounded docs-only publication receipts. No product or probe rerun."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

E = Path(__file__).resolve().parent
R = next(p for p in E.parents if (p / 'AGENTS.md').exists())
BASE = '746789a36091c8601afea23fe176069e2fa7d87b'
HISTORY = 'docs/vault/30_Development/History/2026-11-07_FLEET5_B_A7_Selector_Discovery_R1_Codex.md'
STATE = Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def kst():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()


def emit(name, value):
    path = E / name
    assert not path.exists(), name
    path.write_bytes((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())


def git(*args):
    return subprocess.check_output(['git', *args], cwd=R)


def preserve():
    inputs = json.loads((E / 'probe01/inputs.json').read_bytes())
    for row in inputs['priorResidualUntrackedPreserveAndExclude']:
        assert sha((R / row['path']).read_bytes()) == row['sha256'], row['path']
    for row in inputs['publishedProofInputs'] + inputs['old29Helpers']:
        assert sha((R / row['path']).read_bytes()) == row['sha256'], row['path']
    for path, digest in [('services/control-plane/src/inv/dispatch.py', '82f029614537eb5bab56934e4b6736fe3dd52ece54b9b9a3996815b131e41de4'),
                         ('tests/core/test_delivery_operation_origin.py', '3dacdb63f83ab1d8075ddcbe422d82daad20bd56f643adee0fc7ae97715925d2')]:
        assert sha((R / path).read_bytes()) == digest and sha(git('show', BASE + ':' + path)) == digest


def gates():
    assert git('rev-parse', 'HEAD').decode().strip() == BASE
    assert git('diff', '--name-only') == b'' and git('diff', '--cached', '--name-only') == b''
    preserve()
    commands = [
        [sys.executable, '-B', 'tools/check_docs.py'],
        [sys.executable, '-B', 'tools/check_ontology.py'],
        [sys.executable, '-B', 'tools/check_doc_path_citations.py', '--ratchet', '--base-ref', BASE],
        [sys.executable, '-B', 'tools/check_doc_single_source.py', '--ratchet'],
        [sys.executable, '-B', 'tools/sync_obsidian.py', '--check', '--state', str(STATE),
         '--conflicts-out', str(E / 'sync-check-conflicts.json')],
        ['git', 'diff', '--check', BASE],
    ]
    rows = []
    for number, argv in enumerate(commands, 1):
        before = STATE.read_bytes() if number == 5 else None
        if before is not None:
            (E / 'sync-full-state-before.json').write_bytes(before)
        start = kst()
        result = subprocess.run(argv, cwd=R, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1'))
        end = kst()
        after = STATE.read_bytes() if before is not None else None
        if after is not None:
            (E / 'sync-full-state-after.json').write_bytes(after)
        row = {'argv': argv, 'cwd': str(R), 'interpreter': sys.version, 'startKST': start, 'endKST': end,
               'directExit': result.returncode, 'outputEncoding': 'UTF8-in-JSON-verbatim',
               'rawBytes': len(result.stdout), 'rawSHA256': sha(result.stdout), 'rawUTF8': result.stdout.decode('utf8')}
        if before is not None:
            row.update({'fullStateBeforeSHA256': sha(before), 'fullStateAfterSHA256': sha(after),
                        'fullStateBeforeBytes': len(before), 'fullStateAfterBytes': len(after),
                        'stateBytesEqual': before == after, 'CHECKOnly': True,
                        'concurrentStatePolicy': 'Retain actual Root state changes; no author state write/apply/adopt/resolve/export'})
        emit(f'gate{number:02d}.json', row)
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != 'rawUTF8'}), flush=True)
        print(row['rawUTF8'][-600:], flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    preserve()
    emit('gates-complete.json', {'receipts': rows, 'allDirectExit0': True,
         'probeNotRerun': True, 'productAndTestUnchanged': True, 'runtimeB': 0})


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    assert sys.argv[1:] == ['gates']
    gates()
