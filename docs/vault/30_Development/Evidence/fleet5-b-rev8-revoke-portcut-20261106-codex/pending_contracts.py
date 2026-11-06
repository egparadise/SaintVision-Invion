"""Named EXISTING interface design contracts. Real bindings NULL; no grants."""
import ast,hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent
ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
S='72028cbac903c4415d9979f980a6e0f9948e914f';INPUTS={}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def anchor(path,owner,needle=None):
    raw=subprocess.check_output(['git','show',S+':'+path],cwd=ROOT);text=raw.decode('utf-8-sig');tree=ast.parse(text)
    INPUTS[path]={'path':path,'bytes':len(raw),'sha256':sha(raw)}
    assert len(INPUTS)<=12 and sum(x['bytes'] for x in INPUTS.values())<2*1024*1024
    found=[]
    def walk(n,scope=()):
        for c in ast.iter_child_nodes(n):
            if isinstance(c,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                q=scope+(c.name,)
                if '.'.join(q)==owner:found.append(c)
                walk(c,q)
            else:walk(c,scope)
    walk(tree);assert len(found)==1,(path,owner);n=found[0]
    segment=ast.get_source_segment(text,n);line=n.lineno
    if needle:
        assert needle in segment,(path,owner,needle)
        line=n.lineno+segment[:segment.index(needle)].count('\n')
    return {'source':S,'path':path,'function':owner,'functionRange':[n.lineno,n.end_lineno],'line':line,'fileSHA256':sha(raw),'functionSHA256':sha(segment.encode()),'needle':needle}
def contract(id,wiring,auth,inp,out,error,ownership,transaction,effect,deps):
    return {'id':id,'status':'DESIGN_ONLY_PENDING_IMPLEMENTATION_AND_ROOT_CHOICE','actualBinding':None,'codeGrant':False,'portGrant':False,
      'wiring':wiring,'authentication':auth,'input':inp,'output':out,'error':error,'ownership':ownership,'transaction':transaction,'effect':effect,'verificationDependencies':deps}
def main():
    cp='services/control-plane/src/inv/';cs=[]
    cs.append(contract('T1',[
      anchor(cp+'db.py','Database.transaction','Runtime must use a non-owner role without RLS bypass'),
      anchor(cp+'db.py','BoundDatabase.transaction'),anchor(cp+'db.py','Database.__init__'),
      anchor(cp+'observation.py','NodeObservation.mark_offline')],
      'ONE shared P-DBROLE credential contract. Installed non-superuser, non-schema-owner, no RLS-bypass role; tenant/current epoch from trusted principal. Future B purpose-specific roles require actual grant/RLS proof. Not 13 new ports.',
      'Validated tenant UUID and fixed containment_write boolean chosen by trusted caller; immutable recovery epoch; exact DSN held by private installed owner, never evidence or request input. BoundDatabase tenant must equal outer tenant.',
      'ObservedConnection/psycopg connection scoped to transaction; BoundDatabase yields same existing connection, no new transaction credential.',
      'AUTH-0020 on role check; LEASE-0004 epoch mismatch; AUTH-0060 missing tenant barrier; RES-0007 retry same key on lock timeout/query cancellation/deadlock; AUTH-0011 nested tenant mismatch; unknown commit never success.',
      'Database owns connection; BoundDatabase borrows. statement_observer/placement_metric_sink/logger are pending typed observability only after all production constructor sites/type/effect constraints are proven. Callback exception must not hide commit ambiguity or confer authority.',
      'READ COMMITTED; SET LOCAL tenant via set_config; 500ms lock_timeout/2s statement_timeout; control_epoch FOR SHARE; tenant_controls fixed SHARE or UPDATE before body; no network IO in transaction. ContextVar phase get/set/reset stays related to yield/commit/rollback/lock timing.',
      'DB credential connect + reads/writes of caller body; clock/perf_counter remain real clock sources. Observability output may append metrics/logs only and must not mutate authority, dispatch or credentials.',
      ['A3 context phase provenance','A7 exact tools import/return proof across four runtime import sites','A8 all production constructor argument propagation; subclass override BLOCK; harness doubles retained separately','purpose role PG/RLS/grants and two-session trace NOT_RUN','mark_offline SECOND demonstrator only; no critical entry upgrade from this contract']))
    cs.append(contract('P-DBROLE',cs[0]['wiring'][:3],cs[0]['authentication'],cs[0]['input'],cs[0]['output'],cs[0]['error'],cs[0]['ownership'],cs[0]['transaction'],cs[0]['effect'],['Alias of shared T1 credential boundary, not another grant','real DSN/key/role binding NULL','actual PG NOT_RUN']))
    cs.append(contract('T2',[anchor(cp+'node_transport.py','NodeTLSClient.__init__'),anchor(cp+'node_transport.py','NodeTLSClient._request'),anchor(cp+'node_transport.py','NodeDelivery.deliver')],
      'Installed CP TLS client and current Node channel C/DER/certificate/tenant/epoch; peer authority rechecked. Handle kind/method/rawPath and original request select effect. User observation_only cannot select fresh execution authority.',
      'Exact committed opaque IO handle, independently admitted original request bytes, closed rawPath/method, body SHA and current channel; no arbitrary host/URL/method.',
      'Bounded strict typed response under exact peer/request; ordinary completion one-use LIVE capability or fresh narrow safety recovery where catalog permits.',
      'TLS/timeout/abort/parse/size/schema/peer/channel errors poison completion before handling; READ_ONLY abandonment, SIDE_EFFECT UNKNOWN/HOLD, exact safety recovery as catalog. Timer/not-sent is never never-invoked proof.',
      'OneConnection/request/getresponse/socket/abort timer are implementation of already catalogued 19 caller boundaries, not independent network permissions.',
      'Original admission/registration COMMIT before external call; no DB lock held across network; typed result appended with original checks in its own transaction.',
      'Fixed existing EFFECT per method/rawPath/handler. RECEIPT_OBSERVE SIDE_EFFECT (Go Stop/Remove/Save). CANCEL idempotent safety.',
      ['transport-delta nine ServeHTTP+path branch anchors','Rev7 19 byte-exact caller rows retained by hash','actual Go/TLS/DB/crash CI NOT_RUN','no new socket/network binding']))
    cs.append(contract('T3',[anchor(cp+'buildkit_transport.py','_protected_json'),anchor(cp+'storage.py','verify_content')],
      'Trusted installed build receipt/source plan ownership; existing BUILD_HEALTH_READ/BUILD_CLEANUP_READ/object verification purpose. No public arbitrary path port.',
      'Exact configured owned receipt path or trusted Storage resolved immutable object; expected digest/size; held parent/path identity, current owner/mode; reject symlink/substitution/foreign parent.',
      'Strict bounded protected JSON receipt or verified immutable bytes digest/size; data does not create source writeback or contribution host access.',
      'Unsafe parent/owner/mode/type, lstat/open/fstat mismatch, symlink/TOCTOU/content/size failure -> refusal/uncertainty under owning IO kind. Existing verify_content Path.open alone is not proof of no-symlink protection.',
      'Owning adapter must hold/check exact path and descriptor identity; proposed hardened owner/mode/parent contract for any missing source enforcement remains pending. No generic filesystem capability.',
      'Read outside authority locks; original trusted verification records only in consumer transaction; immutable digest and descriptor/root identity rechecked before acceptance.',
      'Purpose-bound read only; os.open/fstat/fdopen/lstat/S_ISREG are implementation details. No signing, random access, writes or arbitrary filesystem path.',
      ['actual Linux symlink/TOCTOU/mount substitution/owner-mode tests NOT_RUN','descriptor/parent enforcement for verify_content pending','retained contribution read-only/nonrecursive/rprivate boundary unaffected']))
    cs.append(contract('P-INJECT-BUILD',[anchor(cp+'build_product_runtime.py','configured_tenant_product_runtime'),anchor(cp+'build_execution.py','BuildExecutionService.__init__'),anchor(cp+'buildkit_transport.py','RootlessBuildkitTransport.__init__'),anchor(cp+'buildkit_transport.py','NodeAgentReceipts.__init__')],
      'Composition root supplies trusted database/adapter/receipt owner/environment. Builder identity/profile/recovery epoch/channel still original approved build authority. Caller cannot replace clock/runner.',
      'Separate injected clock/now, request-id factory and runner contracts. Clock values are observed time, request IDs fresh identity material; runner accepts only exact configured buildctl executable/address/source authority/args.',
      'Clock sample; request identity; bounded subprocess execution result and existing cleanup/health receipts. No exit-zero-as-application-success.',
      'Unknown callable/subclass/runner override -> DYNAMIC_BLOCK until typed source wiring. Process timeout/start/cleanup/commit ambiguity follows BUILD_DISPATCH SIDE_EFFECT/HOLD.',
      'Clock provider, ID factory, subprocess runner remain separate purpose/effect boundaries; production defaults/overrides must be enumerated before binding. Optional materialize hook ABSENT_IN72028/RES0006 is not implementation.',
      'Original committed build intent before dispatch; no authority DB locks over buildctl; original receipt/consequence commit remains atomic.',
      'Actual datetime/time clock and request randomness are not pure conversions. buildctl run is BUILD_DISPATCH side effect, never generic NONAUTHORITY.',
      ['all composition roots/source types and overrides','clock/id/runner mutation negatives','real Go/Engine/buildctl/crash/PG NOT_RUN','future source capsule implementation requires NEW IO kind']))
    # Current actual apply_capability_offer is 0031; 0030 defines its superseded
    # apply_resource_offer predecessor. Never bind a stale function by filename.
    cs.append(contract('P-DBFUNC',[anchor('migrations/versions/0031_resource_offer_integrity.py','upgrade','CREATE FUNCTION public.apply_capability_offer'),anchor('migrations/versions/0027_business_api_guards.py','upgrade','CREATE OR REPLACE FUNCTION public.business_admin_allowed')],
      'SECURITY DEFINER functions SET search_path=pg_catalog; PUBLIC execute revoked, inv_app EXECUTE granted. Recheck tenant setting/current active public.users and inv.business_admin_grants resources.manage, not caller role string.',
      'apply_capability_offer tenant/capability/verified actor/offered safe integer within capability; GPU mapping explicitly refused. business_admin_allowed tenant/user/permission fixed existing service binding.',
      'Typed applied/reason/resource_ids/capacity or false; no claim release. Existing total/unreleased lease sums include expired/old epoch without stop receipt.',
      'Tenant mismatch/unknown capability/invalid quantity/unit/GPU mapping/resource missing/leased offer refusal; unauthorized admin SQLSTATE42501; lock/commit errors retain original business refusal/rollback.',
      'Definer owns only fixed function body; named reads public.users,node_capabilities,nodes; inv.nodes/resources/resource_leases/business_admin_grants; writes inv.resources.offered. No arbitrary SQL/table parameter.',
      'Lock active principal/grants SHARE, public Node/capability then inv Node and sorted resources UPDATE; re-read capacity/unreleased leases after waiting; update all resource slices in same tenant transaction.',
      'Existing SQL-body authority read + offered write. Rev7 SQL unknown body port remains until full function/procedure effect/rank join proof; this design label grants nothing.',
      ['Correct actual definition in 0031, predecessor 0030 revoked','PG role/definer/search_path/RLS/offer concurrency NOT_RUN','exact all function tables/permissions/source->procedure join before code']))
    cs.append(contract('P-API-DI',[anchor('src/saintvision/api/v1/settings.py','set_resource_offer'),anchor('src/saintvision/api/deps.py','get_principal'),anchor('src/saintvision/api/deps.py','get_session')],
      'FastAPI Depends(get_principal) verifies bearer through installed verifier; get_session derives principal tenant SET LOCAL inside session.begin; set_resource_offer require_global_administrator at current DB scope.',
      'Existing ResourceOffer request/capability/idempotency headers, actual authenticated Principal; body role/principal string never authentication.',
      'Existing canonical business offer response/audit and original idempotency result, not B grant or fresh Node execution permit.',
      'Missing/rejected credential AUTH, permission refusal, schema conflict, idempotency conflict, bounded lock-wait canonical retryable error; unknown commit no success.',
      'App.state credential verifier/engine/clock are pending typed composition dependencies. Header/router.put/Depends declarations are framework wiring, not self-authenticating allowlists.',
      'get_session tenant transaction; original idempotency and bounded lock wait wrap actual write; auth rechecks in SQL definer remain independent.',
      'Business auth and offer writer entry point; no caller-selected user role. Framework/DI provenance stays pending; does not waive any static unknown.',
      ['principal verifier/dependency source closure','tenant/role/idempotency negatives','actual API+PG integration NOT_RUN']))
    cs.append(contract('P-GETATTR',[],
      'No dynamic receiver gains authority from literal attribute spelling. BoundDatabase fields, metric sink, object_store provider/session, build clock/reconciliation, lock_wait.orig.sqlstate and settings audit require exact receiver and production constructor proof.',
      'Exact enumerated literal attribute + proven object type/owner; dynamic attribute/unknown receiver remains DYNAMIC_BLOCK.',
      'Typed optional data/callable only under its specific owning contract; absent optional source capsule closed as RES0006.',
      'Unknown/override/dynamic fallback refuses affected entry. No generic unknown-property exemption.',
      'Per-edge exact source/type/receiver lives in critical-edge-categories.json; never a global getattr port.',
      'Owning original transaction/IO kind applies; callback effect not assumed safe.',
      'Read or injected effect depends on proven target; signing/DB/network/clock retained as actual effects.',
      ['Per-occurrence constructor/import/type proof','unknown property/subclass/callback mutations','real binding NULL']))
    tables=['inv.tenants','inv.node_controls','public.tenants','inv.node_resource_snapshots','inv.model_run_inputs','inv.checkpoints','inv.checkpoint_objects','public.node_bootstrap_tokens','public.recovery_drills','inv.approval_audit','inv.approval_review_snapshots']
    cs.append(contract('P-LOCKRANK',[],
      'DB-discovered full tenant/primary-key set; trusted fixed procedures select tables, never caller table/key authority.',tables,
      'Proposed future ranks/comparator proof for exactly 11 currently unranked actual DML tables; NO rank assigned by Rev8.',
      'Any required unranked table -> affected entry remains blocked; no silent rank0/default omission.',
      'Single shared lock catalog owner; ties use (rank, qualified table, canonical complete PK bytes). Advisory locks remain separate.',
      'Discover full set, preacquire strongest merged lock once before effects; body assert-held; no upgrade after prefix.',
      'Existing table DML locks, no new write permission.',
      ['Root choice of exact ranks in future cut','two-session PG deadlock/rank traces NOT_RUN','39 source-lock plans:33 with procedureRefs,6 none; nonpilot plans unchanged']))
    cs.append(contract('P-SQLSCOPE',[anchor('src/saintvision/api/lock_wait.py','bound_lock_wait'),anchor('src/saintvision/api/lock_wait.py','bounded_lock_wait'),anchor('src/saintvision/api/lock_wait.py','validate_lock_timeout')],
      'Typed existing tenant-scoped Session owned by trusted business write transaction, not user SQL.',
      'timeout_ms validated exact integer (bool refused) in closed min/max range; only SET LOCAL lock_timeout formatted from validated value.',
      'Transaction-local bound; no table reads/writes or new credential.',
      'Invalid range/type ValueError; only known timeout/deadlock OperationalError sqlstates mapped canonical retryable SYS-0001/503; other operational errors reraised.',
      'SQL scope analysis must link validated formatter and original Session; unknown formatting remains DYNAMIC_BLOCK.',
      'Must be inside session.begin and tenant scope; timeout mapping before context exit rolls transaction back.',
      'Session configuration effect, not NONAUTHORITY and not a global/session persistent timeout change.',
      ['bounded SQL formatter proof and invalid bool/string/range mutants','actual PG SET LOCAL/error rollback NOT_RUN']))
    result={'source':S,'contracts':cs,'bindingPolicy':'All real bindings NULL/HOLD. Contracts name existing interfaces, do not register/grant them. Cut3 needs future explicit Root choice after actual Rev8 review.',
      'sourceInputs':list(INPUTS.values()),'sourceBytes':sum(x['bytes'] for x in INPUTS.values()),'actualRuntimeB':0,'actualIndependentRev8Review':'PENDING via Root','partialFreeze':False}
    (E/'pending-interface-contracts.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps({'namedContracts':len(cs),'sourceFiles':len(INPUTS),'sourceBytes':result['sourceBytes'],'actualBindings':None}))
if __name__=='__main__':main()
