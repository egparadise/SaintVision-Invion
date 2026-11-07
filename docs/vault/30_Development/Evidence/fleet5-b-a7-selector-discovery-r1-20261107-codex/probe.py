"""Serial source/AST discovery probes. No product/test/mutant execution."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import collector

E = Path(__file__).resolve().parent
R = next(p for p in E.parents if (p / 'AGENTS.md').exists())
ROOT = R.parent / 'fleet-five-orchestration-20261105'
BASE = '746789a36091c8601afea23fe176069e2fa7d87b'
REVIEW = 'dc18f6681627aca9d3eceb7d5a85dbc97b551b5b'
OLD = E.parent / 'fleet5-b-a7-operation-guard-r1-20261107-codex'
OUT = E / 'probe01'
sys.path.insert(0, str(OLD))
import finite_compatibility as finite


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git(*argv, cwd=R):
    return subprocess.check_output(['git', *argv], cwd=cwd)


def emit(name, value):
    path = OUT / name
    assert not path.exists(), 'Never overwrite existing evidence'
    path.write_bytes((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())


def evaluate_discovered(world):
    # This comparison occurs AFTER actual target discovery and BEFORE the old
    # predicate. base_world() is never an enumeration/read input to collector.
    expected, actual = set(finite.base_world()), set(world)
    if actual != expected:
        return {'reason': 'SOURCE_WORLD_PATH_SET_CHANGED', 'existingFinitePredicateRan': False,
                'extraPaths': sorted(actual - expected), 'missingPaths': sorted(expected - actual)}
    result = finite.evaluate(world)
    return {'reason': result['reason'], 'existingFinitePredicateRan': True,
            'classification': 'EXACT_CAPTURE_GUARD_DELTA_COVERED_WITH_LEGACY_REFUSAL_PRESERVED' if result['reason'] is None else 'UNRESOLVED',
            'referenceCount': len(result.get('referenceContract', {}).get('references', [])),
            'wholeModuleNormalizedASTEqual': result.get('wholeModuleNormalizedASTEqualsDerivedBASEPlusExactDelta'),
            'other24RawBytesEqualRealBASE': result.get('other24RawBytesEqualRealBASE'),
            'ownerDerivationReason': result.get('ownerDerivationReason')}


def fixture(parent, name, world, omit=(), extra=None):
    path = parent / name
    path.mkdir()
    for root in collector.ROOTS:
        (path / root).mkdir(parents=True, exist_ok=True)
    for relative, raw in world.items():
        if relative in omit:
            continue
        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    for relative, raw in (extra or {}).items():
        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    assert not (path / '.git').exists()
    return path


def intake():
    previous = json.loads((OLD / 'inputs.json').read_bytes())
    docs = []
    for row in previous['docs']:
        relative = row['path']
        path = ROOT / relative.removeprefix('ROOT_READ_ONLY/') if relative.startswith('ROOT_READ_ONLY/') else R / relative
        raw = path.read_bytes()
        text = raw.decode('utf-8-sig')
        docs.append({'path': relative, 'sha256': sha(raw),
                     'frontmatter': text.split('---', 2)[1].strip() if text.startswith('---') else None})
    reviewed_paths = [p for p in git('diff-tree', '--no-commit-id', '--name-only', '-r', '-z', REVIEW).decode('utf8').split('\0') if p]
    review_pins = []
    verdict = None
    for path in reviewed_paths:
        raw = git('show', REVIEW + ':' + path)
        review_pins.append({'path': path, 'gitBlobID': git('rev-parse', REVIEW + ':' + path).decode().strip(),
                            'bytes': len(raw), 'sha256': sha(raw), 'kind': 'reference pin, not a new review or corpus copy'})
        if path.endswith('/review.json'):
            verdict = json.loads(raw)
    assert len(review_pins) == 17 and verdict['verdict'] == 'ACCEPT_NARROW_CODE_KEEP_HOLD'
    published = []
    for name in ('finite_compatibility.py', 'operation_proof.py', 'inputs.json', 'wip02-finite-proof.json',
                 'wip02-finite-control-results.json', 'existing-guard-refusal.json'):
        path = (OLD / name).relative_to(R).as_posix()
        raw = git('show', BASE + ':' + path)
        assert (R / path).read_bytes() == raw
        published.append({'path': path, 'sha256': sha(raw), 'gitBlobID': git('rev-parse', BASE + ':' + path).decode().strip()})
    residuals = []
    for path in git('ls-files', '--others', '--exclude-standard', '-z').decode('utf8').split('\0'):
        if not path or path.startswith(E.relative_to(R).as_posix() + '/'):
            continue
        raw = (R / path).read_bytes()
        residuals.append({'path': path, 'bytes': len(raw), 'sha256': sha(raw)})
    emit('inputs.json', {'task': 'FLEET5-B-A7-SELECTOR-DISCOVERY-R1-20261107', 'orcaTask': 'task_a8fd2969f0b3',
         'dispatch': 'ctx_6f0f8253b8a7', 'RootDecision': 'msg_984f62d6c820', 'owner': 'Codex',
         'reviewer': 'Independent delta review through Root PENDING', 'base': BASE,
         'branch': 'agent/codex/fleet5-b-a7-selector-discovery-r1-20261107',
         'kst': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
         'rootHEADAtRead': git('rev-parse', 'HEAD', cwd=ROOT).decode().strip(), 'canonicalDocs': docs,
         'acceptedCodeReview': {'commit': REVIEW, 'verdict': verdict['verdict'], 'versionedReferences': review_pins,
                                'OPG-L1': next(x for x in verdict['findings'] if x['id'] == 'OPG-L1'),
                                'OPG-I2': next(x for x in verdict['findings'] if x['id'] == 'OPG-I2')},
         'publishedProofInputs': published, 'old29Helpers': previous['immutableHelperInputs'],
         'priorResidualUntrackedPreserveAndExclude': residuals,
         'scope': ['only NEW own Evidence and single own History', 'temporary source-data fixtures only under own .work'],
         'notRun': ['application/test import or execution', 'pytest/Go/compiler/crypto/Node/browser/SSH/Docker/build',
                    'Core/Backend CI', 'incident cleanup', 'old write-producing proof scripts'],
         'original19HOLD': True, 'acceptedBaselineDischarges': 0, 'runtimeB': 0, 'realBindings': None})


def main():
    global OUT
    sys.stdout.reconfigure(encoding='utf8')
    tag = sys.argv[1] if len(sys.argv) == 2 else 'probe01'
    assert tag and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in tag)
    OUT = E / tag
    OUT.mkdir(exist_ok=False)
    assert git('rev-parse', 'HEAD').decode().strip() == BASE
    assert git('diff', '--name-only') == b'' and git('diff', '--cached', '--name-only') == b''
    assert collector.SELECTOR == finite.p.PATTERN
    intake()
    committed, inventory = collector.collect(R, 'commit', BASE)
    commit_result = evaluate_discovered(committed)
    assert len(committed) == 25 and commit_result['reason'] is None
    emit('actual-commit-inventory.json', inventory)
    working, working_inventory = collector.collect(R, 'working')
    working_result = evaluate_discovered(working)
    assert working == committed and working_result['reason'] is None
    emit('actual-working-inventory.json', working_inventory)
    # Existing helper receives exactly the independently discovered target blobs.
    # Its historical baseline remains immutable and its refusal remains visible.
    legacy = finite.p.analyze({path: raw.decode('utf-8-sig') for path, raw in committed.items()})
    errors = [{'path': x['path'], 'error': x['error'], 'newReflection': x['reflection']['newRelevantHits']}
              for x in legacy['auditedScope'] if x['error'] or x['reflection']['newRelevantHits']]
    assert errors == [{'path': finite.DC, 'error': 'DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:INSTANCE:operation', 'newReflection': []}]
    assert legacy['guardCompatibilityClean'] is False
    emit('actual-target-results.json', {'commit': commit_result, 'working': working_result,
         'bothInventoriesIndependent': True, 'commitWorkingExactRawBytesEqual': True,
         'legacyStatus': 'REFUSED', 'legacyGuardCompatibilityClean': False, 'legacyRefusals': errors,
         'legacyHistoricalQueryBase': finite.BASE, 'legacyActualWorldInputCommit': BASE,
         'legacyParsedAuditedCount': [len(legacy['parsedScope']), len(legacy['auditedScope'])],
         'legacyConstructorCount': len(legacy['constructorInventory']), 'legacyOldAllowancesChanged': False,
         'productAndTestByteHashesUnchanged': finite.tested_bytes_match(committed),
         'oldHelpersUnchanged': finite.immutable_helpers_match(), 'runtimeB': 0, 'realBindings': None})
    work = R / '.work'
    work.mkdir(exist_ok=True)
    parent = Path(tempfile.mkdtemp(prefix='fleet5-selector-discovery-r1-', dir=work))
    extra_path = 'tools/fixture_second_deliver.py'
    second = b'def fixture_second(delivery, node, permit):\n    return delivery.deliver(node, permit, observation_only="foreign-tag")\n'
    variants = [
        ('fixture-exact-selected-source', (), {}, None),
        ('TREE-DISCOVERY-new-matching-module', (), {extra_path: second}, 'SOURCE_WORLD_PATH_SET_CHANGED'),
        ('TREE-DISCOVERY-missing-selected-module', (finite.p.WK,), {}, 'SOURCE_WORLD_PATH_SET_CHANGED'),
        ('TREE-DISCOVERY-nonmatching-module', (), {'tools/fixture_nonmatching.py': b'def fixture_value():\n    return 42\n'}, None),
        ('encoding-failure-not-dropped', (), {'tools/fixture_bad_encoding.py': b'# .deliver\n\xff'}, 'SOURCE_ENCODING_UNRESOLVED'),
        ('selected-parse-failure-not-dropped', (), {'tools/fixture_bad_parse.py': b'def broken(:\n    delivery.deliver()\n'}, 'SELECTED_SOURCE_PARSE_UNRESOLVED'),
    ]
    rows = []
    for name, omit, extra, expected in variants:
        target = fixture(parent, name, committed, omit=omit, extra=extra)
        try:
            world, report = collector.collect(target, 'filesystem-fixture')
            result = evaluate_discovered(world)
            reason = result['reason']
            deliver_refs = sum(isinstance(n, ast.Attribute) and n.attr == 'deliver'
                               for raw in world.values() for n in ast.walk(ast.parse(raw.decode('utf-8-sig'))))
            row = {'name': name, 'target': str(target), 'targetKind': 'filesystem-fixture', 'inventory': report,
                   'result': result, 'selectedDeliverReferenceCount': deliver_refs}
            if name == 'TREE-DISCOVERY-new-matching-module':
                assert extra_path in world and len(world) == 26 and deliver_refs == 2
                assert result['existingFinitePredicateRan'] is False
            if name == 'TREE-DISCOVERY-missing-selected-module':
                assert len(world) == 24 and result['missingPaths'] == [finite.p.WK]
            if name == 'TREE-DISCOVERY-nonmatching-module':
                assert report['enumeratedProductionPythonCount'] == 26 and len(world) == 25
        except collector.Unresolved as exc:
            reason = exc.reason
            row = {'name': name, 'target': str(target), 'targetKind': 'filesystem-fixture',
                   'unresolvedReason': exc.reason, 'detail': exc.detail, 'existingFinitePredicateRan': False}
        row.update({'reason': reason, 'expectedReason': expected, 'expectationMet': reason == expected,
                    'normalEnumerationReadEntrypoint': True, 'preselectedWorldInjectedInsteadOfDiscovery': False,
                    'fixtureIsRealGitCommitOrCheckout': False, 'fixtureMembershipNotClaimedTrackedOrUntracked': True,
                    'realProductWorktreeMutated': False, 'runtimeExecuted': False})
        rows.append(row)
        assert row['expectationMet'], row
    inherited_path = OLD / 'wip02-finite-control-results.json'
    inherited = next(x for x in json.loads(inherited_path.read_bytes())['rows'] if x['name'] == 'modified-unrelated-module')
    emit('tree-discovery-controls.json', {'rows': rows, 'count': len(rows), 'allExpected': True,
         'temporaryDataRoot': str(parent), 'noCleanupAttempted': True,
         'inheritedInjectedControl': {'path': inherited_path.relative_to(R).as_posix(),
             'publishedSHA256': sha(git('show', BASE + ':' + inherited_path.relative_to(R).as_posix())),
             'row': inherited, 'classification': 'INHERITED_CALLER_INJECTED_WORLD_CONTROL_NOT_TREE_DISCOVERY'},
         'genuineWorkingTreeMembership': 'actual-working-inventory.json, real Git index membership; filesystem fixtures have no tracked/untracked proof',
         'actualRuntimeB': 0, 'acceptedBaselineDischarges': 0, 'independentDeltaReview': 'PENDING'})
    print(json.dumps({'actualCommitSelected': len(committed), 'actualWorkingSelected': len(working),
                      'commitWorkingRawWorldEqual': True, 'controls': len(rows), 'allExpected': True,
                      'legacyStatus': 'REFUSED unchanged', 'applicationOrMutantRuntimeExecuted': False}))


if __name__ == '__main__':
    main()
