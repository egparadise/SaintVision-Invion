from pathlib import Path
import json
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD

root=Path(__file__).resolve().parents[1]
directory=root/'ontology'
directory.mkdir(exist_ok=True)
sv=Namespace('https://saintvision.ai/ontology/core#')
inv=Namespace('https://saintvision.ai/ontology/inv#')
dev=Namespace('https://saintvision.ai/ontology/dev#')
ml=Namespace('https://saintvision.ai/ontology/mlops#')
sec=Namespace('https://saintvision.ai/ontology/security#')
res=Namespace('https://saintvision.ai/resource/')
namespaces={'sv':sv,'inv':inv,'dev':dev,'ml':ml,'sec':sec,'res':res}
original=(root/'docs/sources/50_Ontology/saintvision-inv.ttl').read_text('utf-8-sig')
tbox=Graph().parse(data=original.split('res:cluster-inv-lab-01')[0],format='turtle')
for prefix,ns in namespaces.items(): tbox.bind(prefix,ns)
ontology=URIRef('https://saintvision.ai/ontology/inv')
tbox.set((ontology,OWL.versionInfo,Literal('0.2.0')))
classes={sv:['Tenant','AgentProfile'], inv:['RunGraph','RunAttempt','Checkpoint','NetworkLink','Allocation'],
         dev:['ProductOutcome','AcceptanceCriterion','EvidenceRequirement','DevelopmentCapability','Contract','DevelopmentTask','SkillSpec','PromptSpec','ContextBundle','HarnessProfile','DevelopmentReport','ErrorRecord','ResolutionRecord'],
         sec:['ProvenanceRecord','EvidenceEnvelope','PolicyBundle']}
for ns,terms in classes.items():
    for term in terms:
        tbox.add((ns[term],RDF.type,OWL.Class)); tbox.add((ns[term],RDFS.subClassOf,sv.Entity)); tbox.add((ns[term],RDFS.label,Literal(term)))
objects={dev:['requiresCriterion','requiresEvidence','realizes','ownedBy','reviewedBy','dependsOn','usesContract','usesSkill','verifiesCriterion','reportsTask','hasBuild','hasReport','resolvedBy'],
         inv:['hasAttempt','hasCheckpoint','usesGraph','allocatedBy'],sec:['hasEvidence','hasProvenance']}
for ns,terms in objects.items():
    for term in terms: tbox.add((ns[term],RDF.type,OWL.ObjectProperty))
datatypes={sv:['endedAt','recordKind'],inv:['grantedAt'],dev:['criterionText','scope','evidenceDescription','taskId']}
for ns,terms in datatypes.items():
    for term in terms: tbox.add((ns[term],RDF.type,OWL.DatatypeProperty))
tbox.serialize(directory/'schema.ttl',format='turtle')

a=Graph()
for prefix,ns in namespaces.items(): a.bind(prefix,ns)
def entity(name,cls,**props):
    node=res[name]; a.add((node,RDF.type,cls))
    for key,val in props.items(): a.add((node,sv[key],Literal(val)))
    return node

for name in ['Codex','Claude','Gemini']:
    entity('agent-'+name,sv.AgentProfile,displayName=name,version='1.0.0',recordKind='development_profile')
for skill in ['agent-delivery','core-reliability','service-integration','frontend-delivery']:
    entity('skill-'+skill,dev.SkillSpec,version='1.0.0')
registry=json.loads((root/'docs/task-registry.json').read_text('utf-8'))
for o in registry['outcomes']:
    outcome=entity(o['id'],dev.ProductOutcome,displayName=o['title'],status='planned')
    criterion=entity(o['acceptance_id'],dev.AcceptanceCriterion,status='planned')
    requirement=entity('evidence-required-'+o['id'],dev.EvidenceRequirement,status='planned')
    a.add((outcome,dev.requiresCriterion,criterion))
    a.add((criterion,dev.criterionText,Literal(o['criterion'])))
    a.add((criterion,dev.requiresEvidence,requirement))
    a.add((requirement,dev.evidenceDescription,Literal(o['evidence_required'])))
for t in registry['tasks']:
    node=entity(t['task_id'],dev.DevelopmentTask,status=t['status'],recordKind='development_plan')
    a.add((node,dev.taskId,Literal(t['task_id'])))
    a.add((node,dev.scope,Literal(t['scope'])))
    a.add((node,dev.ownedBy,res['agent-'+t['owner']]))
    a.add((node,dev.reviewedBy,res['agent-'+t['reviewer']]))
    for oid in t['outcome_ids']: a.add((node,dev.realizes,res[oid]))
    for dep in t['depends_on']: a.add((node,dev.dependsOn,res[dep]))
    for skill in t['skill_refs']: a.add((node,dev.usesSkill,res['skill-'+skill]))
    contract=entity('contract-'+t['area'],dev.Contract,version='1.0.0',displayName=t['area'])
    a.add((node,dev.usesContract,contract))

# Synthetic runtime example. None of these identifiers describes a real pilot run.
node=entity('example-node',inv.Node,status='online',recordKind='synthetic_example')
cap=entity('example-capability',inv.Capability,displayName='Synthetic GPU runtime')
gpu=entity('example-gpu',inv.GPUResource); a.add((gpu,inv.vramBytes,Literal(17179869184,datatype=XSD.integer)))
offer=entity('example-offer',inv.ResourceOffer,status='available')
a.add((node,inv.advertisesCapability,cap)); a.add((node,inv.offersResource,offer)); a.add((offer,inv.describesResource,gpu))
dataset=entity('example-dataset-v1',ml.DatasetVersion,version='1.0.0')
location=entity('example-location',ml.DataLocation,status='ready')
a.add((dataset,ml.hasLocation,location)); a.add((location,inv.locatedOn,node))
for obj in [dataset,location]: a.add((obj,ml.checksum,Literal('sha256:'+'0'*64)))
workload=entity('example-workload',inv.Workload)
run=entity('example-run',inv.Run,status='scheduled',recordKind='synthetic_example')
plan=entity('example-plan',inv.PlacementPlan)
lease=entity('example-lease',inv.ResourceLease)
a.add((workload,inv.createsRun,run)); a.add((run,inv.scheduledBy,plan)); a.add((plan,inv.selectsNode,node))
a.add((run,inv.holdsLease,lease)); a.add((lease,inv.leasesResource,gpu))
a.add((lease,inv.fencingToken,Literal('42')))
a.add((lease,inv.grantedAt,Literal('2026-09-09T00:00:00Z',datatype=XSD.dateTime)))
a.add((lease,inv.expiresAt,Literal('2026-09-09T01:00:00Z',datatype=XSD.dateTime)))
attempt=entity('example-attempt',inv.RunAttempt); checkpoint=entity('example-checkpoint',inv.Checkpoint)
a.add((run,inv.hasAttempt,attempt)); a.add((attempt,inv.hasCheckpoint,checkpoint))
model=entity('example-model-v1',ml.ModelVersion,version='1.0.0')
commit=entity('example-commit',dev.CodeCommit); image=entity('example-image',dev.ContainerImage)
a.add((run,ml.consumesDataset,dataset)); a.add((run,ml.registersModel,model))
a.add((run,dev.usesCommit,commit)); a.add((run,dev.usesImage,image))
a.add((commit,dev.commitSha,Literal('0'*40))); a.add((image,dev.imageDigest,Literal('sha256:'+'0'*64)))
a.serialize(directory/'example.ttl',format='turtle')
a.serialize(directory/'example.jsonld',format='json-ld',context={p:str(n) for p,n in namespaces.items()},auto_compact=True,indent=2)

shapes='''@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix sv: <https://saintvision.ai/ontology/core#> .
@prefix inv: <https://saintvision.ai/ontology/inv#> .
@prefix dev: <https://saintvision.ai/ontology/dev#> .
@prefix ml: <https://saintvision.ai/ontology/mlops#> .
@prefix sec: <https://saintvision.ai/ontology/security#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

dev:TaskShape a sh:NodeShape; sh:targetClass dev:DevelopmentTask;
 sh:property [ sh:path dev:ownedBy; sh:minCount 1; sh:maxCount 1; sh:class sv:AgentProfile; sh:disjoint dev:reviewedBy ];
 sh:property [ sh:path dev:reviewedBy; sh:minCount 1; sh:maxCount 1; sh:class sv:AgentProfile ];
 sh:property [ sh:path dev:realizes; sh:minCount 1; sh:class dev:ProductOutcome ];
 sh:property [ sh:path dev:usesContract; sh:minCount 1; sh:class dev:Contract ];
 sh:property [ sh:path dev:usesSkill; sh:minCount 1; sh:class dev:SkillSpec ];
 sh:property [ sh:path sv:status; sh:minCount 1; sh:maxCount 1; sh:in ("planned" "ready" "in_progress" "review" "done" "blocked") ].
dev:OutcomeShape a sh:NodeShape; sh:targetClass dev:ProductOutcome;
 sh:property [ sh:path dev:requiresCriterion; sh:minCount 1; sh:class dev:AcceptanceCriterion ].
dev:CriterionShape a sh:NodeShape; sh:targetClass dev:AcceptanceCriterion;
 sh:property [ sh:path dev:requiresEvidence; sh:minCount 1; sh:class dev:EvidenceRequirement ];
 sh:property [ sh:path dev:criterionText; sh:minCount 1; sh:datatype xsd:string ].
inv:NodeShape a sh:NodeShape; sh:targetClass inv:Node;
 sh:property [ sh:path inv:advertisesCapability; sh:minCount 1; sh:class inv:Capability ].
inv:RunShape a sh:NodeShape; sh:targetClass inv:Run;
 sh:property [ sh:path [ sh:inversePath inv:createsRun ]; sh:minCount 1; sh:maxCount 1; sh:class inv:Workload ];
 sh:property [ sh:path sv:status; sh:minCount 1; sh:maxCount 1; sh:in ("draft" "validated" "planned" "awaiting_approval" "scheduled" "running" "verifying" "recovering" "succeeded" "failed" "cancelled") ];
 sh:or ( [ sh:not [ sh:property [ sh:path sv:status; sh:hasValue "scheduled" ] ] ] [ sh:property [ sh:path inv:scheduledBy; sh:minCount 1; sh:maxCount 1 ] ] );
 sh:or ( [ sh:not [ sh:property [ sh:path sv:status; sh:hasValue "running" ] ] ] [ sh:property [ sh:path inv:holdsLease; sh:minCount 1; sh:class inv:ResourceLease ] ] );
 sh:or ( [ sh:not [ sh:property [ sh:path sv:status; sh:hasValue "succeeded" ] ] ] [ sh:property [ sh:path sec:hasEvidence; sh:minCount 1; sh:class sec:EvidenceEnvelope ]; sh:property [ sh:path sv:endedAt; sh:minCount 1; sh:datatype xsd:dateTime ] ] ).
inv:LeaseShape a sh:NodeShape; sh:targetClass inv:ResourceLease;
 sh:property [ sh:path [ sh:inversePath inv:holdsLease ]; sh:minCount 1; sh:maxCount 1; sh:class inv:Run ];
 sh:property [ sh:path inv:leasesResource; sh:minCount 1; sh:class inv:Resource ];
 sh:property [ sh:path inv:fencingToken; sh:minCount 1; sh:maxCount 1 ];
 sh:property [ sh:path inv:grantedAt; sh:minCount 1; sh:datatype xsd:dateTime; sh:lessThan inv:expiresAt ];
 sh:property [ sh:path inv:expiresAt; sh:minCount 1; sh:datatype xsd:dateTime ].
ml:LocationShape a sh:NodeShape; sh:targetClass ml:DataLocation;
 sh:or ( [ sh:not [ sh:property [ sh:path sv:status; sh:hasValue "ready" ] ] ] [ sh:property [ sh:path ml:checksum; sh:minCount 1; sh:pattern "^sha256:[0-9a-f]{64}$" ] ] ).
'''
(directory/'shapes.ttl').write_text(shapes,encoding='utf-8')
queries={
 'ownership.rq': '''SELECT ?task ?owner ?reviewer ?outcome WHERE { ?task a dev:DevelopmentTask; dev:ownedBy ?owner; dev:reviewedBy ?reviewer; dev:realizes ?outcome. }''',
 'dataset-locality.rq': '''SELECT ?node ?gpu ?location WHERE { ?dataset a ml:DatasetVersion; ml:hasLocation ?location. ?location inv:locatedOn ?node. ?node inv:offersResource ?offer. ?offer inv:describesResource ?gpu. ?gpu a inv:GPUResource. }''',
 'model-lineage.rq': '''SELECT ?model ?run ?dataset ?commit ?image WHERE { ?run ml:registersModel ?model; ml:consumesDataset ?dataset; dev:usesCommit ?commit; dev:usesImage ?image. }''',
 'retry-fencing.rq': '''SELECT ?run ?attempt ?checkpoint ?token WHERE { ?run inv:hasAttempt ?attempt; inv:holdsLease ?lease. ?attempt inv:hasCheckpoint ?checkpoint. ?lease inv:fencingToken ?token. }'''}
(directory/'queries').mkdir(exist_ok=True)
prefixes='\n'.join(f'PREFIX {p}: <{n}>' for p,n in namespaces.items())+'\n'
for filename,query in queries.items(): (directory/'queries'/filename).write_text(prefixes+query+'\n',encoding='utf-8')
(directory/'ONTOLOGY.md').write_text('''# Ontology 0.2.0

schema.ttl = TBox; example.ttl/example.jsonld = the same ABox; shapes.ttl = constraints. The ABox contains 48 development tasks with registry status and a synthetic runtime example. Synthetic IDs, checksums, resource values and times are fixtures, not observations.

Run `python tools/check_ontology.py` to check parsing, defined terms, graph equivalence, task registry alignment, SHACL valid/invalid examples and four competency queries. Product runtime invariants still require SQL, policy and integration tests.
''',encoding='utf-8')
# Export the new ontology without replacing archived source names.
mirror=root/'docs/vault/50_Ontology/Release-0.2.0'
for path in directory.rglob('*'):
    if path.is_file():
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').rstrip(b'\n') + b'\n')
        dest=mirror/path.relative_to(directory)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(path.read_bytes())
print(f'Ontology built: {len(tbox)} schema triples, {len(a)} data triples.')
