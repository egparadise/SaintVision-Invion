"""Finite static checks only; never import/execute the product or unit module."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import operation_proof as proof

E, R = proof.E, proof.R
TEST = 'tests/core/test_delivery_operation_origin.py'
LP = 'tools/lan_pilot.py'


def guard_errors(result):
    return [{'path': x['path'], 'error': x['error'], 'newReflection': x['reflection']['newRelevantHits']}
            for x in result['auditedScope'] if x['error'] or x['reflection']['newRelevantHits']]


def direct(world):
    facts = {p: proof.Facts(p, proof.source(p, world)) for p in (proof.DC, proof.NT, proof.WK, proof.REMOTE)}
    with proof.scope():
        return proof.rule(facts)


def main():
    sys.stdout.reconfigure(encoding='utf8')
    syntax = []
    for path in [R / proof.DC, R / TEST, *sorted(E.glob('*.py'))]:
        b = path.read_bytes()
        ast.parse(b, str(path))
        syntax.append({'path': path.relative_to(R).as_posix(), 'sha256': hashlib.sha256(b).hexdigest(),
                       'bytes': len(b), 'ASTParse': True, 'executed': False})
    original = proof.frozen_source(proof.DC)
    current = (R / proof.DC).read_bytes().decode('utf8')
    before, after = proof.Facts(proof.DC, original), proof.Facts(proof.DC, current)
    oldonce, newonce = before.functions['DeliveryWorker.once'], after.functions['DeliveryWorker.once']
    # Reverse exactly the granted edit, then compare the whole module AST.
    inverse = ast.parse(current)
    invfacts = proof.Facts(proof.DC, current)
    invonce = invfacts.functions['DeliveryWorker.once']
    invtry = next(x for x in invonce.body if isinstance(x, ast.Try))
    assert len(invtry.body) == 3
    invtry.body = invtry.body[2:]
    call = invtry.body[0].value
    for kw in call.keywords:
        literal = {'observation_only': 'observe', 'cancel_only': 'cancel'}[kw.arg]
        kw.value = ast.parse(f'attempt.operation == {literal!r}', mode='eval').body
    assert proof.shape(invfacts.tree) == proof.shape(before.tree), 'Product change exceeds exact once guard contract'
    assert proof.shape(before.functions['DeliveryQueue.finish']) == proof.shape(after.functions['DeliveryQueue.finish'])
    prod_diff = subprocess.check_output(['git', 'diff', proof.SOURCE, '--', proof.DC], cwd=R)
    newtest = (R / TEST).read_bytes()
    test_diff = ''.join(difflib.unified_diff([], newtest.decode('utf8').splitlines(keepends=True),
                                          fromfile='/dev/null', tofile='b/' + TEST)).encode()
    (E / 'complete-product-test.diff.txt').write_bytes(prod_diff + test_diff)
    proof.main()
    base = json.loads((E / 'operation-origin-graph.json').read_bytes())
    assert len(base['parsedScope']) == len(base['auditedScope']) == 25
    assert len(base['constructorInventory']) == 9
    assert base['referenceContract']['reason'] is None
    assert base['modeRule']['reason'] is None
    assert base['constructorArgumentBindingsValid']
    emit = proof.emit
    rows, control_inputs = [], {}
    wip = {proof.DC: current}
    variants = [
        ('actual-WIP', {}, 'CONDITIONAL_CAPTURED_MODE_ORIGIN_CANDIDATE', None),
        ('benign-leading-comment', {proof.DC: '# own benign span shift\n' + current}, 'CONDITIONAL_CAPTURED_MODE_ORIGIN_CANDIDATE', None),
        ('capture-removed', {proof.DC: current.replace('            operation = attempt.operation\n', '', 1)}, 'UNRESOLVED', 'OPERATION_CAPTURE_GUARD_CHANGED'),
        ('guard-domain-expanded', {proof.DC: current.replace('("execute", "observe", "cancel")', '("execute", "observe", "cancel", "foreign")', 1)}, 'UNRESOLVED', 'OPERATION_CAPTURE_GUARD_CHANGED'),
        ('forwarding-changed', {proof.DC: current.replace('observation_only=(operation == "observe")', 'observation_only=False', 1)}, 'UNRESOLVED', 'MODE_FORWARDING_CHANGED'),
        ('second-operation-store', {proof.DC: current.replace('            self.delivery.deliver(\n', '            operation = "execute"\n            self.delivery.deliver(\n', 1)}, 'UNRESOLVED', 'OPERATION_CAPTURE_GUARD_CHANGED'),
    ]
    for name, changes, status, reason in variants:
        world = {**wip, **changes}
        for path, text in changes.items():
            assert text != proof.source(path, wip)
            ast.parse(text, path)
        result = direct(world)
        row = {'name': name, 'layer': 'DIRECT_CAPTURE_FORWARD_RULE', 'status': result['status'],
               'reason': result['reason'], 'expectedStatus': status, 'expectedReason': reason,
               'inputSHA256': {p: proof.sha(s) for p, s in world.items()},
               'earlierGuardCredit': False, 'expectationMet': (result['status'], result['reason']) == (status, reason)}
        rows.append(row)
        control_inputs[name] = changes
        assert row['expectationMet'], row
    # Exact review fixture, including the same appended bytes and resulting hash.
    second = proof.frozen_source(LP) + '\n\ndef _reviewer_second_deliver(delivery, node, permit):\n    return delivery.deliver(node, permit, observation_only="foreign-tag")\n'
    assert proof.sha(second) == 'abb17b22020e6c93820ac9543e1a54a9813d746dcd8dd4851b9543fd0ef93a5e'
    reference_variants = [
        ('reviewer-valid-second-caller', second),
        ('noncall-reference', proof.frozen_source(LP) + '\n\ndef _own_reference(delivery):\n    return delivery.deliver\n'),
        ('second-unconstrained-caller', proof.frozen_source(LP) + '\n\ndef _own_caller(delivery, node, permit):\n    return delivery.deliver(node, permit)\n'),
    ]
    for name, text in reference_variants:
        ast.parse(text, LP)
        result = proof.analyze({LP: text})
        decision = proof.verdict(result)
        # The dedicated C1 predicate must be causal; all earlier conditions are
        # compared to the actual WIP and the mutated caller's own guard is clean.
        caller_guard = next(x for x in result['auditedScope'] if x['path'] == LP)
        unchanged_guards = guard_errors(result) == guard_errors(base)
        row = {'name': name, 'layer': 'WHOLE_SCOPED_DELIVER_REFERENCE_SET', **decision,
               'modeRuleStatus': result['modeRule']['status'], 'modeRuleReason': result['modeRule']['reason'],
               'constructorBindingsValid': result['constructorArgumentBindingsValid'],
               'parsed': len(result['parsedScope']), 'constructors': len(result['constructorInventory']),
               'referenceCount': len(result['deliverReferences']), 'referenceContract': result['referenceContract'],
               'mutatedCallerGuardClean': caller_guard['error'] is None and not caller_guard['reflection']['newRelevantHits'],
               'earlierGuardRefusalsSameAsWIP': unchanged_guards,
               'earlierGuardRefusals': guard_errors(result),
               'inputSHA256': {proof.DC: proof.sha(current), LP: proof.sha(text)},
               'earlierGuardCredit': False,
               'expectationMet': decision['reason'] == 'DELIVER_REFERENCE_SET_CHANGED' and result['modeRule']['reason'] is None and result['constructorArgumentBindingsValid'] and unchanged_guards and caller_guard['error'] is None and not caller_guard['reflection']['newRelevantHits']}
        rows.append(row)
        control_inputs[name] = {LP: text}
        assert row['expectationMet'], row
    # Recompute current witness segments and both node kinds for all graph refs.
    replay = []
    for row in base['deliverReferences']:
        f = proof.Facts(row['source']['path'], proof.source(row['source']['path'], wip))
        hits = [n for n in ast.walk(f.tree) if isinstance(n, ast.Attribute) and f.witness(n) == row['source']]
        assert len(hits) == 1
        parent = f.parent[id(hits[0])]
        assert isinstance(parent, ast.Call) and parent.func is hits[0]
        assert f.witness(parent) == row['parentCallSource']
        replay.append({'attribute': f.witness(hits[0]), 'call': f.witness(parent),
                       'attributeKind': type(hits[0]).__name__, 'parentKind': type(parent).__name__,
                       'directCallFuncIdentity': parent.func is hits[0]})
    emit('control-inputs.json', control_inputs)
    emit('control-results.json', {'rows': rows, 'count': len(rows), 'allExpected': True,
                                  'actualProductOrMutantsExecuted': False, 'acceptedDischarges': 0})
    emit('syntax-source-inspection.json', {'files': syntax, 'inverseExactPatchModuleASTEqualsBASE': True,
                                          'queueFinishASTUnchanged': True, 'currentWitnessReplay': replay,
                                          'base': proof.SOURCE, 'testModuleImportedOrExecuted': False,
                                          'actualProductTests': 'NOT_RUN', 'actualRuntimeB': 0})
    # Every current scope file is paired with the actual Git blob bytes; only
    # dispatch is overlaid. No product source stub is included or executed.
    world = []
    for row in base['parsedScope']:
        path = row['path']
        raw_base = subprocess.check_output(['git', 'show', proof.SOURCE + ':' + path], cwd=R)
        raw = (R / path).read_bytes() if path == proof.DC else raw_base
        assert hashlib.sha256(raw).hexdigest() == row['sha256']
        world.append({**row, 'baseGitBlobSHA256': hashlib.sha256(raw_base).hexdigest(),
                      'inputKind': 'CURRENT_WIP_DISPATCH' if path == proof.DC else 'REAL_BASE_GIT_BLOB'})
    emit('source-world.json', {'base': proof.SOURCE, 'files': world, 'count': len(world),
                               'currentDispatchSHA256': proof.sha(current),
                               'currentTestSHA256': hashlib.sha256(newtest).hexdigest(),
                               'productStubCount': 0, 'sourceOrTestExecuted': False})
    print(json.dumps({'syntax': len(syntax), 'controls': len(rows), 'allExpected': True,
                      'existingGuardRefusals': guard_errors(base), 'actualProductTests': 'NOT_RUN',
                      'sourceWorld': len(world), 'verdict': proof.verdict(base)}))


if __name__ == '__main__':
    main()
