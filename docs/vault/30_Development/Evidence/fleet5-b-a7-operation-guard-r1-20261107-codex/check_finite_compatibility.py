"""One bounded static/mutation pass for the exact Root-authorized delta."""
import ast
import copy
import hashlib
import json
import subprocess
import sys

import finite_compatibility as c


def emit(name, value):
    c.p.emit(name, value)


def summary(result):
    return {k: v for k, v in result.items() if k != 'ownerDerivation'}


def main():
    sys.stdout.reconfigure(encoding='utf8')
    world = c.current_world()
    assert c.tested_bytes_match(world)
    assert c.immutable_helpers_match()
    assert c.sha((c.E / 'existing-guard-refusal.json').read_bytes()) == c.REFUSAL_HASH
    original_zip = c.E / 'fleet5-a7-operation-guard-r1-wip01.zip'
    assert c.sha(original_zip.read_bytes()) == '28c87c268baaf551dde15fcb35f0eb6d3b24b6861e8c1cfcb845fcb6e0a96f37'
    actual = c.evaluate(world)
    assert actual['reason'] is None, summary(actual)
    assert actual['referenceContract']['sameKindWitnessComparison']
    assert actual['referenceContract']['directNodeIdentityRequired']
    assert actual['other24RawBytesEqualRealBASE']
    # Actually run the unchanged legacy helper on the unchanged current source.
    legacy = c.p.analyze()
    errors = [{'path': row['path'], 'error': row['error'], 'reflection': row['reflection']['newRelevantHits']}
              for row in legacy['auditedScope'] if row['error'] or row['reflection']['newRelevantHits']]
    assert errors == [{'path': c.DC, 'error': 'DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:INSTANCE:operation', 'reflection': []}]
    assert legacy['guardCompatibilityClean'] is False
    assert len(legacy['parsedScope']) == len(legacy['auditedScope']) == 25
    assert legacy['modeRule']['reason'] is None and legacy['referenceContract']['reason'] is None
    assert legacy['constructorArgumentBindingsValid']
    emit('wip02-legacy-run.json', legacy)
    # Every static control passes through the new layer. No old guard failure,
    # tested-byte mismatch, or runtime result is credited as its causal reason.
    current = world[c.DC].decode('utf8')
    variants = [('exact-accepted-delta', {}, None)]

    def change(name, old, new, reason):
        assert current.count(old) == 1, (name, old)
        text = current.replace(old, new, 1)
        ast.parse(text)
        variants.append((name, {c.DC: text.encode()}, reason))

    guard = 'type(operation) is not str or operation not in ("execute", "observe", "cancel")'
    change('missing-type-gate', guard, 'operation not in ("execute", "observe", "cancel")', 'CAPTURE_GUARD_GRAMMAR_CHANGED')
    change('wrong-boolean-connective', guard, guard.replace(' or ', ' and '), 'CAPTURE_GUARD_GRAMMAR_CHANGED')
    change('widened-admitted-type', guard, 'type(operation) not in (str, bytes) or operation not in ("execute", "observe", "cancel")', 'CAPTURE_GUARD_GRAMMAR_CHANGED')
    change('widened-domain', '("execute", "observe", "cancel")', '("execute", "observe", "cancel", "foreign")', 'CAPTURE_GUARD_GRAMMAR_CHANGED')
    change('extra-captured-local-reference', '            self.delivery.deliver(\n', '            _unexpected(operation)\n            self.delivery.deliver(\n', 'CAPTURED_LOCAL_REFERENCE_SET_CHANGED')
    change('extra-captured-local-store', '            self.delivery.deliver(\n', '            operation = "execute"\n            self.delivery.deliver(\n', 'CAPTURED_LOCAL_REFERENCE_SET_CHANGED')
    change('extra-captured-local-pass-through', '                cancel_only=(operation == "cancel"),\n', '                cancel_only=(operation == "cancel"),\n                extra=operation,\n', 'CAPTURED_LOCAL_REFERENCE_SET_CHANGED')
    change('extra-captured-local-alias', '            self.delivery.deliver(\n', '            copied = operation\n            self.delivery.deliver(\n', 'CAPTURED_LOCAL_REFERENCE_SET_CHANGED')
    change('extra-captured-local-closure', '            self.delivery.deliver(\n', '            captured = lambda: operation\n            self.delivery.deliver(\n', 'CAPTURED_LOCAL_REFERENCE_SET_CHANGED')
    change('extra-property-access', '            self.delivery.deliver(\n', '            extra = attempt.operation\n            self.delivery.deliver(\n', 'CAPTURED_OPERATION_ACCESS_SET_CHANGED')
    change('wrong-forwarded-literal', 'observation_only=(operation == "observe")', 'observation_only=(operation == "execute")', 'CAPTURE_FORWARDING_GRAMMAR_CHANGED')
    variants.append(('shadowed-type', {c.DC: b'type = None\n' + world[c.DC]}, 'BUILTIN_BINDING_CHANGED'))
    variants.append(('shadowed-str', {c.DC: b'str = None\n' + world[c.DC]}, 'BUILTIN_BINDING_CHANGED'))
    variants.append(('shadowed-ValueError', {c.DC: b'ValueError = None\n' + world[c.DC]}, 'BUILTIN_BINDING_CHANGED'))
    lp = 'tools/lan_pilot.py'
    second = world[lp] + b'\n\ndef _reviewer_second_deliver(delivery, node, permit):\n    return delivery.deliver(node, permit, observation_only="foreign-tag")\n'
    assert c.sha(second) == 'abb17b22020e6c93820ac9543e1a54a9813d746dcd8dd4851b9543fd0ef93a5e'
    variants.append(('reviewer-valid-second-deliver-reference', {lp: second}, 'DELIVER_REFERENCE_SET_CHANGED'))
    variants.append(('noncall-deliver-reference', {lp: world[lp] + b'\n\ndef _finite_reference(delivery):\n    return delivery.deliver\n'}, 'DELIVER_REFERENCE_SET_CHANGED'))
    wrong_function = ast.parse(current)
    queue = next(n for n in wrong_function.body if isinstance(n, ast.ClassDef) and n.name == 'DeliveryQueue')
    finish = next(n for n in queue.body if isinstance(n, ast.FunctionDef) and n.name == 'finish')
    finish.body.insert(0, ast.Expr(value=ast.Constant(value='unexpected other-function statement')))
    ast.fix_missing_locations(wrong_function)
    variants.append(('modified-otherfunction', {c.DC: ast.unparse(wrong_function).encode()}, 'WHOLE_MODULE_DELTA_CHANGED'))
    wk = c.p.WK
    variants.append(('modified-wrong-file', {wk: world[wk] + b'\n# unexpected wrong-file source delta\n'}, 'SOURCE_WORLD_BYTES_CHANGED'))
    outside = 'services/control-plane/src/inv/containment.py'
    unrelated_base = subprocess.check_output(['git', 'show', c.BASE + ':' + outside], cwd=c.R)
    variants.append(('modified-unrelated-module', {outside: unrelated_base + b'\n# unexpected unrelated-module delta\n'}, 'SOURCE_WORLD_PATH_SET_CHANGED'))
    rows = []
    for name, changes, expected in variants:
        for path, source in changes.items():
            ast.parse(source, path)
        result = c.evaluate({**world, **changes})
        row = {'name': name, 'expectedReason': expected, 'reason': result['reason'],
               'layer': 'NEW_FINITE_COMPATIBILITY_ONLY', 'result': summary(result),
               'changedInputs': [{'path': path, 'sha256': c.sha(source)} for path, source in changes.items()],
               'otherActualInputsUnchanged': True, 'syntaxValid': True,
               'legacyGuardCredited': False, 'runtimeOrTestedHashGateCredited': False,
               'expectationMet': result['reason'] == expected}
        assert row['expectationMet'], row
        # Explicit precursor checks for each claimed cause, independent of old guard.
        if expected in ('WHOLE_MODULE_DELTA_CHANGED', 'SOURCE_WORLD_BYTES_CHANGED'):
            assert result['referenceContract']['reason'] is None and result['closedGrammarReason'] is None
        if expected == 'SOURCE_WORLD_BYTES_CHANGED':
            assert result['wholeModuleNormalizedASTEqualsDerivedBASEPlusExactDelta']
        if expected == 'DELIVER_REFERENCE_SET_CHANGED':
            assert result['closedGrammarReason'] is None
            assert result['wholeModuleNormalizedASTEqualsDerivedBASEPlusExactDelta']
        rows.append(row)
    # An extra owner relevance fact is never silently dropped from comparison.
    changed_owners = copy.deepcopy(actual['ownerDerivation'])
    changed_owners[c.DC]['owners']['DeliveryWorker.once'].append('unexpected_owner')
    owner_reason = c.owner_contract(changed_owners, c.expected_owners())
    assert owner_reason == 'OWNER_DERIVATION_CHANGED'
    rows.append({'name': 'unexpected-owner-derivation-data', 'layer': 'EXACT_OWNER_DERIVATION_COMPARISON',
                 'reason': owner_reason, 'expectedReason': owner_reason, 'expectationMet': True,
                 'kind': 'diagnostic data mutation; not a product source execution', 'legacyGuardCredited': False})
    input_manifest = [{'path': path, 'sha256': c.sha(b), 'baseSHA256': c.sha(c.base_world()[path]),
                       'bytes': len(b), 'input': 'unchanged tested WIP dispatch' if path == c.DC else 'raw real BASE Git bytes'}
                      for path, b in sorted(world.items())]
    observed = json.loads((c.E / 'root-verified-unit-observation.json').read_bytes())
    assert observed['greenProductSHA256'] == c.PRODUCT_HASH and observed['testSHA256'] == c.TEST_HASH
    assert observed['green']['passed'] == 24 and observed['green']['directExit'] == 0
    assert observed['red']['failures'] == 1 and observed['red']['directExit'] == 1
    tracked = [x for x in subprocess.check_output(['git', 'diff', '--name-only', '-z', c.BASE], cwd=c.R).decode('utf8').split('\0') if x]
    untracked = [x for x in subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z', '--', 'services/control-plane/src', 'src', 'tools'], cwd=c.R).decode('utf8').split('\0') if x]
    assert tracked == [c.DC] and untracked == []
    syntax = []
    for path in [c.R / c.DC, c.R / c.TEST, *sorted(c.E.glob('*.py'))]:
        ast.parse(path.read_bytes(), str(path))
        syntax.append({'path': path.relative_to(c.R).as_posix(), 'sha256': c.sha(path.read_bytes())})
    emit('wip02-finite-control-results.json', {'rows': rows, 'count': len(rows), 'allExpected': True,
                                             'productOrMutantsExecuted': False, 'legacyHelpersModified': False,
                                             'acceptedBaselineDischarges': 0})
    emit('wip02-finite-proof.json', {
        'classification': 'EXACT_CAPTURE_GUARD_DELTA_COVERED_WITH_LEGACY_REFUSAL_PRESERVED',
        'rootDecision': 'msg_f730b53fb339', 'base': c.BASE, 'sourceWorld': input_manifest,
        'finiteResult': actual, 'legacyStatus': 'REFUSED', 'legacyGuardCompatibilityClean': False,
        'legacyRefusals': errors, 'legacyRefusalDiagnosticSHA256': c.REFUSAL_HASH,
        'oldGuardAllowanceAdded': False, 'oldBaselineOrProofsChanged': False,
        'expectedWholeModuleASTSHA256': c.sha(c.dump(c.expected_module()).encode()),
        'actualWholeModuleASTSHA256': c.sha(c.dump(ast.parse(world[c.DC])).encode()),
        'testedProductAndTestRawHashesMatchRoot': True, 'RootUnitObservationAttribution': observed,
        'actualProductExecutedByThisAuthor': False, 'newStaticControls': len(rows),
        'gitTrackedDeltaPaths': tracked, 'unexpectedUntrackedProductionPaths': untracked,
        'syntaxOnly': syntax, 'acceptedBaselineDischarges': 0, 'baseline19': 'HOLD unchanged',
        'runtimeB': 0, 'realBindings': None, 'independentCODEReview': 'PENDING through Root',
        'premises': ['genuine builtin type/str/ValueError and genuine receiver/plain-field hypotheses remain explicit',
                     'no hostile receiver/property/frame/metaclass exemption or heap completeness is granted',
                     'property read itself and earlier reconciliation/acquire effects have happened before value rejection',
                     'existing finish uncertainty and distinct SQL operation read are unchanged; no SQL/runtime proof here',
                     'NodeDelivery defaults/truthiness/or and delivery permission are unchanged and unaccepted'],
        'publication': 'NOT_RUN; Root next step required',
    })
    print(json.dumps({'classification': 'EXACT_CAPTURE_GUARD_DELTA_COVERED_WITH_LEGACY_REFUSAL_PRESERVED',
                      'legacyStatus': 'REFUSED', 'controls': len(rows), 'allExpected': True,
                      'scopedFiles': len(world), 'actualAuthorProductExecution': False,
                      'RootUnitGreenPassed': 24, 'RootCausalRedFailed': 1, 'baselineDischarges': 0}))


if __name__ == '__main__':
    main()
