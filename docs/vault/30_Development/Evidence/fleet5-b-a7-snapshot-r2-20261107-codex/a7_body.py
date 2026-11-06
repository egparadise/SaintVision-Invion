"""Finite A7 semantic body grammar and authenticated helper/receiver checks.

AST statement/control-flow locks preserve the actual source contract; digests
are evidence, never authentication or a claim of runtime effect closure.
"""
import ast
from contextlib import contextmanager
import callee_identity as ci,call_binding as cb,reflection_audit as ra,use_sites as u,owner_transfer as ot
import analysis_rules as rules,t1_provenance as t
from lexical_bindings import index
from a7_common import *

SNAPSHOT='''def snapshot(self, node, *, observation_only=False):
    with self.db.transaction(node.tenant_id) as conn:
        if not observation_only:
            from .containment import require_execution
            require_execution(conn)
        row = conn.execute("SELECT *,clock_timestamp() AS now FROM inv.nodes WHERE node_id=%s FOR SHARE", (node.node_id,)).fetchone()
        if not row or str(row["recovery_epoch"]) != self.db.recovery_epoch:
            raise DomainError("NODE-0033", "Node channel epoch differs", 403)
        if not observation_only and (row["status"] != "online" or not 0 <= (row["now"] - row["heartbeat_at"]).total_seconds() <= 15):
            raise DomainError("NODE-0033", "Node is not current and online", 403)
        channel = conn.execute("SELECT * FROM inv.node_channels WHERE node_id=%s", (node.node_id,)).fetchone()
        if not channel or str(channel["recovery_epoch"]) != self.db.recovery_epoch:
            raise DomainError("NODE-0033", "Node channel is unavailable", 403)
        result = proof(channel)
        assert_channel(conn, result)
        return result
'''
ASSERT='''def assert_channel(conn, expected):
    row = conn.execute("SELECT * FROM inv.node_channels WHERE node_id=%s FOR SHARE", (expected.node_id,)).fetchone()
    now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    if not row or not row["enabled"] or row["certificate_not_after"] <= now or proof(row) != expected:
        raise DomainError("NODE-0033", "Node channel authority changed or expired", 403)
    return row
'''
PROOF='''def proof(row):
    return ChannelProof(str(row["tenant_id"]), row["node_id"], str(row["recovery_epoch"]), row["version"], row["endpoint"], row["certificate_sha256"])
'''
EXECUTION='''def require_execution(conn):
    gate = conn.execute("SELECT kill_switch FROM inv.tenant_controls").fetchone()
    if not gate or gate["kill_switch"]:
        raise DomainError("AUTH-0061", "Tenant execution is stopped by its operator", 409)
'''
STATEMENTS=['NORMAL_CONTAINMENT_IMPORT_AND_CALL','NODE_LOCK_AND_DB_CLOCK','NODE_EPOCH_ALWAYS','NORMAL_ONLINE_HEARTBEAT_0_15','CHANNEL_READ_SAME_CONNECTION','CHANNEL_EPOCH_ALWAYS','CHANNEL_PROOF_DATA','ASSERT_CURRENT_CHANNEL_ALWAYS','RETURN_PROOF_DATA']

@contextmanager
def target_scope():
    # Necessary target symbols only; these are copied, accepted finite engines.
    old=(u.PROTECTED_PREFIXES,set(u.PROTECTED_CLASS_NAMES),ot.PREFIXES,set(ra.MODULES),set(ra.NAMES))
    u.PROTECTED_PREFIXES+=('inv.node_channels','inv.containment');u.PROTECTED_CLASS_NAMES.update({'NodeChannels','ChannelProof'})
    ot.PREFIXES+=('inv.node_channels',);ra.MODULES.update({'inv.node_channels','inv.containment'});ra.NAMES.update({'NodeChannels','ChannelProof','proof','assert_channel','require_execution'})
    u.baseline_sites.cache_clear();u.baseline_owners.cache_clear();ra.frozen_hits.cache_clear()
    try:yield
    finally:
        u.PROTECTED_PREFIXES,u.PROTECTED_CLASS_NAMES,ot.PREFIXES,ra.MODULES,ra.NAMES=old
        u.baseline_sites.cache_clear();u.baseline_owners.cache_clear();ra.frozen_hits.cache_clear()

def prove(world=None):
    facts={p:Facts(p,get(p,world)) for p in (NC,CT,DB,ER)};f=facts[NC];contain=facts[CT];checks=[];edges=[]
    def reject(code,n=None,detail=''):
        return {'bodyAccepted':False,'reason':code,'detail':detail,'source':witness(f,n) if n is not None and id(n) in f.scope else None,'checks':checks,'blocksGrant':True,'scope':'A7_STATIC_BODY_CERTIFICATION_ONLY'}
    snap=f.functions.get('NodeChannels.snapshot');init=f.functions.get('NodeChannels.__init__')
    if snap is None or init is None:return reject('UNRESOLVED:A7_TARGET_BODY_MISSING')
    if len(init.body)!=1 or text(init.body[0])!='self.db = database' or not t.local_field_proof(f.source,'NodeChannels','db','database'):return reject('UNRESOLVED:A7_DATABASE_OWNER_STORE',init)
    checks.append({'gate':'NODECHANNELS_DATABASE_FIELD','source':witness(f,init),'kind':'constructor parameter stored once; DB input types still need caller closure'})
    functions,classes=cb.registry(facts)
    reason=ci.construction(f,'NodeChannels',classes)
    if reason:return reject(reason,init,'class construction binding')
    for obj in (f,contain):
        for call in ast.walk(obj.tree):
            if not isinstance(call,ast.Call):continue
            q=obj.enclosing(call)
            if not (obj is f and q in {'NodeChannels.snapshot','proof','assert_channel'} or obj is contain and q=='require_execution'):continue
            symbol,pair,bound=cb.target(obj,call,functions,classes)
            if symbol in PROTECTED or (symbol or '').removesuffix('.__init__') in PROTECTED or symbol=='inv.errors.DomainError':
                reason=ci.error(obj,call,symbol,pair,classes)
                if reason:return reject(reason,call if obj is f else None,'authenticated helper/caller binding')
                edges.append({'target':symbol,'source':witness(obj,call),'callerBinding':getattr(obj,'_caller_binding_proofs',{}).get((call.lineno,call.col_offset,call.end_lineno,call.end_col_offset)),'state':'SOURCE_BINDING_ATTESTED_NOT_RUNTIME_PURE'})
    expected=ast.parse(SNAPSHOT).body[0]
    if shape(snap.args)!=shape(expected.args) or snap.decorator_list or snap.returns:return reject('UNRESOLVED:A7_SNAPSHOT_SIGNATURE',snap)
    if len(snap.body)!=1 or not isinstance(snap.body[0],ast.With):return reject('UNRESOLVED:A7_TRANSACTION_BODY',snap)
    txn=snap.body[0];et=expected.body[0]
    if len(txn.items)!=1 or shape(txn.items[0])!=shape(et.items[0]):return reject('UNRESOLVED:A7_TRANSACTION_OWNER',txn)
    if len(txn.body)!=len(et.body):return reject('UNRESOLVED:A7_STATEMENT_OR_FORWARDING_ESCAPE',txn)
    for actual,wanted,label in zip(txn.body,et.body,STATEMENTS):
        if shape(actual)!=shape(wanted):return reject('UNRESOLVED:A7_'+label,actual,'semantic AST/control-flow/SQL/receiver statement contract, not a source-digest gate')
        checks.append({'gate':label,'source':witness(f,actual),'mode':'NORMAL_ONLY' if label.startswith('NORMAL') else 'BOTH_NORMAL_AND_OBSERVATION'})
    # The local relative import is mandatory at exactly the normal-mode branch.
    imp=txn.body[0].body[0];call=txn.body[0].body[1].value
    if f.resolve(call.func)!=REQUIRE or not isinstance(imp,ast.ImportFrom) or imp.level!=1 or imp.module!='containment':return reject('UNRESOLVED:A7_RELATIVE_IMPORT_TARGET',imp)
    for obj,q,template,label in [(f,'proof',PROOF,'PROOF_DATA'),(f,'assert_channel',ASSERT,'CURRENT_CHANNEL_CERTIFICATE_PROOF'),(contain,'require_execution',EXECUTION,'EXECUTION_CONTAINMENT')]:
        actual=obj.functions.get(q);wanted=ast.parse(template).body[0]
        if actual is None or shape(actual.args)!=shape(wanted.args) or actual.decorator_list or [shape(n) for n in actual.body]!=[shape(n) for n in wanted.body]:return reject('UNRESOLVED:A7_'+label,actual if obj is f else None,'helper semantic body/signature lock')
        checks.append({'gate':label,'source':witness(obj,actual),'scope':'exact selected helper only'})
    cls=f.classes.get('ChannelProof');wanted=ast.parse('''@dataclass(frozen=True)
class ChannelProof:
    tenant_id: str
    node_id: str
    recovery_epoch: str
    version: int
    endpoint: str
    certificate_sha256: str
''').body[0]
    if cls is None or shape(cls)!=shape(wanted) or not rules.exact_import(f.tree,'dataclass','dataclasses'):return reject('UNRESOLVED:A7_CHANNEL_PROOF_DATA_DECLARATION',cls)
    if not rules.error_initializer(facts[ER].source,'DomainError'):return reject('UNRESOLVED:A7_DOMAIN_ERROR_ROUTE')
    union,error=t.observed_union(facts[DB].source)
    if error:return reject(error,None,'accepted Database.transaction result union dependency')
    # The union proof alone is not a whole transaction/body/clock claim.
    # Attest the necessary original DB bodies/signatures and import AST as a
    # finite lock; genuine receiver provenance and runtime effects stay open.
    prior=Facts(DB,frozen_source(DB));current=facts[DB]
    selected=['Database.__init__','Database.transaction','_ObservedConnection.__init__','_ObservedConnection.execute','_ObservedConnection.__getattr__']
    for q in selected:
        actual=current.functions.get(q);old=prior.functions[q]
        if actual is None or shape(actual)!=shape(old):return reject('UNRESOLVED:A7_DATABASE_DEPENDENCY_BODY',None,q)
        checks.append({'gate':'DATABASE_DEPENDENCY_BODY_AND_SIGNATURE','qualifiedName':q,'source':witness(current,actual),'meaning':'frozen AST dependency, not runtime effects or Database input type'})
    imports=lambda x:[shape(n) for n in ast.walk(x.tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
    if imports(current)!=imports(prior):return reject('UNRESOLVED:A7_DATABASE_DEPENDENCY_IMPORTS')
    for q in ('Database','_ObservedConnection'):
        reason=ci.construction(current,q,classes)
        if reason:return reject(reason,None,'Database dependency class construction')
    # Necessary lexical loads (including builtin str used by epoch/proof data)
    # keep their actual frozen binding scope and event multiset. This is a
    # finite source binding check; it makes no claim about a live Python heap.
    checked=set()
    selected_bodies=[(f,q) for q in ('NodeChannels.__init__','NodeChannels.snapshot','proof','assert_channel')]+[(contain,'require_execution')]+[(current,q) for q in selected]
    for obj,q in selected_bodies:
        bindings=index(obj);old=Facts(obj.path,frozen_source(obj.path));previous=index(old)
        for n in ast.walk(obj.functions[q]):
            if not isinstance(n,ast.Name) or not isinstance(n.ctx,ast.Load):continue
            lexical=bindings.nodeScopes[id(n)];scope=bindings.binding_scope(lexical,n.id);oldscope=previous.binding_scope(lexical,n.id);k=(obj.path,lexical,n.id)
            if k in checked:continue
            checked.add(k)
            if scope!=oldscope or bindings.events_for(scope,n.id)!=previous.events_for(oldscope,n.id) or bindings.stars_for(scope)!=previous.stars_for(oldscope):return reject('UNRESOLVED:A7_NECESSARY_LEXICAL_BINDING',n if obj is f else None,f'{obj.path}:{q}:{n.id}')
    checks.append({'gate':'NECESSARY_LEXICAL_LOAD_BINDINGS','distinctSourceScopeNamePairs':len(checked),'rule':'same binding scopes and actual frozen binding-event multisets, not name-spelling authentication'})
    for path,obj in facts.items():
        audit=ra.audit(obj,PROTECTED)
        if audit['newRelevantHits']:return reject('UNRESOLVED:A7_RELEVANT_REFLECTION',None,path)
        uses,error=u.module_uses(obj.source,path,instances=True,factories=(),parameter_context={})
        if error:return reject(error,None,'retained full-module use-site guard: '+path)
        checks.append({'gate':'FROZEN_USE_SITE_SCOPE','path':path,'proof':uses,'notPurity':'existing non-target uses are retained, not admitted by this proof'})
    # Only genuine execute receiver loads and explicit, checked conn forwards.
    for obj,q in [(f,'NodeChannels.snapshot'),(f,'assert_channel'),(contain,'require_execution')]:
        fn=obj.functions[q];allowed=set()
        for call in ast.walk(fn):
            if not isinstance(call,ast.Call):continue
            if isinstance(call.func,ast.Attribute) and text(call.func)=='conn.execute':allowed.add(id(call.func.value))
            if obj.resolve(call.func) in {REQUIRE,'inv.node_channels.assert_channel'}:
                allowed.update(id(n) for n in call.args if isinstance(n,ast.Name) and n.id=='conn')
        for n in ast.walk(fn):
            if isinstance(n,ast.Name) and n.id=='conn' and isinstance(n.ctx,ast.Load) and id(n) not in allowed:return reject('UNRESOLVED:A7_CONNECTION_FORWARDING_ESCAPE',n if obj is f else None)
    return {'bodyAccepted':True,'reason':None,'checks':checks,'helperEdges':edges,'databaseResultUnionConditional':union,'dbOwnerCondition':'All source NodeChannels database inputs must still close to the authenticated Database/transaction owner; MAY-owner facts alone are insufficient',
      'purposeMatrix':{'NORMAL':['containment.require_execution','node FOR SHARE/recovery epoch','online + heartbeat [0,15] using DB clock','channel recovery epoch','channel FOR SHARE/enabled/current certificate/current proof'],
                       'OBSERVATION':['node FOR SHARE/recovery epoch','channel recovery epoch','channel FOR SHARE/enabled/current certificate/current proof'],
                       'truthiness':'Original Python truthiness, default False. No runtime exact-bool check invented. Unknown/foreign arguments remain caller blockers.'},
      'unadmitted':['NodeDelivery.deliver/network/crypto/provision/revoke','installed DB role/RLS/READ COMMITTED/SET LOCAL/clock/codec/observer/locks/auth/cutover'],
      'runtimeBinding':None,'actualRuntimeB':0,'scope':'SOURCE_BODY_ATTESTED_CONDITIONAL_ON_RECEIVER_AND_CALLER_CLOSURE_NOT_RUNTIME_EFFECT_CLOSED'}
