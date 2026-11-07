"""Diagnostic replay of the existing guard's first refusal, never an allowance."""
from collections import Counter
import json
import sys

import operation_proof as p


def main():
    sys.stdout.reconfigure(encoding='utf8')
    f = p.Facts(p.DC, (p.R / p.DC).read_bytes().decode('utf8'))
    with p.scope():
        allowed = p.u.baseline_sites(p.DC, True, (), ()).copy()
        first = None
        for node, tag in p.u.audited_nodes(f, True, (), {}, (), ()):
            if p.u.class_field_factory_allowed(f, node):
                continue
            key = p.u.key_for(f, node, tag)
            if allowed[key] <= 0:
                first = {'source': f.witness(node), 'nodeKind': type(node).__name__,
                         'contextKind': type(node.ctx).__name__ if hasattr(node, 'ctx') else None,
                         'tag': tag, 'expression': p.text(node),
                         'enclosingContext': p.text(p.u.context(f, node)), 'key': repr(key),
                         'remainingFrozenMultiplicity': allowed[key]}
                break
            allowed[key] -= 1
        _, actual = p.u.module_uses(f.source, p.DC, instances=True, factories=(), parameter_context={})
        owners, _ = p.ot.derive(f, (), {})
    assert first['tag'] == 'INSTANCE:operation'
    assert actual == 'DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:INSTANCE:operation'
    result = {'firstRefusedSite': first, 'actualExistingGuardReason': actual,
              'ownerDerivation': owners, 'guardFile': (p.OLD / 'use_sites.py').relative_to(p.R).as_posix(),
              'guardFileSHA256': p.sha((p.OLD / 'use_sites.py').read_bytes().decode('utf8')),
              'guardBaseline': p.HELPER_BASELINE, 'firstPartyWorldBase': p.SOURCE,
              'guardWasChanged': False, 'allowanceWasAdded': False,
              'effect': 'Whole WIP candidate remains UNRESOLVED; this diagnostic confers no credit or discharge',
              'rootDecisionRequired': 'Root must specify a bounded proof compatibility contract for the exact capture/guard/forwarding pattern, or keep this WIP held; do not weaken the existing guard implicitly'}
    p.emit('existing-guard-refusal.json', result)
    print(json.dumps({'reason': actual, 'firstRefusedSite': first, 'productImported': False}))


if __name__ == '__main__':
    main()
