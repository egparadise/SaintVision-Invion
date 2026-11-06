"""Source-only counterexamples. Mutated product text is parsed/compiled, never run.

Body-gate red/green is conditional; the overall current caller closure remains
UNRESOLVED and no test here claims a DB runtime outcome or full causal closure.
"""
import ast,json,sys
import a7_body as body,a7_inventory as inventory
from a7_common import *

def replace(path,old,new):
    s=frozen_source(path);assert s.count(old)==1,(path,old,s.count(old));return {path:s.replace(old,new,1)}

def main():
    sys.stdout.reconfigure(encoding='utf8');cases=[];inputs={};fail=[]
    def run(name,world,expected=False,layer='BODY',expected_reason=None):
        for p,s in world.items():compile(s,p,'exec',dont_inherit=True)
        with body.target_scope():
            result=body.prove(world) if layer=='BODY' else inventory.census(world)
        accepted=result['bodyAccepted'] if layer=='BODY' else not result['obligations']
        reason=result['reason'] if layer=='BODY' else [r['code'] for r in result['obligations']]
        valid=accepted==expected and (expected_reason is None or expected_reason in str(reason))
        row={'name':name,'layer':layer,'accepted':accepted,'expected':expected,'reason':reason,'expectationMet':valid,'syntaxValid':True,'inputSHA256':{p:sha(s) for p,s in world.items()},'frozenUnchangedOtherSelectedInputs':{p:sha(frozen_source(p)) for p in (NC,CT,DB,ER) if p not in world},'qualification':'new body-gate/source-census counterexample only; baseline all-caller closure unresolved, no full-runtime/DB result or full causal certification claim'}
        if layer=='BODY':row['checksBeforeRefusal']=[r['gate'] for r in result['checks']]
        cases.append(row);inputs[name]=world
        emit('a7-test-results.json',{'cases':cases,'actualRuntimeB':0,'productImportedOrExecuted':False});emit('a7-test-inputs.json',inputs)
        print(json.dumps(row),flush=True)
        if not valid:fail.append(name)
    run('actual-body-normal-and-observation',{},True)
    run('benign-comment', {NC:frozen_source(NC)+'\n# A7 source-only benign comment control\n'},True)
    changes=[
      ('wrong-relative-import-module',NC,'from .containment import require_execution','from .foreign import require_execution',''),
      ('wrong-import-name-alias',NC,'from .containment import require_execution','from .containment import foreign as require_execution',''),
      ('wrong-import-alias',NC,'from .containment import require_execution','from .containment import require_execution as foreign','NORMAL_CONTAINMENT'),
      ('conditional-import-shadow',NC,'from .containment import require_execution','from .containment import require_execution; require_execution = foreign if node else require_execution',''),
      ('module-helper-rebinding',NC,'def proof(row):','proof = foreign\ndef proof(row):','CALLEE_REBOUND'),
      ('remove-normal-containment',NC,'require_execution(conn)','pass','NORMAL_CONTAINMENT'),
      ('containment-always-including-observation',NC,'if not observation_only:', 'if True:','NORMAL_CONTAINMENT'),
      ('remove-normal-online-heartbeat',NC,'if not observation_only and (','if False and (','NORMAL_ONLINE'),
      ('weaken-normal-heartbeat-limit',NC,'<= 15','<= 150','NORMAL_ONLINE'),
      ('remove-node-epoch-both-modes',NC,'if not row or str(row["recovery_epoch"]) != self.db.recovery_epoch:','if not row:','NODE_EPOCH'),
      ('remove-channel-epoch-both-modes',NC,'if not channel or str(channel["recovery_epoch"]) != self.db.recovery_epoch:','if not channel:','CHANNEL_EPOCH'),
      ('remove-current-channel-assert-both-modes',NC,'assert_channel(conn, result)','pass','ASSERT_CURRENT'),
      ('remove-enabled-channel-both-modes',NC,'or not row["enabled"]','or False','CURRENT_CHANNEL_CERTIFICATE'),
      ('remove-certificate-expiry-both-modes',NC,'or row["certificate_not_after"] <= now','or False','CURRENT_CHANNEL_CERTIFICATE'),
      ('remove-current-proof-both-modes',NC,'or proof(row) != expected','or False','CURRENT_CHANNEL_CERTIFICATE'),
      ('remove-node-share-lock',NC,'FROM inv.nodes WHERE node_id=%s FOR SHARE','FROM inv.nodes WHERE node_id=%s','NODE_LOCK'),
      ('remove-channel-share-lock',NC,'FROM inv.node_channels WHERE node_id=%s FOR SHARE','FROM inv.node_channels WHERE node_id=%s','CURRENT_CHANNEL_CERTIFICATE'),
      ('database-field-escape',NC,'self.db = database','self.db = foreign(database)','DATABASE_OWNER_STORE'),
      ('transaction-receiver-escape',NC,'with self.db.transaction(node.tenant_id) as conn:','with foreign.transaction(node.tenant_id) as conn:','TRANSACTION_OWNER'),
      ('connection-forwarding-escape',NC,'assert_channel(conn, result)','assert_channel(foreign(conn), result)','ASSERT_CURRENT'),
      ('containment-result-not-original',CT,'gate = conn.execute("SELECT kill_switch FROM inv.tenant_controls").fetchone()','gate = foreign(conn)','EXECUTION_CONTAINMENT'),
      ('db-yield-selection-escape',DB,'yield observed_conn','yield foreign(observed_conn)','YIELD'),
      ('db-query-forward-escape',DB,'self._conn.execute(query, params, **kwargs)','foreign(query, params, **kwargs)','CHANGED_OBSERVED_RETURN'),
      ('db-body-outside-result-union',DB,"SET LOCAL lock_timeout = '500ms'","SET LOCAL lock_timeout = '501ms'",'DATABASE_DEPENDENCY_BODY'),
    ]
    for name,p,old,new,reason in changes:run(name,replace(p,old,new),expected_reason=reason or None)
    run('class-monkeypatch', {NC:frozen_source(NC)+'\nNodeChannels.snapshot = foreign\n'},expected_reason='WRITE_USE')
    run('epoch-str-binding-rebound', {NC:frozen_source(NC)+'\nstr = foreign\n'},expected_reason='NECESSARY_LEXICAL_BINDING')
    p=CP+'observation.py'
    for name,old,new,reason in [
      ('caller-import-wrong-module','from .node_channels import NodeChannels','from .foreign import NodeChannels','A7_CONSTRUCTOR'),
      ('caller-import-alias-preserved-name','from .node_channels import NodeChannels','from .node_channels import foreign as NodeChannels','A7_CONSTRUCTOR'),
      ('caller-constructor-rebound','self.channels = NodeChannels(database)','NodeChannels = foreign; self.channels = NodeChannels(database)','A7_CONSTRUCTOR_BINDING'),
      ('caller-receiver-field-rebound','self.channels = NodeChannels(database)','self.channels = NodeChannels(database); self.channels = foreign','A7_CHANNEL_RECEIVER_REBOUND'),
      ('caller-dynamic-purpose','observation_only=True','observation_only=foreign','A7_PURPOSE_PROVENANCE')]:
        run(name,replace(p,old,new),layer='CENSUS',expected_reason=reason)
    # Literal truthiness is a source-classification unit, not an execution test.
    literals=[]
    for expr,purpose in [('False','NORMAL'),('True','OBSERVATION'),('0','NORMAL'),("''",'NORMAL'),("'x'",'OBSERVATION'),('None','NORMAL'),('foreign',None)]:
        actual=inventory.mode(ast.parse('channels.snapshot(node, observation_only='+expr+')').body[0].value);okay=actual.get('purpose')==purpose and (actual['state']=='UNRESOLVED')==(purpose is None);assert okay
        literals.append({'input':expr,'result':actual,'expectationMet':okay})
    emit('a7-test-results.json',{'cases':cases,'literalTruthinessUnits':literals,'failures':fail,'actualRuntimeB':0,'productImportedOrExecuted':False,'scope':'body/source census layers only, no full causal closure while caller ownership is unresolved'})
    assert not fail,fail
if __name__=='__main__':main()
