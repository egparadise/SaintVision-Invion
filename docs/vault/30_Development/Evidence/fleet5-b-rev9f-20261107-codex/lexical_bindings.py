"""Binding categories for the supplied AST only; no general closure/heap audit.

Declarations redirect bindings from their own lexical scope. Nested bodies,
lambdas and comprehension iteration variables have separate scopes. Nonlocal
remains outside this bounded correction. No product source is executed.
"""
import ast
from collections import Counter
from source_bindings import sha

class Bindings(ast.NodeVisitor):
    def __init__(self,f):
        self.f=f;self.scope='';self.kind='module';self.stack=[];self.globals={};self.events=[];self.stars=Counter()
        self.visit(f.tree);self.definitions=Counter();self.writes=set()
        for kind,scope,name in self.events:
            effective='' if name in self.globals.get(scope,set()) else scope
            if kind=='definition':self.definitions[(effective,name)]+=1
            else:self.writes.add((effective,name))
    def event(self,kind,name,scope=None):
        if name:self.events.append((kind,self.scope if scope is None else scope,name))
    def enter(self,name,kind,body):
        self.stack.append((self.scope,self.kind));self.scope=self.scope+'.'+name if self.scope else name;self.kind=kind
        for node in body:self.visit(node)
        self.scope,self.kind=self.stack.pop()
    def visit_Global(self,n):self.globals.setdefault(self.scope,set()).update(n.names)
    def visit_Name(self,n):
        if isinstance(n.ctx,(ast.Store,ast.Del)):self.event('write',n.id)
    def function(self,n):
        self.event('definition',n.name)
        # Header expressions execute in the defining scope; body/arguments do not.
        for d in n.decorator_list+n.args.defaults+[v for v in n.args.kw_defaults if v is not None]:self.visit(d)
        args=n.args.posonlyargs+n.args.args+n.args.kwonlyargs+([n.args.vararg] if n.args.vararg else [])+([n.args.kwarg] if n.args.kwarg else [])
        for a in args:
            if a.annotation:self.visit(a.annotation)
        if n.returns:self.visit(n.returns)
        self.enter(n.name,'function',args+n.body)
    visit_FunctionDef=function
    visit_AsyncFunctionDef=function
    def visit_arg(self,n):self.event('write',n.arg)
    def visit_ClassDef(self,n):
        self.event('definition',n.name)
        for x in n.bases+n.keywords+n.decorator_list:self.visit(x)
        self.enter(n.name,'class',n.body)
    def visit_Lambda(self,n):
        for x in n.args.defaults+[v for v in n.args.kw_defaults if v is not None]:self.visit(x)
        args=n.args.posonlyargs+n.args.args+n.args.kwonlyargs+([n.args.vararg] if n.args.vararg else [])+([n.args.kwarg] if n.args.kwarg else [])
        self.enter(f'<lambda@{n.lineno}:{n.col_offset}>','function',args+[n.body])
    def comprehension(self,n):
        self.visit(n.generators[0].iter)
        self.stack.append((self.scope,self.kind));self.scope+=f'.<comprehension@{n.lineno}:{n.col_offset}>';self.kind='comprehension'
        for i,g in enumerate(n.generators):
            if i:self.visit(g.iter)
            self.visit(g.target)
            for x in g.ifs:self.visit(x)
        for x in ([n.key,n.value] if isinstance(n,ast.DictComp) else [n.elt]):self.visit(x)
        self.scope,self.kind=self.stack.pop()
    visit_ListComp=comprehension
    visit_SetComp=comprehension
    visit_DictComp=comprehension
    visit_GeneratorExp=comprehension
    def visit_NamedExpr(self,n):
        self.visit(n.value)
        scope=self.scope
        if self.kind=='comprehension':
            scope=next(s for s,k in reversed(self.stack) if k!='comprehension')
        if isinstance(n.target,ast.Name):self.event('write',n.target.id,scope)
        else:self.visit(n.target)
    def visit_Import(self,n):
        for a in n.names:self.event('write',a.asname or a.name.split('.')[0])
    def visit_ImportFrom(self,n):
        for a in n.names:
            if a.name=='*':self.stars[(self.scope,sha(ast.get_source_segment(self.f.source,n)))]+=1
            else:self.event('write',a.asname or a.name)
    def visit_ExceptHandler(self,n):
        self.event('write',n.name)
        if n.type:self.visit(n.type)
        for x in n.body:self.visit(x)
    def visit_MatchAs(self,n):
        self.event('write',n.name)
        if n.pattern:self.visit(n.pattern)
    def visit_MatchStar(self,n):self.event('write',n.name)
    def visit_MatchMapping(self,n):
        self.event('write',n.rest)
        for x in n.keys+n.patterns:self.visit(x)

def index(f):
    if not hasattr(f,'_rev9f_bindings'):f._rev9f_bindings=Bindings(f)
    return f._rev9f_bindings
