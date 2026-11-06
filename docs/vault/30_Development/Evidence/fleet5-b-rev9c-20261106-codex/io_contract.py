"""Proposed closed CP effect policy. This is not installed product behavior."""
SIDE_EFFECT='SIDE_EFFECT'
READ_ONLY='READ_ONLY'
SAFETY='IDEMPOTENT_SAFETY'
EFFECT={k:SIDE_EFFECT for k in ('EXECUTE','BUILD_DISPATCH','TERMINAL_FRAME','B_GATE_ARM','RECEIPT_OBSERVE')}
EFFECT.update({k:SAFETY for k in ('CANCEL','QUARANTINE_RECONCILE','B_GATE_INVALIDATE')})
EFFECT.update({k:READ_ONLY for k in ('HEARTBEAT_OBSERVE','GPU_ACTIVE_OBSERVE','STORAGE_SAMPLE','OBJECT_READ','BUILD_HEALTH_READ','BUILD_CLEANUP_READ','B_ROLE_OBSERVE','B_FOLDER_ROOT_OBSERVE')})
# Actual /receipts calls Runner.Observe -> reconcile -> Stop/Remove/Save.
# It cannot acquire READ_ONLY semantics merely because of its CP method name.
CONTINUATIONS={'TERMINAL_FRAME','OBJECT_READ','BUILD_CLEANUP_READ','RECEIPT_OBSERVE','CANCEL'}
RECOVERY='sv_b_recovery_observation_verifier'
RECOVERY_CONTINUATIONS={'CANCEL','RECEIPT_OBSERVE'}
CONTINUATION_POLICY={
 'TERMINAL_FRAME':{'lane':'EXACT_MATCHED_CLAIM_LIVE_TERMINAL','nodeProjection':['online','draining'],'tenantExecutionGate':'KNOWN_AND_KILL_SWITCH_FALSE','parentKind':'EXECUTE','parentState':'PENDING_IO_LIVE_CURRENT_INCARNATION','sameAdmittedClaimVersion':True,'matchedClaimActive':True,'perRunWorkload':'RUNNING_CURRENT_ATTEMPT','allSameRunLeases':'KNOWN_UNRELEASED_UNEXPIRED','deadline':'STRICTLY_GREATER_THAN_NOW_PLUS_5','liveExecutionLease':True,'liveActivationLease':True,'businessFactsAllowed':['DRAIN'],'unknownParent':'REFUSE'},
 'CANCEL':{'lane':'CURRENT_AUTHENTICATED_RECOVERY','liveExecutionLease':False,'liveActivationLease':False,'businessFactsAllowed':['DRAIN','QUARANTINE','RETIRE'],'unknownParent':'ALLOW_SAFETY_ONLY'},
 'RECEIPT_OBSERVE':{'lane':'CURRENT_AUTHENTICATED_RECOVERY','liveExecutionLease':False,'liveActivationLease':False,'businessFactsAllowed':['DRAIN','QUARANTINE','RETIRE'],'unknownParent':'PROTECTED_RECONCILE_ONLY'},
 'OBJECT_READ':{'lane':'EXACT_ORIGINAL_READ_AUTHORIZATION','unknownParent':'REFUSE'},
 'BUILD_CLEANUP_READ':{'lane':'EXACT_PROTECTED_BUILD_EVIDENCE_READ','parentKind':'BUILD_DISPATCH','liveExecutionLease':False,'runningWorkloadRequired':False,'afterPhysicalCompletionOrRelease':'READ_ALLOWED_IF_EXACT_PROTECTED_PURPOSE_CURRENT_AUTH','unknownParent':'BOUNDED_READ_ONLY_NO_SETTLEMENT','claimRelease':'ONLY_ORIGINAL_TYPED_KERNEL_CONSEQUENCE_CAS','runtimeBinding':'NULL_T3_RUNTIME_PENDING'}}
READER_PURPOSE={
 'R01':'CANDIDATE_HINT','R02':'SPECULATIVE_HINT','R03':'EXECUTION_ADMISSION',
 'R04':'LEASE_ADMISSION','R05':'CAPACITY_HINT','R06':'SCHEDULER_HINT',
 'R07':'BUILD_ADMISSION','R08':'GPU_ADMISSION','R09':'MODEL_COMMIT_ADMISSION',
 'R10':'MODEL_LOCALITY_HINT','R11':'TOOL_CLAIM_ADMISSION',
 'R12':'EXACT_TERMINAL_CONTINUATION','R13':'DELIVERY_FOR_ADMITTED_OPERATION'}

def intersects(a,b):
    """DB-discovered lock footprints: shared readers coexist; writes conflict.

    None/unknown is conservative for this operation, never a global outage.
    rank is checked against the shared catalog at fixture admission.
    """
    if not a or not b or not a['known'] or not b['known']:return True
    return any(x['table']==y['table'] and x['key']==y['key'] and
               'UPDATE' in (x['mode'],y['mode']) for x in a['rows'] for y in b['rows'])

def fixture_footprint(resource='resource-1',run='run-1',known=True):
    from rank_contract import RANK
    return {'known':known,'rows':[
        {'rank':RANK[t],'table':t,'key':k,'mode':m} for t,k,m in (
          ('inv.node_channels','node-current','SHARE'),('inv.node_role_current','node-current','SHARE'),
          ('inv.runs',run,'UPDATE'),('inv.resources',resource,'UPDATE'),('inv.resource_claims','claim:'+run+':'+resource,'UPDATE'))]}
