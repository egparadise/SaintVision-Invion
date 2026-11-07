"""Read-only source/doc inventory and own Evidence copies; no product imports."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

E = Path(__file__).resolve().parent
R = next(p for p in E.parents if (p / 'AGENTS.md').exists())
ROOT = R.parent / 'fleet-five-orchestration-20261105'
BASE = 'b3bbdc8d92a39f2f797a7680deb2770d6f705af0'
REVIEW = 'e75b051d8dcd39b24dba4b648d74d7f7adecbd0f'
PREVIOUS = E.parent / 'fleet5-b-a7-mode-origin-r1-20261107-codex'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git(*args, root=R):
    return subprocess.check_output(['git', *args], cwd=root)


def emit(name, value):
    (E / name).write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode())


def main():
    sys.stdout.reconfigure(encoding='utf8')
    assert git('rev-parse', 'HEAD').decode().strip() == BASE
    assert git('branch', '--show-current').decode().strip() == 'agent/codex/fleet5-b-a7-operation-guard-r1-20261107'
    previous = json.loads((PREVIOUS / 'inputs.json').read_bytes())
    docs = []
    for old in previous['docs']:
        raw = old['path']
        path = ROOT / raw.removeprefix('ROOT_READ_ONLY/') if raw.startswith('ROOT_READ_ONLY/') else R / raw
        b = path.read_bytes()
        s = b.decode('utf-8-sig')
        front = s.split('---', 2)[1].strip() if s.startswith('---') else None
        docs.append({'path': raw, 'sha256': sha(b), 'bytes': len(b), 'frontmatter': front,
                     'sameBytesAsPriorRead': sha(b) == old['sha256']})
        print(json.dumps({'read': raw, 'sha256': sha(b), 'frontmatter': front}, ensure_ascii=False))
    names = git('diff-tree', '--no-commit-id', '--name-only', '-r', '-z', REVIEW).decode('utf8').split('\0')
    originals = []
    for path in sorted(p for p in names if p):
        assert path.startswith('docs/vault/30_Development/Evidence/fleet5-b-a7-mode-b3bb-review-20261107-claude/') or path == 'docs/vault/30_Development/History/2026-11-07_FLEET5_B_A7_Mode_B3BB_독립검토_Claude.md'
        b = git('show', REVIEW + ':' + path)
        b.decode('utf-8-sig')
        copy = 'review-original-history.md.txt' if '/History/' in path else 'review-original-' + path.rsplit('/', 1)[1].removeprefix('.')
        if not copy.endswith(('.txt', '.json')):
            copy += '.txt'
        (E / copy).write_bytes(b)
        originals.append({'commit': REVIEW, 'path': path, 'copy': copy, 'bytes': len(b), 'sha256': sha(b),
                          'objectID': git('rev-parse', REVIEW + ':' + path).decode().strip()})
    assert len(originals) == 13
    helper_paths = git('ls-tree', '-r', '--name-only', BASE, '--', str((E.parent / 'fleet5-b-a7-snapshot-r2-20261107-codex').relative_to(R)).replace('\\', '/')).decode('utf8').splitlines()
    helpers = []
    for p in helper_paths + [str((PREVIOUS / 'mode.py').relative_to(R)).replace('\\', '/')]:
        if p.endswith('.py'):
            b = git('show', BASE + ':' + p)
            assert (R / p).read_bytes() == b
            helpers.append({'path': p, 'sha256': sha(b), 'objectID': git('rev-parse', BASE + ':' + p).decode().strip()})
    emit('inputs.json', {
        'task': 'FLEET5-B-A7-OPERATION-GUARD-R1-20261107', 'orcaTask': 'task_a8fd2969f0b3',
        'dispatch': 'ctx_6f0f8253b8a7', 'rootMessage': 'msg_db48b2c9a36e', 'owner': 'Codex',
        'reviewer': 'Independent actual operation guard review through Root PENDING',
        'base': BASE, 'branch': 'agent/codex/fleet5-b-a7-operation-guard-r1-20261107',
        'priorImmutableProductSource': '72028cbac903c4415d9979f980a6e0f9948e914f',
        'sourceWorld': 'Real base Git b3bb for all first-party files, overlay only current WIP dispatch.py; not product72028 labelled as WIP',
        'kst': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
        'rootHeadAtRead': git('rev-parse', 'HEAD', root=ROOT).decode().strip(), 'docs': docs,
        'reviewOriginals': originals, 'immutableHelperInputs': helpers,
        'scope': ['DeliveryWorker.once only in services/control-plane/src/inv/dispatch.py',
                  'new tests/core/test_delivery_operation_origin.py',
                  'only own unique Evidence prefix and History'],
        'localAllowed': 'Syntax/AST/source/hash/static DATA inspection only; no product import/test execution',
        'notRun': ['actual Python product imports/pytest', 'Go/Node/browser/full Core', 'network/host/SSH/Docker/PG/crypto/PKI',
                   'Docs/ontology/sync publication gates', 'commit/push/CI', 'independent operation guard review'],
        'globalStatus': {'baseline19': 'HOLD unchanged', 'acceptedDischarges': 0, 'actualRuntimeB': 0, 'realBindings': None,
                         'A1A16': 'pending', 'fleet': 'incomplete', 'entries': 12, 'edges': 19,
                         'split': [16, 3], 'accounting': [598, 757, 1071, 21, 573, 218]},
        'developmentFailures': [{'phase': 'read-only current docs stdout inventory', 'exit': 1,
                                 'cause': 'cp949 stdout UnicodeEncodeError before completion',
                                 'correction': 'UTF8 stdout in this script; no product executed'}],
    })
    print(json.dumps({'reviewOriginals': len(originals), 'immutableHelperFiles': len(helpers), 'productImported': False}))


if __name__ == '__main__':
    main()
