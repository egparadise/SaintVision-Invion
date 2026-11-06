"""Import-aware, bounded AST facts; no application imports or source execution."""
import ast,hashlib,subprocess
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists());SOURCE='72028cbac903c4415d9979f980a6e0f9948e914f'
TARGETS={'inv.observer_worker.ObservationWorker','inv.observation.NodeObservation','inv.workspace_api.RestrictedWorkspaceRuntime'}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def text(n):return ast.unparse(n)
def span(n):return [n.lineno,n.col_offset,n.end_lineno,n.end_col_offset]
def module_name(path):
    for prefix in ('services/control-plane/src/','src/'):
        if path.startswith(prefix):return path[len(prefix):].removesuffix('.py').replace('/','.')
    return path.removesuffix('.py').replace('/','.')
@lru_cache(maxsize=3)
def frozen_source(path):return subprocess.check_output(['git','show',SOURCE+':'+path],cwd=ROOT,stderr=subprocess.PIPE).decode('utf-8-sig')
class Facts:
    def __init__(self,path,source):
        self.path=path;self.source=source;self.module=module_name(path);self.tree=ast.parse(source);self.parent={};self.scope={};self.functions={};self.classes={};self.aliases=defaultdict(dict);self.defs=defaultdict(dict)
        def walk(n,q=()):
            scope='.'.join(q);self.scope[id(n)]=scope
            for c in ast.iter_child_nodes(n):
                self.parent[id(c)]=n
                if isinstance(c,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                    name=q+(c.name,);qual='.'.join(name)
                    self.defs[scope][c.name]=self.module+'.'+qual
                    if isinstance(c,ast.ClassDef):self.classes[qual]=c
                    else:self.functions[qual]=c
                    walk(c,name)
                else:walk(c,q)
        walk(self.tree)
        package=self.module.rsplit('.',1)[0]
        for n in ast.walk(self.tree):
            q=self.scope[id(n)]
            if isinstance(n,ast.Import):
                for a in n.names:self.aliases[q][a.asname or a.name.split('.')[0]]=a.name if a.asname else a.name.split('.')[0]
            elif isinstance(n,ast.ImportFrom):
                base=n.module or ''
                if n.level:
                    pieces=package.split('.');base='.'.join(pieces[:len(pieces)-n.level+1]+([base] if base else []))
                for a in n.names:self.aliases[q][a.asname or a.name]=base+'.'+a.name
    def lookup(self,name,scope):
        parts=scope.split('.') if scope else []
        for count in range(len(parts),-1,-1):
            q='.'.join(parts[:count])
            if name in self.aliases[q]:return self.aliases[q][name]
            if name in self.defs[q]:return self.defs[q][name]
        if name in ('Exception','type','object','setattr','delattr','getattr','vars','globals','locals','eval','exec','__import__','__builtins__'):return 'builtins.'+name if name!='__builtins__' else 'builtins'
        return None
    def resolve(self,node):
        if isinstance(node,ast.Name):return self.lookup(node.id,self.scope.get(id(node),''))
        if isinstance(node,ast.Attribute):
            root=self.resolve(node.value);return root+'.'+node.attr if root else None
        return None
    def visible_aliases(self,scope):
        out={};parts=scope.split('.') if scope else []
        for count in range(len(parts)+1):out.update(self.aliases['.'.join(parts[:count])])
        return out
    def enclosing(self,node):
        q=self.scope[id(node)]
        while q and q not in self.functions:q=q.rsplit('.',1)[0] if '.' in q else ''
        return q
    def witness(self,node):return {'path':self.path,'function':self.module+'.'+self.enclosing(node),'span':span(node),'fileSHA256':sha(self.source),'expressionSHA256':sha(ast.get_source_segment(self.source,node))}
def candidate_paths():
    cmd=['git','grep','-l','-E',r'ObservationWorker|NodeObservation|RestrictedWorkspaceRuntime|import[[:space:]].*(observer_worker|observation|workspace_api)',SOURCE,'--','services/control-plane/src','src','tools','tests']
    r=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE);assert r.returncode in (0,1),r.stderr.decode()
    return sorted({x.split(':',1)[1] for x in r.stdout.decode().splitlines()}),cmd
def constructor_census(overrides=None):
    paths,command=candidate_paths();paths=sorted(set(paths)|set(overrides or {}));production=[];harness=[];files=[];unresolved=[]
    for path in paths:
        source=overrides[path] if overrides and path in overrides else frozen_source(path);f=Facts(path,source)
        files.append({'path':path,'bytes':len(source.encode()),'sha256':sha(source),'scope':'HARNESS_ONLY_PROVENANCE' if path.startswith('tests/') else 'PRODUCTION_SOURCE'})
        for c in ast.walk(f.tree):
            if not isinstance(c,ast.Call):continue
            target=f.resolve(c.func)
            short=text(c.func).rsplit('.',1)[-1]
            if target not in TARGETS and short not in {x.rsplit('.',1)[1] for x in TARGETS}:continue
            row={'constructor':target or 'UNRESOLVED:'+short,'calleeSpelling':text(c.func),'source':f.witness(c),'argument0':text(c.args[0]) if c.args else None,'argument0AST':ast.dump(c.args[0],include_attributes=False) if c.args else None,'importAliases':f.visible_aliases(f.scope[id(c)]),'scope':'HARNESS_ONLY_PROVENANCE' if path.startswith('tests/') else 'PRODUCTION_SOURCE'}
            (harness if path.startswith('tests/') else production).append(row)
            if target not in TARGETS:unresolved.append(row)
    return {'source':SOURCE,'command':command,'production':production,'harness':harness,'sourceFiles':files,'unresolvedConstructorBindings':unresolved,'readMode':'Serial one-file AST census, no full assembler or application import','actualRuntimeB':0}
