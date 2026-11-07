"""Serial authorized publication gates; captures source/state and exact exits."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

E = Path(__file__).resolve().parent
R = next(p for p in E.parents if (p / 'AGENTS.md').exists())
ROOT = R.parent / 'fleet-five-orchestration-20261105'
BASE = 'b3bbdc8d92a39f2f797a7680deb2770d6f705af0'
STATE = Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def kst():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()


def write(name, value):
    path = E / name
    assert not path.exists(), 'Never overwrite publication evidence: ' + name
    path.write_bytes((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())


def main():
    sys.stdout.reconfigure(encoding='utf8')
    source = ROOT / '.work/b-operation-wip02-root-verified.json'
    raw = source.read_bytes()
    root = json.loads(raw)
    assert root['WIP02SHA256'] == sha((E / 'fleet5-a7-operation-guard-r1-wip02.zip').read_bytes())
    for path, digest in [('services/control-plane/src/inv/dispatch.py', root['productSHA256']),
                         ('tests/core/test_delivery_operation_origin.py', root['testSHA256'])]:
        assert sha((R / path).read_bytes()) == digest
    for row in root['priorUntrackedOtherCardReceiptsPreservedExcludedFromPublication']:
        b = (R / row['path']).read_bytes()
        assert sha(b) == row['SHA256'] and len(b) == row['bytes']
    assert len(root['priorUntrackedOtherCardReceiptsPreservedExcludedFromPublication']) == 14
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=R).decode().strip() == BASE
    write('publication-root-context.json', {'rootDecision': 'msg_fb188c4045e5', 'atKST': kst(),
          'base': BASE, 'source': 'ROOT_READ_ONLY/.work/b-operation-wip02-root-verified.json',
          'sourceSHA256': sha(raw), 'RootVerification': root,
          'stageScope': ['services/control-plane/src/inv/dispatch.py', 'tests/core/test_delivery_operation_origin.py',
                         'docs/vault/30_Development/History/2026-11-07_FLEET5_B_A7_Operation_Guard_R1_Codex.md',
                         E.relative_to(R).as_posix() + '/'],
          'wholeWorktreeClean': False, 'reason': '14 known preserved and excluded untracked prior-card post-CI receipts',
          'actualProductTestsByAuthor': 'NOT_RUN', 'independentCODEReview': 'PENDING'})
    commands = [
        [sys.executable, '-B', 'tools/check_docs.py'],
        [sys.executable, '-B', 'tools/check_ontology.py'],
        [sys.executable, '-B', 'tools/check_doc_path_citations.py', '--ratchet', '--base-ref', BASE],
        [sys.executable, '-B', 'tools/check_doc_single_source.py', '--ratchet'],
        [sys.executable, '-B', 'tools/sync_obsidian.py', '--check', '--state', str(STATE),
         '--conflicts-out', str(E / 'publication-sync-check-conflicts.json')],
        ['git', 'diff', '--check', BASE],
    ]
    receipts = []
    for number, argv in enumerate(commands, 1):
        before = STATE.read_bytes() if number == 5 else None
        if before is not None:
            (E / 'publication-sync-state-before.json').write_bytes(before)
        start = kst()
        result = subprocess.run(argv, cwd=R, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1'))
        end = kst()
        after = STATE.read_bytes() if before is not None else None
        if after is not None:
            (E / 'publication-sync-state-after.json').write_bytes(after)
        write(f'publication-gate{number:02d}-raw.json', {'encoding': 'utf-8', 'rawSHA256': sha(result.stdout),
              'rawBytes': len(result.stdout), 'text': result.stdout.decode('utf8')})
        row = {'argv': argv, 'startKST': start, 'endKST': end, 'exit': result.returncode,
               'rawOutputWrapper': f'publication-gate{number:02d}-raw.json', 'rawOutputSHA256': sha(result.stdout)}
        if before is not None:
            row.update({'fullStateBeforeSHA256': sha(before), 'fullStateAfterSHA256': sha(after),
                        'fullStateBeforeBytes': len(before), 'fullStateAfterBytes': len(after),
                        'stateBytesEqual': before == after, 'CHECKOnly': True,
                        'stateChangePolicy': 'Root may advance concurrently; actual changes retained, never overwritten'})
        receipts.append(row)
        write(f'publication-gate{number:02d}-receipt.json', row)
        print(json.dumps({**row, 'tail': result.stdout.decode('utf8')[-800:]}), flush=True)
        if result.returncode:
            write('publication-gates-stopped.json', {'atKST': kst(), 'receipts': receipts, 'failedGate': row})
            raise SystemExit(result.returncode)
    write('publication-gates-complete.json', {'atKST': kst(), 'receipts': receipts, 'allExit0': True,
          'actualProductTestsByAuthor': False, 'stateSnapshotsFullAndIndependent': True})


if __name__ == '__main__':
    main()
