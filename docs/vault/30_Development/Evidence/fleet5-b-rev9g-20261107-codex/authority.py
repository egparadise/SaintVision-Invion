"""Rev6 proposed mediation: no SQL/permissions/keys/Node changes are executed."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from catalog import build_catalog
from rank_contract import CATALOG,procedure_locks,check as check_ranks

E=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('immutable_rev5_authority',E.parent/'fleet5-b-contract-rev5-20261106-codex/authority.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
OP,VER,ISS,RUN,DEL,SAFE,BUD,USER,BOOT=[getattr(prior,n) for n in ('OP','VER','ISS','RUN','DEL','SAFE','BUD','USER','BOOT')]
OWNER=prior.OWNER
REV='sv_b_revocation_dispatcher'
SIGN='sv_b_signing_service'
DOMAINS=deepcopy(prior.DOMAINS);DOMAINS.pop('LINEAGE_TOMBSTONE',None)
DOMAINS['FOLDER_ROOT_OBSERVATION']=('saintvision/node-folder-root-observation/v1','REGISTERED_NODE_LEAF',['B_PREFLIGHT_FOLDER_ROOT'])


def build():
    d=deepcopy(prior.build());d['version']='fleet5-b-authority-rev9b-t1:1';p=d['procedures']
    p.pop('b_register_node_safety_obligation');p.pop('b_settle_node_safety_obligation')
    def add(name,roles,effects,predicate,protected=False,**extra):
        p[name]=dict(owner=OWNER,execute=roles,effects={t:dict(verb=v,columns=cols) for t,(v,cols) in effects.items()},
            searchPath='pg_catalog',rowSecurity='on/FORCE where applicable',arbitrarySqlOrTableParameter=False,
            protected=protected,transitionPredicate=predicate,**extra)
    obligation='inv.node_role_safety_obligations';anchor='inv.node_role_authority_anchors';lineage='inv.node_role_lineage_anchors'
    add('b_register_io_obligation',[RUN,VER,SAFE],{obligation:('INSERT',['tenant_id','node_id','epoch','operation_id','kind','body_sha','method','raw_path','nonce','run_id','generation','claim_binding_hash','parent_handle_ref','completion_service','completion_incarnation','completion_capability_hash','state']),anchor:('UPDATE',['version'])},
        'same scoped current authority/profile and exact immutable existing request/permit bytes; registration COMMIT proven before IO. PENDING_IO. Opaque handle limited to this exact original operation; no caller-supplied operation-id admission escape',
        denyOnly=True,mayReduceDenial=False)
    add('b_mark_io_uncertain',[RUN,VER,SAFE],{obligation:('UPDATE',['state','causal_error_hash','completion_disposition']),anchor:('UPDATE',['version'])},
        'PENDING_IO->UNCERTAIN only; poison completion capability BEFORE handling failure. DB error leaves PENDING_IO and fenced/poisoned completion authority, never ordinary confirmation after a swallowed quarantine failure',denyOnly=True,mayReduceDenial=False)
    catalog=build_catalog()
    for item in catalog['ioKinds']:
        name=item['closureProcedure']
        if name in ('b_record_gate_ack','b_append_folder_root_observation','b_record_reconcile_observation'):continue
        role=item['closurePrincipal']
        add(name,[role],{obligation:('UPDATE',['state','verified_receipt_hash','completion_disposition']),anchor:('UPDATE',['version'])},
            'PENDING_IO->CONFIRMED_OUTCOME only with live exact one-use verifier completion capability/incarnation and independently verified original typed request/receipt/nonce/run/claim binding; NEVER from UNCERTAIN/poisoned/unknown authority',
            originalAtomicBoundary=item['atomicBoundary'],outcomeDoesNotFreeClaims=True,
            projection='removes ONLY IO-ambiguity denial; ACTIVE keeps workload/lease/claim; terminal cleanup release only by original fully validated kernel receipt path in SAME transaction')
    p['b_record_gate_ack']['effects'][obligation]=dict(verb='UPDATE',columns=['state','verified_receipt_hash','completion_disposition'])
    p['b_record_gate_ack']['effects'][anchor]=dict(verb='UPDATE',columns=['version'])
    p['b_record_gate_ack']['transitionPredicate']='exact durable Node ACK + committed CP IO handle, independently verified same original command/nonce/body/channel/generation; ACK append and PENDING_IO->CONFIRMED_OUTCOME in SAME transaction; normal verifier capability required, never settle UNCERTAIN'
    add('b_settle_uncertain_io',[OP],{obligation:('UPDATE',['state','protected_recovery_ref','physical_proof_hash']),anchor:('UPDATE',['version'])},
        'UNCERTAIN or PENDING_IO with proven lost/fenced completion authority ->SETTLED_PROTECTED only with explicit exact operator recovery+independent physical proof; no ordinary runtime/verifier, no proofless OP, no node containment clear',protected=True,mayReduceDenial=True)
    facts='inv.node_role_denial_facts'
    for name in ('b_raise_node_quarantine','b_set_node_containment','b_clear_node_containment','b_retire_public_node'):
        p[name]['effects'][facts]=dict(verb='INSERT_OR_UPDATE',columns=['tenant_id','node_id','epoch','fact_kind','cause_operation_id','present','protected_clear_ref'])
        p[name]['effects'][anchor]=dict(verb='UPDATE',columns=['version'])
    p['b_raise_node_quarantine']['transitionPredicate']='add QUARANTINE fact from exact current causal operation; never remove DRAIN/RETIRE/other fact. inv.nodes.status is derived projection only; lost EXECUTE cannot settle obligation.'
    p['b_clear_node_containment']['transitionPredicate']='protected exact-fact clear with recovery+physical proof; removes only named quarantine OR draining fact and cause, never other fact or retirement. Recompute projection, retain preexisting drain.'
    p['b_set_node_containment']['transitionPredicate']='add exact DRAIN or QUARANTINE fact, never erase another fact; protected typed operator/safety scope and evidence'
    p['b_retire_public_node']['transitionPredicate']='add terminal RETIRE fact; no ordinary clear/re-enrollment bypass; retain identity/catalogue'
    p['b_commit_node_observation']['transitionPredicate']='liveness/sequence/time only. Derived inv/public projection never removes persistent DRAIN/QUARANTINE/RETIRE/obligation facts.'
    p['b_public_node_heartbeat']['transitionPredicate']='strictly advancing sequence/time, liveness lost->active only; derive status from persistent facts, never change certificate or denial facts'
    p['b_activate_owner_contribution']['transitionPredicate']='ACTUAL PLAIN: same authenticated registered owner, not revoked ->active; no Node confirmation prerequisite, no project grade/operator impersonation, no B admission'
    p['b_activate_owner_contribution']['requiresNodeConfirmation']=False
    p['b_revoke_approval_lineage']['effects'][lineage]=dict(verb='UPDATE',columns=['version','revocation_version'])
    p['b_revoke_approval_lineage']['effects']['inv.node_role_revocation_outbox']=dict(verb='INSERT',columns=['tenant_id','node_id','epoch','root_lineage_id','ancestor_hash','authority_version','target_gate','target_release','state'])
    p['b_revoke_approval_lineage']['transitionPredicate']='protected OP/SAFE + causal evidence/audit and immutable lineage keys; unsigned authoritative DB tombstone, SAME lineage anchor UPDATE serializes every issuer and revoke; increment version and append INVALIDATE outbox in same transaction'
    p['b_revoke_approval_lineage']['unsignedCPRecord']=True
    add('b_prepare_signature',[SIGN],{'inv.node_role_signing_intents':('INSERT',['intent_id','authenticated_service','purpose','domain','exact_body_hash','scope_hash','authority_version','lineage_version','state'])},
        'fixed protected authority read inside signing SERVICE; complete chain/ancestors/tombstones/approved tuple/epoch/fence/expiry; caller booleans/labels not authority. Prepare intent only, returns no signature',protected=True)
    # Delivery controller/SAFE restricted service calls do NOT gain approval APIs.
    p['b_prepare_signature']['protected']=True;p['b_prepare_signature']['servicePurposePolicy']='installed authenticated caller purpose table, not unrestricted OP impersonation'
    add('b_publish_signature',[SIGN],{'inv.node_role_signing_intents':('UPDATE',['state','issued_signature_hash','publication_version'])},
        'network/HSM signature held private outside DB transaction; conditional issuance commit rereads identical authority/lineage anchor versions + full current predicate BEFORE exposing signature. Revoke advances SAME anchor; stale/unknown denies and discards unpublished material',
        protected=True,servicePurposePolicy='same authenticated installed caller/intent/body; only original valid issued bytes may replay, no new timestamp')
    add('b_append_folder_root_observation',[VER],{'inv.node_role_folder_root_observations':('INSERT',['tenant_id','node_id','epoch','contribution_id','signed_observation','challenge_ref','owner_consent_version','observed_at','expires_at'])},
        'B-only new signed FolderRootObservation current Node leaf/domain/purpose; exact authorized normalized path and held root dev/inode+mount identity, generation/epoch/shared C+DER/policyR+hash/challenge/time/expiry; refusal no eligible payload',
        grantsBAdmission=False,businessAuthority=False)
    p['b_approve_readonly_contribution_root']['transitionPredicate']='ADDITIONAL B-only protected approval: fresh authenticated FolderRootObservation + exact ACTIVE current owner consent/root/path/C+DER/generation/epoch/R/policy bytes; preflight establishes root identity, never future installed RO mount. Postinstall mount proof separately mandatory before business.'
    p['b_approve_readonly_contribution_root']['effects']['inv.node_role_folder_root_observations']=dict(verb='UPDATE',columns=['consumed_by_approval'])
    for row in catalog['plainReaders']:
        add(row['replacement'],[RUN,VER],{},row['predicate']+'; '+row['purpose'],readOnly=True,
            scopedObligationPredicate=True,sourceReader=row['id'])
    for row in catalog['newBReaders']:
        add(row['replacement'],[OP,VER,RUN,ISS,DEL,SAFE,REV],{},row['purpose']+'; installed service binding and purpose selects read only scope; current DB truth, never caller flags',readOnly=True)
        if row['caller'].startswith('signing_service.'):
            p[row['replacement']]['execute']=[SIGN]
    add('b_read_observe_reconcile_scope',[OP,VER,RUN,SAFE,REV],{},
        'existing authenticated tenant/Node/current epoch or exact protected prior-operation/frozen-intent target; available under business denial, no new workload/admission/use key or contribution writeback',readOnly=True)
    # Explicit immutable anchors: protected migration/bootstrap only; version writes
    # occur via named procedures above, never runtime direct DML.
    add('b_bootstrap_authority_anchors',[OP],{anchor:('INSERT',['tenant_id','node_id','epoch','profile','version']),lineage:('INSERT',['tenant_id','node_id','epoch','root_lineage_id','version'])},
        'protected offline/backfill or approved initial provisioning only; exact existing identity/epoch, no B identity bypass; missing/ambiguous prior denial history HOLD for reconciliation',protected=True)
    add('b_record_reconcile_observation',[VER,SAFE],{'inv.node_role_reconcile_evidence':('INSERT',['tenant_id','node_id','epoch','operation_id','typed_observation_hash'])},
        'authenticated observe/safety/prior operation only; evidence append cannot settle UNCERTAIN or clear facts',grantsBAdmission=False)
    d['tables']={}
    for name,proc in p.items():
        proc['lockList']=procedure_locks(name,proc['effects'])
        proc['lockScopeDiscovery']='complete persisted tenant/Node/epoch/lineage/operation/resource set BEFORE locks; late earlier-rank abort/replan without effects; no DB locks across HSM/network IO'
        for table,effect in proc['effects'].items():d['tables'].setdefault(table,[]).append(dict(procedure=name,**effect))
    d['tables'].setdefault('inv.control_epoch',[])
    d['canonicalRanks']=CATALOG
    for name,contract in d['lockOnlyProcedures'].items():
        contract.pop('canonicalOrder',None)
        contract['lockList']=procedure_locks(name,{})
        contract['canonicalRankCatalog']='rank_contract.CATALOG (same numeric table/mode/key catalog as source plans)'
        contract['columnsWritten']=[]
    d['signaturePurposes']={k:dict(domain=a,signer=b,purposes=c) for k,(a,b,c) in DOMAINS.items()}
    d['signingService']['installedCallerPolicy'].pop(OP,None)
    d['signingService']['installedCallerPolicy'][OP]=['APPROVAL','RELEASE','DELEGATION','GATE_CONTROL_ARM','GATE_CONTROL_INVALIDATE']
    d['signingService']['installedCallerPolicy'][SAFE]=['GATE_CONTROL_INVALIDATE_FROM_AUTHORITATIVE_OUTBOX']
    d['signingService']['installedCallerPolicy'][REV]=['GATE_CONTROL_INVALIDATE_FROM_AUTHORITATIVE_OUTBOX']
    d['signingService']['authorityRead']='fixed authenticated protected SD read, full chain/tombstones/current tuple/fence/epoch/expiry in SERVICE; prepared intent version + conditional publication before exposure'
    d['signingService']['networkIO']='outside DB transaction, unpublished material stays signing-service private; no raw operator key to caller'
    d['signingService']['tombstones']='UNSIGNED CP DB records; no LINEAGE_TOMBSTONE wire/domain or unpopulated Node knowledge guarantee'
    d['principals'][REV]='installed protected dispatcher: ONLY exact INVALIDATE from authoritative tombstone/current target outbox; cannot ARM/RELEASE/DELEGATE/approve'
    d['principals'][SIGN]='private protected signing-service DB pool; fixed authority reads/intents/conditional publication only; server-verified installed TLS caller/purpose binding, not a client role string or GUC. HSM/network outside DB locks.'
    d['orthogonalDenials']={'facts':['DRAIN','QUARANTINE','RETIRE'],'obligations':['PENDING_IO','UNCERTAIN'],
        'projection':'retired if RETIRE, else quarantined if QUARANTINE, else draining if DRAIN, else ordinary liveness. Projection never deletes facts; public status uses existing enum-compatible draining for quarantine.',
        'clear':'protected clear removes only exact named fact/cause with proof; original drain survives quarantine+clear'}
    d['obligationLifecycle']={'key':['tenant_id','node_id','epoch','operation_id'],
        'edges':{'PENDING_IO':['CONFIRMED_OUTCOME','UNCERTAIN'],'UNCERTAIN':['SETTLED_PROTECTED']},
        'specialLostAuthority':'PENDING_IO with proven fenced/lost verifier completion authority may settle ONLY via explicit protected recovery with physical proof',
        'ordinaryClose':'independently verified exact typed outcome + live one-use private verifier capability/incarnation, same original receipt/evidence transaction',
        'claims':'CONFIRMED_OUTCOME removes only IO ambiguity; ACTIVE never releases. Original terminal kernel receipt validation alone permits release.',
        'noNewPlainWire':True}
    from io_contract import EFFECT,RECOVERY,READER_PURPOSE
    io_columns=['effect_class','attempt_id','authority_footprint']
    p['b_register_io_obligation']['effects'][obligation]['columns']+=io_columns
    for name in ['b_register_io_obligation','b_mark_io_uncertain']+list({r['closureProcedure'] for r in catalog['ioKinds']}):
        if name in p:
            p[name]['effectClasses']=EFFECT
            p[name]['securityVersionRule']='Mere IO ledger/attempt/evidence writes never bump Node/lineage/signing authority versions. Actual containment/revocation/identity/fence/config/consent/overlapping claim changes bump their exact relevant security versions in the ORIGINAL atomic transaction.'
            # Version increments are conditional security effects, not IO ledger writes.
            p[name]['effects'].pop(anchor,None)
    p['b_register_io_obligation']['transitionPredicate']='closed handler/request-derived effectClass and immutable original scope/attempt/parent/DB footprint; register COMMIT before IO; READ_ONLY no denial, SIDE_EFFECT known PENDING intersection only, side uncertainty same-scope Node-wide, SAFETY exact causal target; continuation uses exact prior claim/current lease/purpose, DRAIN allowed for actual claimed terminal'
    p['b_mark_io_uncertain']['transitionPredicate']='poison only affected operation/attempt/capability incarnation first; READ_ONLY may ordinary NO_EFFECT_ABANDONED; side/safety PENDING->UNCERTAIN, failed persistence PENDING with private capability death; never fence unrelated healthy Node capabilities unless actual whole process/trust loss'
    add('b_abandon_read_io',[VER,RECOVERY],{obligation:('UPDATE',['state','verified_receipt_hash','completion_disposition'])},'closed READ_ONLY only PENDING->NO_EFFECT_ABANDONED; no authority refresh, no claim/fact clear, no signature version bump')
    add('b_abort_never_invoked_io',[VER],{obligation:('UPDATE',['state','completion_disposition'])},'atomic original private capability+dispatcher state NOT_INVOKED CAS to ABORTED and NO_EFFECT; no transport timeout/not-sent flag as proof')
    add('b_reconcile_idempotent_safety_io',[RECOVERY],{obligation:('UPDATE',['state','verified_receipt_hash','completion_disposition'])},'fresh separate installed RECOVERY_OBSERVATION verifier; current exact command hash/target/nonce/identity/epoch/generation and independently verified durable ACK or authenticated causal readback; only matched PENDING/UNCERTAIN safety closes, no claim/fact/gate advance without original consumer',protected=True)
    d['principals'][RECOVERY]='private installed purpose-restricted reconciliation verifier; current scoped read + exact safety ACK only, never reconstruct original poisoned capability or execute/ARM'
    for r in catalog['plainReaders']:p[r['replacement']]['transitionPredicate']=r['predicate']+'; '+r['intersectionRule']
    d['orthogonalDenials']['obligations']={'READ_ONLY':'none','SIDE_EFFECT_PENDING':'DB footprint conflicts only; unknown footprint conservative Node-wide for that operation','SIDE_EFFECT_UNCERTAIN':'same tenant/Node/current epoch Node-wide','IDEMPOTENT_SAFETY':'exact documented causal target, recovery reads remain possible'}
    d['obligationLifecycle']={'effectClasses':EFFECT,'READ_ONLY':'register -> verified confirmation or ordinary NO_EFFECT_ABANDONED; no ledger-only authority versions',
       'SIDE_EFFECT':'PENDING ordinary exact typed confirmation or atomic never-invoked NO_EFFECT; UNCERTAIN/dead capability protected physical/quiescence recovery only',
       'IDEMPOTENT_SAFETY':'PENDING or UNCERTAIN fresh protected typed exact causal ACK/readback verifier may close; no replay of poisoned original completion authority',
       'completionFence':'affected operation/attempt/capability only; actual process restart loses all volatile LIVE caps and class-specific recovery applies',
       'claims':'original exact terminal kernel/physical receipt consumer only; ACTIVE retains; safety ACK alone never frees', 'noNewPlainWire':True}
    d['authorityVersionClasses']={'bookkeeping':['IO ledger attempt','observation evidence append'],
       'security':['epoch/fence','Node/cohort/config','owner consent','claim/resource footprint','role/current','lineage/revocation'],
       'signaturePublication':'fixed relevant versions + exact authority footprint/predicate under merged locks; reads do not starve; actual overlapping security changes invalidate'}
    d['authorityVersionStorage']={'table':'inv.node_role_authority_anchors','proposedColumn':'scoped_versions jsonb',
       'key':'closed authority kind + complete canonical DB-discovered key; fixed typed procedures only, no caller arbitrary map/keys',
       'version':'monotonic C2-safe integer <=9007199254740991, retained retired-key version tombstones through epoch; overflow/missing/corrupt HOLD, no ABA reset',
       'securityEffects':'exact Node/cohort/fence/config/consent/claim/role/lineage changes increment their relevant entries in SAME original transaction; heartbeat bookkeeping/no-change does not',
       'publication':'signer-selected version vector/footprint and full authority predicate under merged locks before exposure; unrelated IO ledger never increments; shared global trust failure still fail-closed'}
    for name,proc in p.items():
        if name not in ('b_register_io_obligation','b_mark_io_uncertain','b_abandon_read_io','b_abort_never_invoked_io','b_reconcile_idempotent_safety_io') and any(t in ('inv.nodes','public.nodes','inv.node_channels','public.storage_contributions','inv.node_role_denial_facts','inv.node_role_current','inv.node_role_lineage_tombstones','inv.resource_leases','inv.resource_claims','inv.runs') for t in proc['effects']):
            proc['effects'].setdefault(anchor,dict(verb='UPDATE',columns=[]))['columns']=sorted(set(proc['effects'].get(anchor,{}).get('columns',[]))|{'scoped_versions'})
            proc['versionMapKeysDerivedByFixedProcedure']=True
            proc['securityVersionEffects']='fixed relevant entries in anchor.scoped_versions only when actual authority changes, atomic original effects; no generic runtime flag/JSON map accepted'
        proc['lockList']=procedure_locks(name,proc['effects'])
    d['tables']={}
    for name,proc in p.items():
        for table,effect in proc['effects'].items():d['tables'].setdefault(table,[]).append(dict(procedure=name,**effect))
    d['tables'].setdefault('inv.control_epoch',[])
    from io_contract import CONTINUATION_POLICY
    d['continuationPolicy']=deepcopy(CONTINUATION_POLICY)
    d['internalErrorClasses']=['MISSING_RESOURCE_SCOPE','AUTH_SCOPE_DENIED','AUTHENTICATION_EXPIRED','CHANNEL_CHANGED','PARENT_BINDING_MISMATCH','PARENT_UNKNOWN_PROTECTED_ONLY','DEAD_COMPLETION_CAPABILITY','ORIGINAL_RECEIPT_MISMATCH']
    p['b_register_io_obligation']['perKindContinuationPolicy']=deepcopy(CONTINUATION_POLICY)
    p['b_register_io_obligation']['transitionPredicate']='Fixed per-kind policy selected from method/rawPath/kind and independently committed original request, not caller observation_only. CANCEL and SIDE_EFFECT RECEIPT_OBSERVE use current authenticated recovery scope and exact original command SHA/claim/run/owner; no fresh execution containment/heartbeat/lease/activation requirement. Current identity/tenant/epoch/generation/channel C/DER/key/cert/observe grant required. RECEIPT_OBSERVE original parent PENDING/LIVE only; CANCEL may control UNKNOWN parent without settling it. TERMINAL_FRAME retains original live terminal rights; no new ARM/EXECUTE right.'
    for item in catalog['ioKinds']:
        if item['kind'] in ('CANCEL','RECEIPT_OBSERVE'):
            p[item['closureProcedure']]['recoveryCompletionPolicy']=item['atomicBoundary']
    d['protectedReceiptInput']='NodeStopReceipt from ORIGINAL exact kernel verifier is input to protected quiescence reconciliation; never ordinary UNKNOWN settle or generic fact clear. All source NodeReceiptStore record/release checks remain atomic.'
    d['terminalClaimRights']='Terminal register/invoke/confirm require current epoch, Node projection online or draining and known tenant execution gate with kill switch false, plus exact original EXECUTE PENDING/LIVE current-incarnation parent, active matched claim at original admitted version/current run attempt, THIS run RUNNING and all known leases unreleased/unexpired with deadline>now+5. DRAIN-only continuation exception remains bounded to this parent. Original typed kernel terminal release atomically tombstones execution rights/increments matched claim version; durable identity/UNKNOWN/recovery history retained. No ACK/outbox/row-state claim release.'
    d['trackedReviewInformation']={'I1':'Version/attempt tombstone CAS tracked INFO only; no new receipt/wire fields; normal newer-original admission guard retained','I2':'Unreachable TERMINAL/BUILD_CLEANUP predicate removed only in own model','I3':'Late in-flight frame failing current authority becomes UNCERTAIN/POISONED; same-Node HOLD needs existing protected settlement, never generic ACK/receipt clear','I4':'P-T1-OBSERVER-LOCK-SAFETY is named runtime pending outside fixed 19-edge census; None source default is not runtime handler proof','I5':'Complete alias-aware production and harness census replaces selected grep as constructor coverage authority','I6':'Only new regression wrapper hardened; original reviewer scripts byte-exact; historical bad relative invocation and corrected absolute invocation retained separately'}
    d['protectedBuildCleanupRead']='Exact original BUILD_DISPATCH/session/request/approval/decision/daemon/lease/resource/fence/held owned root and current protected LOCAL_READ purpose/readgrant. May observe after stop/release/deadline; own live read cap only; no read-based claim release or UNKNOWN settle. Actual T3 binding NULL/RUNTIME_PENDING.'
    p['b_register_io_obligation']['transitionPredicate']+=' TERMINAL_FRAME uses exact per-claim version/currentattempt/liveness and parent PENDING LIVE guard, no Node bool substitute. BUILD_CLEANUP_READ is separate protected build evidence read, not live workload continuation.'
    return d


def invariants(d):
    # Retain already-reviewed rights invariants, then add new orthogonality/ranks.
    errors=prior.invariants(d)
    errors=[e for e in errors if e!='quarantine not DENY-only']
    errors+=check_ranks(d)
    if 'LINEAGE_TOMBSTONE' in d['signaturePurposes']:errors.append('FICTITIOUS_TOMBSTONE_WIRE')
    if d['procedures']['b_activate_owner_contribution'].get('requiresNodeConfirmation') is not False:errors.append('PLAIN_OWNER_BEHAVIOR_CHANGED')
    if d['procedures']['b_settle_uncertain_io']['execute']!=[OP]:errors.append('ORDINARY_UNCERTAIN_SETTLE')
    for name,p in d['procedures'].items():
        if name.startswith('b_read_') and p['effects']:errors.append('READ_PROC_HAS_EFFECT:'+name)
        for table,effect in p['effects'].items():
            if table=='inv.node_role_authority_anchors' and set(p['execute'])&{RUN,VER,ISS,USER,BOOT} and (not set(effect['columns'])<={'version','scoped_versions'} or 'scoped_versions' in effect['columns'] and not p.get('versionMapKeysDerivedByFixedProcedure')):errors.append('ORDINARY_ANCHOR_SCOPE_MUTATION:'+name)
    for name in ('b_prepare_signature','b_publish_signature','b_read_signing_authority','b_lock_signature_publication'):
        if d['procedures'][name]['execute']!=[SIGN]:errors.append('SIGNING_DB_POOL:'+name)
    return errors


if __name__=='__main__':
    d=build();assert not invariants(d),invariants(d)
    (E/'authority-matrix.json').write_bytes((json.dumps(d,indent=2)+'\n').encode())
    (E/'reader-io-catalog.json').write_bytes((json.dumps(build_catalog(),indent=2)+'\n').encode())
