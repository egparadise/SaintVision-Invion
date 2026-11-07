"""Root-authorized exact AST-delta coverage; legacy refusal is never removed.

Only parse first-party source. No application/test import or mutant execution.
This is a finite compatibility proof, not a general use-site allowance/resolver.
"""
import ast
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess

import operation_proof as p

E, R, BASE, DC = p.E, p.R, p.SOURCE, p.DC
TEST = 'tests/core/test_delivery_operation_origin.py'
PRODUCT_HASH = '82f029614537eb5bab56934e4b6736fe3dd52ece54b9b9a3996815b131e41de4'
TEST_HASH = '3dacdb63f83ab1d8075ddcbe422d82daad20bd56f643adee0fc7ae97715925d2'
REFUSAL_HASH = '3f5e6214ca11c7b08f54412f3f351242651bc6b9b4477df0f9512859488c5759'
CAPTURE = 'operation = attempt.operation'
GUARD = 'if type(operation) is not str or operation not in ("execute", "observe", "cancel"):\n    raise ValueError("Unsupported delivery operation origin")'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def dump(n):
    return ast.dump(n, include_attributes=False)


@lru_cache(maxsize=1)
def base_world():
    argv = ['git', 'grep', '-l', '-E', p.PATTERN, BASE, '--', 'services/control-plane/src', 'src', 'tools']
    out = subprocess.check_output(argv, cwd=R).decode('utf8')
    paths = sorted({line.split(':', 1)[1] for line in out.splitlines() if line.endswith('.py')})
    assert len(paths) == 25
    return {path: subprocess.check_output(['git', 'show', BASE + ':' + path], cwd=R) for path in paths}


def current_world():
    return {path: (R / path).read_bytes() for path in base_world()}


def worker_once(tree):
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DeliveryWorker']
    if len(classes) != 1:
        return None
    functions = [n for n in classes[0].body if isinstance(n, ast.FunctionDef) and n.name == 'once']
    return functions[0] if len(functions) == 1 else None


def delivery_call(once):
    if once is None:
        return None
    calls = [n for n in ast.walk(once) if isinstance(n, ast.Call) and ast.unparse(n.func) == 'self.delivery.deliver']
    return calls[0] if len(calls) == 1 else None


@lru_cache(maxsize=1)
def expected_module():
    """Derive the sole allowed whole-module AST from real BASE, not WIP text."""
    tree = ast.parse(base_world()[DC], DC)
    once = worker_once(tree)
    old_call = delivery_call(once)
    tries = [n for n in once.body if isinstance(n, ast.Try)]
    assert len(tries) == 1 and len(tries[0].body) == 1
    assert isinstance(tries[0].body[0], ast.Expr) and tries[0].body[0].value is old_call
    assert [k.arg for k in old_call.keywords] == ['observation_only', 'cancel_only']
    assert [ast.unparse(k.value) for k in old_call.keywords] == ["attempt.operation == 'observe'", "attempt.operation == 'cancel'"]
    assert not any(isinstance(n, ast.Name) and n.id == 'operation' for n in ast.walk(once))
    tries[0].body[:0] = [ast.parse(CAPTURE).body[0], ast.parse(GUARD).body[0]]
    for kw, literal in zip(old_call.keywords, ('observe', 'cancel')):
        kw.value = ast.parse(f'operation == {literal!r}', mode='eval').body
    ast.fix_missing_locations(tree)
    return tree


def shadowed_builtins(tree):
    names = {'type', 'str', 'ValueError'}
    result = []
    for n in ast.walk(tree):
        found = None
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            found = n.id
        elif isinstance(n, (ast.arg, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found = n.arg if isinstance(n, ast.arg) else n.name
        elif isinstance(n, ast.alias):
            found = n.asname or n.name.split('.')[0]
        elif isinstance(n, ast.ExceptHandler):
            found = n.name
        elif isinstance(n, (ast.MatchAs, ast.MatchStar)):
            found = n.name
        elif isinstance(n, ast.MatchMapping):
            found = n.rest
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            if names.intersection(n.names):
                result.extend(sorted(names.intersection(n.names)))
        if found in names:
            result.append(found)
    return result


def grammar(tree):
    """Closed capture-local grammar, evaluated independently of old guards."""
    once = worker_once(tree)
    if once is None:
        return 'CAPTURE_GUARD_GRAMMAR_CHANGED'
    shadows = shadowed_builtins(tree)
    if shadows:
        return 'BUILTIN_BINDING_CHANGED'
    refs = [n for n in ast.walk(once) if isinstance(n, ast.Name) and n.id == 'operation']
    kinds = Counter(type(n.ctx).__name__ for n in refs)
    if kinds['Store'] > 1 or kinds['Load'] > 4 or any(k not in ('Store', 'Load') for k in kinds):
        return 'CAPTURED_LOCAL_REFERENCE_SET_CHANGED'
    attributes = [n for n in ast.walk(once) if isinstance(n, ast.Attribute) and n.attr == 'operation']
    if len(attributes) > 1:
        return 'CAPTURED_OPERATION_ACCESS_SET_CHANGED'
    tries = [n for n in once.body if isinstance(n, ast.Try)]
    if len(tries) != 1 or len(tries[0].body) != 3:
        return 'CAPTURE_GUARD_GRAMMAR_CHANGED'
    capture, guard, forward = tries[0].body
    if dump(capture) != dump(ast.parse(CAPTURE).body[0]) or capture.value is not attributes[0]:
        return 'CAPTURE_GUARD_GRAMMAR_CHANGED'
    if dump(guard) != dump(ast.parse(GUARD).body[0]):
        return 'CAPTURE_GUARD_GRAMMAR_CHANGED'
    if kinds != {'Store': 1, 'Load': 4}:
        return 'CAPTURED_LOCAL_REFERENCE_SET_CHANGED'
    call = delivery_call(once)
    if not isinstance(forward, ast.Expr) or forward.value is not call:
        return 'CAPTURE_GUARD_GRAMMAR_CHANGED'
    wanted = [('observation_only', "operation == 'observe'"), ('cancel_only', "operation == 'cancel'")]
    if [(k.arg, ast.unparse(k.value)) for k in call.keywords] != wanted:
        return 'CAPTURE_FORWARDING_GRAMMAR_CHANGED'
    return None


def reference_contract(facts):
    """Same actual AST Call.func Attribute; full current witnesses of each kind."""
    once = facts[DC].functions.get('DeliveryWorker.once')
    forward = delivery_call(once)
    refs = []
    for path, f in facts.items():
        for node in ast.walk(f.tree):
            if not isinstance(node, ast.Attribute) or node.attr != 'deliver':
                continue
            parent = f.parent.get(id(node))
            direct = isinstance(parent, ast.Call) and parent.func is node
            refs.append({'attributeSource': f.witness(node), 'attributeKind': type(node).__name__,
                         'directCallFunc': direct, 'callKind': type(parent).__name__,
                         'callSource': f.witness(parent) if direct else None})
    f = facts[DC]
    expected_attr = f.witness(forward.func) if forward is not None else None
    expected_call = f.witness(forward) if forward is not None else None
    valid = len(refs) == 1 and forward is not None and isinstance(forward.func, ast.Attribute)
    if valid:
        ref = refs[0]
        valid = (ref['attributeKind'] == 'Attribute' and ref['callKind'] == 'Call' and ref['directCallFunc'] is True
                 and f.parent.get(id(forward.func)) is forward and forward.func is f.parent[id(forward.func)].func
                 and ref['attributeSource'] == expected_attr and ref['callSource'] == expected_call)
    return {'reason': None if valid else 'DELIVER_REFERENCE_SET_CHANGED', 'references': refs,
            'projectedForwardAttribute': expected_attr, 'forwardCallWitness': expected_call,
            'sameKindWitnessComparison': True, 'directNodeIdentityRequired': True}


def owners(world):
    with p.scope():
        return {path: p.ot.derive(p.Facts(path, b.decode('utf-8-sig')), (), {})[0]
                for path, b in world.items()}


@lru_cache(maxsize=1)
def expected_owners():
    expected = {**base_world(), DC: ast.unparse(expected_module()).encode()}
    return owners(expected)


def owner_contract(actual, expected):
    return None if actual == expected else 'OWNER_DERIVATION_CHANGED'


def evaluate(world):
    """Finite source/AST predicate. Runtime receipt matching is a separate gate."""
    base = base_world()
    path_equal = set(world) == set(base)
    if not path_equal:
        return {'reason': 'SOURCE_WORLD_PATH_SET_CHANGED', 'sourcePathSetEqual': False,
                'extraPaths': sorted(set(world) - set(base)), 'missingPaths': sorted(set(base) - set(world))}
    try:
        facts = {path: p.Facts(path, b.decode('utf-8-sig')) for path, b in world.items()}
    except (SyntaxError, UnicodeDecodeError):
        return {'reason': 'SOURCE_PARSE_UNRESOLVED', 'sourcePathSetEqual': True}
    reference = reference_contract(facts)
    grammar_reason = grammar(facts[DC].tree)
    module_equal = dump(facts[DC].tree) == dump(expected_module())
    changed_other = [path for path in base if path != DC and world[path] != base[path]]
    actual_owners = owners(world)
    owner_reason = owner_contract(actual_owners, expected_owners())
    # No legacy error is subtracted here. Every gate is independently recorded.
    reason = (reference['reason'] or grammar_reason or
              ('WHOLE_MODULE_DELTA_CHANGED' if not module_equal else None) or
              ('SOURCE_WORLD_BYTES_CHANGED' if changed_other else None) or owner_reason)
    return {'reason': reason, 'sourcePathSetEqual': True, 'scopedSourceCount': len(world),
            'referenceContract': reference, 'closedGrammarReason': grammar_reason,
            'wholeModuleNormalizedASTEqualsDerivedBASEPlusExactDelta': module_equal,
            'other24RawBytesEqualRealBASE': not changed_other, 'changedOtherPaths': changed_other,
            'ownerDerivationReason': owner_reason, 'ownerDerivation': actual_owners,
            'expectedOwnerDerivationSHA256': sha(json.dumps(expected_owners(), sort_keys=True).encode()),
            'capturedLocalReferenceKinds': {'Store': 1, 'Load': 4} if grammar_reason is None else None}


def tested_bytes_match(world):
    return (sha(world[DC]) == PRODUCT_HASH and sha((R / TEST).read_bytes()) == TEST_HASH)


def immutable_helpers_match():
    rows = json.loads((E / 'inputs.json').read_bytes())['immutableHelperInputs']
    return all(sha((R / row['path']).read_bytes()) == row['sha256'] for row in rows)
