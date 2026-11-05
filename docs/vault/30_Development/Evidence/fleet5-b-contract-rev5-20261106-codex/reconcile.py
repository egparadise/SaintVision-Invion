"""Semantic source-writer -> typed procedure audit, independent of golden bytes."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from authority import build, invariants, OP, RUN, VER, SAFE, USER, BOOT
from source_analysis import BASE, dump

E = Path(__file__).resolve().parent
# Exact function/table contracts, NOT an allow-any fallback by table or directory.
RULES = {
 ('inv.build_execution.BuildExecutionService._mark_node_quarantined', 'inv.nodes'): ['b_raise_node_quarantine'],
 ('inv.node_transport.NodeDelivery._quarantine_gpu_node', 'inv.nodes'): ['b_raise_node_quarantine'],
 ('inv.containment.Containment.change', 'inv.nodes'): ['b_set_node_containment', 'b_clear_node_containment'],
 ('inv.containment.Containment.change', 'inv.tenant_controls'): ['b_set_tenant_containment', 'b_clear_tenant_containment'],
 ('inv.observation.NodeObservation.accept', 'inv.nodes'): ['b_commit_node_observation'],
 ('inv.observation.NodeObservation.mark_offline', 'inv.nodes'): ['b_commit_node_observation'],
 ('inv.node_channels.provision_channel', 'inv.node_channels'): ['b_provision_node_channel'],
 ('inv.node_channels.revoke_channel', 'inv.node_channels'): ['b_revoke_node_channel'],
 ('inv.build_execution.BuildExecutionService._commit_consequences', 'inv.evidence'): ['b_append_build_cleanup_evidence'],
 ('inv.results.ResultStore.complete', 'inv.evidence'): ['b_append_result_completion_evidence'],
 ('inv.runs.RunStore.complete', 'inv.evidence'): ['b_append_run_completion_evidence'],
 ('inv.shard_completion.ShardCompletion.once', 'inv.evidence'): ['b_append_shard_completion_evidence'],
 ('inv.storage_commit.StorageSampleStore.apply_sample', 'inv.evidence'): ['b_append_storage_sample_evidence'],
 ('saintvision.services.nodes.enroll_node', 'public.nodes'): ['b_bootstrap_plain_node'],
 ('saintvision.services.nodes.record_heartbeat', 'public.nodes'): ['b_public_node_heartbeat'],
 ('saintvision.services.nodes.mark_lost_nodes', 'public.nodes'): ['b_public_node_lost'],
 ('saintvision.services.storage.register_contribution', 'public.storage_contributions'): ['b_register_owner_contribution'],
 ('saintvision.services.storage.activate_contribution', 'public.storage_contributions'): ['b_activate_owner_contribution'],
 ('saintvision.services.storage.revoke_contribution', 'public.storage_contributions'): ['b_revoke_owner_contribution'],
 ('tools.lan_execution.execute', 'inv.tenant_controls'): ['b_set_tenant_containment', 'b_clear_tenant_containment'],
 ('SQL:services/control-plane/src/inv/migrations/0022_node_containment.sql:inv.seed_containment_control', 'inv.tenant_controls'): ['b_seed_new_tenant_control'],
}
OFFLINE = {
 ('tools.check_migration_upgrade.main', 'inv.control_epoch'): 'disposable migration proof database only',
 ('tools.check_migration_upgrade.main', 'inv.nodes'): 'disposable migration proof database only',
 ('tools.lan_pilot.provision_observation_node', 'inv.nodes'): 'protected initial plain observation identity provisioning',
 ('tools.lan_pilot.provision_observation_node', 'inv.tenant_controls'): 'protected initial plain tenant provisioning',
 ('tools.lan_pilot.init', 'inv.control_epoch'): 'one-time exact empty control-plane initialization',
 ('tools.remote_workspace_entry.initialize', 'inv.control_epoch'): 'disposable/local fixture control-plane initialization',
 ('tools.remote_workspace_entry.initialize', 'inv.nodes'): 'disposable/local fixture plain Node initialization',
 ('tools.run_s04_fe_matrix.run_acceptance', 'inv.nodes'): 'disposable acceptance fixture insert/delete only',
 ('SQL:services/control-plane/src/inv/migrations/0022_node_containment.sql:<migration>', 'inv.tenant_controls'): 'versioned offline migration backfill before any B traffic',
}


def identity(w):
    return (w['path'], w['function'], w['line'], w['column'], w['table'], w['verb'], tuple(w['columns']), w['expressionSHA256'])


def pool(w):
    if w['path'].startswith('src/'):
        return {'source': ['src/saintvision/api/deps.py:69', 'src/saintvision/db/session.py:59', 'src/saintvision/config.py:188'],
                'current': 'request app engine -> SQLAlchemy Session; INV_DATABASE_URL; actual login/DSN UNMEASURED and not read',
                'future': 'shared plain/B scoped API, bootstrap or owner pool per authenticated caller; no inherited app/legacy direct DML'}
    if w['path'].startswith('tools/'):
        return {'source': [w['path'] + ':' + str(w['line'])], 'current': 'explicit tool connection; no actual credentials inspected',
                'future': 'protected narrow online caller for lan_execution only; other named fixture/bootstrap operations exclusive offline prerequisites'}
    return {'source': ['services/control-plane/src/inv/db.py:180', 'services/control-plane/src/inv/db.py:183',
                       'services/control-plane/src/inv/app.py:1313', 'services/control-plane/src/inv/worker.py:118',
                       'services/control-plane/src/inv/observer_worker.py:54'],
            'current': 'Database.transaction psycopg connection; rejects super/bypass/table-owner; exact deployed session_user UNMEASURED',
            'future': 'shared plain/B sv_b_runtime or dedicated verifier/protected pool per mapping; BoundDatabase preserves caller outer transaction; NO legacy inv_kernel DML escape'}


def mapping(census, matrix):
    plans = {p['function']: p for p in census['functionPlans']}
    result = []
    for w in census['writers']:
        if w['table'] not in matrix['tables']:
            continue
        key = (w['function'], w['table'])
        r = {k: w[k] for k in ('source', 'path', 'function', 'line', 'column', 'expression', 'expressionSHA256', 'table', 'verb', 'columns', 'kind')}
        r['writerID'] = list(identity(w))
        r['callerPrincipalPool'] = pool(w)
        r['plainCompatibility'] = 'DB persisted profile/status selects fixed plain or B wrapper; all shared authority writes mediated, no request flag or legacy SET ROLE'
        if key in RULES:
            r['disposition'] = 'RETIRE_DIRECT_DML_REPLACE_NAMED_PROCEDURE'
            r['replacementProcedures'] = RULES[key]
            r['executePrincipals'] = sorted({role for proc in RULES[key] for role in matrix['procedures'][proc]['execute']})
            r['allowedTransitions'] = {proc: matrix['procedures'][proc]['transitionPredicate'] for proc in RULES[key]}
            r['atomicBoundary'] = {proc: matrix['procedures'][proc].get('transactionBoundary',
                'same outer source caller transaction with exact current guard/evidence/idempotency/related effects; no split approval or partial commit') for proc in RULES[key]}
        elif key in OFFLINE:
            r['disposition'] = 'NAMED_EXCLUSIVE_OFFLINE_OR_DISPOSABLE_FIXTURE'
            r['replacementProcedures'] = []
            r['executePrincipals'] = ['protected_nonpooled_initialization_or_fixture_owner']
            r['offlinePrerequisites'] = {'purpose': OFFLINE[key], 'concurrentBTraffic': False,
                'proof': 'exclusive maintenance/advisory lock in separately scoped namespace; B services stopped/fenced and absence of B current/cohort/claims proven; exact DB instance/empty-init CAS; no ongoing online DML permission; no identity merge',
                'failure': 'deny before mutation; existing deployment not initialized here'}
        else:
            r['disposition'] = 'UNMAPPED_WRITER_BLOCK'
            r['replacementProcedures'] = []
        r['lockPlanFunction'] = w['function'] if w['function'] in plans else None
        r['sourceSHA'] = BASE
        result.append(r)
    return result


def audit(census, matrix, mapped):
    errors = invariants(matrix)
    actual = Counter(identity(w) for w in census['writers'] if w['table'] in matrix['tables'])
    recorded = Counter(identity(w) for w in mapped)
    if actual != recorded:
        errors.append('SOURCE_WRITER_COVERAGE_MISMATCH')
    for w in mapped:
        if w['disposition'] == 'UNMAPPED_WRITER_BLOCK':
            errors.append('UNMAPPED_WRITER:' + w['function'])
        elif w['disposition'] == 'RETIRE_DIRECT_DML_REPLACE_NAMED_PROCEDURE':
            columns = set()
            for proc in w['replacementProcedures']:
                if proc not in matrix['procedures']:
                    errors.append('MISSING_REPLACEMENT:' + proc)
                    continue
                effect = matrix['procedures'][proc]['effects'].get(w['table'])
                if not effect or w['verb'] not in effect['verb']:
                    errors.append('WRITER_EFFECT_VERB:' + proc)
                if effect:
                    columns.update(effect['columns'])
            if not set(w['columns']) <= columns:
                errors.append('WRITER_COLUMN_UNCOVERED:' + w['function'])
        elif w['disposition'] == 'NAMED_EXCLUSIVE_OFFLINE_OR_DISPOSABLE_FIXTURE':
            if (w['function'], w['table']) not in OFFLINE or w['offlinePrerequisites']['concurrentBTraffic'] is not False:
                errors.append('UNAUTHORIZED_OFFLINE_ESCAPE')
        if not w['lockPlanFunction']:
            errors.append('MISSING_WRITER_PLAN:' + w['function'])
    return sorted(set(errors))


if __name__ == '__main__':
    census = json.loads((E / 'source-analysis.json').read_bytes())
    matrix = build()
    mapped = mapping(census, matrix)
    errors = audit(census, matrix, mapped)
    dump(E / 'writer-reconciliation.json', {'source': BASE, 'writers': mapped,
        'noCurrentSourceWriter': {t: 'LEGITIMATE_NONE_PROPOSED_CONTRACT_ONLY' for t in matrix['tables'] if not any(w['table'] == t for w in mapped)},
        'missingCurrentLifecycleWriters': {'public.nodes certificate update': 'no current writer beyond initial enrollment found; proposed b_bind_public_node_certificate only protected approved leaf CAS',
            'public.nodes retirement': 'no current writer found; NodePrincipal.lock_current already rejects retired; proposed terminal b_retire_public_node'},
        'errors': errors, 'actualPGGrants': False})
    print(json.dumps({'mappedWriters': len(mapped), 'errors': errors}))
    raise SystemExit(bool(errors))
