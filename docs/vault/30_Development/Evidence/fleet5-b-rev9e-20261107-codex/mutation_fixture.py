"""Reparse and rebase recorded AST spans/hashes for meaningful mutations."""
import ast,copy
import analysis_rules as r
from t1_provenance import qualified_functions
def owner(source,node):
    candidates=[(f.end_lineno-f.lineno,k) for k,f in qualified_functions(source).items() if f.lineno<=node.lineno<=f.end_lineno]
    return min(candidates)[1]
def rebase(original,mutated,rows):
    ot=ast.parse(original);mt=ast.parse(mutated);of=qualified_functions(original);mf=qualified_functions(mutated)
    out=[]
    for row in rows:
        rr=copy.deepcopy(row)
        old=next(n for n in ast.walk(ot) if isinstance(n,ast.Call) and r.span(n)==(row['line'],row['column'],row['endLine'],row['endColumn']))
        name=owner(original,old);key=ast.dump(old,include_attributes=False)
        oldsame=[n for n in ast.walk(of[name]) if isinstance(n,ast.Call) and ast.dump(n,include_attributes=False)==key]
        index=next(i for i,n in enumerate(oldsame) if r.span(n)==r.span(old))
        new=[n for n in ast.walk(mf[name]) if isinstance(n,ast.Call) and ast.dump(n,include_attributes=False)==key]
        assert len(new)==len(oldsame),(name,key)
        n=new[index];rr.update(line=n.lineno,column=n.col_offset,endLine=n.end_lineno,endColumn=n.end_col_offset)
        if 'expressionSHA256' in rr:rr['expressionSHA256']=r.sha(ast.get_source_segment(mutated,n));rr['expression']=ast.get_source_segment(mutated,n)
        if 'fileSHA256' in rr:rr['fileSHA256']=r.sha(mutated)
        out.append(rr)
    return out
def after_line(source,line,statements,indent='        '):
    lines=source.splitlines(keepends=True)
    return ''.join(lines[:line])+''.join(indent+s+'\n' for s in statements.splitlines())+''.join(lines[line:])
