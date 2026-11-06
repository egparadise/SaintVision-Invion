"""Actual source reader/IO surfaces mapped to proposed narrow mediation."""
import ast
import hashlib
import subprocess
from functools import lru_cache
from pathlib import Path

E=Path(__file__).resolve().parent
ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
READERS=[
 ('placement.py',239,'b_read_placement_candidates','candidate eligibility snapshot before normal placement; retains original snapshot freshness/locality/resource-fit checks'),
 ('placement.py',538,'b_read_speculative_candidates','speculative candidate snapshot; selected guard must recheck anchor/obligation and exact selected resource set'),
 ('dispatch.py',79,'b_lock_execution_dispatch','execution admission under exact run/claim/lease/fence/current Node; no new dispatch while unresolved'),
 ('leases.py',253,'b_lock_lease_node_admission','lease reservation for full sorted allocation Node set; original per-project/resource ceilings retained'),
 ('capacity.py',23,'b_read_project_capacity','capacity projection over project members; only eligibility hints, not hard quotas or admission'),
 ('scheduler.py',106,'b_read_scheduler_candidate_snapshot','producer returns opaque typed EligibilitySnapshot; pure _place consumes it, final selected admission rechecks; raw caller Candidate cannot mint eligibility'),
 ('build_adapter.py',138,'b_lock_build_dispatch_authority','build dispatch binding under exact admitted run/resource/approval and unchanged channel/epoch'),
 ('gpu.py',97,'b_lock_gpu_allocation_authority','exact current GPU device/snapshot/channel/allocation proof; active leases retained'),
 ('model_commit.py',57,'b_lock_model_commit_nodes','complete model target Node/location set; owner consent and immutable model bindings retained'),
 ('model_locality.py',27,'b_lock_model_locality_nodes','complete replica Node set and snapshot/fencing/current channel recheck'),
 ('tooling.py',203,'b_lock_tool_claim_node','existing allocation matches Node and run, exact claim/fence and current authority'),
 ('terminal.py',78,'b_lock_terminal_exact_claim','existing terminal command/claim only; draining may continue only exact bounded CommittedIOHandle, never a fresh attach/admission chosen by request opid'),
 ('node_channels.py',137,'b_read_delivery_channel','business channel requires admission view OR exact existing committed operation handle; observe/cancel use separate authenticated scope, no client boolean authorization'),
]
B_READERS=[
 ('b_commit_node_activation','b_lock_activation_current','B current lineage/tuple/gate/CAS before activation'),
 ('b_refresh_same_generation','b_lock_refresh_current','same generation current B chain; effect-class and overlapping authority footprint predicate; READ_ONLY bookkeeping never denies'),
 ('b_record_request_issuance','b_lock_use_issuance','exact B request release/delegation/delivery/current lineage and original request nonce'),
 ('b_commit_business_nonce_evidence','b_lock_use_commit','B current authority and exact request/nonce/verified outcome at commit'),
 ('signing_service.prepare','b_read_signing_authority','protected authenticated full current chain/ancestor/tombstone/tuple/epoch/fence view'),
 ('signing_service.publish','b_lock_signature_publication','same anchors/versions as prepared intent, recheck BEFORE exposing signature'),
 ('b_approve_readonly_contribution_root','b_lock_folder_approval','ACTIVE owner consent + fresh signed B-only folder observation; preflight does not prove installed RO mount'),
]
IO=[
 ('EXECUTE','services/control-plane/src/inv/node_transport.py',289,'POST','/v1/executions','NodeExecutionPermit exact existing serialized bytes','NodeExecutionResult/NodeStopReceipt','b_confirm_execution_stop_io','sv_b_verifier','NodeReceiptStore.record original terminal receipt + permitted lease release/event same TX'),
 ('RECEIPT_OBSERVE','services/control-plane/src/inv/node_transport.py',289,'POST','/v1/executions/receipts','same original permit bytes; existing claimed operation only','NodeExecutionResult/NodeStopReceipt','b_confirm_execution_stop_io','sv_b_verifier','NodeReceiptStore.record duplicate/content/fence rules same TX'),
 ('CANCEL','services/control-plane/src/inv/node_transport.py',289,'POST','/v1/executions/cancel','same original signed permit; exact claimed command','NodeExecutionResult/NodeStopReceipt','b_confirm_execution_stop_io','sv_b_verifier','terminal receipt path alone decides release; obligation state never releases independently'),
 ('BUILD_DISPATCH','services/control-plane/src/inv/build_execution.py',787,'ADAPTER_EXECUTE','existing admitted adapter dispatch descriptor; no invented HTTP endpoint','exact existing request/plan/decision/intent-fencing-token bytes and approved decision hash','Build dispatch/evidence plus independently verified physical cleanup','b_confirm_build_dispatch_io','sv_b_verifier','same _commit_consequences lease CAS/evidence/outbox transaction, not mere adapter return'),
 ('BUILD_CLEANUP_READ','services/control-plane/src/inv/build_execution.py',835,'LOCAL_READ','existing PRODUCT_CLEANUP_RECEIPT_PREFIX + exact build_session_id + .json under held protected transport directory','existing collect_cleanup_receipt argument descriptor, parent BUILD_DISPATCH handle, original request/approval hashes; no claim of a signed local-file wire','BuildPhysicalCleanupReceipt','b_confirm_build_cleanup_read_io','sv_b_verifier','same typed build cleanup append/commit TX as parent, original duplicate physical receipt checks'),
 ('BUILD_HEALTH_READ','services/control-plane/src/inv/build_execution.py',779,'LOCAL_READ','existing PRODUCT_HEALTH_RECEIPT under held protected transport directory','exact collect_product_health descriptor and original operation binding','BuildProviderHealthReceipt','b_confirm_observation_io','sv_b_verifier','typed observation append, no resource release or success grant'),
 ('GPU_ACTIVE_OBSERVE','services/control-plane/src/inv/node_transport.py',93,'POST','/v1/snapshots','existing NodeProbeInput exact bytes and registered channel','authenticated existing GPU/resource snapshot classified ACTIVE by verifier; NOT NodeStopReceipt','b_confirm_active_observation_io','sv_b_verifier','observation/evidence TX only; workload/claim/lease remain ACTIVE; current NodeExecutionResult is terminal-only'),
 ('HEARTBEAT_OBSERVE','services/control-plane/src/inv/node_transport.py',89,'POST','/v1/heartbeats','existing exact NodeProbeInput','NodeProbeResult','b_confirm_observation_io','sv_b_verifier','original NodeObservation nonce/telemetry transaction'),
 ('STORAGE_SAMPLE','services/control-plane/src/inv/node_transport.py',108,'POST','/v1/storage/sample','existing exact signed challenge/envelope bytes, policy/channel/root/R','NodeStorageSignedSample','b_confirm_storage_sample_io','sv_b_verifier','StorageSampleStore.apply_sample typed sample nonce/evidence/check/consumption same TX, not equipment acceptance'),
 ('OBJECT_READ','services/control-plane/src/inv/node_transport.py',120,'POST','/v1/objects/read','existing exact NodeChunkInput and authorized immutable object','NodeChunkResult','b_confirm_object_read_io','sv_b_verifier','typed digest/size/claim validated append, no source writeback'),
 ('TERMINAL_FRAME','services/control-plane/src/inv/node_transport.py',124,'POST','/v1/terminals/frame','existing exact NodeTerminalInput and prior claimed command','NodeTerminalResult','b_confirm_terminal_frame_io','sv_b_verifier','exact sequence/body/expiry transaction; no new authority or lease release'),
 ('QUARANTINE_RECONCILE','services/control-plane/src/inv/node_transport.py',134,'POST','/v1/builds/quarantine','existing exact retained BuildQuarantineRequest','BuildQuarantineReceipt','b_confirm_safety_observation_io','sv_b_safety','durable Node quarantine ACK append; never clears denial'),
 ('B_GATE_ARM','PROPOSED_B_ONLY',None,'POST','/v1/roles/gate','existing proposed exact signed GATE_CONTROL ARM from current protected approved operation','GATE_ACK','b_record_gate_ack','sv_b_verifier','same transaction durable ACK append + exact IO confirmation before activation'),
 ('B_GATE_INVALIDATE','PROPOSED_B_ONLY',None,'POST','/v1/roles/gate','existing proposed exact signed GATE_CONTROL INVALIDATE from CP tombstone outbox','GATE_ACK','b_record_gate_ack','sv_b_verifier','existing durable Node gate record/retired history ACK + IO confirmation same transaction'),
 ('B_ROLE_OBSERVE','PROPOSED_B_ONLY',None,'POST','/v1/roles/observe','existing proposed closed nonce request on CP observe lane','GATE_OBSERVATION','b_record_reconcile_observation','sv_b_verifier','original still-valid ACK readback rules, otherwise B-RECOVERY1 HOLD'),
 ('B_FOLDER_ROOT_OBSERVE','PROPOSED_B_ONLY',None,'B_PREFLIGHT_OBSERVE','authorized contributed path only; no physical value bound yet','closed B observe permit/challenge and exact contribution/root scope','FolderRootObservation','b_append_folder_root_observation','sv_b_verifier','B-only proof append; no plain activation prerequisite and no installed RO mount proof'),
]


@lru_cache(maxsize=None)
def source_bytes(path):return subprocess.check_output(['git','show','72028cbac903c4415d9979f980a6e0f9948e914f:'+path],cwd=ROOT)


def source_record(path,line):
    if line is None:return {'path':path,'line':None,'implemented':False}
    data=source_bytes(path);lines=data.decode('utf-8-sig').splitlines()
    tree=ast.parse(data.decode('utf-8-sig'));matches=[]
    def visit(n,scope=()):
        for c in ast.iter_child_nodes(n):
            if isinstance(c,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                q=scope+(c.name,)
                if not isinstance(c,ast.ClassDef) and c.lineno<=line<=c.end_lineno:matches.append((c.end_lineno-c.lineno,'.'.join(q)))
                visit(c,q)
            else:visit(c,scope)
    visit(tree)
    return dict(path=path,line=line,function=min(matches)[1] if matches else '<module>',sourceSHA='72028cbac903c4415d9979f980a6e0f9948e914f',fileSHA256=hashlib.sha256(data).hexdigest(),exactLine=lines[line-1],implementedSourceOnly=True)


def retained_catalog():
    readers=[]
    for i,(name,line,proc,purpose) in enumerate(READERS,1):
        readers.append(dict(id=f'R{i:02}',**source_record('services/control-plane/src/inv/'+name,line),
            replacement=proc,purpose=purpose,
            predicate='DB-selected profile, exact tenant/Node/current epoch, independent current authority/containment facts and absence of UNRESOLVED scoped obligations; B adds authenticated current lineage/chain; original freshness/fence/resource checks remain',
            exception='only exact already committed own operation through limited authenticated handle; no caller-supplied opid bypass; observe/safety/reconcile use separate scope',
            admissionRecheck='candidate views are hints; actual reservation/dispatch rechecks under same authority anchor FOR UPDATE before new claim'))
    return dict(source='72028cbac903c4415d9979f980a6e0f9948e914f',plainReaders=readers,
        newBReaders=[dict(caller=a,replacement=b,purpose=c,implemented=False) for a,b,c in B_READERS],
        ioKinds=[dict(kind=k,source=source_record(p,l),method=m,rawPath=path,requestBinding=request,
            independentlyVerifiedOutcome=outcome,closureProcedure=proc,closurePrincipal=role,atomicBoundary=atomic,
            registration='committed before IO, typed opaque CommittedIOHandle consumed by CP adapter/verifier; no new plain Node field or floor2 change',
            failure='poison completion capability/incarnation first; persist UNCERTAIN if possible; otherwise PENDING + fenced completion authority and protected recovery, never ordinary settle after swallowed fence failure')
            for k,p,l,m,path,request,outcome,proc,role,atomic in IO],
        currentWireFact='generated core.schema NodeExecutionResult -> NodeStopReceipt with stopped=true/cleanupPending=false; ACTIVE observation cannot be passed to terminal release path',
        actualNewIOEnforcement=False)


from io_contract import EFFECT,READER_PURPOSE,READ_ONLY,SAFETY,SIDE_EFFECT

def build_catalog():
    d=retained_catalog()
    for r in d['plainReaders']:
        r['purposeClass']=READER_PURPOSE[r['id']]
        r['predicate']={'CANDIDATE_HINT':'DB-current eligible resource footprints; snapshot hint, selected claim admission rechecks intersections',
          'SPECULATIVE_HINT':'speculative resource candidate footprint only; original project/locality/resource ceiling and fresh final admission',
          'EXECUTION_ADMISSION':'new exact run/claim/resource dispatch; reject overlapping known SIDE_EFFECT pending, any same-scope side-effect uncertainty, current containment',
          'LEASE_ADMISSION':'new full sorted allocation set; intersect DB claim/resource footprint, not Node-wide single flight',
          'CAPACITY_HINT':'project member availability under original capacity policy; unresolved known footprints remove overlapping capacity only',
          'SCHEDULER_HINT':'typed producer snapshot; _place never mints admission; selected allocations recheck DB footprints',
          'BUILD_ADMISSION':'exact original build admission/intent/decision/claim; conflict with overlapping active obligation, not unrelated Node read',
          'GPU_ADMISSION':'device-specific original allocation and resource snapshot; keep active leases, reject same resource double use',
          'MODEL_COMMIT_ADMISSION':'full manifest target contribution/member/channel read or mutation footprint, frozen exact membership',
          'MODEL_LOCALITY_HINT':'replica snapshot only; exact parent/current authorized object read has separate continuation port',
          'TOOL_CLAIM_ADMISSION':'exact original run/resource claim/fence with DB-known footprint conflict check',
          'EXACT_TERMINAL_CONTINUATION':'already claimed terminal only; exact parent handle/run/claim/owner/deadline/lease/epoch/generation; DRAIN allowed as actual terminal.py:78, quarantine/retirement denied',
          'DELIVERY_FOR_ADMITTED_OPERATION':'exact admitted own command or signed observe/safety purpose; original owner/current channel/epoch/fence, not arbitrary opid or fresh selection'}[r['purposeClass']]
        r['intersectionRule']='same tenant/Node/current epoch; DB-derived complete rank/table/key/mode footprint; SHARE/SHARE coexists, overlapping UPDATE conflicts; unknown footprint is conservative Node-wide for that operation only. SIDE_EFFECT UNCERTAIN same-scope Node-wide; READ_ONLY never denial; safety only exact target/causal denial. Existing facts independent.'
    raw=source_bytes('services/control-plane/src/inv/node_transport.py');tree=ast.parse(raw.decode());methods={n.name:n for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='NodeTLSClient' for n in c.body if isinstance(n,ast.FunctionDef)}
    transport={'EXECUTE':'exchange','CANCEL':'exchange','RECEIPT_OBSERVE':'exchange','HEARTBEAT_OBSERVE':'probe','GPU_ACTIVE_OBSERVE':'resource_snapshot','STORAGE_SAMPLE':'storage_sample','OBJECT_READ':'read_chunk','TERMINAL_FRAME':'terminal_frame','QUARANTINE_RECONCILE':'quarantine'}
    for row in d['ioKinds']:
        k=row['kind'];row['effectClass']=EFFECT[k]
        row['effectSelection']='fixed method/rawPath/handler plus independently admitted exact request; same binding in schema/row/procedure/capability/consumer. Caller cannot downgrade.'
        row['failure']={READ_ONLY:'ordinary verifier NO_EFFECT_ABANDONED, never business denial/version bump; late reply cannot reopen or refresh. Actual verified liveness/revoke effects remain separate original writers',SIDE_EFFECT:'uncertain invocation or dead original capability => protected physical/quiescence proof only; atomic proven-never-invoked dispatch abort may NO_EFFECT; no timeout/not-sent boolean proof',SAFETY:'fresh protected RECOVERY_OBSERVATION verifier may close exact command/identity/epoch/generation/target/nonce durable ACK or authenticated causally bound readback; original poisoned cap never reconstructed; no ACK means uncertainty retained'}[EFFECT[k]]
        if k in transport:
            fn=methods[transport[k]];call=next(n for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='_request')
            row['source']=source_record('services/control-plane/src/inv/node_transport.py',call.lineno)
            row['transportMethod']='NodeTLSClient.'+transport[k]
            assert '_request(' in row['source']['exactLine']
        if k=='RECEIPT_OBSERVE':row['effectCounterexample']='Actual Runner.Observe invokes reconcile; reconcile can Stop and finish can Remove/Save. Exact method-scoped file/line/hash proof is generated in transport-inventory.json readOnlyException. Actual path retained SIDE_EFFECT; no pure read endpoint invented.'
    return d
