"""Six bounded AST/DATA controls; earlier guard results are separate evidence."""
import ast,json,sys
import mode
from mode import E,DC,NT,source,emit,scope,rule,Facts,sha
def main():
    sys.stdout.reconfigure(encoding='utf8');base={p:source(p,{}) for p in (mode.DC,mode.NT,mode.WK,mode.REMOTE)};rows=[];inputs={}
    variants=[('actual-source',{} ,'CONDITIONAL_LITERAL_MODE_ORIGIN_CANDIDATE',None),('benign-leading-comment',{DC:'# mode origin benign span shift\n'+base[DC]},'CONDITIONAL_LITERAL_MODE_ORIGIN_CANDIDATE',None),('causal-forwarded-mode-change',{DC:base[DC].replace('observation_only=attempt.operation == "observe"','observation_only=False',1)},'UNRESOLVED','MODE_FORWARDING_CHANGED'),('dynamic-operation-origin',{DC:base[DC].replace('operation = "execute"','operation = row["operation"]',1)},'UNRESOLVED','UNRESOLVED_DYNAMIC_OPERATION_ORIGIN'),('foreign-rebound-attempt-callee',{DC:base[DC]+'\nfrom .foreign import DeliveryAttempt as DeliveryAttempt\n'},'UNRESOLVED','EARLIER_CALLEE_BINDING')]
    for name,world,status,reason in variants:
        assert all(s!=base[p] for p,s in world.items())
        for p,s in world.items():compile(s,p,'exec',dont_inherit=True)
        # Mode rule is independently evaluated at the selected anchors. A
        # generic old full-use-site refusal is not evidence of this rule's cause.
        facts={p:Facts(p,world.get(p,s)) for p,s in base.items()}
        with scope():r=rule(facts)
        row={'name':name,'kind':'DIRECT_MODE_RULE' if name!='foreign-rebound-attempt-callee' else 'EARLIER_BINDING_PRECONDITION','status':r['status'],'reason':r['reason'],'expectedStatus':status,'expectedReason':reason,'inputSHA256':{p:sha(s) for p,s in world.items()},'unchangedOtherInputs':{p:sha(s) for p,s in base.items() if p not in world},'syntaxValid':True,'currentWitnesses':[e.get('source') for e in r['edges'] if e.get('source')],'qualification':'AST/DATA conditional source rule only; old full-use-site/context refusals are not counted as causal mode-rule proof; no runtime/DB/caller discharge'}
        for witness in row['currentWitnesses']:
            f=facts[witness['path']];matches=[n for n in ast.walk(f.tree) if getattr(n,'lineno',None) is not None and [n.lineno,n.col_offset,n.end_lineno,n.end_col_offset]==witness['span']]
            assert sha(f.source)==witness['fileSHA256'] and any(sha(ast.get_source_segment(f.source,n))==witness['expressionSHA256'] for n in matches)
        row['currentSpansRecomputedAndVerified']=True;row['acceptedSnapshotMatrix']='Referenced immutable R1/R2 proof at product72028; no snapshot body/matrix rerun or mutation'
        row['expectationMet']=r['status']==status and r['reason']==reason;rows.append(row);inputs[name]=world;emit('control-results.json',{'rows':rows});emit('control-inputs.json',inputs);print(json.dumps(row),flush=True);assert row['expectationMet'],name
    data=[]
    for left,right in [(False,False),(False,True),(True,False),(True,True),('tag',False),(False,'cancel-tag'),(None,'tag')]:
        # Literal builtin DATA, never a foreign object's __bool__/__eq__.
        result=left if bool(left) else right;data.append({'left':left,'right':right,'returnedOperand':'left' if bool(left) else 'right','result':result,'resultType':type(result).__name__,'snapshotTruthiness':bool(result)})
    assert data[4]['result']=='tag' and data[5]['result']=='cancel-tag' and data[0]['snapshotTruthiness'] is False
    rows.append({'name':'truthiness-and-or-operand-data','kind':'LITERAL_DATA_WITH_UNKNOWN_TYPE_PREMISE','matrix':data,'foreignTypePremise':'UNKNOWN; rich __eq__/__bool__ not evaluated, not certified builtin bool/string from annotation/comparison AST','noExactBoolRuntimeCheckInvented':True,'expectationMet':True})
    emit('control-results.json',{'rows':rows,'allExpected':True,'count':6,'actualRuntimeB':0,'productOrMutantsExecuted':False,'baselineDischarges':0});print(json.dumps({'controls':6,'allExpected':True,'actualRuntimeB':0}))
if __name__=='__main__':main()
