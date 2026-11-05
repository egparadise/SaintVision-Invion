"""Proposed semantic authority policy; no SQL/GRANTs are executed."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

E = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('rev4_authority_immutable', E.parent / 'fleet5-b-contract-rev4-20261106-codex/authority.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
OP, VER, ISS, RUN, DEL, SAFE, BUD = prior.OP, prior.VER, prior.ISS, prior.RUN, prior.DEL, prior.SAFE, prior.BUD
BOOT, USER = 'sv_node_bootstrap', 'sv_storage_owner_api'
OWNER = prior.OWNER
DOMAINS = deepcopy(prior.DOMAINS)
DOMAINS.update({'GATE_OBSERVATION': ('saintvision/node-role-observe/v1', 'REGISTERED_NODE_LEAF', ['READ_DURABLE_GATE']),
                'LINEAGE_TOMBSTONE': ('saintvision/node-role-lineage-revoke/v1', 'OPERATOR_RELEASE', ['REVOKE_LINEAGE'])})


def build():
    d = deepcopy(prior.build())
    d['version'] = 'fleet5-b-authority-rev5:1'
    p = d['procedures']
    for name in ('b_commit_node_observation', 'b_change_node_containment',
                 'b_public_node_observation', 'b_public_contribution_change'):
        p.pop(name)
    # Evidence is typed append-only data, distinct from role/business admission.
    p['b_commit_business_nonce_evidence']['effects'].pop('inv.evidence')
    p['b_commit_business_nonce_evidence']['effects']['inv.node_role_request_commits']['columns'] = ['issuance_ref', 'request_hash', 'verified_outcome_ref']

    def add(name, roles, table, verb, columns, predicate, protected=False, **extra):
        p[name] = dict(owner=OWNER, execute=roles,
                       effects={table: dict(verb=verb, columns=columns)},
                       searchPath='pg_catalog', rowSecurity='on/FORCE where applicable',
                       arbitrarySqlOrTableParameter=False, protected=protected,
                       transitionPredicate=predicate, **extra)

    add('b_raise_node_quarantine', [RUN, VER, SAFE], 'inv.nodes', 'UPDATE', ['status'],
        'DENY_ONLY: owned tenant+Node+epoch+current operation and authenticated causal reconciliation obligation; raise quarantined from schedulable/offline or retain stronger denial; never clear draining/retired/quarantined, release claims, physical stop or success',
        denyOnly=True, mayReduceDenial=False, requiresDurableCausalEvidence=True,
        relatedAtomicEffects=['causal reconciliation/outbox obligation, no success assertion'])
    add('b_register_node_safety_obligation', [RUN, VER], 'inv.node_role_safety_obligations', 'INSERT',
        ['tenant_id', 'node_id', 'epoch', 'operation_id', 'causal_intent_hash', 'state'],
        'durable PRE_IO exact current owned operation obligation; state=PENDING_PROOF; inability to commit denies IO; every eligibility query checks unresolved obligation independently of nodes.status',
        denyOnly=True, mayReduceDenial=False)
    add('b_settle_node_safety_obligation', [OP], 'inv.node_role_safety_obligations', 'UPDATE',
        ['state', 'protected_clear_ref', 'physical_proof_hash'],
        'protected automated reconciliation service only: exact current operation + independent authenticated physical cleanup proof + protected clear/restore record; unknown/failed quarantine writes cannot settle from ordinary success path; no node.status clear',
        protected=True, mayReduceDenial=True)
    add('b_commit_node_observation', [VER], 'inv.nodes', 'UPDATE',
        ['heartbeat_at', 'probe_started_at', 'clock_skew_seconds', 'status'],
        'telemetry update; status only offline->online or online->offline when no containment/retirement; preserves quarantined/draining/retired',
        statusTransitions=[['offline', 'online'], ['online', 'offline']], mayReduceDenial=False)
    add('b_set_node_containment', [OP, SAFE], 'inv.nodes', 'UPDATE', ['status'],
        'DENY_ONLY typed quarantine/drain/retire with current operation and evidence; retirement terminal',
        protected=True, denyOnly=True, mayReduceDenial=False)
    add('b_clear_node_containment', [OP], 'inv.nodes', 'UPDATE', ['status'],
        'reviewed protected recovery only: current signed clear/restore grant + physical reconciliation + unchanged identity/epoch/shared C; never revive retired via ordinary clear',
        protected=True, mayReduceDenial=True)
    add('b_set_tenant_containment', [OP, SAFE], 'inv.tenant_controls', 'UPDATE', ['kill_switch', 'version', 'updated_at'],
        'DENY_ONLY false->true CAS version with causal evidence', protected=True, denyOnly=True, mayReduceDenial=False)
    add('b_clear_tenant_containment', [OP], 'inv.tenant_controls', 'UPDATE', ['kill_switch', 'version', 'updated_at'],
        'true->false protected restore grant + reconciled proof + version CAS', protected=True, mayReduceDenial=True)
    add('b_seed_new_tenant_control', [], 'inv.tenant_controls', 'INSERT', ['tenant_id'],
        'internal fixed-scope SECURITY DEFINER trigger replacement only for NEW tenant insertion; absence proven under bootstrap lock; defaults only, cannot reset existing control or create B identity; no service EXECUTE/PUBLIC membership',
        protected=True, internalTriggerOnly=True)
    add('b_provision_node_channel', [OP], 'inv.node_channels', 'INSERT_OR_UPDATE',
        ['tenant_id', 'node_id', 'recovery_epoch', 'version', 'endpoint', 'certificate_sha256', 'certificate_not_after', 'enabled'],
        'derive identity/fingerprint/expiry from approved DER; current control/Node epoch equal; exact expected C (0 only initial) -> C+1; separate initial provisioning vs existing B leaf rotation plan; retired/revoked requires reviewed recovery; audit in same transaction',
        protected=True, relatedAtomicEffects=['inv.node_channel_audit action provision same C and DER'])
    add('b_revoke_node_channel', [OP], 'inv.node_channels', 'UPDATE', ['enabled', 'version'],
        'exact tenant+Node+expected shared C; enabled=false,C+1,audit; cannot re-enable/reset/replace certificate, no separate storage C',
        protected=True, denyOnly=True, mayReduceDenial=False,
        relatedAtomicEffects=['inv.node_channel_audit action revoke same C and DER; affected B eligibility denied'])
    add('b_bootstrap_plain_node', [BOOT], 'public.nodes', 'INSERT',
        ['node_id', 'tenant_id', 'hostname', 'os_type', 'os_version', 'agent_version', 'status', 'certificate_fingerprint', 'labels', 'enrolled_at', 'heartbeat_sequence'],
        'authenticated one-use tenant-bound bootstrap consumption, same capability/offer/audit transaction; status enrolling or active; protected approved cert binding if present; cannot create a fresh B identity to bypass existing quarantined/partial cohort',
        oneUseBootstrap=True, dbTruthSelectsProfile=True,
        relatedAtomicEffects=['bootstrap consumed once; capabilities/offers/audit same enrollment transaction; token never reusable after committed consumption'])
    add('b_bind_public_node_certificate', [OP], 'public.nodes', 'UPDATE', ['certificate_fingerprint', 'version'],
        'protected approved enrollment/leaf CAS; exact same identity/tenant/epoch and shared node_channels C; no heartbeat change to certificate', protected=True)
    add('b_public_node_heartbeat', [RUN], 'public.nodes', 'UPDATE', ['heartbeat_sequence', 'last_heartbeat_at', 'status'],
        'atomic sequence strictly advances; lost->active only if no containment/retirement; other statuses unchanged',
        statusTransitions=[['lost', 'active']], mayReduceDenial=False)
    add('b_public_node_lost', [RUN, VER], 'public.nodes', 'UPDATE', ['status'],
        'active->lost only on stale heartbeat; preserve stronger denial and retirement; replica unavailability in same transaction',
        statusTransitions=[['active', 'lost']], mayReduceDenial=False)
    add('b_retire_public_node', [OP, SAFE], 'public.nodes', 'UPDATE', ['status', 'version'],
        'terminal retired; authenticated narrow request + evidence, retains identity and catalogue; no ordinary recovery',
        protected=True, denyOnly=True, mayReduceDenial=False)
    add('b_register_owner_contribution', [USER], 'public.storage_contributions', 'INSERT',
        ['contribution_id', 'tenant_id', 'node_id', 'declared_path', 'normalized_path', 'mode', 'status', 'capacity_bytes', 'available_bytes', 'registered_by_user_id', 'registered_at'],
        'authenticated tenant user registration on same tenant Node, OS-aware safe path and uniqueness; registered_by_user_id from authenticated principal, status pending; preserves plain mode catalogue semantics, never B admission',
        ownerConsent=True, grantsBAdmission=False)
    add('b_activate_owner_contribution', [USER], 'public.storage_contributions', 'UPDATE', ['status'],
        'row registered_by_user_id equals authenticated owner; pending->active or active idempotent, Node folder confirmation; revoked terminal; no project grade/operator impersonation substitute',
        ownerConsent=True, grantsBAdmission=False, statusTransitions=[['pending', 'active'], ['active', 'active']])
    add('b_revoke_owner_contribution', [USER], 'public.storage_contributions', 'UPDATE', ['status', 'revoked_at'],
        'same registered owner withdraws ->revoked terminal; retain folder+catalogue; affected B eligibility denied, no deletion/reactivation/policy regeneration/compute downgrade',
        ownerConsent=True, grantsBAdmission=False, denyOnly=True, mayReduceDenial=False)
    add('b_approve_readonly_contribution_root', [OP], 'inv.node_role_storage_bindings', 'INSERT',
        ['tenant_id', 'node_id', 'contribution_id', 'root_identity', 'policy_bytes_hash', 'r', 'approval_ref'],
        'ADDITIONAL protected B RO/root/R/policy approval with current ACTIVE owner consent; no consent substitute; no RW, arbitrary mount, writeback or workload host-path access', protected=True)
    for suffix, role, atomic in [
        ('build_cleanup', RUN, 'BuildExecutionService._commit_consequences: current intent/run/lease CAS, verified duplicate physical cleanup receipts, resource lease release, BuildCleanupReceipt validation and completion outbox together'),
        ('result_completion', RUN, 'ResultStore.complete: authenticated stop receipt, ready immutable prepared output, workspace checkpoint/pin, result_completions and RunStore transitions together'),
        ('run_completion', RUN, 'RunStore.complete: EvidenceEnvelope validation, trusted bytes hash/size, verifying exact version and current fencing proofs, succeeded transition together'),
        ('shard_completion', RUN, 'ShardCompletion.once: exact run/shard/attempt and authenticated receipt/nonce/dedup, shard sample/completion/run transitions together'),
        ('storage_sample', VER, 'StorageSampleStore.apply_sample: exact Node/channel/epoch/nonce/signed sample, storage claim/sample and evidence commit together')]:
        add('b_append_' + suffix + '_evidence', [role], 'inv.evidence', 'INSERT',
            ['tenant_id', 'run_id', 'evidence_id', 'envelope'],
            'typed ' + suffix + ' evidence append only; body schema and persisted scope/reference hashes verified, not arbitrary JSON; ' + atomic,
            appendOnlyData=True, grantsApproval=False, assertsSuccessByAppendAlone=False,
            transactionBoundary=atomic)
    add('b_revoke_approval_lineage', [OP, SAFE], 'inv.node_role_lineage_tombstones', 'INSERT',
        ['root_lineage_id', 'revoked_ancestor_hash', 'node_id', 'epoch', 'version', 'causal_evidence_hash'],
        'authenticated immutable ancestor chain; durable terminal tombstone; any descendant denied at every current CP commit gate; no ordinary renewal clears',
        protected=True, denyOnly=True, mayReduceDenial=False)
    # Earlier protected procedures are classified explicitly, never inferred from name.
    ordinary = {'b_append_candidate', 'b_record_gate_ack', 'b_refresh_same_generation',
                'b_prepare_key_delivery', 'b_append_key_possession', 'b_consume_key_challenge',
                'b_record_key_delivery', 'b_record_request_issuance',
                'b_commit_business_nonce_evidence', 'b_commit_reconcile_receipt', 'b_record_safety_request'}
    for name, proc in p.items():
        proc.setdefault('protected', name not in ordinary)
        proc.setdefault('transitionPredicate', 'exact typed current approved operation, tenant/Node/epoch/shared C and predecessor CAS; lineage checked at commit, never caller-selected plain/B flag')
    d['tables'] = {}
    for name, proc in p.items():
        for table, effect in proc['effects'].items():
            d['tables'].setdefault(table, []).append(dict(procedure=name, **effect))
    d['tables'].setdefault('inv.control_epoch', [])
    d['legitimateNoOnlineWriter'] = {'inv.control_epoch': 'one-time/offline exclusive bootstrap only; online epoch change is B-RECOVERY1 HOLD'}
    d['principals'][RUN] = 'plain AND B shared online pool; external plain behavior retained through fixed plain wrappers; no inherited legacy inv_kernel/app DML or SET ROLE'
    d['principals'][USER] = 'authenticated owner API pool; only owner registration/activation/withdrawal; actor derived from authenticated service binding, never request GUC/project grade'
    d['principals'][BOOT] = 'authenticated tenant-bound one-use bootstrap pool; no approval, containment clear or arbitrary identity creation'
    d['plainAndBSharedMediation'] = True
    d['profileSelection'] = 'persisted routing/current/cohort/status is authoritative; request profile/compatibility flags cannot choose a legacy bypass'
    d['ordinaryOnline'] = [RUN, VER, ISS, USER, BOOT]
    d['signaturePurposes'] = {k: dict(domain=a, signer=b, purposes=c) for k, (a, b, c) in DOMAINS.items()}
    d['signingService'] = {'rawOperatorPrivateKeyToController': False,
        'installedCallerPolicy': {OP: ['APPROVAL', 'RELEASE', 'DELEGATION', 'GATE_CONTROL', 'LINEAGE_TOMBSTONE'],
                                  DEL: ['DELIVERY_CHALLENGE', 'KEY_DELIVERY_RECEIPT'], BUD: ['CONTEXT_BUDGET']},
        'scopeValidation': 'authenticated installed caller binding -> exact purpose/domain/body scope; controller requires postcommit activation ledger, current ARM ACK, exact recipient/key/challenge/possession; reject BEFORE signing',
        'keyCustody': {'OPERATOR_RELEASE': 'existing protected signing service only', 'CONTEXT_BUDGET': 'separate protected budget key'},
        'actualCustody': None}
    return d


def invariants(d):
    errors = []
    procs = d.get('procedures', {})
    ordinary = {RUN,VER,ISS,USER,BOOT}
    if set(d.get('ordinaryOnline',[]))!=ordinary:
        errors.append('ordinary principal classification changed')
    protected_tables={'inv.node_role_approvals','inv.node_role_operations','inv.node_role_routing',
        'inv.node_role_cohorts','inv.node_role_member_cas','inv.node_role_releases',
        'inv.node_role_delegations','inv.node_role_admissions','inv.node_role_activation_ledger',
        'inv.node_role_service_bindings','inv.node_role_storage_bindings','inv.node_role_lineage_tombstones',
        'inv.node_channels'}
    required_protected={'b_append_approval','b_begin_node_switch','b_plan_fresh','b_fence_cohort',
        'b_member_cas','b_commit_node_activation','b_commit_fresh_cohort','b_update_service_bindings',
        'b_provision_node_channel','b_revoke_node_channel','b_bind_public_node_certificate',
        'b_clear_node_containment','b_clear_tenant_containment','b_revoke_approval_lineage',
        'b_approve_readonly_contribution_root'}
    for name, p in procs.items():
        if p.get('owner')!=OWNER or p.get('searchPath')!='pg_catalog':
            errors.append('unsafe procedure owner/search path:' + name)
        if name in required_protected and p.get('protected') is not True:
            errors.append('protected classification removed:' + name)
        if (p.get('protected') or name in required_protected) and ordinary.intersection(p.get('execute', [])):
            errors.append('ordinary principal protected EXECUTE:' + name)
        if p.get('arbitrarySqlOrTableParameter') is not False:
            errors.append('arbitrary scope:' + name)
        for table, effect in p.get('effects', {}).items():
            roles = set(p.get('execute', []))
            cols = effect.get('columns', [])
            if table in protected_tables and roles & ordinary:
                errors.append('ordinary protected-table writer:' + name)
            if table=='inv.node_role_current' and roles & ordinary and not (name=='b_refresh_same_generation' and roles=={VER} and set(cols)=={'lease_ref'}):
                errors.append('ordinary protected current pointer:' + name)
            if table == 'inv.evidence' and (effect['verb'] != 'INSERT' or not p.get('appendOnlyData') or p.get('grantsApproval') is not False or p.get('assertsSuccessByAppendAlone') is not False):
                errors.append('evidence authority factory:' + name)
            if table in ('inv.nodes', 'public.nodes') and 'status' in cols:
                if p.get('mayReduceDenial') and not roles <= {OP}:
                    errors.append('unprotected containment clear:' + name)
                if roles & ordinary and name not in {'b_raise_node_quarantine', 'b_commit_node_observation', 'b_public_node_heartbeat', 'b_public_node_lost', 'b_bootstrap_plain_node'}:
                    errors.append('ordinary status writer:' + name)
            if table == 'inv.tenant_controls' and not roles <= {OP, SAFE}:
                errors.append('unprotected tenant containment:' + name)
            if table == 'public.nodes' and 'certificate_fingerprint' in cols and name != 'b_bootstrap_plain_node' and not roles <= {OP}:
                errors.append('ordinary certificate writer:' + name)
            if table == 'public.storage_contributions' and (roles != {USER} or not p.get('ownerConsent') or p.get('grantsBAdmission') is not False):
                errors.append('owner storage authority:' + name)
    for table, writers in d.get('tables', {}).items():
        if not writers and table not in d.get('legitimateNoOnlineWriter', {}):
            errors.append('missing table writer:' + table)
        for w in writers:
            if w['procedure'] not in procs or table not in procs[w['procedure']]['effects']:
                errors.append('table/procedure disagreement:' + table)
    for name,p in procs.items():
        for table,effect in p['effects'].items():
            if not any(w.get('procedure')==name and w.get('verb')==effect['verb'] and set(w.get('columns',[]))==set(effect['columns']) for w in d.get('tables',{}).get(table,[])):
                errors.append('procedure absent from table writer index:' + name)
    if any(d.get('allOnlineDirectAuthorityDML', {}).values()):
        errors.append('online direct DML/SET ROLE')
    q = procs.get('b_raise_node_quarantine', {})
    if not q.get('denyOnly') or q.get('mayReduceDenial') is not False or not q.get('requiresDurableCausalEvidence'):
        errors.append('quarantine not DENY-only')
    for name, allowed in [('b_commit_node_observation', [['offline', 'online'], ['online', 'offline']]),
                           ('b_public_node_heartbeat', [['lost', 'active']]), ('b_public_node_lost', [['active', 'lost']])]:
        if procs.get(name, {}).get('statusTransitions') != allowed:
            errors.append('unsafe liveness transition:' + name)
    for name, p in d.get('lockOnlyProcedures', {}).items():
        if p.get('columnsWritten'):
            errors.append('read/lock procedure writes:' + name)
    sign = d.get('signingService', {})
    if sign.get('rawOperatorPrivateKeyToController') is not False or sign.get('installedCallerPolicy', {}).get(DEL) != ['DELIVERY_CHALLENGE', 'KEY_DELIVERY_RECEIPT']:
        errors.append('unrestricted controller signer')
    return errors


if __name__ == '__main__':
    d = build()
    assert not invariants(d), invariants(d)
    (E / 'authority-matrix.json').write_bytes((json.dumps(d, indent=2) + '\n').encode())
