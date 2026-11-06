"""Closed proposed CP records/B-only folder proof; no new plain Node wire."""
from copy import deepcopy
import json
from pathlib import Path
from catalog import IO
from io_contract import EFFECT,READ_ONLY,SAFETY,SIDE_EFFECT

E=Path(__file__).resolve().parent
H={'type':'string','pattern':'^[0-9a-f]{64}$(?![\\s\\S])'}
I={'type':'string','minLength':1,'maxLength':128,'pattern':'^[A-Za-z0-9][A-Za-z0-9_.:-]*$(?![\\s\\S])'}
T={'type':'integer','minimum':1,'maximum':9007199254740991}
U={'type':'integer','minimum':0,'maximum':9007199254740991}
DEC={'type':'string','pattern':'^(0|[1-9][0-9]{0,19})$(?![\\s\\S])'}


def obj(p):return {'type':'object','additionalProperties':False,'required':list(p),'properties':p}
def ref(k):return {'$ref':'#/$defs/'+k}
def nullable(s):return {'oneOf':[s,{'type':'null'}]}


def build():
    d=json.loads((E.parent/'fleet5-b-contract-rev5-20261106-codex/contract.schema.json').read_bytes())
    defs=d['$defs'];defs.pop('lineageTombstone',None)
    defs['signedEnvelope']['properties']['kind']['enum']=[x for x in defs['signedEnvelope']['properties']['kind']['enum'] if x!='LINEAGE_TOMBSTONE']+['FOLDER_ROOT_OBSERVATION']
    defs['scope']=obj({'tenantId':I,'nodeId':I,'epoch':I})
    defs['ioFootprint']=obj({'known':{'type':'boolean'},'rows':{'type':'array','maxItems':1024,'items':obj({'rank':U,'table':I,'key':{'type':'string','minLength':1,'maxLength':512},'mode':{'enum':['SHARE','UPDATE']}})}})
    defs['ioBinding']=obj({'scope':ref('scope'),'operationId':I,'attemptId':I,'effectClass':{'enum':[READ_ONLY,SAFETY,SIDE_EFFECT]},'footprint':ref('ioFootprint'),'kind':{'enum':[r[0] for r in IO]},
        'method':{'enum':['POST','LOCAL_READ','ADAPTER_EXECUTE','B_PREFLIGHT_OBSERVE']},'rawPath':{'type':'string','minLength':1,'maxLength':1024},
        'channelVersion':T,'nodeDER':H,'targetBindingSHA':H,'ownerBindingSHA':nullable(H),'bodySHA':H,'existingPermitOrApprovalSHA':H,'nonce':H,'runId':nullable(I),'generation':I,'claimBindingSHA':nullable(H),'parentHandleHash':nullable(H)})
    defs['ioBinding']['allOf']=[{'if':{'properties':{'kind':{'enum':['EXECUTE','CANCEL','RECEIPT_OBSERVE','BUILD_DISPATCH','BUILD_CLEANUP_READ','TERMINAL_FRAME']}}},
        'then':{'properties':{'runId':I,'claimBindingSHA':H,'ownerBindingSHA':H}}}]
    defs['ioBinding']['allOf'] += [{'if':{'properties':{'kind':{'const':k}}},'then':{'properties':{'effectClass':{'const':v}}}} for k,v in EFFECT.items()]
    defs['ioBinding']['allOf'] += [{'if':{'properties':{'kind':{'enum':['TERMINAL_FRAME','OBJECT_READ','BUILD_CLEANUP_READ','RECEIPT_OBSERVE','CANCEL']}}},'then':{'properties':{'parentHandleHash':H}}}]
    defs['ioBinding']['allOf'] += [{'if':{'properties':{'kind':{'const':r[0]}}},'then':{'properties':{'method':{'const':r[3]},'rawPath':{'const':r[4]}}}} for r in IO]
    defs['ioObligation']=obj({'binding':ref('ioBinding'),'bindingHash':H,
        'state':{'enum':['PENDING_IO','CONFIRMED_OUTCOME','UNCERTAIN','SETTLED_PROTECTED','NO_EFFECT','NO_EFFECT_ABANDONED']},
        'completionService':I,'completionIncarnation':I,'completionCapabilityHash':H,
        'verifiedOutcomeHash':nullable(H),'causalErrorHash':nullable(H),'protectedRecoveryHash':nullable(H)})
    defs['completionAuthority']=obj({'serviceId':I,'incarnation':I,'state':{'enum':['ACTIVE','FENCED_UNKNOWN','RETIRED']},
        'durableSequence':U,'lastErrorHash':nullable(H)})
    defs['denialFact']=obj({'scope':ref('scope'),'factKind':{'enum':['DRAIN','QUARANTINE','RETIRE']},
        'causeOperationId':I,'present':{'type':'boolean'},'evidenceHash':H,'protectedClearHash':nullable(H)})
    defs['cpTombstoneRecord']=obj({'scope':ref('scope'),'rootLineageID':H,'revokedAncestorHash':H,
        'authenticatedPrincipal':{'enum':['sv_b_operator','sv_b_safety']},'causalEvidenceHash':H,
        'auditRef':I,'anchorVersion':T,'recordedAt':T})
    defs['signingIntent']=obj({'intentId':I,'scope':ref('scope'),'authenticatedService':I,
        'kind':I,'purpose':I,'domain':{'type':'string','minLength':1,'maxLength':128},'bodyHash':H,
        'authorityVersion':T,'lineageVersion':T,'authorityFootprintHash':H,
        'state':{'enum':['PREPARED','HSM_UNPUBLISHED','ISSUED','DISCARDED','HOLD']},
        'issuedSignatureHash':nullable(H),'issuedAt':T,'expiresAt':T})
    defs['revocationOutbox']=obj({'outboxId':I,'scope':ref('scope'),'rootLineageID':H,'ancestorHash':H,
        'anchorVersion':T,'targetGateId':nullable(I),'targetReleaseHash':nullable(H),
        'state':{'enum':['PENDING','PREPARED','SIGNED_UNPUBLISHED','READY_TO_DISPATCH','DISPATCHED_AWAIT_ACK','ACK_RECORDED','UNKNOWN_TARGET_HOLD','RETRY_SAME_COMMAND','EXPIRED_HOLD','RECONCILIATION_REQUIRED']},
        'commandHash':nullable(H),'ackHash':nullable(H),'causalEvidenceHash':H})
    root=obj({'device':DEC,'inode':DEC,'mountId':DEC,'mountNamespaceId':DEC,'mountIdentityHash':H})
    defs['folderRootObservation']=obj({'kind':{'const':'FOLDER_ROOT_OBSERVATION'},'stage':{'const':'PREFLIGHT_ROOT_IDENTITY'},
        'purpose':{'const':'B_PREFLIGHT_FOLDER_ROOT'},'businessAuthority':{'const':False},'scope':ref('scope'),
        'contributionId':I,'normalizedPath':{'type':'string','minLength':1,'maxLength':4096},'heldRoot':root,
        'generation':I,'channelVersion':T,'nodeDER':H,'policyR':T,'policyHash':H,'ownerConsentVersion':T,
        'observePermitHash':H,'challenge':H,'observedAt':T,'expiresAt':T})
    defs['folderRootResponse']={'oneOf':[obj({'status':{'const':'AVAILABLE'},'observation':ref('folderRootObservation')}),
        obj({'status':{'enum':['SCOPE_DENIED','ROOT_UNKNOWN','PATH_UNSAFE','EXPIRED','CHANNEL_MISMATCH','OWNER_UNAVAILABLE']},
        'businessAuthority':{'const':False},'scope':ref('scope'),'challenge':H,'observedAt':T,'reason':I})]}
    d['$id']='urn:saintvision:proposal:fleet5-b-rev7'
    d['description']='PROPOSED SCHEMA/STATIC/SYMBOLIC ONLY. Unsigned CP tombstones, CP-only IO handles/intents; new folder observation B-only; plain floor2 wire unchanged. Strict decoder, C2, actual authority and temporal predicates remain required.'
    return deepcopy(d)


if __name__=='__main__':(E/'contract.schema.json').write_bytes((json.dumps(build(),indent=2)+'\n').encode())
