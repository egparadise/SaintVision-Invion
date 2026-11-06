"""Structured transition/guard contracts for EVERY RULES writer, not 10 names.

This regression contract is source-semantic evidence, not runtime authorization.
Reference contracts are extracted from immutable72028; mutants never regenerate
their expected contract. Column/target/CASE/WHERE/branch/parameter drift blocks.
"""
import ast,hashlib,json,re,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent
BASE='72028cbac903c4415d9979f980a6e0f9948e914f'

def insert_shape(expr):
    m=re.fullmatch(r'INSERT\s+INTO\s+(inv\.[a-z_]+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)\s*',expr,re.I)
    return {'table':m[1].lower(),'columns':[x.strip() for x in m[2].split(',')],'values':[x.strip() for x in m[3].split(',')]} if m else {'UNRESOLVED_INSERT_SHAPE':True}

def ddl_defaults(raw):
    body=raw.decode('utf-8-sig').split('CREATE TABLE inv.tenant_controls (',1)[1].split('\n);',1)[0]
    return {'kill_switch':re.search(r'kill_switch\s+boolean[^\n]*DEFAULT\s+(true|false)',body,re.I)[1].lower(),
            'version':int(re.search(r'\bversion\s+bigint[^\n]*DEFAULT\s+([0-9]+)',body,re.I)[1])}

def flows(sources,wanted):
    from source_analysis import modname,ownwalk
    out={}
    for path,raw in sources.items():
        if not path.endswith('.py') or not any(f.startswith(modname(path)+'.') for f in wanted):continue
        tree=ast.parse(raw.decode('utf-8-sig'))
        def visit(node,names=()):
            for c in ast.iter_child_nodes(node):
                if isinstance(c,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                    q=names+(c.name,);fn=modname(path)+'.'+'.'.join(q)
                    if fn in wanted:
                        guards=[];assign=[];writes=[]
                        for n in ownwalk(c):
                            if isinstance(n,ast.Call) and ast.unparse(n.func).split('.')[-1] in ('execute','executemany','execute_values','scalar','scalars','update','delete','add','add_all','setattr','bulk_update_mappings','bulk_insert_mappings'):writes.append(ast.unparse(n))
                            if isinstance(n,(ast.If,ast.Assert,ast.While)):guards.append(ast.unparse(n.test))
                            if isinstance(n,(ast.Assign,ast.AnnAssign,ast.AugAssign)) and n.value is not None:
                                ts=n.targets if isinstance(n,ast.Assign) else [n.target]
                                assign.append({'targets':[ast.unparse(t) for t in ts],'value':ast.unparse(n.value)})
                        out[fn]={'guards':guards,'assignments':assign,'writeExpressions':writes,'kind':'STRUCTURED_BRANCH_BINDING_CONTRACT','path':path}
                    visit(c,q)
                else:visit(c,names)
        visit(tree)
    return out

def attach(sources,result):
    path='services/control-plane/src/inv/migrations/0022_node_containment.sql'
    result['authorityDDLDefaults']=ddl_defaults(sources[path]) if path in sources else None
    contracts=flows(sources,{w['function'] for w in result['writers']})
    for w in result['writers']:
        w['allTransitionGuards']=contracts.get(w['function'],{'kind':'SQL_ROUTINE_OFFLINE_CONTRACT','path':w['path']})
        # All SET columns and exact RHS plus parameter binding; not only status.
        expr=w.get('resolvedSQL') or w['expression'];set_clause=re.search(r'\bSET\b([\s\S]*?)(?=\bWHERE\b|\bRETURNING\b|$)',expr,re.I)
        w['allColumnTransitions']={'columns':w['columns'],'setExpression':re.sub(r'\s+',' ',set_clause.group(1)).strip() if set_clause else None,
          'typedStatement':ast.dump(ast.parse(w['expression']),include_attributes=False) if not w['kind'].startswith('SQL') else None,
          'where':w.get('transitionSemantics',{}).get('whereNormalized',''),'semantics':w.get('transitionSemantics',{})}
        if w['function'].startswith('SQL:') and w['verb']=='INSERT':w['allColumnTransitions']['insertShape']=insert_shape(w['expression'])

def build_contracts():
    from reconcile import RULES
    # Read only the immutable source files needed by RULES. No app import or DB.
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'--','services/control-plane/src/inv','src/saintvision/services','tools'],text=True).splitlines()
    wanted={fn for fn,table in RULES if not fn.startswith('SQL:')}
    from source_analysis import modname
    selected=[p for p in names if p.endswith('.py') and any(f.startswith(modname(p)+'.') for f in wanted)]
    sources={p:subprocess.check_output(['git','show',BASE+':'+p]) for p in selected}
    flow=flows(sources,wanted)
    assert set(flow)==wanted,(set(wanted)-set(flow))
    sqlpath='services/control-plane/src/inv/migrations/0022_node_containment.sql';sql=source_sql=subprocess.check_output(['git','show',BASE+':'+sqlpath])
    expr=re.search(rb'INSERT INTO inv\.tenant_controls\(tenant_id\) VALUES\(NEW\.tenant_id\)',sql)[0].decode()
    return {'source':BASE,'coveredRuleKeys':[list(k) for k in sorted(RULES)],'functions':flow,
      'SQLRoutineInsert':insert_shape(expr),'SQLRoutineDDLDefaults':ddl_defaults(source_sql),
      'SQLRoutineRule':'actual seed inserts NEW.tenant_id only; source DDL default kill_switch=false/version=0, exclusive no-B traffic; no invented version1 or runtime DB-default proof',
      'plainActivation':'owner+not-revoked only; no Node confirmation; B-only FolderRootObservation separate'}

def compare_contracts(census,mapped):
    path=E/'transition-contracts.json'
    if not path.exists():return ['MISSING_ALL_RULE_TRANSITION_CONTRACTS']
    expected=json.loads(path.read_text(encoding='utf8'));errors=[]
    from reconcile import RULES
    if {tuple(k) for k in expected['coveredRuleKeys']}!=set(RULES):errors.append('STALE_TRANSITION_RULE_COVERAGE')
    by_id={(w['function'],w['table'],w['line'],w['column']):w for w in census['writers']}
    for w in mapped:
        if (w['function'],w['table']) not in RULES:continue
        original=by_id[(w['function'],w['table'],w['line'],w['column'])]
        if w['function'] in expected['functions'] and original.get('allTransitionGuards')!=expected['functions'][w['function']]:errors.append('ALL_RULE_TRANSITION_GUARD_DRIFT:'+w['function'])
        if w['function'].startswith('SQL:'):
            if original.get('allColumnTransitions',{}).get('insertShape')!=expected['SQLRoutineInsert']:errors.append('SQL_ROUTINE_INSERT_AUTHORITY_DRIFT:'+w['function'])
            if census.get('authorityDDLDefaults')!=expected['SQLRoutineDDLDefaults']:errors.append('SQL_ROUTINE_DEFAULT_AUTHORITY_DRIFT:'+w['function'])
    return sorted(set(errors))

if __name__=='__main__':
    result=build_contracts();(E/'transition-contracts.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'ruleKeys':len(result['coveredRuleKeys']),'functions':len(result['functions'])}))
