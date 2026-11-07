"""Freeze the new WIP02 packet; only hash/AST/archive inspection is performed."""
import ast
import datetime
import difflib
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
ZIP = E / 'fleet5-a7-operation-guard-r1-wip02.zip'
MANIFEST = E / 'wip02-manifest.json'
RECEIPT = E / 'wip02-receipt.json'
PATCH = E / 'wip02-full-product-test.diff.txt'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=R)


def encoded(x):
    return (json.dumps(x, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def safe(name):
    path = PurePosixPath(name)
    assert not path.is_absolute() and all(p not in ('', '.', '..') for p in path.parts)
    assert '\\' not in name and ':' not in name
    return name


def main():
    sys.stdout.reconfigure(encoding='utf8')
    assert not any(p.exists() for p in (ZIP, MANIFEST, RECEIPT, PATCH)), 'WIP02 exists; never overwrite'
    assert git('rev-parse', 'HEAD').decode().strip() == BASE
    assert git('branch', '--show-current').decode().strip() == 'agent/codex/fleet5-b-a7-operation-guard-r1-20261107'
    tracked = [p for p in git('diff', '--name-only', '-z', BASE).decode('utf8').split('\0') if p]
    assert tracked == [DC]
    oldreceipt = json.loads((E / 'wip01-receipt.json').read_bytes())
    oldzip = R / oldreceipt['packet']
    assert sha(oldzip.read_bytes()) == oldreceipt['zipSHA256'] == '28c87c268baaf551dde15fcb35f0eb6d3b24b6861e8c1cfcb845fcb6e0a96f37'
    # WIP01 itself stays immutable. Only own History gets its authorized WIP02
    # continuation; every other old entry must still equal the frozen bytes.
    with zipfile.ZipFile(oldzip) as z:
        for row in oldreceipt['entrySet']:
            b = z.read(row['path'])
            assert sha(b) == row['sha256']
            if row['path'] != HISTORY:
                assert (R / row['path']).read_bytes() == b
    assert sha((E / 'existing-guard-refusal.json').read_bytes()) == '3f5e6214ca11c7b08f54412f3f351242651bc6b9b4477df0f9512859488c5759'
    inputs = json.loads((E / 'inputs.json').read_bytes())
    for row in inputs['immutableHelperInputs']:
        assert sha((R / row['path']).read_bytes()) == row['sha256']
    proof = json.loads((E / 'wip02-finite-proof.json').read_bytes())
    assert proof['classification'] == 'EXACT_CAPTURE_GUARD_DELTA_COVERED_WITH_LEGACY_REFUSAL_PRESERVED'
    assert proof['legacyStatus'] == 'REFUSED' and proof['legacyGuardCompatibilityClean'] is False
    assert proof['acceptedBaselineDischarges'] == 0 and proof['runtimeB'] == 0 and proof['realBindings'] is None
    assert json.loads((E / 'wip02-static-attempt1.json').read_bytes())['exit'] == 0
    controls = json.loads((E / 'wip02-finite-control-results.json').read_bytes())
    assert controls['count'] == 21 and controls['allExpected'] is True
    for row in proof['sourceWorld']:
        b = (R / row['path']).read_bytes()
        assert sha(b) == row['sha256']
        base = git('show', BASE + ':' + row['path'])
        assert sha(base) == row['baseSHA256']
        if row['path'] != DC:
            assert b == base
    root = json.loads((E / 'root-verified-unit-observation.json').read_bytes())
    assert root['greenProductSHA256'] == sha((R / DC).read_bytes()) == '82f029614537eb5bab56934e4b6736fe3dd52ece54b9b9a3996815b131e41de4'
    assert root['testSHA256'] == sha((R / TEST).read_bytes()) == '3dacdb63f83ab1d8075ddcbe422d82daad20bd56f643adee0fc7ae97715925d2'
    assert root['redRealBaseProductSHA256'] == sha(git('show', BASE + ':' + DC))
    diff = git('diff', BASE, '--', DC)
    newtest = (R / TEST).read_bytes()
    newdiff = ''.join(difflib.unified_diff([], newtest.decode('utf8').splitlines(keepends=True), fromfile='/dev/null', tofile='b/' + TEST)).encode()
    PATCH.write_bytes(diff + newdiff)
    assert PATCH.read_bytes() == (E / 'complete-product-test.diff.txt').read_bytes()
    paths = [R / DC, R / TEST, R / HISTORY, *sorted(p for p in E.rglob('*') if p.is_file())]
    entries, syntax = {}, []
    for path in paths:
        name = safe(path.relative_to(R).as_posix())
        assert name in (DC, TEST, HISTORY) or name.startswith(E.relative_to(R).as_posix() + '/')
        assert not path.is_symlink() and '__pycache__' not in path.parts and path.suffix != '.pyc'
        b = path.read_bytes()
        if path.suffix == '.py':
            ast.parse(b, name)
            syntax.append({'path': name, 'sha256': sha(b), 'ASTOnly': True})
        assert name not in entries
        entries[name] = b
    entries = dict(sorted(entries.items()))
    manifest = {
        'schema': 'FLEET5_A7_OPERATION_GUARD_WIP02_V1', 'packet': 'WIP02',
        'rootDecision': 'msg_f730b53fb339', 'previousAsk': 'msg_d3f6facfd6b5',
        'task': inputs['task'], 'orcaTask': inputs['orcaTask'], 'dispatch': inputs['dispatch'],
        'owner': 'Codex', 'independentCODEReview': 'PENDING through Root', 'base': BASE,
        'branch': inputs['branch'], 'kst': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
        'entrySetExcludesThisManifest': True, 'allPathsSafeRelative': True,
        'files': [{'path': n, 'bytes': len(b), 'sha256': sha(b)} for n, b in entries.items()],
        'productSHA256': sha(entries[DC]), 'testSHA256': sha(entries[TEST]),
        'fullProductTestPatchSHA256': sha(PATCH.read_bytes()),
        'newOwnProofAndDocsPresentAsFullEntries': True,
        'WIP01SHA256': sha(oldzip.read_bytes()), 'WIP01AllEntriesExceptAuthorizedHistoryCurrentBytesUnchanged': True,
        'sourceWorldCount': 25, 'sourceWorld': proof['sourceWorld'], 'finalSyntaxOnly': syntax,
        'finiteClassification': proof['classification'], 'legacyStatus': 'REFUSED', 'legacyGuardCompatibilityClean': False,
        'legacyDiagnosticSHA256': sha((E / 'existing-guard-refusal.json').read_bytes()),
        'unchangedHelperCount': len(inputs['immutableHelperInputs']), 'legacyAllowanceAdded': False,
        'staticControlCount': controls['count'], 'staticControlsAllExpected': controls['allExpected'],
        'rootActualUnitAttribution': 'Root verified receipt 09:46:10 KST; GREEN24/direct0 and realBASE RED1failed/direct1; not author rerun',
        'rootVerifiedObservationSHA256': sha((E / 'root-verified-unit-observation.json').read_bytes()),
        'rootPublicProjectionSHA256': sha((E / 'root-collect-public-projection.json').read_bytes()),
        'actualAuthorProductExecution': False, 'acceptedBaselineDischarges': 0, 'original19': 'HOLD unchanged',
        'actualPeakMemory': 'NOT_MEASURED', 'installedVenvBeforeAfterInventory': 'NOT_MEASURED',
        'runtimeB': 0, 'realBindings': None, 'A1A16': 'pending', 'fullProgram': 'incomplete',
        'publicationGatesCommitPushCI': 'NOT_RUN; next Root step required',
    }
    MANIFEST.write_bytes(encoded(manifest))
    entries[safe(MANIFEST.relative_to(R).as_posix())] = MANIFEST.read_bytes()
    entries = dict(sorted(entries.items()))
    with zipfile.ZipFile(ZIP, 'x', compression=zipfile.ZIP_STORED) as z:
        for name, b in entries.items():
            info = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0))
            info.create_system, info.external_attr = 3, 0o100644 << 16
            z.writestr(info, b)
    with zipfile.ZipFile(ZIP) as z:
        assert z.namelist() == list(entries) and z.testzip() is None
        for name, b in entries.items():
            assert z.read(name) == b and (R / name).read_bytes() == b
    data = ZIP.read_bytes()
    receipt = {
        'schema': 'FLEET5_WIP02_FROZEN_RECEIPT_V1', 'packet': ZIP.relative_to(R).as_posix(),
        'base': BASE, 'zipSHA256': sha(data), 'zipBytes': len(data), 'entryCount': len(entries),
        'entrySet': [{'path': n, 'bytes': len(v), 'sha256': sha(v)} for n, v in entries.items()],
        'manifestSHA256': sha(MANIFEST.read_bytes()), 'productSHA256': sha(entries[DC]), 'testSHA256': sha(entries[TEST]),
        'fullPatchSHA256': sha(PATCH.read_bytes()), 'allSafeRelativePaths': True,
        'archiveCurrentFileHashReadbackAndCRC': True, 'WIP01Unchanged': True,
        'legacyDiagnosticUnchanged': True, 'legacyStatus': 'REFUSED',
        'finiteClassification': proof['classification'], 'controls': 21, 'allExpected': True,
        'RootUnitResult': 'GREEN24/direct0; realBASE causalRED1failed/direct1, attributed, not author rerun',
        'argv': [sys.executable, '-B', Path(__file__).relative_to(R).as_posix()], 'exitOnSuccessfulReceipt': 0,
        'authorActualProductExecution': False, 'baselineDischarges': 0, 'runtimeB': 0, 'realBindings': None,
        'independentCODEReview': 'PENDING', 'publicationGatesCommitPushCI': 'NOT_RUN',
        'nextOwner': 'Root verifies WIP02 then authorizes normal gates/publication/appropriate CI/actual CODE review',
    }
    RECEIPT.write_bytes(encoded(receipt))
    print(json.dumps({k: v for k, v in receipt.items() if k != 'entrySet'}))


if __name__ == '__main__':
    main()
