"""Proposed Rev4 closed record shapes; normative decoder/semantic checks also apply."""
from pathlib import Path
import json

E=Path(__file__).resolve().parent
END=r'(?![\s\S])'
H={'type':'string','minLength':64,'maxLength':64,'pattern':'^[0-9a-f]{64}'+END}
I={'type':'string','minLength':1,'maxLength':128,'pattern':'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}'+END}
T={'type':'integer','minimum':1,'maximum':9007199254740991}
U={'type':'integer','minimum':0,'maximum':9007199254740991}


def obj(p):return {'type':'object','additionalProperties':False,'required':list(p),'properties':p}
def ref(k):return {'$ref':'#/$defs/'+k}
def enum(*v):return {'enum':list(v)}
def const(v):return {'const':v}
def array(v):return {'type':'array','minItems':1,'uniqueItems':True,'items':v}


def build():
    prior=json.loads((E.parent/'fleet5-b-contract-rev3-20261106-codex/contract.schema.json').read_bytes())
    D=prior['$defs']
    static={k:v for k,v in D['tuple']['properties'].items() if k not in ('generation','gateId','operationId')}
    static['tenantId']=I;D['static']=obj(static)
    D['operatorGrant']=obj({'grantId':I,'nodeIds':array(I),'staticHash':H,'purposes':array(enum('APPROVAL_RENEW_SAME_CONFIG','REAPPROVE_SAME_CONFIG','READMIT_SAME_CONFIG','FRESH_ACTIVATE')),'issuedAt':T,'expiresAt':T,'revoked':{'type':'boolean'}})
    D['trust']=obj({'nodeDER':H,'nodeCertificateNotBefore':T,'nodeCertificateNotAfter':T,'operatorTrustNotBefore':T,'operatorTrustNotAfter':T,'cpTrustNotAfter':T,'revoked':{'type':'boolean'}})
    D['candidate']=obj({'candidateId':I,'static':ref('static'),'generation':I,'nodeProofHash':H,'hostProofHash':H,'nonce':H,'observedAt':T,'expiresAt':T})
    D['approval']=obj({'approvalId':I,'priorApprovalHash':H,'static':ref('static'),'operationId':I,'operatorGrantHash':H,'trustHash':H,'candidateHash':H,'purpose':enum('APPROVAL_RENEW_SAME_CONFIG','REAPPROVE_SAME_CONFIG','FRESH_ACTIVATE'),'nonce':H,'issuedAt':T,'expiresAt':T})
    D['release']=obj({'releaseId':I,'approvalHash':H,'static':ref('static'),'operationId':I,'generation':I,'gateId':I,'activationLedgerId':I,'expectedPriorCurrentPointerHash':H,'useKeyHash':H,'issuerServiceId':I,'issuerTLSHash':H,'issuedAt':T,'expiresAt':T})
    D['delegation']=obj({'delegationId':I,'releaseHash':H,'nodeId':I,'epoch':I,'generation':I,'gateId':I,'usePublicKeyHex64':H,'useKeyHash':H,'issuerServiceId':I,'issuerTLSHash':H,'purposes':array(enum('EXECUTION','MODEL','TRANSFER','TERMINAL','STORAGE_COLLECT')),'issuedAt':T,'expiresAt':T})
    D['gateControl']=obj({'action':enum('ARM_EXACT_RELEASE','INVALIDATE_EXACT_GATE'),'method':const('POST'),'path':const('/v1/roles/gate'),'staticHash':H,'nodeId':I,'epoch':I,'generation':I,'gateId':I,'expectedPriorGateId':I,'releaseHash':H,'delegationHash':H,'useKeyHash':H,'nonce':H,'issuedAt':T,'expiresAt':T})
    D['gateAck']=obj({'nodeId':I,'tenantId':I,'nodeCertificateSHA256':H,'action':enum('ARM_EXACT_RELEASE','INVALIDATE_EXACT_GATE'),'commandHash':H,'requestBodyHash':H,'releaseHash':H,'delegationHash':H,'useKeyHash':H,'gateId':I,'priorGateId':I,'generation':I,'epoch':I,'static':ref('static'),'nonce':H,'observedAt':T,'expiresAt':T,'localGateRecordId':H,'priorLocalGateRecordId':H,'state':enum('ARMED','INVALIDATED')})
    context={'deliveryId':I,'challengeId':I,'activationLedgerId':I,'activationLedgerHash':H,'releaseHash':H,'delegationHash':H,'useKeyHash':H,'gateAckHash':H,'nodeId':I,'cohortId':I,'epoch':I,'generation':I,'gateId':I,'staticHash':H,'issuerServiceId':I,'issuerTLSHash':H,'nonce':H,'issuedAt':T,'expiresAt':T}
    D['deliveryChallenge']=obj(context)
    D['keyPossession']=obj({'challengeHash':H,'challenge':ref('deliveryChallenge')})
    receipt={**context,'receiptId':I,'challengeHash':H,'possessionHash':H,'consumptionLedgerId':I,'priorCurrentPointerHash':H,'priorState':const('CONSUMED_PENDING_RECEIPT'),'currentState':const('DELIVERED_CURRENT')}
    D['keyDeliveryReceipt']=obj(receipt)
    D['roleUse']=obj({'releaseHash':H,'delegationHash':H,'receiptHash':H,'nodeId':I,'epoch':I,'generation':I,'gateId':I,'purpose':enum('EXECUTION','MODEL','TRANSFER','TERMINAL','STORAGE_COLLECT'),'method':const('POST'),'path':enum('/v1/executions','/v1/objects/read','/v1/terminals/frame','/v1/storage/sample'),'bodyHash':H,'nonce':H,'issuedAt':T,'expiresAt':T})
    D['roleUse']['allOf']=[{'if':{'properties':{'purpose':enum(*purposes)}},'then':{'properties':{'path':const(path)}}} for purposes,path in [(['EXECUTION','MODEL'],'/v1/executions'),(['TRANSFER'],'/v1/objects/read'),(['TERMINAL'],'/v1/terminals/frame'),(['STORAGE_COLLECT'],'/v1/storage/sample')]]
    D['safety']=obj({'nodeId':I,'epoch':I,'action':enum('CANCEL_EXACT_COMMAND','QUARANTINE_EXACT_OBLIGATION'),'method':const('POST'),'path':enum('/v1/executions/cancel','/v1/builds/quarantine'),'permitHash':H,'bodyHash':H,'nonce':H,'issuedAt':T,'expiresAt':T})
    D['safety']['allOf']=[{'if':{'properties':{'action':const(action)}},'then':{'properties':{'path':const(path)}}} for action,path in [('CANCEL_EXACT_COMMAND','/v1/executions/cancel'),('QUARANTINE_EXACT_OBLIGATION','/v1/builds/quarantine')]]
    D['observeInput']=obj({'nonce':H})
    available=obj({'kind':const('OBSERVATION_SCOPE'),'status':const('AVAILABLE'),'businessAuthority':const(False),'source':enum('CURRENT_REGISTERED','FROZEN_INTENT_TARGET'),'tenantId':I,'nodeId':I,'currentControlEpoch':I,'targetNodeEpoch':I,'targetDER':H,'currentTuple':ref('static'),'provenanceHash':H,'intentId':{'type':['string','null'],'maxLength':128},'method':const('POST'),'paths':array(enum('/v1/heartbeats','/v1/snapshots','/v1/roles/observe','/v1/executions/receipts')),'challenge':H,'issuedAt':T,'expiresAt':T,'diagnostic':enum('OBSERVE_ONLY','RECONCILE_ONLY')})
    available['allOf']=[{'if':{'properties':{'source':const('CURRENT_REGISTERED')}},'then':{'properties':{'intentId':const(None)}}},{'if':{'properties':{'source':const('FROZEN_INTENT_TARGET')}},'then':{'properties':{'intentId':I}}}]
    refused=obj({'kind':const('OBSERVATION_SCOPE'),'status':enum('AUTHORITY_UNAVAILABLE','SCOPE_DENIED','EXPIRED','UNKNOWN_SCOPE'),'businessAuthority':const(False),'reason':enum('INVALID_TRUST','EPOCH_UNAVAILABLE','NO_OBSERVER_GRANT','MISSING_PROTECTED_INTENT','UNKNOWN_CURRENT_TUPLE'),'nodeId':I,'observedAt':T})
    D['observationScope']={'oneOf':[available,refused]}
    D['roleConfig']=obj({'schemaVersion':const('saintvision-node-role-config:2'),'role':const('workspace-storage-ro-v1'),'operatorReleaseAnchorSha256':H,'operatorReleasePublicPath':const('/state/role-release-authority.pub'),'safetyAnchorSha256':H,'safetyPublicPath':const('/state/role-safety-authority.pub'),'contextId':I,'gateProtocol':const('saintvision-node-role-release:1'),'useProtocol':const('saintvision-node-role-use:1')})
    D['signedEnvelope']=obj({'kind':enum('APPROVAL','RELEASE','DELEGATION','GATE_CONTROL','GATE_ACK','DELIVERY_CHALLENGE','KEY_POSSESSION','KEY_DELIVERY_RECEIPT','ROLE_USE','SAFETY','CONTEXT_BUDGET'),'payloadBase64url':{'type':'string','minLength':1,'maxLength':65536,'pattern':'^[A-Za-z0-9_-]+'+END},'signatureHex128':{'type':'string','minLength':128,'maxLength':128,'pattern':'^[0-9a-f]{128}'+END}})
    D['displayLabel']={'type':'string','maxLength':128,'description':'Unicode code points, additionally <=512 strict UTF8 bytes; no NFC; no controls/surrogates'}
    clock=obj({'target':enum('HOST','GUEST'),'targetId':I,'contextId':I,'challenge':H,'clockOffsetMillis':{'type':'integer','minimum':-9007199254740991,'maximum':9007199254740991},'uncertaintyMillis':U,'syncSource':I,'method':const('AUTHENTICATED_CP_ROUNDTRIP_BOUND'),'producerId':I,'producerArtifactHash':H,'evidenceHash':H,'observedAt':T})
    D['clockMeasurement']=clock
    cap=D['capability'];cap['properties']['hostClock']=ref('clockMeasurement');cap['properties']['guestClock']=ref('clockMeasurement');cap['required']+=['hostClock','guestClock'];cap['properties']['vmSpecHash']=H;cap['required'].append('vmSpecHash')
    budget=D['budget'];budget['properties'].update({'cohortId':I,'vmSpecHash':H,'hostProbeHash':H,'guestProbeHash':H,'approvedSkewMillis':{'type':'integer','minimum':0,'maximum':30000},'nonce':H,'issuedAt':T});budget['required']=list(budget['properties'])
    return {'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:saintvision:proposal:fleet5-b-rev4','$defs':D,'description':'PROPOSED only. Strict UTF8/duplicate/float decoding and semantic signature/state/time checks are normative; JSON Schema alone does not reject lexical 2.0.'}


if __name__=='__main__':
    (E/'contract.schema.json').write_bytes((json.dumps(build(),indent=2)+'\n').encode())
