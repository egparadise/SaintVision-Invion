"""PUBLIC SYNTHETIC ALREADY-BOUND hypotheses, not real trust or certificates.

No key generation/signing/provider/OS call. Fake DER is deliberately not a
cryptographic fixture. Source and capsule values are constructed independently
of each untrusted test mutation; rebinding below requires explicit flags.
"""
from dataclasses import replace
import copy
import p02_rev3_model as m
from p02_rev2_schema import schema, PIN_MAP

CLASSIFICATION='SYNTHETIC_ALREADY_BOUND_NO_CRYPTO_PROVIDER_OR_RUNTIME_AUTHENTICATION'
ARTIFACT=b'SYNTHETIC_ARTIFACT_BYTES_NOT_AN_ARCHIVE_OR_BINARY'
SOURCE='b1'*20
SCOPE_ROWS=[dict(tenantId='synthetic-tenant',nodeId='synthetic-'+slot,recoveryEpoch='synthetic-epoch') for slot in ('PC2','PC4')]
GRAPH=b'{"syntheticGraph":true}'
PROOF_SLOTS=b'{"syntheticSlots":77}'
REGISTRATION=b'{"syntheticRegistration":"design-only"}\r\n'
NODE_KINDS={'synthetic-kind':'SYNTHETIC'}
SOURCE_CONSTANTS=dict(k1SourcePinSetSHA256=m.sha(b'SYNTHETIC_K1_SOURCE_PINS'),
    recipeDefinitionsSHA256=m.sha(b'SYNTHETIC_RECIPE_DEFINITIONS'),
    derivedDigestContractSHA256=m.sha(b'SYNTHETIC_DERIVED_DIGEST'),
    proofSlotRegistrySHA256=m.sha(PROOF_SLOTS),graphSHA256=m.sha(GRAPH),
    nodeKindsSHA256=m.sha(m.c2(NODE_KINDS)),designRegistrationSHA256=m.sha(REGISTRATION))

def _review(ordinal,sha,target,verdict,scope,reviewer):
    raw_scope=scope.encode()
    return dict(ordinal=ordinal,reviewSHA=sha,targetSHA=target,verdict=verdict,
        scopeId='synthetic-scope-'+str(ordinal),scopeUTF8Hex=raw_scope.hex(),
        scopeSHA256=m.sha(raw_scope),reviewerId=reviewer,reviewerSPKISHA256=('61' if ordinal==1 else '62')*32,
        rawReviewSHA256=m.sha(('SYNTHETIC ORIGINAL '+sha).encode()))

REVIEWS=[_review(1,'a2'*20,'a1'*20,'SYNTHETIC_K1_CODE_ACCEPT','Original bounded K1 scope','synthetic-reviewer-A'),
         _review(2,'b2'*20,SOURCE,'SYNTHETIC_ADAPTER_DELTA_ACCEPT','Original adapter delta scope','synthetic-reviewer-B')]
PARTS={'k1-core':m.sha(b'SYNTHETIC SAME K1 CODE BYTES'),'adapter':m.sha(b'SYNTHETIC CURRENT ADAPTER CODE')}
REVIEWED={REVIEWS[0]['reviewSHA']:{'k1-core':PARTS['k1-core']},REVIEWS[1]['reviewSHA']:{'adapter':PARTS['adapter']}}
# Independently provisioned symbolic policy constant, NOT derived from EFFECTIVE.
EXPECTED_EFFECTIVE_VERDICT='SYNTHETIC_ROOT_COVERAGE_ACCEPT'
EFFECTIVE=dict(publicationSHA='e2'*20,targetSourceSHA=SOURCE,scopeId='synthetic-effective-reviewed-source',verdict='SYNTHETIC_ROOT_COVERAGE_ACCEPT')
STATEMENT=dict(sourceSHA=SOURCE,sourceTreeSHA256=m.sha(m.c2(PARTS)),reviewSetSHA256=m.sha(m.c2(REVIEWS)),
    effective=EFFECTIVE,parts=[dict(partId=pid,reviewSHA=r['reviewSHA'],reviewTargetSHA=r['targetSHA'],
        reviewedBlobSHA256=PARTS[pid],currentBlobSHA256=PARTS[pid],relation=relation)
        for pid,r,relation in [('k1-core',REVIEWS[0],'BYTE_IDENTICAL'),('adapter',REVIEWS[1],'DIRECT')]])
COVERAGE=dict(purpose='root-effective-source-approval-candidate:1',authorityId='synthetic-root-approval-origin',
    evidenceRawSHA256=m.sha(b'SYNTHETIC AUTHENTICATED ROOT APPROVAL ENVELOPE'),statement=STATEMENT)
CI=[dict(runId=101,repository='synthetic/repo',headSHA=SOURCE,ref='synthetic/core-ref',event='workflow_dispatch',
    workflow='.github/workflows/core.yml',correlation='synthetic-core-one',attempt=1,conclusion='success',
    jobs=[dict(id=201,name='core',conclusion='success',steps=[dict(number=1,name='required-build',conclusion='success'),
        dict(number=2,name='required-test',conclusion='success'),dict(number=3,name='optional-native',conclusion='skipped')])]),
    dict(runId=102,repository='synthetic/repo',headSHA=SOURCE,ref='synthetic/docs-ref',event='workflow_dispatch',
    workflow='.github/workflows/docs.yml',correlation='synthetic-docs-two',attempt=2,conclusion='success',
    jobs=[dict(id=202,name='docs',conclusion='success',steps=[dict(number=1,name='required-docs',conclusion='success')])])]
REQUIRED=[[101,'core',1,'required-build'],[101,'core',2,'required-test'],[102,'docs',1,'required-docs']]
OPTIONAL=[[101,'core',3,'optional-native']]

def policy():
    members=[dict(slot=slot,scope=copy.deepcopy(sc),certificateDERHex=('a1' if slot=='PC2' else 'a2')*64,
        caRootDERHex='a3'*64) for slot,sc in zip(('PC2','PC4'),SCOPE_ROWS)]
    grants=[dict(role='node-leaf',authorityScopeC2Hex=m.c2(dict(**{'class':'NODE'},scope=sc)).hex(),
        publicKeyHex=key*32,notBefore=900,notAfter=(950 if index==0 else 1200))
        for index,(sc,key) in enumerate(zip(SCOPE_ROWS,('11','22')))]
    grants.append(dict(role='host-helper',authorityScopeC2Hex=m.c2(dict(**{'class':'COMPONENT'},component='synthetic&helper')).hex(),
        publicKeyHex='31'*32,notBefore=800,notAfter=1500))
    return dict(selector='synthetic_legacy_two',version='7',
        verifier=dict(id='saintvision-migrationverify-k1:1',sourceSHA=SOURCE,artifactSHA256=m.sha(b'SYNTHETIC EXECUTABLE'),
            reviewSHA=EFFECTIVE['publicationSHA'],ciRunIDs=[101,102]),
        contractPins=copy.deepcopy(PIN_MAP),grants=grants,cohortId='synthetic-legacy-two',members=members,
        graphHex=GRAPH.hex(),nodeKinds=copy.deepcopy(NODE_KINDS),proofSlotRegistryHex=PROOF_SLOTS.hex(),
        designRegistrationHex=REGISTRATION.hex(),semanticPins={k:v for k,v in SOURCE_CONSTANTS.items() if k!='designRegistrationSHA256'})

def fixture():
    p=policy();raw=m.canonical(p);comp=m.components(p)
    cohort=m.c2(dict(**{'class':'COHORT'},cohortId=p['cohortId'],members=SCOPE_ROWS))
    member_bindings=[dict(slot=x['slot'],scope=x['scope'],certificateSHA256=m.sha(m.unhex(x['certificateDERHex'])),
        caSHA256=m.sha(m.unhex(x['caRootDERHex'])),SPKISHA256=('81' if i==0 else '82')*32,
        publicKeyHex=('11' if i==0 else '22')*32) for i,x in enumerate(p['members'])]
    cap=dict(format=m.FORMAT,purpose=m.PURPOSE,selector='synthetic_legacy_two',scopeSHA256=m.sha(cohort),generation='synthetic-install-1',
        anchorVersion=1,keySPKI='93'*32,keyNotBefore=900,keyNotAfter=1200,approvedReviewScope=EFFECTIVE['scopeId'],
        primaryCI=dict(runId=102,jobId=202,jobName='docs'),sourceConstants=copy.deepcopy(SOURCE_CONSTANTS),
        memberBindings=member_bindings,sourceParts=copy.deepcopy(PARTS),reviewedParts=copy.deepcopy(REVIEWED),
        requiredParts=['k1-core','adapter'],requiredSteps=copy.deepcopy(REQUIRED),optionalSteps=copy.deepcopy(OPTIONAL),
        rootApprovalIdentity=COVERAGE['authorityId'],rootApprovalPurpose=COVERAGE['purpose'],
        approvedReviewOutcomes={r['reviewSHA']:r['verdict'] for r in REVIEWS},componentSHA256='71'*32,
        expectedUID=1000,expectedRootSHA256='72'*32,minimumRecordVersion=7,
        expectedEffectiveVerdict=EXPECTED_EFFECTIVE_VERDICT)
    props=schema('envelope')['properties']['body']['properties']['facts']['properties']
    facts={}
    for k,v in props.items():
        if v.get('type')=='boolean':facts[k]=False
        elif v.get('type')=='integer':facts[k]=303
        elif '{40}' in v.get('pattern',''):facts[k]='a1'*20
        elif '{64}' in v.get('pattern',''):facts[k]='a1'*32
        else:facts[k]='synthetic-'+k
    facts.update(comp,policyPayloadSHA256=m.sha(raw),sourceSHA=SOURCE,sourceTreeSHA256=STATEMENT['sourceTreeSHA256'],
        effectiveReviewSHA=EFFECTIVE['publicationSHA'],effectiveReviewTargetSHA=SOURCE,effectiveReviewScope=EFFECTIVE['scopeId'],
        effectiveReviewVerdict=EFFECTIVE['verdict'],reviewCoverageSHA256=m.sha(m.c2(STATEMENT)),
        rootChoiceSHA256=COVERAGE['evidenceRawSHA256'],sourceEquivalenceSHA256=m.sha(m.c2(STATEMENT['parts'])),
        artifactId=303,artifactZipSHA256=m.sha(ARTIFACT),artifactZipBytes=len(ARTIFACT),binarySHA256=p['verifier']['artifactSHA256'],
        binaryVCSRevision=SOURCE,binaryVCSModified=False,toolchain='synthetic-toolchain',
        installationSourceSHA=SOURCE,runningSourceSHA=SOURCE,sourcePublicationAnchorSHA256=m.sha(b'SYNTHETIC ORIGINAL SOURCE ANCHOR'),
        sourceAcquisitionSHA256=m.sha(b'SYNTHETIC ORIGINAL CODE ACQUISITION BEFORE REGISTRY'))
    for k in ('installationBinarySHA256','runningBinarySHA256'):facts[k]=facts['binarySHA256']
    facts['installationReceiptSHA256']=facts['runningReceiptSHA256']='c3'*32
    facts['runtimeLockSHA256']=facts['runningRuntimeLockSHA256']='d4'*32
    facts['linkedClosureSHA256']=facts['runningLinkedClosureSHA256']='e5'*32
    h5=dict(purpose='running-integration-measurement',componentSHA256=cap['componentSHA256'],executableSHA256=facts['binarySHA256'],
        sourceSHA=SOURCE,receiptSHA256=facts['installationReceiptSHA256'],runtimeLockSHA256=facts['runtimeLockSHA256'],
        linkedClosureSHA256=facts['linkedClosureSHA256'],pid=123,startGeneration='synthetic-pid-generation-1',uid=1000,
        rootIdentitySHA256=cap['expectedRootSHA256'],observedAt=995,expiresAt=1100,proofNonce='synthetic-H5-1')
    facts[m.ECHO]=m.sha(m.canonical(h5))
    e=dict(body=dict(format=m.FORMAT,purpose=m.PURPOSE,selector=cap['selector'],scopeSHA256=cap['scopeSHA256'],
        capsuleSHA256=m.sha(m.canonical(cap)),provisioningGeneration=cap['generation'],anchorVersion=1,recordVersion=7,
        requestBindingSHA256='92'*32,issuedAt=990,validUntil=1100,facts=facts,ciRuns=copy.deepcopy(CI),reviews=copy.deepcopy(REVIEWS)),
        signer=dict(keySPKISHA256=cap['keySPKI']),signatureHex='94'*64)
    life=dict(status='ACTIVE',keyStatus='ACTIVE',sourceStatus='ACTIVE',coverageStatus='ACTIVE',receiptStatus='ACTIVE',
        currentVersion=7,currentRecordIdentity=m.record_identity(e),floor=7,generation=cap['generation'],capsuleSHA256=m.sha(m.canonical(cap)),
        checkedAt=995,expiresAt=1100,reviews={r['reviewSHA']:'ACTIVE' for r in REVIEWS},
        grants={m.grant_registration(g,sc):'ACTIVE' for g,sc in zip(p['grants'],[m.strict_json(m.unhex(g['authorityScopeC2Hex']),65536,65536,False,True) for g in p['grants']])},
        certificates={m.sha(m.unhex(x['certificateDERHex'])):'ACTIVE' for x in p['members']})
    ticket=dict(purpose='p02-read-ticket-candidate:2',id='synthetic-ticket-1',issuedAt=985,expiresAt=1100,
        selector=cap['selector'],scopeSHA256=cap['scopeSHA256'],capsuleSHA256=m.sha(m.canonical(cap)),generation=cap['generation'],
        currentVersion=7,currentRecordIdentity=life['currentRecordIdentity'])
    a=m.BoundInputs(capsule=m.canonical(cap),source_facts=m.canonical({k:v for k,v in facts.items() if k!=m.ECHO}),
        ci=m.canonical(CI),reviews=m.canonical(REVIEWS),coverage=m.canonical(COVERAGE),lifecycle=m.canonical(life),
        ticket=m.canonical(ticket),h5=m.canonical(h5),clock=m.canonical(dict(lower=1000,upper=1001)),
        signatures=frozenset(),v0=b'synthetic-readback-1',v1=b'synthetic-readback-1')
    e['body']['requestBindingSHA256']=m.sha(m.c2(m.request_projection(a)))
    a=replace(a,signatures=frozenset(((m.sha(m.projection(e)),e['signatureHex'],cap['keySPKI']),)))
    return e,p,ARTIFACT,a

def seal(e,p,artifact,a,*,bind_payload=False,source_fields=(),new_head=False,new_request=False,
         bind_ci=False,bind_reviews=False,bind_coverage=False,bind_grant_status=False,bind_member_status=False):
    """Explicit symbolic rebindings for adversarial hypotheses, never production.

    Expected selectors, scopes, primary tuples and approved scope are NEVER
    learned from the response. Callers deliberately replace private fixture
    snapshots when modelling an independently authenticated inconsistent source.
    """
    raw=p if type(p) is bytes else m.canonical(p)
    src=m.strict_json(a.source_facts);cap=m.strict_json(a.capsule);life=m.strict_json(a.lifecycle)
    if bind_payload:
        e['body']['facts']['policyPayloadSHA256']=m.sha(raw)
        src['policyPayloadSHA256']=m.sha(raw)
    for field in source_fields:src[field]=e['body']['facts'][field]
    a=replace(a,source_facts=m.canonical(src))
    if bind_ci:a=replace(a,ci=m.canonical(e['body']['ciRuns']))
    if bind_reviews:a=replace(a,reviews=m.canonical(e['body']['reviews']))
    if bind_coverage:
        cov=m.strict_json(a.coverage);s=cov['statement'];f=e['body']['facts']
        updates=dict(reviewCoverageSHA256=m.sha(m.c2(s)),rootChoiceSHA256=cov['evidenceRawSHA256'],sourceEquivalenceSHA256=m.sha(m.c2(s['parts'])))
        f.update(updates);src.update(updates);a=replace(a,source_facts=m.canonical(src))
    if bind_grant_status:
        pp=m.strict_json(raw,m.MAX_POLICY,m.MAX_POLICY)
        life['grants']={m.grant_registration(g,m.strict_json(m.unhex(g['authorityScopeC2Hex']),65536,65536,False,True)):'ACTIVE' for g in pp['grants']}
    if bind_member_status:
        pp=m.strict_json(raw,m.MAX_POLICY,m.MAX_POLICY)
        life['certificates']={m.sha(m.unhex(x['certificateDERHex'])):'ACTIVE' for x in pp['members']}
    if new_head:
        life.update(currentVersion=e['body']['recordVersion'],currentRecordIdentity=m.record_identity(e),
                    generation=cap['generation'],capsuleSHA256=m.sha(a.capsule))
    a=replace(a,lifecycle=m.canonical(life))
    if new_request:
        t=m.strict_json(a.ticket)
        t.update(selector=cap['selector'],scopeSHA256=cap['scopeSHA256'],capsuleSHA256=m.sha(a.capsule),generation=cap['generation'],
                 currentVersion=life['currentVersion'],currentRecordIdentity=life['currentRecordIdentity'])
        a=replace(a,ticket=m.canonical(t))
        e['body']['facts'][m.ECHO]=m.sha(a.h5)
        e['body']['requestBindingSHA256']=m.sha(m.c2(m.request_projection(a)))
    a=replace(a,signatures=frozenset(((m.sha(m.projection(e)),e['signatureHex'],cap['keySPKI']),)))
    return m.canonical(e),raw,artifact,a
