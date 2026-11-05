"""Typed proposed table/procedure policy, not executed SQL or actual GRANTs."""
from pathlib import Path
import json

E=Path(__file__).resolve().parent
OWNER='sv_b_proc_owner'
OP='sv_b_operator';VER='sv_b_verifier';ISS='sv_b_use_issuer';RUN='sv_b_runtime';DEL='sv_b_delivery_controller';SAFE='sv_b_safety';BUD='sv_b_budget_approver'
# Every entry is an exact procedure -> login EXECUTE set -> table verb/columns.
P={
'b_append_approval':([OP],{'inv.node_role_approvals':('INSERT',['signed_record','prior_approval_hash','candidate_ref','operator_grant_ref'])}),
'b_begin_node_switch':([OP],{'inv.node_role_operations':('INSERT',['frozen_intent','expected_current_hash']),'inv.node_role_current':('UPDATE',['switch_state','operation_ref'])}),
'b_plan_fresh':([OP],{'inv.node_role_operations':('INSERT',['frozen_intent']),'inv.node_role_routing':('INSERT',['tenant_id','node_id','cohort_id','assignment_hash'])}),
'b_fence_cohort':([OP],{'inv.node_role_cohorts':('UPDATE',['fence_state','operation_ref'])}),
'b_append_candidate':([OP,VER],{'inv.node_role_candidates':('INSERT',['raw_node_proof','raw_host_proof','nonce','observed_at','static_hash'])}),
'b_record_gate_ack':([OP,VER],{'inv.node_role_gate_acks':('INSERT',['raw_node_signed_ack','command_hash','node_der_hash','candidate_ref'])}),
'b_member_cas':([OP],{'inv.node_channels':('UPDATE',['version','certificate_sha256','certificate_not_after','enabled']),'inv.node_role_member_cas':('INSERT',['operation_id','node_id','old_tuple','target_tuple'])}),
'b_commit_node_activation':([OP],{'inv.node_role_releases':('INSERT',['signed_record','approval_ref','candidate_ref']),'inv.node_role_delegations':('INSERT',['signed_record','release_ref']),'inv.node_role_admissions':('INSERT',['release_ref','delegation_ref','gate_ack_ref','generation']),'inv.node_role_leases':('INSERT',['admission_ref','expires_at','fresh_proof_ref']),'inv.node_role_current':('UPDATE',['approval_ref','admission_ref','lease_ref','switch_state','activation_ledger_ref']),'inv.node_role_activation_ledger':('INSERT',['exact_result','expected_prior_pointer_hash'])}),
'b_commit_fresh_cohort':([OP],{'inv.node_role_cohorts':('UPDATE',['fence_state','release_evidence_ref'])}),
'b_refresh_same_generation':([VER],{'inv.node_role_leases':('INSERT',['admission_ref','expires_at','fresh_proof_ref']),'inv.node_role_current':('UPDATE',['lease_ref'])}),
'b_prepare_key_delivery':([DEL],{'inv.node_role_delivery_challenges':('INSERT',['signed_challenge','activation_ledger_ref','nonce','expires_at','state'])}),
'b_append_key_possession':([ISS],{'inv.node_role_key_possessions':('INSERT',['challenge_ref','raw_use_key_signature','authenticated_issuer_tls_hash'])}),
'b_consume_key_challenge':([DEL],{'inv.node_role_delivery_challenges':('UPDATE',['state','consumption_ledger_ref']),'inv.node_role_delivery_consumptions':('INSERT',['challenge_ref','possession_ref','exact_context_hash'])}),
'b_record_key_delivery':([DEL],{'inv.node_role_key_deliveries':('INSERT',['protected_receipt','consumption_ref','activation_ledger_ref']),'inv.node_role_current':('UPDATE',['delivery_receipt_ref'])}),
'b_record_request_issuance':([ISS],{'inv.node_role_request_issuance':('INSERT',['node_id','request_hash','nonce','release_ref','expires_at'])}),
'b_commit_business_nonce_evidence':([RUN],{'inv.node_role_request_commits':('INSERT',['issuance_ref','request_hash','verified_outcome_ref']),'inv.evidence':('INSERT',['tenant_id','evidence_id','record'])}),
'b_commit_reconcile_receipt':([RUN,VER],{'inv.node_role_reconcile_evidence':('INSERT',['recorded_permit_hash','actual_node_outcome','authority_scope_ref'])}),
'b_record_safety_request':([SAFE],{'inv.node_role_safety_requests':('INSERT',['scoped_request','nonce','grant_ref'])}),
'b_update_service_bindings':([OP],{'inv.node_role_service_bindings':('INSERT_OR_UPDATE',['login_oid','tenant_scope','permitted_purposes','tls_identity_hash'])}),
'b_commit_node_observation':([VER],{'inv.nodes':('UPDATE',['heartbeat_at','probe_started_at','clock_skew_seconds','status'])}),
'b_change_node_containment':([OP,SAFE],{'inv.nodes':('UPDATE',['status']),'inv.tenant_controls':('UPDATE',['kill_switch','version'])}),
'b_public_node_observation':([RUN],{'public.nodes':('UPDATE',['heartbeat_sequence','last_heartbeat_at','status'])}),
'b_public_contribution_change':([OP],{'public.storage_contributions':('UPDATE',['status','version','normalized_path','registered_by_user_id'])}),
}
LOCKS={
'b_lock_business_scope':[RUN,ISS],
'b_lock_observation_scope':[OP,VER,RUN,SAFE],
'b_lock_operator_scope':[OP,DEL,SAFE],
'b_read_observation_scope':[OP,VER,RUN,SAFE],
}
DOMAINS={
'APPROVAL':('saintvision/node-role-approval/v1','OPERATOR_RELEASE',['APPROVAL_RENEW_SAME_CONFIG','REAPPROVE_SAME_CONFIG','FRESH_ACTIVATE']),
'RELEASE':('saintvision/node-role-release/v1','OPERATOR_RELEASE',['RELEASE']),
'DELEGATION':('saintvision/node-role-delegation/v1','OPERATOR_RELEASE',['DELEGATION']),
'GATE_CONTROL':('saintvision/node-role-gate/v1','OPERATOR_RELEASE',['ARM_EXACT_RELEASE','INVALIDATE_EXACT_GATE']),
'GATE_ACK':('saintvision/node-role-gate-ack/v1','REGISTERED_NODE_LEAF',['ACK_EXACT_DURABLE_TRANSITION']),
'DELIVERY_CHALLENGE':('saintvision/node-role-key-delivery-challenge/v1','OPERATOR_RELEASE',['KEY_DELIVERY_PREPARE']),
'KEY_POSSESSION':('saintvision/node-role-key-possession/v1','DELEGATED_USE_KEY',['PROVE_EXACT_CHALLENGE_POSSESSION']),
'KEY_DELIVERY_RECEIPT':('saintvision/node-role-key-delivery-receipt/v1','OPERATOR_RELEASE',['KEY_DELIVERY_RECEIPT']),
'ROLE_USE':('saintvision/node-role-use/v1','DELEGATED_USE_KEY',['BUSINESS_USE']),
'SAFETY':('saintvision/node-role-safety/v1','PROTECTED_SAFETY',['CANCEL_EXACT_COMMAND','QUARANTINE_EXACT_OBLIGATION']),
'CONTEXT_BUDGET':('saintvision/context-budget/v1','PROTECTED_BUDGET_APPROVER',['APPROVE_MEASURED_CONTEXT_BUDGET']),
}


def build():
    tables={}
    for proc,(roles,effects) in P.items():
        for table,(verb,columns) in effects.items():tables.setdefault(table,[]).append({'procedure':proc,'verb':verb,'columns':columns})
    tables.setdefault('inv.control_epoch',[])  # B-FRESH1 has no epoch-write procedure; external change enters recovery.
    return {'version':'fleet5-b-authority-rev4:1','implemented':False,'tables':tables,
            'procedures':{name:{'owner':OWNER,'execute':roles,'effects':{t:{'verb':v,'columns':cols} for t,(v,cols) in effects.items()},'searchPath':'pg_catalog','rowSecurity':'on/FORCE where applicable','arbitrarySqlOrTableParameter':False} for name,(roles,effects) in P.items()},
            'lockOnlyProcedures':{p:{'owner':OWNER,'execute':r,'columnsWritten':[],'canonicalOrder':['control_epoch','tenant_controls','routing/fence','sorted inv.nodes','sorted public.nodes/contributions','shared node_channels','role/current','business/run','operator grants/resources','nonce/evidence/ledger']} for p,r in LOCKS.items()},
            'allOnlineDirectAuthorityDML':{'INSERT':False,'UPDATE':False,'DELETE':False,'lock_sentinel_UPDATE':False,'SET_ROLE_to_owner_operator_or_legacy_inv_kernel':False},
            'principals':{'sv_b_ddl_owner':'NOLOGIN owns new B tables; not pooled',OWNER:'NOLOGIN non-super/non-bypass leastpriv function owner; no runtime membership',OP:'protected approval/release planner, separate credentials and purpose-restricted signing service',DEL:'protected postcommit delivery controller; no approval/plan EXECUTE',VER:'online authenticated evidence verifier, no approval/release signing key',ISS:'online delegated use key only, raw PoP append/issuance functions only',RUN:'dedicated ordinary B pool; no legacy inv_kernel/app membership that inherits authority DML',SAFE:'typed containment only; separate safety key',BUD:'distinct protected planning-budget role/key/pin, no Node release/business authority'},
            'signaturePurposes':{k:{'domain':d,'signer':s,'purposes':p} for k,(d,s,p) in DOMAINS.items()},
            'rls':'Every new B table ENABLE+FORCE RLS, add to actual census/collector/ratchet/aggregate pin during future migration. Procedures verify session_user/service binding, tenant/sorted Node set/purpose/current grant; GUC alone not authority. Fixed qualified SQL, no caller-supplied table or lock mode. b_guard equivalent retains mandatory epoch then tenant guard via owner lock operations before B locks.',
            'nodeCompromiseBound':'CP 300s admission lease is NOT a Node-enforced use-key compromise bound. Node bound is delegated/release/approval/cert expiry plus acknowledged gate invalidation; future protected signer/custody availability remains prerequisite.',
            'externalPlanningTrustPin':{'contextBudgetApproverPublicKeySHA256':None,'custodyRole':BUD,'permittedKind':'CONTEXT_BUDGET','cannotAuthorize':['Node release','business','safety']},'actualKeys':None,'actualDBGrants':False}


def valid_matrix(doc):
    expected=build()
    return all(doc.get(k)==expected[k] for k in ('tables','procedures','lockOnlyProcedures','allOnlineDirectAuthorityDML','signaturePurposes'))


if __name__=='__main__':(E/'authority-matrix.json').write_bytes((json.dumps(build(),indent=2)+'\n').encode())
