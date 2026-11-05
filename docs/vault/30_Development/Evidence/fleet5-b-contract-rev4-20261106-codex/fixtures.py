"""Causal Rev4 schema/state/policy fixtures, SYMBOLIC ONLY; real systems=0."""
from copy import deepcopy
from pathlib import Path
import base64
import json
import sys

from authority import build as authority_build,valid_matrix,OP,VER,ISS,DEL,SAFE,P
from model import *

E=Path(__file__).resolve().parent
RESULTS=[];SCHEMA_COVERAGE={}


def check(name,actual,expected=True):
    RESULTS.append({'name':name,'actual':actual,'expected':expected,'passed':actual==expected})


def artifact_schema(kind,obj):
    check('schema-positive-'+kind,shape(kind,obj));SCHEMA_COVERAGE[kind]={'positive':1,'negative':0}
    bad=deepcopy(obj);bad['unknownAuthority']=True
    check('schema-extra-deny-'+kind,shape(kind,bad),False);SCHEMA_COVERAGE[kind]['negative']+=1
    # Every required field, not just one convenient field.
    defs=SCHEMA['$defs'][kind]
    if 'required' in defs:
        for field in defs['required']:
            bad=deepcopy(obj);bad.pop(field);check('schema-missing-'+kind+'-'+field,shape(kind,bad),False);SCHEMA_COVERAGE[kind]['negative']+=1


def observation_scope(s,role=VER,intentId=None):
    permitted=role in (OP,VER,'sv_b_runtime',SAFE)
    if not permitted or not s['cpAuthenticated'] or s['trust']['nodeCertificateNotAfter']<=s['now']:
        return {'kind':'OBSERVATION_SCOPE','status':'AUTHORITY_UNAVAILABLE','businessAuthority':False,'reason':'INVALID_TRUST' if permitted else 'NO_OBSERVER_GRANT','nodeId':s['static']['nodeId'],'observedAt':s['now']}
    if intentId is not None and (not s.get('frozenIntent') or s['frozenIntent']['id']!=intentId):return {'kind':'OBSERVATION_SCOPE','status':'UNKNOWN_SCOPE','businessAuthority':False,'reason':'MISSING_PROTECTED_INTENT','nodeId':s['static']['nodeId'],'observedAt':s['now']}
    result={'kind':'OBSERVATION_SCOPE','status':'AVAILABLE','businessAuthority':False,'source':'CURRENT_REGISTERED','tenantId':s['static']['tenantId'],'nodeId':s['static']['nodeId'],'currentControlEpoch':s['static']['epoch'],'targetNodeEpoch':s['static']['epoch'],'targetDER':s['static']['DER'],'currentTuple':deepcopy(s['static']),'provenanceHash':digest(s['static']),'intentId':None,'method':'POST','paths':['/v1/roles/observe','/v1/executions/receipts'],'challenge':H,'issuedAt':s['now'],'expiresAt':s['now']+30,'diagnostic':'OBSERVE_ONLY'}
    if intentId is not None:result.update(source='FROZEN_INTENT_TARGET',intentId=intentId,targetDER=s['frozenIntent']['targetDER'],targetNodeEpoch=s['frozenIntent']['targetNodeEpoch'],provenanceHash=digest(s['frozenIntent']))
    return result


def clocks_valid(cap,budget):
    if not verified(budget,'CONTEXT_BUDGET','PROTECTED_BUDGET_APPROVER'):return False
    body=budget['body']
    for name,target,targetId in [('hostClock','HOST',cap['hostId']),('guestClock','GUEST',cap['vmUuid'])]:
        c=cap[name]
        if not shape('clockMeasurement',c) or c['target']!=target or c['targetId']!=targetId or c['contextId']!=body['contextId'] or c['challenge']!=body['nonce'] or not NOW-30<=c['observedAt']<=NOW or c['syncSource']!='AUTHENTICATED_CP_PROBE':return False
        if abs(c['clockOffsetMillis'])+c['uncertaintyMillis']>min(body['approvedSkewMillis'],30000):return False
        if c['producerArtifactHash']!=body['hostProbeHash' if target=='HOST' else 'guestProbeHash']:return False
    return True


def capability_valid(cap,budget):
    if not shape('capability',cap) or not shape('budget',budget['body']) or not clocks_valid(cap,budget):return False
    b=budget['body']
    if not window(b,NOW) or cap['root']['contextId']!=b['contextId'] or cap['hostId']!=b['hostId'] or cap['vmUuid']!=b['vmUuid'] or cap['vmSpecHash']!=b['vmSpecHash']:return False
    if cap['vmVcpus']!=b['vcpus'] or cap['vmRamBytes']!=b['guestRamBytes'] or cap['vmDiskBytes']!=b['guestDiskBytes']:return False
    if cap['nodeKernelBootId']!=cap['vmKernelBootId'] or cap['hostKernelId']==cap['vmKernelBootId']:return False
    return cap['hostPhysicalAvailableBytes']>=b['guestRamBytes']+b['hostMemoryHeadroomBytes'] and cap['hostCommitAvailableBytes']>=b['guestRamBytes']+b['hostMemoryHeadroomBytes'] and cap['hostDiskAvailableBytes']>=b['guestDiskBytes']+b['hostDiskHeadroomBytes'] and cap['guestNativeFsAvailableBytes']>=b['guestNativeFreeMinBytes'] and cap['hostCpuAvailableMilliCpus']>=b['vcpus']*1000+b['hostCpuSpareMinMilliCpus']


def cas_outcome(current,ledger,target,authority=True,fresh=True,externalOutcomeKnown=False):
    if not authority or not fresh:return 'QUARANTINED'
    if ledger is not None and ledger.get('target')==target and current==target:return 'RESOLVED_EXACT_COMMIT_FORWARD'
    if ledger is not None:return 'QUARANTINED'
    if current==target:return 'QUARANTINED'
    return 'EXACT_INTENT_FORWARD_AFTER_REOBSERVATION' if externalOutcomeKnown and current.get('enabled') and current['C']==target['C']-1 else 'REOBSERVE_OR_QUARANTINED'


def approval_phase_trace(after_expiry):
    s=released_state()
    if after_expiry:s['now']+=700
    rows=[]
    def capture(phase):
        cur=s['current'];gate=s['node']['gate'];eligible=cp_eligible(s,cur,role_use(s))
        rows.append({'phase':phase,'approvalMode':'REAPPROVE_ONLY_TIME_EXPIRED' if after_expiry else 'APPROVAL_RENEW_BEFORE_EXPIRY','currentApprovalHash':digest(cur['approval']),'currentApprovalInterval':{'issuedAt':cur['approval']['body']['issuedAt'],'expiresAt':cur['approval']['body']['expiresAt']},'currentPointerHash':cur['pointerHash'],'nodeGeneration':s['node']['generation'],'gateId':gate['gateId'] if gate else None,'gateState':gate['state'] if gate else 'NONE','currentReceiptHash':digest(cur['receipt']) if cur['receipt'] else None,'switchPending':s['switchPending'],'computedEligible':eligible,'lossRule':'Stop next transition, UNKNOWN until exact committed ledger/current tuple plus fresh Node proof; no old authority restoration, no claims freed','expiryRule':'Affected Node unavailable, no silent time extension/new key/challenge. Resume exact still-valid intent or reviewed recovery.'})
        if phase not in ('OBSERVE_SELECTED','APPEND_APPROVAL_NOT_CURRENT','FINAL_RECEIPT_COMMITTED'):
            check('phase-no-premature-business-'+str(after_expiry)+'-'+phase,eligible,False)
    capture('OBSERVE_SELECTED');a=append_approval(s,'REAPPROVE_SAME_CONFIG' if after_expiry else 'APPROVAL_RENEW_SAME_CONFIG',s['now']+7200);assert a;capture('APPEND_APPROVAL_NOT_CURRENT')
    m=material(s,a,'phase-after' if after_expiry else 'phase-before');s['switchPending']=True;capture('PAUSE_SELECTED')
    old={k:s['current'][k] for k in ('approval','release','delegation')};ia=node_command(s,old,command(s,old,'INVALIDATE_EXACT_GATE'));assert ia and record_ack(s,ia);capture('INVALIDATE_OLD_ACK_AND_DRAIN')
    ack=node_command(s,m,command(s,m,'ARM_EXACT_RELEASE'));assert ack and record_ack(s,ack);capture('ARM_NEW_ACK')
    assert commit_activation(s,m,ack);capture('CURRENT_CAS_COMMITTED_NO_RECEIPT')
    ch=delivery_challenge(s);assert ch;capture('CHALLENGE_PREPARED_POSTCOMMIT')
    pop=possession(ch);capture('USE_KEY_POSSESSION_PENDING_VERIFY')
    receipt=consume_possession(s,ch,pop);assert receipt;capture('CHALLENGE_CONSUMED_PENDING_RECEIPT')
    assert record_delivery(s,receipt);capture('FINAL_RECEIPT_COMMITTED')
    check('phase-final-selected-eligible-'+str(after_expiry),rows[-1]['computedEligible'])
    return rows


def main():
    s=released_state();u=role_use(s);check('stateful-full-old-chain',cp_eligible(s,s['current'],u))
    examples={k:deepcopy(s['current'][k]) for k in ('approval','release','delegation','receipt')}
    for kind,key in [('approval','approval'),('release','release'),('delegation','delegation'),('keyDeliveryReceipt','receipt')]:artifact_schema(kind,examples[key]['body'])
    artifact_schema('roleUse',u['body']);artifact_schema('gateAck',s['current']['ack']['body'])
    ch=next(iter(s['challenges'].values()))['artifact'];pop=next(iter(s['challenges'].values()))['possession']
    artifact_schema('deliveryChallenge',ch['body']);artifact_schema('keyPossession',pop['body'])
    a=append_approval(s,'APPROVAL_RENEW_SAME_CONFIG',s['now']+7200);check('before-expiry-per-node-new-approval',a is not None)
    check('approval-prior-hash-links-immutable-current',a['body']['priorApprovalHash']==digest(s['current']['approval']))
    check('old-approval-not-mutated',s['current']['approval']==examples['approval'])
    m=material(s,a,'renew');cmd=command(s,m,'ARM_EXACT_RELEASE');artifact_schema('gateControl',cmd['body'])
    check('cannot-ARM-over-live-old-gate',node_command(deepcopy(s),m,cmd),None)
    for signer in ('DELEGATED_USE_KEY','PROTECTED_SAFETY'):
        bad=seal('GATE_CONTROL',cmd['body'],signer);check('ARM-wrong-signer-rebound-'+signer,node_command(deepcopy(s),m,bad),None)
    oldUse=deepcopy(u);s['switchPending']=True;newUse=finish(s,m)
    check('same-generation-approval-renew-complete',cp_eligible(s,s['current'],newUse))
    check('invalidated-old-gate-token-no-overlap',node_accepts(s,{**examples,'ack':s['current']['ack']},oldUse),False)
    for missing in ('NONE','INVALIDATED'):
        bad=deepcopy(s);bad['node']['gate']=None if missing=='NONE' else {**bad['node']['gate'],'state':'INVALIDATED'};check('valid-chain-'+missing+'-gate-deny',node_accepts(bad,bad['current'],newUse),False)
    bad=deepcopy(s);bad['node']['generation']='new-trusted-generation';bad['node']['gate']=None
    check('restart-has-no-gate-old-chain-denied',node_accepts(bad,bad['current'],newUse),False)
    check('READMIT-genuinely-changed-generation',readmit_allowed(bad,candidate(bad)))
    check('READMIT-old-old-denied',readmit_allowed(s,candidate(s)),False)
    check('same-generation-REFRESH-positive',refresh_same_generation(s,candidate(s)))
    readmitUse=finish(bad,material(bad,bad['current']['approval'],'readmit'))
    check('changed-generation-protected-readmit-complete',cp_eligible(bad,bad['current'],readmitUse))
    # Only approval time expired; unrelated offline members are never read.
    expired=released_state();expired['now']+=700
    check('REFRESH-expired-approval-denied',approval_valid(expired,expired['current']['approval']),False)
    check('ordinary-renew-cannot-use-expired-approval',append_approval(expired,'APPROVAL_RENEW_SAME_CONFIG',expired['now']+3600),None)
    renewed=append_approval(expired,'REAPPROVE_SAME_CONFIG',expired['now']+7200);check('after-only-expiry-new-protected-approval',renewed is not None)
    use=finish(expired,material(expired,renewed,'reapprove'));check('after-expiry-per-node-no-unrelated-refresh',cp_eligible(expired,expired['current'],use))
    for field in ('cohortFence','quarantined','containment','switchPending'):
        x=released_state();x['now']+=700;x[field]=True;check('REAPPROVE-block-'+field,append_approval(x,'REAPPROVE_SAME_CONFIG',x['now']+1000),None)
    for field in ('C','R','P','epoch','policySha256','configSha256','peerFloorSha256','storageFloorSha256'):
        x=released_state();x['now']+=700;x['static'][field]=x['static'][field]+1 if type(x['static'][field]) is int else 'changed';check('REAPPROVE-drift-'+field,append_approval(x,'REAPPROVE_SAME_CONFIG',x['now']+1000),None)
    for why in ('revoked','grantExpired','certExpired','trustExpired'):
        x=released_state();x['now']+=700
        if why=='revoked':x['revokedApprovals'].add(digest(x['current']['approval']))
        if why=='grantExpired':x['grant']['expiresAt']=x['now']
        if why=='certExpired':x['trust']['nodeCertificateNotAfter']=x['now']
        if why=='trustExpired':x['trust']['operatorTrustNotAfter']=x['now']
        check('REAPPROVE-authority-'+why,append_approval(x,'REAPPROVE_SAME_CONFIG',x['now']+1000),None)
    for role in (VER,ISS,DEL):
        x=released_state();check('online-cannot-append-approval-'+role,append_approval(x,'APPROVAL_RENEW_SAME_CONFIG',x['now']+1000,role),None)
    x=released_state();check('approval-max24h',append_approval(x,'APPROVAL_RENEW_SAME_CONFIG',x['now']+86401),None)
    # Gate ack is Node signed and represents an actual durable model transition.
    ack=deepcopy(s['current']['ack']);fake=seal('GATE_ACK',ack['body'],'HELPER_ASSERTED_ARMED');check('helper-ARMED-not-node-ack',record_ack(s,fake),False)
    fake=seal('GATE_ACK',{**ack['body'],'localGateRecordId':'f'*64},'NODE:'+s['static']['DER']);check('no-durable-transition-no-ack',record_ack(s,fake),False)
    fake=seal('GATE_ACK',{**ack['body'],'nodeCertificateSHA256':'f'*64},'NODE:'+s['static']['DER']);check('ack-wrong-registered-leaf',record_ack(s,fake),False)
    # Full postcommit delivery flow, independent proofs and causal rebindings.
    x=released_state();a=append_approval(x,'APPROVAL_RENEW_SAME_CONFIG',NOW+3600);mat=material(x,a,'delivery');old={k:x['current'][k] for k in ('approval','release','delegation')};ia=node_command(x,old,command(x,old,'INVALIDATE_EXACT_GATE'));assert record_ack(x,ia)
    ga=node_command(x,mat,command(x,mat,'ARM_EXACT_RELEASE'));assert record_ack(x,ga)
    check('delivery-before-activation-commit-deny',delivery_challenge(x),None)
    assert commit_activation(x,mat,ga);check('no-new-approval-from-incomplete-handoff',append_approval(x,'APPROVAL_RENEW_SAME_CONFIG',NOW+7200),None);check('ACTIVE-row-without-delivery-not-business',cp_eligible(x,x['current'],role_use(x)),False);challenge=delivery_challenge(x);assert challenge
    check('prepare-retry-SAME-frozen-challenge',delivery_challenge(x)==challenge)
    for label,signer,domain in [('wrong-use-key','USE:wrong',None),('wrong-domain',None,'saintvision/wrong/v1')]:
        trial=deepcopy(x);check('PoP-'+label,consume_possession(trial,challenge,possession(challenge,signer,domain)),None)
    check('PoP-wrong-issuer-TLS',consume_possession(deepcopy(x),challenge,possession(challenge),{'id':x['issuer']['id'],'tlsHash':'f'*64}),None)
    for field,value in [('activationLedgerId','foreign-ledger'),('releaseHash','e'*64),('delegationHash','e'*64),('useKeyHash','e'*64),('gateId','foreign-gate'),('issuerServiceId','foreign-issuer')]:
        trial=deepcopy(x);body={**challenge['body'],field:value};changed=seal('DELIVERY_CHALLENGE',body);trial['challenges'][body['challengeId']]['artifact']=changed
        check('rebound-challenge-context-'+field,consume_possession(trial,changed,possession(changed)),None)
    trial=deepcopy(x);trial['now']+=61;check('expired-challenge-deny',consume_possession(trial,challenge,possession(challenge)),None)
    receipt=consume_possession(x,challenge,possession(challenge));assert receipt
    check('consumed-challenge-replay-deny',consume_possession(x,challenge,possession(challenge)),None)
    check('issuer-cannot-record-controller-receipt',record_delivery(x,receipt,ISS),False)
    check('use-key-cannot-sign-controller-receipt',record_delivery(x,seal('KEY_DELIVERY_RECEIPT',receipt['body'],'USE:'+receipt['body']['useKeyHash'])),False)
    assert record_delivery(x,receipt);check('cannot-reset-consumed-challenge-by-prepare',delivery_challenge(x),None);u=role_use(x);check('controller-receipt-final-chain-positive',cp_eligible(x,x['current'],u))
    for field,value in [('activationLedgerId','wrong'),('issuerTLSHash','e'*64),('issuerServiceId','wrong'),('releaseHash','e'*64),('useKeyHash','e'*64),('gateAckHash','e'*64),('expiresAt',NOW-1)]:
        trial=deepcopy(x);trial['current']['receipt']=seal('KEY_DELIVERY_RECEIPT',{**receipt['body'],field:value});rebound=role_use(trial)
        check('all-dependent-hashes-rebound-receipt-'+field,node_accepts(trial,trial['current'],rebound),False)
    # CP lease is intentionally not a Node-side compromised-use-key bound.
    trial=deepcopy(x);trial['now']+=301;forgedUse=role_use(trial)
    check('expired-CP-lease-denies-business-issuer',cp_eligible(trial,trial['current'],forgedUse),False)
    check('Node-role-layer-bound-is-delegation-not300s',node_accepts(trial,trial['current'],forgedUse))
    # Closed ancillary artifacts, both AVAILABLE and refusal schemas.
    available=observation_scope(x);artifact_schema('observationScope',available)
    denied=observation_scope(x,role=ISS);check('scope-refusal-positive',shape('observationScope',denied));bad={**denied,'targetDER':H};check('refusal-cannot-carry-eligible-target',shape('observationScope',bad),False)
    frozen=deepcopy(x);frozen['frozenIntent']={'id':'protected-intent','targetDER':'e'*64,'targetNodeEpoch':x['static']['epoch']}
    fs=observation_scope(frozen,intentId='protected-intent');check('scope-frozen-intent-positive',shape('observationScope',fs));check('scope-frozen-missing-intent-deny',shape('observationScope',{**fs,'intentId':None}),False)
    check('scope-missing-authoritative-intent-refusal',observation_scope(x,intentId='unknown')['status'],'UNKNOWN_SCOPE')
    late=deepcopy(x);late['now']=late['current']['approval']['body']['expiresAt']+1
    check('observation-independent-business-approval-expiry',observation_scope(late)['status'],'AVAILABLE')
    check('ObservationScope-cannot-be-admission',cp_eligible(x,available,u),False);check('ObservationScope-cannot-be-node-business',node_accepts(x,available,u),False);check('ObservationScope-cannot-be-gate-ack',record_ack(x,available),False)
    artifact_schema('observeInput',{'nonce':H})
    safety={'nodeId':x['static']['nodeId'],'epoch':x['static']['epoch'],'action':'CANCEL_EXACT_COMMAND','method':'POST','path':'/v1/executions/cancel','permitHash':H,'bodyHash':H,'nonce':H,'issuedAt':NOW,'expiresAt':NOW+60};artifact_schema('safety',safety)
    for field,value in [('method','GET'),('path','/v1/builds/quarantine'),('path','/v1/executions/cancel?x=1')]:check('safety-raw-binding-'+field+'-'+value,shape('safety',{**safety,field:value}),False)
    config={'schemaVersion':'saintvision-node-role-config:2','role':'workspace-storage-ro-v1','operatorReleaseAnchorSha256':H,'operatorReleasePublicPath':'/state/role-release-authority.pub','safetyAnchorSha256':'b'*64,'safetyPublicPath':'/state/role-safety-authority.pub','contextId':'vm-fixture','gateProtocol':'saintvision-node-role-release:1','useProtocol':'saintvision-node-role-use:1'};artifact_schema('roleConfig',config)
    wire={'kind':'GATE_ACK','payloadBase64url':base64.urlsafe_b64encode(canonical(ga['body'])).rstrip(b'=').decode(),'signatureHex128':'a'*128};artifact_schema('signedEnvelope',wire)
    for tail in ('\n','\x00','x'):check('exact-hash-alphabet-'+repr(tail),shape('hash',H+tail),False)
    check('strict-float-time-composition',shape('roleUse',{**u['body'],'issuedAt':float(NOW)}),False)
    check('purpose-path-coupled-schema',shape('roleUse',{**u['body'],'purpose':'TERMINAL'}),False)
    label='\U0001f600'*128;check('display-128-codepoints-512bytes',shape('displayLabel',label) and len(label.encode())==512);check('display129-deny',shape('displayLabel',label+'x'),False)
    # Budget key purpose and raw authenticated host/guest clock measurement.
    old=json.loads((E.parent/'fleet5-b-contract-rev3-20261106-codex/synthetic-positive-fixtures.json').read_bytes());cap=old['capability'];bb=old['SYNTHETIC_approvedBudget']['body'];bb.update(cohortId='cohort',vmSpecHash=H,hostProbeHash=H,guestProbeHash=H,approvedSkewMillis=30000,nonce=H,issuedAt=NOW);budget=seal('CONTEXT_BUDGET',bb);cap['vmSpecHash']=bb['vmSpecHash']
    for name,target,tid in [('hostClock','HOST',cap['hostId']),('guestClock','GUEST',cap['vmUuid'])]:cap[name]={'target':target,'targetId':tid,'contextId':bb['contextId'],'challenge':H,'clockOffsetMillis':-100,'uncertaintyMillis':100,'syncSource':'AUTHENTICATED_CP_PROBE','method':'AUTHENTICATED_CP_ROUNDTRIP_BOUND','producerId':'independent-probe','producerArtifactHash':H,'evidenceHash':H,'observedAt':NOW}
    artifact_schema('clockMeasurement',cap['hostClock']);artifact_schema('capability',cap);artifact_schema('budget',bb)
    check('clock-budget-positive',clocks_valid(cap,budget));check('raw-resource-plus-clock-budget-positive',capability_valid(cap,budget))
    low=deepcopy(cap);low['hostPhysicalAvailableBytes']=125*2**20;check('host-resource-unavailable-not-a-guest-positive',capability_valid(low,budget),False)
    over=deepcopy(cap);over['vmRamBytes']*=2;check('unapproved-vm-spec-not-minimum-budget',capability_valid(over,budget),False)
    check('release-key-cannot-approve-budget',clocks_valid(cap,seal('CONTEXT_BUDGET',bb,'OPERATOR_RELEASE')),False)
    for side in ('hostClock','guestClock'):
        for field,value in [('clockOffsetMillis',30000),('uncertaintyMillis',30000),('clockOffsetMillis',1.0),('syncSource','UNTRUSTED'),('observedAt',NOW-31),('challenge','e'*64)]:
            bad=deepcopy(cap);bad[side][field]=value;check('clock-'+side+'-'+field,clocks_valid(bad,budget),False)
    # Every typed table, writer, principal/owner/column grant is checked.
    policy=authority_build();stored=json.loads((E/'authority-matrix.json').read_bytes());check('complete-typed-policy',valid_matrix(stored))
    for table,writers in policy['tables'].items():
        for index,writer in enumerate(writers):
            bad=deepcopy(policy);bad['tables'][table].pop(index);check('remove-writer-'+table+'-'+writer['procedure'],valid_matrix(bad),False)
    for proc,definition in policy['procedures'].items():
        for index,principal in enumerate(definition['execute']):
            bad=deepcopy(policy);bad['procedures'][proc]['execute'].pop(index);check('remove-execute-'+proc+'-'+principal,valid_matrix(bad),False)
    for proc,definition in policy['lockOnlyProcedures'].items():
        for index,principal in enumerate(definition['execute']):
            bad=deepcopy(policy);bad['lockOnlyProcedures'][proc]['execute'].pop(index);check('remove-lock-execute-'+proc+'-'+principal,valid_matrix(bad),False)
    bad=deepcopy(policy);bad['procedures']['b_append_approval']['execute'].append('sv_b_runtime');check('add-runtime-approval-grant-deny',valid_matrix(bad),False)
    bad=deepcopy(policy);bad['allOnlineDirectAuthorityDML']['UPDATE']=True;check('direct-authority-UPDATE-deny',valid_matrix(bad),False)
    # Not-yet-CAS revocations C+1==target while DER stays old are never done.
    phase=[]
    for k in range(1,5):
        for node in range(k,5):
            target={'node':node,'C':8,'DER':'B','enabled':True};revoked={'node':node,'C':8,'DER':'A','enabled':False};result=cas_outcome(revoked,None,target);check('not-yet-CAS-revoke-'+str(k)+'-'+str(node),result,'REOBSERVE_OR_QUARANTINED');phase.append({'kCAS':k,'revokedUnCASNode':node,'POverlap':102,'PFinalRequired':103,'R':2,'current':revoked,'target':target,'ledger':None,'outcome':result,'fenceRetained':True})
    target={'node':0,'C':8,'DER':'B','enabled':True};ledger={'target':target}
    check('resolved-exact-commit-forward',cas_outcome(target,ledger,target),'RESOLVED_EXACT_COMMIT_FORWARD')
    check('exact-ledger-no-revocation-waiver',cas_outcome(target,ledger,target,authority=False),'QUARANTINED')
    check('exact-ledger-no-freshness-waiver',cas_outcome(target,ledger,target,fresh=False),'QUARANTINED')
    check('missing-ledger-no-external-effects-inference',cas_outcome({'node':0,'C':7,'DER':'A','enabled':True},None,target),'REOBSERVE_OR_QUARANTINED')
    approvalRows=approval_phase_trace(False)+approval_phase_trace(True)
    phase.extend([{'event':'UNRESOLVED_AFTER_EXACT_LEDGER_REREAD','outcome':'QUARANTINED','freshAuthorityDoesNotResolveUnknownEffects':True},{'event':'RESOLVED_EXACT_COMMIT_FORWARD','requires':'matching full ledger+DER+current tuple+fresh valid frozen authority; no expiry/revoke waiver'}])
    (E/'phase-cases.json').write_bytes((json.dumps({'overlapP':102,'requiredFinalP':103,'CBase':7,'CTarget':8,'R':2,'revocationsAndLostResponses':phase,'perNodeApprovalRows':approvalRows,'perNodeApprovalPhases':['OBSERVE_SELECTED','APPEND_NEW_PROTECTED_APPROVAL_NOT_CURRENT','PAUSE_SELECTED_ISSUANCE','INVALIDATE_OLD_GATE_ACK_AND_DRAIN','ARM_REPLACEMENT_ACK','CANONICAL_PER_NODE_ACTIVATION_CURRENT_CAS','POSTCOMMIT_CHALLENGE','USE_KEY_POSSESSION','CONTROLLER_CONSUMPTION','PROTECTED_RECEIPT_COMMIT_AND_PUBLISH','ELIGIBLE_SELECTED_NODE'],'allLossOrExpiry':'UNAVAILABLE/UNKNOWN; retain claims/monotonic evidence, exact ledger+fresh Node proof only, no old authority restore'},indent=2)+'\n').encode())
    result={'level':'SCHEMA_STATIC_STATEFUL_SYMBOLIC_ONLY','passed':sum(r['passed'] for r in RESULTS),'failed':sum(not r['passed'] for r in RESULTS),'schemaCoverage':SCHEMA_COVERAGE,'realGoCryptoPGDockerCrashConcurrencyEquipment':0,'cases':RESULTS}
    (E/'fixture-results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());(E/'stateful-positive.json').write_bytes((json.dumps({'WARNING':'SYMBOLIC ONLY, NO REAL KEYS OR SIGNATURES','state':x,'use':u,'scope':available,'wireShapeOnly':wire,'clockCapability':cap,'budget':budget},indent=2,default=lambda o:sorted(o))+'\n').encode())
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','schemaCoverage')}))
    if result['failed']:print(json.dumps([r for r in RESULTS if not r['passed']]));raise SystemExit(1)


if __name__=='__main__':main()
