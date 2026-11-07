"""Make one immutable WIP01 packet, using only own files and source/hash checks."""
import ast
import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

E = Path(__file__).resolve().parent
R = next(p for p in E.parents if (p / 'AGENTS.md').exists())
BASE = 'b3bbdc8d92a39f2f797a7680deb2770d6f705af0'
DC = 'services/control-plane/src/inv/dispatch.py'
TEST = 'tests/core/test_delivery_operation_origin.py'
HISTORY = 'docs/vault/30_Development/History/2026-11-07_FLEET5_B_A7_Operation_Guard_R1_Codex.md'
ZIP = E / 'fleet5-a7-operation-guard-r1-wip01.zip'
RECEIPT = E / 'wip01-receipt.json'
MANIFEST = E / 'wip01-manifest.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=R)


def safe(path):
    p = PurePosixPath(path)
    assert not p.is_absolute() and all(x not in ('', '.', '..') for x in p.parts)
    assert '\\' not in path and ':' not in path
    return path


def serialized(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def main():
    sys.stdout.reconfigure(encoding='utf8')
    assert not any(p.exists() for p in (ZIP, RECEIPT, MANIFEST)), 'WIP01 exists: do not overwrite frozen packet'
    assert git('rev-parse', 'HEAD').decode().strip() == BASE
    assert git('branch', '--show-current').decode().strip() == 'agent/codex/fleet5-b-a7-operation-guard-r1-20261107'
    tracked = [x for x in git('diff', '--name-only', '-z', BASE).decode('utf8').split('\0') if x]
    assert tracked == [DC], tracked
    # Baseline dependency/import/fixture surfaces stay real and byte exact.
    dependencies = []
    for path in ('tests/conftest.py', 'pyproject.toml', 'services/control-plane/pyproject.toml',
                 'requirements-core.txt', 'requirements-test.txt', 'requirements-backend.txt'):
        b = git('show', BASE + ':' + path)
        assert (R / path).read_bytes() == b
        dependencies.append({'path': path, 'bytes': len(b), 'sha256': sha(b),
                             'origin': 'REAL_BASE_GIT; not a declaration that dependencies were installed or executed here'})
    source_world = json.loads((E / 'source-world.json').read_bytes())
    for row in source_world['files']:
        b = (R / DC).read_bytes() if row['path'] == DC else git('show', BASE + ':' + row['path'])
        assert sha(b) == row['sha256']
    assert sha((R / TEST).read_bytes()) == source_world['currentTestSHA256']
    aux = json.loads((E / 'operation-obligation-auxiliary.json').read_bytes())
    assert aux['reason'] == 'EXISTING_GUARD_REFUSED_WIP_PATTERN'
    assert aux['acceptedBaselineDischarges'] == 0
    assert json.loads((E / 'static-inspection-attempt1.json').read_bytes())['exit'] == 0
    assert json.loads((E / 'refusal-inspection.json').read_bytes())['exit'] == 0
    # All Evidence and the sole own History are packet inputs. The manifest is
    # outside its own entry digest set; the outer receipt binds it as well.
    inputs = [R / DC, R / TEST, R / HISTORY, *sorted(p for p in E.rglob('*') if p.is_file())]
    assert len(inputs) == len(set(inputs))
    entries, syntax = {}, []
    for path in inputs:
        name = safe(path.relative_to(R).as_posix())
        assert name in (DC, TEST, HISTORY) or name.startswith(E.relative_to(R).as_posix() + '/')
        assert not path.is_symlink()
        b = path.read_bytes()
        if path.suffix == '.py':
            ast.parse(b, name)
            syntax.append({'path': name, 'sha256': sha(b), 'ASTParseOnly': True})
        assert path.suffix != '.pyc' and '__pycache__' not in path.parts
        entries[name] = b
    entries = dict(sorted(entries.items()))
    manifest = {
        'schema': 'FLEET5_A7_OPERATION_GUARD_IMMUTABLE_WIP_V1', 'packet': 'WIP01',
        'base': BASE, 'branch': 'agent/codex/fleet5-b-a7-operation-guard-r1-20261107',
        'task': 'FLEET5-B-A7-OPERATION-GUARD-R1-20261107', 'orcaTask': 'task_a8fd2969f0b3',
        'dispatch': 'ctx_6f0f8253b8a7', 'rootMessage': 'msg_db48b2c9a36e',
        'owner': 'Codex', 'independentOperationGuardReview': 'PENDING through Root',
        'freezeKST': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
        'entrySetExcludesThisManifest': True, 'allSafeRelativePaths': True,
        'files': [{'path': name, 'bytes': len(b), 'sha256': sha(b)} for name, b in entries.items()],
        'nonDocFiles': [DC, TEST], 'realBaseDependencySurfaces': dependencies,
        'sourceWorldCount': 25, 'sourceWorldManifestSHA256': sha((E / 'source-world.json').read_bytes()),
        'productSHA256': sha(entries[DC]), 'testSHA256': sha(entries[TEST]),
        'completeProductAndTestDiffSHA256': sha((E / 'complete-product-test.diff.txt').read_bytes()),
        'newOwnDocsArePresentInFull': True, 'finalSyntaxInspections': syntax,
        'inspectionOnly': True, 'actualProductImportAndTests': 'NOT_RUN locally',
        'noLocalCommitPushCI': True, 'wholeCandidate': aux['status'], 'reason': aux['reason'],
        'acceptedDischarges': 0, 'baseline19': 'HOLD unchanged', 'runtimeB': 0, 'realBindings': None,
        'rootMustDecideGuardCompatibility': True,
    }
    MANIFEST.write_bytes(serialized(manifest))
    entries[safe(MANIFEST.relative_to(R).as_posix())] = MANIFEST.read_bytes()
    entries = dict(sorted(entries.items()))
    with zipfile.ZipFile(ZIP, 'x', compression=zipfile.ZIP_STORED) as z:
        for name, b in entries.items():
            info = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, b)
    with zipfile.ZipFile(ZIP) as z:
        assert z.namelist() == list(entries)
        assert z.testzip() is None
        for name, b in entries.items():
            assert z.read(name) == b
            assert (R / name).read_bytes() == b
    b = ZIP.read_bytes()
    receipt = {
        'schema': 'FLEET5_WIP01_FROZEN_RECEIPT_V1', 'packet': ZIP.relative_to(R).as_posix(),
        'base': BASE, 'zipSHA256': sha(b), 'zipBytes': len(b), 'entryCount': len(entries),
        'entrySet': [{'path': n, 'bytes': len(v), 'sha256': sha(v)} for n, v in entries.items()],
        'productSHA256': sha(entries[DC]), 'testSHA256': sha(entries[TEST]),
        'manifestSHA256': sha(MANIFEST.read_bytes()), 'fullArchiveReadbackAndCurrentFileHashMatch': True,
        'allPathsSafeRelative': True, 'zipCRCCheck': 'PASS',
        'argv': [sys.executable, '-B', str(Path(__file__).relative_to(R))],
        'exitOnSuccessfulReceipt': 0, 'checks': 'source/hash/AST/archive readback only; no product tests/imports',
        'actualProductTests': 'NOT_RUN', 'candidate': 'UNRESOLVED_OPERATION_ORIGIN',
        'reason': 'EXISTING_GUARD_REFUSED_WIP_PATTERN', 'guardChanged': False,
        'publication': 'NOT_AUTHORIZED at this WIP stage; no commit/push/CI',
        'independentOperationGuardReview': 'PENDING', 'runtimeB': 0, 'realBindings': None,
    }
    RECEIPT.write_bytes(serialized(receipt))
    print(json.dumps({k: v for k, v in receipt.items() if k != 'entrySet'}))


if __name__ == '__main__':
    main()
