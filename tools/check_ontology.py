"""Semantic checks: positive/negative constraints, graph equivalence and queries."""
from pathlib import Path
import json
from rdflib import Graph, Namespace, URIRef, RDF, RDFS, OWL, Literal
from rdflib.compare import isomorphic
from pyshacl import validate

root=Path(__file__).resolve().parents[1]
folder=root/'ontology'
sv=Namespace('https://saintvision.ai/ontology/core#')
dev=Namespace('https://saintvision.ai/ontology/dev#')
inv=Namespace('https://saintvision.ai/ontology/inv#')
ml=Namespace('https://saintvision.ai/ontology/mlops#')
res=Namespace('https://saintvision.ai/resource/')
schema=Graph().parse(folder/'schema.ttl',format='turtle')
data=Graph().parse(folder/'example.ttl',format='turtle')
jsonld=Graph().parse(folder/'example.jsonld',format='json-ld')
shapes=Graph().parse(folder/'shapes.ttl',format='turtle')
assert isomorphic(data,jsonld), 'Turtle and JSON-LD differ'
defined=set(schema.subjects())
for graph in [schema,data]:
    for subject,predicate,obj in graph:
        for term in [subject,predicate,obj]:
            if isinstance(term,URIRef) and str(term).startswith('https://saintvision.ai/ontology/') and '#' in str(term):
                assert term in defined, f'Undefined project term: {term}'
ok,_,report=validate(data,shacl_graph=shapes,ont_graph=schema,inference='rdfs')
assert ok, report
registry=json.loads((root/'docs/task-registry.json').read_text('utf-8'))
tasks=registry['tasks']
# ownership.rq returns one row per task/outcome edge. Derive that cardinality
# from the registry, the source of truth for those edges, instead of copying
# today's count here. The edge set itself is checked below for each task.
expected={
    'ownership.rq':sum(len(task['outcome_ids']) for task in tasks),
    # These are intentional semantic fixture invariants: each example query
    # currently has exactly one demonstrated result, and a changed example
    # should require an explicit review of that fixture.
    'dataset-locality.rq':1,
    'model-lineage.rq':1,
    'retry-fencing.rq':1,
}
for filename,count in expected.items():
    results=list((schema+data).query((folder/'queries'/filename).read_text('utf-8')))
    assert len(results)==count, f'{filename}: expected {count}, got {len(results)}'
assert len(list(data.subjects(RDF.type,dev.DevelopmentTask)))==len(registry['tasks'])
for task in registry['tasks']:
    node=res[task['task_id']]
    assert (node,dev.ownedBy,res['agent-'+task['owner']]) in data
    assert (node,dev.reviewedBy,res['agent-'+task['reviewer']]) in data
    assert (node,sv.status,Literal(task['status'])) in data
    assert set(data.objects(node,dev.dependsOn))=={res[d] for d in task['depends_on']}
    assert set(data.objects(node,dev.realizes))=={res[o] for o in task['outcome_ids']}
for test in ['missing_owner','self_review','succeeded_without_evidence','ready_without_checksum']:
    bad=Graph()
    for triple in data: bad.add(triple)
    task=res['S01-FE']
    if test=='missing_owner': bad.remove((task,dev.ownedBy,None))
    elif test=='self_review': bad.set((task,dev.reviewedBy,res['agent-Gemini']))
    elif test=='succeeded_without_evidence': bad.set((res['example-run'],sv.status,Literal('succeeded')))
    else: bad.remove((res['example-location'],ml.checksum,None))
    conforms,_,_=validate(bad,shacl_graph=shapes,ont_graph=schema,inference='rdfs')
    assert not conforms, f'Negative fixture accepted: {test}'
for path in folder.rglob('*'):
    if path.is_file():
        mirror=root/'docs/vault/50_Ontology/Release-0.2.0'/path.relative_to(folder)
        assert mirror.is_file() and mirror.read_bytes()==path.read_bytes(), f'Ontology mirror mismatch: {path.name}'
print('PASS: RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings, positive SHACL, 4 rejected invalid fixtures, 4 competency queries, Obsidian mirrors.')
